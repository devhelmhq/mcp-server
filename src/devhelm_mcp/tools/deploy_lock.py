"""Deploy lock tools — coordinate safe deployments."""

from __future__ import annotations

from typing import Any

from devhelm import DevhelmError
from fastmcp import FastMCP

from devhelm_mcp.client import format_error, get_client, serialize


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def acquire_deploy_lock(api_token: str, body: dict[str, Any]) -> Any:
        """Acquire a deploy lock to prevent concurrent deployments.

        Required fields: reason. Optional: ttlSeconds.
        """
        try:
            return serialize(get_client(api_token).deploy_lock.acquire(body))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_current_deploy_lock(api_token: str) -> Any:
        """Get the currently active deploy lock, or null if unlocked."""
        try:
            result = get_client(api_token).deploy_lock.current()
            return serialize(result) if result else None
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def release_deploy_lock(api_token: str, lock_id: str) -> str:
        """Release a deploy lock by ID."""
        try:
            get_client(api_token).deploy_lock.release(lock_id)
            return "Deploy lock released."
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def force_release_deploy_lock(api_token: str) -> str:
        """Force-release any active deploy lock (admin action)."""
        try:
            get_client(api_token).deploy_lock.force_release()
            return "Deploy lock force-released."
        except DevhelmError as e:
            return format_error(e)
