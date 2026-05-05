"""Tag tools — organize monitors with tags."""

from __future__ import annotations

from devhelm import DevhelmError
from devhelm.types import CreateTagRequest, UpdateTagRequest
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
    def list_tags(api_token: str | None = None) -> ToolResult:
        """List all tags in the workspace."""
        try:
            return serialize(get_client(api_token).tags.list())
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def get_tag(tag_id: str, api_token: str | None = None) -> ToolResult:
        """Get a tag by ID."""
        try:
            return serialize(get_client(api_token).tags.get(tag_id))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def create_tag(body: CreateTagRequest, api_token: str | None = None) -> ToolResult:
        """Create a tag.

        Required fields: name. Optional: color.
        """
        try:
            return serialize(get_client(api_token).tags.create(as_payload(body)))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def update_tag(
        tag_id: str, body: UpdateTagRequest, api_token: str | None = None
    ) -> ToolResult:
        """Update a tag."""
        try:
            return serialize(
                get_client(api_token).tags.update(tag_id, as_payload(body))
            )
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool()
    def delete_tag(tag_id: str, api_token: str | None = None) -> str:
        """Delete a tag."""
        try:
            get_client(api_token).tags.delete(tag_id)
            return "Tag deleted successfully."
        except DevhelmError as e:
            raise_tool_error(e)
