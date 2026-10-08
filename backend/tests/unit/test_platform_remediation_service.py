# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from services.platform_remediation_service import PlatformRemediationService


def test_platform_remediation_service_builds_local_and_global_action_items():
    service = PlatformRemediationService()
    maintenance_service = MagicMock()
    maintenance_service.get_status.return_value = {
        "status": "success",
        "reason": "startup",
        "notification": {"webhook_count": 0, "ready": False, "summary": "No alert webhook configured"},
        "data_quality": {
            "suspect_history_count": 0,
            "archived_history_count": 52,
            "clean": True,
            "summary": "Archived 52 maintenance history records",
        },
        "risk": {
            "shadow_count": 1,
            "summary": "Detected 1 shadow business database",
        },
    }
    readiness_service = MagicMock()
    readiness_service.evaluate.return_value = {
        "stage": "pre-production",
        "score": 75,
        "summary": "Core capabilities are ready for staging, but alert integration and environment governance remain the main constraints.",
    }
    chatops_service = MagicMock()
    chatops_service.get_overview.return_value = {
        "webhook_ready": False,
        "verification_token_configured": False,
        "platform_ready": False,
        "external_connected": False,
        "subscription_endpoint_verified": False,
        "ready": False,
        "healthy_notification_platform_webhook_count": 0,
        "summary": "The notification platform event callback endpoint is available, but there is no healthy reply channel yet.",
    }

    with patch("services.platform_remediation_service.get_platform_maintenance_service", return_value=maintenance_service), \
         patch("services.platform_remediation_service.get_commander_chatops_service", return_value=chatops_service), \
         patch("services.platform_remediation_service.get_platform_readiness_service", return_value=readiness_service), \
         patch("services.platform_remediation_service.get_db_observability", return_value={
             "path": r"D:\workspace\ai_test_platform\backend\data\business.db",
             "shadow_paths": [r"D:\workspace\ai_test_platform\data\business.db"],
             "shadow_count": 1,
         }):
        result = service.evaluate()

    assert result["status"] == "attention"
    assert result["counts"]["total"] == 4
    assert result["counts"]["blocking"] == 2
    assert result["counts"]["local"] == 2
    assert result["counts"]["global"] == 2
    assert result["items"][0]["key"] == "notification_webhook"
    assert result["items"][0]["route"] == "/notifications"
    assert any(item["key"] == "shadow_business_db" for item in result["items"])
    assert any(item["key"] == "production_readiness_gap" for item in result["items"])


def test_platform_remediation_skips_archive_governance_when_export_is_fresh():
    service = PlatformRemediationService()
    maintenance_service = MagicMock()
    maintenance_service.get_status.return_value = {
        "status": "success",
        "reason": "startup",
        "notification": {"webhook_count": 1, "tested_enabled": 1, "healthy_enabled": 1, "ready": True, "summary": "Alert webhook configured"},
        "data_quality": {
            "suspect_history_count": 0,
            "archived_history_count": 52,
            "archive_export_count": 1,
            "archive_export_fresh": True,
            "last_archive_export_at": "2026-03-16T16:00:00",
            "clean": True,
            "summary": "Archived 52 maintenance history records; the latest export is complete",
        },
        "risk": {
            "shadow_count": 0,
            "summary": "No shadow business database detected",
        },
    }
    readiness_service = MagicMock()
    readiness_service.evaluate.return_value = {
        "stage": "pre-production",
        "score": 88,
        "summary": "The platform is close to the production operations baseline.",
    }
    chatops_service = MagicMock()
    chatops_service.get_overview.return_value = {
        "webhook_ready": True,
        "verification_token_configured": True,
        "platform_ready": True,
        "external_connected": True,
        "subscription_endpoint_verified": True,
        "ready": True,
        "healthy_notification_platform_webhook_count": 1,
        "summary": "The latest notification platform command was received and successfully sent back to the group.",
    }

    with patch("services.platform_remediation_service.get_platform_maintenance_service", return_value=maintenance_service), \
         patch("services.platform_remediation_service.get_commander_chatops_service", return_value=chatops_service), \
         patch("services.platform_remediation_service.get_platform_readiness_service", return_value=readiness_service), \
         patch("services.platform_remediation_service.get_db_observability", return_value={
             "path": r"D:\workspace\ai_test_platform\backend\data\business.db",
             "shadow_paths": [],
             "shadow_count": 0,
         }):
        result = service.evaluate()

    assert not any(item["key"] == "archived_history_governance" for item in result["items"])
    assert result["counts"]["total"] == 1


def test_platform_remediation_adds_chatops_subscription_task_when_notification_is_ready():
    service = PlatformRemediationService()
    maintenance_service = MagicMock()
    maintenance_service.get_status.return_value = {
        "status": "success",
        "reason": "startup",
        "notification": {"webhook_count": 1, "tested_enabled": 1, "healthy_enabled": 1, "ready": True, "summary": "Alert webhook configured"},
        "data_quality": {"suspect_history_count": 0, "archived_history_count": 0, "clean": True, "summary": "Maintenance history is normal"},
        "risk": {"shadow_count": 0, "summary": "No shadow business database detected"},
    }
    readiness_service = MagicMock()
    readiness_service.evaluate.return_value = {
        "stage": "production-ready",
        "score": 92,
        "summary": "The platform is close to the production operations baseline.",
    }
    chatops_service = MagicMock()
    chatops_service.get_overview.return_value = {
        "webhook_ready": True,
        "verification_token_configured": False,
        "platform_ready": False,
        "external_connected": False,
        "subscription_endpoint_verified": False,
        "ready": False,
        "healthy_notification_platform_webhook_count": 1,
        "summary": "The notification platform reply channel is healthy, but the event subscription verification token is missing, so group messages cannot reliably return to the platform.",
    }

    with patch("services.platform_remediation_service.get_platform_maintenance_service", return_value=maintenance_service), \
         patch("services.platform_remediation_service.get_commander_chatops_service", return_value=chatops_service), \
         patch("services.platform_remediation_service.get_platform_readiness_service", return_value=readiness_service), \
         patch("services.platform_remediation_service.get_db_observability", return_value={
             "path": r"D:\workspace\ai_test_platform\backend\data\business.db",
             "shadow_paths": [],
             "shadow_count": 0,
         }):
        result = service.evaluate()

    assert any(item["key"] == "notification_platform_chatops_subscription" for item in result["items"])


def test_platform_remediation_guides_fixing_public_callback_when_probe_fails():
    service = PlatformRemediationService()
    maintenance_service = MagicMock()
    maintenance_service.get_status.return_value = {
        "status": "success",
        "reason": "startup",
        "notification": {"webhook_count": 1, "tested_enabled": 1, "healthy_enabled": 1, "ready": True, "summary": "Alert webhook configured"},
        "data_quality": {"suspect_history_count": 0, "archived_history_count": 0, "clean": True, "summary": "Maintenance history is normal"},
        "risk": {"shadow_count": 0, "summary": "No shadow business database detected"},
    }
    readiness_service = MagicMock()
    readiness_service.evaluate.return_value = {
        "stage": "production-ready",
        "score": 92,
        "summary": "The platform is close to the production operations baseline.",
    }
    chatops_service = MagicMock()
    chatops_service.get_overview.return_value = {
        "webhook_ready": True,
        "verification_token_configured": True,
        "platform_ready": True,
        "external_connected": False,
        "subscription_endpoint_verified": True,
        "ready": False,
        "healthy_notification_platform_webhook_count": 1,
        "callback_url_public": True,
        "callback_url": "https://ops.example.com/api/commander/notification_platform/events",
        "callback_probe": {
            "attempted": True,
            "success": False,
            "issue": "interstitial_page",
            "summary": "The public callback URL returned a tunnel warning page; the notification platform's cloud service likely cannot reach the platform callback directly.",
        },
        "summary": "The public callback URL returned a tunnel warning page; the notification platform's cloud service likely cannot reach the platform callback directly.",
    }

    with patch("services.platform_remediation_service.get_platform_maintenance_service", return_value=maintenance_service), \
         patch("services.platform_remediation_service.get_commander_chatops_service", return_value=chatops_service), \
         patch("services.platform_remediation_service.get_platform_readiness_service", return_value=readiness_service), \
         patch("services.platform_remediation_service.get_db_observability", return_value={
             "path": r"D:\workspace\ai_test_platform\backend\data\business.db",
             "shadow_paths": [],
             "shadow_count": 0,
         }):
        result = service.evaluate()

    chatops_item = next(item for item in result["items"] if item["key"] == "notification_platform_chatops_subscription")
    assert "Restore public callback reachability" in chatops_item["next_step"]
    assert chatops_item["evidence"]["callback_probe_success"] is False


def test_platform_remediation_guides_event_subscription_after_external_self_check_passes():
    service = PlatformRemediationService()
    maintenance_service = MagicMock()
    maintenance_service.get_status.return_value = {
        "status": "success",
        "reason": "startup",
        "notification": {"webhook_count": 1, "tested_enabled": 1, "healthy_enabled": 1, "ready": True, "summary": "Alert webhook configured"},
        "data_quality": {"suspect_history_count": 0, "archived_history_count": 0, "clean": True, "summary": "Maintenance history is normal"},
        "risk": {"shadow_count": 0, "summary": "No shadow business database detected"},
    }
    readiness_service = MagicMock()
    readiness_service.evaluate.return_value = {
        "stage": "production-ready",
        "score": 96,
        "summary": "The platform is close to the production operations baseline.",
    }
    chatops_service = MagicMock()
    chatops_service.get_overview.return_value = {
        "webhook_ready": True,
        "verification_token_configured": True,
        "platform_ready": True,
        "ready": False,
        "callback_url_public": True,
        "callback_url": "https://test.example-user.top:8443/api/commander/notification_platform/events",
        "callback_probe": {
            "attempted": True,
            "success": False,
            "issue": "timeout",
            "summary": "The public callback probe timed out; the notification platform's cloud service likely cannot reach this endpoint reliably.",
        },
        "external_connection_stale": False,
        "external_callback_ready": True,
        "external_self_check_recent_success": True,
        "external_connected_history_observed": False,
        "latest_external_success_at": "",
        "app_bot_configured": True,
        "app_bot_ready": True,
        "app_bot_check": {"success": True, "message": "App bot credentials validated; tenant_access_token obtained successfully."},
        "app_bot_id_masked": "cli...bcb",
        "summary": "The latest public platform self-check passed, confirming that the public callback endpoint, challenge, and text-message flow are available.",
    }

    with patch("services.platform_remediation_service.get_platform_maintenance_service", return_value=maintenance_service), \
         patch("services.platform_remediation_service.get_commander_chatops_service", return_value=chatops_service), \
         patch("services.platform_remediation_service.get_platform_readiness_service", return_value=readiness_service), \
         patch("services.platform_remediation_service.get_db_observability", return_value={
             "path": r"D:\workspace\ai_test_platform\backend\data\business.db",
             "shadow_paths": [],
             "shadow_count": 0,
         }):
        result = service.evaluate()

    chatops_item = next(item for item in result["items"] if item["key"] == "notification_platform_chatops_subscription")
    assert "Enable event subscription in the notification provider's developer console" in chatops_item["next_step"]
    assert "add the app bot to the target group" in chatops_item["next_step"]
    assert chatops_item["evidence"]["external_callback_ready"] is True
    assert chatops_item["evidence"]["external_self_check_recent_success"] is True
