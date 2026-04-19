"""Incident tools — manual and auto-detected incidents."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from devhelm import DevhelmError
from devhelm.types import CreateManualIncidentRequest
from fastmcp import FastMCP

from devhelm_mcp.client import (
    format_error,
    format_validation_error,
    get_client,
    serialize,
    validate_body,
)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_incidents(api_token: str) -> Any:
        """List all incidents in the workspace."""
        try:
            return serialize(get_client(api_token).incidents.list())
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_incident(api_token: str, incident_id: str) -> Any:
        """Get a single incident by ID with full details."""
        try:
            return serialize(get_client(api_token).incidents.get(incident_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_incident(api_token: str, body: dict[str, Any]) -> Any:
        """Create a manual incident.

        Required fields: monitorId, severity (CRITICAL/HIGH/MEDIUM/LOW).
        Optional: message.
        """
        try:
            validate_body(body, CreateManualIncidentRequest)
            return serialize(get_client(api_token).incidents.create(body))
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def resolve_incident(
        api_token: str, incident_id: str, message: str | None = None
    ) -> Any:
        """Resolve an active incident, optionally with a resolution message."""
        try:
            return serialize(
                get_client(api_token).incidents.resolve(incident_id, message)
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_incident(api_token: str, incident_id: str) -> str:
        """Delete an incident permanently."""
        try:
            get_client(api_token).incidents.delete(incident_id)
            return "Incident deleted successfully."
        except DevhelmError as e:
            return format_error(e)
