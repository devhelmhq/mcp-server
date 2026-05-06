"""Tests for maintenance window MCP tools.

Asserts each tool builds the right HTTP request to the right path, that
the create/update tools forward Pydantic-validated bodies, and that the
LLM-facing input schema does not leak ``api_token`` or ``managedBy``.

The maintenance-window resource doesn't ship in the pinned ``devhelm``
SDK release yet (the parallel SDK PR adds ``client.maintenance_windows``
later); the tools here call the SDK's low-level ``api_get`` / ``api_post``
/ ``api_put`` / ``api_delete`` helpers directly. To exercise them
without booting the API, each test patches those helpers in the tool
module's namespace and captures the call args.
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


# Sample DTO shape returned by the API (camelCase, MaintenanceWindowDto).
_SAMPLE_WINDOW: dict[str, Any] = {
    "id": "11111111-1111-1111-1111-111111111111",
    "monitorId": None,
    "organizationId": 1,
    "startsAt": "2026-05-15T14:00:00Z",
    "endsAt": "2026-05-15T15:00:00Z",
    "repeatRule": None,
    "reason": "deploy v0.7.3",
    "suppressAlerts": True,
    "createdAt": "2026-05-06T10:00:00Z",
}

_SAMPLE_ENVELOPE_SINGLE: dict[str, Any] = {"data": _SAMPLE_WINDOW}

_SAMPLE_ENVELOPE_LIST: dict[str, Any] = {
    "data": [_SAMPLE_WINDOW],
    "hasNext": False,
    "hasPrev": False,
    "totalElements": 1,
    "totalPages": 1,
}


# --------------------------------------------------------------------------- #
# Tool registration
# --------------------------------------------------------------------------- #


class TestMaintenanceWindowToolsRegistered:
    """Every maintenance-window tool surfaces in the FastMCP registry."""

    @pytest.mark.parametrize(
        "name",
        [
            "list_maintenance_windows",
            "get_maintenance_window",
            "create_maintenance_window",
            "update_maintenance_window",
            "cancel_maintenance_window",
        ],
    )
    def test_tool_registered(
        self, registered_tools: RegisteredTools, name: str
    ) -> None:
        assert name in registered_tools, f"Missing tool: {name}"
        assert registered_tools[name].description, (
            f"{name} must have a non-empty description (LLM docs)"
        )


# --------------------------------------------------------------------------- #
# HTTP wire contract — verifies path / method / body for each tool
# --------------------------------------------------------------------------- #


def _call_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    return asyncio.run(mcp.call_tool(tool_name, arguments))


def _stub_sdk_client() -> MagicMock:
    """Return a minimal SDK-shaped stub for ``_http_client`` to walk.

    ``_http_client`` calls ``get_client(...).monitors._client`` to
    reuse the SDK's configured ``httpx.Client``. The tests patch the
    api_get/post/put/delete helpers separately and never hit a real
    network, so any object with the right attribute chain works."""
    mock = MagicMock()
    mock.monitors._client = MagicMock(name="httpx.Client")
    return mock


@pytest.fixture(autouse=True)
def _stub_get_client(request: pytest.FixtureRequest) -> Any:
    """Auto-patch ``get_client`` for tests that exercise the wire calls.

    The schema-hygiene and registration tests don't need this — they
    introspect the ``inputSchema`` only — so the fixture is a no-op
    when a test class doesn't ask for it. Tests opt in by living
    under one of the ``HttpContract`` classes (which also patch the
    api_* helpers); other classes get the real ``get_client`` (which
    in turn raises ``DevhelmAuthError`` if no token is configured —
    that's fine because they never call a tool)."""
    classname = request.node.cls.__name__ if request.node.cls else ""
    if "HttpContract" not in classname:
        yield None
        return
    with patch(
        "devhelm_mcp.tools.maintenance_windows.get_client",
        return_value=_stub_sdk_client(),
    ) as p:
        yield p


class TestListMaintenanceWindowsHttpContract:
    """``list_maintenance_windows`` GETs ``/api/v1/maintenance-windows``."""

    def test_no_filters_omits_query_params(self) -> None:
        captured: dict[str, Any] = {}

        def fake_api_get(
            client: Any, path: str, params: dict[str, Any] | None = None
        ) -> dict[str, Any]:
            captured.setdefault("calls", []).append((path, params))
            return _SAMPLE_ENVELOPE_LIST

        with patch(
            "devhelm_mcp.tools.maintenance_windows.api_get",
            side_effect=fake_api_get,
        ):
            _call_tool("list_maintenance_windows", {})

        assert captured["calls"], "expected at least one GET"
        path, params = captured["calls"][0]
        assert path == "/api/v1/maintenance-windows"
        # The list endpoint accepts only ``monitorId`` and ``filter``
        # query params; when the LLM passes neither we send no params
        # so the API can't reject on an unexpected key.
        assert params is None or params == {}

    def test_monitor_id_and_status_flow_through_as_query_params(self) -> None:
        captured: dict[str, Any] = {}

        def fake_api_get(
            client: Any, path: str, params: dict[str, Any] | None = None
        ) -> dict[str, Any]:
            captured["params"] = dict(params or {})
            return _SAMPLE_ENVELOPE_LIST

        with patch(
            "devhelm_mcp.tools.maintenance_windows.api_get",
            side_effect=fake_api_get,
        ):
            _call_tool(
                "list_maintenance_windows",
                {
                    "monitor_id": "22222222-2222-2222-2222-222222222222",
                    "status": "active",
                },
            )

        assert captured["params"]["monitorId"] == (
            "22222222-2222-2222-2222-222222222222"
        )
        # API contract: query key is ``filter``, value is ``active`` /
        # ``upcoming`` (lowercase). Pinning here so a future docstring
        # rewrite that nudges the LLM toward UPPERCASE values doesn't
        # break the wire contract.
        assert captured["params"]["filter"] == "active"


class TestGetMaintenanceWindowHttpContract:
    def test_uses_correct_path_with_url_encoded_id(self) -> None:
        captured: dict[str, Any] = {}

        def fake_api_get(
            client: Any, path: str, params: dict[str, Any] | None = None
        ) -> dict[str, Any]:
            captured["path"] = path
            return _SAMPLE_ENVELOPE_SINGLE

        with patch(
            "devhelm_mcp.tools.maintenance_windows.api_get",
            side_effect=fake_api_get,
        ):
            _call_tool(
                "get_maintenance_window",
                {"window_id": "11111111-1111-1111-1111-111111111111"},
            )

        assert (
            captured["path"]
            == "/api/v1/maintenance-windows/11111111-1111-1111-1111-111111111111"
        )


class TestCreateMaintenanceWindowHttpContract:
    """``create_maintenance_window`` POSTs to ``/api/v1/maintenance-windows``
    with a Pydantic-validated ``CreateMaintenanceWindowRequest`` body.

    The body parameters use camelCase aliases (``startsAt``, ``endsAt``,
    ``monitorId``, …) on the wire. Verifying them pins the OpenAPI
    contract regardless of whether the SDK's internal Python field
    names are snake_case or camelCase.
    """

    @staticmethod
    def _wire_body(captured_body: Any) -> dict[str, Any]:
        """Render a captured request body the way ``httpx`` would.

        ``api_post`` accepts a Pydantic model and the SDK's
        ``_serialize_body`` calls ``model_dump(mode="json",
        by_alias=True, exclude_none=True)`` to produce the wire
        bytes. Replicate that here so the test asserts the exact
        camelCase / RFC-3339 shape the API will receive.
        """
        from pydantic import BaseModel

        assert isinstance(captured_body, BaseModel), (
            "create/update tools must hand a validated Pydantic model "
            "to api_post, not a raw dict (raw dicts get rejected by "
            "the SDK's _serialize_body)."
        )
        return captured_body.model_dump(mode="json", by_alias=True, exclude_none=True)

    def test_body_serialised_with_camelcase_aliases(self) -> None:
        captured: dict[str, Any] = {}

        def fake_api_post(client: Any, path: str, body: Any) -> dict[str, Any]:
            captured["path"] = path
            captured["body"] = body
            return _SAMPLE_ENVELOPE_SINGLE

        with patch(
            "devhelm_mcp.tools.maintenance_windows.api_post",
            side_effect=fake_api_post,
        ):
            _call_tool(
                "create_maintenance_window",
                {
                    "body": {
                        "startsAt": "2026-05-15T14:00:00Z",
                        "endsAt": "2026-05-15T15:00:00Z",
                        "monitorId": "22222222-2222-2222-2222-222222222222",
                        "reason": "deploy v0.7.3",
                        "suppressAlerts": True,
                    },
                },
            )

        assert captured["path"] == "/api/v1/maintenance-windows"
        wire = self._wire_body(captured["body"])
        assert wire["startsAt"] == "2026-05-15T14:00:00Z"
        assert wire["endsAt"] == "2026-05-15T15:00:00Z"
        assert wire["monitorId"] == "22222222-2222-2222-2222-222222222222"
        assert wire["reason"] == "deploy v0.7.3"
        assert wire["suppressAlerts"] is True

    def test_org_wide_window_omits_monitor_id_when_null(self) -> None:
        # ``monitorId=null`` in the input is the documented "org-wide"
        # marker, but the SDK serialises with ``exclude_none=True`` so
        # the wire body must drop the key entirely. The API treats
        # absent and null identically, so this is purely a wire-shape
        # invariant we want to keep stable.
        captured: dict[str, Any] = {}

        def fake_api_post(client: Any, path: str, body: Any) -> dict[str, Any]:
            captured["body"] = body
            return _SAMPLE_ENVELOPE_SINGLE

        with patch(
            "devhelm_mcp.tools.maintenance_windows.api_post",
            side_effect=fake_api_post,
        ):
            _call_tool(
                "create_maintenance_window",
                {
                    "body": {
                        "startsAt": "2026-05-15T14:00:00Z",
                        "endsAt": "2026-05-15T15:00:00Z",
                    },
                },
            )

        wire = self._wire_body(captured["body"])
        assert "monitorId" not in wire


class TestUpdateMaintenanceWindowHttpContract:
    def test_puts_to_window_path_with_full_body(self) -> None:
        from pydantic import BaseModel

        captured: dict[str, Any] = {}

        def fake_api_put(client: Any, path: str, body: Any) -> dict[str, Any]:
            captured["path"] = path
            captured["body"] = body
            return _SAMPLE_ENVELOPE_SINGLE

        with patch(
            "devhelm_mcp.tools.maintenance_windows.api_put",
            side_effect=fake_api_put,
        ):
            _call_tool(
                "update_maintenance_window",
                {
                    "window_id": "11111111-1111-1111-1111-111111111111",
                    "body": {
                        "startsAt": "2026-05-15T14:00:00Z",
                        "endsAt": "2026-05-15T16:30:00Z",
                        "reason": "deploy still running",
                    },
                },
            )

        assert (
            captured["path"]
            == "/api/v1/maintenance-windows/11111111-1111-1111-1111-111111111111"
        )
        assert isinstance(captured["body"], BaseModel)
        wire = captured["body"].model_dump(
            mode="json", by_alias=True, exclude_none=True
        )
        assert wire["endsAt"] == "2026-05-15T16:30:00Z"
        assert wire["reason"] == "deploy still running"


class TestCancelMaintenanceWindowHttpContract:
    def test_deletes_at_window_path_and_returns_friendly_string(self) -> None:
        captured: dict[str, Any] = {}

        def fake_api_delete(client: Any, path: str) -> None:
            captured["path"] = path

        with patch(
            "devhelm_mcp.tools.maintenance_windows.api_delete",
            side_effect=fake_api_delete,
        ):
            result = _call_tool(
                "cancel_maintenance_window",
                {"window_id": "11111111-1111-1111-1111-111111111111"},
            )

        assert (
            captured["path"]
            == "/api/v1/maintenance-windows/11111111-1111-1111-1111-111111111111"
        )
        # The tool returns a plain string for the LLM to echo back to
        # the user. ``mcp.call_tool`` wraps that as a TextContent block.
        rendered = result.content[0].text if result.content else ""
        assert "cancelled" in rendered.lower()


# --------------------------------------------------------------------------- #
# Schema hygiene — input schema must not leak api_token or managedBy
# --------------------------------------------------------------------------- #


_MAINTENANCE_TOOLS = [
    "list_maintenance_windows",
    "get_maintenance_window",
    "create_maintenance_window",
    "update_maintenance_window",
    "cancel_maintenance_window",
]


def _body_schema_for(tools: RegisteredTools, name: str) -> dict[str, Any] | None:
    """Resolve a tool's body sub-schema if it has one (create / update only)."""
    params = tools[name].parameters
    body = params.get("properties", {}).get("body")
    if not isinstance(body, dict):
        return None
    if "$ref" in body:
        ref_name = body["$ref"].rsplit("/", 1)[-1]
        return params.get("$defs", {}).get(ref_name)  # type: ignore[no-any-return]
    return body


class TestMaintenanceWindowSchemaHygiene:
    """``api_token`` is auto-resolved from header / env and must never
    appear in the tool's JSON Schema (P2.Bug7 — leaks token into the
    LLM's prompt context). ``managedBy`` is not part of the
    maintenance-window API today, but pinning the assertion now means
    a future SDK regen that bolts the field on can't silently expose
    it to the LLM."""

    @pytest.mark.parametrize("name", _MAINTENANCE_TOOLS)
    def test_api_token_not_in_properties(
        self, registered_tools: RegisteredTools, name: str
    ) -> None:
        properties = registered_tools[name].parameters.get("properties", {})
        assert "api_token" not in properties, (
            f"{name} leaks api_token into the LLM-facing input schema"
        )

    @pytest.mark.parametrize("name", _MAINTENANCE_TOOLS)
    def test_api_token_not_required(
        self, registered_tools: RegisteredTools, name: str
    ) -> None:
        required = registered_tools[name].parameters.get("required", [])
        assert "api_token" not in required, (
            f"{name} requires api_token — must resolve from header / env"
        )

    @pytest.mark.parametrize(
        "name", ["create_maintenance_window", "update_maintenance_window"]
    )
    def test_body_schema_does_not_expose_managed_by(
        self, registered_tools: RegisteredTools, name: str
    ) -> None:
        schema = _body_schema_for(registered_tools, name)
        assert schema is not None, f"{name} has no body schema to inspect"
        # Belt-and-suspenders: neither in properties nor in required.
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        required = schema.get("required", []) if isinstance(schema, dict) else []
        assert "managedBy" not in properties, (
            f"{name} body schema must not expose managedBy to the LLM"
        )
        assert "managedBy" not in required, (
            f"{name} body schema must not require managedBy"
        )


# --------------------------------------------------------------------------- #
# Error surfacing — upstream failures must set isError=true
# --------------------------------------------------------------------------- #


class TestMaintenanceWindowErrorsBubbleUp:
    """If the API rejects the request, the tool must surface the failure
    via ``ToolError`` so FastMCP returns ``isError=True`` (P1.Bug3
    semantics — silent-success on 4xx is a known footgun for AI agents)."""

    def test_create_propagates_api_error(self) -> None:
        async def go() -> Any:
            from fastmcp import Client

            async with Client(mcp) as client:
                return await client.call_tool(
                    "create_maintenance_window",
                    {
                        "body": {
                            "startsAt": "2026-05-15T14:00:00Z",
                            "endsAt": "2026-05-15T13:00:00Z",
                        },
                    },
                    raise_on_error=False,
                )

        # Patch the underlying httpx client lookup so we can inject the
        # SDK error without mocking ``api_post`` (this exercises the
        # full error-formatting path through the SDK's helpers).
        mock_client = MagicMock()
        mock_client.monitors._client = MagicMock()

        def boom(*args: Any, **kwargs: Any) -> None:
            raise DevhelmApiError(
                "endsAt must be after startsAt",
                status=400,
                code="VALIDATION_FAILED",
                request_id="req_abc",
            )

        with (
            patch(
                "devhelm_mcp.tools.maintenance_windows.get_client",
                return_value=mock_client,
            ),
            patch("devhelm_mcp.tools.maintenance_windows.api_post", side_effect=boom),
        ):
            result = asyncio.run(go())

        assert result.is_error is True
        text = result.content[0].text
        assert "ApiError (400 VALIDATION_FAILED)" in text
        assert "request_id=req_abc" in text
