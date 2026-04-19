"""Negative validation tests for MCP tool input validation.

Verifies that each create/update tool rejects invalid input through
Pydantic model validation before the request reaches the API.
"""

from __future__ import annotations

from typing import Any

import pytest
from devhelm._generated import AddResourceGroupMemberRequest
from devhelm._generated import ResolveIncidentRequest

from devhelm_mcp.tools.status_pages import PublishStatusPageIncidentRequest
from devhelm.types import (
    AcquireDeployLockRequest,
    AddCustomDomainRequest,
    AdminAddSubscriberRequest,
    CreateAlertChannelRequest,
    CreateApiKeyRequest,
    CreateEnvironmentRequest,
    CreateManualIncidentRequest,
    CreateMonitorRequest,
    CreateNotificationPolicyRequest,
    CreateResourceGroupRequest,
    CreateSecretRequest,
    CreateStatusPageComponentGroupRequest,
    CreateStatusPageComponentRequest,
    CreateStatusPageIncidentRequest,
    CreateStatusPageIncidentUpdateRequest,
    CreateStatusPageRequest,
    CreateTagRequest,
    CreateWebhookEndpointRequest,
    UpdateAlertChannelRequest,
    UpdateEnvironmentRequest,
    UpdateMonitorRequest,
    UpdateNotificationPolicyRequest,
    UpdateResourceGroupRequest,
    UpdateSecretRequest,
    UpdateStatusPageComponentGroupRequest,
    UpdateStatusPageComponentRequest,
    UpdateStatusPageIncidentRequest,
    UpdateStatusPageRequest,
    UpdateTagRequest,
    UpdateWebhookEndpointRequest,
)
from pydantic import ValidationError

from devhelm_mcp.client import validate_body


def _assert_rejects(body: dict[str, Any], model: type) -> ValidationError:
    """Assert that validate_body raises ValidationError and return it."""
    with pytest.raises(ValidationError) as exc_info:
        validate_body(body, model)
    return exc_info.value


def _error_fields(err: ValidationError) -> set[str]:
    """Extract the top-level field names from a ValidationError."""
    fields: set[str] = set()
    for e in err.errors():
        if e["loc"]:
            fields.add(str(e["loc"][0]))
    return fields


# ---------------------------------------------------------------------------
# Monitors
# ---------------------------------------------------------------------------


class TestCreateMonitorValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, CreateMonitorRequest)
        missing = _error_fields(err)
        assert "name" in missing
        assert "type" in missing
        assert "config" in missing

    def test_missing_name(self) -> None:
        err = _assert_rejects(
            {
                "type": "HTTP",
                "config": {"url": "https://example.com", "method": "GET"},
                "managedBy": "DASHBOARD",
            },
            CreateMonitorRequest,
        )
        assert "name" in _error_fields(err)

    def test_invalid_type(self) -> None:
        err = _assert_rejects(
            {
                "name": "test",
                "type": "INVALID",
                "config": {"url": "https://example.com", "method": "GET"},
                "managedBy": "DASHBOARD",
            },
            CreateMonitorRequest,
        )
        assert "type" in _error_fields(err)

    def test_missing_config(self) -> None:
        err = _assert_rejects(
            {"name": "test", "type": "HTTP", "managedBy": "DASHBOARD"},
            CreateMonitorRequest,
        )
        assert "config" in _error_fields(err)

    def test_valid_http_monitor(self) -> None:
        validate_body(
            {
                "name": "My HTTP Monitor",
                "type": "HTTP",
                "config": {"url": "https://example.com", "method": "GET"},
                "managedBy": "DASHBOARD",
            },
            CreateMonitorRequest,
        )

    def test_missing_managed_by(self) -> None:
        err = _assert_rejects(
            {
                "name": "test",
                "type": "HTTP",
                "config": {"url": "https://example.com", "method": "GET"},
            },
            CreateMonitorRequest,
        )
        assert "managedBy" in _error_fields(err) or "managed_by" in _error_fields(err)


class TestUpdateMonitorValidation:
    def test_empty_body_rejected(self) -> None:
        err = _assert_rejects({}, UpdateMonitorRequest)
        assert "name" in _error_fields(err)

    def test_invalid_type_value(self) -> None:
        _assert_rejects({"type": "INVALID_TYPE"}, UpdateMonitorRequest)


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------


class TestCreateIncidentValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, CreateManualIncidentRequest)
        missing = _error_fields(err)
        assert "title" in missing
        assert "severity" in missing

    def test_missing_title(self) -> None:
        err = _assert_rejects({"severity": "DOWN"}, CreateManualIncidentRequest)
        assert "title" in _error_fields(err)

    def test_invalid_severity(self) -> None:
        err = _assert_rejects(
            {"title": "Outage", "severity": "CRITICAL"},
            CreateManualIncidentRequest,
        )
        assert "severity" in _error_fields(err)

    def test_empty_title_rejected(self) -> None:
        _assert_rejects(
            {"title": "", "severity": "DOWN"},
            CreateManualIncidentRequest,
        )

    def test_valid_incident(self) -> None:
        validate_body(
            {"title": "API outage", "severity": "DOWN"},
            CreateManualIncidentRequest,
        )


class TestResolveIncidentRequestValidation:
    def test_valid_with_body(self) -> None:
        req = ResolveIncidentRequest(body="Root cause identified and fixed.")
        assert req.body == "Root cause identified and fixed."

    def test_rejects_non_string_body(self) -> None:
        with pytest.raises(ValidationError):
            ResolveIncidentRequest(body=123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Alert Channels
# ---------------------------------------------------------------------------


class TestCreateAlertChannelValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, CreateAlertChannelRequest)
        missing = _error_fields(err)
        assert "name" in missing
        assert "config" in missing

    def test_missing_config(self) -> None:
        err = _assert_rejects({"name": "My Channel"}, CreateAlertChannelRequest)
        assert "config" in _error_fields(err)

    def test_missing_name(self) -> None:
        err = _assert_rejects(
            {"config": {"channelType": "EMAIL", "recipients": ["a@b.com"]}},
            CreateAlertChannelRequest,
        )
        assert "name" in _error_fields(err)

    def test_valid_email_channel(self) -> None:
        validate_body(
            {
                "name": "Email alerts",
                "config": {
                    "channelType": "EMAIL",
                    "recipients": ["team@example.com"],
                },
            },
            CreateAlertChannelRequest,
        )


class TestUpdateAlertChannelValidation:
    def test_empty_body_rejected(self) -> None:
        err = _assert_rejects({}, UpdateAlertChannelRequest)
        missing = _error_fields(err)
        assert "name" in missing
        assert "config" in missing


# ---------------------------------------------------------------------------
# Notification Policies
# ---------------------------------------------------------------------------


class TestCreateNotificationPolicyValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, CreateNotificationPolicyRequest)
        missing = _error_fields(err)
        assert "name" in missing

    def test_missing_escalation(self) -> None:
        err = _assert_rejects(
            {
                "name": "My Policy",
                "matchRules": [],
                "enabled": True,
                "priority": 0,
            },
            CreateNotificationPolicyRequest,
        )
        assert "escalation" in _error_fields(err)

    def test_empty_escalation_steps(self) -> None:
        _assert_rejects(
            {
                "name": "My Policy",
                "matchRules": [],
                "escalation": {"steps": []},
                "enabled": True,
                "priority": 0,
            },
            CreateNotificationPolicyRequest,
        )

    def test_valid_policy(self) -> None:
        validate_body(
            {
                "name": "My Policy",
                "matchRules": [],
                "escalation": {
                    "steps": [
                        {
                            "delayMinutes": 0,
                            "channelIds": ["00000000-0000-0000-0000-000000000001"],
                        }
                    ]
                },
                "enabled": True,
                "priority": 0,
            },
            CreateNotificationPolicyRequest,
        )


class TestUpdateNotificationPolicyValidation:
    def test_empty_body_rejected(self) -> None:
        err = _assert_rejects({}, UpdateNotificationPolicyRequest)
        assert "name" in _error_fields(err)

    def test_invalid_escalation_steps(self) -> None:
        _assert_rejects(
            {"escalation": {"steps": []}},
            UpdateNotificationPolicyRequest,
        )


# ---------------------------------------------------------------------------
# Environments
# ---------------------------------------------------------------------------


class TestCreateEnvironmentValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, CreateEnvironmentRequest)
        missing = _error_fields(err)
        assert "name" in missing
        assert "slug" in missing

    def test_missing_slug(self) -> None:
        err = _assert_rejects({"name": "Production"}, CreateEnvironmentRequest)
        assert "slug" in _error_fields(err)

    def test_invalid_slug_pattern(self) -> None:
        _assert_rejects(
            {"name": "Production", "slug": "UPPER CASE!"},
            CreateEnvironmentRequest,
        )

    def test_valid_environment(self) -> None:
        validate_body(
            {"name": "Production", "slug": "production"},
            CreateEnvironmentRequest,
        )


class TestUpdateEnvironmentValidation:
    def test_empty_body_rejected(self) -> None:
        err = _assert_rejects({}, UpdateEnvironmentRequest)
        assert "name" in _error_fields(err)


# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------


class TestCreateSecretValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, CreateSecretRequest)
        missing = _error_fields(err)
        assert "key" in missing
        assert "value" in missing

    def test_missing_value(self) -> None:
        err = _assert_rejects({"key": "MY_SECRET"}, CreateSecretRequest)
        assert "value" in _error_fields(err)

    def test_missing_key(self) -> None:
        err = _assert_rejects({"value": "secret-value"}, CreateSecretRequest)
        assert "key" in _error_fields(err)

    def test_valid_secret(self) -> None:
        validate_body(
            {"key": "DB_PASSWORD", "value": "super-secret"},
            CreateSecretRequest,
        )


class TestUpdateSecretValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, UpdateSecretRequest)
        assert "value" in _error_fields(err)

    def test_valid_update(self) -> None:
        validate_body({"value": "new-secret-value"}, UpdateSecretRequest)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


class TestCreateTagValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, CreateTagRequest)
        assert "name" in _error_fields(err)

    def test_invalid_color_pattern(self) -> None:
        _assert_rejects(
            {"name": "production", "color": "red"},
            CreateTagRequest,
        )

    def test_valid_tag(self) -> None:
        validate_body({"name": "production"}, CreateTagRequest)

    def test_valid_tag_with_color(self) -> None:
        validate_body({"name": "staging", "color": "#FF5733"}, CreateTagRequest)


class TestUpdateTagValidation:
    def test_empty_body_rejected(self) -> None:
        err = _assert_rejects({}, UpdateTagRequest)
        assert "name" in _error_fields(err)

    def test_invalid_color(self) -> None:
        _assert_rejects({"color": "not-a-color"}, UpdateTagRequest)


# ---------------------------------------------------------------------------
# Resource Groups
# ---------------------------------------------------------------------------


class TestCreateResourceGroupValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, CreateResourceGroupRequest)
        assert "name" in _error_fields(err)

    def test_valid_group(self) -> None:
        validate_body({"name": "API Servers"}, CreateResourceGroupRequest)


class TestUpdateResourceGroupValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, UpdateResourceGroupRequest)
        assert "name" in _error_fields(err)

    def test_valid_update(self) -> None:
        validate_body({"name": "Renamed Group"}, UpdateResourceGroupRequest)


class TestAddResourceGroupMemberValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, AddResourceGroupMemberRequest)
        missing = _error_fields(err)
        assert "memberType" in missing or "member_type" in missing
        assert "memberId" in missing or "member_id" in missing

    def test_invalid_member_type(self) -> None:
        _assert_rejects(
            {
                "memberType": "invalid",
                "memberId": "00000000-0000-0000-0000-000000000001",
            },
            AddResourceGroupMemberRequest,
        )

    def test_invalid_member_id_format(self) -> None:
        _assert_rejects(
            {"memberType": "monitor", "memberId": "not-a-uuid"},
            AddResourceGroupMemberRequest,
        )

    def test_valid_member(self) -> None:
        validate_body(
            {
                "memberType": "monitor",
                "memberId": "00000000-0000-0000-0000-000000000001",
            },
            AddResourceGroupMemberRequest,
        )


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------


class TestCreateWebhookValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, CreateWebhookEndpointRequest)
        assert "url" in _error_fields(err)

    def test_missing_subscribed_events(self) -> None:
        err = _assert_rejects(
            {"url": "https://hooks.example.com/webhook"},
            CreateWebhookEndpointRequest,
        )
        fields = _error_fields(err)
        assert "subscribedEvents" in fields or "subscribed_events" in fields

    def test_valid_webhook(self) -> None:
        validate_body(
            {
                "url": "https://hooks.example.com/webhook",
                "subscribedEvents": ["monitor.created"],
            },
            CreateWebhookEndpointRequest,
        )


class TestUpdateWebhookValidation:
    def test_empty_body_rejected(self) -> None:
        err = _assert_rejects({}, UpdateWebhookEndpointRequest)
        assert "url" in _error_fields(err)


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------


class TestCreateApiKeyValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, CreateApiKeyRequest)
        assert "name" in _error_fields(err)

    def test_valid_api_key(self) -> None:
        validate_body({"name": "CI Key"}, CreateApiKeyRequest)


# ---------------------------------------------------------------------------
# Deploy Lock
# ---------------------------------------------------------------------------


class TestAcquireDeployLockValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, AcquireDeployLockRequest)
        assert "lockedBy" in _error_fields(err) or "locked_by" in _error_fields(err)

    def test_empty_locked_by(self) -> None:
        _assert_rejects({"lockedBy": ""}, AcquireDeployLockRequest)

    def test_valid_lock(self) -> None:
        validate_body({"lockedBy": "ci-deploy-job-123"}, AcquireDeployLockRequest)


# ---------------------------------------------------------------------------
# Status Pages — page CRUD
# ---------------------------------------------------------------------------


class TestCreateStatusPageValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, CreateStatusPageRequest)
        missing = _error_fields(err)
        assert "name" in missing
        assert "slug" in missing

    def test_missing_slug(self) -> None:
        err = _assert_rejects({"name": "My Page"}, CreateStatusPageRequest)
        assert "slug" in _error_fields(err)

    def test_slug_too_short(self) -> None:
        _assert_rejects({"name": "My Page", "slug": "ab"}, CreateStatusPageRequest)

    def test_invalid_slug_uppercase(self) -> None:
        _assert_rejects(
            {"name": "My Page", "slug": "My-Page"},
            CreateStatusPageRequest,
        )

    def test_valid_page(self) -> None:
        validate_body(
            {"name": "My Status Page", "slug": "my-status-page"},
            CreateStatusPageRequest,
        )


class TestUpdateStatusPageValidation:
    def test_empty_body_rejected(self) -> None:
        err = _assert_rejects({}, UpdateStatusPageRequest)
        assert "name" in _error_fields(err)

    def test_invalid_visibility(self) -> None:
        _assert_rejects({"visibility": "INVALID"}, UpdateStatusPageRequest)


# ---------------------------------------------------------------------------
# Status Pages — components
# ---------------------------------------------------------------------------


class TestCreateStatusPageComponentValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, CreateStatusPageComponentRequest)
        missing = _error_fields(err)
        assert "name" in missing
        assert "type" in missing

    def test_missing_type(self) -> None:
        err = _assert_rejects({"name": "API"}, CreateStatusPageComponentRequest)
        assert "type" in _error_fields(err)

    def test_invalid_type(self) -> None:
        _assert_rejects(
            {"name": "API", "type": "INVALID"},
            CreateStatusPageComponentRequest,
        )

    def test_valid_static_component(self) -> None:
        validate_body(
            {"name": "API", "type": "STATIC"},
            CreateStatusPageComponentRequest,
        )


class TestUpdateStatusPageComponentValidation:
    def test_empty_body_rejected(self) -> None:
        err = _assert_rejects({}, UpdateStatusPageComponentRequest)
        assert "name" in _error_fields(err)


# ---------------------------------------------------------------------------
# Status Pages — component groups
# ---------------------------------------------------------------------------


class TestCreateStatusPageGroupValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, CreateStatusPageComponentGroupRequest)
        assert "name" in _error_fields(err)

    def test_valid_group(self) -> None:
        validate_body({"name": "Infrastructure"}, CreateStatusPageComponentGroupRequest)


class TestUpdateStatusPageGroupValidation:
    def test_empty_body_rejected(self) -> None:
        err = _assert_rejects({}, UpdateStatusPageComponentGroupRequest)
        assert "name" in _error_fields(err)


# ---------------------------------------------------------------------------
# Status Pages — incidents
# ---------------------------------------------------------------------------


class TestCreateStatusPageIncidentValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, CreateStatusPageIncidentRequest)
        missing = _error_fields(err)
        assert "title" in missing
        assert "impact" in missing
        assert "body" in missing

    def test_missing_impact(self) -> None:
        err = _assert_rejects(
            {"title": "Outage", "body": "We are investigating"},
            CreateStatusPageIncidentRequest,
        )
        assert "impact" in _error_fields(err)

    def test_invalid_impact(self) -> None:
        _assert_rejects(
            {"title": "Outage", "impact": "INVALID", "body": "desc"},
            CreateStatusPageIncidentRequest,
        )

    def test_empty_body_text(self) -> None:
        _assert_rejects(
            {"title": "Outage", "impact": "MAJOR", "body": ""},
            CreateStatusPageIncidentRequest,
        )

    def test_valid_incident(self) -> None:
        validate_body(
            {"title": "API Degradation", "impact": "MINOR", "body": "Investigating."},
            CreateStatusPageIncidentRequest,
        )


class TestUpdateStatusPageIncidentValidation:
    def test_empty_body_rejected(self) -> None:
        err = _assert_rejects({}, UpdateStatusPageIncidentRequest)
        assert "title" in _error_fields(err)

    def test_invalid_impact(self) -> None:
        _assert_rejects({"impact": "INVALID"}, UpdateStatusPageIncidentRequest)


# ---------------------------------------------------------------------------
# Status Pages — publish incident
# ---------------------------------------------------------------------------


class TestPublishStatusPageIncidentValidation:
    def test_valid_empty_body_skips_validation(self) -> None:
        """None body is fine — publish with defaults."""
        pass

    def test_valid_with_overrides(self) -> None:
        validate_body(
            {"title": "Updated Title", "impact": "MAJOR"},
            PublishStatusPageIncidentRequest,
        )

    def test_invalid_impact(self) -> None:
        _assert_rejects(
            {"impact": "INVALID"},
            PublishStatusPageIncidentRequest,
        )

    def test_invalid_status(self) -> None:
        _assert_rejects(
            {"status": "INVALID"},
            PublishStatusPageIncidentRequest,
        )

    def test_title_too_long(self) -> None:
        _assert_rejects(
            {"title": "x" * 501},
            PublishStatusPageIncidentRequest,
        )

    def test_valid_all_fields(self) -> None:
        validate_body(
            {
                "title": "Incident Title",
                "impact": "CRITICAL",
                "status": "INVESTIGATING",
                "body": "Initial update",
                "notifySubscribers": True,
            },
            PublishStatusPageIncidentRequest,
        )

    def test_rejects_non_string_body(self) -> None:
        with pytest.raises(ValidationError):
            PublishStatusPageIncidentRequest(body=123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Status Pages — incident updates
# ---------------------------------------------------------------------------


class TestCreateStatusPageIncidentUpdateValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, CreateStatusPageIncidentUpdateRequest)
        missing = _error_fields(err)
        assert "status" in missing
        assert "body" in missing

    def test_missing_status(self) -> None:
        err = _assert_rejects(
            {"body": "We are monitoring the fix."},
            CreateStatusPageIncidentUpdateRequest,
        )
        assert "status" in _error_fields(err)

    def test_invalid_status(self) -> None:
        _assert_rejects(
            {"status": "INVALID", "body": "desc"},
            CreateStatusPageIncidentUpdateRequest,
        )

    def test_valid_update(self) -> None:
        validate_body(
            {"status": "MONITORING", "body": "Fix deployed, monitoring."},
            CreateStatusPageIncidentUpdateRequest,
        )


# ---------------------------------------------------------------------------
# Status Pages — subscribers
# ---------------------------------------------------------------------------


class TestAddStatusPageSubscriberValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, AdminAddSubscriberRequest)
        assert "email" in _error_fields(err)

    def test_invalid_email(self) -> None:
        _assert_rejects({"email": "not-an-email"}, AdminAddSubscriberRequest)

    def test_valid_subscriber(self) -> None:
        validate_body({"email": "user@example.com"}, AdminAddSubscriberRequest)


# ---------------------------------------------------------------------------
# Status Pages — custom domains
# ---------------------------------------------------------------------------


class TestAddCustomDomainValidation:
    def test_empty_body(self) -> None:
        err = _assert_rejects({}, AddCustomDomainRequest)
        assert "hostname" in _error_fields(err)

    def test_invalid_hostname_uppercase(self) -> None:
        _assert_rejects({"hostname": "Status.Example.COM"}, AddCustomDomainRequest)

    def test_invalid_hostname_no_dot(self) -> None:
        _assert_rejects({"hostname": "localhost"}, AddCustomDomainRequest)

    def test_valid_domain(self) -> None:
        validate_body({"hostname": "status.example.com"}, AddCustomDomainRequest)


# ---------------------------------------------------------------------------
# Cross-cutting: validate_body returns original dict on success
# ---------------------------------------------------------------------------


class TestValidateBodyPassthrough:
    def test_returns_original_dict(self) -> None:
        body = {"name": "test-tag"}
        result = validate_body(body, CreateTagRequest)
        assert result is body

    def test_extra_fields_pass_through(self) -> None:
        body = {"name": "test-tag", "extraField": "should pass"}
        result = validate_body(body, CreateTagRequest)
        assert result is body
        assert result["extraField"] == "should pass"
