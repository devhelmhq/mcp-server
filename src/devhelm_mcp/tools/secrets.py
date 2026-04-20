"""Secret tools — encrypted secrets for monitor authentication."""

from __future__ import annotations

from devhelm import DevhelmError
from devhelm.types import CreateSecretRequest, UpdateSecretRequest
from fastmcp import FastMCP

from devhelm_mcp.client import (
    ToolResult,
    as_payload,
    format_error,
    get_client,
    serialize,
)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_secrets(api_token: str) -> ToolResult:
        """List all secrets (metadata only, values are never returned)."""
        try:
            return serialize(get_client(api_token).secrets.list())
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_secret(api_token: str, body: CreateSecretRequest) -> ToolResult:
        """Create an encrypted secret.

        Required fields: key, value. The value is encrypted at rest
        and can be referenced in monitor auth configs as {{secrets.KEY}}.
        """
        try:
            return serialize(get_client(api_token).secrets.create(as_payload(body)))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_secret(
        api_token: str, key: str, body: UpdateSecretRequest
    ) -> ToolResult:
        """Update a secret's value by key."""
        try:
            return serialize(
                get_client(api_token).secrets.update(key, as_payload(body))
            )
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
