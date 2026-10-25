"""Code revision tools: drafts, tests, files, diffs, publish and rollback."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from devhelm import (
    CreateDraftRevisionResponse,
    RevisionDiffDto,
    RevisionDto,
    RollbackPreviewDto,
    RunSessionContext,
)
from fastmcp import FastMCP

from devhelm_mcp import _confirm
from devhelm_mcp._models import (
    CodeFiles,
    ConfirmationRequired,
    Done,
    PageOut,
    Published,
    PublishPreview,
    RolledBack,
    RunEnvelope,
    TextFiles,
)
from devhelm_mcp._runs import envelope
from devhelm_mcp._tooling import (
    DESTRUCTIVE,
    DESTRUCTIVE_IDEMPOTENT,
    READ,
    TEXT_CAP_BYTES,
    WRITE,
    tool,
)
from devhelm_mcp.client import get_client, resolve_api_token
from devhelm_mcp.tools.monitors import Limit, WaitS, check_inline_size


def cap_files(entrypoint: str, files: dict[str, str], path: str | None) -> TextFiles:
    """Keep files (entrypoint first) until the text cap; name the rest."""
    if path is not None:
        files = {path: files[path]} if path in files else {}
    order = sorted(files, key=lambda p: (p != entrypoint, p))
    kept: dict[str, str] = {}
    omitted: list[str] = []
    used = 0
    for p in order:
        size = len(files[p].encode("utf-8")) + len(p)
        if used + size > TEXT_CAP_BYTES:
            omitted.append(p)
            continue
        kept[p] = files[p]
        used += size
    return TextFiles(
        entrypoint=entrypoint, files=kept, truncated=bool(omitted), omitted=omitted
    )


def _expires(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, UTC)


def register(mcp: FastMCP) -> None:
    @tool(mcp, READ)
    def list_monitor_revisions(
        monitor_id: str,
        state: str | None = None,
        page: int = 0,
        size: Limit = 20,
        api_token: str | None = None,
    ) -> PageOut[RevisionDto]:
        """Revisions newest first. ``state`` is a comma list of draft,
        tested_passed, tested_failed, live, previous, discarded or all
        (default live,previous)."""
        p = get_client(api_token).monitors.revisions.list(
            monitor_id, state=state, page=page, size=size
        )
        return PageOut[RevisionDto](
            data=p.data,
            has_next=p.has_next,
            has_prev=p.has_prev,
            total_elements=p.total_elements,
            total_pages=p.total_pages,
        )

    @tool(mcp, READ)
    def get_monitor_revision(
        monitor_id: str, revision_id: str, api_token: str | None = None
    ) -> RevisionDto:
        """One revision: state, digest, test result and who made it."""
        return get_client(api_token).monitors.revisions.get(monitor_id, revision_id)

    @tool(mcp, READ)
    def get_monitor_revision_files(
        monitor_id: str,
        revision_id: str,
        path: str | None = None,
        api_token: str | None = None,
    ) -> TextFiles:
        """A revision's source files as text (64 KB per call; ``omitted``
        lists the rest, fetch one with ``path``)."""
        f = get_client(api_token).monitors.revisions.files(monitor_id, revision_id)
        return cap_files(f.entrypoint, f.files, path)

    @tool(mcp, WRITE)
    def create_monitor_revision(
        monitor_id: str, code: CodeFiles, api_token: str | None = None
    ) -> CreateDraftRevisionResponse:
        """Save new code as a draft. Nothing goes live. Next:
        test_monitor_revision, then publish_monitor. Drafts with the same
        files are reused; at most 10 drafts (``evicted`` names one dropped)."""
        check_inline_size(code)
        return get_client(api_token).monitors.revisions.create(
            monitor_id, code=code.as_code()
        )

    @tool(mcp, WRITE)
    def test_monitor_revision(
        monitor_id: str,
        revision_id: str,
        region: str | None = None,
        session: RunSessionContext | None = None,
        wait_s: WaitS = 0,
        api_token: str | None = None,
    ) -> RunEnvelope:
        """Queue a validation run of a revision in the monitor's environment.
        Billed and saved, never alerts."""
        client = get_client(api_token)
        run = client.monitors.revisions.test(
            monitor_id, revision_id, region=region, session=session
        )
        return envelope(client, run, wait_s)

    @tool(mcp, READ)
    def diff_monitor_revisions(
        monitor_id: str,
        revision_id: str,
        other_revision_id: str | None = None,
        api_token: str | None = None,
    ) -> RevisionDiffDto:
        """Diff two revisions (default: against the live revision)."""
        return get_client(api_token).monitors.revisions.diff(
            monitor_id, revision_id, other_revision_id
        )

    @tool(mcp, DESTRUCTIVE_IDEMPOTENT)
    def discard_monitor_revision(
        monitor_id: str, revision_id: str, api_token: str | None = None
    ) -> Done:
        """Discard a draft. A live or once-live revision is refused."""
        get_client(api_token).monitors.revisions.discard(monitor_id, revision_id)
        return Done(message=f"Draft {revision_id} discarded.")

    @tool(mcp, DESTRUCTIVE)
    def publish_monitor(
        monitor_id: str,
        revision_id: str,
        expected_live_revision_id: str | None = None,
        require_tested: bool | None = None,
        note: str | None = None,
        confirmation_token: str | None = None,
        api_token: str | None = None,
    ) -> ConfirmationRequired[PublishPreview] | Published:
        """Make a revision live. The first call returns
        ``confirmation_required`` with the changes: show them to the user,
        ask, then call again with ``confirmation_token`` (valid 15 min).
        ``expected_live_revision_id`` refuses the publish if someone
        published in between."""
        client = get_client(api_token)
        caller = resolve_api_token(api_token)
        args = {
            "monitor_id": monitor_id,
            "revision_id": revision_id,
            "expected_live_revision_id": expected_live_revision_id,
            "require_tested": require_tested,
            "note": note,
        }
        if confirmation_token is None:
            monitor = client.monitors.get(monitor_id)
            revision = client.monitors.revisions.get(monitor_id, revision_id)
            token, expires = _confirm.issue("publish_monitor", args, monitor_id, caller)
            return ConfirmationRequired[PublishPreview](
                changes=[
                    f"Revision {revision.id} ({revision.state}) becomes live on "
                    f"'{monitor.name}', replacing {monitor.live_revision_id}",
                    "Scheduled runs and alerts use the new code from now on",
                ],
                preview=PublishPreview(monitor=monitor, revision=revision),
                confirmation_token=token,
                expires_at=_expires(expires),
                next_action="Ask the user to confirm, then call publish_monitor "
                "again with the same arguments and confirmation_token.",
            )
        _confirm.verify(confirmation_token, "publish_monitor", args, monitor_id, caller)
        head = client.monitors.publish(
            monitor_id,
            revision_id=UUID(revision_id),
            expected_live_revision_id=(
                UUID(expected_live_revision_id) if expected_live_revision_id else None
            ),
            require_tested=require_tested,
            note=note,
        )
        return Published(head=head)

    @tool(mcp, READ)
    def preview_rollback_monitor(
        monitor_id: str,
        revision_id: str | None = None,
        api_token: str | None = None,
    ) -> RollbackPreviewDto:
        """What a rollback would restore (default: the revision live before)."""
        return get_client(api_token).monitors.rollback_preview(
            monitor_id, revision_id=revision_id
        )

    @tool(mcp, DESTRUCTIVE)
    def rollback_monitor(
        monitor_id: str,
        reason: str,
        revision_id: str | None = None,
        emergency: bool | None = None,
        expected_live_revision_id: str | None = None,
        confirmation_token: str | None = None,
        api_token: str | None = None,
    ) -> ConfirmationRequired[RollbackPreviewDto] | RolledBack:
        """Restore a previous revision (default: the one live before).
        The first call returns ``confirmation_required`` with the rollback
        preview: show it to the user, ask, then call again with
        ``confirmation_token`` (valid 15 min)."""
        client = get_client(api_token)
        caller = resolve_api_token(api_token)
        args = {
            "monitor_id": monitor_id,
            "reason": reason,
            "revision_id": revision_id,
            "emergency": emergency,
            "expected_live_revision_id": expected_live_revision_id,
        }
        if confirmation_token is None:
            preview = client.monitors.rollback_preview(
                monitor_id, revision_id=revision_id
            )
            token, expires = _confirm.issue(
                "rollback_monitor", args, monitor_id, caller
            )
            return ConfirmationRequired[RollbackPreviewDto](
                changes=[
                    f"Roll monitor {monitor_id} back to "
                    f"{revision_id or 'the revision live before'}: {reason}",
                    "Scheduled runs and alerts use the restored code from now on",
                ],
                preview=preview,
                confirmation_token=token,
                expires_at=_expires(expires),
                next_action="Ask the user to confirm, then call rollback_monitor "
                "again with the same arguments and confirmation_token.",
            )
        _confirm.verify(
            confirmation_token, "rollback_monitor", args, monitor_id, caller
        )
        head = client.monitors.rollback(
            monitor_id,
            reason=reason,
            revision_id=UUID(revision_id) if revision_id else None,
            emergency=emergency,
            expected_live_revision_id=(
                UUID(expected_live_revision_id) if expected_live_revision_id else None
            ),
        )
        return RolledBack(head=head)
