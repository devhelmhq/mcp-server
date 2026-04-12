"""Notification policy tools — routing rules for alerts."""

from __future__ import annotations

from typing import Any

from devhelm import DevhelmError
from fastmcp import FastMCP

from devhelm_mcp.client import format_error, get_client, serialize


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_notification_policies(api_token: str) -> Any:
        """List all notification policies in the workspace."""
        try:
            return serialize(get_client(api_token).notification_policies.list())
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_notification_policy(api_token: str, policy_id: str) -> Any:
        """Get a notification policy by ID."""
        try:
            return serialize(get_client(api_token).notification_policies.get(policy_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_notification_policy(api_token: str, body: dict[str, Any]) -> Any:
        """Create a notification policy.

        Required fields: name, monitorIds, channelIds, severity.
        """
        try:
            return serialize(get_client(api_token).notification_policies.create(body))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_notification_policy(
        api_token: str, policy_id: str, body: dict[str, Any]
    ) -> Any:
        """Update a notification policy."""
        try:
            return serialize(
                get_client(api_token).notification_policies.update(policy_id, body)
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_notification_policy(api_token: str, policy_id: str) -> str:
        """Delete a notification policy."""
        try:
            get_client(api_token).notification_policies.delete(policy_id)
            return "Notification policy deleted successfully."
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def test_notification_policy(api_token: str, policy_id: str) -> str:
        """Send a test dispatch to verify a notification policy's routing."""
        try:
            get_client(api_token).notification_policies.test(policy_id)
            return "Test dispatch sent successfully."
        except DevhelmError as e:
            return format_error(e)
