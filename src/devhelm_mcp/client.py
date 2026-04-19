"""SDK client helpers for tool implementations."""

from __future__ import annotations

import os
from typing import Any

from devhelm import Devhelm, DevhelmError
from pydantic import BaseModel, ValidationError

API_BASE_URL = os.getenv("DEVHELM_API_URL", "https://api.devhelm.io")

ToolResult = dict[str, Any] | list[dict[str, Any]] | str


def get_client(api_token: str) -> Devhelm:
    """Build a Devhelm SDK client from the user's API token."""
    return Devhelm(token=api_token, base_url=API_BASE_URL)


def validate_body(data: dict[str, Any], model: type[BaseModel]) -> dict[str, Any]:
    """Validate a raw dict through a Pydantic model and return the validated dict.

    Raises ValidationError with clear field-level messages on bad input.
    Returns the original dict (not the model's dump) so alias keys pass through
    to the SDK unchanged.
    """
    model.model_validate(data)
    return data


def format_error(err: DevhelmError) -> str:
    """Format a DevhelmError into a human-readable message for the LLM."""
    parts = [f"Error ({err.code}): {err.message}"]
    if err.detail:
        parts.append(f"Detail: {err.detail}")
    return " | ".join(parts)


def format_validation_error(err: ValidationError) -> str:
    """Format a Pydantic ValidationError into a readable message for the LLM."""
    issues = []
    for e in err.errors():
        loc = " → ".join(str(part) for part in e["loc"])
        issues.append(f"  {loc}: {e['msg']}")
    return "Validation error:\n" + "\n".join(issues)


def serialize(data: object) -> dict[str, Any] | list[dict[str, Any]]:
    """Serialize Pydantic models or other objects to JSON-safe dicts."""
    if hasattr(data, "model_dump"):
        return data.model_dump(mode="json")  # type: ignore[no-any-return]
    if isinstance(data, list):
        return [serialize(item) for item in data]  # type: ignore[misc]
    if isinstance(data, dict):
        return {k: serialize(v) for k, v in data.items()}
    return data  # type: ignore[return-value]
