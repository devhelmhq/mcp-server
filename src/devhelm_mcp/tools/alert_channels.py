"""Alert channel tools — Slack, email, webhook, and other notification channels."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from devhelm import DevhelmError
from devhelm.types import CreateAlertChannelRequest, UpdateAlertChannelRequest
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
    def list_alert_channels(api_token: str) -> Any:
        """List all alert channels configured in the workspace."""
        try:
            return serialize(get_client(api_token).alert_channels.list())
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_alert_channel(api_token: str, channel_id: str) -> Any:
        """Get an alert channel by ID."""
        try:
            return serialize(get_client(api_token).alert_channels.get(channel_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_alert_channel(api_token: str, body: dict[str, Any]) -> Any:
        """Create a new alert channel.

        Required: name, type, config (type-specific).
        Types: SLACK, EMAIL, WEBHOOK, PAGERDUTY, OPSGENIE,
        TELEGRAM, DISCORD, MSTEAMS.
        """
        try:
            validate_body(body, CreateAlertChannelRequest)
            return serialize(get_client(api_token).alert_channels.create(body))
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_alert_channel(
        api_token: str, channel_id: str, body: dict[str, Any]
    ) -> Any:
        """Update an existing alert channel."""
        try:
            validate_body(body, UpdateAlertChannelRequest)
            return serialize(
                get_client(api_token).alert_channels.update(channel_id, body)
            )
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_alert_channel(api_token: str, channel_id: str) -> str:
        """Delete an alert channel."""
        try:
            get_client(api_token).alert_channels.delete(channel_id)
            return "Alert channel deleted successfully."
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def test_alert_channel(api_token: str, channel_id: str) -> Any:
        """Send a test notification to an alert channel to verify it works."""
        try:
            return serialize(get_client(api_token).alert_channels.test(channel_id))
        except DevhelmError as e:
            return format_error(e)
