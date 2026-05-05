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
    forensics,
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
    forensics,
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


def _get_app() -> Starlette:
    """Build the ASGI app with path-based auth routing."""
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    from starlette.routing import Mount, Route

    # ``mcp.http_app(path="/")`` mounts the JSON-RPC handler at the root of
    # the inner ASGI app. We then ``Mount`` that app at ``/mcp`` of the parent
    # so the customer-facing URL is ``https://mcp.devhelm.io/mcp``.
    #
    # Earlier this code passed ``path="/mcp"`` *and* mounted at ``/mcp``,
    # which produced the live URL ``/mcp/mcp/`` — every documented client
    # config (``mcp.devhelm.io/mcp``) 307-redirected to ``/mcp/`` and then
    # 404'd. END-1186.
    mcp_app = mcp.http_app(path="/")

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
    # ``lifespan=mcp_app.lifespan`` is required by FastMCP's
    # ``StreamableHTTPSessionManager`` — without it the inner app raises
    # "task group was not initialized" on the first POST. See
    # https://gofastmcp.com/deployment/asgi.
    #
    # Trailing-slash semantics: Starlette's ``Mount("/mcp", inner_app)``
    # only forwards paths under ``/mcp/`` to the inner app — the bare
    # ``/mcp`` URL gets a 307 redirect to ``/mcp/``. With
    # ``proxy_headers=True`` on Uvicorn (set in ``main()``), the redirect's
    # ``Location`` honors ``X-Forwarded-Proto: https`` from the upstream
    # proxy (Cloudflare → Traefik → here), so clients still end up on
    # ``https://mcp.devhelm.io/mcp/`` instead of being downgraded to HTTP.
    # See END-1186 for why this matters.
    app = Starlette(
        routes=[
            Route("/health", health_handler, methods=["GET"]),
            Mount("/mcp", app=mcp_app),
            Mount("/{api_key}/mcp", app=mcp_app),
        ],
        middleware=middleware,
        lifespan=mcp_app.lifespan,
    )
    return app


app = _get_app()


def main() -> None:
    """Entry point for the ``devhelm-mcp-server`` console script.

    Defaults to **stdio** — the transport that local MCP clients (Cursor,
    Claude Desktop, Windsurf) speak when they spawn the server as a
    subprocess. Set ``DEVHELM_MCP_TRANSPORT=http`` to start the ASGI app
    under Uvicorn instead, which is what the hosted ``mcp.devhelm.io``
    deployment uses (and what the Dockerfile sets via env).

    Why stdio is the default: the published binary is overwhelmingly
    invoked from MCP client configs that look like::

        "mcpServers": {
          "devhelm": {
            "command": "uvx",
            "args": ["devhelm-mcp-server"]
          }
        }

    If the binary booted an HTTP server in that context, every documented
    Cursor / Claude Desktop config would silently fail. The HTTP path is
    a deliberate opt-in for the hosted-server deployment.
    """
    transport = os.getenv("DEVHELM_MCP_TRANSPORT", "stdio").lower()
    if transport == "stdio":
        mcp.run()
        return
    if transport != "http":
        raise SystemExit(
            f"Unknown DEVHELM_MCP_TRANSPORT={transport!r}; expected 'stdio' or 'http'."
        )

    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    # ``proxy_headers=True`` + ``forwarded_allow_ips="*"`` make Uvicorn honor
    # ``X-Forwarded-Proto`` (and ``X-Forwarded-For``) from the reverse proxy
    # in front of the deployment (Cloudflare → Traefik → here). Without this,
    # any redirect Starlette emits — for example the implicit
    # ``/mcp`` → ``/mcp/`` trailing-slash redirect — uses the *internal*
    # request scheme (``http://``) for the ``Location`` header, which downgrades
    # the client off TLS and then 404s on the bare HTTP host. Production
    # discovered this by seeing every MCP client (Cursor, Claude Desktop,
    # raw curl) bounce through ``Location: http://mcp.devhelm.io/mcp/`` and
    # never reach the JSON-RPC handler. END-1186.
    uvicorn.run(
        "devhelm_mcp.server:app",
        host=host,
        port=port,
        log_level="info",
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
