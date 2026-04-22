"""SDK client helpers for tool implementations."""

from __future__ import annotations

import os
from typing import Any

from devhelm import (
    Devhelm,
    DevhelmApiError,
    DevhelmError,
    DevhelmTransportError,
    DevhelmValidationError,
)
from pydantic import BaseModel

API_BASE_URL = os.getenv("DEVHELM_API_URL", "https://api.devhelm.io")

ToolResult = dict[str, Any] | list[dict[str, Any]] | str


def get_client(api_token: str) -> Devhelm:
    """Build a Devhelm SDK client from the user's API token."""
    return Devhelm(token=api_token, base_url=API_BASE_URL)


def as_payload(model: BaseModel) -> dict[str, Any]:
    """Convert a typed request model into the dict payload the SDK consumes.

    - ``by_alias=True``: keep the OpenAPI field names (camelCase) — the SDK
      forwards the dict verbatim to the API which expects camelCase keys.
    - ``exclude_none=True``: optional fields that the LLM omitted shouldn't
      end up as explicit ``"foo": null`` in the request body, which can be
      semantically different from "absent" for some endpoints (e.g. PATCH
      semantics where ``null`` means "clear").
    """
    return model.model_dump(by_alias=True, exclude_none=True)


def format_error(err: DevhelmError) -> str:
    """Format a DevhelmError into a human-readable message for the LLM.

    The SDK splits errors into three classes (P4):
      * `DevhelmValidationError` — the request (or response) didn't match
        the schema; surfaced before/after I/O.
      * `DevhelmApiError` — the API returned a non-2xx; carries an HTTP
        status code and body.
      * `DevhelmTransportError` — the request never reached a server
        response (DNS, refused, timeout, TLS, …).

    Each gets its own labelled prefix so the LLM can decide whether to
    fix the inputs, retry, or surface the failure to the user.
    """
    if isinstance(err, DevhelmValidationError):
        parts = [f"ValidationError: {err.message}"]
        if err.errors:
            joined = "; ".join(
                f"{'.'.join(str(p) for p in (e.get('loc') or ()))}: {e.get('msg', '')}"
                for e in err.errors
                if isinstance(e, dict)
            )
            if joined:
                parts.append(f"Details: {joined}")
        return " | ".join(parts)

    if isinstance(err, DevhelmApiError):
        # Header line: "ApiError (404 NOT_FOUND): Monitor not found".
        # The SDK always populates `code`, but falls back to the generic
        # "API_ERROR" sentinel when the server didn't supply a more specific
        # one (non-canonical envelopes, HTML proxy errors). Suppress the
        # label in that case — the HTTP status already conveys all the same
        # info, and "(429 API_ERROR)" is just noise.
        if err.code and err.code != "API_ERROR":
            header = f"ApiError ({err.status} {err.code}): {err.message}"
        else:
            header = f"ApiError ({err.status}): {err.message}"
        parts = [header]
        if err.detail:
            parts.append(f"Detail: {err.detail}")
        # Always surface the request id when present so the LLM can pass
        # it back to the user for support correlation. Same value as the
        # X-Request-Id response header.
        if err.request_id:
            parts.append(f"request_id={err.request_id}")
        return " | ".join(parts)

    if isinstance(err, DevhelmTransportError):
        return f"TransportError: {err.message}"

    return f"Error: {err}"


JsonValue = dict[str, "JsonValue"] | list["JsonValue"] | str | int | float | bool | None


def _serialize_value(data: object) -> JsonValue:
    """Serialize a single value into a JSON-safe `JsonValue`.

    The shape mirrors `json.dumps` semantics: dicts become string-keyed
    dicts of `JsonValue`, lists become lists of `JsonValue`, primitives
    pass through, and Pydantic models are dumped via `.model_dump(mode="json")`.
    Anything else (e.g. arbitrary objects) raises `TypeError` rather than
    being silently coerced — `serialize` is meant for SDK return shapes.
    """
    if isinstance(data, BaseModel):
        # `.model_dump(mode="json", by_alias=True)` returns plain Python
        # primitives that are all instances of `JsonValue`; recursing through
        # `_serialize_value` is unnecessary because Pydantic has already done
        # the work.
        #
        # `by_alias=True` is critical: the SDK's generated models pin field
        # names to their snake_case Python identifiers and reach the API's
        # camelCase shape only via `Field(alias=...)`. Dumping without
        # `by_alias` would emit snake_case keys that no consumer (LLM tool
        # output, public docs, our own surface tests) expects.
        dumped = data.model_dump(mode="json", by_alias=True)
        return _serialize_value(dumped)
    if isinstance(data, dict):
        return {str(k): _serialize_value(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_serialize_value(item) for item in data]
    if isinstance(data, (str, int, float, bool)) or data is None:
        return data
    raise TypeError(
        f"Cannot serialize {type(data).__name__!s} to a JSON value; expected "
        "a Pydantic model, dict, list, or primitive."
    )


def serialize(data: object) -> dict[str, Any] | list[dict[str, Any]]:
    """Serialize Pydantic models / dicts / lists to JSON-safe shapes.

    The signature returns the legacy `dict | list-of-dict` envelope that
    every MCP tool is wired against, but the recursive work is delegated
    to `_serialize_value` which is fully typed. We narrow at this single
    boundary, so removing the `Any` from tool implementations only
    requires changing this function's return type without touching any
    callers.
    """
    value = _serialize_value(data)
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        # Tools always feed `serialize` a list of model instances or
        # dicts; the recursive call returns a list of either dicts
        # (Pydantic / dict items) or scalars (which would be a tool
        # bug). Reject scalars loudly so the LLM sees the error.
        out: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                raise TypeError(
                    "serialize() expected list items to be dicts or Pydantic "
                    f"models, got {type(item).__name__}."
                )
            out.append(item)
        return out
    raise TypeError(
        "serialize() expected a Pydantic model, dict, or list of those; "
        f"got {type(data).__name__}."
    )
