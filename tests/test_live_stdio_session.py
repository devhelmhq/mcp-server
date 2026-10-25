"""A real MCP client session over stdio against the mono test stack (doc 42
§5.5.3, §10 "Tests").

Runs only with ``DEVHELM_MCP_LIVE=1`` and the test API on
``DEVHELM_API_URL`` (default http://localhost:8081). For BROWSER and
MULTI_STEP_API it walks: test inline (no monitor) → create → test → draft →
test revision → publish (confirmation token) → trigger → revisions list /
get / files / diff → rollback (confirmation token) → delete (confirmation
token) → restore → delete. The stack has no execution fleet, so runs are
asserted on the contract (run envelope shape, phase, startDeadlineAt), not
on ``passed``.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent
from pydantic import JsonValue

pytestmark = pytest.mark.skipif(
    os.getenv("DEVHELM_MCP_LIVE") != "1", reason="set DEVHELM_MCP_LIVE=1"
)

API_URL = os.getenv("DEVHELM_API_URL", "http://localhost:8081")

SPECS = {
    "BROWSER": (
        "checks/home.spec.ts",
        "import { test, expect } from '@playwright/test';\n"
        "import { HOME } from './urls';\n"
        "test('home', async ({ page }) => {\n"
        "  await page.goto(HOME);\n"
        "  await expect(page).toHaveTitle(/Example/);\n"
        "});\n",
    ),
    "MULTI_STEP_API": (
        "checks/api.spec.ts",
        "import { test, expect } from '@playwright/test';\n"
        "import { HOME } from './urls';\n"
        "test('api', async ({ request }) => {\n"
        "  const res = await request.get(HOME);\n"
        "  expect(res.ok()).toBeTruthy();\n"
        "});\n",
    ),
}
URLS = "export const HOME = 'https://example.com';\n"


def _code(kind: str, marker: str) -> dict[str, JsonValue]:
    entry, text = SPECS[kind]
    return {
        "entrypoint": entry,
        "files": {entry: text + f"// {marker}\n", "checks/urls.ts": URLS},
    }


@asynccontextmanager
async def _session() -> AsyncIterator[ClientSession]:
    env = {
        **os.environ,
        "DEVHELM_API_URL": API_URL,
        "DEVHELM_API_TOKEN": os.getenv("DEVHELM_API_TOKEN", "devhelm-dev-token"),
        "DEVHELM_ORG_ID": os.getenv("DEVHELM_ORG_ID", "2"),
        "DEVHELM_WORKSPACE_ID": os.getenv("DEVHELM_WORKSPACE_ID", "2"),
    }
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "devhelm_mcp.server"], env=env
    )
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        yield session


def _structured(res: CallToolResult) -> dict[str, JsonValue]:
    text = res.content[0].text if isinstance(res.content[0], TextContent) else ""
    assert not res.isError, text
    data = res.structuredContent
    assert isinstance(data, dict), text
    inner = data.get("result", data) if len(data) == 1 else data
    assert isinstance(inner, dict)
    return inner


async def _call(
    s: ClientSession, name: str, args: Mapping[str, JsonValue]
) -> dict[str, JsonValue]:
    return _structured(await s.call_tool(name, dict(args)))


async def _run(
    s: ClientSession, name: str, args: Mapping[str, JsonValue]
) -> dict[str, JsonValue] | None:
    """A run tool's envelope, or ``None`` when the stack holds admissions.

    A stack without #1435's admissions opener answers 503
    RUNTIME_UNAVAILABLE; the tool must surface it as a structured isError.
    """
    res = await s.call_tool(name, dict(args))
    if res.isError:
        text = res.content[0].text if isinstance(res.content[0], TextContent) else ""
        fields = json.loads(text.splitlines()[-1])["error"]
        assert fields["code"] == "RUNTIME_UNAVAILABLE", text
        assert fields["category"] == "platform"
        UNAVAILABLE.append(name)
        return None
    env = _structured(res)
    _assert_run(env)
    return env


UNAVAILABLE: list[str] = []


def _assert_run(env: Mapping[str, JsonValue]) -> None:
    assert {"runId", "phase", "nextAction", "steps", "artifacts"} <= set(env)
    assert env["phase"] in {"created", "queued", "running", "finished"}
    if env["phase"] != "finished":
        assert "get_run" in str(env["nextAction"])


async def _confirmed(
    s: ClientSession, name: str, args: dict[str, JsonValue]
) -> dict[str, JsonValue]:
    first = await _call(s, name, args)
    assert first["status"] == "confirmation_required", first
    assert first["changes"]
    token = first["confirmationToken"]
    # A token for other arguments is refused.
    bad = await s.call_tool(
        name, {**args, "monitor_id": str(uuid.uuid4()), "confirmation_token": token}
    )
    assert bad.isError
    return await _call(s, name, {**args, "confirmation_token": token})


async def _journey(s: ClientSession, kind: str, env_slug: str, env_id: str) -> None:
    name = f"mcp-e2e-{kind.lower()}-{uuid.uuid4().hex[:8]}"

    await _run(
        s,
        "test_monitor_adhoc",
        {
            "body": {"type": kind, "environmentId": env_id},
            "code": _code(kind, "adhoc"),
            "wait_s": 2,
        },
    )

    monitor = await _call(
        s,
        "create_monitor",
        {
            "body": {
                "name": name,
                "type": kind,
                "frequencySeconds": 3600,
                "regions": ["us-east"],
            },
            "code": _code(kind, "v1"),
            "environment": env_slug,
        },
    )
    mid = str(monitor["id"])
    assert monitor["managedBy"] == "MCP"
    try:
        await _run(s, "test_monitor", {"monitor_id": mid, "wait_s": 1})

        draft = await _call(
            s, "create_monitor_revision", {"monitor_id": mid, "code": _code(kind, "v2")}
        )
        revision = draft["revision"]
        assert isinstance(revision, dict)
        rid = str(revision["id"])
        await _run(s, "test_monitor_revision", {"monitor_id": mid, "revision_id": rid})

        published = await _confirmed(
            s, "publish_monitor", {"monitor_id": mid, "revision_id": rid}
        )
        assert published["status"] == "published"

        res = await s.call_tool("trigger_monitor", {"monitor_id": mid})
        if not res.isError:
            runs = _structured(res)["runs"]
            assert isinstance(runs, list) and runs
            for run in runs:
                assert isinstance(run, dict)
                _assert_run(run)
                await _run(s, "get_run", {"run_id": str(run["runId"])})
        else:
            UNAVAILABLE.append("trigger_monitor")

        revs = await _call(
            s, "list_monitor_revisions", {"monitor_id": mid, "state": "all"}
        )
        assert isinstance(revs["data"], list) and len(revs["data"]) >= 2
        assert (
            await _call(
                s, "get_monitor_revision", {"monitor_id": mid, "revision_id": rid}
            )
        )["id"] == rid
        files = await _call(
            s, "get_monitor_revision_files", {"monitor_id": mid, "revision_id": rid}
        )
        assert isinstance(files["files"], dict) and SPECS[kind][0] in files["files"]
        await _call(
            s, "diff_monitor_revisions", {"monitor_id": mid, "revision_id": rid}
        )

        rolled = await _confirmed(
            s, "rollback_monitor", {"monitor_id": mid, "reason": "mcp e2e"}
        )
        assert rolled["status"] == "rolled_back"

        await _call(s, "list_monitor_history", {"monitor_id": mid, "limit": 5})
    finally:
        deleted = await _confirmed(s, "delete_monitor", {"monitor_id": mid})
        assert deleted["status"] == "deleted"
    restored = await _call(s, "restore_monitor", {"monitor_id": mid})
    assert restored["id"] == mid
    await _confirmed(s, "delete_monitor", {"monitor_id": mid})


def test_both_code_types_over_stdio() -> None:
    async def main() -> None:
        async with _session() as s:
            tools = {t.name: t for t in (await s.list_tools()).tools}
            assert all(t.annotations is not None for t in tools.values())
            slug = f"mcp-e2e-{uuid.uuid4().hex[:8]}"
            env = await _call(
                s, "create_environment", {"body": {"name": slug, "slug": slug}}
            )
            try:
                for kind in ("BROWSER", "MULTI_STEP_API"):
                    await _journey(s, kind, slug, str(env["id"]))
                    print(json.dumps({"kind": kind, "ok": True, "held": UNAVAILABLE}))
            finally:
                await s.call_tool("delete_environment", {"slug": slug})

    anyio.run(main)
