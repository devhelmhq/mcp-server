"""Shared helpers for the Email Testing and Webhook Testing tools.

The SDK returns bound handles (``Message``, ``Domain``, ``Inbox``, ``Event``)
rather than Pydantic models, so ``serialize`` cannot dump them. ``plain``
turns a handle into the camelCase JSON the API returned, minus the nested
sub-resource handles (``address.messages``, ``inbox.events``).

Outputs are bounded for agents: waits are capped at ``MAX_WAIT_S`` seconds
and long text fields at ``MAX_TEXT_BYTES``, with a ``truncated`` flag.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from fastmcp.exceptions import ToolError
from pydantic import BaseModel

MAX_WAIT_S = 25
MAX_TEXT_BYTES = 64 * 1024
MAX_LIST_LIMIT = 50

# Annotation presets (MCP tool hints). Destructive tools are deliberately not
# offered on MCP until the confirmation envelope exists.
READ_ONLY: dict[str, bool] = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}
WAIT: dict[str, bool] = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": False,
}
CREATE: dict[str, bool] = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": False,
}
UPDATE: dict[str, bool] = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

_SKIP_ATTRS = frozenset({"messages", "events"})


def _camel(name: str) -> str:
    if name == "from_":
        return "from"
    head, *rest = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in rest)


def plain(value: object) -> Any:
    """Convert an SDK handle, model or primitive into JSON-safe data."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", by_alias=True)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return plain(value.value)
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    attrs = getattr(value, "__dict__", None)
    if attrs is None and hasattr(value, "__slots__"):
        attrs = {name: getattr(value, name) for name in value.__slots__}
    if isinstance(attrs, dict):
        return {
            _camel(key): plain(item)
            for key, item in attrs.items()
            if not key.startswith("_") and key not in _SKIP_ATTRS
        }
    raise TypeError(f"Cannot serialize {type(value).__name__} to JSON")


def as_dict(value: object) -> dict[str, Any]:
    """``plain`` for a single handle or model; the result is always an object."""
    data = plain(value)
    if not isinstance(data, dict):
        raise TypeError(f"Expected an object, got {type(value).__name__}")
    return data


def cap_text(text: str | None) -> tuple[str | None, bool]:
    """Clip ``text`` to ``MAX_TEXT_BYTES`` of UTF-8. Returns (text, truncated)."""
    if text is None:
        return None, False
    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_TEXT_BYTES:
        return text, False
    return encoded[:MAX_TEXT_BYTES].decode("utf-8", errors="ignore"), True


def cap_fields(
    data: dict[str, Any], fields: tuple[str, ...], flag: str
) -> dict[str, Any]:
    """Clip each text field in ``data``; set ``flag`` when any was clipped."""
    clipped = False
    for field in fields:
        value = data.get(field)
        if isinstance(value, str):
            data[field], cut = cap_text(value)
            clipped = clipped or cut
    if clipped:
        data[flag] = True
    return data


def wait_ms(wait_s: int) -> int:
    """Bound a wait to ``1..MAX_WAIT_S`` seconds, in milliseconds."""
    return max(1, min(wait_s, MAX_WAIT_S)) * 1000


def bound_limit(limit: int | None) -> int:
    if limit is None:
        return 20
    return max(1, min(limit, MAX_LIST_LIMIT))


def split_address(to: str) -> tuple[str, str]:
    """Split ``local@domain`` into (local_part, domain)."""
    local, sep, domain = to.rpartition("@")
    if not sep or not local or not domain:
        raise ToolError(f"Expected a full address like name@domain, got {to!r}")
    return local, domain
