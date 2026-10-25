"""Monitor tools: uptime probes and code checks (BROWSER, MULTI_STEP_API).

Code checks follow one lifecycle (doc 42 §1): create (revision 1 is live) →
change code as a draft → test it → publish. Files are passed inline
(``code: {entrypoint, files}``); the server never reads a filesystem.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from devhelm import (
    CreateMonitorRequest,
    MonitorDriftDto,
    MonitorDto,
    MonitorHistoryEntryDto,
    MonitorOverlayRequest,
    MonitorTestRequest,
    MonitorTestResultDto,
    MonitorVersionDto,
    QuarantineMonitorRequest,
    RunSessionContext,
    UpdateMonitorRequest,
)
from devhelm._authoring import (
    CodeMonitorType,
    UptimeMonitorType,
    deprecated,
    is_code_type,
)
from devhelm._errors import client_error
from devhelm._generated import ManagedBy
from fastmcp import FastMCP
from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from devhelm_mcp import _confirm
from devhelm_mcp._models import (
    MAX_INLINE_CODE_BYTES,
    CodeFiles,
    ConfirmationRequired,
    CursorPageOut,
    Deleted,
    PageOut,
    ProbeResult,
    RunEnvelope,
    TriggerEnvelope,
)
from devhelm_mcp._runs import MAX_WAIT_S, envelope, trigger_envelope
from devhelm_mcp._tooling import (
    DESTRUCTIVE,
    READ,
    WRITE,
    WRITE_IDEMPOTENT,
    tool,
)
from devhelm_mcp.client import get_client, resolve_api_token

# Wire value of ``ManagedBy.MCP``: the server always attributes MCP writes.
_MCP_MANAGED_BY = "MCP"

#: ``monitors.test()`` on an uptime monitor returns the probe until then (R16).
PROBE_ALIAS_UNTIL = datetime(2027, 1, 31, tzinfo=UTC)

WaitS = Annotated[
    int,
    Field(
        ge=0,
        le=MAX_WAIT_S,
        description="Seconds to wait for the run to finish (0–25). The tool "
        "never blocks longer; poll get_run for more",
    ),
]
Limit = Annotated[int, Field(ge=1, le=100, description="Page size (1–100)")]


class McpCreateMonitorRequest(CreateMonitorRequest):
    """``CreateMonitorRequest`` without ``managedBy`` (always ``MCP``) and
    ``code`` (pass files in the tool's ``code`` argument)."""

    managed_by: SkipJsonSchema[ManagedBy | None] = Field(
        default=None, alias="managedBy", exclude=True
    )
    code: SkipJsonSchema[None] = Field(default=None, exclude=True)


class McpUpdateMonitorRequest(UpdateMonitorRequest):
    """``UpdateMonitorRequest`` without ``managedBy`` and ``code``."""

    managed_by: SkipJsonSchema[ManagedBy | None] = Field(
        default=None, alias="managedBy", exclude=True
    )
    code: SkipJsonSchema[None] = Field(default=None, exclude=True)


class McpMonitorTestRequest(MonitorTestRequest):
    """``MonitorTestRequest`` without ``code`` (inline files go in ``code``)."""

    code: SkipJsonSchema[None] = Field(default=None, exclude=True)


_CODE_TYPES: dict[str, CodeMonitorType] = {
    "BROWSER": "BROWSER",
    "MULTI_STEP_API": "MULTI_STEP_API",
}
_UPTIME_TYPES: dict[str, UptimeMonitorType] = {
    "HTTP": "HTTP",
    "DNS": "DNS",
    "MCP_SERVER": "MCP_SERVER",
    "TCP": "TCP",
    "ICMP": "ICMP",
    "HEARTBEAT": "HEARTBEAT",
}


def check_inline_size(code: CodeFiles) -> None:
    total = sum(len(v.encode("utf-8")) for v in code.files.values())
    if total > MAX_INLINE_CODE_BYTES:
        raise client_error(
            "validation",
            "BUNDLE_TOO_LARGE",
            f"Inline files total {total} bytes; one tool call takes at most "
            f"{MAX_INLINE_CODE_BYTES} bytes. Trim fixtures or split data files.",
            field="code.files",
        )


def _overlay(reason: str | None, expires_at: datetime | None) -> MonitorOverlayRequest:
    return MonitorOverlayRequest(reason=reason, expires_at=expires_at)


def register(mcp: FastMCP) -> None:
    # -- read ---------------------------------------------------------------

    @tool(mcp, READ)
    def list_monitors(
        name: str | None = None,
        environment: str | None = None,
        type: str | None = None,
        search: str | None = None,
        api_token: str | None = None,
    ) -> list[MonitorDto]:
        """List monitors. ``name`` is an exact, case-sensitive match;
        ``environment`` is a slug or id; ``search`` is a substring."""
        return get_client(api_token).monitors.list(
            name=name, environment=environment, type=type, search=search
        )

    @tool(mcp, READ)
    def get_monitor(monitor_id: str, api_token: str | None = None) -> MonitorDto:
        """Get one monitor, including its config and liveRevisionId."""
        return get_client(api_token).monitors.get(monitor_id)

    @tool(mcp, READ)
    def get_monitor_drift(
        monitor_id: str, api_token: str | None = None
    ) -> MonitorDriftDto:
        """How the live monitor differs from what was last applied from code."""
        return get_client(api_token).monitors.drift(monitor_id)

    @tool(mcp, READ)
    def list_monitor_versions(
        monitor_id: str,
        page: int = 0,
        size: Limit = 20,
        api_token: str | None = None,
    ) -> PageOut[MonitorVersionDto]:
        """Settings history of a monitor, newest first."""
        p = get_client(api_token).monitors.versions.list(
            monitor_id, page=page, size=size
        )
        return PageOut[MonitorVersionDto](
            data=p.data,
            has_next=p.has_next,
            has_prev=p.has_prev,
            total_elements=p.total_elements,
            total_pages=p.total_pages,
        )

    @tool(mcp, READ)
    def get_monitor_version(
        monitor_id: str, version: int, api_token: str | None = None
    ) -> MonitorVersionDto:
        """One settings snapshot by version number."""
        return get_client(api_token).monitors.versions.get(monitor_id, version)

    def _history(
        monitor_id: str, cursor: str | None, limit: int, api_token: str | None
    ) -> CursorPageOut[MonitorHistoryEntryDto]:
        p = get_client(api_token).monitors.history.list(
            monitor_id, cursor=cursor, limit=limit
        )
        return CursorPageOut[MonitorHistoryEntryDto](
            data=p.data, next_cursor=p.next_cursor, has_more=p.has_more
        )

    @tool(mcp, READ)
    def list_monitor_history(
        monitor_id: str,
        cursor: str | None = None,
        limit: Limit = 20,
        api_token: str | None = None,
    ) -> CursorPageOut[MonitorHistoryEntryDto]:
        """What happened to a monitor over time (probe results and code runs).
        Pass ``nextCursor`` as ``cursor`` for the next page."""
        return _history(monitor_id, cursor, limit, api_token)

    @tool(mcp, READ)
    def list_monitor_results(
        monitor_id: str,
        cursor: str | None = None,
        limit: Limit = 20,
        api_token: str | None = None,
    ) -> CursorPageOut[MonitorHistoryEntryDto]:
        """Deprecated since 1.9 (removed 2027-01-31): use list_monitor_history.
        Same result."""
        deprecated("list_monitor_results", "list_monitor_history")
        return _history(monitor_id, cursor, limit, api_token)

    @tool(mcp, READ)
    def list_monitor_trash(
        page: int = 0,
        size: Limit = 20,
        api_token: str | None = None,
    ) -> PageOut[MonitorDto]:
        """Deleted monitors, restorable with restore_monitor."""
        p = get_client(api_token).monitors.trash.list_page(page, size)
        return PageOut[MonitorDto](
            data=p.data,
            has_next=p.has_next,
            has_prev=p.has_prev,
            total_elements=p.total_elements,
            total_pages=p.total_pages,
        )

    # -- write --------------------------------------------------------------

    @tool(mcp, WRITE)
    def create_monitor(
        body: McpCreateMonitorRequest,
        code: CodeFiles | None = None,
        environment: str | None = None,
        api_token: str | None = None,
    ) -> MonitorDto:
        """Create a monitor. Types: HTTP, DNS, TCP, ICMP, HEARTBEAT, MCP_SERVER,
        BROWSER, MULTI_STEP_API.

        Code types (BROWSER, MULTI_STEP_API) need ``code`` (inline files) and
        an environment (``environment`` slug or ``body.environmentId``).
        Revision 1 goes live at once and the monitor runs right away. Next:
        test_monitor to see it run. ``managedBy`` is always MCP.
        """
        if code is not None:
            check_inline_size(code)
        payload = body.model_dump(by_alias=True, exclude_none=True)
        payload["managedBy"] = _MCP_MANAGED_BY
        return get_client(api_token).monitors.create(
            payload,
            code=code.as_code() if code is not None else None,
            environment=environment,
        )

    @tool(mcp, WRITE_IDEMPOTENT)
    def update_monitor(
        monitor_id: str,
        body: McpUpdateMonitorRequest,
        code: CodeFiles | None = None,
        api_token: str | None = None,
    ) -> MonitorDto:
        """Update a monitor's settings. With ``code`` the new code goes live
        in one call, untested; prefer create_monitor_revision →
        test_monitor_revision → publish_monitor to test first."""
        if code is not None:
            check_inline_size(code)
        return get_client(api_token).monitors.update(
            monitor_id,
            body.model_dump(by_alias=True, exclude_none=True),
            code=code.as_code() if code is not None else None,
        )

    @tool(mcp, DESTRUCTIVE)
    def delete_monitor(
        monitor_id: str,
        confirmation_token: str | None = None,
        api_token: str | None = None,
    ) -> ConfirmationRequired[MonitorDto] | Deleted:
        """Move a monitor to Trash. The first call returns
        ``confirmation_required`` with the changes: show them to the user,
        ask, then call again with ``confirmation_token`` (valid 15 min)."""
        client = get_client(api_token)
        caller = resolve_api_token(api_token)
        args = {"monitor_id": monitor_id}
        if confirmation_token is None:
            monitor = client.monitors.get(monitor_id)
            token, expires = _confirm.issue("delete_monitor", args, monitor_id, caller)
            return ConfirmationRequired[MonitorDto](
                changes=[
                    f"Move {monitor.type} monitor '{monitor.name}' ({monitor.id}) "
                    "to Trash; it stops running and alerting",
                    "restore_monitor brings it back until Trash is purged",
                ],
                preview=monitor,
                confirmation_token=token,
                expires_at=datetime.fromtimestamp(expires, UTC),
                next_action="Ask the user to confirm, then call delete_monitor "
                "again with confirmation_token.",
            )
        _confirm.verify(confirmation_token, "delete_monitor", args, monitor_id, caller)
        client.monitors.delete(monitor_id)
        return Deleted(
            monitor_id=monitor_id,
            next_action="Moved to Trash. restore_monitor undoes it.",
        )

    @tool(mcp, WRITE_IDEMPOTENT)
    def restore_monitor(
        monitor_id: str,
        environment: str | None = None,
        api_token: str | None = None,
    ) -> MonitorDto:
        """Restore a monitor from Trash (optionally into another environment)."""
        return get_client(api_token).monitors.restore(
            monitor_id, environment=environment
        )

    @tool(mcp, WRITE_IDEMPOTENT)
    def pause_monitor(
        monitor_id: str,
        reason: str | None = None,
        expires_at: datetime | None = None,
        api_token: str | None = None,
    ) -> MonitorDto:
        """Pause scheduled runs until resume_monitor (or ``expires_at``)."""
        return get_client(api_token).monitors.pause(
            monitor_id, _overlay(reason, expires_at)
        )

    @tool(mcp, WRITE_IDEMPOTENT)
    def resume_monitor(monitor_id: str, api_token: str | None = None) -> MonitorDto:
        """Resume a paused monitor."""
        return get_client(api_token).monitors.resume(monitor_id)

    @tool(mcp, WRITE_IDEMPOTENT)
    def mute_monitor(
        monitor_id: str,
        reason: str | None = None,
        expires_at: datetime | None = None,
        api_token: str | None = None,
    ) -> MonitorDto:
        """Stop alert delivery; the monitor keeps running."""
        return get_client(api_token).monitors.mute(
            monitor_id, _overlay(reason, expires_at)
        )

    @tool(mcp, WRITE_IDEMPOTENT)
    def unmute_monitor(monitor_id: str, api_token: str | None = None) -> MonitorDto:
        """Deliver alerts again."""
        return get_client(api_token).monitors.unmute(monitor_id)

    @tool(mcp, WRITE_IDEMPOTENT)
    def quarantine_monitor(
        monitor_id: str,
        body: QuarantineMonitorRequest,
        api_token: str | None = None,
    ) -> MonitorDto:
        """Hold a flaky monitor out of alerting (``reason`` required)."""
        return get_client(api_token).monitors.quarantine(monitor_id, body)

    @tool(mcp, WRITE_IDEMPOTENT)
    def release_quarantine_monitor(
        monitor_id: str, api_token: str | None = None
    ) -> MonitorDto:
        """End a quarantine early."""
        return get_client(api_token).monitors.release_quarantine(monitor_id)

    # -- runs ---------------------------------------------------------------

    @tool(mcp, WRITE)
    def test_monitor(
        monitor_id: str,
        code: CodeFiles | None = None,
        region: str | None = None,
        session: RunSessionContext | None = None,
        wait_s: WaitS = 0,
        api_token: str | None = None,
    ) -> RunEnvelope | ProbeResult:
        """Queue a validation run of a code monitor in its own environment.

        Billed and saved, never alerts. With ``code`` it tests those files
        instead of the live revision. Waits up to ``wait_s`` (≤25); poll
        get_run after that.

        On an uptime monitor it returns the probe result until 2027-01-31
        (deprecated): use probe_monitor for those.
        """
        client = get_client(api_token)
        monitor = client.monitors.get(monitor_id)
        if not is_code_type(str(monitor.type)):
            if datetime.now(UTC) >= PROBE_ALIAS_UNTIL:
                raise client_error(
                    "validation",
                    "USE_PROBE",
                    "This is an uptime monitor; test_monitor runs code checks.",
                    next_command="probe_monitor",
                )
            deprecated("test_monitor on an uptime monitor", "probe_monitor")
            return ProbeResult(
                probe=client.monitors.probe(monitor_id),
                deprecation="test_monitor on an uptime monitor is deprecated "
                "(removed 2027-01-31); call probe_monitor",
            )
        if code is not None:
            check_inline_size(code)
        run = client.monitors.test(
            monitor_id,
            code=code.as_code() if code is not None else None,
            region=region,
            session=session,
        )
        return envelope(client, run, wait_s)

    @tool(mcp, READ)
    def probe_monitor(
        monitor_id: str, api_token: str | None = None
    ) -> MonitorTestResultDto:
        """Probe an uptime monitor once and return the result. Nothing is
        saved. Code monitors: use test_monitor."""
        return get_client(api_token).monitors.probe(monitor_id)

    @tool(mcp, WRITE)
    def test_monitor_adhoc(
        body: McpMonitorTestRequest,
        code: CodeFiles | None = None,
        environment: str | None = None,
        wait_s: WaitS = 0,
        api_token: str | None = None,
    ) -> RunEnvelope | MonitorTestResultDto:
        """Test code or a probe config without creating a monitor.

        BROWSER / MULTI_STEP_API: pass ``code`` and an environment
        (``environment`` slug or ``body.environmentId``); returns a billed
        validation run. Uptime types: ``body.config`` (+ assertions); returns
        the probe result.
        """
        client = get_client(api_token)
        env = environment or (str(body.environment_id) if body.environment_id else None)
        kind = body.type.value
        code_kind = _CODE_TYPES.get(kind)
        if code_kind is not None:
            if code is None:
                raise client_error(
                    "validation",
                    "FIELD_REQUIRED",
                    f"A {kind} test needs code (inline files).",
                    field="code",
                )
            if env is None:
                raise client_error(
                    "validation",
                    "FIELD_REQUIRED",
                    f"A {kind} test needs an environment (slug or id).",
                    field="environment",
                )
            check_inline_size(code)
            run = client.monitors.test_adhoc(
                type=code_kind,
                environment=env,
                code=code.as_code(),
                config=body.config,
                region=body.region,
                session=body.session,
            )
            return envelope(client, run, wait_s)
        return client.monitors.test_adhoc(
            type=_UPTIME_TYPES[kind],
            config=body.config,
            environment=env,
            assertions=body.assertions,
        )

    @tool(mcp, WRITE)
    def run_monitor_now(
        monitor_id: str,
        wait_s: WaitS = 0,
        api_token: str | None = None,
    ) -> RunEnvelope:
        """Run a code monitor once in its first region now (works when
        paused). Recorded and billed; never votes on health."""
        client = get_client(api_token)
        return envelope(client, client.monitors.run_now(monitor_id), wait_s)

    @tool(mcp, WRITE)
    def trigger_monitor(
        monitor_id: str,
        regions: list[str] | None = None,
        signal: bool | None = None,
        session: RunSessionContext | None = None,
        wait_s: WaitS = 0,
        api_token: str | None = None,
    ) -> TriggerEnvelope:
        """Run a code monitor now in several regions (default: all configured).

        Billed one run per region. Never alerts unless ``signal`` is true.
        Code monitors only.
        """
        client = get_client(api_token)
        started = client.monitors.trigger(
            monitor_id, regions=regions, signal=signal, session=session
        )
        return trigger_envelope(client, started, wait_s)
