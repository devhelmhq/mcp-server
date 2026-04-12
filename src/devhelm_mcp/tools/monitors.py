"""Monitor tools — HTTP, DNS, TCP, ICMP, MCP, and Heartbeat monitors."""

from __future__ import annotations

from typing import Any

from devhelm import DevhelmError
from fastmcp import FastMCP

from devhelm_mcp.client import format_error, get_client, serialize


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_monitors(api_token: str) -> Any:
        """List all uptime monitors in the workspace."""
        try:
            return serialize(get_client(api_token).monitors.list())
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_monitor(api_token: str, monitor_id: str) -> Any:
        """Get a single monitor by ID, including its full configuration."""
        try:
            return serialize(get_client(api_token).monitors.get(monitor_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_monitor(api_token: str, body: dict[str, Any]) -> Any:
        """Create a new uptime monitor.

        Required fields: name, type (HTTP/DNS/TCP/ICMP/MCP/HEARTBEAT),
        config (type-specific), frequencySeconds (30-86400).
        """
        try:
            return serialize(get_client(api_token).monitors.create(body))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_monitor(api_token: str, monitor_id: str, body: dict[str, Any]) -> Any:
        """Update an existing monitor's configuration."""
        try:
            return serialize(get_client(api_token).monitors.update(monitor_id, body))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_monitor(api_token: str, monitor_id: str) -> str:
        """Delete a monitor permanently."""
        try:
            get_client(api_token).monitors.delete(monitor_id)
            return "Monitor deleted successfully."
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def pause_monitor(api_token: str, monitor_id: str) -> Any:
        """Pause a monitor (stops checking until resumed)."""
        try:
            return serialize(get_client(api_token).monitors.pause(monitor_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def resume_monitor(api_token: str, monitor_id: str) -> Any:
        """Resume a paused monitor."""
        try:
            return serialize(get_client(api_token).monitors.resume(monitor_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def test_monitor(api_token: str, monitor_id: str) -> Any:
        """Trigger an ad-hoc test run for a monitor and return the result."""
        try:
            return serialize(get_client(api_token).monitors.test(monitor_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def list_monitor_results(
        api_token: str,
        monitor_id: str,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> Any:
        """List recent check results for a monitor (cursor-paginated)."""
        try:
            page = get_client(api_token).monitors.results(
                monitor_id, cursor=cursor, limit=limit
            )
            return serialize({"items": page.items, "next_cursor": page.next_cursor})
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def list_monitor_versions(
        api_token: str, monitor_id: str, page: int = 0, size: int = 20
    ) -> Any:
        """List version history for a monitor."""
        try:
            result = get_client(api_token).monitors.versions(
                monitor_id, page=page, size=size
            )
            return serialize(
                {"items": result.items, "page": result.page, "total": result.total}
            )
        except DevhelmError as e:
            return format_error(e)
