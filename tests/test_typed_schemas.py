"""Tests for FastMCP-derived typed schemas on tool body parameters.

Now that tools take typed Pydantic models (e.g. ``body: CreateMonitorRequest``)
instead of opaque ``dict[str, Any]``, FastMCP introspects the model and emits a
proper JSON Schema for the LLM to consume. These tests assert the schema
actually surfaces required fields, enums, and field descriptions — replacing
the manual ``validate_body`` checks that were necessary while bodies were
typed as plain dicts.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from devhelm_mcp.server import mcp

RegisteredTools = dict[str, Any]


@pytest.fixture(scope="module")
def registered_tools() -> RegisteredTools:
    tools = asyncio.run(mcp.list_tools())
    return {t.name: t for t in tools}


def _body_schema(tools: RegisteredTools, name: str) -> dict[str, Any]:
    """Resolve the JSON Schema for a tool's ``body`` parameter, dereffing $refs."""
    tool = tools[name]
    params = tool.parameters
    body = params["properties"]["body"]
    if "$ref" in body:
        ref = body["$ref"].rsplit("/", 1)[-1]
        return params["$defs"][ref]  # type: ignore[no-any-return]
    if "anyOf" in body:
        # Optional body: pick the non-null branch.
        for branch in body["anyOf"]:
            if branch.get("type") != "null":
                if "$ref" in branch:
                    ref = branch["$ref"].rsplit("/", 1)[-1]
                    return params["$defs"][ref]  # type: ignore[no-any-return]
                return branch  # type: ignore[no-any-return]
    return body  # type: ignore[no-any-return]


class TestTypedBodySchemas:
    """Body parameters derive from Pydantic models, not opaque dicts."""

    @pytest.mark.parametrize(
        ("tool_name", "required_fields"),
        [
            ("create_monitor", {"name", "type", "config"}),
            ("create_alert_channel", {"name", "config"}),
            ("create_environment", {"name", "slug"}),
            ("create_secret", {"key", "value"}),
            ("create_tag", {"name"}),
            ("create_resource_group", {"name"}),
            ("create_webhook", {"url"}),
            ("create_api_key", {"name"}),
            ("create_status_page", {"name", "slug"}),
            ("create_status_page_component", {"name", "type"}),
            ("create_status_page_group", {"name"}),
            ("create_status_page_incident", {"title", "impact", "body"}),
            ("post_status_page_incident_update", {"status", "body"}),
            ("add_status_page_subscriber", {"email"}),
            ("add_status_page_domain", {"hostname"}),
            ("acquire_deploy_lock", {"lockedBy"}),
            ("create_incident", {"title", "severity"}),
            ("create_notification_policy", {"name", "escalation"}),
            ("add_resource_group_member", {"memberType", "memberId"}),
            ("reorder_status_page_components", {"positions"}),
        ],
    )
    def test_required_fields_surface_in_body_schema(
        self,
        registered_tools: RegisteredTools,
        tool_name: str,
        required_fields: set[str],
    ) -> None:
        schema = _body_schema(registered_tools, tool_name)
        required = set(schema.get("required", []))
        missing = required_fields - required
        assert not missing, (
            f"{tool_name}: body schema missing required fields {sorted(missing)} "
            f"(got required={sorted(required)})"
        )

    def test_body_schema_has_field_descriptions(
        self, registered_tools: RegisteredTools
    ) -> None:
        """Field descriptions from @Schema annotations flow through to LLM."""
        schema = _body_schema(registered_tools, "create_monitor")
        properties = schema["properties"]
        assert properties["name"].get("description"), (
            "create_monitor body.name should have a description"
        )
        assert properties["type"].get("description"), (
            "create_monitor body.type should have a description"
        )

    def test_body_is_not_opaque_dict(self, registered_tools: RegisteredTools) -> None:
        """Body params must be typed objects, never untyped dicts/anys."""
        for name in [
            "create_monitor",
            "create_alert_channel",
            "create_environment",
            "create_status_page",
            "create_incident",
            "create_notification_policy",
            "create_secret",
            "create_tag",
            "create_resource_group",
            "create_webhook",
            "create_api_key",
            "acquire_deploy_lock",
            "add_resource_group_member",
            "reorder_status_page_components",
            "create_status_page_component",
            "create_status_page_group",
            "create_status_page_incident",
            "post_status_page_incident_update",
            "add_status_page_subscriber",
            "add_status_page_domain",
        ]:
            schema = _body_schema(registered_tools, name)
            assert schema.get("type") == "object", (
                f"{name}: body schema must have type=object, "
                f"got {json.dumps(schema)[:200]}"
            )
            assert schema.get("properties"), (
                f"{name}: body schema must enumerate properties (typed model)"
            )

    def test_enum_values_surface_in_body_schema(
        self, registered_tools: RegisteredTools
    ) -> None:
        """Enum-typed fields expose their allowed values."""
        schema = _body_schema(registered_tools, "create_monitor")
        type_field = schema["properties"]["type"]
        assert "enum" in type_field, (
            "create_monitor body.type must declare its enum values"
        )
        assert "HTTP" in type_field["enum"]

    def test_publish_status_page_incident_body_optional(
        self, registered_tools: RegisteredTools
    ) -> None:
        """publish allows an empty body (None) to keep the draft as-is."""
        tool = registered_tools["publish_status_page_incident"]
        required = tool.parameters.get("required", [])
        assert "body" not in required
