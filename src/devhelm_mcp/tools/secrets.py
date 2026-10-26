"""Secret tools. A secret value never passes through the chat (doc 42 R10).

Values are collected from the human with MCP elicitation when the client
supports it; otherwise the tool returns the dashboard link where the human
sets the value. ``create_secret`` / ``update_secret`` take no ``value``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlencode
from uuid import UUID

import anyio
from devhelm import CreateSecretRequest, Devhelm, SecretDto, UpdateSecretRequest
from fastmcp import Context, FastMCP
from fastmcp.server.elicitation import AcceptedElicitation
from pydantic import BaseModel, Field

from devhelm_mcp._models import Declined, Done, SecretValueLink
from devhelm_mcp._tooling import DESTRUCTIVE, READ, WRITE, WRITE_IDEMPOTENT, tool
from devhelm_mcp.client import get_client

APP_URL = os.getenv("DEVHELM_APP_URL", "https://app.devhelm.io")


def secret_link(key: str, environment: str | None) -> str:
    query = {"key": key, **({"environment": environment} if environment else {})}
    return f"{APP_URL}/secrets?{urlencode(query)}"


class SecretValueInput(BaseModel):
    """What the elicitation form asks the human for."""

    value: str = Field(description="Secret value (sent to DevHelm only)")


def _supports_elicitation(ctx: Context) -> bool:
    if ctx.request_context is None:
        return False  # no live MCP session (direct calls): nobody to ask
    params = ctx.session.client_params
    return bool(params and params.capabilities and params.capabilities.elicitation)


@dataclass(frozen=True)
class Answer:
    """What asking the human produced."""

    kind: Literal["value", "declined", "unsupported"]
    value: str = ""


async def ask_value(ctx: Context, key: str, environment: str | None) -> Answer:
    """Ask the human for the value with MCP elicitation, when the client can."""
    if not _supports_elicitation(ctx):
        return Answer("unsupported")
    where = f" in environment {environment}" if environment else ""
    answer = await ctx.elicit(
        f"Enter the value for secret {key}{where}. It goes straight to DevHelm "
        "and is not shown to the assistant.",
        # fastmcp's ``elicit`` overloads are split by docstrings, so mypy only
        # sees the ``None`` one; the runtime accepts a BaseModel type.
        response_type=SecretValueInput,  # type: ignore[arg-type]
    )
    if isinstance(answer, AcceptedElicitation):
        data: object = answer.data
        if isinstance(data, SecretValueInput) and data.value:
            return Answer("value", data.value)
    return Answer("declined")


def _link(key: str, environment: str | None) -> SecretValueLink:
    return SecretValueLink(
        url=secret_link(key, environment),
        message="This client can't collect secret values safely. Ask the user to "
        "open the link and set the value there; never ask them to paste it in "
        "chat.",
    )


def _declined() -> Declined:
    return Declined(
        message="The user declined; nothing changed. Don't retry unless they ask."
    )


def _environment_id(client: Devhelm, environment: str) -> UUID:
    try:
        return UUID(environment)
    except ValueError:
        return client.environments.get(environment).id


def register(mcp: FastMCP) -> None:
    @tool(mcp, READ)
    def list_secrets(
        environment: str | None = None, api_token: str | None = None
    ) -> list[SecretDto]:
        """Secrets (metadata only; values are never returned). With
        ``environment`` each carries that environment's value stamp."""
        return get_client(api_token).secrets.list(environment=environment)

    @tool(mcp, WRITE_IDEMPOTENT)
    async def set_secret_value(
        key: str,
        environment: str,
        ctx: Context,
        api_token: str | None = None,
    ) -> Done | Declined | SecretValueLink:
        """Set a secret's value in one environment (slug or id). The value is
        asked from the user directly (elicitation), or the tool returns the
        dashboard link. Never put a value in the arguments or the chat."""
        answer = await ask_value(ctx, key, environment)
        if answer.kind == "unsupported":
            return _link(key, environment)
        if answer.kind == "declined":
            return _declined()
        client = get_client(api_token)
        await anyio.to_thread.run_sync(
            lambda: client.secrets.values.set(
                key, environment=environment, value=answer.value
            )
        )
        return Done(message=f"Value of {key} set in {environment}.")

    @tool(mcp, WRITE)
    async def create_secret(
        key: str,
        ctx: Context,
        environment: str | None = None,
        api_token: str | None = None,
    ) -> SecretDto | Declined | SecretValueLink:
        """Create a secret. Its value is asked from the user directly
        (elicitation), or the tool returns the dashboard link. Code reads it
        as {{secrets.KEY}}."""
        answer = await ask_value(ctx, key, environment)
        if answer.kind == "unsupported":
            return _link(key, environment)
        if answer.kind == "declined":
            return _declined()
        client = get_client(api_token)

        def create() -> SecretDto:
            env_id = _environment_id(client, environment) if environment else None
            body = CreateSecretRequest(
                key=key, value=answer.value, environment_id=env_id
            )
            return client.secrets.create(body)

        return await anyio.to_thread.run_sync(create)

    @tool(mcp, WRITE)
    async def update_secret(
        key: str, ctx: Context, api_token: str | None = None
    ) -> SecretDto | Declined | SecretValueLink:
        """Replace a secret's value. Asked from the user directly
        (elicitation), or the tool returns the dashboard link."""
        answer = await ask_value(ctx, key, None)
        if answer.kind == "unsupported":
            return _link(key, None)
        if answer.kind == "declined":
            return _declined()
        client = get_client(api_token)
        return await anyio.to_thread.run_sync(
            lambda: client.secrets.update(key, UpdateSecretRequest(value=answer.value))
        )

    @tool(mcp, DESTRUCTIVE)
    def delete_secret(key: str, api_token: str | None = None) -> Done:
        """Delete a secret by key."""
        get_client(api_token).secrets.delete(key)
        return Done(message=f"Secret {key} deleted.")
