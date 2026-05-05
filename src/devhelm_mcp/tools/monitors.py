"""Monitor tools — HTTP, DNS, TCP, ICMP, MCP, and Heartbeat monitors."""

from __future__ import annotations

from typing import Any

from devhelm import DevhelmError
from devhelm.types import CreateMonitorRequest, UpdateMonitorRequest
from fastmcp import FastMCP
from pydantic import Field

from devhelm_mcp.client import (
    ToolResult,
    as_payload,
    get_client,
    raise_tool_error,
    serialize,
)

# Wire-format value of ``ManagedBy.MCP``. Hard-coded as a string (rather than
# pulled from ``devhelm.types.ManagedBy``) because the SDK enum may lag behind
# the API enum during the spec-sync release window — the API is the source of
# truth for the value, and pinning the literal here keeps the MCP server
# attribution working even when the SDK rebuild hasn't shipped yet.
_MCP_MANAGED_BY = "MCP"


class _McpCreateMonitorRequest(CreateMonitorRequest):
    """``CreateMonitorRequest`` with ``managed_by`` hidden from MCP callers.

    The MCP server *always* sets ``managedBy="MCP"`` on the API call so the
    dashboard can attribute the monitor to its real origin (an AI agent),
    rather than letting the LLM thread an arbitrary value through. This
    subclass:

    1. Re-declares ``managed_by`` as optional (``default=None``) so a body
       that omits it passes Pydantic validation — the parent class makes the
       field required, which would force the LLM to set it.
    2. Marks the field with ``exclude=True`` so any value the LLM does
       smuggle in via a permissive client never reaches ``model_dump()``.
       The server-side ``managedBy`` injection in :func:`create_monitor` is
       the only writer that survives the boundary.

    The field is also stripped from the JSON Schema FastMCP advertises (see
    ``server.py`` post-registration step), so well-behaved LLMs never see
    ``managedBy`` as a callable parameter at all.
    """

    managed_by: Any = Field(default=None, alias="managedBy", exclude=True)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_monitors(api_token: str | None = None) -> ToolResult:
        """List all uptime monitors in the workspace."""
        try:
            return serialize(get_client(api_token).monitors.list())
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def get_monitor(monitor_id: str, api_token: str | None = None) -> ToolResult:
        """Get a single monitor by ID, including its full configuration."""
        try:
            return serialize(get_client(api_token).monitors.get(monitor_id))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def create_monitor(
        body: _McpCreateMonitorRequest, api_token: str | None = None
    ) -> ToolResult:
        """Create a new uptime monitor.

        Required fields: name, type (HTTP/DNS/TCP/ICMP/MCP/HEARTBEAT),
        config (type-specific), frequencySeconds (30-86400).

        ``managedBy`` is set automatically to ``MCP`` server-side; callers
        cannot override it. Use the SDK or CLI directly if you need a
        different attribution.
        """
        try:
            payload = as_payload(body)
            # Belt-and-suspenders: even if a permissive client manages to
            # smuggle ``managedBy`` past the schema strip, drop it before
            # the SDK call so server-side attribution is *guaranteed*.
            payload.pop("managedBy", None)
            payload.pop("managed_by", None)
            payload["managedBy"] = _MCP_MANAGED_BY
            return serialize(get_client(api_token).monitors.create(payload))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def update_monitor(
        monitor_id: str,
        body: UpdateMonitorRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Update an existing monitor's configuration."""
        try:
            return serialize(
                get_client(api_token).monitors.update(monitor_id, as_payload(body))
            )
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def delete_monitor(monitor_id: str, api_token: str | None = None) -> str:
        """Delete a monitor permanently."""
        try:
            get_client(api_token).monitors.delete(monitor_id)
            return "Monitor deleted successfully."
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def pause_monitor(monitor_id: str, api_token: str | None = None) -> ToolResult:
        """Pause a monitor (stops checking until resumed)."""
        try:
            return serialize(get_client(api_token).monitors.pause(monitor_id))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def resume_monitor(monitor_id: str, api_token: str | None = None) -> ToolResult:
        """Resume a paused monitor."""
        try:
            return serialize(get_client(api_token).monitors.resume(monitor_id))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def test_monitor(monitor_id: str, api_token: str | None = None) -> ToolResult:
        """Trigger an ad-hoc test run for a monitor and return the result."""
        try:
            return serialize(get_client(api_token).monitors.test(monitor_id))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def list_monitor_results(
        monitor_id: str,
        cursor: str | None = None,
        limit: int | None = None,
        api_token: str | None = None,
    ) -> ToolResult:
        """List recent check results for a monitor (cursor-paginated)."""
        try:
            page = get_client(api_token).monitors.results(
                monitor_id, cursor=cursor, limit=limit
            )
            return serialize({"data": page.data, "next_cursor": page.next_cursor})
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def list_monitor_versions(
        monitor_id: str,
        page: int = 0,
        size: int = 20,
        api_token: str | None = None,
    ) -> ToolResult:
        """List version history for a monitor."""
        try:
            result = get_client(api_token).monitors.versions(
                monitor_id, page=page, size=size
            )
            return serialize({"data": result.data, "hasNext": result.has_next})
        except DevhelmError as e:
            raise_tool_error(e)
