"""Alert channel tools — Slack, email, webhook, and other notification channels."""

from __future__ import annotations

from devhelm import DevhelmError
from devhelm.types import CreateAlertChannelRequest, UpdateAlertChannelRequest
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
    def list_alert_channels(api_token: str | None = None) -> ToolResult:
        """List all alert channels configured in the workspace."""
        try:
            return serialize(get_client(api_token).alert_channels.list())
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def get_alert_channel(channel_id: str, api_token: str | None = None) -> ToolResult:
        """Get an alert channel by ID."""
        try:
            return serialize(get_client(api_token).alert_channels.get(channel_id))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def create_alert_channel(
        body: CreateAlertChannelRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Create a new alert channel.

        Required: name, type, config (type-specific).
        Types: SLACK, EMAIL, WEBHOOK, PAGERDUTY, OPSGENIE,
        TELEGRAM, DISCORD, MSTEAMS.
        """
        try:
            return serialize(
                get_client(api_token).alert_channels.create(as_payload(body))
            )
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def update_alert_channel(
        channel_id: str,
        body: UpdateAlertChannelRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Update an existing alert channel."""
        try:
            return serialize(
                get_client(api_token).alert_channels.update(
                    channel_id, as_payload(body)
                )
            )
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def delete_alert_channel(channel_id: str, api_token: str | None = None) -> str:
        """Delete an alert channel."""
        try:
            get_client(api_token).alert_channels.delete(channel_id)
            return "Alert channel deleted successfully."
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def test_alert_channel(channel_id: str, api_token: str | None = None) -> ToolResult:
        """Send a test notification to an alert channel to verify it works."""
        try:
            return serialize(get_client(api_token).alert_channels.test(channel_id))
        except DevhelmError as e:
            raise_tool_error(e)
