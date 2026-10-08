# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from services.platform_readiness_service import PlatformReadinessService


def test_platform_readiness_evaluate_reports_local_and_global_views():
    service = PlatformReadinessService()
    maintenance_service = MagicMock()
    maintenance_service.get_status.return_value = {
        "status": "success",
        "reason": "startup",
        "notification": {"webhook_count": 0, "ready": False, "summary": "未配置告警 Webhook"},
        "data_quality": {
            "suspect_history_count": 0,
            "archived_history_count": 52,
            "raw_history_count": 138,
            "visible_history_count": 86,
            "clean": True,
            "summary": "已归档 52 条历史维护记录",
        },
        "report_history": {"history_entries": 17, "updated_entries": 0},
    }
    chatops_service = MagicMock()
    chatops_service.get_overview.return_value = {
        "webhook_ready": False,
        "verification_token_configured": False,
        "platform_ready": False,
        "external_connected": False,
        "ready": False,
        "enabled_notification_platform_webhook_count": 0,
        "healthy_notification_platform_webhook_count": 0,
        "summary": "已提供通知平台事件回调入口，但还没有健康的通知平台回推通道。",
    }

    with patch("services.platform_readiness_service.get_platform_maintenance_service", return_value=maintenance_service), \
         patch("services.platform_readiness_service.get_commander_chatops_service", return_value=chatops_service), \
         patch("services.platform_readiness_service.get_db_observability", return_value={
             "path": r"D:\workspace\ai_test_platform\backend\data\business.db",
             "shadow_paths": [r"D:\workspace\ai_test_platform\data\business.db"],
             "shadow_count": 1,
             "risk_level": "warning",
             "current_db": {
                 "exists": True,
                 "size_bytes": 1024,
                 "updated_at": "2026-03-16T12:00:00",
             },
         }), \
         patch.object(service, "_safe_count", side_effect=lambda table: 104 if table == "execution_groups" else 139):
        readiness = service.evaluate()

    assert readiness["stage"] == "beta"
    assert readiness["score"] > 0
    assert readiness["local_score"] > 0
    assert readiness["global_score"] > 0
    assert "the main remaining gaps are operational governance" in readiness["summary"]
    assert len(readiness["local"]) == 5
    assert len(readiness["global"]) == 4
    assert readiness["local"][1]["name"] == "Alerting Module"
    assert readiness["local"][1]["status"] == "critical"
    assert "Connect at least one production alert Webhook" in readiness["recommendations"][0]


def test_platform_readiness_treats_archived_history_as_governed_after_export():
    service = PlatformReadinessService()
    maintenance_service = MagicMock()
    maintenance_service.get_status.return_value = {
        "status": "success",
        "reason": "startup",
        "notification": {"webhook_count": 1, "tested_enabled": 1, "healthy_enabled": 1, "ready": True, "summary": "已配置 1 个 Webhook，其中 1 个最近测试通过"},
        "data_quality": {
            "suspect_history_count": 0,
            "archived_history_count": 52,
            "archive_export_count": 1,
            "archive_export_fresh": True,
            "last_archive_export_at": "2026-03-16T16:00:00",
            "clean": True,
            "summary": "已归档 52 条历史维护记录，最近已完成导出",
        },
        "report_history": {"history_entries": 17, "updated_entries": 0},
    }
    chatops_service = MagicMock()
    chatops_service.get_overview.return_value = {
        "webhook_ready": True,
        "verification_token_configured": True,
        "platform_ready": True,
        "external_connected": True,
        "ready": True,
        "enabled_notification_platform_webhook_count": 1,
        "healthy_notification_platform_webhook_count": 1,
        "summary": "最近一条通知平台指令已接收并成功回推到群里。",
    }

    with patch("services.platform_readiness_service.get_platform_maintenance_service", return_value=maintenance_service), \
         patch("services.platform_readiness_service.get_commander_chatops_service", return_value=chatops_service), \
         patch("services.platform_readiness_service.get_db_observability", return_value={
             "path": r"D:\workspace\ai_test_platform\backend\data\business.db",
             "shadow_paths": [],
             "shadow_count": 0,
             "risk_level": "normal",
             "current_db": {
                 "exists": True,
                 "size_bytes": 1024,
                 "updated_at": "2026-03-16T12:00:00",
             },
         }), \
         patch.object(service, "_safe_count", side_effect=lambda table: 104 if table == "execution_groups" else 139):
        readiness = service.evaluate()

    governance = next(section for section in readiness["local"] if section["key"] == "data_governance_module")
    assert governance["score"] == 100
    assert "archive export: complete" in governance["summary"]
    assert not any("offline export or retention policies" in item for item in readiness["recommendations"])


def test_platform_readiness_recommends_notification_platform_subscription_when_webhook_ready_but_token_missing():
    service = PlatformReadinessService()
    maintenance_service = MagicMock()
    maintenance_service.get_status.return_value = {
        "status": "success",
        "reason": "startup",
        "notification": {"webhook_count": 1, "tested_enabled": 1, "healthy_enabled": 1, "ready": True, "summary": "已配置 1 个 Webhook，其中 1 个最近测试通过"},
        "data_quality": {"suspect_history_count": 0, "archived_history_count": 0, "clean": True, "summary": "维护历史正常"},
        "report_history": {"history_entries": 17, "updated_entries": 0},
    }
    chatops_service = MagicMock()
    chatops_service.get_overview.return_value = {
        "webhook_ready": True,
        "verification_token_configured": False,
        "platform_ready": False,
        "external_connected": False,
        "ready": False,
        "enabled_notification_platform_webhook_count": 1,
        "healthy_notification_platform_webhook_count": 1,
        "summary": "通知平台回推通道已健康，但还缺少事件订阅 verification token，群消息还不能稳定回流到平台。",
    }

    with patch("services.platform_readiness_service.get_platform_maintenance_service", return_value=maintenance_service), \
         patch("services.platform_readiness_service.get_commander_chatops_service", return_value=chatops_service), \
         patch("services.platform_readiness_service.get_db_observability", return_value={
             "path": r"D:\workspace\ai_test_platform\backend\data\business.db",
             "shadow_paths": [],
             "shadow_count": 0,
             "risk_level": "normal",
             "current_db": {"exists": True, "size_bytes": 1024, "updated_at": "2026-03-18T10:00:00"},
         }), \
         patch.object(service, "_safe_count", side_effect=lambda table: 104 if table == "execution_groups" else 139):
        readiness = service.evaluate()

    chatops_section = next(section for section in readiness["local"] if section["key"] == "chatops_module")
    assert chatops_section["status"] == "warning"
    assert any("verification token" in item for item in readiness["recommendations"])


def test_platform_readiness_recommends_fixing_public_callback_when_probe_fails():
    service = PlatformReadinessService()
    maintenance_service = MagicMock()
    maintenance_service.get_status.return_value = {
        "status": "success",
        "reason": "startup",
        "notification": {"webhook_count": 1, "tested_enabled": 1, "healthy_enabled": 1, "ready": True, "summary": "已配置 1 个 Webhook，其中 1 个最近测试通过"},
        "data_quality": {"suspect_history_count": 0, "archived_history_count": 0, "clean": True, "summary": "维护历史正常"},
        "report_history": {"history_entries": 17, "updated_entries": 0},
    }
    chatops_service = MagicMock()
    chatops_service.get_overview.return_value = {
        "webhook_ready": True,
        "verification_token_configured": True,
        "platform_ready": True,
        "external_connected": False,
        "ready": False,
        "callback_url_public": True,
        "callback_probe": {
            "attempted": True,
            "success": False,
            "issue": "interstitial_page",
            "summary": "公网回调地址返回了隧道警告页，通知平台云侧大概率无法直接命中平台回调。",
        },
        "enabled_notification_platform_webhook_count": 1,
        "healthy_notification_platform_webhook_count": 1,
        "summary": "公网回调地址返回了隧道警告页，通知平台云侧大概率无法直接命中平台回调。",
    }

    with patch("services.platform_readiness_service.get_platform_maintenance_service", return_value=maintenance_service), \
         patch("services.platform_readiness_service.get_commander_chatops_service", return_value=chatops_service), \
         patch("services.platform_readiness_service.get_db_observability", return_value={
             "path": r"D:\workspace\ai_test_platform\backend\data\business.db",
             "shadow_paths": [],
             "shadow_count": 0,
             "risk_level": "normal",
             "current_db": {"exists": True, "size_bytes": 1024, "updated_at": "2026-03-18T10:00:00"},
         }), \
         patch.object(service, "_safe_count", side_effect=lambda table: 104 if table == "execution_groups" else 139):
        readiness = service.evaluate()

    assert any("Restore public callback reachability" in item for item in readiness["recommendations"])
