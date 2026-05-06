"""Round-3 DevEx fixes — pinned regression tests.

Each ``TestX`` class below pins one fix from the round-3 audit. Keeping the
coverage in a dedicated file (rather than scattered across ``test_tools``,
``test_client``, etc.) makes it obvious which behavior survives re-shuffles
of the SDK or FastMCP framework.

Bug index (mirrors PR #18 description):
  P0.Bug5 + P1.Bug4 + P1.Bug5 — ``managedBy="MCP"`` is server-set
  P1.Bug3                    — upstream API errors surface as ``isError=True``
  P2.Bug7                    — ``api_token`` is hidden from ``inputSchema``
  P2.Bug8                    — ``serverInfo.version`` reports the package
  P2.Bug9                    — FastMCP banner suppressed on stdio
  P1.Bug6                    — ``/mcp`` and ``/mcp/`` both return 200, no 307
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from devhelm import DevhelmApiError, DevhelmTransportError
from fastmcp import Client
from starlette.testclient import TestClient

from devhelm_mcp.server import _package_version, _strip_internal_schema_fields, app, mcp

RegisteredTools = dict[str, Any]


@pytest.fixture(scope="module")
def registered_tools() -> RegisteredTools:
    # The schema strip now runs only inside the Starlette lifespan (HTTP)
    # or before ``mcp.run()`` (stdio) — see v0.7.2 hotfix. Tests that
    # inspect the registered tool schemas have to perform the strip
    # explicitly, otherwise they see the raw FastMCP-generated schema.
    asyncio.run(_strip_internal_schema_fields())
    tools = asyncio.run(mcp.list_tools())
    return {t.name: t for t in tools}


# --------------------------------------------------------------------------- #
# P0.Bug5 + P1.Bug4 + P1.Bug5 — managedBy is forced server-side to "MCP"
# --------------------------------------------------------------------------- #


class TestCreateMonitorAlwaysSetsManagedByMcp:
    """``create_monitor`` is the AI agent's single entry into the monitor
    table — every row it creates must be attributed to ``managedBy="MCP"``
    so the dashboard can filter / count agent-created monitors honestly.

    The fix is two-layer:
      1. Hide ``managedBy`` from the JSON Schema FastMCP advertises so the
         LLM never sees the field as a callable parameter.
      2. ``pop()`` the field from the payload server-side and inject ``"MCP"``
         before forwarding to the SDK, so a permissive client that smuggles
         the field through still gets overridden.
    """

    def _create_monitor_body_schema(
        self, registered_tools: RegisteredTools
    ) -> dict[str, Any]:
        schema = registered_tools["create_monitor"].parameters
        body = schema["properties"]["body"]
        if "$ref" in body:
            ref = body["$ref"].rsplit("/", 1)[-1]
            return schema["$defs"][ref]  # type: ignore[no-any-return]
        return body  # type: ignore[no-any-return]

    def test_managed_by_not_in_body_schema(
        self, registered_tools: RegisteredTools
    ) -> None:
        body = self._create_monitor_body_schema(registered_tools)
        assert "managedBy" not in body.get("properties", {}), (
            "managedBy must be hidden from the create_monitor input schema"
        )
        assert "managedBy" not in body.get("required", []), (
            "managedBy must not be required (it's server-set)"
        )

    def test_payload_carries_managed_by_mcp_when_omitted(self) -> None:
        captured: dict[str, Any] = {}

        def fake_create(payload: dict[str, Any]) -> dict[str, Any]:
            captured["payload"] = payload
            return {"id": "mon_x", **payload}

        mock_client = MagicMock()
        mock_client.monitors.create.side_effect = fake_create

        with patch("devhelm_mcp.tools.monitors.get_client", return_value=mock_client):
            asyncio.run(
                mcp.call_tool(
                    "create_monitor",
                    {
                        "body": {
                            "name": "test",
                            "type": "HTTP",
                            "config": {
                                "url": "https://example.com",
                                "method": "GET",
                            },
                        },
                    },
                )
            )

        assert captured["payload"]["managedBy"] == "MCP"

    def test_payload_overrides_managed_by_when_caller_smuggles_one(self) -> None:
        # A permissive HTTP client could still POST a body with ``managedBy``
        # set even though the schema doesn't expose it. Belt-and-suspenders:
        # the server-side strip + inject must overwrite *any* value before
        # the SDK call, so attribution is guaranteed.
        captured: dict[str, Any] = {}

        def fake_create(payload: dict[str, Any]) -> dict[str, Any]:
            captured["payload"] = payload
            return {"id": "mon_x", **payload}

        mock_client = MagicMock()
        mock_client.monitors.create.side_effect = fake_create

        with patch("devhelm_mcp.tools.monitors.get_client", return_value=mock_client):
            asyncio.run(
                mcp.call_tool(
                    "create_monitor",
                    {
                        "body": {
                            "name": "test",
                            "type": "HTTP",
                            "config": {
                                "url": "https://example.com",
                                "method": "GET",
                            },
                            "managedBy": "DASHBOARD",
                        },
                    },
                )
            )

        assert captured["payload"]["managedBy"] == "MCP", (
            "managedBy must be overridden, not preserved"
        )


# --------------------------------------------------------------------------- #
# P1.Bug3 — upstream API errors surface with isError=True
# --------------------------------------------------------------------------- #


class TestUpstreamErrorsReportIsError:
    """Per the MCP spec, tools that fail must set ``isError=true`` on the
    ``CallToolResult``. Returning the formatted error as a regular tool
    return value (the previous behavior) made every API failure look like
    a successful tool call to the LLM, which then confidently reported
    "monitor created" after a 4xx.

    This test exercises the full FastMCP middleware chain via ``Client`` so
    we catch any future middleware that might swallow the ``ToolError``.
    """

    def _run_tool_and_get_result(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> Any:
        async def go() -> Any:
            async with Client(mcp) as client:
                return await client.call_tool(
                    tool_name, arguments, raise_on_error=False
                )

        return asyncio.run(go())

    def test_api_error_returns_is_error_true(self) -> None:
        mock_client = MagicMock()
        mock_client.monitors.list.side_effect = DevhelmApiError(
            "Monitor not found",
            status=404,
            code="NOT_FOUND",
            request_id="req_abc123",
        )

        with patch("devhelm_mcp.tools.monitors.get_client", return_value=mock_client):
            result = self._run_tool_and_get_result("list_monitors", {})

        assert result.is_error is True
        text = result.content[0].text
        assert "ApiError (404 NOT_FOUND): Monitor not found" in text
        # Request id must survive the wrap so users can quote it for support.
        assert "request_id=req_abc123" in text

    def test_transport_error_returns_is_error_true(self) -> None:
        mock_client = MagicMock()
        mock_client.monitors.list.side_effect = DevhelmTransportError(
            "connection refused"
        )

        with patch("devhelm_mcp.tools.monitors.get_client", return_value=mock_client):
            result = self._run_tool_and_get_result("list_monitors", {})

        assert result.is_error is True
        assert "TransportError: connection refused" in result.content[0].text

    def test_delete_tool_also_sets_is_error_on_failure(self) -> None:
        # ``delete_monitor`` returns a plain string on success (rather than a
        # serialized dict) — make sure the ``isError`` wrap survives that
        # narrower return-type contract too.
        mock_client = MagicMock()
        mock_client.monitors.delete.side_effect = DevhelmApiError(
            "Insufficient permissions",
            status=403,
            code="FORBIDDEN",
        )

        with patch("devhelm_mcp.tools.monitors.get_client", return_value=mock_client):
            result = self._run_tool_and_get_result(
                "delete_monitor", {"monitor_id": "mon_x"}
            )

        assert result.is_error is True
        assert "ApiError (403 FORBIDDEN)" in result.content[0].text


# --------------------------------------------------------------------------- #
# P2.Bug7 — api_token must not appear in any tool's inputSchema
# --------------------------------------------------------------------------- #


class TestApiTokenHiddenFromInputSchema:
    """``api_token`` is still accepted as a Python kwarg for back-compat with
    path-style ``/{api_key}/mcp`` clients (and direct test invocation), but
    it must NEVER appear in the JSON Schema FastMCP advertises. Surfacing it
    invited the LLM to populate the field from chat context, leaking the
    user's token into prompt traces / model telemetry.
    """

    def test_no_tool_exposes_api_token_in_properties(
        self, registered_tools: RegisteredTools
    ) -> None:
        offenders = [
            name
            for name, tool in registered_tools.items()
            if "api_token" in tool.parameters.get("properties", {})
        ]
        assert not offenders, f"Tools still surfacing api_token to the LLM: {offenders}"

    def test_no_tool_requires_api_token(
        self, registered_tools: RegisteredTools
    ) -> None:
        offenders = [
            name
            for name, tool in registered_tools.items()
            if "api_token" in tool.parameters.get("required", [])
        ]
        assert not offenders, (
            f"Tools still requiring api_token: {offenders} — must resolve "
            "from header / env"
        )

    def test_api_token_still_accepted_as_python_kwarg(self) -> None:
        # Path-style ``/{api_key}/mcp`` clients (and direct test calls) need
        # to continue passing ``api_token`` through. The schema strip must
        # not break the function signature.
        captured: dict[str, Any] = {}

        def fake_list() -> list[dict[str, Any]]:
            return []

        mock_client = MagicMock()
        mock_client.monitors.list.side_effect = fake_list

        def fake_get_client(api_token: str | None = None) -> MagicMock:
            captured["api_token"] = api_token
            return mock_client

        with patch(
            "devhelm_mcp.tools.monitors.get_client", side_effect=fake_get_client
        ):
            asyncio.run(mcp.call_tool("list_monitors", {"api_token": "explicit_token"}))

        assert captured["api_token"] == "explicit_token"


# --------------------------------------------------------------------------- #
# P2.Bug8 — serverInfo.version reports the package, not the FastMCP framework
# --------------------------------------------------------------------------- #


class TestServerInfoVersion:
    def test_fastmcp_version_pinned_to_package_version(self) -> None:
        # The FastMCP server's ``version`` field flows directly into the
        # MCP ``initialize`` handshake's ``serverInfo.version``. Before the
        # round-3 fix it defaulted to the FastMCP framework version (e.g.
        # ``"3.2.4"``), which made it impossible to correlate user reports
        # with a specific MCP server release.
        version = _package_version()
        assert isinstance(version, str)
        assert mcp.version == version

    def test_fastmcp_name_pinned_to_package_name(self) -> None:
        # The MCP wire identity must match the package name so client
        # configs / docs that point at "devhelm-mcp-server" actually find it.
        assert mcp.name == "devhelm-mcp-server"

    def test_initialize_response_includes_server_version(self) -> None:
        # End-to-end: drive the real Starlette app and assert
        # ``serverInfo.version`` matches the package version. Anything less
        # would let a future refactor that bypasses ``mcp.version`` slip
        # through.
        with TestClient(app) as client:
            resp = client.post(
                "/mcp/",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "0.0.0"},
                    },
                },
                headers={"Accept": "application/json, text/event-stream"},
            )
        assert resp.status_code == 200, resp.text
        body_text = resp.text
        # The handshake may come back as either JSON or an SSE event; both
        # carry the same JSON-RPC body.
        assert _package_version() in body_text


# --------------------------------------------------------------------------- #
# P1.Bug6 — POST /mcp and POST /mcp/ both reach the JSON-RPC handler
# --------------------------------------------------------------------------- #


class TestTrailingSlashNormalization:
    """Naive HTTP clients drop the body and ``Authorization`` header on a
    307. Production observed every MCP client (Cursor, Claude Desktop, raw
    curl) bouncing through ``/mcp`` → ``/mcp/`` and failing the JSON-RPC
    handshake because the body was lost in flight.

    The middleware fix rewrites the ASGI scope before routing so both URLs
    deliver to the inner streamable-HTTP handler with no redirect.
    """

    def _initialize_payload(self) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "trailing-slash-test", "version": "0.0.0"},
            },
        }

    def test_post_mcp_no_trailing_slash_returns_200_not_307(self) -> None:
        with TestClient(app) as client:
            resp = client.post(
                "/mcp",
                json=self._initialize_payload(),
                headers={"Accept": "application/json, text/event-stream"},
                follow_redirects=False,
            )
        assert resp.status_code == 200, (
            f"Expected 200 (no redirect), got {resp.status_code}: {resp.text[:200]}"
        )
        assert resp.headers.get("mcp-session-id"), (
            "initialize must hand out a session id"
        )

    def test_post_mcp_trailing_slash_returns_200(self) -> None:
        with TestClient(app) as client:
            resp = client.post(
                "/mcp/",
                json=self._initialize_payload(),
                headers={"Accept": "application/json, text/event-stream"},
                follow_redirects=False,
            )
        assert resp.status_code == 200, resp.text
        assert resp.headers.get("mcp-session-id")

    def test_path_style_mcp_no_trailing_slash_returns_200(self) -> None:
        # ``/{api_key}/mcp`` is the URL-only auth variant; same redirect
        # bug applies, same fix has to cover it.
        with TestClient(app) as client:
            resp = client.post(
                "/dh_test_token/mcp",
                json=self._initialize_payload(),
                headers={"Accept": "application/json, text/event-stream"},
                follow_redirects=False,
            )
        assert resp.status_code == 200, resp.text

    def test_health_endpoint_unaffected(self) -> None:
        # The path normalizer must only fire on the MCP family — health and
        # any future top-level routes must pass through untouched.
        with TestClient(app) as client:
            resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


# --------------------------------------------------------------------------- #
# v0.7.2 hotfix — module import + lifespan must work from a running loop
# --------------------------------------------------------------------------- #


class TestImportFromRunningLoopDoesNotCrash:
    """v0.7.1 regressed by calling ``asyncio.run()`` at module import time.

    Uvicorn imports the user app from inside ``asyncio.run(self.serve(...))``,
    so by the time ``devhelm_mcp.server`` ran its top-level
    ``_strip_internal_schema_fields()`` it was already inside a running
    event loop and Python raised ``RuntimeError: asyncio.run() cannot be
    called from a running event loop``. Cluster pods crashed in a tight
    restart loop until the deployment was reverted.

    The fix moved the strip into the Starlette lifespan (HTTP) and into
    ``_run_stdio()`` (stdio). This test pins both halves: importing the
    module from inside a running loop must succeed, and the lifespan
    must perform the strip on entry.
    """

    def test_lifespan_entry_strips_internal_fields(self) -> None:
        async def go() -> None:
            # Re-import inside the running loop — this is what Uvicorn does.
            import importlib

            import devhelm_mcp.server as srv

            srv = importlib.reload(srv)

            async with srv.app.router.lifespan_context(srv.app):
                tools = await srv.mcp.list_tools(run_middleware=False)
                api_token_leaks = [
                    t.name
                    for t in tools
                    if isinstance(t.parameters, dict)
                    and "api_token"
                    in (t.parameters.get("properties") or {})
                ]
                assert not api_token_leaks, (
                    f"lifespan must strip api_token from {api_token_leaks!r}"
                )

        asyncio.run(go())
