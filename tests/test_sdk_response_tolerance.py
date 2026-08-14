"""MCP inherits sdk-python's response-decoder tolerance (Postel's Law).

Published MCP 1.4.0 wrapped sdk-python 1.4.0, whose response models used
``extra='forbid'``. Additive API fields (``StatusPageDto.openIncident``,
``StatusPageComponentDto.serviceSubscriptionId``, subscriber ``channel``)
then crashed every matching tool with ``extra_forbidden``.

This pins the floor: the installed SDK's status-page response DTOs must
ignore unknown keys. Request models stay strict.
"""

from __future__ import annotations

from devhelm._generated import (
    CreateStatusPageRequest,
    StatusPageComponentDto,
    StatusPageDto,
    StatusPageSubscriberDto,
)


def test_status_page_response_dtos_ignore_unknown_fields() -> None:
    for model in (StatusPageDto, StatusPageComponentDto, StatusPageSubscriberDto):
        assert model.model_config.get("extra") == "ignore", model.__name__


def test_status_page_request_models_still_forbid_unknown_fields() -> None:
    assert CreateStatusPageRequest.model_config.get("extra") == "forbid"
