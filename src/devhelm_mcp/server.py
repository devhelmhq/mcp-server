"""DevHelm MCP Server.

Supports two connection modes:
  1. Bearer auth at /mcp  — standard MCP client with Authorization header
  2. API key in path at /{api_key}/mcp — for clients that only accept a URL

Both resolve the token to a Devhelm SDK client per-request.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from starlette.applications import Starlette

from devhelm_mcp.tools import (
    alert_channels,
    api_keys,
    dependencies,
    deploy_lock,
    environments,
    incidents,
    monitors,
    notification_policies,
    resource_groups,
    secrets,
    status,
    status_pages,
    tags,
    webhooks,
)

mcp = FastMCP(
    "DevHelm",
    instructions=(
        "DevHelm MCP server for monitoring infrastructure. "
        "Use these tools to manage uptime monitors, incidents, alert channels, "
        "notification policies, environments, secrets, tags, resource groups, "
        "webhooks, API keys, service dependencies, deploy locks, status pages, "
        "and view dashboard status. All operations require a valid DevHelm API token."
    ),
)

ALL_TOOL_MODULES = [
    monitors,
    incidents,
    alert_channels,
    notification_policies,
    environments,
    secrets,
    tags,
    resource_groups,
    webhooks,
    api_keys,
    dependencies,
    deploy_lock,
    status,
    status_pages,
]

for mod in ALL_TOOL_MODULES:
    mod.register(mcp)


def _get_app() -> "Starlette":
    """Build the ASGI app with path-based auth routing."""
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    from starlette.routing import Mount, Route

    mcp_app = mcp.http_app(path="/mcp")

    async def health_handler(request: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy", "service": "devhelm-mcp-server"})

    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        ),
    ]

    # Both routes mount the same MCP app:
    #   - ``/mcp``           — clients send the API token in the
    #     ``Authorization: Bearer …`` header (preferred).
    #   - ``/{api_key}/mcp`` — clients that can only configure a URL
    #     embed the token in the path. The bearer-auth shim that used
    #     to translate the path segment into an ``Authorization`` header
    #     was removed (it was unreachable: the ``Mount`` below claims
    #     these requests first), so per-tool token args remain the
    #     authoritative auth path for path-style clients today. See
    #     END-1150.
    app = Starlette(
        routes=[
            Route("/health", health_handler, methods=["GET"]),
            Mount("/mcp", app=mcp_app),
            Mount("/{api_key}/mcp", app=mcp_app),
        ],
        middleware=middleware,
    )
    return app


app = _get_app()


def main() -> None:
    """Entry point for production: uvicorn devhelm_mcp.server:app"""
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "devhelm_mcp.server:app",
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
