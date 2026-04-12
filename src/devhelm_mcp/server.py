"""DevHelm MCP Server.

Supports two connection modes:
  1. Bearer auth at /mcp  — standard MCP client with Authorization header
  2. API key in path at /{api_key}/mcp — for clients that only accept a URL

Both resolve the token to a Devhelm SDK client per-request.
"""

from __future__ import annotations

import os
from typing import Any

from devhelm import Devhelm, DevhelmError
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

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
    tags,
    webhooks,
)

API_BASE_URL = os.getenv("DEVHELM_API_URL", "https://api.devhelm.io")

mcp = FastMCP(
    "DevHelm",
    instructions=(
        "DevHelm MCP server for monitoring infrastructure. "
        "Use these tools to manage uptime monitors, incidents, alert channels, "
        "notification policies, environments, secrets, tags, resource groups, "
        "webhooks, API keys, service dependencies, deploy locks, and view "
        "dashboard status. All operations require a valid DevHelm API token."
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
]

for mod in ALL_TOOL_MODULES:
    mod.register(mcp)


def _get_client(token: str) -> Devhelm:
    return Devhelm(token=token, base_url=API_BASE_URL)


def _error_response(err: DevhelmError) -> dict[str, Any]:
    return {"error": err.code, "message": err.message, "status": err.status}


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "healthy", "service": "devhelm-mcp-server"})


def _get_app():
    """Build the ASGI app with path-based auth routing."""
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    from starlette.routing import Mount, Route

    mcp_app = mcp.http_app(path="/mcp")

    async def health_handler(request: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy", "service": "devhelm-mcp-server"})

    async def path_auth_handler(request: Request) -> JSONResponse:
        """Handle /{api_key}/mcp/* — extract token from path, proxy to MCP app."""
        api_key = request.path_params["api_key"]
        scope = dict(request.scope)
        original_path: str = scope.get("path", "")
        prefix = f"/{api_key}"
        if original_path.startswith(prefix):
            scope["path"] = original_path[len(prefix) :]
        scope["headers"] = [
            *[(k, v) for k, v in scope.get("headers", []) if k != b"authorization"],
            (b"authorization", f"Bearer {api_key}".encode()),
        ]
        from starlette.requests import Request as StarletteRequest

        inner_request = StarletteRequest(scope, request.receive)
        response = await mcp_app(inner_request.scope, inner_request.receive, None)  # type: ignore[arg-type]
        return response  # type: ignore[return-value]

    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        ),
    ]

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
