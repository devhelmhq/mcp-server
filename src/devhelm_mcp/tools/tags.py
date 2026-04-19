"""Tag tools — organize monitors with tags."""

from __future__ import annotations

from typing import Any

from devhelm import DevhelmError
from devhelm.types import CreateTagRequest, UpdateTagRequest
from fastmcp import FastMCP
from pydantic import ValidationError

from devhelm_mcp.client import (
    ToolResult,
    format_error,
    format_validation_error,
    get_client,
    serialize,
    validate_body,
)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_tags(api_token: str) -> ToolResult:
        """List all tags in the workspace."""
        try:
            return serialize(get_client(api_token).tags.list())
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_tag(api_token: str, tag_id: str) -> ToolResult:
        """Get a tag by ID."""
        try:
            return serialize(get_client(api_token).tags.get(tag_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_tag(api_token: str, body: dict[str, Any]) -> ToolResult:
        """Create a tag.

        Required fields: name. Optional: color.
        """
        try:
            validate_body(body, CreateTagRequest)
            return serialize(get_client(api_token).tags.create(body))
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_tag(api_token: str, tag_id: str, body: dict[str, Any]) -> ToolResult:
        """Update a tag."""
        try:
            validate_body(body, UpdateTagRequest)
            return serialize(get_client(api_token).tags.update(tag_id, body))
        except ValidationError as e:
            return format_validation_error(e)
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
