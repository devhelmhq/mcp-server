"""Resource group tools — logical grouping of monitors."""

from __future__ import annotations

from devhelm import DevhelmError
from devhelm.types import (
    AddResourceGroupMemberRequest,
    CreateResourceGroupRequest,
    UpdateResourceGroupRequest,
)
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
    def list_resource_groups(api_token: str | None = None) -> ToolResult:
        """List all resource groups in the workspace."""
        try:
            return serialize(get_client(api_token).resource_groups.list())
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_resource_group(group_id: str, api_token: str | None = None) -> ToolResult:
        """Get a resource group by ID."""
        try:
            return serialize(get_client(api_token).resource_groups.get(group_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def create_resource_group(
        body: CreateResourceGroupRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Create a resource group.

        Required fields: name. Optional: description.
        """
        try:
            return serialize(
                get_client(api_token).resource_groups.create(as_payload(body))
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def update_resource_group(
        group_id: str,
        body: UpdateResourceGroupRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Update a resource group."""
        try:
            return serialize(
                get_client(api_token).resource_groups.update(group_id, as_payload(body))
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def delete_resource_group(group_id: str, api_token: str | None = None) -> str:
        """Delete a resource group."""
        try:
            get_client(api_token).resource_groups.delete(group_id)
            return "Resource group deleted successfully."
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def add_resource_group_member(
        group_id: str,
        body: AddResourceGroupMemberRequest,
        api_token: str | None = None,
    ) -> ToolResult:
        """Add a monitor to a resource group.

        Required fields: monitorId.
        """
        try:
            return serialize(
                get_client(api_token).resource_groups.add_member(
                    group_id, as_payload(body)
                )
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def remove_resource_group_member(
        group_id: str,
        member_id: str,
        api_token: str | None = None,
    ) -> str:
        """Remove a monitor from a resource group."""
        try:
            get_client(api_token).resource_groups.remove_member(group_id, member_id)
            return "Member removed from resource group."
        except DevhelmError as e:
            return format_error(e)
