"""Tests for service catalog MCP tools + dependency alert-sensitivity tools.

The ``client.services`` SDK resource and the extended
``client.dependencies.track`` / ``update_alert_sensitivity`` signatures ship
in a parallel SDK release; these tests patch ``get_client`` in the tool
module's namespace (the same pattern as ``test_devex_round3_fixes.py``) so
the tools are exercised against the agreed SDK call contract without
requiring the new SDK methods to be installed.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from devhelm import DevhelmApiError

from devhelm_mcp.server import _strip_internal_schema_fields, mcp

RegisteredTools = dict[str, Any]


@pytest.fixture(scope="module")
def registered_tools() -> RegisteredTools:
    asyncio.run(_strip_internal_schema_fields())
    tools = asyncio.run(mcp.list_tools())
    return {t.name: t for t in tools}


_SERVICE_TOOLS = [
    "search_services",
    "get_service",
    "get_service_live_status",
    "get_services_summary",
    "list_service_categories",
    "list_service_components",
    "get_service_uptime",
    "list_service_incidents",
    "get_service_incident",
    "get_service_day_rollup",
    "get_component_uptime",
    "get_all_components_uptime",
    "list_service_maintenances",
]

_SAMPLE_SERVICE: dict[str, Any] = {
    "slug": "stripe",
    "name": "Stripe",
    "category": "payments",
    "status": "OPERATIONAL",
}

_SAMPLE_PAGE: dict[str, Any] = {
    "data": [_SAMPLE_SERVICE],
    "nextCursor": None,
    "hasMore": False,
}


def _call_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    return asyncio.run(mcp.call_tool(tool_name, arguments))


def _mock_services_client() -> MagicMock:
    """SDK client stub whose ``services`` / ``dependencies`` methods return
    JSON-safe dicts (``serialize`` rejects bare MagicMocks)."""
    client = MagicMock()
    client.services.list.return_value = _SAMPLE_PAGE
    client.services.get.return_value = _SAMPLE_SERVICE
    client.services.live_status.return_value = {
        "slug": "stripe",
        "status": "OPERATIONAL",
    }
    client.services.categories.return_value = [{"slug": "payments"}]
    client.services.components.return_value = [{"id": "comp_1", "name": "API"}]
    client.services.uptime.return_value = {"period": "30d", "uptime": 99.99}
    client.services.incidents.return_value = [{"id": "inc_1", "status": "active"}]
    client.services.summary.return_value = {
        "totalServices": 1200,
        "operationalCount": 1190,
    }
    client.services.incident.return_value = {
        "id": "inc_1",
        "status": "resolved",
        "updates": [{"status": "investigating"}, {"status": "resolved"}],
    }
    client.services.day.return_value = {
        "date": "2026-06-01",
        "uptime": 99.5,
        "incidents": [{"id": "inc_1"}],
    }
    client.services.component_uptime.return_value = [
        {"date": "2026-06-01", "uptime": 100.0}
    ]
    client.services.batch_component_uptime.return_value = {
        "comp_1": [{"date": "2026-06-01", "uptime": 100.0}]
    }
    client.services.maintenances.return_value = [{"id": "mw_1"}]
    client.dependencies.track.return_value = {"id": "sub_1", "slug": "stripe"}
    client.dependencies.update_alert_sensitivity.return_value = {
        "id": "sub_1",
        "alertSensitivity": "MAJOR_ONLY",
    }
    return client


# --------------------------------------------------------------------------- #
# Registration + schema hygiene
# --------------------------------------------------------------------------- #


class TestServiceToolsRegistered:
    @pytest.mark.parametrize("name", _SERVICE_TOOLS)
    def test_tool_registered_with_description(
        self, registered_tools: RegisteredTools, name: str
    ) -> None:
        assert name in registered_tools, f"Missing tool: {name}"
        desc = registered_tools[name].description
        assert desc and len(desc) >= 10, f"{name} description too short: {desc!r}"

    def test_search_services_mentions_example_services(
        self, registered_tools: RegisteredTools
    ) -> None:
        # The docstring is the LLM's only hint about what lives in the
        # catalog; the Stripe/GitHub/AWS examples anchor that.
        desc = registered_tools["search_services"].description
        for example in ("Stripe", "GitHub", "AWS"):
            assert example in desc, f"search_services should mention {example}"

    @pytest.mark.parametrize("name", _SERVICE_TOOLS)
    def test_api_token_hidden_from_input_schema(
        self, registered_tools: RegisteredTools, name: str
    ) -> None:
        properties = registered_tools[name].parameters.get("properties", {})
        assert "api_token" not in properties, (
            f"{name} leaks api_token into the LLM-facing input schema"
        )
        required = registered_tools[name].parameters.get("required", [])
        assert "api_token" not in required

    def test_slug_required_on_per_service_tools(
        self, registered_tools: RegisteredTools
    ) -> None:
        for name in [
            "get_service",
            "get_service_live_status",
            "list_service_components",
            "get_service_uptime",
            "get_service_incident",
            "get_service_day_rollup",
            "get_component_uptime",
            "get_all_components_uptime",
            "list_service_maintenances",
        ]:
            required = registered_tools[name].parameters.get("required", [])
            assert "slug" in required, f"{name} should require slug"

    def test_cross_service_tools_have_optional_filters(
        self, registered_tools: RegisteredTools
    ) -> None:
        # search_services, list_service_incidents, and get_services_summary
        # work with no args at all (browse mode / cross-service sweeps /
        # global overview).
        for name in [
            "search_services",
            "list_service_incidents",
            "get_services_summary",
        ]:
            required = registered_tools[name].parameters.get("required", [])
            assert required == [], f"{name} should have no required params"

    def test_id_params_required_on_detail_tools(
        self, registered_tools: RegisteredTools
    ) -> None:
        required_incident = registered_tools["get_service_incident"].parameters.get(
            "required", []
        )
        assert "incident_id" in required_incident
        required_day = registered_tools["get_service_day_rollup"].parameters.get(
            "required", []
        )
        assert "date" in required_day
        required_comp = registered_tools["get_component_uptime"].parameters.get(
            "required", []
        )
        assert "component_id" in required_comp


# --------------------------------------------------------------------------- #
# SDK call contract — each tool forwards args to the agreed SDK signature
# --------------------------------------------------------------------------- #


class TestServiceToolsSdkContract:
    def test_search_services_forwards_query_category_limit(self) -> None:
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.services.get_client", return_value=client):
            _call_tool(
                "search_services",
                {"query": "stripe", "category": "payments", "limit": 5},
            )
        client.services.list.assert_called_once_with(
            search="stripe", category="payments", limit=5
        )

    def test_search_services_defaults(self) -> None:
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.services.get_client", return_value=client):
            _call_tool("search_services", {})
        client.services.list.assert_called_once_with(
            search=None, category=None, limit=20
        )

    def test_get_service_uses_summary(self) -> None:
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.services.get_client", return_value=client):
            _call_tool("get_service", {"slug": "stripe"})
        client.services.get.assert_called_once_with("stripe", summary=True)

    def test_get_service_live_status(self) -> None:
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.services.get_client", return_value=client):
            _call_tool("get_service_live_status", {"slug": "stripe"})
        client.services.live_status.assert_called_once_with("stripe")

    def test_list_service_categories(self) -> None:
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.services.get_client", return_value=client):
            _call_tool("list_service_categories", {})
        client.services.categories.assert_called_once_with()

    def test_list_service_components(self) -> None:
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.services.get_client", return_value=client):
            _call_tool("list_service_components", {"slug": "stripe"})
        client.services.components.assert_called_once_with("stripe")

    def test_get_service_uptime_forwards_period(self) -> None:
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.services.get_client", return_value=client):
            _call_tool("get_service_uptime", {"slug": "stripe", "period": "90d"})
        client.services.uptime.assert_called_once_with("stripe", period="90d")

    def test_get_service_uptime_default_period(self) -> None:
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.services.get_client", return_value=client):
            _call_tool("get_service_uptime", {"slug": "stripe"})
        client.services.uptime.assert_called_once_with("stripe", period="30d")

    def test_list_service_incidents_per_service(self) -> None:
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.services.get_client", return_value=client):
            _call_tool("list_service_incidents", {"slug": "stripe", "status": "active"})
        client.services.incidents.assert_called_once_with(
            slug_or_id="stripe", status="active"
        )

    def test_list_service_incidents_cross_service(self) -> None:
        # Omitting slug must hit the cross-service listing (slug_or_id=None).
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.services.get_client", return_value=client):
            _call_tool("list_service_incidents", {})
        client.services.incidents.assert_called_once_with(slug_or_id=None, status=None)

    def test_list_service_maintenances(self) -> None:
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.services.get_client", return_value=client):
            _call_tool("list_service_maintenances", {"slug": "aws"})
        client.services.maintenances.assert_called_once_with("aws")

    def test_get_services_summary(self) -> None:
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.services.get_client", return_value=client):
            _call_tool("get_services_summary", {})
        client.services.summary.assert_called_once_with()

    def test_get_service_incident(self) -> None:
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.services.get_client", return_value=client):
            _call_tool(
                "get_service_incident", {"slug": "stripe", "incident_id": "inc_1"}
            )
        client.services.incident.assert_called_once_with("stripe", "inc_1")

    def test_get_service_day_rollup(self) -> None:
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.services.get_client", return_value=client):
            _call_tool(
                "get_service_day_rollup", {"slug": "stripe", "date": "2026-06-01"}
            )
        client.services.day.assert_called_once_with("stripe", "2026-06-01")

    def test_get_component_uptime_forwards_period(self) -> None:
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.services.get_client", return_value=client):
            _call_tool(
                "get_component_uptime",
                {"slug": "stripe", "component_id": "comp_1", "period": "90d"},
            )
        client.services.component_uptime.assert_called_once_with(
            "stripe", "comp_1", period="90d"
        )

    def test_get_component_uptime_default_period(self) -> None:
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.services.get_client", return_value=client):
            _call_tool(
                "get_component_uptime", {"slug": "stripe", "component_id": "comp_1"}
            )
        client.services.component_uptime.assert_called_once_with(
            "stripe", "comp_1", period="30d"
        )

    def test_get_all_components_uptime_forwards_period(self) -> None:
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.services.get_client", return_value=client):
            _call_tool("get_all_components_uptime", {"slug": "stripe", "period": "7d"})
        client.services.batch_component_uptime.assert_called_once_with(
            "stripe", period="7d"
        )

    def test_get_all_components_uptime_default_period(self) -> None:
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.services.get_client", return_value=client):
            _call_tool("get_all_components_uptime", {"slug": "stripe"})
        client.services.batch_component_uptime.assert_called_once_with(
            "stripe", period="30d"
        )


# --------------------------------------------------------------------------- #
# Dependencies — extended track + alert sensitivity update
# --------------------------------------------------------------------------- #


class TestDependencyTrackExtensions:
    def test_track_dependency_defaults_pass_none(self) -> None:
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.dependencies.get_client", return_value=client):
            _call_tool("track_dependency", {"slug": "stripe"})
        client.dependencies.track.assert_called_once_with(
            "stripe", component_id=None, alert_sensitivity=None
        )

    def test_track_dependency_forwards_component_and_sensitivity(self) -> None:
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.dependencies.get_client", return_value=client):
            _call_tool(
                "track_dependency",
                {
                    "slug": "stripe",
                    "component_id": "comp_1",
                    "alert_sensitivity": "INCIDENTS_ONLY",
                },
            )
        client.dependencies.track.assert_called_once_with(
            "stripe", component_id="comp_1", alert_sensitivity="INCIDENTS_ONLY"
        )

    def test_update_dependency_alert_sensitivity(self) -> None:
        client = _mock_services_client()
        with patch("devhelm_mcp.tools.dependencies.get_client", return_value=client):
            _call_tool(
                "update_dependency_alert_sensitivity",
                {"subscription_id": "sub_1", "alert_sensitivity": "MAJOR_ONLY"},
            )
        client.dependencies.update_alert_sensitivity.assert_called_once_with(
            "sub_1", "MAJOR_ONLY"
        )

    def test_update_sensitivity_docstring_lists_all_levels(
        self, registered_tools: RegisteredTools
    ) -> None:
        desc = registered_tools["update_dependency_alert_sensitivity"].description
        for level in ("AWARENESS", "INCIDENTS_ONLY", "MAJOR_ONLY", "ALL"):
            assert level in desc, f"description should document level {level}"


# --------------------------------------------------------------------------- #
# Error surfacing — upstream failures must set isError=true
# --------------------------------------------------------------------------- #


class TestServiceToolErrorsBubbleUp:
    def test_get_service_propagates_api_error(self) -> None:
        async def go() -> Any:
            from fastmcp import Client

            async with Client(mcp) as client:
                return await client.call_tool(
                    "get_service",
                    {"slug": "nonexistent"},
                    raise_on_error=False,
                )

        mock_client = MagicMock()
        mock_client.services.get.side_effect = DevhelmApiError(
            "Service not found",
            status=404,
            code="NOT_FOUND",
            request_id="req_svc",
        )

        with patch("devhelm_mcp.tools.services.get_client", return_value=mock_client):
            result = asyncio.run(go())

        assert result.is_error is True
        text = result.content[0].text
        assert "ApiError (404 NOT_FOUND)" in text
        assert "request_id=req_svc" in text
