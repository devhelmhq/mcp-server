"""SDK client helpers for tool implementations."""

from __future__ import annotations

import os
from typing import Any

from devhelm import Devhelm, DevhelmError

API_BASE_URL = os.getenv("DEVHELM_API_URL", "https://api.devhelm.io")


def get_client(api_token: str) -> Devhelm:
    """Build a Devhelm SDK client from the user's API token."""
    return Devhelm(token=api_token, base_url=API_BASE_URL)


def format_error(err: DevhelmError) -> str:
    """Format a DevhelmError into a human-readable message for the LLM."""
    parts = [f"Error ({err.code}): {err.message}"]
    if err.detail:
        parts.append(f"Detail: {err.detail}")
    return " | ".join(parts)


def serialize(data: Any) -> Any:
    """Serialize Pydantic models or other objects to JSON-safe dicts."""
    if hasattr(data, "model_dump"):
        return data.model_dump(mode="json")
    if isinstance(data, list):
        return [serialize(item) for item in data]
    if isinstance(data, dict):
        return {k: serialize(v) for k, v in data.items()}
    return data
