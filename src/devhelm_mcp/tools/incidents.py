"""Incident tools — manual and auto-detected incidents."""

from __future__ import annotations

from devhelm import DevhelmError
from devhelm.types import CreateManualIncidentRequest, ResolveIncidentRequest
from fastmcp import FastMCP

from devhelm_mcp.client import (
    ToolResult,
    as_payload,
    get_client,
    raise_tool_error,
    serialize,
)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_incidents(api_token: str | None = None) -> ToolResult:
        """List all incidents in the workspace."""
        try:
            return serialize(get_client(api_token).incidents.list())
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def get_incident(incident_id: str, api_token: str | None = None) -> ToolResult:
        """Get a single incident by ID with full details."""
        try:
            return serialize(get_client(api_token).incidents.get(incident_id))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def create_incident(
        body: CreateManualIncidentRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Create a manual incident.

        Required fields: title, severity (DOWN/DEGRADED/MAINTENANCE).
        Optional: monitorId (UUID), body (detailed description).
        """
        try:
            return serialize(get_client(api_token).incidents.create(as_payload(body)))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def resolve_incident(
        incident_id: str,
        message: str | None = None,
        api_token: str | None = None,
    ) -> ToolResult:
        """Resolve an active incident, optionally with a resolution message."""
        try:
            body = ResolveIncidentRequest(body=message) if message else None
            payload = as_payload(body) if body is not None else None
            return serialize(
                get_client(api_token).incidents.resolve(incident_id, payload)
            )
        except DevhelmError as e:
            raise_tool_error(e)
