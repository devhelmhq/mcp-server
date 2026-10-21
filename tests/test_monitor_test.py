"""``test_monitor`` and ``test_monitor_run``.

``POST /api/v1/monitors/{id}/test`` answers 200 with the probe result for
uptime monitors and 202 with a queued validation run for browser and
multi-step API monitors. ``test_monitor`` returns the probe result unchanged
(no wrapping key) and the run for code monitors; ``test_monitor_run`` queues
a run with an optional target. The tools run the real SDK ``Monitors``
resource against an ``httpx.MockTransport`` so the wire request and the
tool output are both asserted.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from devhelm.resources.monitors import Monitors
from fastmcp.exceptions import ToolError

from devhelm_mcp.server import _strip_internal_schema_fields, mcp

MONITOR_ID = "550e8400-e29b-41d4-a716-446655440000"

_PROBE_RESULT: dict[str, Any] = {
    "passed": True,
    "error": None,
    "statusCode": 200,
    "responseTimeMs": 42,
    "assertionResults": [],
}

_QUEUED_RUN: dict[str, Any] = {
    "id": "6f1c2a3b-4d5e-4f60-8a7b-9c0d1e2f3a4b",
    "organizationId": 1,
    "monitorId": MONITOR_ID,
    "monitorType": "BROWSER",
    "revisionId": "7a8b9c0d-1e2f-4a3b-8c4d-5e6f7a8b9c0d",
    "region": "us-east",
    "source": "VALIDATION",
    "countsTowardHealth": False,
    "enqueuedAt": "2026-10-21T10:00:00Z",
    "phase": "QUEUED",
    "cancelRequested": False,
    "bundleDigest": "sha256:abc",
    "capturePolicySnapshot": {},
    "bindingVersionSnapshot": {},
    "stream": False,
    "evidence": [],
    "tabCounts": {"steps": 0, "assets": 0, "diff": 0},
    "attempt": 1,
    "attemptOf": 1,
    "attempts": [],
    "executionAttempts": [],
}


def _call(
    arguments: dict[str, Any],
    status: int,
    body: dict[str, Any],
    tool: str = "test_monitor",
) -> tuple[Any, list[httpx.Request]]:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(status, json=body)

    http = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://localhost:8080"
    )
    client = MagicMock()
    client.monitors = Monitors(http)

    async def go() -> Any:
        await _strip_internal_schema_fields()
        return await mcp.call_tool(tool, {"monitor_id": MONITOR_ID, **arguments})

    with patch("devhelm_mcp.tools.monitors.get_client", return_value=client):
        result = asyncio.run(go())
    return result, captured


def _payload(result: Any) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(result.content[0].text)
    return data


def test_test_monitor_returns_probe_result_unwrapped() -> None:
    result, captured = _call({}, 200, {"data": _PROBE_RESULT})
    out = _payload(result)
    # Same shape as before: the serialized probe result, no wrapping key.
    assert "kind" not in out
    assert out["passed"] is True
    assert out["statusCode"] == 200
    assert out["assertionResults"] == []
    assert captured[0].url.path == f"/api/v1/monitors/{MONITOR_ID}/test"
    assert captured[0].content == b""


def test_test_monitor_returns_run_for_code_monitor() -> None:
    result, _ = _call({}, 202, {"data": _QUEUED_RUN})
    out = _payload(result)
    assert out["id"] == _QUEUED_RUN["id"]
    assert out["countsTowardHealth"] is False


def test_test_monitor_run_returns_run_and_sends_target() -> None:
    env_id = "8b9c0d1e-2f3a-4b4c-9d5e-6f7a8b9c0d1e"
    result, captured = _call(
        {"environment_id": env_id, "region": "eu-west"},
        202,
        {"data": _QUEUED_RUN},
        tool="test_monitor_run",
    )
    assert _payload(result)["id"] == _QUEUED_RUN["id"]
    assert json.loads(captured[0].content) == {
        "environmentId": env_id,
        "region": "eu-west",
    }


def test_test_monitor_run_sends_no_body_by_default() -> None:
    _, captured = _call({}, 202, {"data": _QUEUED_RUN}, tool="test_monitor_run")
    assert captured[0].content == b""


def test_test_monitor_run_on_uptime_monitor_is_a_tool_error() -> None:
    with pytest.raises(ToolError, match=r"test\(\)"):
        _call({}, 200, {"data": _PROBE_RESULT}, tool="test_monitor_run")


def test_input_schemas() -> None:
    async def go() -> Any:
        await _strip_internal_schema_fields()
        return {t.name: t for t in await mcp.list_tools()}

    tools = asyncio.run(go())
    assert set(tools["test_monitor"].parameters["properties"]) == {"monitor_id"}
    run_props = tools["test_monitor_run"].parameters["properties"]
    assert set(run_props) == {"monitor_id", "environment_id", "region"}
