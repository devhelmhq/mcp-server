"""Runtime catalog and plan facts (read-only)."""

from __future__ import annotations

from devhelm import EntitlementResponse, RuntimeProfileDto, SyntheticsUsagePeriodDto
from fastmcp import FastMCP

from devhelm_mcp._tooling import READ, tool
from devhelm_mcp.client import get_client


def register(mcp: FastMCP) -> None:
    @tool(mcp, READ)
    def list_runtimes(api_token: str | None = None) -> list[RuntimeProfileDto]:
        """Runtime profiles (Node, Playwright, packages). Pin one with
        config.runtimeId."""
        return get_client(api_token).runtimes.list()

    @tool(mcp, READ)
    def get_runtime(runtime_id: str, api_token: str | None = None) -> RuntimeProfileDto:
        """One runtime profile, e.g. 2026.11, with its package catalog."""
        return get_client(api_token).runtimes.get(runtime_id)

    @tool(mcp, READ)
    def get_account_usage(api_token: str | None = None) -> SyntheticsUsagePeriodDto:
        """Synthetics runs used this period, per meter and per monitor."""
        return get_client(api_token).account.usage()

    @tool(mcp, READ)
    def get_account_entitlements(
        api_token: str | None = None,
    ) -> EntitlementResponse:
        """The plan tier, its limits and current usage. Read plan facts here;
        never assume them."""
        return get_client(api_token).account.entitlements()
