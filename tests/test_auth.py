"""Tests for ``Authorization: Bearer`` → ``api_token`` resolution.

Round-2 DevEx surfaced a hosted-server papercut: every ``tools/call`` returned
``-32602: api_token Field required`` even though the request already carried
``Authorization: Bearer dh_live_…``. Agents had to duplicate the secret in
both the header and every single tool call's arguments.

The fix lives in :mod:`devhelm_mcp.client`'s ``resolve_api_token`` / the
optional ``api_token`` arg on every tool. These tests pin the resolution
order:

  1. Explicit ``api_token`` argument (back-compat)
  2. ``Authorization: Bearer <token>`` header on the active HTTP request
  3. ``DEVHELM_API_TOKEN`` env var (stdio fallback)
  4. ``DevhelmAuthError`` if none of the above produce a token

Both unit-level (``resolve_api_token``) and end-to-end (real ASGI POST to
``/mcp``) coverage are included so the bug can never regress unnoticed.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import patch

import pytest
from devhelm import DevhelmAuthError
from starlette.testclient import TestClient

from devhelm_mcp.client import _bearer_token_from_request, resolve_api_token
from devhelm_mcp.server import app, mcp

# --------------------------------------------------------------------------- #
# resolve_api_token — unit-level resolution-order coverage
# --------------------------------------------------------------------------- #


class TestResolveApiToken:
    def test_explicit_arg_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Even if a header AND the env var would resolve a token, the
        # explicit argument must take precedence — that's the existing
        # path-style ``/{api_key}/mcp`` contract and any client we'd
        # break would silently start auth'ing as the wrong workspace.
        monkeypatch.setenv("DEVHELM_API_TOKEN", "env-token")
        with patch(
            "devhelm_mcp.client._bearer_token_from_request",
            return_value="header-token",
        ):
            assert resolve_api_token("explicit-token") == "explicit-token"

    def test_header_used_when_arg_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("DEVHELM_API_TOKEN", raising=False)
        with patch(
            "devhelm_mcp.client._bearer_token_from_request",
            return_value="header-token",
        ):
            assert resolve_api_token(None) == "header-token"

    def test_header_used_when_arg_empty_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An empty string is falsy and must NOT be treated as a valid
        # token — fall through to the header / env path. Otherwise an
        # LLM that omits the field but still sends `"api_token": ""`
        # would 401 instead of using the bearer header.
        monkeypatch.delenv("DEVHELM_API_TOKEN", raising=False)
        with patch(
            "devhelm_mcp.client._bearer_token_from_request",
            return_value="header-token",
        ):
            assert resolve_api_token("") == "header-token"

    def test_env_var_used_when_no_arg_and_no_header(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DEVHELM_API_TOKEN", "env-token")
        with patch(
            "devhelm_mcp.client._bearer_token_from_request",
            return_value=None,
        ):
            assert resolve_api_token(None) == "env-token"

    def test_raises_devhelm_auth_error_when_nothing_resolves(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("DEVHELM_API_TOKEN", raising=False)
        with patch(
            "devhelm_mcp.client._bearer_token_from_request",
            return_value=None,
        ):
            with pytest.raises(DevhelmAuthError) as excinfo:
                resolve_api_token(None)
            assert excinfo.value.status == 401
            # The message must mention all three ways to provide the token
            # — the LLM uses this string verbatim to ask the user.
            msg = str(excinfo.value)
            assert "api_token" in msg
            assert "Authorization" in msg
            assert "DEVHELM_API_TOKEN" in msg


# --------------------------------------------------------------------------- #
# _bearer_token_from_request — header parsing
# --------------------------------------------------------------------------- #


class TestBearerTokenFromRequest:
    def test_returns_none_when_no_active_http_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pure stdio call (no FastMCP HTTP context). The helper must
        # silently return None — never raise — so the env-var path can
        # take over.
        assert _bearer_token_from_request() is None

    @pytest.mark.parametrize(
        ("header_value", "expected"),
        [
            ("Bearer dh_live_xxx", "dh_live_xxx"),
            ("bearer dh_live_yyy", "dh_live_yyy"),
            ("BEARER dh_live_zzz", "dh_live_zzz"),
            ("Bearer    dh_live_padded   ", "dh_live_padded"),
        ],
    )
    def test_parses_bearer_with_case_insensitive_scheme(
        self, header_value: str, expected: str
    ) -> None:
        with patch(
            "fastmcp.server.dependencies.get_http_headers",
            return_value={"authorization": header_value},
        ):
            assert _bearer_token_from_request() == expected

    @pytest.mark.parametrize(
        "header_value",
        ["Basic dXNlcjpwYXNz", "ApiKey dh_live_xxx", "", "Bearer "],
    )
    def test_returns_none_for_non_bearer_or_empty(self, header_value: str) -> None:
        with patch(
            "fastmcp.server.dependencies.get_http_headers",
            return_value={"authorization": header_value},
        ):
            assert _bearer_token_from_request() is None


# --------------------------------------------------------------------------- #
# End-to-end: POST /mcp with Authorization header, no api_token in args
# --------------------------------------------------------------------------- #


def _initialize_session(client: TestClient, headers: dict[str, str]) -> str:
    """Drive the MCP ``initialize`` handshake and return the session id.

    The streamable-HTTP transport requires a session id for every
    subsequent request. The server hands one out on the response to the
    ``initialize`` call via the ``mcp-session-id`` header.
    """
    init_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "auth-test", "version": "0.0.0"},
        },
    }
    resp = client.post(
        "/mcp/",
        json=init_payload,
        headers={"Accept": "application/json, text/event-stream", **headers},
    )
    assert resp.status_code == 200, resp.text
    session_id = resp.headers.get("mcp-session-id")
    assert session_id, "server didn't issue mcp-session-id on initialize"
    # ``notifications/initialized`` finishes the handshake on the client side.
    resp = client.post(
        "/mcp/",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers={
            "Accept": "application/json, text/event-stream",
            "mcp-session-id": session_id,
            **headers,
        },
    )
    assert resp.status_code in (200, 202), resp.text
    return session_id


def _parse_sse_or_json(resp_text: str) -> dict[str, Any]:
    """Parse an MCP HTTP response which may be either JSON or an SSE event."""
    text = resp_text.strip()
    if text.startswith("{"):
        return json.loads(text)  # type: ignore[no-any-return]
    # Server-sent events: lines like ``event: message`` and ``data: {...}``.
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[len("data:") :].strip())  # type: ignore[no-any-return]
    raise AssertionError(f"Couldn't parse MCP response: {resp_text!r}")


class TestBearerHeaderEndToEnd:
    """The hosted ``/mcp`` endpoint must accept header-only auth.

    These drive the real Starlette app (``devhelm_mcp.server.app``) over
    ``starlette.testclient.TestClient`` so the path mirrors what curl /
    Cursor / Claude Desktop send. The ``list_monitors`` tool is patched
    to capture the resolved token instead of hitting the live API — the
    contract under test is the resolution layer, not the SDK.
    """

    def test_tool_call_with_header_only_resolves_token_from_header(
        self,
    ) -> None:
        captured: dict[str, Any] = {}

        def fake_list_monitors(api_token: str | None = None) -> list[dict[str, Any]]:
            from devhelm_mcp.client import resolve_api_token

            captured["resolved"] = resolve_api_token(api_token)
            captured["arg"] = api_token
            return []

        # Replace the registered tool's underlying function so we can
        # introspect resolution without an outbound HTTP call.
        tools = asyncio.run(mcp.list_tools())
        tool = next(t for t in tools if t.name == "list_monitors")
        original_fn = tool.fn  # type: ignore[attr-defined]
        tool.fn = fake_list_monitors  # type: ignore[attr-defined]

        try:
            with TestClient(app) as client:
                headers = {"Authorization": "Bearer dh_live_from_header"}
                session_id = _initialize_session(client, headers)
                payload = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "list_monitors", "arguments": {}},
                }
                resp = client.post(
                    "/mcp/",
                    json=payload,
                    headers={
                        "Accept": "application/json, text/event-stream",
                        "mcp-session-id": session_id,
                        **headers,
                    },
                )
                assert resp.status_code == 200, resp.text
                body = _parse_sse_or_json(resp.text)
                # No JSON-RPC error envelope.
                assert "error" not in body, body
        finally:
            tool.fn = original_fn  # type: ignore[attr-defined]

        # The tool body resolved the token from the bearer header; the
        # arg was None because the client didn't pass it.
        assert captured["arg"] is None
        assert captured["resolved"] == "dh_live_from_header"

    def test_tool_call_with_arg_overrides_header(self) -> None:
        captured: dict[str, Any] = {}

        def fake_list_monitors(api_token: str | None = None) -> list[dict[str, Any]]:
            from devhelm_mcp.client import resolve_api_token

            captured["resolved"] = resolve_api_token(api_token)
            captured["arg"] = api_token
            return []

        tools = asyncio.run(mcp.list_tools())
        tool = next(t for t in tools if t.name == "list_monitors")
        original_fn = tool.fn  # type: ignore[attr-defined]
        tool.fn = fake_list_monitors  # type: ignore[attr-defined]

        try:
            with TestClient(app) as client:
                headers = {"Authorization": "Bearer dh_live_from_header"}
                session_id = _initialize_session(client, headers)
                payload = {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "list_monitors",
                        "arguments": {"api_token": "dh_live_from_arg"},
                    },
                }
                resp = client.post(
                    "/mcp/",
                    json=payload,
                    headers={
                        "Accept": "application/json, text/event-stream",
                        "mcp-session-id": session_id,
                        **headers,
                    },
                )
                assert resp.status_code == 200, resp.text
                body = _parse_sse_or_json(resp.text)
                assert "error" not in body, body
        finally:
            tool.fn = original_fn  # type: ignore[attr-defined]

        # Arg wins over header (back-compat for path-style clients).
        assert captured["arg"] == "dh_live_from_arg"
        assert captured["resolved"] == "dh_live_from_arg"
