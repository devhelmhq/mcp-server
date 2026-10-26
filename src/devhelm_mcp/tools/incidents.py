"""Incident tools: manual and auto-detected incidents."""

from __future__ import annotations

from devhelm import (
    AcknowledgeAllIncidentsResponse,
    AddIncidentUpdateRequest,
    CreateManualIncidentRequest,
    IncidentActivityEventDto,
    IncidentDetailDto,
    IncidentDto,
    IncidentTriggerDto,
    RelatedIncidentsResponse,
    ResolveIncidentRequest,
    RunDto,
    UpdateIncidentRequest,
)
from fastmcp import FastMCP

from devhelm_mcp._models import CursorPageOut
from devhelm_mcp._tooling import READ, WRITE, WRITE_IDEMPOTENT, tool
from devhelm_mcp.client import get_client
from devhelm_mcp.tools.monitors import Limit


def register(mcp: FastMCP) -> None:
    @tool(mcp, READ)
    def list_incidents(api_token: str | None = None) -> list[IncidentDto]:
        """List all incidents in the workspace."""
        return get_client(api_token).incidents.list()

    @tool(mcp, READ)
    def get_incident(
        incident_id: str, api_token: str | None = None
    ) -> IncidentDetailDto:
        """Get one incident with its updates and affected monitors."""
        return get_client(api_token).incidents.get(incident_id)

    @tool(mcp, WRITE)
    def create_incident(
        body: CreateManualIncidentRequest, api_token: str | None = None
    ) -> IncidentDetailDto:
        """Create a manual incident (title, severity DOWN/DEGRADED/MAINTENANCE)."""
        return get_client(api_token).incidents.create(body)

    @tool(mcp, WRITE_IDEMPOTENT)
    def update_incident(
        incident_id: str, body: UpdateIncidentRequest, api_token: str | None = None
    ) -> IncidentDetailDto:
        """Change an incident's title, severity or other fields."""
        return get_client(api_token).incidents.update(incident_id, body)

    @tool(mcp, WRITE_IDEMPOTENT)
    def acknowledge_incident(
        incident_id: str, api_token: str | None = None
    ) -> AcknowledgeAllIncidentsResponse:
        """Acknowledge an incident (stops escalation)."""
        return get_client(api_token).incidents.acknowledge(incident_id)

    @tool(mcp, WRITE)
    def add_incident_update(
        incident_id: str, body: AddIncidentUpdateRequest, api_token: str | None = None
    ) -> IncidentDetailDto:
        """Post an update to an incident's timeline."""
        return get_client(api_token).incidents.add_update(incident_id, body)

    @tool(mcp, WRITE_IDEMPOTENT)
    def resolve_incident(
        incident_id: str, message: str | None = None, api_token: str | None = None
    ) -> IncidentDetailDto:
        """Resolve an active incident, optionally with a resolution message."""
        body = ResolveIncidentRequest(body=message) if message else None
        return get_client(api_token).incidents.resolve(incident_id, body)

    @tool(mcp, READ)
    def list_incident_runs(
        incident_id: str,
        cursor: str | None = None,
        limit: Limit = 20,
        api_token: str | None = None,
    ) -> CursorPageOut[RunDto]:
        """Code-check runs linked to an incident, newest first."""
        p = get_client(api_token).incidents.runs(
            incident_id, cursor=cursor, limit=limit
        )
        return CursorPageOut[RunDto](
            data=p.data, next_cursor=p.next_cursor, has_more=p.has_more
        )

    @tool(mcp, READ)
    def list_incident_events(
        incident_id: str,
        cursor: str | None = None,
        limit: Limit = 20,
        api_token: str | None = None,
    ) -> CursorPageOut[IncidentActivityEventDto]:
        """An incident's activity feed (state changes, updates, notifications)."""
        p = get_client(api_token).incidents.events(
            incident_id, cursor=cursor, limit=limit
        )
        return CursorPageOut[IncidentActivityEventDto](
            data=p.data, next_cursor=p.next_cursor, has_more=p.has_more
        )

    @tool(mcp, READ)
    def get_related_incidents(
        incident_id: str,
        window_days: int | None = None,
        limit: Limit = 20,
        api_token: str | None = None,
    ) -> RelatedIncidentsResponse:
        """Earlier incidents on the same monitors (recurrence check)."""
        return get_client(api_token).incidents.related(
            incident_id, window_days=window_days, limit=limit
        )

    @tool(mcp, READ)
    def get_incident_trigger(
        incident_id: str, api_token: str | None = None
    ) -> IncidentTriggerDto:
        """What opened the incident: the rule, the check and the run."""
        return get_client(api_token).incidents.trigger(incident_id)
