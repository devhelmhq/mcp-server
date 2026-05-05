"""Notification policy tools — routing rules for alerts."""

from __future__ import annotations

from devhelm import DevhelmError
from devhelm.types import (
    CreateNotificationPolicyRequest,
    UpdateNotificationPolicyRequest,
)
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
    def list_notification_policies(api_token: str | None = None) -> ToolResult:
        """List all notification policies in the workspace."""
        try:
            return serialize(get_client(api_token).notification_policies.list())
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_notification_policy(
        policy_id: str, api_token: str | None = None
    ) -> ToolResult:
        """Get a notification policy by ID."""
        try:
            return serialize(get_client(api_token).notification_policies.get(policy_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_notification_policy(
        body: CreateNotificationPolicyRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Create a notification policy.

        Required: name, matchRules (list of {type, value?, monitorIds?, regions?}),
        escalation ({steps: [{delayMinutes, channelIds}], onResolve?, onReopen?}),
        enabled (bool), priority (int, higher = evaluated first).
        """
        try:
            return serialize(
                get_client(api_token).notification_policies.create(as_payload(body))
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_notification_policy(
        policy_id: str,
        body: UpdateNotificationPolicyRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Update a notification policy."""
        try:
            return serialize(
                get_client(api_token).notification_policies.update(
                    policy_id, as_payload(body)
                )
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_notification_policy(policy_id: str, api_token: str | None = None) -> str:
        """Delete a notification policy."""
        try:
            get_client(api_token).notification_policies.delete(policy_id)
            return "Notification policy deleted successfully."
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def test_notification_policy(policy_id: str, api_token: str | None = None) -> str:
        """Send a test dispatch to verify a notification policy's routing."""
        try:
            get_client(api_token).notification_policies.test(policy_id)
            return "Test dispatch sent successfully."
        except DevhelmError as e:
            return format_error(e)
