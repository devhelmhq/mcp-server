"""Confirmation tokens for delete_monitor, publish_monitor and rollback_monitor.

The first call returns ``{status: "confirmation_required", changes,
confirmationToken}``. The token is an HMAC-SHA256, signed by this server
process, over the tool name, its arguments, the target and the caller's
token, plus the issue time. It is valid for 15 minutes. The agent shows the
changes to the human and calls again with ``confirmation_token``.

The key is ``DEVHELM_MCP_CONFIRMATION_SECRET`` when set (so every replica of
the hosted server accepts the same token), else random per process.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from collections.abc import Mapping

from devhelm import DevhelmApiError
from devhelm._errors import client_error
from pydantic import JsonValue

TOKEN_TTL_SECONDS = 15 * 60

_env_secret = os.getenv("DEVHELM_MCP_CONFIRMATION_SECRET")
_KEY = _env_secret.encode() if _env_secret else secrets.token_bytes(32)


def _mac(
    tool: str,
    args: Mapping[str, JsonValue],
    target: str,
    caller: str,
    issued: int,
) -> bytes:
    message = json.dumps(
        {
            "tool": tool,
            "args": args,
            "target": target,
            "caller": hashlib.sha256(caller.encode()).hexdigest(),
            "issued": issued,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hmac.new(_KEY, message.encode(), hashlib.sha256).digest()


def issue(
    tool: str,
    args: Mapping[str, JsonValue],
    target: str,
    caller: str,
    *,
    now: float | None = None,
) -> tuple[str, int]:
    """A token for this exact call, and its expiry (unix seconds)."""
    issued = int(now if now is not None else time.time())
    mac = _mac(tool, args, target, caller, issued)
    raw = issued.to_bytes(8, "big") + mac
    return base64.urlsafe_b64encode(raw).decode().rstrip(
        "="
    ), issued + TOKEN_TTL_SECONDS


def verify(
    token: str,
    tool: str,
    args: Mapping[str, JsonValue],
    target: str,
    caller: str,
    *,
    now: float | None = None,
) -> None:
    """Raise ``ConfirmationRequiredError`` unless the token matches this call."""
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except (ValueError, TypeError):
        raw = b""
    if len(raw) != 8 + 32:
        raise _invalid("The confirmation token is malformed.")
    issued = int.from_bytes(raw[:8], "big")
    expected = _mac(tool, args, target, caller, issued)
    if not hmac.compare_digest(expected, raw[8:]):
        raise _invalid(
            "The confirmation token does not match this call (different "
            "arguments, target or caller)."
        )
    current = now if now is not None else time.time()
    if current > issued + TOKEN_TTL_SECONDS or current < issued - 60:
        raise _invalid("The confirmation token expired (tokens last 15 minutes).")


def _invalid(message: str) -> DevhelmApiError:
    return client_error(
        "confirmation_required",
        "CONFIRMATION_TOKEN_INVALID",
        message,
        field="confirmation_token",
    )
