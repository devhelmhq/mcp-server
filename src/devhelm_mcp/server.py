"""DevHelm MCP Server.

Supports two connection modes:
  1. Bearer auth at /mcp  — standard MCP client with Authorization header
  2. API key in path at /{api_key}/mcp — for clients that only accept a URL

Both resolve the token to a Devhelm SDK client per-request.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import TYPE_CHECKING, Any

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


def _strip_internal_schema_fields() -> None:
    """Hide server-controlled / sensitive fields from the LLM-facing schema.

    Two targets:

    1. ``api_token`` — every tool accepts it as a kwarg for back-compat with
       path-style ``/{api_key}/mcp`` clients, but after the 0.7.0 Bearer /
       env-var fix the LLM should never need to set it. Surfacing it in
       ``inputSchema.properties`` invites the model to populate the field
       from chat context, which leaks the user's API token into telemetry
       and tool-call traces. Removing the property entirely keeps the
       Python signature wired (so direct callers / tests still work) while
       preventing the LLM from seeing it. DevEx P2.Bug7.

    2. ``managedBy`` on ``create_monitor`` — the MCP server forces this to
       ``"MCP"`` server-side (see ``tools/monitors.py``). Hiding the field
       from the schema stops the LLM from trying to set it (which would
       either be ignored or, worse, fail validation on a stale SDK enum).
       The Pydantic model for the body still excludes the field from
       serialization, so this strip is purely about LLM ergonomics.
       DevEx P0.Bug5 + P1.Bug4 + P1.Bug5.

    ``run_middleware=False`` returns the source-of-truth ``Tool`` objects
    from the providers; the dereference middleware copies them on every
    ``tools/list`` and would lose any edits we made to the copies.
    """
    tools = asyncio.run(mcp.list_tools(run_middleware=False))
    for tool in tools:
        params = tool.parameters
        if not isinstance(params, dict):
            continue
        properties = params.get("properties")
        if isinstance(properties, dict):
            properties.pop("api_token", None)
        required = params.get("required")
        if isinstance(required, list) and "api_token" in required:
            required.remove("api_token")

        if tool.name == "create_monitor":
            _strip_managed_by_from_create_monitor(params)


def _strip_managed_by_from_create_monitor(params: dict[str, Any]) -> None:
    """Remove ``managedBy`` from the ``create_monitor`` body schema.

    FastMCP emits the body either inline (``properties.body.properties``) or
    behind a ``$ref`` into ``$defs`` — depends on whether the Pydantic model
    has nested ``$ref``-able children. For ``CreateMonitorRequest`` it's the
    second shape because of the discriminated ``config`` union, so the fix
    has to drop ``managedBy`` from the def *before* the dereference
    middleware inlines it for the wire response.
    """
    properties = params.get("properties")
    if isinstance(properties, dict):
        body = properties.get("body")
        if isinstance(body, dict):
            _strip_field_from_object_schema(body, "managedBy")
            ref = body.get("$ref")
            if isinstance(ref, str):
                defs = params.get("$defs")
                if isinstance(defs, dict):
                    def_name = ref.rsplit("/", 1)[-1]
                    target = defs.get(def_name)
                    if isinstance(target, dict):
                        _strip_field_from_object_schema(target, "managedBy")


def _strip_field_from_object_schema(schema: dict[str, Any], field: str) -> None:
    """Remove ``field`` from a JSON Schema object's ``properties`` and ``required``."""
    schema_props = schema.get("properties")
    if isinstance(schema_props, dict):
        schema_props.pop(field, None)
    schema_required = schema.get("required")
    if isinstance(schema_required, list) and field in schema_required:
        schema_required.remove(field)


_strip_internal_schema_fields()


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


def _package_version() -> str:
    """Best-effort lookup of the installed package version for ``--version``."""
    try:
        return _pkg_version("devhelm-mcp-server")
    except PackageNotFoundError:
        return "unknown"


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for ``devhelm-mcp-server``.

    Defined as a separate function so the wheel's entry point and tests
    can both render the same ``--help`` output without booting the
    server. Every flag has an env-var equivalent and the env var wins
    only when the flag is *not* passed on the command line — that's the
    contract every existing deployment relies on (Dockerfile sets
    ``DEVHELM_MCP_TRANSPORT=http``; ``uvx devhelm-mcp-server`` reads
    nothing and gets stdio).
    """
    parser = argparse.ArgumentParser(
        prog="devhelm-mcp-server",
        description=(
            "DevHelm MCP server — exposes monitors, incidents, alerting, "
            "and more to AI agents over the Model Context Protocol."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Local stdio (Cursor / Claude Desktop / Windsurf):\n"
            "  DEVHELM_API_TOKEN=dh_live_xxx devhelm-mcp-server\n"
            "\n"
            "  # Self-hosted HTTP listener:\n"
            "  devhelm-mcp-server --transport http --host 0.0.0.0 --port 8080\n"
            "\n"
            "Environment variables (overridden by the matching flag):\n"
            "  DEVHELM_MCP_TRANSPORT  stdio | http (default: stdio)\n"
            "  DEVHELM_MCP_HOST       HTTP bind host (default: 0.0.0.0)\n"
            "  DEVHELM_MCP_PORT       HTTP bind port (default: 8000)\n"
            "  DEVHELM_API_TOKEN      Bearer token used when none is provided\n"
            "                         in tool args or Authorization header\n"
            "  DEVHELM_API_URL        Override the upstream DevHelm API URL"
        ),
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "http"),
        default=None,
        help=(
            "transport to serve (default: stdio, or DEVHELM_MCP_TRANSPORT). "
            "stdio is what local MCP clients (Cursor, Claude Desktop, "
            "Windsurf, uvx) spawn as a subprocess; http is the hosted / "
            "self-hosted ASGI listener under Uvicorn."
        ),
    )
    parser.add_argument(
        "--host",
        default=None,
        help=(
            "HTTP bind host (default: 0.0.0.0, or DEVHELM_MCP_HOST). "
            "Ignored when --transport stdio."
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=(
            "HTTP bind port (default: 8000, or DEVHELM_MCP_PORT). "
            "Ignored when --transport stdio."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"devhelm-mcp-server {_package_version()}",
    )
    return parser


def _resolve_transport(arg: str | None) -> str:
    transport = (arg or os.getenv("DEVHELM_MCP_TRANSPORT") or "stdio").lower()
    if transport not in ("stdio", "http"):
        raise SystemExit(
            f"Unknown transport {transport!r}; expected 'stdio' or 'http'."
        )
    return transport


def _resolve_host(arg: str | None) -> str:
    # ``DEVHELM_MCP_HOST`` is the documented env var; ``HOST`` is the
    # legacy name still set by some Dockerfile setups, kept as a
    # back-compat fallback so we don't silently regress on the existing
    # production deploy.
    return arg or os.getenv("DEVHELM_MCP_HOST") or os.getenv("HOST") or "0.0.0.0"


def _resolve_port(arg: int | None) -> int:
    if arg is not None:
        return arg
    raw = os.getenv("DEVHELM_MCP_PORT") or os.getenv("PORT") or "8000"
    try:
        return int(raw)
    except ValueError as exc:
        raise SystemExit(f"Invalid port {raw!r}: {exc}") from exc


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``devhelm-mcp-server`` console script.

    Defaults to **stdio** — the transport that local MCP clients (Cursor,
    Claude Desktop, Windsurf) speak when they spawn the server as a
    subprocess. Set ``DEVHELM_MCP_TRANSPORT=http`` (or pass
    ``--transport http``) to start the ASGI app under Uvicorn instead,
    which is what the hosted ``mcp.devhelm.io`` deployment uses (and
    what the Dockerfile sets via env).

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

    The ``--help`` / ``--version`` flags exit immediately without booting
    a transport — before this CLI parser was added, ``--help`` was
    silently consumed and the server started in stdio mode, leaving
    users unable to discover any of the flags or env vars.
    """
    args = _build_arg_parser().parse_args(argv if argv is not None else sys.argv[1:])

    transport = _resolve_transport(args.transport)
    if transport == "stdio":
        mcp.run()
        return

    import uvicorn

    host = _resolve_host(args.host)
    port = _resolve_port(args.port)
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
