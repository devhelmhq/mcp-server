"""Webhook Testing tools — capture HTTP requests sent to inbox URLs.

Agent flow: ``create_webhook_inbox`` → point the system under test at the
returned ``httpUrl`` → ``wait_for_webhook_event`` (bounded) or poll
``get_latest_webhook_event`` → inspect headers and body.

Not offered here: deleting an inbox, deleting or clearing events (MCP
deletes need a confirmation step the API does not have yet), and raw body
downloads (binary; ``get_webhook_event`` returns the UTF-8 body, capped).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from devhelm import DevhelmError
from devhelm.resources.inboxes import InboxEvents, ListedEvent
from devhelm.types import CreateWebhookInboxRequest, UpdateWebhookInboxRequest
from fastmcp import FastMCP

from devhelm_mcp.client import ToolResult, as_payload, get_client, raise_tool_error
from devhelm_mcp.tools._inbound import (
    CREATE,
    READ_ONLY,
    UPDATE,
    WAIT,
    as_dict,
    bound_limit,
    cap_fields,
    plain,
    wait_ms,
)


def _event(event: ListedEvent) -> dict[str, Any]:
    data = as_dict(event)
    return cap_fields(data, ("body", "bodyPreview"), "bodyTruncated")


def _events(api_token: str | None, inbox_id: str) -> InboxEvents:
    return InboxEvents(get_client(api_token).inboxes, inbox_id)


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ_ONLY)
    def list_webhook_inboxes(
        search: str | None = None, api_token: str | None = None
    ) -> ToolResult:
        """List webhook testing inboxes in the workspace."""
        try:
            inboxes = get_client(api_token).inboxes.list(search=search)
            return [plain(inbox) for inbox in inboxes]
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=READ_ONLY)
    def get_webhook_inbox(inbox_id: str, api_token: str | None = None) -> ToolResult:
        """Get a webhook testing inbox, including its capture ``httpUrl``."""
        try:
            return as_dict(get_client(api_token).inboxes.get(inbox_id))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=CREATE)
    def create_webhook_inbox(
        body: CreateWebhookInboxRequest, api_token: str | None = None
    ) -> ToolResult:
        """Create a webhook testing inbox and return its capture ``httpUrl``.

        Required: name. Optional: status, httpResponse (mock reply), cors,
        retentionDays, maxEvents.
        """
        try:
            payload = as_payload(body)
            inbox = get_client(api_token).inboxes.create(
                name=payload["name"],
                status=payload.get("status"),
                http_response=payload.get("httpResponse"),
                cors=payload.get("cors"),
                retention_days=payload.get("retentionDays"),
                max_events=payload.get("maxEvents"),
            )
            return as_dict(inbox)
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=UPDATE)
    def update_webhook_inbox(
        inbox_id: str,
        body: UpdateWebhookInboxRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Update a webhook testing inbox (name, status, mock reply, limits)."""
        try:
            inbox = get_client(api_token).inboxes.update(inbox_id, as_payload(body))
            return as_dict(inbox)
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=READ_ONLY)
    def list_webhook_inbox_activity(
        inbox_ids: list[str], api_token: str | None = None
    ) -> ToolResult:
        """Hourly received-request counts for the last 24 h, per inbox ID."""
        try:
            rows = get_client(api_token).inboxes.activity(inbox_ids)
            return [plain(row) for row in rows]
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=WAIT)
    def wait_for_webhook_event(
        inbox_id: str,
        wait_s: int = 25,
        method: str | None = None,
        path_prefix: str | None = None,
        received_after: str | None = None,
        api_token: str | None = None,
    ) -> ToolResult:
        """Wait up to ``wait_s`` seconds (max 25) for a request to an inbox.

        Returns the oldest matching event with headers and body (body capped
        at 64 KB). Filter with ``method`` and ``path_prefix``. On timeout the
        tool errors; call it again or poll ``get_latest_webhook_event``.
        """
        try:
            http: dict[str, str] | None = None
            if method is not None or path_prefix is not None:
                http = {}
                if method is not None:
                    http["method"] = method
                if path_prefix is not None:
                    http["pathPrefix"] = path_prefix
            after = datetime.fromisoformat(received_after) if received_after else None
            event = get_client(api_token).inboxes.wait(
                inbox_id,
                timeout_ms=wait_ms(wait_s),
                received_after=after,
                http=http,
            )
            return _event(event)
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=READ_ONLY)
    def list_webhook_events(
        inbox_id: str,
        limit: int | None = None,
        cursor: str | None = None,
        method: str | None = None,
        path: str | None = None,
        api_token: str | None = None,
    ) -> ToolResult:
        """List requests captured by an inbox, newest first.

        ``limit`` defaults to 20 (max 50); pass ``nextCursor`` back as
        ``cursor`` for the next page. Rows carry a body preview only.
        """
        try:
            page = _events(api_token, inbox_id).list(
                cursor=cursor, limit=bound_limit(limit), method=method, path=path
            )
            return {
                "data": [_event(row) for row in page.data],
                "nextCursor": page.next_cursor,
                "hasMore": page.has_more,
            }
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=READ_ONLY)
    def get_latest_webhook_event(
        inbox_id: str, api_token: str | None = None
    ) -> ToolResult:
        """Get the newest request captured by an inbox without waiting.

        Returns ``{"event": null}`` when nothing has arrived yet.
        """
        try:
            events = _events(api_token, inbox_id)
            page = events.list(limit=1)
            if not page.data:
                return {"event": None}
            return {"event": _event(events.get(str(page.data[0].id)))}
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=READ_ONLY)
    def get_webhook_event(
        inbox_id: str, event_id: str, api_token: str | None = None
    ) -> ToolResult:
        """Get one captured request with headers and body (capped at 64 KB)."""
        try:
            return _event(_events(api_token, inbox_id).get(event_id))
        except DevhelmError as e:
            raise_tool_error(e)
