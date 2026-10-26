"""Tests for the SDK client wrapper helpers used by every MCP tool.

``format_error`` is what the agent reads on ``isError``: a header, one
sentence on what to do, then every ``ErrorResponse`` field as JSON. One test
per category pins the sentence (doc 42 §10 "Errors").
"""

from __future__ import annotations

import json

import pytest
from devhelm import (
    DevhelmApiError,
    DevhelmAuthError,
    DevhelmTransportError,
    DevhelmValidationError,
    WaitTimeoutError,
)
from devhelm._errors import error_from_response

from devhelm_mcp.client import format_error


def _fields(text: str) -> dict[str, object]:
    payload = json.loads(text.splitlines()[-1])
    assert isinstance(payload, dict)
    err = payload["error"]
    assert isinstance(err, dict)
    return err


CATEGORY_SENTENCES = {
    "validation": "Fix the fields named in `errors`",
    "blocked": "must be set up first",
    "auth": "check the DevHelm API token",
    "permission": "lacks a scope or role",
    "ownership": "Another tool owns this resource",
    "plan": "whether to upgrade",
    "quota": "quota for this period is used up",
    "rate_limit": "Wait `retryAfterSeconds`",
    "conflict": "Re-read it, then retry",
    "confirmation_required": "ask before calling again",
    "not_found": "do not guess",
    "gone": "expired past retention",
    "platform": "give the user the `requestId`",
}


@pytest.mark.parametrize(("category", "sentence"), CATEGORY_SENTENCES.items())
def test_every_category_maps_to_an_agent_sentence(category: str, sentence: str) -> None:
    body = {
        "status": 409,
        "code": "SOME_CODE",
        "category": category,
        "retryable": False,
        "message": "refused",
        "timestamp": 1,
        "requestId": "req_1",
        "owner": "TERRAFORM",
        "next": {"command": "devhelm doctor"},
    }
    err = error_from_response(409, json.dumps(body))
    text = format_error(err)
    assert sentence in text
    assert "Suggested next step: devhelm doctor" in text
    fields = _fields(text)
    assert fields["category"] == category
    assert fields["requestId"] == "req_1"
    assert fields["owner"] == "TERRAFORM"
    assert fields["timestamp"] == 1


def test_code_hint_wins_over_category() -> None:
    body = {
        "status": 409,
        "code": "LIVE_REVISION_CHANGED",
        "category": "conflict",
        "retryable": False,
        "message": "stale",
        "timestamp": 1,
    }
    text = format_error(error_from_response(409, json.dumps(body)))
    assert "liveRevisionId" in text


def test_validation_error_lists_field_paths() -> None:
    err = DevhelmValidationError(
        "Request body validation failed",
        errors=[{"loc": ("body", "url"), "msg": "must not be empty"}],  # type: ignore[list-item, typeddict-item]  # partial pydantic ErrorDetails
    )
    fields = _fields(format_error(err))
    assert fields["category"] == "validation"
    assert fields["errors"] == [
        {"code": "FIELD_INVALID", "field": "body.url", "message": "must not be empty"}
    ]


def test_non_envelope_error_falls_back_to_status_category() -> None:
    err = DevhelmApiError("Monitor not found", status=404, request_id="req_abc")
    text = format_error(err)
    fields = _fields(text)
    assert fields["category"] == "not_found"
    assert fields["requestId"] == "req_abc"
    assert DevhelmApiError("boom", status=503).status == 503
    assert _fields(format_error(DevhelmApiError("boom", status=503)))["category"] == (
        "platform"
    )


def test_auth_subclass() -> None:
    err = DevhelmAuthError("bad token", status=401, code="UNAUTHORIZED")
    assert "check the DevHelm API token" in format_error(err)


def test_transport_and_wait_timeout() -> None:
    text = format_error(DevhelmTransportError("connection refused"))
    assert _fields(text)["category"] == "transport"
    assert _fields(text)["retryable"] is True
    timeout = WaitTimeoutError("run-1", "running", timeout_ms=1000)
    fields = _fields(format_error(timeout))
    assert fields["details"] == {"runId": "run-1", "phase": "running"}


def test_get_client_overrides_surface_to_mcp() -> None:
    """MCP traffic is attributed to surface=mcp, SDK identity preserved."""
    from devhelm_mcp.client import get_client

    client = get_client("dummy-token-for-test")
    headers = client._http.headers
    assert headers["x-devhelm-surface"] == "mcp"
    assert headers["x-devhelm-sdk-name"] == "sdk-py"
    assert headers["x-devhelm-surface-version"]
    client.close()
