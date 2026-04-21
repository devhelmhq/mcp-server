"""Tests for the SDK client wrapper helpers used by every MCP tool.

The MCP server's only contact with the API is through the `devhelm` SDK
client wrapper in `devhelm_mcp.client`. The most user-visible function is
`format_error`, which translates SDK exceptions into the strings the LLM
shows to the user. We pin its output here so that:

  * regressions in the error envelope (e.g. losing `code` or `request_id`)
    surface as a unit-test failure rather than a degraded UX in the LLM,
  * downstream MCP clients (Cursor, Claude Desktop) can parse the error
    string for the `request_id` token when filing support tickets.
"""

from __future__ import annotations

from devhelm import (
    DevhelmApiError,
    DevhelmAuthError,
    DevhelmNotFoundError,
    DevhelmTransportError,
    DevhelmValidationError,
)

from devhelm_mcp.client import format_error


def test_format_validation_error_includes_field_path() -> None:
    err = DevhelmValidationError(
        "Request body validation failed",
        errors=[{"loc": ("body", "url"), "msg": "must not be empty"}],
    )
    out = format_error(err)
    assert out.startswith("ValidationError: Request body validation failed")
    assert "body.url: must not be empty" in out


def test_format_api_error_surfaces_status_code_and_request_id() -> None:
    err = DevhelmApiError(
        "Monitor not found",
        status=404,
        code="NOT_FOUND",
        request_id="req_abc123",
        detail="No monitor with id mon_42",
    )
    out = format_error(err)
    assert "ApiError (404 NOT_FOUND): Monitor not found" in out
    assert "Detail: No monitor with id mon_42" in out
    assert "request_id=req_abc123" in out


def test_format_api_error_omits_code_when_absent() -> None:
    err = DevhelmApiError("Server error", status=500)
    out = format_error(err)
    assert out.startswith("ApiError (500): Server error")
    assert "request_id" not in out


def test_format_api_error_request_id_present_without_code() -> None:
    err = DevhelmApiError(
        "Rate limit exceeded",
        status=429,
        request_id="req_xyz",
    )
    out = format_error(err)
    assert "ApiError (429): Rate limit exceeded" in out
    assert "request_id=req_xyz" in out


def test_format_auth_and_not_found_subclasses_use_api_error_shape() -> None:
    # Subclasses still go through the DevhelmApiError branch, so the
    # request_id/code surfacing must work for them too.
    auth = DevhelmAuthError(
        "Missing or invalid token",
        status=401,
        code="UNAUTHORIZED",
        request_id="req_auth_1",
    )
    assert "ApiError (401 UNAUTHORIZED)" in format_error(auth)
    assert "request_id=req_auth_1" in format_error(auth)

    nf = DevhelmNotFoundError(
        "Monitor not found",
        status=404,
        code="NOT_FOUND",
        request_id="req_nf_1",
    )
    assert "ApiError (404 NOT_FOUND)" in format_error(nf)
    assert "request_id=req_nf_1" in format_error(nf)


def test_format_transport_error_passthrough() -> None:
    err = DevhelmTransportError("connection refused")
    out = format_error(err)
    assert out == "TransportError: connection refused"
