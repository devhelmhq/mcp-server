"""Service catalog tools — browse third-party services and their status."""

from __future__ import annotations

from typing import Any, cast

from devhelm import DevhelmError
from fastmcp import FastMCP

from devhelm_mcp.client import ToolResult, get_client, raise_tool_error, serialize


def _services(api_token: str | None) -> Any:
    """Resolve the SDK's ``services`` resource for the given token.

    The ``client.services`` resource ships in the parallel devhelm SDK
    release; until the pinned SDK includes it, the resource type is erased
    here (single seam) so ``mypy --strict`` accepts the agreed call
    signatures. The wire contract is pinned by ``tests/test_services.py``,
    and the SDK bump will make this cast a no-op.
    """
    return cast(Any, get_client(api_token)).services


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def search_services(
        query: str | None = None,
        category: str | None = None,
        limit: int = 20,
        api_token: str | None = None,
    ) -> ToolResult:
        """Search the catalog of third-party services (Stripe, GitHub, AWS, ...)
        that can be tracked as dependencies.

        Use `query` for free-text search by name (e.g. 'stripe', 'cloudflare')
        and `category` to filter by catalog category (see
        list_service_categories). Results are paginated; raise `limit`
        (default 20) for broader sweeps."""
        try:
            return serialize(
                _services(api_token).list(search=query, category=category, limit=limit)
            )
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def get_service(slug: str, api_token: str | None = None) -> ToolResult:
        """Get a catalog service's summary by slug (e.g. 'github'), including
        its current status, categories, and component overview."""
        try:
            return serialize(_services(api_token).get(slug, summary=True))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def get_service_live_status(slug: str, api_token: str | None = None) -> ToolResult:
        """Get the live (real-time) operational status of a catalog service,
        fetched from its upstream status page. Use this when freshness matters
        more than latency — e.g. 'is Stripe down right now?'."""
        try:
            return serialize(_services(api_token).live_status(slug))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def get_services_summary(api_token: str | None = None) -> ToolResult:
        """Get the global status summary across the entire service catalog —
        counts of operational / degraded / outage services. Use this for a
        quick 'is anything broken on the internet right now?' overview before
        drilling into a specific service."""
        try:
            return serialize(_services(api_token).summary())
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def list_service_categories(api_token: str | None = None) -> ToolResult:
        """List all service catalog categories (e.g. cloud, payments, devtools)
        usable as the `category` filter in search_services."""
        try:
            return serialize(_services(api_token).categories())
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def list_service_components(slug: str, api_token: str | None = None) -> ToolResult:
        """List a catalog service's components (e.g. 'API', 'Dashboard',
        'Webhooks') with their individual statuses. Component IDs can be used
        to track a single component via track_dependency."""
        try:
            return serialize(_services(api_token).components(slug))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def get_service_uptime(
        slug: str, period: str = "30d", api_token: str | None = None
    ) -> ToolResult:
        """Get historical uptime stats for a catalog service over a period
        (e.g. '7d', '30d', '90d'; default '30d')."""
        try:
            return serialize(_services(api_token).uptime(slug, period=period))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def list_service_incidents(
        slug: str | None = None,
        status: str | None = None,
        api_token: str | None = None,
    ) -> ToolResult:
        """List incidents for a catalog service, or across all services when
        `slug` is omitted. Filter by `status` (e.g. 'active', 'resolved') to
        answer questions like 'which of my dependencies have open incidents?'."""
        try:
            return serialize(
                _services(api_token).incidents(slug_or_id=slug, status=status)
            )
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def get_service_incident(
        slug: str, incident_id: str, api_token: str | None = None
    ) -> ToolResult:
        """Get one vendor incident in full detail, including the vendor's
        timeline of status updates (investigating → identified → resolved).
        Get incident IDs from list_service_incidents."""
        try:
            return serialize(_services(api_token).incident(slug, incident_id))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def get_service_day_rollup(
        slug: str, date: str, api_token: str | None = None
    ) -> ToolResult:
        """Get a one-day rollup for a catalog service on a UTC calendar day
        (ISO YYYY-MM-DD): aggregated uptime, per-component impact windows,
        and the incidents that overlapped that day. Use this to answer
        'what happened to Stripe on 2026-06-01?'."""
        try:
            return serialize(_services(api_token).day(slug, date))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def get_component_uptime(
        slug: str,
        component_id: str,
        period: str = "30d",
        api_token: str | None = None,
    ) -> ToolResult:
        """Get daily uptime history for a single component of a catalog
        service (e.g. just the 'API' component of Stripe) over a period
        ('7d', '30d', '90d', '1y'; default '30d'). Get component IDs from
        list_service_components."""
        try:
            return serialize(
                _services(api_token).component_uptime(slug, component_id, period=period)
            )
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def get_all_components_uptime(
        slug: str, period: str = "30d", api_token: str | None = None
    ) -> ToolResult:
        """Get daily uptime history for every leaf component of a catalog
        service in one call, keyed by component ID, over a period ('7d',
        '30d', '90d', '1y'; default '30d'). Prefer this over repeated
        get_component_uptime calls when comparing components."""
        try:
            return serialize(
                _services(api_token).batch_component_uptime(slug, period=period)
            )
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def list_service_maintenances(
        slug: str, api_token: str | None = None
    ) -> ToolResult:
        """List scheduled and past maintenance windows announced by a catalog
        service (e.g. upcoming AWS maintenance that could affect you)."""
        try:
            return serialize(_services(api_token).maintenances(slug))
        except DevhelmError as e:
            raise_tool_error(e)
