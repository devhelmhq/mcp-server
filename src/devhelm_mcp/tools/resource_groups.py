"""Resource group tools — logical grouping of monitors."""

from __future__ import annotations

from typing import Any

from devhelm import DevhelmError
from devhelm._generated import AddResourceGroupMemberRequest
from devhelm.types import (
    CreateResourceGroupRequest,
    UpdateResourceGroupRequest,
)
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
    def list_resource_groups(api_token: str) -> ToolResult:
        """List all resource groups in the workspace."""
        try:
            return serialize(get_client(api_token).resource_groups.list())
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_resource_group(api_token: str, group_id: str) -> ToolResult:
        """Get a resource group by ID."""
        try:
            return serialize(get_client(api_token).resource_groups.get(group_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_resource_group(api_token: str, body: dict[str, Any]) -> ToolResult:
        """Create a resource group.

        Required fields: name. Optional: description.
        """
        try:
            validate_body(body, CreateResourceGroupRequest)
            return serialize(get_client(api_token).resource_groups.create(body))
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_resource_group(
        api_token: str, group_id: str, body: dict[str, Any]
    ) -> ToolResult:
        """Update a resource group."""
        try:
            validate_body(body, UpdateResourceGroupRequest)
            return serialize(
                get_client(api_token).resource_groups.update(group_id, body)
            )
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_resource_group(api_token: str, group_id: str) -> str:
        """Delete a resource group."""
        try:
            get_client(api_token).resource_groups.delete(group_id)
            return "Resource group deleted successfully."
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def add_resource_group_member(
        api_token: str, group_id: str, body: dict[str, Any]
    ) -> ToolResult:
        """Add a monitor to a resource group.

        Required fields: monitorId.
        """
        try:
            validate_body(body, AddResourceGroupMemberRequest)
            return serialize(
                get_client(api_token).resource_groups.add_member(group_id, body)
            )
        except ValidationError as e:
            return format_validation_error(e)
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def remove_resource_group_member(
        api_token: str, group_id: str, member_id: str
    ) -> str:
        """Remove a monitor from a resource group."""
        try:
            get_client(api_token).resource_groups.remove_member(group_id, member_id)
            return "Member removed from resource group."
        except DevhelmError as e:
            return format_error(e)
