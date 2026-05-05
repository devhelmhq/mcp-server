"""Dependency tools — track third-party service dependencies."""

from __future__ import annotations

from devhelm import DevhelmError
from fastmcp import FastMCP

from devhelm_mcp.client import ToolResult, format_error, get_client, serialize


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_dependencies(api_token: str | None = None) -> ToolResult:
        """List all tracked service dependencies."""
        try:
            return serialize(get_client(api_token).dependencies.list())
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_dependency(dependency_id: str, api_token: str | None = None) -> ToolResult:
        """Get a tracked dependency by ID."""
        try:
            return serialize(get_client(api_token).dependencies.get(dependency_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def track_dependency(slug: str, api_token: str | None = None) -> ToolResult:
        """Start tracking a service dependency by its slug (e.g. 'github', 'aws')."""
        try:
            return serialize(get_client(api_token).dependencies.track(slug))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_dependency(dependency_id: str, api_token: str | None = None) -> str:
        """Stop tracking a service dependency."""
        try:
            get_client(api_token).dependencies.delete(dependency_id)
            return "Dependency removed successfully."
        except DevhelmError as e:
            return format_error(e)
