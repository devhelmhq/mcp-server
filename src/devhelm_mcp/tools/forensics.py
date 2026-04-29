"""Forensic tools — audit trails for detection: incident timelines, check
traces, policy snapshots, rule evaluations, and state transitions.

Backed by the event-sourced forensic model
(cowork/design/046-detection-forensic-model.md) — every detection outcome
is recorded as an immutable row, and these tools expose the read side to
AI agents that need to explain why an incident fired or replay a
detection decision.
"""

from __future__ import annotations

from devhelm import DevhelmError
from fastmcp import FastMCP

from devhelm_mcp.client import (
    ToolResult,
    format_error,
    get_client,
    serialize,
)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def get_incident_timeline(api_token: str, incident_id: str) -> ToolResult:
        """Full forensic timeline for an incident.

        Returns every recorded state transition for the incident, the
        rule evaluations that caused each triggering transition, and the
        policy snapshot in effect at the time.

        Use this to explain why an incident was declared/confirmed/resolved,
        or to audit a past detection decision.
        """
        try:
            return serialize(
                get_client(api_token).forensics.incident_timeline(incident_id)
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_check_trace(api_token: str, check_id: str) -> ToolResult:
        """Everything the detection engine recorded for a single check.

        Includes the rule evaluations produced for this check_id, the
        state transitions that fired (if any), and the policy snapshot
        active at evaluation time. Use when a user references a specific
        check execution ID (e.g. from a support ticket or webhook).
        """
        try:
            return serialize(get_client(api_token).forensics.check_trace(check_id))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def get_policy_snapshot(api_token: str, hash_hex: str) -> ToolResult:
        """Fetch a policy snapshot by its content-addressed SHA-256 hash.

        Useful for inspecting the exact detection policy that was active
        when a specific evaluation or transition happened — the hash is
        stable, so historical data keeps pointing at the right policy
        even if the monitor has been edited since.
        """
        try:
            return serialize(get_client(api_token).forensics.policy_snapshot(hash_hex))
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def list_monitor_rule_evaluations(
        api_token: str,
        monitor_id: str,
        rule_type: str | None = None,
        region: str | None = None,
        only_matched: bool | None = None,
        from_: str | None = None,
        to: str | None = None,
        page: int = 0,
        size: int = 50,
    ) -> ToolResult:
        """List rule evaluations produced for a monitor (paginated).

        Filters:
          - rule_type: e.g. "consecutive_failures", "latency_threshold"
          - region: probe region, e.g. "us-east"
          - only_matched: if True, return only evaluations that fired
          - from_/to: ISO-8601 datetime bounds

        Use to answer "which rules fired on monitor X in the last hour?".
        """
        try:
            result = get_client(api_token).forensics.monitor_rule_evaluations(
                monitor_id,
                rule_type=rule_type,
                region=region,
                only_matched=only_matched,
                from_=from_,
                to=to,
                page=page,
                size=size,
            )
            return serialize(
                {
                    "data": result.data,
                    "hasNext": result.has_next,
                    "hasPrev": result.has_prev,
                    "totalElements": result.total_elements,
                    "totalPages": result.total_pages,
                }
            )
        except DevhelmError as e:
            return format_error(e)

    @mcp.tool()
    def list_monitor_transitions(
        api_token: str,
        monitor_id: str,
        from_: str | None = None,
        to: str | None = None,
        page: int = 0,
        size: int = 50,
    ) -> ToolResult:
        """List state transitions recorded for a monitor (paginated).

        A transition captures every WATCHING→TRIGGERED→CONFIRMED→RESOLVED
        edge the detection engine walked. Includes transitions that
        occurred before an incident was declared (incident_id = null).

        Use to reconstruct the full reliability history of a monitor.
        """
        try:
            result = get_client(api_token).forensics.monitor_transitions(
                monitor_id,
                from_=from_,
                to=to,
                page=page,
                size=size,
            )
            return serialize(
                {
                    "data": result.data,
                    "hasNext": result.has_next,
                    "hasPrev": result.has_prev,
                    "totalElements": result.total_elements,
                    "totalPages": result.total_pages,
                }
            )
        except DevhelmError as e:
            return format_error(e)
