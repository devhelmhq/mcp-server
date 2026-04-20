"""Unit tests for MCP tool registration.

Verifies all tools are registered and have correct metadata,
with deep coverage of status-page tool schemas.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from devhelm_mcp.server import mcp

RegisteredTools = dict[str, Any]

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
    "list_status_pages",
    "get_status_page",
    "create_status_page",
    "update_status_page",
    "delete_status_page",
    "list_status_page_components",
    "create_status_page_component",
    "update_status_page_component",
    "delete_status_page_component",
    "reorder_status_page_components",
    "list_status_page_groups",
    "create_status_page_group",
    "update_status_page_group",
    "delete_status_page_group",
    "list_status_page_incidents",
    "get_status_page_incident",
    "create_status_page_incident",
    "update_status_page_incident",
    "post_status_page_incident_update",
    "publish_status_page_incident",
    "dismiss_status_page_incident",
    "delete_status_page_incident",
    "list_status_page_subscribers",
    "add_status_page_subscriber",
    "remove_status_page_subscriber",
    "list_status_page_domains",
    "add_status_page_domain",
    "verify_status_page_domain",
    "remove_status_page_domain",
]


@pytest.fixture(scope="module")
def registered_tools() -> RegisteredTools:
    tools = asyncio.run(mcp.list_tools())
    return {t.name: t for t in tools}


class TestToolRegistration:
    def test_all_expected_tools_registered(
        self, registered_tools: RegisteredTools
    ) -> None:
        registered = set(registered_tools.keys())
        expected = set(EXPECTED_TOOLS)
        missing = expected - registered
        assert not missing, f"Missing tools: {sorted(missing)}"

    def test_no_unexpected_tools(self, registered_tools: RegisteredTools) -> None:
        registered = set(registered_tools.keys())
        expected = set(EXPECTED_TOOLS)
        extra = registered - expected
        assert not extra, f"Unexpected tools: {sorted(extra)}"

    def test_all_tools_have_descriptions(
        self, registered_tools: RegisteredTools
    ) -> None:
        missing_desc = [
            name for name, tool in registered_tools.items() if not tool.description
        ]
        assert not missing_desc, f"Tools without descriptions: {missing_desc}"

    def test_tool_count(self, registered_tools: RegisteredTools) -> None:
        assert len(registered_tools) == len(EXPECTED_TOOLS), (
            f"Expected {len(EXPECTED_TOOLS)} tools, got {len(registered_tools)}"
        )


STATUS_PAGE_TOOLS = [t for t in EXPECTED_TOOLS if "status_page" in t]

STATUS_PAGE_CRUD = [
    "list_status_pages",
    "get_status_page",
    "create_status_page",
    "update_status_page",
    "delete_status_page",
]

STATUS_PAGE_COMPONENT_TOOLS = [
    "list_status_page_components",
    "create_status_page_component",
    "update_status_page_component",
    "delete_status_page_component",
    "reorder_status_page_components",
]

STATUS_PAGE_GROUP_TOOLS = [
    "list_status_page_groups",
    "create_status_page_group",
    "update_status_page_group",
    "delete_status_page_group",
]

STATUS_PAGE_INCIDENT_TOOLS = [
    "list_status_page_incidents",
    "get_status_page_incident",
    "create_status_page_incident",
    "update_status_page_incident",
    "post_status_page_incident_update",
    "publish_status_page_incident",
    "dismiss_status_page_incident",
    "delete_status_page_incident",
]

STATUS_PAGE_SUBSCRIBER_TOOLS = [
    "list_status_page_subscribers",
    "add_status_page_subscriber",
    "remove_status_page_subscriber",
]

STATUS_PAGE_DOMAIN_TOOLS = [
    "list_status_page_domains",
    "add_status_page_domain",
    "verify_status_page_domain",
    "remove_status_page_domain",
]


class TestStatusPageToolCompleteness:
    """Verify the status page surface covers all sub-resources."""

    def test_crud_tools_present(self, registered_tools: RegisteredTools) -> None:
        for name in STATUS_PAGE_CRUD:
            assert name in registered_tools, f"Missing CRUD tool: {name}"

    def test_component_tools_present(self, registered_tools: RegisteredTools) -> None:
        for name in STATUS_PAGE_COMPONENT_TOOLS:
            assert name in registered_tools, f"Missing component tool: {name}"

    def test_group_tools_present(self, registered_tools: RegisteredTools) -> None:
        for name in STATUS_PAGE_GROUP_TOOLS:
            assert name in registered_tools, f"Missing group tool: {name}"

    def test_incident_tools_present(self, registered_tools: RegisteredTools) -> None:
        for name in STATUS_PAGE_INCIDENT_TOOLS:
            assert name in registered_tools, f"Missing incident tool: {name}"

    def test_subscriber_tools_present(self, registered_tools: RegisteredTools) -> None:
        for name in STATUS_PAGE_SUBSCRIBER_TOOLS:
            assert name in registered_tools, f"Missing subscriber tool: {name}"

    def test_domain_tools_present(self, registered_tools: RegisteredTools) -> None:
        for name in STATUS_PAGE_DOMAIN_TOOLS:
            assert name in registered_tools, f"Missing domain tool: {name}"

    def test_total_status_page_tool_count(
        self, registered_tools: RegisteredTools
    ) -> None:
        expected_count = (
            len(STATUS_PAGE_CRUD)
            + len(STATUS_PAGE_COMPONENT_TOOLS)
            + len(STATUS_PAGE_GROUP_TOOLS)
            + len(STATUS_PAGE_INCIDENT_TOOLS)
            + len(STATUS_PAGE_SUBSCRIBER_TOOLS)
            + len(STATUS_PAGE_DOMAIN_TOOLS)
        )
        actual = len(STATUS_PAGE_TOOLS)
        assert actual == expected_count, (
            f"Expected {expected_count} status page tools, found {actual}"
        )


class TestStatusPageToolSchemas:
    """Validate input schemas for status page tools."""

    def _params(
        self, registered_tools: RegisteredTools, name: str
    ) -> dict[str, dict[str, Any]]:
        """Get a tool's input schema properties as {param_name: schema}."""
        tool = registered_tools[name]
        result: dict[str, dict[str, Any]] = tool.parameters.get("properties", {})
        return result

    def _required(self, registered_tools: RegisteredTools, name: str) -> list[str]:
        tool = registered_tools[name]
        result: list[str] = tool.parameters.get("required", [])
        return result

    def test_all_tools_require_api_token(
        self, registered_tools: RegisteredTools
    ) -> None:
        for name in STATUS_PAGE_TOOLS:
            params = self._params(registered_tools, name)
            assert "api_token" in params, f"{name} missing api_token parameter"
            required = self._required(registered_tools, name)
            assert "api_token" in required, f"{name} should require api_token"

    def test_page_id_tools_require_page_id(
        self, registered_tools: RegisteredTools
    ) -> None:
        tools_needing_page_id = (
            STATUS_PAGE_COMPONENT_TOOLS
            + STATUS_PAGE_GROUP_TOOLS
            + STATUS_PAGE_INCIDENT_TOOLS
            + STATUS_PAGE_SUBSCRIBER_TOOLS
            + STATUS_PAGE_DOMAIN_TOOLS
            + ["get_status_page", "update_status_page", "delete_status_page"]
        )
        for name in tools_needing_page_id:
            params = self._params(registered_tools, name)
            assert "page_id" in params, f"{name} missing page_id parameter"

    def test_crud_create_and_update_have_body(
        self, registered_tools: RegisteredTools
    ) -> None:
        for name in [
            "create_status_page",
            "update_status_page",
            "create_status_page_component",
            "update_status_page_component",
            "create_status_page_group",
            "update_status_page_group",
            "create_status_page_incident",
            "update_status_page_incident",
            "post_status_page_incident_update",
            "add_status_page_subscriber",
            "add_status_page_domain",
        ]:
            params = self._params(registered_tools, name)
            assert "body" in params, f"{name} missing body parameter"

    def test_component_id_on_component_mutations(
        self, registered_tools: RegisteredTools
    ) -> None:
        for name in ["update_status_page_component", "delete_status_page_component"]:
            params = self._params(registered_tools, name)
            assert "component_id" in params, f"{name} missing component_id"

    def test_group_id_on_group_mutations(
        self, registered_tools: RegisteredTools
    ) -> None:
        for name in ["update_status_page_group", "delete_status_page_group"]:
            params = self._params(registered_tools, name)
            assert "group_id" in params, f"{name} missing group_id"

    def test_incident_id_on_incident_operations(
        self, registered_tools: RegisteredTools
    ) -> None:
        for name in [
            "get_status_page_incident",
            "update_status_page_incident",
            "post_status_page_incident_update",
            "publish_status_page_incident",
            "dismiss_status_page_incident",
            "delete_status_page_incident",
        ]:
            params = self._params(registered_tools, name)
            assert "incident_id" in params, f"{name} missing incident_id"

    def test_subscriber_id_on_remove(self, registered_tools: RegisteredTools) -> None:
        params = self._params(registered_tools, "remove_status_page_subscriber")
        assert "subscriber_id" in params

    def test_domain_id_on_verify_and_remove(
        self, registered_tools: RegisteredTools
    ) -> None:
        for name in ["verify_status_page_domain", "remove_status_page_domain"]:
            params = self._params(registered_tools, name)
            assert "domain_id" in params, f"{name} missing domain_id"

    def test_list_incidents_has_pagination_params(
        self, registered_tools: RegisteredTools
    ) -> None:
        params = self._params(registered_tools, "list_status_page_incidents")
        assert "page" in params
        assert "size" in params

    def test_list_subscribers_has_pagination_params(
        self, registered_tools: RegisteredTools
    ) -> None:
        params = self._params(registered_tools, "list_status_page_subscribers")
        assert "page" in params
        assert "size" in params

    def test_publish_body_is_optional(self, registered_tools: RegisteredTools) -> None:
        required = self._required(registered_tools, "publish_status_page_incident")
        assert "body" not in required, "publish body should be optional"

    def test_delete_tools_have_no_body(self, registered_tools: RegisteredTools) -> None:
        for name in [
            "delete_status_page",
            "delete_status_page_component",
            "delete_status_page_group",
            "delete_status_page_incident",
        ]:
            params = self._params(registered_tools, name)
            assert "body" not in params, f"{name} should not accept a body"


class TestStatusPageToolDescriptions:
    """Ensure descriptions are meaningful and non-trivial."""

    def test_descriptions_are_non_empty(
        self, registered_tools: RegisteredTools
    ) -> None:
        for name in STATUS_PAGE_TOOLS:
            desc = registered_tools[name].description
            assert desc and len(desc) >= 10, f"{name} description too short: {desc!r}"

    def test_no_duplicate_descriptions(self, registered_tools: RegisteredTools) -> None:
        descs = [registered_tools[n].description for n in STATUS_PAGE_TOOLS]
        assert len(descs) == len(set(descs)), "Duplicate descriptions found"

    def test_list_tools_mention_list(self, registered_tools: RegisteredTools) -> None:
        for name in STATUS_PAGE_TOOLS:
            if name.startswith("list_"):
                desc = registered_tools[name].description.lower()
                assert "list" in desc, f"{name} description should mention listing"

    def test_create_tools_mention_create(
        self, registered_tools: RegisteredTools
    ) -> None:
        for name in STATUS_PAGE_TOOLS:
            if name.startswith("create_") or name.startswith("add_"):
                desc = registered_tools[name].description.lower()
                assert "create" in desc or "add" in desc, (
                    f"{name} description should mention creating/adding"
                )
