"""Environment tools — prod, staging, and custom environment grouping."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from devhelm import DevhelmError
from devhelm.types import CreateEnvironmentRequest, UpdateEnvironmentRequest
from fastmcp import FastMCP

from devhelm_mcp.client import (
    format_error,
    format_validation_error,
    get_client,
    serialize,
    validate_body,
)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_environments(api_token: str) -> Any:
        """List all environments in the workspace."""
        try:
            return serialize(get_client(api_token).environments.list())
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_environment(api_token: str, slug: str) -> Any:
        """Get an environment by slug (e.g. 'production', 'staging')."""
        try:
            return serialize(get_client(api_token).environments.get(slug))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_environment(api_token: str, body: dict[str, Any]) -> Any:
        """Create an environment.

        Required fields: name, slug, color.
        """
        try:
            validate_body(body, CreateEnvironmentRequest)
            return serialize(get_client(api_token).environments.create(body))
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_environment(api_token: str, slug: str, body: dict[str, Any]) -> Any:
        """Update an environment by slug."""
        try:
            validate_body(body, UpdateEnvironmentRequest)
            return serialize(get_client(api_token).environments.update(slug, body))
        except ValidationError as e:
            return format_validation_error(e)
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
