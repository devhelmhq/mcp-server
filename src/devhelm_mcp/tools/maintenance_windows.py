"""Maintenance window tools — schedule downtime so deploys don't page on-call.

These tools let an AI agent proactively suppress alerts before running a
risky operation (a database migration, a deploy, a third-party API
maintenance) and then clear the suppression once the operation succeeds.
The flow that ships value to users looks like:

    1. agent calls ``create_maintenance_window(...)`` before kicking off
       a deploy script
    2. the deploy runs (monitors may briefly fail — alerts stay silent)
    3. on success the agent calls ``cancel_maintenance_window(...)`` so
       new failures page on-call again
    4. on a runaway deploy the agent calls ``update_maintenance_window``
       to push the end time back instead of letting the window expire
       and pages flood the channel

The underlying ``client.maintenance_windows`` resource is being added to
the Python SDK in a parallel PR. Until that lands and a new SDK release
is published, the tools below call the generated request/response models
through the SDK's existing low-level HTTP helpers — same wire contract,
same telemetry headers, same auth resolution. Once
``client.maintenance_windows.create(...)`` ships we can swap the bodies
of these tools to use it; the public tool surface stays unchanged.
"""

from __future__ import annotations

from typing import Any

import httpx
from devhelm import DevhelmError

# The maintenance-window models live in ``devhelm._generated`` — they
# haven't been re-exported through ``devhelm.types`` yet (that's part of
# the SDK PR that adds ``client.maintenance_windows``). Reaching into
# ``_generated`` is the documented workaround for surfaces that need a
# resource ahead of its SDK release. Once the SDK ships the public
# re-exports, switch these imports to ``from devhelm.types import ...``.
from devhelm._generated import (
    CreateMaintenanceWindowRequest,
    MaintenanceWindowDto,
    UpdateMaintenanceWindowRequest,
)
from devhelm._http import api_delete, api_get, api_post, api_put, path_param
from devhelm._validation import parse_list, parse_single
from fastmcp import FastMCP

from devhelm_mcp.client import (
    ToolResult,
    get_client,
    raise_tool_error,
    serialize,
)

_BASE_PATH = "/api/v1/maintenance-windows"


def _http_client(api_token: str | None) -> httpx.Client:
    """Resolve the SDK's configured ``httpx.Client``.

    ``Devhelm.__init__`` builds exactly one ``httpx.Client`` (auth
    header, tenant headers, telemetry headers, base URL, timeout) and
    shares it across every resource. Reaching into
    ``client.monitors._client`` reuses that same instance instead of
    duplicating the env-resolution + header-building logic on the MCP
    side. This is a deliberate, narrow workaround until the SDK ships
    a public ``client.maintenance_windows`` resource — at which point
    every tool here collapses to a one-liner against that resource.
    """
    return get_client(api_token).monitors._client


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_maintenance_windows(
        monitor_id: str | None = None,
        status: str | None = None,
        api_token: str | None = None,
    ) -> ToolResult:
        """List maintenance windows for the workspace.

        Use this BEFORE creating a new window to check whether someone
        else (or an earlier agent run) already scheduled overlap, or
        AFTER a deploy to confirm the window you opened is still
        active.

        Filters (all optional; combine freely):
          - ``monitor_id``: UUID of a monitor — only windows attached
            to that single monitor (org-wide windows are excluded).
          - ``status``: ``"active"`` for windows currently in
            progress, or ``"upcoming"`` for windows scheduled in the
            future. Past / cancelled windows are not returned by the
            API today; omit ``status`` for the broadest result.
        """
        try:
            params: dict[str, Any] = {}
            if monitor_id:
                params["monitorId"] = monitor_id
            if status:
                params["filter"] = status
            data = api_get(
                _http_client(api_token),
                _BASE_PATH,
                params=params or None,
            )
            # The API returns a ``TableValueResult<MaintenanceWindowDto>``
            # envelope (``{data: [...], hasNext, hasPrev, …}``). The list
            # is small enough in practice (per-org, active + upcoming
            # only) that the controller doesn't paginate today, so we
            # surface the ``data`` array directly. If the controller
            # ever starts honouring ``page``/``size``, swap this for
            # ``fetch_all_pages`` once the SDK ships
            # ``client.maintenance_windows``.
            items = data.get("data", []) if isinstance(data, dict) else (data or [])
            windows = parse_list(MaintenanceWindowDto, items, f"GET {_BASE_PATH}")
            return serialize(windows)
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def get_maintenance_window(
        window_id: str, api_token: str | None = None
    ) -> ToolResult:
        """Get a single maintenance window by ID with full details."""
        try:
            data = api_get(
                _http_client(api_token),
                f"{_BASE_PATH}/{path_param(window_id)}",
            )
            return serialize(
                parse_single(
                    MaintenanceWindowDto,
                    data,
                    f"GET {_BASE_PATH}/{window_id}",
                )
            )
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def create_maintenance_window(
        body: CreateMaintenanceWindowRequest, api_token: str | None = None
    ) -> ToolResult:
        """Schedule a maintenance window to suppress alerts during planned work.

        Call this BEFORE running an operation that may legitimately
        cause monitors to fail — a deploy, a database migration, a
        third-party service's announced downtime — so the on-call
        rotation isn't paged for known-expected failures. Always
        pair every successful create with a follow-up
        ``cancel_maintenance_window`` once the operation finishes;
        if the operation runs long, call ``update_maintenance_window``
        to push the end time back rather than letting the window
        lapse early.

        Time fields use ISO 8601 / RFC 3339 timestamps with explicit
        timezone — UTC strongly preferred. Example:
        ``"2026-05-15T14:00:00Z"``. Naive timestamps (no timezone)
        are rejected by the API.

        Body fields:
          - ``startsAt`` (required): when the window opens.
          - ``endsAt`` (required): when the window closes; must be
            strictly after ``startsAt``.
          - ``monitorId`` (optional): UUID of a single monitor to
            scope the window to. Omit (or set null) to make this an
            **org-wide window** that suppresses alerts on every
            monitor in the workspace — the right choice for a deploy
            or migration that touches the whole platform.
          - ``reason`` (optional): human-readable explanation
            ("v0.7.3 deploy", "Postgres major upgrade"). Surfaces in
            the dashboard and on-call channel; keep it specific.
          - ``repeatRule`` (optional): iCal RRULE string for
            recurring windows (max 100 chars), e.g.
            ``FREQ=WEEKLY;BYDAY=SU`` for weekly Sunday maintenance.
            Omit for one-time windows.
          - ``suppressAlerts`` (optional): whether the window
            actually silences alerts. Default ``true``; set
            ``false`` to record a maintenance window for audit
            without changing alerting behavior.
        """
        try:
            # Pass the validated Pydantic model straight to ``api_post``;
            # the SDK's ``_serialize_body`` does ``model_dump(mode="json",
            # by_alias=True, exclude_none=True)`` which is the canonical
            # camelCase / RFC-3339 wire shape. Dicts are intentionally
            # rejected by ``api_post`` (P5: no raw-dict request bodies),
            # so handing it the model also catches a future regression
            # where ``body`` is downgraded to ``dict[str, Any]``.
            data = api_post(_http_client(api_token), _BASE_PATH, body)
            return serialize(
                parse_single(
                    MaintenanceWindowDto,
                    data,
                    f"POST {_BASE_PATH}",
                )
            )
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def update_maintenance_window(
        window_id: str,
        body: UpdateMaintenanceWindowRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Update an in-flight or scheduled maintenance window.

        The most common use is **extending** an active window when a
        deploy runs longer than expected — call this with the new
        ``endsAt`` to keep alerts suppressed past the original
        deadline. The endpoint is a full replacement (PUT, not
        PATCH): pass the complete intended state, not a delta.
        Any field omitted falls back to the underlying model's
        default rather than preserving the existing value.

        Time fields use ISO 8601 / RFC 3339 timestamps with explicit
        timezone (UTC preferred), e.g. ``"2026-05-15T16:30:00Z"``.

        Body fields (same schema as create):
          - ``startsAt`` (required)
          - ``endsAt`` (required)
          - ``monitorId`` (optional; null = org-wide)
          - ``reason`` (optional; null clears)
          - ``repeatRule`` (optional; null clears the recurrence)
          - ``suppressAlerts`` (optional)
        """
        try:
            data = api_put(
                _http_client(api_token),
                f"{_BASE_PATH}/{path_param(window_id)}",
                body,
            )
            return serialize(
                parse_single(
                    MaintenanceWindowDto,
                    data,
                    f"PUT {_BASE_PATH}/{window_id}",
                )
            )
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def cancel_maintenance_window(window_id: str, api_token: str | None = None) -> str:
        """Cancel a maintenance window — alerts resume immediately.

        Call this AFTER a deploy or maintenance operation completes
        successfully so any new monitor failures surface as real
        incidents instead of being silently absorbed. If the window
        was scheduled but not yet started, this prevents it from
        ever opening.

        The window record is removed; the audit log preserves the
        historical fact that the window existed. There is no
        "uncancel" — schedule a new window if you need to restore
        suppression.
        """
        try:
            api_delete(
                _http_client(api_token),
                f"{_BASE_PATH}/{path_param(window_id)}",
            )
            return "Maintenance window cancelled."
        except DevhelmError as e:
            raise_tool_error(e)
