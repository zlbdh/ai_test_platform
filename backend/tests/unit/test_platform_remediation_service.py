# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from services.platform_remediation_service import PlatformRemediationService


def test_platform_remediation_service_builds_local_and_global_action_items():
    service = PlatformRemediationService()
    maintenance_service = MagicMock()
    maintenance_service.get_status.return_value = {
        "status": "success",
        "reason": "startup",
        "notification": {"webhook_count": 0, "ready": False, "summary": "未配置告警 Webhook"},
        "data_quality": {
            "suspect_history_count": 0,
            "archived_history_count": 52,
            "clean": True,
            "summary": "已归档 52 条历史维护记录",
        },
        "risk": {
            "shadow_count": 1,
            "summary": "检测到 1 个影子业务库",
        },
    }
    readiness_service = MagicMock()
    readiness_service.evaluate.return_value = {
        "stage": "pre-production",
        "score": 75,
        "summary": "主能力已收口到准生产阶段，但告警接出与环境治理仍是主要约束。",
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
        "summary": "已提供通知平台事件回调入口，但还没有健康的通知平台回推通道。",
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
        "notification": {"webhook_count": 1, "tested_enabled": 1, "healthy_enabled": 1, "ready": True, "summary": "已配置告警 Webhook"},
        "data_quality": {
            "suspect_history_count": 0,
            "archived_history_count": 52,
            "archive_export_count": 1,
            "archive_export_fresh": True,
            "last_archive_export_at": "2026-03-16T16:00:00",
            "clean": True,
            "summary": "已归档 52 条历史维护记录，最近已完成导出",
        },
        "risk": {
            "shadow_count": 0,
            "summary": "未发现影子业务库",
        },
    }
    readiness_service = MagicMock()
    readiness_service.evaluate.return_value = {
        "stage": "pre-production",
        "score": 88,
        "summary": "平台整体接近生产级运行基线。",
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
        "summary": "最近一条通知平台指令已接收并成功回推到群里。",
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
        "notification": {"webhook_count": 1, "tested_enabled": 1, "healthy_enabled": 1, "ready": True, "summary": "已配置告警 Webhook"},
        "data_quality": {"suspect_history_count": 0, "archived_history_count": 0, "clean": True, "summary": "维护历史正常"},
        "risk": {"shadow_count": 0, "summary": "未发现影子业务库"},
    }
    readiness_service = MagicMock()
    readiness_service.evaluate.return_value = {
        "stage": "production-ready",
        "score": 92,
        "summary": "平台整体已接近生产级运行基线。",
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
        "summary": "通知平台回推通道已健康，但还缺少事件订阅 verification token，群消息还不能稳定回流到平台。",
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
        "notification": {"webhook_count": 1, "tested_enabled": 1, "healthy_enabled": 1, "ready": True, "summary": "已配置告警 Webhook"},
        "data_quality": {"suspect_history_count": 0, "archived_history_count": 0, "clean": True, "summary": "维护历史正常"},
        "risk": {"shadow_count": 0, "summary": "未发现影子业务库"},
    }
    readiness_service = MagicMock()
    readiness_service.evaluate.return_value = {
        "stage": "production-ready",
        "score": 92,
        "summary": "平台整体已接近生产级运行基线。",
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
            "summary": "公网回调地址返回了隧道警告页，通知平台云侧大概率无法直接命中平台回调。",
        },
        "summary": "公网回调地址返回了隧道警告页，通知平台云侧大概率无法直接命中平台回调。",
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
        "notification": {"webhook_count": 1, "tested_enabled": 1, "healthy_enabled": 1, "ready": True, "summary": "已配置告警 Webhook"},
        "data_quality": {"suspect_history_count": 0, "archived_history_count": 0, "clean": True, "summary": "维护历史正常"},
        "risk": {"shadow_count": 0, "summary": "未发现影子业务库"},
    }
    readiness_service = MagicMock()
    readiness_service.evaluate.return_value = {
        "stage": "production-ready",
        "score": 96,
        "summary": "平台整体已接近生产级运行基线。",
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
            "summary": "公网回调地址回探超时，通知平台云侧当前大概率无法稳定访问该入口。",
        },
        "external_connection_stale": False,
        "external_callback_ready": True,
        "external_self_check_recent_success": True,
        "external_connected_history_observed": False,
        "latest_external_success_at": "",
        "app_bot_configured": True,
        "app_bot_ready": True,
        "app_bot_check": {"success": True, "message": "应用机器人凭据校验通过，已成功获取 tenant_access_token。"},
        "app_bot_id_masked": "cli...bcb",
        "summary": "最近一次平台公网自测已经通过，说明公网回调入口、challenge 和文本消息链路都可用。",
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
