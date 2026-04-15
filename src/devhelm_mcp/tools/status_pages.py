"""Status page tools — components, incidents, subscribers, and custom domains."""

from __future__ import annotations

from typing import Any

from devhelm import DevhelmError
from fastmcp import FastMCP

from devhelm_mcp.client import format_error, get_client, serialize


def register(mcp: FastMCP) -> None:
    # ── Page CRUD ─────────────────────────────────────────────────────────

    @mcp.tool()
    def list_status_pages(api_token: str) -> Any:
        """List all status pages in the workspace."""
        try:
            return serialize(get_client(api_token).status_pages.list())
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_status_page(api_token: str, page_id: str) -> Any:
        """Get a status page by ID, including branding and overall status."""
        try:
            return serialize(get_client(api_token).status_pages.get(page_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_status_page(api_token: str, body: dict[str, Any]) -> Any:
        """Create a new status page.

        Required fields: name, slug.
        Optional: description, branding (brandColor, theme, headerStyle, etc.),
        visibility (PUBLIC/PASSWORD), enabled, incidentMode (MANUAL/REVIEW/AUTOMATIC).
        """
        try:
            return serialize(get_client(api_token).status_pages.create(body))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_status_page(
        api_token: str, page_id: str, body: dict[str, Any]
    ) -> Any:
        """Update a status page's name, slug, branding, visibility, or incident mode."""
        try:
            return serialize(
                get_client(api_token).status_pages.update(page_id, body)
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_status_page(api_token: str, page_id: str) -> str:
        """Delete a status page permanently."""
        try:
            get_client(api_token).status_pages.delete(page_id)
            return "Status page deleted successfully."
        except DevhelmError as e:
            return format_error(e)

    # ── Components ────────────────────────────────────────────────────────

    @mcp.tool()
    def list_status_page_components(api_token: str, page_id: str) -> Any:
        """List all components on a status page."""
        try:
            return serialize(
                get_client(api_token).status_pages.components.list(page_id)
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_status_page_component(
        api_token: str, page_id: str, body: dict[str, Any]
    ) -> Any:
        """Add a component to a status page.

        Required fields: name, type (STATIC or MONITOR).
        Optional: groupId (nest under a group), monitorId (for MONITOR type).
        """
        try:
            return serialize(
                get_client(api_token).status_pages.components.create(page_id, body)
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_status_page_component(
        api_token: str, page_id: str, component_id: str, body: dict[str, Any]
    ) -> Any:
        """Update a status page component's name, group, or status."""
        try:
            return serialize(
                get_client(api_token).status_pages.components.update(
                    page_id, component_id, body
                )
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_status_page_component(
        api_token: str, page_id: str, component_id: str
    ) -> str:
        """Remove a component from a status page."""
        try:
            get_client(api_token).status_pages.components.delete(
                page_id, component_id
            )
            return "Component deleted successfully."
        except DevhelmError as e:
            return format_error(e)

    # ── Component Groups ──────────────────────────────────────────────────

    @mcp.tool()
    def list_status_page_groups(api_token: str, page_id: str) -> Any:
        """List component groups on a status page (with nested components)."""
        try:
            return serialize(
                get_client(api_token).status_pages.groups.list(page_id)
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_status_page_group(
        api_token: str, page_id: str, body: dict[str, Any]
    ) -> Any:
        """Create a component group on a status page.

        Required fields: name.
        """
        try:
            return serialize(
                get_client(api_token).status_pages.groups.create(page_id, body)
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_status_page_group(
        api_token: str, page_id: str, group_id: str, body: dict[str, Any]
    ) -> Any:
        """Update a component group's name or display order."""
        try:
            return serialize(
                get_client(api_token).status_pages.groups.update(
                    page_id, group_id, body
                )
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_status_page_group(
        api_token: str, page_id: str, group_id: str
    ) -> str:
        """Delete a component group from a status page."""
        try:
            get_client(api_token).status_pages.groups.delete(page_id, group_id)
            return "Component group deleted successfully."
        except DevhelmError as e:
            return format_error(e)

    # ── Incidents ─────────────────────────────────────────────────────────

    @mcp.tool()
    def list_status_page_incidents(
        api_token: str, page_id: str, page: int = 0, size: int = 20
    ) -> Any:
        """List incidents on a status page (paginated)."""
        try:
            result = get_client(api_token).status_pages.incidents.list(
                page_id, page=page, size=size
            )
            return serialize(
                {"data": result.data, "hasNext": result.has_next}
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_status_page_incident(
        api_token: str, page_id: str, incident_id: str
    ) -> Any:
        """Get a status page incident with its full timeline of updates."""
        try:
            return serialize(
                get_client(api_token).status_pages.incidents.get(
                    page_id, incident_id
                )
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_status_page_incident(
        api_token: str, page_id: str, body: dict[str, Any]
    ) -> Any:
        """Create an incident on a status page.

        Required fields: title, impact (NONE/MINOR/MAJOR/CRITICAL).
        Optional: body, status (INVESTIGATING/IDENTIFIED/MONITORING/RESOLVED),
        affectedComponents (list of {componentId, status}).
        """
        try:
            return serialize(
                get_client(api_token).status_pages.incidents.create(page_id, body)
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_status_page_incident(
        api_token: str, page_id: str, incident_id: str, body: dict[str, Any]
    ) -> Any:
        """Update a status page incident's title, impact, or status."""
        try:
            return serialize(
                get_client(api_token).status_pages.incidents.update(
                    page_id, incident_id, body
                )
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def post_status_page_incident_update(
        api_token: str, page_id: str, incident_id: str, body: dict[str, Any]
    ) -> Any:
        """Post a timeline update on a status page incident.

        Required fields: body (message text), status.
        Optional: notifySubscribers (default true),
        affectedComponents (list of {componentId, status}).
        """
        try:
            return serialize(
                get_client(api_token).status_pages.incidents.post_update(
                    page_id, incident_id, body
                )
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def publish_status_page_incident(
        api_token: str, page_id: str, incident_id: str,
        body: dict[str, Any] | None = None,
    ) -> Any:
        """Publish a draft incident (sets it live, notifies subscribers).

        Optional body fields: title, impact, status, body (overrides on publish).
        """
        try:
            return serialize(
                get_client(api_token).status_pages.incidents.publish(
                    page_id, incident_id, body
                )
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def dismiss_status_page_incident(
        api_token: str, page_id: str, incident_id: str
    ) -> str:
        """Dismiss a draft incident (deletes it without publishing)."""
        try:
            get_client(api_token).status_pages.incidents.dismiss(
                page_id, incident_id
            )
            return "Draft incident dismissed successfully."
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_status_page_incident(
        api_token: str, page_id: str, incident_id: str
    ) -> str:
        """Delete a status page incident permanently."""
        try:
            get_client(api_token).status_pages.incidents.delete(
                page_id, incident_id
            )
            return "Status page incident deleted successfully."
        except DevhelmError as e:
            return format_error(e)

    # ── Subscribers ───────────────────────────────────────────────────────

    @mcp.tool()
    def list_status_page_subscribers(
        api_token: str, page_id: str, page: int = 0, size: int = 20
    ) -> Any:
        """List confirmed subscribers on a status page (paginated)."""
        try:
            result = get_client(api_token).status_pages.subscribers.list(
                page_id, page=page, size=size
            )
            return serialize(
                {"data": result.data, "hasNext": result.has_next}
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def add_status_page_subscriber(
        api_token: str, page_id: str, body: dict[str, Any]
    ) -> Any:
        """Add a subscriber to a status page (admin).

        Required fields: email.
        """
        try:
            return serialize(
                get_client(api_token).status_pages.subscribers.add(page_id, body)
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def remove_status_page_subscriber(
        api_token: str, page_id: str, subscriber_id: str
    ) -> str:
        """Remove a subscriber from a status page."""
        try:
            get_client(api_token).status_pages.subscribers.remove(
                page_id, subscriber_id
            )
            return "Subscriber removed successfully."
        except DevhelmError as e:
            return format_error(e)

    # ── Custom Domains ────────────────────────────────────────────────────

    @mcp.tool()
    def list_status_page_domains(api_token: str, page_id: str) -> Any:
        """List custom domains on a status page."""
        try:
            return serialize(
                get_client(api_token).status_pages.domains.list(page_id)
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def add_status_page_domain(
        api_token: str, page_id: str, body: dict[str, Any]
    ) -> Any:
        """Add a custom domain to a status page.

        Required fields: hostname (e.g. "status.example.com").
        Returns verification records (CNAME target and TXT token) that must
        be configured in your DNS before calling verify.
        """
        try:
            return serialize(
                get_client(api_token).status_pages.domains.add(page_id, body)
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def verify_status_page_domain(
        api_token: str, page_id: str, domain_id: str
    ) -> Any:
        """Trigger DNS verification for a custom domain.

        Returns the updated domain with current verification status.
        """
        try:
            return serialize(
                get_client(api_token).status_pages.domains.verify(
                    page_id, domain_id
                )
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def remove_status_page_domain(
        api_token: str, page_id: str, domain_id: str
    ) -> str:
        """Remove a custom domain from a status page."""
        try:
            get_client(api_token).status_pages.domains.remove(
                page_id, domain_id
            )
            return "Custom domain removed successfully."
        except DevhelmError as e:
            return format_error(e)
