"""API key tools — manage API keys for programmatic access."""

from __future__ import annotations

from devhelm import DevhelmError
from devhelm.types import CreateApiKeyRequest
from fastmcp import FastMCP

from devhelm_mcp.client import (
    ToolResult,
    as_payload,
    get_client,
    raise_tool_error,
    serialize,
)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_api_keys(api_token: str | None = None) -> ToolResult:
        """List all API keys in the workspace."""
        try:
            return serialize(get_client(api_token).api_keys.list())
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def create_api_key(
        body: CreateApiKeyRequest, api_token: str | None = None
    ) -> ToolResult:
        """Create a new API key. The key value is returned only once.

        Required fields: name. Optional: expiresAt.
        """
        try:
            return serialize(get_client(api_token).api_keys.create(as_payload(body)))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def revoke_api_key(key_id: str, api_token: str | None = None) -> str:
        """Revoke an API key (disables it without deleting)."""
        try:
            get_client(api_token).api_keys.revoke(key_id)
            return "API key revoked successfully."
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def delete_api_key(key_id: str, api_token: str | None = None) -> str:
        """Delete an API key permanently."""
        try:
            get_client(api_token).api_keys.delete(key_id)
            return "API key deleted successfully."
        except DevhelmError as e:
            raise_tool_error(e)
