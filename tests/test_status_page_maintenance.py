"""HTTP-path tests for status-page maintenance MCP tools.

The published ``devhelm`` SDK does not yet expose
``status_pages.maintenance``; these tools call ``api_get`` / ``api_post``
/ ``api_put`` / ``api_delete`` on the SDK HTTP layer. Patch those
helpers in the tool module and assert path + body shape.

Create / update / post-update must hand a Pydantic model to ``api_post``
/ ``api_put``. Raw dicts are rejected by ``_serialize_body``.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

from pydantic import BaseModel

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
    "scheduledUntil": "2026-08-24T04:00:00Z",
    "autoResolve": False,
    "startedAt": "2026-08-24T02:00:00Z",
    "createdAt": "2026-08-23T10:00:00Z",
    "updatedAt": "2026-08-23T10:00:00Z",
}

_SAMPLE_ENVELOPE: dict[str, Any] = {"data": _SAMPLE_WINDOW}


def _call_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    return asyncio.run(mcp.call_tool(tool_name, arguments))


def _stub_sdk_client() -> MagicMock:
    mock = MagicMock()
    mock.status_pages._client = MagicMock(name="httpx.Client")
    return mock


def _wire_body(captured_body: Any) -> dict[str, Any]:
    assert isinstance(captured_body, BaseModel), (
        "create/update/post-update tools must hand a validated Pydantic "
        "model to api_post/api_put, not a raw dict (raw dicts are "
        "rejected by the SDK's _serialize_body)."
    )
    return captured_body.model_dump(mode="json", by_alias=True, exclude_none=True)


class TestCreateStatusPageMaintenanceHttpContract:
    def test_posts_pydantic_body_to_maintenance_collection(self) -> None:
        captured: dict[str, Any] = {}

        def fake_api_post(client: Any, path: str, body: Any) -> dict[str, Any]:
            captured["path"] = path
            captured["body"] = body
            return _SAMPLE_ENVELOPE

        with (
            patch(
                "devhelm_mcp.tools.status_pages.get_client",
                return_value=_stub_sdk_client(),
            ),
            patch(
                "devhelm_mcp.tools.status_pages.api_post",
                side_effect=fake_api_post,
            ),
        ):
            _call_tool(
                "create_status_page_maintenance",
                {
                    "page_id": _PAGE_ID,
                    "body": {
                        "title": "Database upgrade",
                        "impact": "MINOR",
                        "body": "Upgrading primary.",
                        "scheduledFor": "2026-08-24T02:00:00Z",
                        "scheduledUntil": "2026-08-24T04:00:00Z",
                        "autoResolve": True,
                    },
                },
            )

        assert captured["path"] == f"/api/v1/status-pages/{_PAGE_ID}/maintenance"
        wire = _wire_body(captured["body"])
        assert wire["title"] == "Database upgrade"
        assert wire["impact"] == "MINOR"
        assert wire["body"] == "Upgrading primary."
        assert wire["scheduledFor"] == "2026-08-24T02:00:00Z"
        assert wire["scheduledUntil"] == "2026-08-24T04:00:00Z"
        assert wire["autoResolve"] is True


class TestUpdateStatusPageMaintenanceHttpContract:
    def test_puts_pydantic_body_including_schedule(self) -> None:
        captured: dict[str, Any] = {}

        def fake_api_put(client: Any, path: str, body: Any) -> dict[str, Any]:
            captured["path"] = path
            captured["body"] = body
            return _SAMPLE_ENVELOPE

        with (
            patch(
                "devhelm_mcp.tools.status_pages.get_client",
                return_value=_stub_sdk_client(),
            ),
            patch(
                "devhelm_mcp.tools.status_pages.api_put",
                side_effect=fake_api_put,
            ),
        ):
            _call_tool(
                "update_status_page_maintenance",
                {
                    "page_id": _PAGE_ID,
                    "window_id": _WINDOW_ID,
                    "body": {
                        "title": "Extended window",
                        "scheduledFor": "2026-08-24T03:00:00Z",
                    },
                },
            )

        assert (
            captured["path"]
            == f"/api/v1/status-pages/{_PAGE_ID}/maintenance/{_WINDOW_ID}"
        )
        wire = _wire_body(captured["body"])
        assert wire["title"] == "Extended window"
        assert wire["scheduledFor"] == "2026-08-24T03:00:00Z"


class TestPostStatusPageMaintenanceUpdateHttpContract:
    def test_posts_pydantic_body_to_updates(self) -> None:
        captured: dict[str, Any] = {}

        def fake_api_post(client: Any, path: str, body: Any) -> dict[str, Any]:
            captured["path"] = path
            captured["body"] = body
            return _SAMPLE_ENVELOPE

        with (
            patch(
                "devhelm_mcp.tools.status_pages.get_client",
                return_value=_stub_sdk_client(),
            ),
            patch(
                "devhelm_mcp.tools.status_pages.api_post",
                side_effect=fake_api_post,
            ),
        ):
            _call_tool(
                "post_status_page_maintenance_update",
                {
                    "page_id": _PAGE_ID,
                    "window_id": _WINDOW_ID,
                    "body": {
                        "status": "MONITORING",
                        "body": "Halfway through the upgrade.",
                    },
                },
            )

        assert (
            captured["path"]
            == f"/api/v1/status-pages/{_PAGE_ID}/maintenance/{_WINDOW_ID}/updates"
        )
        wire = _wire_body(captured["body"])
        assert wire["status"] == "MONITORING"
        assert wire["body"] == "Halfway through the upgrade."


class TestGetPublishDismissDeleteHttpContract:
    def test_get_path(self) -> None:
        captured: dict[str, Any] = {}

        def fake_api_get(client: Any, path: str, params: Any = None) -> dict[str, Any]:
            captured["path"] = path
            return _SAMPLE_ENVELOPE

        with (
            patch(
                "devhelm_mcp.tools.status_pages.get_client",
                return_value=_stub_sdk_client(),
            ),
            patch(
                "devhelm_mcp.tools.status_pages.api_get",
                side_effect=fake_api_get,
            ),
        ):
            _call_tool(
                "get_status_page_maintenance",
                {"page_id": _PAGE_ID, "window_id": _WINDOW_ID},
            )

        assert (
            captured["path"]
            == f"/api/v1/status-pages/{_PAGE_ID}/maintenance/{_WINDOW_ID}"
        )

    def test_publish_path(self) -> None:
        captured: dict[str, Any] = {}

        def fake_api_post(client: Any, path: str, body: Any = None) -> dict[str, Any]:
            captured["path"] = path
            return _SAMPLE_ENVELOPE

        with (
            patch(
                "devhelm_mcp.tools.status_pages.get_client",
                return_value=_stub_sdk_client(),
            ),
            patch(
                "devhelm_mcp.tools.status_pages.api_post",
                side_effect=fake_api_post,
            ),
        ):
            _call_tool(
                "publish_status_page_maintenance",
                {"page_id": _PAGE_ID, "window_id": _WINDOW_ID},
            )

        assert (
            captured["path"]
            == f"/api/v1/status-pages/{_PAGE_ID}/maintenance/{_WINDOW_ID}/publish"
        )

    def test_dismiss_path(self) -> None:
        captured: dict[str, Any] = {}

        def fake_api_post(client: Any, path: str, body: Any = None) -> dict[str, Any]:
            captured["path"] = path
            return _SAMPLE_ENVELOPE

        with (
            patch(
                "devhelm_mcp.tools.status_pages.get_client",
                return_value=_stub_sdk_client(),
            ),
            patch(
                "devhelm_mcp.tools.status_pages.api_post",
                side_effect=fake_api_post,
            ),
        ):
            _call_tool(
                "dismiss_status_page_maintenance",
                {"page_id": _PAGE_ID, "window_id": _WINDOW_ID},
            )

        assert (
            captured["path"]
            == f"/api/v1/status-pages/{_PAGE_ID}/maintenance/{_WINDOW_ID}/dismiss"
        )

    def test_delete_path(self) -> None:
        captured: dict[str, Any] = {}

        def fake_api_delete(client: Any, path: str) -> None:
            captured["path"] = path

        with (
            patch(
                "devhelm_mcp.tools.status_pages.get_client",
                return_value=_stub_sdk_client(),
            ),
            patch(
                "devhelm_mcp.tools.status_pages.api_delete",
                side_effect=fake_api_delete,
            ),
        ):
            _call_tool(
                "delete_status_page_maintenance",
                {"page_id": _PAGE_ID, "window_id": _WINDOW_ID},
            )

        assert (
            captured["path"]
            == f"/api/v1/status-pages/{_PAGE_ID}/maintenance/{_WINDOW_ID}"
        )
