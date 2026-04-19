"""Status page management tools for the MCP server."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

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
    UpdateStatusPageComponentGroupRequest,
    UpdateStatusPageComponentRequest,
    UpdateStatusPageIncidentRequest,
    UpdateStatusPageRequest,
)
from fastmcp import FastMCP
from pydantic import BaseModel, Field, ValidationError

from devhelm_mcp.client import (
    ToolResult,
    format_error,
    format_validation_error,
    get_client,
    serialize,
    validate_body,
)


class _SpIncidentImpact(StrEnum):
    NONE = "NONE"
    MINOR = "MINOR"
    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"


class _SpIncidentStatus(StrEnum):
    INVESTIGATING = "INVESTIGATING"
    IDENTIFIED = "IDENTIFIED"
    MONITORING = "MONITORING"
    RESOLVED = "RESOLVED"


class PublishStatusPageIncidentRequest(BaseModel):
    """Local model matching the API's PublishStatusPageIncidentRequest.

    All fields are optional — null keeps the draft value.
    Defined locally because the published SDK (0.1.2) incorrectly marks
    these fields as required; remove once SDK is republished.
    """

    title: str | None = Field(None, max_length=500)
    impact: _SpIncidentImpact | None = None
    status: _SpIncidentStatus | None = None
    body: str | None = None
    affected_components: list[dict[str, Any]] | None = Field(
        None, alias="affectedComponents"
    )
    notify_subscribers: bool | None = Field(None, alias="notifySubscribers")


def _sp(api_token: str) -> StatusPages:
    """Return status_pages resource."""
    return get_client(api_token).status_pages


def register(mcp: FastMCP) -> None:
    # ── Page CRUD ─────────────────────────────────────────────────────────

    @mcp.tool()
    def list_status_pages(api_token: str) -> ToolResult:
        """List all status pages in the workspace."""
        try:
            return serialize(_sp(api_token).list())
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_status_page(api_token: str, page_id: str) -> ToolResult:
        """Get a status page by ID, including branding and overall status."""
        try:
            return serialize(_sp(api_token).get(page_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_status_page(api_token: str, body: dict[str, Any]) -> ToolResult:
        """Create a new status page.

        Required fields: name, slug.
        Optional: description, branding (brandColor, theme, headerStyle, etc.),
        visibility (PUBLIC/PASSWORD), enabled, incidentMode (MANUAL/REVIEW/AUTOMATIC).
        """
        try:
            validate_body(body, CreateStatusPageRequest)
            return serialize(_sp(api_token).create(body))
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_status_page(api_token: str, page_id: str, body: dict[str, Any]) -> ToolResult:
        """Update a status page's name, slug, branding, visibility, or incident mode."""
        try:
            validate_body(body, UpdateStatusPageRequest)
            return serialize(_sp(api_token).update(page_id, body))
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_status_page(api_token: str, page_id: str) -> str:
        """Delete a status page permanently."""
        try:
            _sp(api_token).delete(page_id)
            return "Status page deleted successfully."
        except DevhelmError as e:
            return format_error(e)

    # ── Components ────────────────────────────────────────────────────────

    @mcp.tool()
    def list_status_page_components(api_token: str, page_id: str) -> ToolResult:
        """List all components on a status page."""
        try:
            return serialize(_sp(api_token).components.list(page_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_status_page_component(
        api_token: str, page_id: str, body: dict[str, Any]
    ) -> ToolResult:
        """Add a component to a status page.

        Required fields: name, type (STATIC or MONITOR).
        Optional: groupId (nest under a group), monitorId (for MONITOR type).
        """
        try:
            validate_body(body, CreateStatusPageComponentRequest)
            return serialize(_sp(api_token).components.create(page_id, body))
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_status_page_component(
        api_token: str, page_id: str, component_id: str, body: dict[str, Any]
    ) -> ToolResult:
        """Update a status page component's name, group, or status."""
        try:
            validate_body(body, UpdateStatusPageComponentRequest)
            return serialize(
                _sp(api_token).components.update(page_id, component_id, body)
            )
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_status_page_component(
        api_token: str, page_id: str, component_id: str
    ) -> str:
        """Remove a component from a status page."""
        try:
            _sp(api_token).components.delete(page_id, component_id)
            return "Component deleted successfully."
        except DevhelmError as e:
            return format_error(e)

    # ── Component Groups ──────────────────────────────────────────────────

    @mcp.tool()
    def list_status_page_groups(api_token: str, page_id: str) -> ToolResult:
        """List component groups on a status page (with nested components)."""
        try:
            return serialize(_sp(api_token).groups.list(page_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_status_page_group(
        api_token: str, page_id: str, body: dict[str, Any]
    ) -> ToolResult:
        """Create a component group on a status page.

        Required fields: name.
        """
        try:
            validate_body(body, CreateStatusPageComponentGroupRequest)
            return serialize(_sp(api_token).groups.create(page_id, body))
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_status_page_group(
        api_token: str, page_id: str, group_id: str, body: dict[str, Any]
    ) -> ToolResult:
        """Update a component group's name or display order."""
        try:
            validate_body(body, UpdateStatusPageComponentGroupRequest)
            return serialize(_sp(api_token).groups.update(page_id, group_id, body))
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_status_page_group(api_token: str, page_id: str, group_id: str) -> str:
        """Delete a component group from a status page."""
        try:
            _sp(api_token).groups.delete(page_id, group_id)
            return "Component group deleted successfully."
        except DevhelmError as e:
            return format_error(e)

    # ── Incidents ─────────────────────────────────────────────────────────

    @mcp.tool()
    def list_status_page_incidents(
        api_token: str, page_id: str, page: int = 0, size: int = 20
    ) -> ToolResult:
        """List incidents on a status page (paginated)."""
        try:
            result = _sp(api_token).incidents.list(page_id, page=page, size=size)
            return serialize({"data": result.data, "hasNext": result.has_next})
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_status_page_incident(api_token: str, page_id: str, incident_id: str) -> ToolResult:
        """Get a status page incident with its full timeline of updates."""
        try:
            return serialize(_sp(api_token).incidents.get(page_id, incident_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_status_page_incident(
        api_token: str, page_id: str, body: dict[str, Any]
    ) -> ToolResult:
        """Create an incident on a status page.

        Required fields: title, impact (NONE/MINOR/MAJOR/CRITICAL).
        Optional: body, status (INVESTIGATING/IDENTIFIED/MONITORING/RESOLVED),
        affectedComponents (list of {componentId, status}).
        """
        try:
            validate_body(body, CreateStatusPageIncidentRequest)
            return serialize(_sp(api_token).incidents.create(page_id, body))
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_status_page_incident(
        api_token: str, page_id: str, incident_id: str, body: dict[str, Any]
    ) -> ToolResult:
        """Update a status page incident's title, impact, or status."""
        try:
            validate_body(body, UpdateStatusPageIncidentRequest)
            return serialize(
                _sp(api_token).incidents.update(page_id, incident_id, body)
            )
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def post_status_page_incident_update(
        api_token: str, page_id: str, incident_id: str, body: dict[str, Any]
    ) -> ToolResult:
        """Post a timeline update on a status page incident.

        Required fields: body (message text), status.
        Optional: notifySubscribers (default true),
        affectedComponents (list of {componentId, status}).
        """
        try:
            validate_body(body, CreateStatusPageIncidentUpdateRequest)
            return serialize(
                _sp(api_token).incidents.post_update(page_id, incident_id, body)
            )
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def publish_status_page_incident(
        api_token: str,
        page_id: str,
        incident_id: str,
        body: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Publish a draft incident (sets it live, notifies subscribers).

        Optional body fields: title, impact, status, body (overrides on publish),
        affectedComponents, notifySubscribers.
        """
        try:
            if body is not None:
                validate_body(body, PublishStatusPageIncidentRequest)
            return serialize(
                _sp(api_token).incidents.publish(page_id, incident_id, body)
            )
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def dismiss_status_page_incident(
        api_token: str, page_id: str, incident_id: str
    ) -> str:
        """Dismiss a draft incident (deletes it without publishing)."""
        try:
            _sp(api_token).incidents.dismiss(page_id, incident_id)
            return "Draft incident dismissed successfully."
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_status_page_incident(
        api_token: str, page_id: str, incident_id: str
    ) -> str:
        """Delete a status page incident permanently."""
        try:
            _sp(api_token).incidents.delete(page_id, incident_id)
            return "Status page incident deleted successfully."
        except DevhelmError as e:
            return format_error(e)

    # ── Subscribers ───────────────────────────────────────────────────────

    @mcp.tool()
    def list_status_page_subscribers(
        api_token: str, page_id: str, page: int = 0, size: int = 20
    ) -> ToolResult:
        """List confirmed subscribers on a status page (paginated)."""
        try:
            result = _sp(api_token).subscribers.list(page_id, page=page, size=size)
            return serialize({"data": result.data, "hasNext": result.has_next})
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def add_status_page_subscriber(
        api_token: str, page_id: str, body: dict[str, Any]
    ) -> ToolResult:
        """Add a subscriber to a status page (admin).

        Required fields: email.
        """
        try:
            validate_body(body, AdminAddSubscriberRequest)
            return serialize(_sp(api_token).subscribers.add(page_id, body))
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def remove_status_page_subscriber(
        api_token: str, page_id: str, subscriber_id: str
    ) -> str:
        """Remove a subscriber from a status page."""
        try:
            _sp(api_token).subscribers.remove(page_id, subscriber_id)
            return "Subscriber removed successfully."
        except DevhelmError as e:
            return format_error(e)

    # ── Custom Domains ────────────────────────────────────────────────────

    @mcp.tool()
    def list_status_page_domains(api_token: str, page_id: str) -> ToolResult:
        """List custom domains on a status page."""
        try:
            return serialize(_sp(api_token).domains.list(page_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def add_status_page_domain(
        api_token: str, page_id: str, body: dict[str, Any]
    ) -> ToolResult:
        """Add a custom domain to a status page.

        Required fields: hostname (e.g. "status.example.com").
        Returns verification records (CNAME target and TXT token) that must
        be configured in your DNS before calling verify.
        """
        try:
            validate_body(body, AddCustomDomainRequest)
            return serialize(_sp(api_token).domains.add(page_id, body))
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def verify_status_page_domain(api_token: str, page_id: str, domain_id: str) -> ToolResult:
        """Trigger DNS verification for a custom domain.

        Returns the updated domain with current verification status.
        """
        try:
            return serialize(_sp(api_token).domains.verify(page_id, domain_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def remove_status_page_domain(api_token: str, page_id: str, domain_id: str) -> str:
        """Remove a custom domain from a status page."""
        try:
            _sp(api_token).domains.remove(page_id, domain_id)
            return "Custom domain removed successfully."
        except DevhelmError as e:
            return format_error(e)
