"""Unit tests for the synthetics tools (doc 42 §10): one per tool, plus the
run envelope, confirmation tokens, bounded output and secrets rules.

The SDK client is a mock returning real generated models (``_factory``), and
every structured result is validated against the tool's advertised
``outputSchema``.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import jsonschema
import pytest
from devhelm import (
    CreateDraftRevisionResponse,
    DefinitionHeadDto,
    EntitlementResponse,
    IncidentActivityEventDto,
    IncidentDetailDto,
    IncidentTriggerDto,
    MonitorDriftDto,
    MonitorDto,
    MonitorHistoryEntryDto,
    MonitorTestResultDto,
    MonitorVersionDto,
    RelatedIncidentsResponse,
    RevisionDiffDto,
    RevisionDto,
    RevisionFilesDto,
    RollbackPreviewDto,
    RunArtifactDto,
    RunCaseDto,
    RunConsoleDto,
    RunDiffDto,
    RunDto,
    RunNetworkDto,
    RunStepDto,
    RuntimeProfileDto,
    RunTraceSummaryDto,
    SecretDto,
    SyntheticsUsagePeriodDto,
    TriggerRunRef,
    TriggerRunsResponse,
    WaitTimeoutError,
)
from devhelm._pages import CursorPage, Page
from fastmcp.exceptions import ToolError
from fastmcp.tools import ToolResult
from mcp.types import ImageContent
from pydantic import JsonValue
from pydantic import ValidationError as PydanticValidationError

from devhelm_mcp import _confirm
from devhelm_mcp._tooling import TEXT_CAP_BYTES, capped_text
from devhelm_mcp.server import _strip_internal_schema_fields, mcp
from devhelm_mcp.tools.revisions import cap_files
from tests._factory import build

MODULES = ["monitors", "revisions", "runs", "account", "secrets", "incidents"]
MID = str(uuid.uuid4())
RID = str(uuid.uuid4())


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    monkeypatch.setenv("DEVHELM_API_TOKEN", "dh_test")
    mock = MagicMock()
    patches = [
        patch(f"devhelm_mcp.tools.{m}.get_client", return_value=mock) for m in MODULES
    ]
    for p in patches:
        p.start()
    yield mock
    for p in patches:
        p.stop()


def call(name: str, args: Mapping[str, JsonValue]) -> ToolResult:
    result = asyncio.run(mcp.call_tool(name, dict(args)))
    assert isinstance(result, ToolResult)
    tool = asyncio.run(mcp.get_tool(name))
    assert tool is not None
    if tool.output_schema is not None:
        jsonschema.validate(result.structured_content, tool.output_schema)
    return result


def data(result: ToolResult) -> dict[str, JsonValue]:
    sc = result.structured_content
    assert isinstance(sc, dict)
    inner = sc.get("result", sc) if (result.meta or {}).get("fastmcp") else sc
    assert isinstance(inner, dict)
    return inner


def items(result: ToolResult) -> list[JsonValue]:
    sc = result.structured_content
    assert isinstance(sc, dict)
    out = sc["result"]
    assert isinstance(out, list)
    return out


def run(phase: str = "queued", **kw: object) -> RunDto:
    return build(RunDto, phase=phase, **kw)


# -- run envelope -------------------------------------------------------------


def test_run_envelope_queued_points_at_get_run(client: MagicMock) -> None:
    client.runs.get.return_value = run("queued")
    out = data(call("get_run", {"run_id": RID}))
    assert out["phase"] == "queued"
    assert "get_run" in str(out["nextAction"])
    assert set(out) >= {
        "runId",
        "phase",
        "outcome",
        "flaky",
        "headline",
        "failure",
        "steps",
        "artifacts",
        "runUrl",
        "nextAction",
    }


def test_run_envelope_finished_carries_steps_and_artifacts(client: MagicMock) -> None:
    step = build(RunStepDto)
    client.runs.get.return_value = run("queued")
    client.runs.wait.return_value = run("finished", outcome="failed")
    client.runs.steps.return_value = [build(RunCaseDto, steps=[step])]
    client.runs.artifacts.list.return_value = [build(RunArtifactDto)]
    out = data(call("get_run", {"run_id": RID, "wait_s": 25}))
    assert client.runs.wait.call_args.kwargs["timeout_ms"] == 25_000
    assert len(out["steps"]) == 1  # type: ignore[arg-type]
    assert len(out["artifacts"]) == 1  # type: ignore[arg-type]
    assert "get_run_trace_summary" in str(out["nextAction"])


def test_wait_s_is_capped_at_25(client: MagicMock) -> None:
    with pytest.raises(PydanticValidationError, match="less than or equal to 25"):
        asyncio.run(mcp.call_tool("get_run", {"run_id": RID, "wait_s": 26}))


def test_wait_timeout_returns_current_state(client: MagicMock) -> None:
    client.runs.get.return_value = run("running")
    client.runs.wait.side_effect = WaitTimeoutError(RID, "running", timeout_ms=1)
    assert data(call("get_run", {"run_id": RID, "wait_s": 1}))["phase"] == "running"


# -- monitors -------------------------------------------------------------------

CODE = {"entrypoint": "a.spec.ts", "files": {"a.spec.ts": "test()"}}


def test_create_monitor_passes_inline_code_and_forces_mcp(client: MagicMock) -> None:
    client.monitors.create.return_value = build(MonitorDto)
    call(
        "create_monitor",
        {
            "body": {"name": "c", "type": "BROWSER"},
            "code": {**CODE, "include": ["a.spec.ts"]},
            "environment": "production",
        },
    )
    args, kwargs = client.monitors.create.call_args
    assert args[0]["managedBy"] == "MCP"
    assert kwargs["code"]["files"] == CODE["files"]
    assert kwargs["code"]["include"] == ["a.spec.ts"]
    assert kwargs["environment"] == "production"


def test_create_monitor_refuses_over_1mb_inline(client: MagicMock) -> None:
    big = {"entrypoint": "a.ts", "files": {"a.ts": "x" * (1024 * 1024 + 1)}}
    with pytest.raises(ToolError, match="BUNDLE_TOO_LARGE"):
        asyncio.run(
            mcp.call_tool(
                "create_monitor",
                {"body": {"name": "c", "type": "BROWSER"}, "code": big},
            )
        )
    client.monitors.create.assert_not_called()


def test_update_monitor(client: MagicMock) -> None:
    client.monitors.update.return_value = build(MonitorDto)
    call("update_monitor", {"monitor_id": MID, "body": {"name": "n"}, "code": CODE})
    assert client.monitors.update.call_args.kwargs["code"]["entrypoint"] == "a.spec.ts"


@pytest.mark.parametrize(
    ("tool", "method", "extra"),
    [
        ("get_monitor", "get", {}),
        ("resume_monitor", "resume", {}),
        ("unmute_monitor", "unmute", {}),
        ("release_quarantine_monitor", "release_quarantine", {}),
        ("restore_monitor", "restore", {}),
        ("pause_monitor", "pause", {"reason": "deploy"}),
        ("mute_monitor", "mute", {"reason": "noise"}),
        (
            "quarantine_monitor",
            "quarantine",
            {"body": {"reason": "flaky", "expiresAt": "2026-11-01T00:00:00Z"}},
        ),
    ],
)
def test_monitor_dto_tools(
    client: MagicMock, tool: str, method: str, extra: dict[str, JsonValue]
) -> None:
    getattr(client.monitors, method).return_value = build(MonitorDto)
    call(tool, {"monitor_id": MID, **extra})
    assert getattr(client.monitors, method).called


def test_list_monitors(client: MagicMock) -> None:
    client.monitors.list.return_value = [build(MonitorDto)]
    assert len(items(call("list_monitors", {"name": "Checkout"}))) == 1
    assert client.monitors.list.call_args.kwargs["name"] == "Checkout"


def test_get_monitor_drift(client: MagicMock) -> None:
    client.monitors.drift.return_value = build(MonitorDriftDto)
    call("get_monitor_drift", {"monitor_id": MID})


def test_versions(client: MagicMock) -> None:
    client.monitors.versions.list.return_value = Page(data=[build(MonitorVersionDto)])
    client.monitors.versions.get.return_value = build(MonitorVersionDto)
    assert len(data(call("list_monitor_versions", {"monitor_id": MID}))["data"]) == 1  # type: ignore[arg-type]
    call("get_monitor_version", {"monitor_id": MID, "version": 2})


@pytest.mark.parametrize("tool", ["list_monitor_history", "list_monitor_results"])
def test_history_and_deprecated_alias(client: MagicMock, tool: str) -> None:
    client.monitors.history.list.return_value = CursorPage(
        data=[build(MonitorHistoryEntryDto)], next_cursor="c2", has_more=True
    )
    out = data(call(tool, {"monitor_id": MID, "limit": 5}))
    assert out["nextCursor"] == "c2" and out["hasMore"] is True


def test_list_monitor_results_is_marked_deprecated() -> None:
    tool = asyncio.run(mcp.get_tool("list_monitor_results"))
    assert tool is not None and "2027-01-31" in (tool.description or "")


def test_list_monitor_trash(client: MagicMock) -> None:
    client.monitors.trash.list_page.return_value = Page(data=[build(MonitorDto)])
    call("list_monitor_trash", {})


def test_test_monitor_code(client: MagicMock) -> None:
    client.monitors.get.return_value = build(MonitorDto, type="BROWSER")
    client.monitors.test.return_value = run()
    out = data(call("test_monitor", {"monitor_id": MID, "code": CODE}))
    assert out["phase"] == "queued"


def test_test_monitor_uptime_returns_probe_until_cutoff(client: MagicMock) -> None:
    client.monitors.get.return_value = build(MonitorDto, type="HTTP")
    client.monitors.probe.return_value = build(MonitorTestResultDto)
    with pytest.warns(DeprecationWarning):
        out = data(call("test_monitor", {"monitor_id": MID}))
    assert "probe_monitor" in str(out["deprecation"])


def test_test_monitor_uptime_after_cutoff_says_use_probe(client: MagicMock) -> None:
    client.monitors.get.return_value = build(MonitorDto, type="HTTP")
    with (
        patch(
            "devhelm_mcp.tools.monitors.PROBE_ALIAS_UNTIL",
            datetime(2000, 1, 1, tzinfo=UTC),
        ),
        pytest.raises(ToolError, match="probe_monitor"),
    ):
        asyncio.run(mcp.call_tool("test_monitor", {"monitor_id": MID}))


def test_probe_monitor(client: MagicMock) -> None:
    client.monitors.probe.return_value = build(MonitorTestResultDto)
    call("probe_monitor", {"monitor_id": MID})


def test_test_monitor_adhoc_code(client: MagicMock) -> None:
    client.monitors.test_adhoc.return_value = run()
    call(
        "test_monitor_adhoc",
        {"body": {"type": "MULTI_STEP_API"}, "code": CODE, "environment": "prod"},
    )
    kw = client.monitors.test_adhoc.call_args.kwargs
    assert kw["type"] == "MULTI_STEP_API" and kw["environment"] == "prod"


def test_test_monitor_adhoc_code_needs_environment(client: MagicMock) -> None:
    with pytest.raises(ToolError, match="FIELD_REQUIRED"):
        asyncio.run(
            mcp.call_tool(
                "test_monitor_adhoc", {"body": {"type": "BROWSER"}, "code": CODE}
            )
        )


def test_test_monitor_adhoc_uptime(client: MagicMock) -> None:
    client.monitors.test_adhoc.return_value = build(MonitorTestResultDto)
    call(
        "test_monitor_adhoc",
        {
            "body": {
                "type": "HTTP",
                "config": {"url": "https://example.com", "method": "GET"},
            }
        },
    )


def test_run_monitor_now(client: MagicMock) -> None:
    client.monitors.run_now.return_value = run()
    call("run_monitor_now", {"monitor_id": MID})


def test_trigger_monitor(client: MagicMock) -> None:
    ref = build(TriggerRunRef)
    client.monitors.trigger.return_value = build(
        TriggerRunsResponse, runs=[ref, ref], billed_runs=2
    )
    client.runs.get.return_value = run()
    out = data(call("trigger_monitor", {"monitor_id": MID, "regions": ["us-east"]}))
    assert out["billedRuns"] == 2 and len(out["runs"]) == 2  # type: ignore[arg-type]
    assert client.monitors.trigger.call_args.kwargs["regions"] == ["us-east"]


# -- confirmation tokens ----------------------------------------------------------


def _confirm_flow(
    client: MagicMock, tool: str, args: dict[str, JsonValue]
) -> dict[str, JsonValue]:
    first = data(call(tool, args))
    assert first["status"] == "confirmation_required"
    assert first["changes"]
    token = first["confirmationToken"]
    with pytest.raises(ToolError, match="CONFIRMATION_TOKEN_INVALID"):
        asyncio.run(
            mcp.call_tool(
                tool,
                {**args, "monitor_id": str(uuid.uuid4()), "confirmation_token": token},
            )
        )
    return data(call(tool, {**args, "confirmation_token": token}))


def test_delete_monitor_needs_confirmation(client: MagicMock) -> None:
    client.monitors.get.return_value = build(MonitorDto)
    out = _confirm_flow(client, "delete_monitor", {"monitor_id": MID})
    assert out["status"] == "deleted"
    client.monitors.delete.assert_called_once_with(MID)


def test_publish_monitor_needs_confirmation(client: MagicMock) -> None:
    client.monitors.get.return_value = build(MonitorDto)
    client.monitors.revisions.get.return_value = build(RevisionDto)
    client.monitors.publish.return_value = build(DefinitionHeadDto)
    out = _confirm_flow(
        client, "publish_monitor", {"monitor_id": MID, "revision_id": RID}
    )
    assert out["status"] == "published"
    assert str(client.monitors.publish.call_args.kwargs["revision_id"]) == RID


def test_rollback_monitor_needs_confirmation(client: MagicMock) -> None:
    client.monitors.rollback_preview.return_value = build(RollbackPreviewDto)
    client.monitors.rollback.return_value = build(DefinitionHeadDto)
    out = _confirm_flow(
        client, "rollback_monitor", {"monitor_id": MID, "reason": "bad"}
    )
    assert out["status"] == "rolled_back"


def test_token_expires_after_15_minutes() -> None:
    token, _ = _confirm.issue("delete_monitor", {"a": 1}, "m", "tok", now=1000)
    _confirm.verify(token, "delete_monitor", {"a": 1}, "m", "tok", now=1000 + 899)
    with pytest.raises(Exception, match="expired"):
        _confirm.verify(token, "delete_monitor", {"a": 1}, "m", "tok", now=1000 + 901)


def test_token_bound_to_caller_and_args() -> None:
    token, _ = _confirm.issue("publish_monitor", {"a": 1}, "m", "tok", now=1000)
    for tool, args, caller in [
        ("publish_monitor", {"a": 2}, "tok"),
        ("publish_monitor", {"a": 1}, "other"),
        ("delete_monitor", {"a": 1}, "tok"),
    ]:
        with pytest.raises(Exception, match="does not match"):
            _confirm.verify(token, tool, args, "m", caller, now=1000)
    with pytest.raises(Exception, match="malformed"):
        _confirm.verify("abc", "publish_monitor", {"a": 1}, "m", "tok", now=1000)


# -- revisions --------------------------------------------------------------------


def test_list_and_get_revision(client: MagicMock) -> None:
    client.monitors.revisions.list.return_value = Page(data=[build(RevisionDto)])
    client.monitors.revisions.get.return_value = build(RevisionDto)
    call("list_monitor_revisions", {"monitor_id": MID, "state": "all"})
    call("get_monitor_revision", {"monitor_id": MID, "revision_id": RID})


def test_create_and_test_revision(client: MagicMock) -> None:
    client.monitors.revisions.create.return_value = build(CreateDraftRevisionResponse)
    client.monitors.revisions.test.return_value = run()
    call("create_monitor_revision", {"monitor_id": MID, "code": CODE})
    call("test_monitor_revision", {"monitor_id": MID, "revision_id": RID})


def test_diff_and_discard_revision(client: MagicMock) -> None:
    client.monitors.revisions.diff.return_value = build(RevisionDiffDto)
    call("diff_monitor_revisions", {"monitor_id": MID, "revision_id": RID})
    assert (
        data(call("discard_monitor_revision", {"monitor_id": MID, "revision_id": RID}))[
            "status"
        ]
        == "ok"
    )


def test_revision_files_are_capped(client: MagicMock) -> None:
    files = {"a.spec.ts": "x", **{f"data/{i}.json": "y" * 20_000 for i in range(5)}}
    client.monitors.revisions.files.return_value = RevisionFilesDto(
        entrypoint="a.spec.ts", files=files
    )
    out = data(
        call("get_monitor_revision_files", {"monitor_id": MID, "revision_id": RID})
    )
    assert out["truncated"] is True
    assert "a.spec.ts" in out["files"]  # type: ignore[operator]
    assert out["omitted"]
    one = cap_files("a.spec.ts", files, "data/4.json")
    assert list(one.files) == ["data/4.json"]


def test_preview_rollback(client: MagicMock) -> None:
    client.monitors.rollback_preview.return_value = build(RollbackPreviewDto)
    call("preview_rollback_monitor", {"monitor_id": MID})


# -- runs ---------------------------------------------------------------------------


def test_list_runs_caps_limit(client: MagicMock) -> None:
    client.runs.list.return_value = CursorPage(data=[run()])
    call("list_runs", {"params": {"limit": 80, "monitorId": MID}})
    assert client.runs.list.call_args.args[0].limit == 50


@pytest.mark.parametrize(
    ("tool", "path", "model"),
    [
        ("get_run_steps", "steps", None),
        ("get_run_console", "console", RunConsoleDto),
        ("get_run_network", "network", RunNetworkDto),
        ("list_run_artifacts", "artifacts.list", None),
        ("get_run_trace_summary", "trace_summary", RunTraceSummaryDto),
        ("diff_run", "diff", RunDiffDto),
        ("cancel_run", "cancel", RunDto),
    ],
)
def test_run_read_tools(
    client: MagicMock, tool: str, path: str, model: type[RunDto] | None
) -> None:
    target = client.runs
    for part in path.split("."):
        target = getattr(target, part)
    target.return_value = build(model) if model is not None else []
    call(tool, {"run_id": RID})


def test_screenshot_is_an_image_block(client: MagicMock) -> None:
    art = build(RunArtifactDto, content_type="image/png", byte_size=10)
    client.runs.artifacts.list.return_value = [art]
    client.runs.artifacts.link.return_value = MagicMock(url="https://signed")
    client.runs.artifacts.link.return_value = build(
        __import__("devhelm").ArtifactDownloadDto, url="https://signed"
    )
    with patch("devhelm_mcp.tools.runs.read_signed_url", return_value=b"\x89PNG"):
        res = call("get_run_artifact", {"run_id": RID, "artifact_id": str(art.id)})
    assert isinstance(res.content[0], ImageContent)


def test_trace_is_a_signed_url_not_inlined(client: MagicMock) -> None:
    art = build(RunArtifactDto, content_type="application/zip", kind="trace")
    client.runs.artifacts.list.return_value = [art]
    client.runs.artifacts.link.return_value = build(
        __import__("devhelm").ArtifactDownloadDto, url="https://signed/trace"
    )
    with patch("devhelm_mcp.tools.runs.read_signed_url") as read:
        res = call("get_run_artifact", {"run_id": RID, "artifact_id": str(art.id)})
    read.assert_not_called()
    assert len(res.content) == 1 and "https://signed/trace" in res.content[0].text  # type: ignore[union-attr]


# -- account, runtimes, incidents ---------------------------------------------------


@pytest.mark.parametrize(
    ("tool", "path", "value", "args"),
    [
        ("list_runtimes", "runtimes.list", [], {}),
        ("get_runtime", "runtimes.get", RuntimeProfileDto, {"runtime_id": "2026.11"}),
        ("get_account_usage", "account.usage", SyntheticsUsagePeriodDto, {}),
        ("get_account_entitlements", "account.entitlements", EntitlementResponse, {}),
        (
            "get_incident_trigger",
            "incidents.trigger",
            IncidentTriggerDto,
            {"incident_id": "1"},
        ),
        (
            "get_related_incidents",
            "incidents.related",
            RelatedIncidentsResponse,
            {"incident_id": "1"},
        ),
        ("acknowledge_incident", "incidents.acknowledge", None, {"incident_id": "1"}),
        (
            "update_incident",
            "incidents.update",
            IncidentDetailDto,
            {"incident_id": "1", "body": {"title": "t"}},
        ),
        (
            "add_incident_update",
            "incidents.add_update",
            IncidentDetailDto,
            {"incident_id": "1", "body": {"body": "b", "notifySubscribers": False}},
        ),
    ],
)
def test_read_and_incident_tools(
    client: MagicMock,
    tool: str,
    path: str,
    value: object,
    args: dict[str, JsonValue],
) -> None:
    target = client
    for part in path.split("."):
        target = getattr(target, part)
    if value is None:
        from devhelm import AcknowledgeAllIncidentsResponse

        target.return_value = build(AcknowledgeAllIncidentsResponse)
    elif isinstance(value, type):
        target.return_value = build(value)
    else:
        target.return_value = value
    call(tool, args)


@pytest.mark.parametrize(
    ("tool", "method", "model"),
    [
        ("list_incident_runs", "runs", RunDto),
        ("list_incident_events", "events", IncidentActivityEventDto),
    ],
)
def test_incident_cursor_tools(
    client: MagicMock, tool: str, method: str, model: type[RunDto]
) -> None:
    getattr(client.incidents, method).return_value = CursorPage(data=[build(model)])
    call(tool, {"incident_id": "1"})


# -- secrets -----------------------------------------------------------------------


def test_create_and_update_secret_take_no_value() -> None:
    for name in ("create_secret", "update_secret", "set_secret_value"):
        tool = asyncio.run(mcp.get_tool(name))
        assert tool is not None
        assert "value" not in json.dumps(tool.parameters.get("properties", {}))


def test_set_secret_value_without_elicitation_returns_link(client: MagicMock) -> None:
    out = data(call("set_secret_value", {"key": "API_KEY", "environment": "prod"}))
    assert out["status"] == "needs_human"
    assert "key=API_KEY" in str(out["url"]) and "environment=prod" in str(out["url"])
    client.secrets.values.set.assert_not_called()


def test_set_secret_value_with_elicitation(client: MagicMock) -> None:
    async def answer(*_: object) -> str:
        return "s3cret"

    with patch("devhelm_mcp.tools.secrets.ask_value", side_effect=answer):
        out = data(call("set_secret_value", {"key": "K", "environment": "prod"}))
    assert out["status"] == "ok"
    client.secrets.values.set.assert_called_once_with(
        "K", environment="prod", value="s3cret"
    )
    assert "s3cret" not in json.dumps(out)


def test_create_secret_with_elicitation(client: MagicMock) -> None:
    async def answer(*_: object) -> str:
        return "v"

    client.secrets.create.return_value = build(SecretDto)
    with patch("devhelm_mcp.tools.secrets.ask_value", side_effect=answer):
        call("create_secret", {"key": "K"})
    assert client.secrets.create.call_args.args[0] == {"key": "K", "value": "v"}


# -- server-wide rules ---------------------------------------------------------------


def test_every_tool_has_annotations() -> None:
    asyncio.run(_strip_internal_schema_fields())
    tools = asyncio.run(mcp.list_tools())
    missing = [t.name for t in tools if t.annotations is None]
    assert not missing
    by = {t.name: t.annotations for t in tools}
    assert by["get_run"].readOnlyHint is True  # type: ignore[union-attr]
    for name in ("delete_monitor", "publish_monitor", "rollback_monitor"):
        assert by[name].destructiveHint is True  # type: ignore[union-attr]


def test_section_10_tools_are_registered() -> None:
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    spec = [
        "create_monitor",
        "update_monitor",
        "test_monitor",
        "probe_monitor",
        "test_monitor_adhoc",
        "run_monitor_now",
        "trigger_monitor",
        "get_run",
        "list_runs",
        "get_run_steps",
        "get_run_console",
        "get_run_network",
        "list_run_artifacts",
        "get_run_artifact",
        "get_run_trace_summary",
        "diff_run",
        "cancel_run",
        "list_monitor_revisions",
        "get_monitor_revision",
        "get_monitor_revision_files",
        "create_monitor_revision",
        "test_monitor_revision",
        "diff_monitor_revisions",
        "discard_monitor_revision",
        "publish_monitor",
        "rollback_monitor",
        "preview_rollback_monitor",
        "list_monitor_versions",
        "get_monitor_version",
        "list_monitor_history",
        "get_monitor_drift",
        "pause_monitor",
        "resume_monitor",
        "mute_monitor",
        "unmute_monitor",
        "quarantine_monitor",
        "release_quarantine_monitor",
        "delete_monitor",
        "restore_monitor",
        "list_monitor_trash",
        "list_runtimes",
        "get_runtime",
        "set_secret_value",
        "get_account_usage",
        "get_account_entitlements",
        "list_monitor_results",
    ]
    assert set(spec) <= names
    assert not {"deploy", "transfer_monitor", "deploy_monitor"} & names


def test_investigate_incident_prompt() -> None:
    prompts = asyncio.run(mcp.list_prompts())
    assert "investigate_incident" in {p.name for p in prompts}


def test_instructions_are_workflows() -> None:
    text = mcp.instructions or ""
    for step in (
        "test_monitor_adhoc",
        "create_monitor_revision",
        "publish_monitor",
        "trigger_monitor",
        "rollback_monitor",
        "confirmation_token",
    ):
        assert step in text


def test_text_cap() -> None:
    text = capped_text({"x": "y" * (TEXT_CAP_BYTES * 2)})
    assert len(text.encode()) <= TEXT_CAP_BYTES
    assert '"truncated": true' in text
