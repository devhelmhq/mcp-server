"""Environment tools — prod, staging, and custom environment grouping."""

from __future__ import annotations

from devhelm import DevhelmError
from devhelm.types import CreateEnvironmentRequest, UpdateEnvironmentRequest
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
    def list_environments(api_token: str) -> ToolResult:
        """List all environments in the workspace."""
        try:
            return serialize(get_client(api_token).environments.list())
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_environment(api_token: str, slug: str) -> ToolResult:
        """Get an environment by slug (e.g. 'production', 'staging')."""
        try:
            return serialize(get_client(api_token).environments.get(slug))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_environment(
        api_token: str, body: CreateEnvironmentRequest
    ) -> ToolResult:
        """Create an environment.

        Required fields: name, slug, color.
        """
        try:
            return serialize(
                get_client(api_token).environments.create(as_payload(body))
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_environment(
        api_token: str, slug: str, body: UpdateEnvironmentRequest
    ) -> ToolResult:
        """Update an environment by slug."""
        try:
            return serialize(
                get_client(api_token).environments.update(slug, as_payload(body))
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_environment(api_token: str, slug: str) -> str:
        """Delete an environment by slug."""
        try:
            get_client(api_token).environments.delete(slug)
            return "Environment deleted successfully."
        except DevhelmError as e:
            return format_error(e)
