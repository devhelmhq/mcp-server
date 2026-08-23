"""SDK-call tests for status-page maintenance MCP tools.

Tools delegate to ``client.status_pages.maintenance`` (sdk-python >= 1.7).
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

from devhelm_mcp.server import mcp

_PAGE_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_WINDOW_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

_SAMPLE_WINDOW: dict[str, Any] = {
    "id": _WINDOW_ID,
    "statusPageId": _PAGE_ID,
    "title": "Database upgrade",
    "status": "INVESTIGATING",
    "impact": "MINOR",
    "scheduled": True,
    "scheduledFor": "2026-08-24T02:00:00Z",
    "autoResolve": False,
}


def _call_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    return asyncio.run(mcp.call_tool(tool_name, arguments))


def _stub_sdk_client() -> MagicMock:
    mock = MagicMock()
    mock.status_pages.maintenance.list.return_value = MagicMock(
        data=[_SAMPLE_WINDOW], has_next=False
    )
    mock.status_pages.maintenance.get.return_value = _SAMPLE_WINDOW
    mock.status_pages.maintenance.create.return_value = _SAMPLE_WINDOW
    mock.status_pages.maintenance.update.return_value = _SAMPLE_WINDOW
    mock.status_pages.maintenance.post_update.return_value = _SAMPLE_WINDOW
    mock.status_pages.maintenance.publish.return_value = _SAMPLE_WINDOW
    mock.status_pages.maintenance.dismiss.return_value = None
    mock.status_pages.maintenance.delete.return_value = None
    return mock


class TestStatusPageMaintenanceSdkCalls:
    def test_create_forwards_payload(self) -> None:
        client = _stub_sdk_client()
        with patch("devhelm_mcp.tools.status_pages.get_client", return_value=client):
            _call_tool(
                "create_status_page_maintenance",
                {
                    "page_id": _PAGE_ID,
                    "body": {
                        "title": "Database upgrade",
                        "impact": "MINOR",
                        "body": "Upgrading primary.",
                        "scheduledFor": "2026-08-24T02:00:00Z",
                    },
                },
            )
        client.status_pages.maintenance.create.assert_called_once()
        args = client.status_pages.maintenance.create.call_args.args
        assert args[0] == _PAGE_ID
        assert args[1]["title"] == "Database upgrade"
        assert args[1]["scheduledFor"].isoformat().startswith("2026-08-24T02:00:00")

    def test_update_forwards_schedule(self) -> None:
        client = _stub_sdk_client()
        with patch("devhelm_mcp.tools.status_pages.get_client", return_value=client):
            _call_tool(
                "update_status_page_maintenance",
                {
                    "page_id": _PAGE_ID,
                    "window_id": _WINDOW_ID,
                    "body": {"scheduledFor": "2026-08-24T03:00:00Z"},
                },
            )
        args = client.status_pages.maintenance.update.call_args.args
        assert args[0] == _PAGE_ID
        assert args[1] == _WINDOW_ID
        assert args[2]["scheduledFor"].isoformat().startswith("2026-08-24T03:00:00")

    def test_post_update_forwards_body(self) -> None:
        client = _stub_sdk_client()
        with patch("devhelm_mcp.tools.status_pages.get_client", return_value=client):
            _call_tool(
                "post_status_page_maintenance_update",
                {
                    "page_id": _PAGE_ID,
                    "window_id": _WINDOW_ID,
                    "body": {"status": "MONITORING", "body": "Halfway."},
                },
            )
        client.status_pages.maintenance.post_update.assert_called_once()

    def test_get_publish_dismiss_delete(self) -> None:
        client = _stub_sdk_client()
        with patch("devhelm_mcp.tools.status_pages.get_client", return_value=client):
            _call_tool(
                "get_status_page_maintenance",
                {"page_id": _PAGE_ID, "window_id": _WINDOW_ID},
            )
            _call_tool(
                "publish_status_page_maintenance",
                {"page_id": _PAGE_ID, "window_id": _WINDOW_ID},
            )
            _call_tool(
                "dismiss_status_page_maintenance",
                {"page_id": _PAGE_ID, "window_id": _WINDOW_ID},
            )
            _call_tool(
                "delete_status_page_maintenance",
                {"page_id": _PAGE_ID, "window_id": _WINDOW_ID},
            )
        client.status_pages.maintenance.get.assert_called_once_with(
            _PAGE_ID, _WINDOW_ID
        )
        client.status_pages.maintenance.publish.assert_called_once_with(
            _PAGE_ID, _WINDOW_ID
        )
        client.status_pages.maintenance.dismiss.assert_called_once_with(
            _PAGE_ID, _WINDOW_ID
        )
        client.status_pages.maintenance.delete.assert_called_once_with(
            _PAGE_ID, _WINDOW_ID
        )
