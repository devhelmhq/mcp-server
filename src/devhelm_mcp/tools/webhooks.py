"""Webhook tools — outgoing webhook endpoint management."""

from __future__ import annotations

from devhelm import DevhelmError
from devhelm.types import CreateWebhookEndpointRequest, UpdateWebhookEndpointRequest
from fastmcp import FastMCP

from devhelm_mcp.client import (
    ToolResult,
    as_payload,
    format_error,
    get_client,
    serialize,
)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_webhooks(api_token: str) -> ToolResult:
        """List all webhook endpoints in the workspace."""
        try:
            return serialize(get_client(api_token).webhooks.list())
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_webhook(api_token: str, webhook_id: str) -> ToolResult:
        """Get a webhook endpoint by ID."""
        try:
            return serialize(get_client(api_token).webhooks.get(webhook_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_webhook(
        api_token: str, body: CreateWebhookEndpointRequest
    ) -> ToolResult:
        """Create a webhook endpoint.

        Required fields: url, events (list of event types to subscribe to).
        """
        try:
            return serialize(get_client(api_token).webhooks.create(as_payload(body)))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_webhook(
        api_token: str, webhook_id: str, body: UpdateWebhookEndpointRequest
    ) -> ToolResult:
        """Update a webhook endpoint."""
        try:
            return serialize(
                get_client(api_token).webhooks.update(webhook_id, as_payload(body))
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_webhook(api_token: str, webhook_id: str) -> str:
        """Delete a webhook endpoint."""
        try:
            get_client(api_token).webhooks.delete(webhook_id)
            return "Webhook deleted successfully."
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def test_webhook(api_token: str, webhook_id: str) -> ToolResult:
        """Send a test event to a webhook endpoint to verify it works."""
        try:
            return serialize(get_client(api_token).webhooks.test(webhook_id))
        except DevhelmError as e:
            return format_error(e)
