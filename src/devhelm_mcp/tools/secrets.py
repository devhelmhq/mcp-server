"""Secret tools — encrypted secrets for monitor authentication."""

from __future__ import annotations

from typing import Any

from devhelm import DevhelmError
from devhelm.types import CreateSecretRequest, UpdateSecretRequest
from fastmcp import FastMCP
from pydantic import ValidationError

from devhelm_mcp.client import (
    format_error,
    format_validation_error,
    get_client,
    serialize,
    validate_body,
)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_secrets(api_token: str) -> Any:
        """List all secrets (metadata only, values are never returned)."""
        try:
            return serialize(get_client(api_token).secrets.list())
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_secret(api_token: str, body: dict[str, Any]) -> Any:
        """Create an encrypted secret.

        Required fields: key, value. The value is encrypted at rest
        and can be referenced in monitor auth configs as {{secrets.KEY}}.
        """
        try:
            validate_body(body, CreateSecretRequest)
            return serialize(get_client(api_token).secrets.create(body))
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_secret(api_token: str, key: str, body: dict[str, Any]) -> Any:
        """Update a secret's value by key."""
        try:
            validate_body(body, UpdateSecretRequest)
            return serialize(get_client(api_token).secrets.update(key, body))
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_secret(api_token: str, key: str) -> str:
        """Delete a secret by key."""
        try:
            get_client(api_token).secrets.delete(key)
            return "Secret deleted successfully."
        except DevhelmError as e:
            return format_error(e)
