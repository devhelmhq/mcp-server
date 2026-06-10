"""Dependency tools — track third-party service dependencies."""

from __future__ import annotations

from typing import Any, cast

from devhelm import DevhelmError
from fastmcp import FastMCP

from devhelm_mcp.client import ToolResult, get_client, raise_tool_error, serialize


def _dependencies(api_token: str | None) -> Any:
    """Resolve the SDK's ``dependencies`` resource for the given token.

    The extended ``track(slug, component_id=, alert_sensitivity=)`` and the
    new ``update_alert_sensitivity`` ship in the parallel devhelm SDK
    release; until the pinned SDK includes them, the resource type is erased
    here (single seam) so ``mypy --strict`` accepts the agreed call
    signatures. The wire contract is pinned by ``tests/test_services.py``,
    and the SDK bump will make this cast a no-op.
    """
    return cast(Any, get_client(api_token)).dependencies


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_dependencies(api_token: str | None = None) -> ToolResult:
        """List all tracked service dependencies."""
        try:
            return serialize(get_client(api_token).dependencies.list())
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def get_dependency(dependency_id: str, api_token: str | None = None) -> ToolResult:
        """Get a tracked dependency by ID."""
        try:
            return serialize(get_client(api_token).dependencies.get(dependency_id))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def track_dependency(
        slug: str,
        component_id: str | None = None,
        alert_sensitivity: str | None = None,
        api_token: str | None = None,
    ) -> ToolResult:
        """Start tracking a service dependency by its slug (e.g. 'github', 'aws').

        Optionally track a single component via `component_id` (see
        list_service_components) and set `alert_sensitivity`: AWARENESS
        (silent tracking, default), INCIDENTS_ONLY, MAJOR_ONLY, or ALL."""
        try:
            return serialize(
                _dependencies(api_token).track(
                    slug,
                    component_id=component_id,
                    alert_sensitivity=alert_sensitivity,
                )
            )
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def update_dependency_alert_sensitivity(
        subscription_id: str,
        alert_sensitivity: str,
        api_token: str | None = None,
    ) -> ToolResult:
        """Change how loudly a tracked dependency alerts you.

        Levels: AWARENESS (silent tracking, default — status visible on the
        dashboard but no notifications), INCIDENTS_ONLY (notify on any
        incident), MAJOR_ONLY (notify only on major/critical incidents), and
        ALL (every status change, including maintenance)."""
        try:
            return serialize(
                _dependencies(api_token).update_alert_sensitivity(
                    subscription_id, alert_sensitivity
                )
            )
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def delete_dependency(dependency_id: str, api_token: str | None = None) -> str:
        """Stop tracking a service dependency."""
        try:
            get_client(api_token).dependencies.delete(dependency_id)
            return "Dependency removed successfully."
        except DevhelmError as e:
            raise_tool_error(e)
