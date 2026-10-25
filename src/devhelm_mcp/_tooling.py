"""Typed tool registration: annotations, output conversion and errors.

``@tool(mcp, READ)`` registers a function whose return annotation is a
generated SDK model (or a surface envelope in ``devhelm_mcp._models``). The
wrapper:

* dumps the result by alias (``camelCase``, the API's field names) into both
  ``structuredContent`` and the text block, and advertises the matching
  ``outputSchema``. FastMCP on its own dumps by Python name but describes
  the schema by alias, which a validating client rejects;
* caps the text block at 64 KB (``truncated: true``);
* turns every ``DevhelmError`` into ``isError: true`` carrying the
  ``ErrorResponse`` fields plus one sentence telling the agent what to do.
"""

from __future__ import annotations

import functools
import inspect
import json
from collections.abc import Callable, Mapping
from typing import ParamSpec, TypeVar, get_type_hints

from devhelm import DevhelmApiError, DevhelmError, DevhelmValidationError
from devhelm import WaitTimeoutError as _WaitTimeout
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import ToolResult
from mcp.types import ContentBlock, ImageContent, TextContent, ToolAnnotations
from pydantic import BaseModel, JsonValue, TypeAdapter

P = ParamSpec("P")
R = TypeVar("R")

#: Text content cap per tool call (doc 42 §10 "bounded output").
TEXT_CAP_BYTES = 64 * 1024

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)
WRITE_IDEMPOTENT = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True
)
DESTRUCTIVE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=False
)
DESTRUCTIVE_IDEMPOTENT = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=True
)

#: Content blocks a tool may return instead of a model (screenshots).
Blocks = list[TextContent | ImageContent]


# -- output -------------------------------------------------------------------


def _is_object_schema(schema: Mapping[str, JsonValue]) -> bool:
    if schema.get("type") == "object" or "$ref" in schema:
        return True
    for key in ("anyOf", "oneOf"):
        branches = schema.get(key)
        if isinstance(branches, list) and branches:
            return all(
                isinstance(b, dict) and (b.get("type") == "object" or "$ref" in b)
                for b in branches
            )
    return False


def output_schema_for(tp: object) -> tuple[dict[str, JsonValue], bool]:
    """The by-alias serialization schema for ``tp`` and whether it is wrapped.

    MCP output schemas must be objects; anything else (a list) is wrapped as
    ``{"result": …}``, the FastMCP convention.
    """
    adapter: TypeAdapter[object] = TypeAdapter(tp)
    schema: dict[str, JsonValue] = adapter.json_schema(
        mode="serialization", by_alias=True
    )
    if _is_object_schema(schema):
        schema.setdefault("type", "object")
        return schema, False
    defs = schema.pop("$defs", None)
    wrapped: dict[str, JsonValue] = {
        "type": "object",
        "properties": {"result": schema},
        "required": ["result"],
        "x-fastmcp-wrap-result": True,
    }
    if defs is not None:
        wrapped["$defs"] = defs
    return wrapped, True


def to_json(value: object) -> JsonValue:
    """Dump models by alias in JSON mode; lists and dicts recurse."""
    if isinstance(value, BaseModel):
        dumped: JsonValue = value.model_dump(mode="json", by_alias=True)
        return dumped
    if isinstance(value, list | tuple):
        return [to_json(v) for v in value]
    if isinstance(value, dict):
        return {str(k): to_json(v) for k, v in value.items()}
    adapter: TypeAdapter[object] = TypeAdapter(type(value))
    out: JsonValue = adapter.dump_python(value, mode="json")
    return out


def capped_text(data: JsonValue) -> str:
    """JSON text, cut at ``TEXT_CAP_BYTES`` with a ``truncated`` marker."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    raw = text.encode("utf-8")
    if len(raw) <= TEXT_CAP_BYTES:
        return text
    head = raw[: TEXT_CAP_BYTES - 200].decode("utf-8", errors="ignore")
    note = json.dumps(
        {
            "truncated": True,
            "bytes": len(raw),
            "hint": "Output exceeds 64 KB; narrow the call with limit/cursor "
            "or a filter.",
        }
    )
    return f"{head}\n…\n{note}"


def _convert(value: object, wrapped: bool, is_blocks: bool) -> ToolResult:
    if is_blocks and isinstance(value, list):
        blocks: list[ContentBlock] = [
            v for v in value if isinstance(v, TextContent | ImageContent)
        ]
        return ToolResult(content=blocks)
    data = to_json(value)
    text = TextContent(type="text", text=capped_text(data))
    if wrapped:
        return ToolResult(
            content=[text],
            structured_content={"result": data},
            meta={"fastmcp": {"wrap_result": True}},
        )
    if not isinstance(data, dict):
        raise TypeError(f"tool returned {type(value).__name__}, expected an object")
    return ToolResult(content=[text], structured_content=data)


# -- errors -------------------------------------------------------------------

_CATEGORY_HINTS: dict[str, str] = {
    "validation": "Fix the fields named in `errors` and call the tool again.",
    "blocked": "Something must be set up first (see `next`). Tell the user what "
    "is missing; do not try to work around it.",
    "auth": "Ask the user to check the DevHelm API token (DEVHELM_API_TOKEN, or "
    "the Authorization header for the hosted server).",
    "permission": "The API key lacks a scope or role (`required`). Ask the user "
    "for a key that has it.",
    "ownership": "Another tool owns this resource (`owner`). Ask the user to "
    "change it there, or to transfer ownership in the dashboard.",
    "plan": "The plan does not allow this (`limit`, `plan`). Ask the user "
    "whether to upgrade (`upgradeUrl`) or reduce usage.",
    "quota": "The usage quota for this period is used up until `resetsAt`. Ask "
    "the user whether to raise the cap or wait.",
    "rate_limit": "Rate limited. Wait `retryAfterSeconds` seconds, then retry once.",
    "conflict": "The resource changed or is locked. Re-read it, then retry with "
    "fresh values; ask the user if the conflict is not yours.",
    "confirmation_required": "This needs explicit confirmation. Show the user "
    "the change and ask before calling again.",
    "not_found": "Nothing exists with that id. List the resources to find the "
    "right id; do not guess.",
    "gone": "The data expired past retention and cannot be recovered. Tell the user.",
    "platform": "DevHelm failed on its side. Retry once later; if it persists, "
    "give the user the `requestId`.",
    "transport": "DevHelm could not be reached. Retry once; if it persists, ask "
    "the user to check network access to the API.",
    "timeout": "The run is still going. Call get_run with wait_s to keep polling.",
}

_CODE_HINTS: dict[str, str] = {
    "USE_PROBE": "This is an uptime monitor: call probe_monitor instead.",
    "LIVE_REVISION_CHANGED": "Someone published in between. Call "
    "get_monitor for the new liveRevisionId and ask the user before retrying.",
    "REVISION_UNTESTED": "Test the revision with test_monitor_revision first, "
    "or ask the user whether to publish untested.",
    "DRAFT_LIMIT": "The monitor has 10 drafts. Discard one with "
    "discard_monitor_revision, then retry.",
    "ROLLBACK_INCIDENT_REQUIRED": "An emergency rollback needs a confirmed "
    "incident. Retry without emergency.",
    "SYNTHETICS_USAGE_CAPPED": "The synthetics run cap is reached. Ask the user "
    "to raise it (get_account_usage shows the numbers).",
    "CONFIRMATION_TOKEN_INVALID": "Call the tool again without "
    "confirmation_token to get a fresh one, show the user the changes and ask.",
}


_STATUS_CATEGORY = {
    400: "validation",
    401: "auth",
    402: "plan",
    403: "permission",
    404: "not_found",
    409: "conflict",
    410: "gone",
    429: "rate_limit",
}


def _category(err: DevhelmApiError) -> str:
    """The envelope's category; else the HTTP status's (non-envelope bodies)."""
    if err.envelope is not None or err.status == 0:
        return err.category
    if err.status >= 500:
        return "platform"
    return _STATUS_CATEGORY.get(err.status, err.category)


def error_payload(err: DevhelmError) -> dict[str, JsonValue]:
    """Every ``ErrorResponse`` field the error carries, by wire name."""
    if isinstance(err, DevhelmApiError):
        if err.envelope is not None:
            data: dict[str, JsonValue] = err.envelope.model_dump(
                mode="json", by_alias=True, exclude_none=True
            )
        else:
            data = {
                "status": err.status,
                "code": err.code,
                "category": _category(err),
                "retryable": err.retryable,
                "message": err.message,
            }
            if err.errors:
                data["errors"] = [
                    e.model_dump(mode="json", by_alias=True, exclude_none=True)
                    for e in err.errors
                ]
            if err.next is not None:
                data["next"] = err.next.model_dump(
                    mode="json", by_alias=True, exclude_none=True
                )
            if err.details is not None:
                data["details"] = err.details
        if err.request_id and "requestId" not in data:
            data["requestId"] = err.request_id
        if err.retry_after is not None:
            data["retryAfterSeconds"] = err.retry_after
        return data
    data = {
        "status": 0,
        "code": err.code,
        "category": err.category,
        "retryable": err.category in ("transport", "timeout"),
        "message": err.message,
    }
    if isinstance(err, DevhelmValidationError) and err.errors:
        data["errors"] = [
            {
                "code": "FIELD_INVALID",
                "field": ".".join(str(p) for p in e.get("loc", ())),
                "message": e.get("msg", ""),
            }
            for e in err.errors
        ]
    if isinstance(err, _WaitTimeout):
        data["details"] = {"runId": err.run_id, "phase": err.phase}
    return data


def agent_text(err: DevhelmError) -> str:
    """One sentence for the agent, then the error fields as JSON."""
    payload = error_payload(err)
    code = str(payload.get("code", ""))
    category = str(payload.get("category", ""))
    hint = _CODE_HINTS.get(code) or _CATEGORY_HINTS.get(
        category, "Tell the user what failed and include the requestId."
    )
    nxt = payload.get("next")
    if isinstance(nxt, dict) and nxt.get("command"):
        hint += f" Suggested next step: {nxt['command']}."
    header = f"{category or 'error'} {code}: {payload.get('message', '')}".strip()
    return f"{header}\n{hint}\n{json.dumps({'error': payload}, ensure_ascii=False)}"


def tool_error(err: DevhelmError) -> ToolError:
    return ToolError(agent_text(err))


_READ_VERBS = ("list_", "get_", "search_", "preview_")
_DESTRUCTIVE_VERBS = (
    "delete_",
    "remove_",
    "revoke_",
    "cancel_",
    "dismiss_",
    "force_release_",
    "release_",
)
_IDEMPOTENT_VERBS = ("update_", "set_", "reorder_", "publish_", "resolve_")


def default_annotations(name: str) -> ToolAnnotations:
    """Annotations for a tool registered without explicit ones, by verb."""
    if name.startswith(_READ_VERBS):
        return READ
    if name.startswith(_DESTRUCTIVE_VERBS):
        return DESTRUCTIVE_IDEMPOTENT
    if name.startswith(_IDEMPOTENT_VERBS):
        return WRITE_IDEMPOTENT
    return WRITE


# -- registration ---------------------------------------------------------------


def tool(
    mcp: FastMCP,
    annotations: ToolAnnotations,
    *,
    name: str | None = None,
    description: str | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Register a typed tool. See the module docstring."""

    def decorate(fn: Callable[P, R]) -> Callable[P, R]:
        hints = get_type_hints(fn, include_extras=True)
        returns = hints.pop("return")
        is_blocks = returns == Blocks
        schema, wrapped = (None, False) if is_blocks else output_schema_for(returns)
        sig = inspect.signature(fn)
        params = [
            p.replace(annotation=hints.get(p.name, p.annotation))
            for p in sig.parameters.values()
        ]

        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def run_async(*args: P.args, **kwargs: P.kwargs) -> ToolResult:
                try:
                    value = await fn(*args, **kwargs)
                except DevhelmError as e:
                    raise tool_error(e) from e
                return _convert(value, wrapped, is_blocks)

            wrapper: Callable[..., object] = run_async
        else:

            @functools.wraps(fn)
            def run_sync(*args: P.args, **kwargs: P.kwargs) -> ToolResult:
                try:
                    value = fn(*args, **kwargs)
                except DevhelmError as e:
                    raise tool_error(e) from e
                return _convert(value, wrapped, is_blocks)

            wrapper = run_sync

        wrapper.__signature__ = sig.replace(  # type: ignore[attr-defined]  # read by inspect.signature
            parameters=params, return_annotation=ToolResult
        )
        wrapper.__annotations__ = {**hints, "return": ToolResult}
        del wrapper.__wrapped__  # type: ignore[attr-defined]  # stop signature unwrapping
        mcp.tool(
            wrapper,
            name=name or fn.__name__,
            description=description or inspect.getdoc(fn),
            annotations=annotations,
            output_schema=schema,
        )
        return fn

    return decorate
