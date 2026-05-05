"""Status page management tools for the MCP server."""

from __future__ import annotations

from devhelm import DevhelmError
from devhelm.resources.status_pages import StatusPages
from devhelm.types import (
    AddCustomDomainRequest,
    AdminAddSubscriberRequest,
    CreateStatusPageComponentGroupRequest,
    CreateStatusPageComponentRequest,
    CreateStatusPageIncidentRequest,
    CreateStatusPageIncidentUpdateRequest,
    CreateStatusPageRequest,
    ReorderComponentsRequest,
    ReorderPageLayoutRequest,
    UpdateStatusPageComponentGroupRequest,
    UpdateStatusPageComponentRequest,
    UpdateStatusPageIncidentRequest,
    UpdateStatusPageRequest,
)
from fastmcp import FastMCP

from devhelm_mcp.client import (
    ToolResult,
    as_payload,
    get_client,
    raise_tool_error,
    serialize,
)


def _sp(api_token: str | None) -> StatusPages:
    """Return status_pages resource."""
    return get_client(api_token).status_pages


def register(mcp: FastMCP) -> None:
    # ── Page CRUD ─────────────────────────────────────────────────────────

    @mcp.tool()
    def list_status_pages(api_token: str | None = None) -> ToolResult:
        """List all status pages in the workspace."""
        try:
            return serialize(_sp(api_token).list())
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def get_status_page(page_id: str, api_token: str | None = None) -> ToolResult:
        """Get a status page by ID, including branding and overall status."""
        try:
            return serialize(_sp(api_token).get(page_id))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def create_status_page(
        body: CreateStatusPageRequest, api_token: str | None = None
    ) -> ToolResult:
        """Create a new status page.

        Required fields: name, slug.
        Optional: description, branding (brandColor, theme, headerStyle, etc.),
        visibility (PUBLIC/PASSWORD), enabled, incidentMode (MANUAL/REVIEW/AUTOMATIC).
        """
        try:
            return serialize(_sp(api_token).create(as_payload(body)))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def update_status_page(
        page_id: str,
        body: UpdateStatusPageRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Update a status page's name, slug, branding, visibility, or incident mode."""
        try:
            return serialize(_sp(api_token).update(page_id, as_payload(body)))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def delete_status_page(page_id: str, api_token: str | None = None) -> str:
        """Delete a status page permanently."""
        try:
            _sp(api_token).delete(page_id)
            return "Status page deleted successfully."
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def reorder_status_page_layout(
        page_id: str,
        body: ReorderPageLayoutRequest,
        api_token: str | None = None,
    ) -> str:
        """Batch-reorder a status page's full layout.

        Required: sections — top-level layout in their new order, where each
        entry is either {kind:"component", componentId} or
        {kind:"group", groupId}. Use ``groupOrders`` (optional) to also
        reorder components within specific groups; only include groups whose
        internal order changed. The full top-level set must be provided —
        partial reorders are rejected by the API.

        Use this for "drag-and-drop" layout edits that touch both groups and
        ungrouped components. To reorder components within a single group
        only, prefer ``reorder_status_page_components``.
        """
        try:
            _sp(api_token).reorder_layout(page_id, as_payload(body))
            return "Status page layout reordered successfully."
        except DevhelmError as e:
            raise_tool_error(e)

    # ── Components ────────────────────────────────────────────────────────

    @mcp.tool()
    def list_status_page_components(
        page_id: str, api_token: str | None = None
    ) -> ToolResult:
        """List all components on a status page."""
        try:
            return serialize(_sp(api_token).components.list(page_id))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def create_status_page_component(
        page_id: str,
        body: CreateStatusPageComponentRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Add a component to a status page.

        Required fields: name, type (STATIC or MONITOR).
        Optional: groupId (nest under a group), monitorId (for MONITOR type).
        """
        try:
            return serialize(
                _sp(api_token).components.create(page_id, as_payload(body))
            )
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def update_status_page_component(
        page_id: str,
        component_id: str,
        body: UpdateStatusPageComponentRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Update a status page component's name, group, or status."""
        try:
            return serialize(
                _sp(api_token).components.update(
                    page_id, component_id, as_payload(body)
                )
            )
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def delete_status_page_component(
        page_id: str,
        component_id: str,
        api_token: str | None = None,
    ) -> str:
        """Remove a component from a status page."""
        try:
            _sp(api_token).components.delete(page_id, component_id)
            return "Component deleted successfully."
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def reorder_status_page_components(
        page_id: str,
        body: ReorderComponentsRequest,
        api_token: str | None = None,
    ) -> str:
        """Reorder components on a status page.

        Required: positions — list of {componentId, position} entries giving
        every component its new zero-based ordinal. The full set must be
        provided; partial reorders are rejected by the API.
        """
        try:
            _sp(api_token).components.reorder(page_id, as_payload(body))
            return "Components reordered successfully."
        except DevhelmError as e:
            raise_tool_error(e)

    # ── Component Groups ──────────────────────────────────────────────────

    @mcp.tool()
    def list_status_page_groups(
        page_id: str, api_token: str | None = None
    ) -> ToolResult:
        """List component groups on a status page (with nested components)."""
        try:
            return serialize(_sp(api_token).groups.list(page_id))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def create_status_page_group(
        page_id: str,
        body: CreateStatusPageComponentGroupRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Create a component group on a status page.

        Required fields: name.
        """
        try:
            return serialize(_sp(api_token).groups.create(page_id, as_payload(body)))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def update_status_page_group(
        page_id: str,
        group_id: str,
        body: UpdateStatusPageComponentGroupRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Update a component group's name or display order."""
        try:
            return serialize(
                _sp(api_token).groups.update(page_id, group_id, as_payload(body))
            )
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def delete_status_page_group(
        page_id: str, group_id: str, api_token: str | None = None
    ) -> str:
        """Delete a component group from a status page."""
        try:
            _sp(api_token).groups.delete(page_id, group_id)
            return "Component group deleted successfully."
        except DevhelmError as e:
            raise_tool_error(e)

    # ── Incidents ─────────────────────────────────────────────────────────

    @mcp.tool()
    def list_status_page_incidents(
        page_id: str,
        page: int = 0,
        size: int = 20,
        api_token: str | None = None,
    ) -> ToolResult:
        """List incidents on a status page (paginated)."""
        try:
            result = _sp(api_token).incidents.list(page_id, page=page, size=size)
            return serialize({"data": result.data, "hasNext": result.has_next})
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def get_status_page_incident(
        page_id: str,
        incident_id: str,
        api_token: str | None = None,
    ) -> ToolResult:
        """Get a status page incident with its full timeline of updates."""
        try:
            return serialize(_sp(api_token).incidents.get(page_id, incident_id))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def create_status_page_incident(
        page_id: str,
        body: CreateStatusPageIncidentRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Create an incident on a status page.

        Required fields: title, impact (NONE/MINOR/MAJOR/CRITICAL).
        Optional: body, status (INVESTIGATING/IDENTIFIED/MONITORING/RESOLVED),
        affectedComponents (list of {componentId, status}).
        """
        try:
            return serialize(_sp(api_token).incidents.create(page_id, as_payload(body)))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def update_status_page_incident(
        page_id: str,
        incident_id: str,
        body: UpdateStatusPageIncidentRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Update a status page incident's title, impact, or status."""
        try:
            return serialize(
                _sp(api_token).incidents.update(page_id, incident_id, as_payload(body))
            )
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def post_status_page_incident_update(
        page_id: str,
        incident_id: str,
        body: CreateStatusPageIncidentUpdateRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Post a timeline update on a status page incident.

        Required fields: body (message text), status.
        Optional: notifySubscribers (default true),
        affectedComponents (list of {componentId, status}).
        """
        try:
            return serialize(
                _sp(api_token).incidents.post_update(
                    page_id, incident_id, as_payload(body)
                )
            )
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def publish_status_page_incident(
        page_id: str,
        incident_id: str,
        api_token: str | None = None,
    ) -> ToolResult:
        """Publish a draft incident (sets it live, notifies subscribers).

        Use update_status_page_incident first if you need to change the draft's
        title, impact, status, body, or affected components before publishing.
        """
        try:
            return serialize(_sp(api_token).incidents.publish(page_id, incident_id))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def dismiss_status_page_incident(
        page_id: str,
        incident_id: str,
        api_token: str | None = None,
    ) -> str:
        """Dismiss a draft incident (deletes it without publishing)."""
        try:
            _sp(api_token).incidents.dismiss(page_id, incident_id)
            return "Draft incident dismissed successfully."
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def delete_status_page_incident(
        page_id: str,
        incident_id: str,
        api_token: str | None = None,
    ) -> str:
        """Delete a status page incident permanently."""
        try:
            _sp(api_token).incidents.delete(page_id, incident_id)
            return "Status page incident deleted successfully."
        except DevhelmError as e:
            raise_tool_error(e)

    # ── Subscribers ───────────────────────────────────────────────────────

    @mcp.tool()
    def list_status_page_subscribers(
        page_id: str,
        page: int = 0,
        size: int = 20,
        api_token: str | None = None,
    ) -> ToolResult:
        """List confirmed subscribers on a status page (paginated)."""
        try:
            result = _sp(api_token).subscribers.list(page_id, page=page, size=size)
            return serialize({"data": result.data, "hasNext": result.has_next})
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def add_status_page_subscriber(
        page_id: str,
        body: AdminAddSubscriberRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Add a subscriber to a status page (admin).

        Required fields: email.
        """
        try:
            return serialize(_sp(api_token).subscribers.add(page_id, as_payload(body)))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def remove_status_page_subscriber(
        page_id: str,
        subscriber_id: str,
        api_token: str | None = None,
    ) -> str:
        """Remove a subscriber from a status page."""
        try:
            _sp(api_token).subscribers.remove(page_id, subscriber_id)
            return "Subscriber removed successfully."
        except DevhelmError as e:
            raise_tool_error(e)

    # ── Custom Domains ────────────────────────────────────────────────────

    @mcp.tool()
    def list_status_page_domains(
        page_id: str, api_token: str | None = None
    ) -> ToolResult:
        """List custom domains on a status page."""
        try:
            return serialize(_sp(api_token).domains.list(page_id))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def add_status_page_domain(
        page_id: str,
        body: AddCustomDomainRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Add a custom domain to a status page.

        Required fields: hostname (e.g. "status.example.com").
        Returns verification records (CNAME target and TXT token) that must
        be configured in your DNS before calling verify.
        """
        try:
            return serialize(_sp(api_token).domains.add(page_id, as_payload(body)))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def verify_status_page_domain(
        page_id: str,
        domain_id: str,
        api_token: str | None = None,
    ) -> ToolResult:
        """Trigger DNS verification for a custom domain.

        Returns the updated domain with current verification status.
        """
        try:
            return serialize(_sp(api_token).domains.verify(page_id, domain_id))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def remove_status_page_domain(
        page_id: str, domain_id: str, api_token: str | None = None
    ) -> str:
        """Remove a custom domain from a status page."""
        try:
            _sp(api_token).domains.remove(page_id, domain_id)
            return "Custom domain removed successfully."
        except DevhelmError as e:
            raise_tool_error(e)
