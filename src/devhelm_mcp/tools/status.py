"""Status tools — dashboard overview."""

from __future__ import annotations

from devhelm import DevhelmError
from fastmcp import FastMCP

from devhelm_mcp.client import ToolResult, get_client, raise_tool_error, serialize


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def get_status_overview(api_token: str | None = None) -> ToolResult:
        """Get the dashboard overview with monitor counts,
        incident summary, and uptime stats."""
        try:
            return serialize(get_client(api_token).status.overview())
        except DevhelmError as e:
            raise_tool_error(e)
