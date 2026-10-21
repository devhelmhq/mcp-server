"""Tests for the Email Testing and Webhook Testing MCP tools.

The tools wrap the SDK's bound handles (``client.email`` / ``client.inboxes``).
Each test wires real SDK resources to an ``httpx.MockTransport`` so the tools
are exercised end to end against the wire contract: request path, query,
body, and the bounded, JSON-safe tool output.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from devhelm.resources.email import Email
from devhelm.resources.inboxes import Inboxes

from devhelm_mcp.server import _strip_internal_schema_fields, mcp
from devhelm_mcp.tools._inbound import MAX_TEXT_BYTES

RegisteredTools = dict[str, Any]
Handler = Callable[[httpx.Request], httpx.Response]

EMAIL_TOOLS = [
    "create_email_address",
    "wait_for_email",
    "list_email_messages",
    "get_latest_email",
    "get_email_message",
    "get_email_message_source",
    "list_email_otp_codes",
    "list_email_links",
    "inject_email_message",
    "list_email_domains",
    "get_email_domain",
    "create_email_domain",
    "update_email_domain",
    "verify_email_domain",
    "list_email_domain_activity",
]

INBOX_TOOLS = [
    "list_webhook_inboxes",
    "get_webhook_inbox",
    "create_webhook_inbox",
    "update_webhook_inbox",
    "list_webhook_inbox_activity",
    "wait_for_webhook_event",
    "list_webhook_events",
    "get_latest_webhook_event",
    "get_webhook_event",
]

DOMAIN = "abc.devhelmmail.com"
MESSAGE_ID = "22222222-2222-2222-2222-222222222222"
INBOX_ID = "33333333-3333-3333-3333-333333333333"
EVENT_ID = "44444444-4444-4444-4444-444444444444"

_DOMAIN_DTO: dict[str, Any] = {
    "id": "11111111-1111-1111-1111-111111111111",
    "name": DOMAIN,
    "workspaceId": 1,
    "kind": "assigned",
    "status": "active",
    "mxVerified": True,
    "verificationToken": None,
    "verificationError": None,
    "verifiedAt": None,
    "dnsRecords": [],
    "retentionDays": 7,
    "lastMessageAt": None,
    "createdAt": "2026-10-01T00:00:00Z",
    "updatedAt": "2026-10-01T00:00:00Z",
}

_MESSAGE_DTO: dict[str, Any] = {
    "id": MESSAGE_ID,
    "domainId": _DOMAIN_DTO["id"],
    "inbox": "signup-1",
    "receivedAt": "2026-10-21T10:00:00Z",
    "sizeBytes": 1200,
    "from": "noreply@app.example",
    "to": [f"signup-1@{DOMAIN}"],
    "subject": "Your code",
    "headers": {},
    "bodyPreview": "Your code is 123456",
    "otp": [{"value": "123456", "source": "text"}],
    "links": [{"href": "https://app.example/verify", "text": "Verify"}],
    "attachments": [],
    "text": "Your code is 123456",
    "html": None,
    "bodyTruncated": False,
    "rawUrl": None,
    "sha256": "0" * 64,
}

_INBOX_DTO: dict[str, Any] = {
    "id": INBOX_ID,
    "workspaceId": 1,
    "name": "stripe",
    "status": "active",
    "publicToken": "tok",
    "httpUrl": "https://in.devhelm.io/tok",
    "httpResponse": {
        "status": 200,
        "headers": {},
        "body": "",
        "contentType": "text/plain",
        "delayMs": 0,
    },
    "cors": True,
    "retentionDays": 7,
    "maxEvents": 10000,
    "lastEventAt": None,
    "createdAt": "2026-10-01T00:00:00Z",
    "updatedAt": "2026-10-01T00:00:00Z",
}

_EVENT_DTO: dict[str, Any] = {
    "id": EVENT_ID,
    "inboxId": INBOX_ID,
    "receivedAt": "2026-10-21T10:00:00Z",
    "sizeBytes": 12,
    "sourceIp": "203.0.113.1",
    "headers": {"content-type": ["application/json"]},
    "method": "POST",
    "path": "/hook",
    "query": None,
    "url": "https://in.devhelm.io/tok/hook",
    "host": "in.devhelm.io",
    "bodyPreview": '{"ok":true}',
    "body": '{"ok":true}',
    "sha256": "0" * 64,
    "bodyTruncated": False,
    "rawUrl": None,
}


@pytest.fixture(scope="module")
def registered_tools() -> RegisteredTools:
    asyncio.run(_strip_internal_schema_fields())
    tools = asyncio.run(mcp.list_tools())
    return {t.name: t for t in tools}


class _Recorder:
    def __init__(self, handler: Handler) -> None:
        self.handler = handler
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.handler(request)


def _sdk(handler: Handler) -> tuple[MagicMock, _Recorder]:
    recorder = _Recorder(handler)
    http = httpx.Client(
        base_url="https://api.test", transport=httpx.MockTransport(recorder)
    )
    client = MagicMock()
    client.email = Email(http)
    client.inboxes = Inboxes(http)
    return client, recorder


def _call(module: str, client: MagicMock, name: str, args: dict[str, Any]) -> Any:
    with patch(f"devhelm_mcp.tools.{module}.get_client", return_value=client):
        result = asyncio.run(mcp.call_tool(name, args))
    # ``ToolResult`` is a union, so FastMCP wraps output under ``result``.
    return result.structured_content["result"]


def _ok(data: Any) -> httpx.Response:
    return httpx.Response(200, json=data)


# --------------------------------------------------------------------------- #
# Registration and annotations
# --------------------------------------------------------------------------- #


class TestRegistration:
    @pytest.mark.parametrize("name", EMAIL_TOOLS + INBOX_TOOLS)
    def test_registered_with_annotations(
        self, registered_tools: RegisteredTools, name: str
    ) -> None:
        tool = registered_tools[name]
        assert tool.annotations is not None
        assert tool.annotations.destructiveHint is False
        assert "api_token" not in tool.parameters.get("properties", {})

    @pytest.mark.parametrize(
        "name",
        [n for n in EMAIL_TOOLS + INBOX_TOOLS if n.startswith(("list_", "get_"))],
    )
    def test_reads_are_read_only(
        self, registered_tools: RegisteredTools, name: str
    ) -> None:
        assert registered_tools[name].annotations.readOnlyHint is True

    def test_no_destructive_or_binary_tools(
        self, registered_tools: RegisteredTools
    ) -> None:
        for name in registered_tools:
            if "email" in name or "webhook_inbox" in name or "webhook_event" in name:
                assert not name.startswith(("delete_", "clear_", "remove_"))
                assert "raw" not in name and "attachment" not in name


# --------------------------------------------------------------------------- #
# Email Testing
# --------------------------------------------------------------------------- #


class TestEmailTools:
    def test_create_email_address_uses_assigned_domain(self) -> None:
        client, rec = _sdk(
            lambda r: _ok({"data": [_DOMAIN_DTO], "hasNext": False, "hasPrev": False})
        )
        out = _call(
            "email_testing", client, "create_email_address", {"label": "signup"}
        )
        assert out["domain"] == DOMAIN
        assert out["email"].startswith("signup-")
        assert out["email"].endswith(f"@{DOMAIN}")
        assert rec.requests[0].url.path == "/api/v1/email/domains"

    def test_wait_for_email_caps_wait(self) -> None:
        client, rec = _sdk(lambda r: _ok({"message": _MESSAGE_DTO}))
        out = _call(
            "email_testing",
            client,
            "wait_for_email",
            {"to": f"signup-1@{DOMAIN}", "wait_s": 600},
        )
        body = json.loads(rec.requests[0].content)
        assert rec.requests[0].url.path == "/api/v1/email/wait"
        assert body["timeoutMs"] == 25_000
        assert body["to"] == f"signup-1@{DOMAIN}"
        assert out["otp"][0]["value"] == "123456"
        assert out["from"] == "noreply@app.example"

    def test_list_email_messages_filters_by_local_part(self) -> None:
        client, rec = _sdk(
            lambda r: _ok({"data": [_MESSAGE_DTO], "nextCursor": "c2", "hasMore": True})
        )
        out = _call(
            "email_testing",
            client,
            "list_email_messages",
            {"to": f"signup-1@{DOMAIN}", "limit": 500},
        )
        req = rec.requests[0]
        assert req.url.path == f"/api/v1/email/domains/{DOMAIN}/messages"
        assert req.url.params["inbox"] == "signup-1"
        assert req.url.params["limit"] == "50"
        assert out["nextCursor"] == "c2"
        assert out["hasMore"] is True

    def test_get_latest_email_empty(self) -> None:
        client, _ = _sdk(
            lambda r: _ok({"data": [], "nextCursor": None, "hasMore": False})
        )
        out = _call("email_testing", client, "get_latest_email", {"to": f"x@{DOMAIN}"})
        assert out == {"message": None}

    def test_message_text_is_capped(self) -> None:
        big = dict(_MESSAGE_DTO, text="a" * (MAX_TEXT_BYTES + 10))
        client, _ = _sdk(lambda r: _ok({"data": big}))
        out = _call(
            "email_testing",
            client,
            "get_email_message",
            {"to": f"signup-1@{DOMAIN}", "message_id": MESSAGE_ID},
        )
        assert len(out["text"]) == MAX_TEXT_BYTES
        assert out["bodyTruncated"] is True

    def test_otp_codes(self) -> None:
        def handler(r: httpx.Request) -> httpx.Response:
            if r.url.path.endswith("/otp"):
                return _ok(
                    {
                        "data": [{"value": "123456", "source": "text"}],
                        "hasNext": False,
                        "hasPrev": False,
                    }
                )
            return _ok({"data": _MESSAGE_DTO})

        client, rec = _sdk(handler)
        out = _call(
            "email_testing",
            client,
            "list_email_otp_codes",
            {"to": f"signup-1@{DOMAIN}", "message_id": MESSAGE_ID},
        )
        assert rec.requests[-1].url.path.endswith(f"/messages/{MESSAGE_ID}/otp")
        assert out == [{"value": "123456", "source": "text"}]

    def test_source_is_capped(self) -> None:
        def handler(r: httpx.Request) -> httpx.Response:
            if r.url.path.endswith("/source"):
                return _ok(
                    {"data": {"source": "b" * (MAX_TEXT_BYTES * 2), "truncated": False}}
                )
            return _ok({"data": _MESSAGE_DTO})

        client, _ = _sdk(handler)
        out = _call(
            "email_testing",
            client,
            "get_email_message_source",
            {"to": f"signup-1@{DOMAIN}", "message_id": MESSAGE_ID},
        )
        assert len(out["source"]) == MAX_TEXT_BYTES
        assert out["truncated"] is True

    def test_inject_email_message(self) -> None:
        client, rec = _sdk(
            lambda r: _ok(
                {
                    "data": {
                        "eventId": EVENT_ID,
                        "receivedAt": "2026-10-21T10:00:00Z",
                        "inbox": "signup-1",
                    }
                }
            )
        )
        out = _call(
            "email_testing",
            client,
            "inject_email_message",
            {
                "to": f"signup-1@{DOMAIN}",
                "from_address": "qa@app.example",
                "subject": "hi",
            },
        )
        req = rec.requests[0]
        assert req.url.path == f"/api/v1/email/domains/{DOMAIN}/messages/inject"
        assert json.loads(req.content)["from"] == "qa@app.example"
        assert out["eventId"] == EVENT_ID

    def test_update_email_domain(self) -> None:
        client, rec = _sdk(
            lambda r: _ok({"data": dict(_DOMAIN_DTO, status="disabled")})
        )
        out = _call(
            "email_testing",
            client,
            "update_email_domain",
            {"name": DOMAIN, "status": "disabled"},
        )
        assert rec.requests[0].method == "PATCH"
        assert json.loads(rec.requests[0].content) == {"status": "disabled"}
        assert out["status"] == "disabled"

    def test_bad_address_is_tool_error(self) -> None:
        client, _ = _sdk(lambda r: _ok({}))
        with pytest.raises(Exception, match="full address"):
            _call("email_testing", client, "get_latest_email", {"to": "nobody"})


# --------------------------------------------------------------------------- #
# Webhook Testing
# --------------------------------------------------------------------------- #


class TestWebhookInboxTools:
    def test_create_webhook_inbox(self) -> None:
        client, rec = _sdk(lambda r: _ok({"data": _INBOX_DTO}))
        out = _call(
            "webhook_inboxes",
            client,
            "create_webhook_inbox",
            {"body": {"name": "stripe", "maxEvents": 100}},
        )
        req = rec.requests[0]
        assert req.method == "POST"
        assert req.url.path == "/api/v1/webhook/inboxes"
        assert json.loads(req.content) == {"name": "stripe", "maxEvents": 100}
        assert out["httpUrl"] == "https://in.devhelm.io/tok"
        assert "events" not in out

    def test_wait_for_webhook_event(self) -> None:
        client, rec = _sdk(lambda r: _ok({"event": _EVENT_DTO}))
        out = _call(
            "webhook_inboxes",
            client,
            "wait_for_webhook_event",
            {"inbox_id": INBOX_ID, "wait_s": 90, "method": "POST"},
        )
        body = json.loads(rec.requests[0].content)
        assert rec.requests[0].url.path == f"/api/v1/webhook/inboxes/{INBOX_ID}/wait"
        assert body["timeoutMs"] == 25_000
        assert body["http"] == {"method": "POST"}
        assert out["body"] == '{"ok":true}'

    def test_list_webhook_events(self) -> None:
        client, rec = _sdk(
            lambda r: _ok({"data": [_EVENT_DTO], "nextCursor": None, "hasMore": False})
        )
        out = _call(
            "webhook_inboxes",
            client,
            "list_webhook_events",
            {"inbox_id": INBOX_ID, "limit": 5},
        )
        assert rec.requests[0].url.path == f"/api/v1/webhook/inboxes/{INBOX_ID}/events"
        assert rec.requests[0].url.params["limit"] == "5"
        assert out["data"][0]["id"] == EVENT_ID

    def test_get_latest_webhook_event_reads_full_body(self) -> None:
        def handler(r: httpx.Request) -> httpx.Response:
            if r.url.path.endswith(f"/events/{EVENT_ID}"):
                return _ok({"data": dict(_EVENT_DTO, body="z" * (MAX_TEXT_BYTES + 1))})
            return _ok(
                {
                    "data": [dict(_EVENT_DTO, body=None)],
                    "nextCursor": None,
                    "hasMore": False,
                }
            )

        client, rec = _sdk(handler)
        out = _call(
            "webhook_inboxes",
            client,
            "get_latest_webhook_event",
            {"inbox_id": INBOX_ID},
        )
        assert len(rec.requests) == 2
        assert len(out["event"]["body"]) == MAX_TEXT_BYTES
        assert out["event"]["bodyTruncated"] is True

    def test_activity_skips_empty_ids(self) -> None:
        client, rec = _sdk(lambda r: _ok({"data": []}))
        _call(
            "webhook_inboxes", client, "list_webhook_inbox_activity", {"inbox_ids": []}
        )
        assert rec.requests == []
