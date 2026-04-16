#!/usr/bin/env python3
"""Thin test harness invoked by monorepo pytest surface tests.

Usage: python tests/run_mcp.py <tool_name> [--arg=value ...] --token=<t> --api-url=<u>

Calls the MCP tool function directly and prints JSON to stdout on success,
exits non-zero with error JSON on stderr.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any


def extract_flag(args: list[str], name: str) -> str | None:
    prefix = f"--{name}="
    for i, arg in enumerate(args):
        if arg.startswith(prefix):
            val = arg[len(prefix) :]
            args.pop(i)
            return val
    return None


def extract_kwargs(args: list[str]) -> dict[str, Any]:
    """Extract --key=value pairs into a dict, JSON-parsing values when possible."""
    kwargs: dict[str, Any] = {}
    remaining: list[str] = []
    for arg in args:
        if arg.startswith("--") and "=" in arg:
            key, val = arg[2:].split("=", 1)
            key = key.replace("-", "_")
            try:
                kwargs[key] = json.loads(val)
            except json.JSONDecodeError:
                kwargs[key] = val
        else:
            remaining.append(arg)
    args.clear()
    args.extend(remaining)
    return kwargs


def main() -> None:
    args = sys.argv[1:]

    token = extract_flag(args, "token") or os.environ.get(
        "DEVHELM_API_TOKEN", "devhelm-dev-token"
    )
    api_url = extract_flag(args, "api-url") or os.environ.get(
        "TEST_API_URL", "http://localhost:8081"
    )
    org_id = extract_flag(args, "org-id") or os.environ.get("DEVHELM_ORG_ID", "1")
    workspace_id = extract_flag(args, "workspace-id") or os.environ.get(
        "DEVHELM_WORKSPACE_ID", "1"
    )

    os.environ["DEVHELM_API_URL"] = api_url
    os.environ["DEVHELM_ORG_ID"] = org_id
    os.environ["DEVHELM_WORKSPACE_ID"] = workspace_id

    if not args:
        err = {"error": "Usage: run_mcp.py <tool_name> [--arg=value ...]"}
        sys.stderr.write(json.dumps(err))
        sys.exit(2)

    tool_name = args.pop(0)
    kwargs = extract_kwargs(args)
    kwargs["api_token"] = token

    import asyncio

    from devhelm_mcp.server import mcp  # noqa: E402

    async def call_tool() -> Any:
        tools = await mcp.list_tools()
        tool_map = {t.name: t for t in tools}
        if tool_name not in tool_map:
            return {"error": f"Unknown tool: {tool_name}"}
        result = await mcp.call_tool(tool_name, kwargs)
        if not result.content:
            return []
        content = result.content[0]
        if hasattr(content, "text"):
            try:
                return json.loads(content.text)
            except (json.JSONDecodeError, TypeError):
                return content.text
        return str(content)

    try:
        result = asyncio.run(call_tool())
        if isinstance(result, str) and result.startswith("Error ("):
            err_payload = {"error": result, "code": "SDK_ERROR", "status": 0}
            sys.stderr.write(json.dumps(err_payload))
            sys.exit(1)
        if isinstance(result, dict) and "error" in result and len(result) <= 3:
            sys.stderr.write(json.dumps(result))
            sys.exit(1)
        if result is not None:
            out = json.dumps(result) if not isinstance(result, str) else result
            sys.stdout.write(out)
    except Exception as err:
        err_payload = {"error": str(err), "code": "UNKNOWN", "status": 0}
        sys.stderr.write(json.dumps(err_payload))
        sys.exit(1)


if __name__ == "__main__":
    main()
