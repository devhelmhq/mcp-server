"""Monitor tools — HTTP, DNS, TCP, ICMP, MCP, and Heartbeat monitors."""

from __future__ import annotations

from typing import Any

from devhelm import DevhelmError
from devhelm.types import CreateMonitorRequest, UpdateMonitorRequest
from fastmcp import FastMCP
from pydantic import ValidationError

from devhelm_mcp.client import (
    ToolResult,
    format_error,
    format_validation_error,
    get_client,
    serialize,
    validate_body,
)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_monitors(api_token: str) -> ToolResult:
        """List all uptime monitors in the workspace."""
        try:
            return serialize(get_client(api_token).monitors.list())
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_monitor(api_token: str, monitor_id: str) -> ToolResult:
        """Get a single monitor by ID, including its full configuration."""
        try:
            return serialize(get_client(api_token).monitors.get(monitor_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_monitor(api_token: str, body: dict[str, Any]) -> ToolResult:
        """Create a new uptime monitor.

        Required fields: name, type (HTTP/DNS/TCP/ICMP/MCP/HEARTBEAT),
        config (type-specific), frequencySeconds (30-86400).
        """
        try:
            validate_body(body, CreateMonitorRequest)
            return serialize(get_client(api_token).monitors.create(body))
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_monitor(
        api_token: str, monitor_id: str, body: dict[str, Any]
    ) -> ToolResult:
        """Update an existing monitor's configuration."""
        try:
            validate_body(body, UpdateMonitorRequest)
            return serialize(get_client(api_token).monitors.update(monitor_id, body))
        except ValidationError as e:
            return format_validation_error(e)
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
    def pause_monitor(api_token: str, monitor_id: str) -> ToolResult:
        """Pause a monitor (stops checking until resumed)."""
        try:
            return serialize(get_client(api_token).monitors.pause(monitor_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def resume_monitor(api_token: str, monitor_id: str) -> ToolResult:
        """Resume a paused monitor."""
        try:
            return serialize(get_client(api_token).monitors.resume(monitor_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def test_monitor(api_token: str, monitor_id: str) -> ToolResult:
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
    ) -> ToolResult:
        """List recent check results for a monitor (cursor-paginated)."""
        try:
            page = get_client(api_token).monitors.results(
                monitor_id, cursor=cursor, limit=limit
            )
            return serialize({"data": page.data, "next_cursor": page.next_cursor})
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def list_monitor_versions(
        api_token: str, monitor_id: str, page: int = 0, size: int = 20
    ) -> ToolResult:
        """List version history for a monitor."""
        try:
            result = get_client(api_token).monitors.versions(
                monitor_id, page=page, size=size
            )
            return serialize({"data": result.data, "hasNext": result.has_next})
        except DevhelmError as e:
            return format_error(e)
