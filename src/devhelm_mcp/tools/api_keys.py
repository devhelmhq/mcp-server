"""API key tools — manage API keys for programmatic access."""

from __future__ import annotations

from typing import Any

from devhelm import DevhelmError
from fastmcp import FastMCP

from devhelm_mcp.client import format_error, get_client, serialize


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_api_keys(api_token: str) -> Any:
        """List all API keys in the workspace."""
        try:
            return serialize(get_client(api_token).api_keys.list())
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_api_key(api_token: str, body: dict[str, Any]) -> Any:
        """Create a new API key. The key value is returned only once.

        Required fields: name. Optional: expiresAt.
        """
        try:
            return serialize(get_client(api_token).api_keys.create(body))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def revoke_api_key(api_token: str, key_id: str) -> str:
        """Revoke an API key (disables it without deleting)."""
        try:
            get_client(api_token).api_keys.revoke(key_id)
            return "API key revoked successfully."
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_api_key(api_token: str, key_id: str) -> str:
        """Delete an API key permanently."""
        try:
            get_client(api_token).api_keys.delete(key_id)
            return "API key deleted successfully."
        except DevhelmError as e:
            return format_error(e)
