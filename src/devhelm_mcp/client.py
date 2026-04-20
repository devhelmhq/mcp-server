"""SDK client helpers for tool implementations."""

from __future__ import annotations

import os
from typing import Any

from devhelm import Devhelm, DevhelmError
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
    """Format a DevhelmError into a human-readable message for the LLM."""
    parts = [f"Error ({err.code}): {err.message}"]
    if err.detail:
        parts.append(f"Detail: {err.detail}")
    return " | ".join(parts)


def serialize(data: object) -> dict[str, Any] | list[dict[str, Any]]:
    """Serialize Pydantic models or other objects to JSON-safe dicts."""
    if hasattr(data, "model_dump"):
        return data.model_dump(mode="json")  # type: ignore[no-any-return]
    if isinstance(data, list):
        return [serialize(item) for item in data]  # type: ignore[misc]
    if isinstance(data, dict):
        return {k: serialize(v) for k, v in data.items()}
    return data  # type: ignore[return-value]
