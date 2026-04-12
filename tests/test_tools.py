"""Unit tests for MCP tool registration.

Verifies all tools are registered and have correct metadata.
"""

from __future__ import annotations

import asyncio

import pytest

from devhelm_mcp.server import mcp

EXPECTED_TOOLS = [
    "list_monitors",
    "get_monitor",
    "create_monitor",
    "update_monitor",
    "delete_monitor",
    "pause_monitor",
    "resume_monitor",
    "test_monitor",
    "list_monitor_results",
    "list_monitor_versions",
    "list_incidents",
    "get_incident",
    "create_incident",
    "resolve_incident",
    "delete_incident",
    "list_alert_channels",
    "get_alert_channel",
    "create_alert_channel",
    "update_alert_channel",
    "delete_alert_channel",
    "test_alert_channel",
    "list_notification_policies",
    "get_notification_policy",
    "create_notification_policy",
    "update_notification_policy",
    "delete_notification_policy",
    "test_notification_policy",
    "list_environments",
    "get_environment",
    "create_environment",
    "update_environment",
    "delete_environment",
    "list_secrets",
    "create_secret",
    "update_secret",
    "delete_secret",
    "list_tags",
    "get_tag",
    "create_tag",
    "update_tag",
    "delete_tag",
    "list_resource_groups",
    "get_resource_group",
    "create_resource_group",
    "update_resource_group",
    "delete_resource_group",
    "add_resource_group_member",
    "remove_resource_group_member",
    "list_webhooks",
    "get_webhook",
    "create_webhook",
    "update_webhook",
    "delete_webhook",
    "test_webhook",
    "list_api_keys",
    "create_api_key",
    "revoke_api_key",
    "delete_api_key",
    "list_dependencies",
    "get_dependency",
    "track_dependency",
    "delete_dependency",
    "acquire_deploy_lock",
    "get_current_deploy_lock",
    "release_deploy_lock",
    "force_release_deploy_lock",
    "get_status_overview",
]


@pytest.fixture(scope="module")
def registered_tools():
    tools = asyncio.run(mcp.list_tools())
    return {t.name: t for t in tools}


class TestToolRegistration:
    def test_all_expected_tools_registered(self, registered_tools) -> None:
        registered = set(registered_tools.keys())
        expected = set(EXPECTED_TOOLS)
        missing = expected - registered
        assert not missing, f"Missing tools: {sorted(missing)}"

    def test_no_unexpected_tools(self, registered_tools) -> None:
        registered = set(registered_tools.keys())
        expected = set(EXPECTED_TOOLS)
        extra = registered - expected
        assert not extra, f"Unexpected tools: {sorted(extra)}"

    def test_all_tools_have_descriptions(self, registered_tools) -> None:
        missing_desc = [
            name for name, tool in registered_tools.items() if not tool.description
        ]
        assert not missing_desc, f"Tools without descriptions: {missing_desc}"

    def test_tool_count(self, registered_tools) -> None:
        assert len(registered_tools) == len(EXPECTED_TOOLS), (
            f"Expected {len(EXPECTED_TOOLS)} tools, got {len(registered_tools)}"
        )
