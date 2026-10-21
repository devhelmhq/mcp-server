"""Email Testing tools — capture mail sent to test addresses.

Agent flow: ``create_email_address`` → trigger the signup / reset in the app
under test → ``wait_for_email`` (bounded) or poll ``get_latest_email`` →
read ``list_email_otp_codes`` / ``list_email_links``.

Not offered here: deleting messages, clearing an address and deleting a
domain (MCP deletes need a confirmation step the API does not have yet),
raw RFC822 and attachment downloads (binary; MCP never inlines them), and the
local-part wait route (``wait_for_email`` takes the full address).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from devhelm import DevhelmError
from devhelm.resources.email import Address, Message
from fastmcp import FastMCP

from devhelm_mcp.client import ToolResult, get_client, raise_tool_error
from devhelm_mcp.tools._inbound import (
    CREATE,
    READ_ONLY,
    UPDATE,
    WAIT,
    as_dict,
    bound_limit,
    cap_fields,
    cap_text,
    plain,
    split_address,
    wait_ms,
)


def _address(api_token: str | None, to: str) -> Address:
    local, domain = split_address(to)
    client = get_client(api_token)
    return Address(client.email, address=to, domain=domain, local_part=local)


def _message(message: Message) -> dict[str, Any]:
    data = as_dict(message)
    return cap_fields(data, ("text", "html"), "bodyTruncated")


def _message_page(
    address: Address, limit: int | None, cursor: str | None, q: str | None
) -> dict[str, Any]:
    page = address.messages.list(cursor=cursor, limit=bound_limit(limit), q=q)
    return {
        "data": [_message(row) for row in page.data],
        "nextCursor": page.next_cursor,
        "hasMore": page.has_more,
    }


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=CREATE)
    def create_email_address(
        label: str | None = None,
        domain: str | None = None,
        api_token: str | None = None,
    ) -> ToolResult:
        """Create a fresh test email address to receive mail.

        Uses the workspace's DevHelm-assigned domain (allocated on first use)
        unless ``domain`` names a verified custom domain. ``label`` prefixes
        the random local part. Returns ``email``, ``domain`` and ``localPart``.
        """
        try:
            address = get_client(api_token).email.address(label=label, domain=domain)
            return {
                "email": address.email,
                "domain": address.domain,
                "localPart": address.local_part,
            }
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=WAIT)
    def wait_for_email(
        to: str,
        wait_s: int = 25,
        subject_contains: str | None = None,
        received_after: str | None = None,
        api_token: str | None = None,
    ) -> ToolResult:
        """Wait up to ``wait_s`` seconds (max 25) for mail to a full address.

        Returns the oldest matching message, with extracted ``otp`` and
        ``links``. On timeout the tool errors; call it again or poll
        ``get_latest_email``. ``received_after`` is an ISO 8601 timestamp.
        """
        try:
            after = datetime.fromisoformat(received_after) if received_after else None
            message = get_client(api_token).email.wait(
                to=to,
                timeout_ms=wait_ms(wait_s),
                received_after=after,
                subject_contains=subject_contains,
            )
            return _message(message)
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=READ_ONLY)
    def list_email_messages(
        to: str,
        limit: int | None = None,
        cursor: str | None = None,
        q: str | None = None,
        api_token: str | None = None,
    ) -> ToolResult:
        """List messages received at a full address, newest first.

        ``limit`` defaults to 20 (max 50); pass ``nextCursor`` back as
        ``cursor`` for the next page. ``q`` filters on subject and sender.
        """
        try:
            return _message_page(_address(api_token, to), limit, cursor, q)
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=READ_ONLY)
    def get_latest_email(to: str, api_token: str | None = None) -> ToolResult:
        """Get the newest message at a full address without waiting.

        Returns ``{"message": null}`` when nothing has arrived yet.
        """
        try:
            page = _address(api_token, to).messages.list(limit=1)
            return {"message": _message(page.data[0]) if page.data else None}
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=READ_ONLY)
    def get_email_message(
        to: str, message_id: str, api_token: str | None = None
    ) -> ToolResult:
        """Get one captured message (headers, text, html, otp, links)."""
        try:
            return _message(_address(api_token, to).messages.get(message_id))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=READ_ONLY)
    def get_email_message_source(
        to: str, message_id: str, api_token: str | None = None
    ) -> ToolResult:
        """Get the stored message source as text (capped at 64 KB)."""
        try:
            source = _address(api_token, to).messages.get(message_id).source()
            text, cut = cap_text(source.source)
            return {"source": text, "truncated": source.truncated or cut}
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=READ_ONLY)
    def list_email_otp_codes(
        to: str, message_id: str, api_token: str | None = None
    ) -> ToolResult:
        """List one-time codes extracted from a message."""
        try:
            message = _address(api_token, to).messages.get(message_id)
            return [plain(code) for code in message.list_otp()]
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=READ_ONLY)
    def list_email_links(
        to: str, message_id: str, api_token: str | None = None
    ) -> ToolResult:
        """List links extracted from a message (verification, reset, ...)."""
        try:
            message = _address(api_token, to).messages.get(message_id)
            return [plain(link) for link in message.list_links()]
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=CREATE)
    def inject_email_message(
        to: str,
        from_address: str,
        subject: str | None = None,
        text: str | None = None,
        html: str | None = None,
        api_token: str | None = None,
    ) -> ToolResult:
        """Deliver a test message to an address without SMTP.

        Uses the same capture path as real mail, so waits and extraction
        behave the same. Returns ``eventId``, ``receivedAt`` and ``inbox``.
        """
        try:
            result = _address(api_token, to).receive(
                from_=from_address, subject=subject, text=text, html=html
            )
            return as_dict(result)
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=READ_ONLY)
    def list_email_domains(
        search: str | None = None, api_token: str | None = None
    ) -> ToolResult:
        """List email testing domains (assigned and custom) in the workspace."""
        try:
            domains = get_client(api_token).email.domains.list(search=search)
            return [plain(domain) for domain in domains]
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=READ_ONLY)
    def get_email_domain(name: str, api_token: str | None = None) -> ToolResult:
        """Get an email testing domain, including the DNS records to set."""
        try:
            return as_dict(get_client(api_token).email.domains.get(name))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=CREATE)
    def create_email_domain(
        name: str | None = None, api_token: str | None = None
    ) -> ToolResult:
        """Create an email testing domain.

        Omit ``name`` for the DevHelm-assigned domain; pass a hostname you
        control for a custom domain, then add the returned DNS records and
        call ``verify_email_domain``.
        """
        try:
            return as_dict(get_client(api_token).email.domains.create(name=name))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=UPDATE)
    def update_email_domain(
        name: str,
        status: Literal["active", "disabled"],
        api_token: str | None = None,
    ) -> ToolResult:
        """Enable (``active``) or disable (``disabled``) mail capture on a domain."""
        try:
            domain = get_client(api_token).email.domains.update(
                name, {"status": status}
            )
            return as_dict(domain)
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=UPDATE)
    def verify_email_domain(name: str, api_token: str | None = None) -> ToolResult:
        """Re-check the TXT and MX records of a custom email testing domain."""
        try:
            return as_dict(get_client(api_token).email.domains.verify(name))
        except DevhelmError as e:
            raise_tool_error(e)

    @mcp.tool(annotations=READ_ONLY)
    def list_email_domain_activity(
        domain_ids: list[str], api_token: str | None = None
    ) -> ToolResult:
        """Hourly received-message counts for the last 24 h, per domain ID."""
        try:
            rows = get_client(api_token).email.domains.activity(domain_ids)
            return [plain(row) for row in rows]
        except DevhelmError as e:
            raise_tool_error(e)
