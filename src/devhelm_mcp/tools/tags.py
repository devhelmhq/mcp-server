"""Tag tools — organize monitors with tags."""

from __future__ import annotations

from typing import Any

from devhelm import DevhelmError
from fastmcp import FastMCP

from devhelm_mcp.client import format_error, get_client, serialize


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_tags(api_token: str) -> Any:
        """List all tags in the workspace."""
        try:
            return serialize(get_client(api_token).tags.list())
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_tag(api_token: str, tag_id: str) -> Any:
        """Get a tag by ID."""
        try:
            return serialize(get_client(api_token).tags.get(tag_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_tag(api_token: str, body: dict[str, Any]) -> Any:
        """Create a tag.

        Required fields: name. Optional: color.
        """
        try:
            return serialize(get_client(api_token).tags.create(body))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_tag(api_token: str, tag_id: str, body: dict[str, Any]) -> Any:
        """Update a tag."""
        try:
            return serialize(get_client(api_token).tags.update(tag_id, body))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_tag(api_token: str, tag_id: str) -> str:
        """Delete a tag."""
        try:
            get_client(api_token).tags.delete(tag_id)
            return "Tag deleted successfully."
        except DevhelmError as e:
            return format_error(e)
