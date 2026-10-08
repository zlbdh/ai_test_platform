"""
P2-3: Backend API integration tests
Coverage: /api/plan/generate, /api/history/*, /api/health, /api/config/ai, /api/gallery/*
"""
import asyncio
import io
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from main import app
from core.config import Config

client = TestClient(app)


# ============================================================
# /api/health — Health check
# ============================================================
class TestHealthAPI:
    def test_health_returns_200(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        # The test environment may have no LLM key, so status may be degraded.
        assert data["status"] in ("healthy", "degraded")

    def test_health_contains_version(self):
        resp = client.get("/api/health")
        data = resp.json()
        assert "version" in data
        assert "checks" in data
        assert "maintenance" in data["checks"]
        assert "database_path" in data["checks"]
        assert "database_shadow_paths" in data["checks"]
        assert "database_shadow_count" in data["checks"]
        assert "database_consistency" in data["checks"]
        assert "notification_webhook_count" in data["checks"]
        assert "notification_tested_webhook_count" in data["checks"]
        assert "notification_healthy_webhook_count" in data["checks"]
        assert "notification_untested_webhook_count" in data["checks"]
        assert "notification_ready" in data["checks"]
        assert "maintenance_suspect_history_count" in data["checks"]
        assert "maintenance_archived_history_count" in data["checks"]
        assert "maintenance_history_clean" in data["checks"]
        assert "readiness_stage" in data["checks"]
        assert "readiness_score" in data["checks"]

    def test_root_endpoint(self):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


# ============================================================
# /api/plan/generate — Plan generation
# ============================================================
class TestPlanGenerateAPI:
    """Mock planner_service to avoid real LLM calls."""

    MOCK_PLAN_RESULT = {
        "test_cases": [
            {
                "scenario": "Login functionality test",
                "priority": "P0",
                "steps": [
                    {"action": "goto", "target": "https://example.com/login", "value": ""},
                    {"action": "fill", "target": "#username", "value": "admin"},
                    {"action": "fill", "target": "#password", "value": "pass123"},
                    {"action": "click", "target": "button[type=submit]", "value": ""},
                ],
            }
        ],
        "sources": ["prd_doc_1"],
        "coverage_summary": {"total": 4, "covered": 4, "rate": "100%"},
    }

    @patch("routers.plan.planner_service")
    def test_plan_generate_success(self, mock_svc):
        mock_svc.generate_plan = AsyncMock(return_value=self.MOCK_PLAN_RESULT)

        resp = client.post("/api/plan/generate", json={
            "requirement": "Test login functionality",
            "enable_rag": True,
            "target_url": "https://example.com"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert len(data["steps"]) == 4
        assert data["steps"][0]["action"] == "goto"
        assert data["coverage_summary"]["rate"] == "100%"

    @patch("routers.plan.planner_service")
    def test_plan_generate_empty_steps(self, mock_svc):
        """An empty LLM result should return error status."""
        mock_svc.generate_plan = AsyncMock(return_value={"test_cases": []})

        resp = client.post("/api/plan/generate", json={
            "requirement": "Invalid requirement",
            "enable_rag": False
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "LLM" in data["message"]
        assert data["steps"] == []

    @patch("routers.plan.planner_service")
    def test_plan_generate_llm_exception(self, mock_svc):
        """LLM exceptions should degrade gracefully."""
        mock_svc.generate_plan = AsyncMock(side_effect=Exception("API key invalid"))

        resp = client.post("/api/plan/generate", json={
            "requirement": "Test the shopping cart"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "API key invalid" in data["message"]

    @patch("routers.plan.planner_service")
    def test_plan_generate_with_priority(self, mock_svc):
        """Verify that priority and scenario map correctly to description."""
        mock_svc.generate_plan = AsyncMock(return_value=self.MOCK_PLAN_RESULT)

        resp = client.post("/api/plan/generate", json={
            "requirement": "Test login",
            "enable_rag": True
        })
        data = resp.json()
        step = data["steps"][0]
        assert step["priority"] == "P0"
        assert step["scenario"] == "Login functionality test"
        assert "[P0]" in step["description"]

    def test_plan_generate_missing_requirement(self):
        """A missing requirement field should return 422."""
        resp = client.post("/api/plan/generate", json={})
        assert resp.status_code == 422


# ============================================================
# /api/config/ai — AI configuration
# ============================================================
class TestAIConfigAPI:
    def test_get_ai_config(self):
        resp = client.get("/api/config/ai")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "config" in data

    def test_update_ai_config(self):
        """Test AI configuration updates by calling the endpoint directly and verifying reachability and response format."""
        resp = client.post("/api/config/ai", json={
            "provider": "openai",
            "model": "should-be-overridden",
            "vision_model": "should-be-overridden",
            "temperature": 0.35,
            "top_p": 0.85,
            "max_tokens": 2048,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success", data
        assert "config" in data
        assert data["config"]["model"] == "claude-haiku-4-5-20251001"
        assert data["config"]["vision_model"] == "claude-haiku-4-5-20251001"
        assert data["config"]["planner_model"] == "claude-haiku-4-5-20251001"
        assert data["config"]["executor_model"] == "claude-haiku-4-5-20251001"
        assert data["config"]["temperature"] == 0.35
        assert data["config"]["top_p"] == 0.85
        assert data["config"]["max_tokens"] == 2048
        assert data["config"]["provider_locked"] is True
        assert data["config"]["model_locked"] is True


# ============================================================
# /api/history — History
# ============================================================
class TestHistoryAPI:
    def test_get_history_returns_list(self):
        resp = client.get("/api/history?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_history_detail_not_found(self):
        resp = client.get("/api/history/nonexistent-task-id-12345")
        assert resp.status_code == 404

    def test_delete_history_not_found(self):
        resp = client.delete("/api/history/nonexistent-task-id-12345")
        assert resp.status_code == 404

    def test_gallery_empty_task(self):
        resp = client.get("/api/gallery/nonexistent-task-id-12345")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 0


# ============================================================
# /api/report — Reports
# ============================================================
class TestReportAPI:
    @patch("routers.report.get_reporter")
    def test_generate_report_supports_task_id(self, mock_get_reporter):
        reporter = MagicMock()
        reporter.generate_report.return_value = {"status": "success", "id": "demo"}
        mock_get_reporter.return_value = reporter

        resp = client.post("/api/report/generate", json={"task_id": "task-123"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        reporter.generate_report.assert_called_once_with(task_id="task-123")

    @patch("routers.report.get_reporter")
    def test_generate_report_supports_execution_group_id(self, mock_get_reporter):
        reporter = MagicMock()
        reporter.generate_report.return_value = {"status": "success", "id": "demo-group"}
        mock_get_reporter.return_value = reporter

        resp = client.post("/api/report/generate", json={"execution_group_id": "group-123"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        reporter.generate_report.assert_called_once_with(task_id="group-123")

    def test_report_history(self):
        resp = client.get("/api/report/history?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "history" in data

    @patch("routers.report.get_reporter")
    def test_report_view_success(self, mock_get_reporter, tmp_path):
        report_file = tmp_path / "demo.html"
        report_file.write_text("<html><body>demo report</body></html>", encoding="utf-8")
        reporter = MagicMock()
        reporter.get_report_path.return_value = report_file
        mock_get_reporter.return_value = reporter

        resp = client.get("/api/report/view/demo")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "demo report" in resp.text

    @patch("routers.report.get_reporter")
    def test_report_view_not_found(self, mock_get_reporter):
        reporter = MagicMock()
        reporter.get_report_path.return_value = None
        mock_get_reporter.return_value = reporter

        resp = client.get("/api/report/view/nonexistent-report")
        assert resp.status_code == 404

    @patch("routers.report.get_reporter")
    def test_delete_report_success(self, mock_get_reporter):
        reporter = MagicMock()
        reporter.delete_report.return_value = True
        mock_get_reporter.return_value = reporter

        resp = client.delete("/api/report/demo")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

    @patch("routers.report.get_reporter")
    def test_delete_report_not_found(self, mock_get_reporter):
        reporter = MagicMock()
        reporter.delete_report.return_value = False
        mock_get_reporter.return_value = reporter

        resp = client.delete("/api/report/nonexistent-report")
        assert resp.status_code == 404


class TestPlatformMaintenanceAPI:
    @patch("routers.platform.get_platform_readiness_service")
    @patch("routers.platform.get_commander_chatops_service")
    @patch("routers.platform.get_platform_maintenance_service")
    @patch("routers.platform.get_db_observability")
    def test_platform_info_contains_db_observability(self, mock_get_db_observability, mock_get_service, mock_get_chatops_service, mock_get_readiness_service):
        mock_get_db_observability.return_value = {
            "path": r"D:\demo\business.db",
            "shadow_paths": [r"D:\legacy\business.db"],
            "shadow_count": 1,
            "risk_level": "warning",
            "current_db": {
                "path": r"D:\demo\business.db",
                "exists": True,
                "size_bytes": 1024,
                "updated_at": "2026-03-16T10:00:00",
            },
            "is_memory": False,
        }
        svc = MagicMock()
        svc.get_status.return_value = {
            "status": "success",
            "reason": "startup",
            "notification": {
                "webhook_count": 2,
                "tested_enabled": 2,
                "healthy_enabled": 1,
                "untested_enabled": 0,
                "ready": True,
                "summary": "2 webhooks configured; 1 passed its most recent test",
            },
            "data_quality": {"suspect_history_count": 3, "archived_history_count": 4, "clean": False, "summary": "Detected 3 suspicious maintenance history records, hidden from the default main view"},
        }
        mock_get_service.return_value = svc
        chatops_svc = MagicMock()
        chatops_svc.get_overview.return_value = {
            "ready": False,
            "platform_ready": False,
            "webhook_ready": True,
            "external_connected": False,
            "external_callback_ready": False,
            "direct_chat_ready": False,
            "app_bot_configured": False,
            "app_bot_id_masked": "",
            "app_bot_updated_at": "",
            "subscription_endpoint_verified": False,
            "verification_token_configured": False,
            "verification_token_masked": "",
            "verification_token_updated_at": "",
            "summary": "The notification platform's outbound channel is healthy, but the event subscription verification token is missing, so group messages cannot reliably return to the platform.",
            "latest_event": {"created_at": "2026-03-18T11:10:00", "delivery_delivered": 1},
            "latest_successful_event": {"created_at": "2026-03-18T11:09:00"},
        }
        mock_get_chatops_service.return_value = chatops_svc
        readiness_svc = MagicMock()
        readiness_svc.evaluate.return_value = {"stage": "pre-production", "score": 78, "summary": "Core capabilities are ready for staging, but alert integration and environment governance remain the main constraints."}
        mock_get_readiness_service.return_value = readiness_svc
        resp = client.get("/api/platform/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["operations"]["business_db_path"] == r"D:\demo\business.db"
        assert data["operations"]["shadow_business_dbs"] == [r"D:\legacy\business.db"]
        assert data["operations"]["shadow_business_db_count"] == 1
        assert data["operations"]["business_db_risk_level"] == "warning"
        assert data["operations"]["notification_webhook_count"] == 2
        assert data["operations"]["notification_tested_webhook_count"] == 2
        assert data["operations"]["notification_healthy_webhook_count"] == 1
        assert data["operations"]["notification_untested_webhook_count"] == 0
        assert data["operations"]["notification_ready"] is True
        assert data["operations"]["commander_chatops_ready"] is False
        assert data["operations"]["commander_chatops_platform_ready"] is False
        assert data["operations"]["commander_chatops_webhook_ready"] is True
        assert data["operations"]["commander_chatops_external_connected"] is False
        assert data["operations"]["commander_chatops_external_callback_ready"] is False
        assert data["operations"]["commander_chatops_direct_chat_ready"] is False
        assert data["operations"]["commander_chatops_app_bot_configured"] is False
        assert data["operations"]["commander_chatops_subscription_endpoint_verified"] is False
        assert data["operations"]["commander_chatops_verification_token_configured"] is False
        assert data["operations"]["maintenance_suspect_history_count"] == 3
        assert data["operations"]["maintenance_archived_history_count"] == 4
        assert data["operations"]["maintenance_archive_export_count"] == 0
        assert data["operations"]["maintenance_archive_export_fresh"] is True
        assert data["operations"]["maintenance_history_clean"] is False
        assert data["operations"]["readiness_stage"] == "pre-production"
        assert data["operations"]["readiness_score"] == 78
        assert "readiness_summary" in data["operations"]

    @patch("routers.platform.quarantine_shadow_databases")
    def test_quarantine_platform_shadow_db_endpoint(self, mock_quarantine):
        mock_quarantine.return_value = {
            "reason": "ops_quarantine",
            "archive_dir": r"D:\workspace\ai_test_platform\data\shadow_db_archive",
            "moved_count": 1,
            "moved": [{"source_path": r"D:\workspace\ai_test_platform\data\business.db", "archived_path": r"D:\workspace\ai_test_platform\data\shadow_db_archive\business.shadow_ops_quarantine_20260316.db"}],
            "skipped_count": 0,
            "skipped": [],
            "observability": {
                "path": r"D:\workspace\ai_test_platform\backend\data\business.db",
                "shadow_paths": [],
                "shadow_count": 0,
                "risk_level": "normal",
                "current_db": {"exists": True, "size_bytes": 1024, "updated_at": "2026-03-16T15:00:00"},
            },
        }

        resp = client.post("/api/platform/shadow-db/quarantine", json={"reason": "ops_quarantine"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["result"]["moved_count"] == 1
        assert data["result"]["observability"]["shadow_count"] == 0
        mock_quarantine.assert_called_once_with(reason="ops_quarantine")

    @patch("routers.platform.get_platform_readiness_service")
    def test_platform_readiness_endpoint(self, mock_get_readiness_service):
        readiness_svc = MagicMock()
        readiness_svc.evaluate.return_value = {
            "stage": "pre-production",
            "score": 78,
            "local_score": 74,
            "global_score": 83,
            "summary": "Core capabilities are ready for staging, but alert integration and environment governance remain the main constraints.",
            "local": [{"key": "maintenance_module", "name": "Maintenance module", "score": 100, "status": "good", "summary": "ok"}],
            "global": [{"key": "architecture", "name": "Architecture stability", "score": 88, "status": "good", "summary": "ok"}],
            "recommendations": ["Connect at least 1 production alert webhook to deliver maintenance failures and risk alerts through the notification channel."],
        }
        mock_get_readiness_service.return_value = readiness_svc

        resp = client.get("/api/platform/readiness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["readiness"]["stage"] == "pre-production"
        assert data["readiness"]["score"] == 78

    @patch("routers.platform.get_platform_maintenance_service")
    def test_get_platform_maintenance(self, mock_get_service):
        svc = MagicMock()
        svc.get_status.return_value = {
            "status": "success",
            "reason": "startup",
            "risk": {"level": "warning", "shadow_count": 1},
            "warning_detected": True,
            "risk_alert_sent": True,
            "notification": {
                "webhook_count": 1,
                "tested_enabled": 1,
                "healthy_enabled": 1,
                "untested_enabled": 0,
                "ready": True,
                "summary": "1 webhook configured; 1 passed its most recent test",
            },
            "data_quality": {"suspect_history_count": 2, "archived_history_count": 5, "clean": False, "summary": "Detected 2 suspicious maintenance history records, hidden from the default main view"},
        }
        svc.get_latest_activity.return_value = {
            "status": "success",
            "reason": "history_list",
            "risk": {"level": "warning", "shadow_count": 1},
            "warning_detected": True,
            "risk_alert_sent": False,
            "notification": {
                "webhook_count": 1,
                "tested_enabled": 1,
                "healthy_enabled": 1,
                "untested_enabled": 0,
                "ready": True,
                "summary": "1 webhook configured; 1 passed its most recent test",
            },
            "data_quality": {"suspect_history_count": 2, "archived_history_count": 5, "clean": False, "summary": "Detected 2 suspicious maintenance history records, hidden from the default main view"},
        }
        svc.list_runs.return_value = {
            "items": [{"id": 1, "status": "success", "risk": {"level": "warning", "shadow_count": 1}, "warning_detected": True, "risk_alert_sent": True}],
            "total": 1,
            "raw_total": 3,
            "suspect_count": 2,
            "archived_count": 5,
            "filtered": True,
            "include_suspect": False,
            "include_archived": False,
        }
        mock_get_service.return_value = svc

        resp = client.get("/api/platform/maintenance?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["current"]["reason"] == "startup"
        assert data["latest_activity"]["reason"] == "history_list"
        assert data["current"]["risk"]["shadow_count"] == 1
        assert data["history"]["items"][0]["warning_detected"] is True
        assert data["current"]["risk_alert_sent"] is True
        assert data["history"]["total"] == 1
        assert data["current"]["notification"]["ready"] is True
        assert data["current"]["data_quality"]["suspect_history_count"] == 2
        assert data["current"]["data_quality"]["archived_history_count"] == 5
        assert data["history"]["suspect_count"] == 2
        assert data["history"]["archived_count"] == 5
        assert data["history"]["filtered"] is True
        svc.list_runs.assert_called_once_with(limit=5, include_suspect=False, include_archived=False)

    @patch("routers.platform.get_platform_maintenance_service")
    def test_get_platform_maintenance_supports_include_suspect(self, mock_get_service):
        svc = MagicMock()
        svc.get_status.return_value = {"status": "success", "reason": "startup"}
        svc.get_latest_activity.return_value = {"status": "success", "reason": "history_list"}
        svc.list_runs.return_value = {"items": [], "total": 0, "raw_total": 2, "suspect_count": 2, "archived_count": 0, "filtered": False, "include_suspect": True, "include_archived": False}
        mock_get_service.return_value = svc

        resp = client.get("/api/platform/maintenance?limit=3&include_suspect=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["history"]["include_suspect"] is True
        svc.list_runs.assert_called_once_with(limit=3, include_suspect=True, include_archived=False)

    @patch("routers.platform.get_platform_maintenance_service")
    def test_get_platform_maintenance_supports_include_archived(self, mock_get_service):
        svc = MagicMock()
        svc.get_status.return_value = {"status": "success", "reason": "startup"}
        svc.get_latest_activity.return_value = {"status": "success", "reason": "history_list"}
        svc.list_runs.return_value = {"items": [], "total": 2, "raw_total": 2, "suspect_count": 0, "archived_count": 1, "filtered": True, "include_suspect": False, "include_archived": True}
        mock_get_service.return_value = svc

        resp = client.get("/api/platform/maintenance?limit=3&include_archived=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["history"]["include_archived"] is True
        svc.list_runs.assert_called_once_with(limit=3, include_suspect=False, include_archived=True)

    @patch("routers.platform.get_platform_maintenance_service")
    def test_archive_suspect_platform_maintenance(self, mock_get_service):
        svc = MagicMock()
        svc.archive_suspect_runs.return_value = {
            "archived_count": 4,
            "archived_ids": [1, 2, 3, 4],
            "reason": "ops_archive",
            "archived_at": "2026-03-16T12:00:00",
            "remaining": 0,
            "data_quality": {"suspect_history_count": 0, "archived_history_count": 4, "clean": True, "summary": "Archived 4 maintenance history records"},
        }
        mock_get_service.return_value = svc

        resp = client.post("/api/platform/maintenance/archive-suspect", json={"reason": "ops_archive", "limit": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["result"]["archived_count"] == 4
        svc.archive_suspect_runs.assert_called_once_with(reason="ops_archive", limit=0)

    @patch("routers.platform.get_platform_maintenance_service")
    def test_export_archived_platform_maintenance(self, mock_get_service):
        svc = MagicMock()
        svc.export_archived_runs.return_value = {
            "reason": "ops_export_archive",
            "format": "json",
            "exported_at": "2026-03-16T16:00:00",
            "file_path": r"D:\workspace\ai_test_platform\data\platform_maintenance_exports\platform_maintenance_archive_ops_export_archive_20260316_160000.json",
            "count": 52,
            "bytes_written": 2048,
            "data_quality": {
                "suspect_history_count": 0,
                "raw_history_count": 140,
                "archived_history_count": 52,
                "visible_history_count": 88,
                "archive_export_count": 1,
                "last_archive_export_at": "2026-03-16T16:00:00",
                "last_archive_export_reason": "ops_export_archive",
                "last_archive_export_path": r"D:\workspace\ai_test_platform\data\platform_maintenance_exports\platform_maintenance_archive_ops_export_archive_20260316_160000.json",
                "last_archive_export_format": "json",
                "archive_export_fresh": True,
                "clean": True,
                "summary": "Archived 52 maintenance history records; the latest export is complete",
            },
        }
        mock_get_service.return_value = svc

        resp = client.post("/api/platform/maintenance/export-archive", json={"reason": "ops_export_archive", "format": "json"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["result"]["count"] == 52
        svc.export_archived_runs.assert_called_once_with(reason="ops_export_archive", export_format="json")

    @patch("routers.platform.get_platform_maintenance_service")
    def test_export_archived_platform_maintenance_rejects_invalid_format(self, mock_get_service):
        svc = MagicMock()
        svc.export_archived_runs.side_effect = ValueError("unsupported export format")
        mock_get_service.return_value = svc

        resp = client.post("/api/platform/maintenance/export-archive", json={"reason": "ops_export_archive", "format": "csv"})
        assert resp.status_code == 400
        assert "unsupported export format" in resp.text

    @patch("routers.platform.get_platform_maintenance_service")
    def test_cleanup_archived_platform_maintenance(self, mock_get_service):
        svc = MagicMock()
        svc.cleanup_archive_retention.return_value = {
            "reason": "ops_cleanup_archive",
            "retention_days": 30,
            "dry_run": True,
            "cutoff": "2026-02-15T00:00:00",
            "candidate_runs": 0,
            "candidate_exports": 0,
            "deleted_runs": 0,
            "deleted_exports": 0,
            "deleted_export_files": [],
            "data_quality": {
                "suspect_history_count": 0,
                "raw_history_count": 140,
                "archived_history_count": 52,
                "visible_history_count": 88,
                "archive_export_count": 1,
                "last_archive_export_at": "2026-03-16T16:00:00",
                "last_archive_export_reason": "ops_export_archive",
                "last_archive_export_path": r"D:\workspace\ai_test_platform\data\platform_maintenance_exports\platform_maintenance_archive_ops_export_archive_20260316_160000.json",
                "last_archive_export_format": "json",
                "archive_export_fresh": True,
                "archive_retention_days": 30,
                "archive_cleanup_needed": False,
                "archive_cleanup_candidate_count": 0,
                "archive_run_cleanup_candidates": 0,
                "archive_export_cleanup_candidates": 0,
                "last_archive_cleanup_at": "2026-03-16T16:10:00",
                "last_archive_cleanup_reason": "ops_cleanup_archive",
                "last_archive_cleanup_dry_run": True,
                "last_archive_cleanup_deleted_runs": 0,
                "last_archive_cleanup_deleted_exports": 0,
                "clean": True,
                "summary": "Archived 52 maintenance history records; the latest export is complete",
            },
        }
        mock_get_service.return_value = svc

        resp = client.post("/api/platform/maintenance/cleanup-archive", json={"reason": "ops_cleanup_archive", "retention_days": 30, "dry_run": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["result"]["candidate_runs"] == 0
        svc.cleanup_archive_retention.assert_called_once_with(reason="ops_cleanup_archive", retention_days=30, dry_run=True)

    @patch("routers.platform.get_platform_readiness_service")
    @patch("routers.platform.get_commander_chatops_service")
    def test_platform_capabilities_contains_readiness_snapshot(self, mock_get_chatops_service, mock_get_readiness_service):
        readiness_svc = MagicMock()
        readiness_svc.evaluate.return_value = {"stage": "beta", "score": 72}
        mock_get_readiness_service.return_value = readiness_svc
        chatops_svc = MagicMock()
        chatops_svc.get_overview.return_value = {"ready": False, "platform_ready": False}
        mock_get_chatops_service.return_value = chatops_svc

        resp = client.get("/api/platform/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["readiness_snapshot"]["stage"] == "beta"
        assert data["readiness_snapshot"]["score"] == 72
        assert data["production_readiness"]["notification_platform_chatops_platform_ready"] is False
        assert data["production_readiness"]["notification_platform_chatops_bridge"] is False

    @patch("routers.platform.get_platform_remediation_service")
    def test_platform_remediation_endpoint(self, mock_get_remediation_service):
        remediation_svc = MagicMock()
        remediation_svc.evaluate.return_value = {
            "status": "attention",
            "summary": "Production readiness action items still need attention.",
            "counts": {"total": 2, "blocking": 1, "local": 1, "global": 1, "p0": 1, "p1": 1},
            "items": [
                {
                    "key": "notification_webhook",
                    "title": "Connect a production alert webhook",
                    "scope": "local",
                    "priority": "P0",
                    "blocking": True,
                    "route": "/notifications",
                    "summary": "No production alert webhook is currently enabled",
                    "impact": "impact",
                    "next_step": "step",
                    "evidence": {"webhook_count": 0},
                }
            ],
        }
        mock_get_remediation_service.return_value = remediation_svc

        resp = client.get("/api/platform/remediation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["remediation"]["counts"]["total"] == 2
        assert data["remediation"]["items"][0]["route"] == "/notifications"

    @patch("routers.platform.get_platform_maintenance_service")
    def test_run_platform_maintenance(self, mock_get_service):
        svc = MagicMock()
        svc.run.return_value = {"status": "success", "reason": "manual", "skipped": False}
        mock_get_service.return_value = svc

        resp = client.post("/api/platform/maintenance/run", json={"force": True, "reason": "ops"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["result"]["reason"] == "manual"
        svc.run.assert_called_once_with(force=True, reason="ops")


# ============================================================
# /api/knowledge — Knowledge base
# ============================================================
class TestKnowledgeAPI:
    @patch("routers.knowledge._get_kb")
    def test_knowledge_content_success(self, mock_get_kb):
        kb = MagicMock()
        kb.get_knowledge_item.return_value = {
            "id": "doc-1",
            "content": "hello",
            "metadata": {"filename": "demo.md"},
        }
        mock_get_kb.return_value = kb

        resp = client.get("/api/knowledge/doc-1/content")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["content"] == "hello"
        assert data["metadata"]["filename"] == "demo.md"

    @patch("routers.knowledge._get_kb")
    def test_knowledge_content_not_found(self, mock_get_kb):
        kb = MagicMock()
        kb.get_knowledge_item.return_value = None
        mock_get_kb.return_value = kb

        resp = client.get("/api/knowledge/missing/content")
        assert resp.status_code == 404

    @patch("routers.knowledge._get_kb")
    def test_knowledge_upload_success(self, mock_get_kb):
        kb = MagicMock()
        kb.ingest_file.return_value = True
        mock_get_kb.return_value = kb

        resp = client.post(
            "/api/knowledge/upload",
            files={"file": ("demo.md", io.BytesIO(b"# hello"), "text/markdown")},
            data={"description": "uploaded from test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        kb.ingest_file.assert_called_once()
        _, metadata = kb.ingest_file.call_args[0]
        assert metadata["description"] == "uploaded from test"
        assert metadata["original_filename"] == "demo.md"

    def test_knowledge_upload_rejects_pdf(self):
        resp = client.post(
            "/api/knowledge/upload",
            files={"file": ("demo.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
            data={"description": "pdf"},
        )
        assert resp.status_code == 400


class TestNotificationAPI:
    @patch("routers.notification.query_all")
    def test_notification_overview_reports_not_ready_when_no_healthy_webhook(self, mock_query_all):
        raw_url = "https://example.com/webhook?token=example-webhook-token"
        mock_query_all.return_value = [
            {
                "id": "wh_1",
                "name": "ops",
                "url": raw_url,
                "type": "custom",
                "enabled": 1,
                "last_test_at": "",
                "last_test_success": 0,
                "last_test_status": 0,
                "last_test_message": "",
            }
        ]

        resp = client.get("/api/notify/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overview"]["enabled"] == 1
        assert data["overview"]["production_ready"] is False
        assert data["overview"]["untested_enabled"] == 1
        assert data["webhooks"][0]["url"] != raw_url
        assert "example.com" in data["webhooks"][0]["url"]
        assert "example-webhook-token" not in data["webhooks"][0]["url"]
        assert "secret" not in data["webhooks"][0]

    @patch("routers.notification.query_all")
    def test_notification_list_webhooks_masks_url(self, mock_query_all):
        raw_url = "https://open.notification_platform.cn/open-apis/bot/v2/hook/b23a4f19-0226-4f5d-ba1d-8cfd33736e0b"
        mock_query_all.return_value = [
            {
                "id": "wh_1",
                "name": "ops",
                "url": raw_url,
                "type": "notification_platform",
                "enabled": 1,
                "secret": "top-secret",
                "last_test_at": "2026-03-18 10:00:00",
                "last_test_success": 1,
                "last_test_status": 200,
                "last_test_message": "Sent successfully",
                "created_at": "2026-03-18 10:00:00",
            }
        ]

        resp = client.get("/api/notify/webhooks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["webhooks"][0]["url"] != raw_url
        assert "open.notification_platform.cn" in data["webhooks"][0]["url"]
        assert "b23a4f19-0226-4f5d-ba1d-8cfd33736e0b" not in data["webhooks"][0]["url"]
        assert "secret" not in data["webhooks"][0]

    @patch("routers.notification.query_one")
    @patch("routers.notification.execute")
    def test_notification_create_webhook_returns_masked_url(self, mock_execute, mock_query_one):
        raw_url = "https://example.com/webhook?token=example-webhook-token"
        mock_query_one.return_value = {
            "id": "wh_1",
            "name": "ops",
            "url": raw_url,
            "type": "custom",
            "enabled": 1,
            "secret": "s3cr3t",
            "last_test_at": "",
            "last_test_success": 0,
            "last_test_status": 0,
            "last_test_message": "",
            "created_at": "2026-03-18 10:00:00",
        }

        resp = client.post("/api/notify/webhooks", json={
            "name": "ops",
            "url": raw_url,
            "type": "custom",
            "enabled": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["url"] != raw_url
        assert "example-webhook-token" not in data["url"]
        assert "secret" not in data
        mock_execute.assert_called_once()

    @patch("routers.notification.execute")
    @patch("routers.notification.query_one")
    @patch("routers.notification.httpx.AsyncClient")
    def test_notification_test_webhook_updates_last_test_status(self, mock_client_cls, mock_query_one, mock_execute):
        mock_query_one.return_value = {
            "id": "wh_1",
            "name": "ops",
            "url": "https://example.com/webhook",
            "type": "custom",
            "enabled": 1,
        }
        response = MagicMock()
        response.status_code = 200
        response.text = "ok"
        client_mock = AsyncMock()
        client_mock.post.return_value = response
        mock_client_cls.return_value.__aenter__.return_value = client_mock

        resp = client.post("/api/notify/webhooks/wh_1/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["message"] == "Sent successfully"
        mock_execute.assert_called_once()

    @patch("routers.notification.query_one")
    @patch("routers.notification.execute")
    def test_notification_update_webhook_can_toggle_enabled(self, mock_execute, mock_query_one):
        mock_query_one.side_effect = [
            {
                "id": "wh_1",
                "name": "ops",
                "url": "https://example.com/webhook",
                "type": "custom",
                "enabled": 1,
                "secret": None,
                "last_test_at": "2026-03-16T10:00:00",
                "last_test_success": 1,
                "last_test_status": 200,
                "last_test_message": "Sent successfully",
                "created_at": "2026-03-16T10:00:00",
            },
            {
                "id": "wh_1",
                "name": "ops",
                "url": "https://example.com/webhook",
                "type": "custom",
                "enabled": 0,
                "secret": None,
                "last_test_at": "2026-03-16T10:00:00",
                "last_test_success": 1,
                "last_test_status": 200,
                "last_test_message": "Sent successfully",
                "created_at": "2026-03-16T10:00:00",
            },
        ]

        resp = client.patch("/api/notify/webhooks/wh_1", json={"enabled": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False
        assert data["url"] != "https://example.com/webhook"
        assert "secret" not in data
        mock_execute.assert_called_once()
        sql = mock_execute.call_args.args[0]
        assert "last_test_at=''" not in sql

    @patch("routers.notification.query_one")
    @patch("routers.notification.execute")
    def test_notification_update_webhook_resets_test_status_when_endpoint_changes(self, mock_execute, mock_query_one):
        mock_query_one.side_effect = [
            {
                "id": "wh_1",
                "name": "ops",
                "url": "https://example.com/webhook",
                "type": "custom",
                "enabled": 1,
                "secret": None,
                "last_test_at": "2026-03-16T10:00:00",
                "last_test_success": 1,
                "last_test_status": 200,
                "last_test_message": "Sent successfully",
                "created_at": "2026-03-16T10:00:00",
            },
            {
                "id": "wh_1",
                "name": "ops",
                "url": "https://example.org/new-webhook",
                "type": "custom",
                "enabled": 1,
                "secret": None,
                "last_test_at": "",
                "last_test_success": 0,
                "last_test_status": 0,
                "last_test_message": "",
                "created_at": "2026-03-16T10:00:00",
            },
        ]

        resp = client.patch("/api/notify/webhooks/wh_1", json={"url": "https://example.org/new-webhook"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["last_test_at"] == ""
        assert data["last_test_success"] is False
        assert data["url"] != "https://example.org/new-webhook"
        assert "new-webhook" not in data["url"]
        mock_execute.assert_called_once()
        sql = mock_execute.call_args.args[0]
        assert "last_test_at=''" in sql

    @patch("routers.notification.query_all")
    def test_notification_drill_handles_no_enabled_webhooks(self, mock_query_all):
        mock_query_all.return_value = []

        resp = client.post("/api/notify/drill", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] == 0
        assert data["delivered"] == 0
        assert "cannot run an alert drill" in data["summary"]

    @patch("routers.notification.execute")
    @patch("routers.notification.query_all")
    @patch("routers.notification.httpx.AsyncClient")
    def test_notification_drill_sends_enabled_webhooks(self, mock_client_cls, mock_query_all, mock_execute):
        mock_query_all.return_value = [
            {
                "id": "wh_1",
                "name": "ops",
                "url": "https://example.com/webhook",
                "type": "custom",
                "enabled": 1,
            }
        ]
        response = MagicMock()
        response.status_code = 200
        client_mock = AsyncMock()
        client_mock.post.return_value = response
        mock_client_cls.return_value.__aenter__.return_value = client_mock

        resp = client.post("/api/notify/drill", json={"title": "Platform alert drill"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] == 1
        assert data["delivered"] == 1
        assert data["results"][0]["message"] == "Sent successfully"
        assert mock_execute.called


class TestCommanderWebhookAPI:
    @pytest.fixture(autouse=True)
    def _isolate_chatops_event_recording(self):
        with patch("routers.commander._record_chatops_event"):
            yield

    @patch.dict("os.environ", {"NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT": "", "PUBLIC_API_BASE_URL_UPDATED_AT": ""}, clear=False)
    @patch.object(Config, "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token")
    @patch.object(Config, "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", "")
    @patch.object(Config, "NOTIFICATION_PLATFORM_APP_ID", "cli_demo_bot")
    @patch.object(Config, "NOTIFICATION_PLATFORM_APP_SECRET", "secret-demo")
    @patch.object(Config, "PUBLIC_API_BASE_URL", "https://callback.example.com")
    @patch.object(Config, "PUBLIC_API_BASE_URL_UPDATED_AT", "")
    @patch("services.commander_chatops_service.CommanderChatOpsService._probe_callback_url")
    @patch("services.commander_chatops_service.query_all")
    def test_commander_chatops_overview(self, mock_query_all, mock_probe_callback):
        mock_probe_callback.return_value = {
            "attempted": True,
            "success": True,
            "issue": "",
            "summary": "The public callback URL passed its active probe and is externally reachable.",
            "status_code": 200,
            "content_type": "application/json",
            "response_excerpt": '{"challenge":"chatops-probe"}',
            "probed_at": "2026-03-18T11:10:05",
        }
        mock_query_all.side_effect = [
            [
                {
                    "id": 2,
                    "channel": "notification_platform",
                    "source": "event_subscription",
                    "event_type": "message",
                    "message": "health",
                    "from_user": "ou_demo",
                    "chat_id": "oc_demo",
                    "response": "🟢 Agent fleet status: 6/6 agents online",
                    "status": "ok",
                    "delivery_configured": 1,
                    "delivery_delivered": 1,
                    "delivery_failed": 0,
                    "created_at": "2026-03-18 11:10:00",
                },
                {
                    "id": 1,
                    "channel": "notification_platform",
                    "source": "event_subscription",
                    "event_type": "url_verification",
                    "message": "url_verification",
                    "from_user": "",
                    "chat_id": "",
                    "response": "challenge accepted",
                    "status": "verified",
                    "delivery_configured": 0,
                    "delivery_delivered": 0,
                    "delivery_failed": 0,
                    "created_at": "2026-03-18 11:09:00",
                }
            ],
            [
                {
                    "id": "wh_1",
                    "name": "NotificationPlatform Production Alert",
                    "enabled": 1,
                    "last_test_success": 1,
                }
            ],
            [],
            [],
            [],
        ]

        resp = client.get("/api/commander/chatops/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["overview"]["channel"] == "notification_platform"
        assert data["overview"]["ready"] is True
        assert data["overview"]["platform_ready"] is True
        assert data["overview"]["external_connected"] is True
        assert data["overview"]["external_connected_history_observed"] is True
        assert data["overview"]["external_connection_stale"] is False
        assert data["overview"]["subscription_endpoint_verified"] is True
        assert data["overview"]["verification_token_configured"] is True
        assert data["overview"]["verification_token_masked"] == "demo...oken"
        assert data["overview"]["healthy_notification_platform_webhook_count"] == 1
        assert data["overview"]["latest_event"]["message"] == "health"
        assert data["overview"]["latest_event"]["delivery_delivered"] == 1
        assert data["overview"]["latest_successful_event"]["message"] == "health"

    @patch.dict("os.environ", {"NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT": "", "PUBLIC_API_BASE_URL_UPDATED_AT": ""}, clear=False)
    @patch.object(Config, "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token")
    @patch.object(Config, "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", "")
    @patch.object(Config, "NOTIFICATION_PLATFORM_APP_ID", "cli_demo_bot")
    @patch.object(Config, "NOTIFICATION_PLATFORM_APP_SECRET", "secret-demo")
    @patch.object(Config, "PUBLIC_API_BASE_URL", "https://callback.example.com")
    @patch.object(Config, "PUBLIC_API_BASE_URL_UPDATED_AT", "")
    @patch("services.commander_chatops_service.CommanderChatOpsService._probe_callback_url")
    @patch("services.commander_chatops_service.query_all")
    def test_commander_chatops_overview_prefers_success_summary_when_latest_is_ignored(self, mock_query_all, mock_probe_callback):
        mock_probe_callback.return_value = {
            "attempted": True,
            "success": True,
            "issue": "",
            "summary": "The public callback URL passed its active probe and is externally reachable.",
            "status_code": 200,
            "content_type": "application/json",
            "response_excerpt": '{"challenge":"chatops-probe"}',
            "probed_at": "2026-03-18T11:10:05",
        }
        mock_query_all.side_effect = [
            [
                {
                    "id": 3,
                    "channel": "notification_platform",
                    "source": "event_subscription",
                    "event_type": "message",
                    "message": "[image]",
                    "from_user": "",
                    "chat_id": "oc_demo",
                    "response": "unsupported_message_type",
                    "status": "ignored",
                    "delivery_configured": 0,
                    "delivery_delivered": 0,
                    "delivery_failed": 0,
                    "created_at": "2026-03-18 11:10:00",
                },
                {
                    "id": 2,
                    "channel": "notification_platform",
                    "source": "event_subscription",
                    "event_type": "message",
                    "message": "health",
                    "from_user": "ou_demo",
                    "chat_id": "oc_demo",
                    "response": "🟢 Agent fleet status: 6/6 agents online",
                    "status": "ok",
                    "delivery_configured": 1,
                    "delivery_delivered": 1,
                    "delivery_failed": 0,
                    "created_at": "2026-03-18 11:09:00",
                },
                {
                    "id": 1,
                    "channel": "notification_platform",
                    "source": "event_subscription",
                    "event_type": "url_verification",
                    "message": "url_verification",
                    "from_user": "",
                    "chat_id": "",
                    "response": "challenge accepted",
                    "status": "verified",
                    "delivery_configured": 0,
                    "delivery_delivered": 0,
                    "delivery_failed": 0,
                    "created_at": "2026-03-18 11:08:00",
                },
            ],
            [
                {
                    "id": "wh_1",
                    "name": "NotificationPlatform Production Alert",
                    "enabled": 1,
                    "last_test_success": 1,
                }
            ],
            [],
            [],
            [],
        ]

        resp = client.get("/api/commander/chatops/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overview"]["latest_event"]["status"] == "ignored"
        assert data["overview"]["latest_successful_event"]["message"] == "health"
        assert "the latest text command was still successfully sent back" in data["overview"]["summary"]

    @patch.dict("os.environ", {"NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN": "", "PUBLIC_API_BASE_URL": "https://callback.example.com"}, clear=False)
    @patch.object(Config, "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "")
    @patch.object(Config, "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", "")
    @patch.object(Config, "PUBLIC_API_BASE_URL", "https://callback.example.com")
    @patch("services.commander_chatops_service.query_all")
    def test_commander_chatops_overview_marks_not_ready_when_token_missing(self, mock_query_all):
        mock_query_all.side_effect = [
            [],
            [
                {
                    "id": "wh_1",
                    "name": "NotificationPlatform Production Alert",
                    "enabled": 1,
                    "last_test_success": 1,
                }
            ],
            [],
            [],
            [],
        ]

        resp = client.get("/api/commander/chatops/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overview"]["webhook_ready"] is True
        assert data["overview"]["ready"] is False
        assert data["overview"]["platform_ready"] is False
        assert data["overview"]["verification_token_configured"] is False
        assert "verification token" in data["overview"]["summary"]

    @patch.object(Config, "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token")
    def test_notification_platform_url_verification_returns_challenge(self):
        resp = client.post("/api/commander/notification_platform/events", json={
            "type": "url_verification",
            "challenge": "challenge-token",
            "token": "demo-token",
        })
        assert resp.status_code == 200
        assert resp.json()["challenge"] == "challenge-token"

    @patch("routers.commander._deliver_commander_response", new_callable=AsyncMock)
    @patch("routers.commander._handle_commander_chat_message", new_callable=AsyncMock)
    def test_notification_platform_message_event_dispatches_and_pushes_reply(self, mock_handle_message, mock_deliver_reply):
        mock_handle_message.return_value = {"response": "🟢 Agent fleet status: 1/1 agents online"}
        mock_deliver_reply.return_value = {
            "configured": 2,
            "delivered": 1,
            "failed": 0,
            "sender": "app_bot",
            "mode": "app_bot",
            "fallback_used": False,
            "message": "The notification platform app bot has replied.",
            "failures": [],
        }

        resp = client.post("/api/commander/notification_platform/events", json={
            "schema": "2.0",
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "sender": {"sender_id": {"open_id": "ou_demo"}},
                "message": {
                    "message_type": "text",
                    "chat_id": "oc_demo",
                    "content": "{\"text\":\"状态\"}",
                },
            },
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["message"] == "状态"
        assert data["result"]["response"] == "🟢 Agent fleet status: 1/1 agents online"
        assert data["delivery"]["delivered"] == 1
        mock_handle_message.assert_awaited_once_with("状态", from_user="ou_demo", chat_id="oc_demo")
        mock_deliver_reply.assert_awaited_once_with("🟢 Agent fleet status: 1/1 agents online", chat_id="oc_demo")

    @patch("services.commander_chatops_service.query_all")
    @patch("routers.commander._deliver_commander_response", new_callable=AsyncMock)
    @patch("routers.commander._handle_commander_chat_message", new_callable=AsyncMock)
    def test_commander_chatops_simulate(self, mock_handle_message, mock_deliver_reply, mock_query_all):
        mock_handle_message.return_value = {"response": "🟢 Agent fleet status: 1/1 agents online"}
        mock_deliver_reply.return_value = {
            "configured": 2,
            "delivered": 1,
            "failed": 0,
            "sender": "app_bot",
            "mode": "app_bot",
            "fallback_used": False,
            "message": "The notification platform app bot has replied.",
        }
        mock_query_all.side_effect = [
            [],
            [
                {"id": "wh_1", "name": "NotificationPlatform Production Alert", "enabled": 1, "last_test_success": 1},
            ],
            [],
            [],
            [],
        ]

        resp = client.post("/api/commander/chatops/simulate", json={
            "message": "状态",
            "from_user": "tester",
            "chat_id": "debug_chat",
            "deliver": True,
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["result"]["response"] == "🟢 Agent fleet status: 1/1 agents online"
        assert data["delivery"]["delivered"] == 1
        mock_handle_message.assert_awaited_once_with("状态", from_user="tester", chat_id="debug_chat")
        mock_deliver_reply.assert_awaited_once_with("🟢 Agent fleet status: 1/1 agents online", chat_id="debug_chat")

    @patch("routers.commander._get_chatops_overview")
    @patch("core.agent_profile.get_profile_manager")
    @patch("core.agent_bus.get_agent_bus")
    @patch("agents.commander.get_commander")
    def test_commander_chatops_simulate_status_uses_registered_agents_and_explains_idle_heartbeat(
        self,
        mock_get_commander,
        mock_get_agent_bus,
        mock_get_profile_manager,
        mock_get_chatops_overview,
    ):
        mock_get_commander.return_value = MagicMock()
        bus = MagicMock()
        bus.get_health.return_value = [
            {"name": "ui_squad", "healthy": False, "active": True},
            {"name": "api_squad", "healthy": False, "active": True},
            {"name": "sec_squad", "healthy": False, "active": True},
            {"name": "perf_squad", "healthy": False, "active": True},
            {"name": "data_squad", "healthy": False, "active": True},
            {"name": "commander", "healthy": False, "active": True},
        ]
        mock_get_agent_bus.return_value = bus
        profile_manager = MagicMock()
        profile_manager.list_all.return_value = [MagicMock() for _ in range(6)]
        mock_get_profile_manager.return_value = profile_manager
        mock_get_chatops_overview.return_value = {
            "ready": False,
            "platform_ready": True,
            "summary": "The platform is ready; notification platform integration testing is pending.",
        }

        resp = client.post("/api/commander/chatops/simulate", json={
            "message": "状态",
            "from_user": "tester",
            "chat_id": "debug_chat",
            "deliver": False,
        })

        assert resp.status_code == 200
        data = resp.json()
        message = data["result"]["response"]
        assert "Registered agents: 6" in message
        assert "Healthy heartbeats: 0/6" in message
        assert "zero is normal when idle" in message
        assert "Notification platform two-way connection: Platform ready; notification platform integration pending" in message

    def test_commander_chatops_simulate_greeting_returns_help_instead_of_starting_swarm(self):
        resp = client.post("/api/commander/chatops/simulate", json={
            "message": "Hello",
            "from_user": "tester",
            "chat_id": "debug_chat",
            "deliver": False,
        })

        assert resp.status_code == 200
        data = resp.json()
        message = data["result"]["response"]
        assert "testing platform's legion bot" in message
        assert "status" in message
        assert "report <mission-id>" in message
        assert "test <URL/requirements>" in message

    def test_notification_platform_message_event_ignores_empty_text_payload(self):
        resp = client.post("/api/commander/notification_platform/events", json={
            "schema": "2.0",
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "message": {
                    "message_type": "text",
                    "chat_id": "oc_demo",
                    "content": "{}",
                },
            },
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ignored"
        assert data["reason"] == "empty_message"

    @patch("routers.commander.Config.set_notification_platform_event_verification_token")
    @patch("routers.commander.get_commander_chatops_service")
    def test_commander_chatops_config_token(self, mock_get_chatops_service, mock_set_token):
        mock_set_token.return_value = {
            "verification_token_configured": True,
            "verification_token_updated_at": "2026-03-18T12:00:00",
        }
        chatops_svc = MagicMock()
        chatops_svc.get_overview.return_value = {
            "ready": False,
            "platform_ready": False,
            "webhook_ready": True,
            "external_connected": False,
            "subscription_endpoint_verified": False,
            "verification_token_configured": True,
            "verification_token_masked": "demo...oken",
            "verification_token_updated_at": "2026-03-18T12:00:00",
        }
        mock_get_chatops_service.return_value = chatops_svc

        resp = client.post("/api/commander/chatops/config/token", json={"verification_token": "demo-token"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["token"] == "demo-token"
        assert data["token_masked"] == "demo...oken"
        mock_set_token.assert_called_once_with("demo-token")

    @patch("routers.commander.Config.update_runtime_env")
    @patch("routers.commander._get_chatops_overview")
    def test_commander_chatops_config_callback_url(self, mock_get_overview, mock_update_runtime_env):
        mock_get_overview.return_value = {
            "callback_url": "https://ops.example.com/api/commander/notification_platform/events",
            "callback_url_public": True,
            "callback_url_updated_at": "2026-03-18 08:45:00",
            "platform_ready": False,
            "ready": False,
        }

        resp = client.post("/api/commander/chatops/config/callback-url", json={"public_api_base_url": "https://ops.example.com/"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["public_api_base_url"] == "https://ops.example.com"
        assert data["public_api_base_url_updated_at"]
        assert data["callback_url"] == "https://ops.example.com/api/commander/notification_platform/events"
        assert data["callback_url_public"] is True
        mock_update_runtime_env.assert_called_once()
        updates = mock_update_runtime_env.call_args.args[0]
        assert updates["PUBLIC_API_BASE_URL"] == "https://ops.example.com"
        assert updates["PUBLIC_API_BASE_URL_UPDATED_AT"]

    def test_commander_chatops_config_callback_url_rejects_invalid_value(self):
        resp = client.post("/api/commander/chatops/config/callback-url", json={"public_api_base_url": "not-a-url"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "http" in data["message"]

    @patch("routers.commander._get_chatops_overview")
    @patch("routers.commander._record_app_bot_check")
    @patch("routers.commander._get_notification_platform_tenant_access_token", new_callable=AsyncMock)
    @patch("routers.commander.Config.set_notification_platform_app_bot_credentials")
    def test_commander_chatops_config_app_bot_runs_validation(
        self,
        mock_set_credentials,
        mock_get_token,
        mock_record_check,
        mock_get_overview,
    ):
        mock_set_credentials.return_value = {
            "app_bot_configured": True,
            "app_bot_updated_at": "2026-03-19 11:20:00",
        }
        mock_get_token.return_value = {
            "ok": True,
            "message": "App bot credentials validated; tenant_access_token obtained successfully.",
            "status_code": 200,
            "app_id_masked": "cli...bot",
            "app_bot_configured": True,
        }
        mock_get_overview.return_value = {
            "app_bot_id_masked": "cli...bot",
            "app_bot_ready": True,
        }

        resp = client.post("/api/commander/chatops/config/app-bot", json={
            "app_id": "cli_demo_bot",
            "app_secret": "secret-demo",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["app_bot_configured"] is True
        assert data["validation"]["ok"] is True
        assert "tenant_access_token" in data["validation"]["message"]
        mock_record_check.assert_called_once()
        mock_get_token.assert_awaited_once()

    @patch("routers.commander._get_chatops_overview")
    @patch("routers.commander._purge_app_bot_state")
    @patch("routers.commander.Config.set_notification_platform_app_bot_credentials")
    def test_commander_chatops_unbind_app_bot(
        self,
        mock_set_credentials,
        mock_purge,
        mock_get_overview,
    ):
        mock_set_credentials.return_value = {
            "app_bot_configured": False,
            "app_bot_updated_at": "2026-03-19 11:30:00",
        }
        mock_purge.return_value = {
            "checks_removed": 2,
            "bindings_removed": 1,
            "events_removed": 3,
        }
        mock_get_overview.return_value = {
            "app_bot_configured": False,
            "delivery_strategy": "webhook_only",
        }

        resp = client.post("/api/commander/chatops/config/app-bot/unbind", json={"purge_history": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["app_bot_configured"] is False
        assert data["purged"]["checks_removed"] == 2
        assert data["purged"]["bindings_removed"] == 1
        assert data["purged"]["events_removed"] == 3
        mock_set_credentials.assert_called_once_with("", "")
        mock_purge.assert_called_once_with(True)

    @patch("routers.commander._get_chatops_overview")
    @patch("routers.commander._record_app_bot_check")
    @patch("routers.commander._get_notification_platform_tenant_access_token", new_callable=AsyncMock)
    def test_commander_chatops_app_bot_self_check(
        self,
        mock_get_token,
        mock_record_check,
        mock_get_overview,
    ):
        mock_get_token.return_value = {
            "ok": False,
            "message": "invalid app credentials",
            "status_code": 401,
            "app_id_masked": "cli...bad",
            "app_bot_configured": True,
        }
        mock_get_overview.return_value = {
            "app_bot_configured": True,
            "app_bot_ready": False,
        }

        resp = client.post("/api/commander/chatops/app-bot-self-check")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert data["validation"]["ok"] is False
        assert data["validation"]["status_code"] == 401
        mock_record_check.assert_called_once()
        mock_get_token.assert_awaited_once()

    @patch("routers.commander.get_commander_chatops_service")
    def test_commander_chatops_probe_refresh(self, mock_get_chatops_service):
        service = MagicMock()
        service.refresh_callback_probe.return_value = {
            "probe": {
                "attempted": True,
                "success": False,
                "issue": "connect_error",
                "summary": "Public callback URL probe failed: ConnectionError",
                "status_code": None,
                "content_type": "",
                "response_excerpt": "",
                "probed_at": "2026-03-18T13:00:00",
            },
            "overview": {
                "callback_probe_history": [
                    {
                        "id": 3,
                        "callback_url": "https://ops.example.com/api/commander/notification_platform/events",
                        "attempted": True,
                        "success": False,
                        "issue": "connect_error",
                        "summary": "Public callback URL probe failed: ConnectionError",
                        "status_code": None,
                        "content_type": "",
                        "response_excerpt": "",
                        "source": "manual_refresh",
                        "force_refresh": True,
                        "created_at": "2026-03-18 13:00:00",
                    }
                ],
            },
        }
        mock_get_chatops_service.return_value = service

        resp = client.post("/api/commander/chatops/probe-refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["probe"]["issue"] == "connect_error"
        assert data["overview"]["callback_probe_history"][0]["source"] == "manual_refresh"
        service.refresh_callback_probe.assert_called_once()

    @patch("routers.commander.get_commander_chatops_service")
    def test_commander_chatops_local_tunnel_restart(self, mock_get_chatops_service):
        service = MagicMock()
        service.restart_local_tunnel.return_value = {
            "ok": True,
            "message": "The local reverse tunnel has restarted.",
            "stdout": "native_ssh_reverse_tunnel_pid=4321",
            "stderr": "",
            "tunnel": {
                "supported": True,
                "script_exists": True,
                "running": True,
                "pid": 4321,
                "status": "running",
                "summary": "Detected a local OpenSSH reverse tunnel process (PID 4321).",
            },
            "overview": {
                "local_tunnel": {
                    "running": True,
                    "pid": 4321,
                    "status": "running",
                },
            },
        }
        mock_get_chatops_service.return_value = service

        resp = client.post("/api/commander/chatops/local-tunnel/restart")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["ok"] is True
        assert data["message"] == "The local reverse tunnel has restarted."
        assert data["tunnel"]["running"] is True
        assert data["tunnel"]["pid"] == 4321
        assert data["overview"]["local_tunnel"]["running"] is True
        service.restart_local_tunnel.assert_called_once()

    @patch("routers.commander._get_chatops_overview")
    @patch("routers.commander._process_notification_platform_event", new_callable=AsyncMock)
    @patch("routers.commander.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token")
    def test_commander_chatops_subscription_self_check(self, mock_process_event, mock_get_overview):
        mock_process_event.return_value = {"challenge": "codex-self-check"}
        mock_get_overview.return_value = {"platform_ready": True, "ready": False}

        resp = client.post("/api/commander/chatops/subscription-self-check", json={"challenge": "codex-self-check"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["result"]["challenge"] == "codex-self-check"
        mock_process_event.assert_awaited_once()

    def test_commander_chatops_external_self_check(self):
        from routers.commander import commander_chatops_external_self_check

        class FakeResponse:
            def __init__(self, status_code: int, body):
                self.status_code = status_code
                self._body = body
                self.text = json.dumps(body, ensure_ascii=False)
                self.is_success = 200 <= status_code < 300

            def json(self):
                return self._body

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, json):
                if json.get("type") == "url_verification":
                    return FakeResponse(200, {"challenge": json.get("challenge")})
                return FakeResponse(200, {
                    "status": "ok",
                    "result": {"response": "📡 Agent fleet status\n• Registered agents: 6\n• Healthy heartbeats: 6/6"},
                    "delivery": {"configured": 1, "delivered": 1, "failed": 0},
                })

        with patch("routers.commander.secrets.token_hex", side_effect=["abcd1234", "event5678"]), \
             patch("routers.commander._get_chatops_overview", side_effect=[
                 {
                     "callback_url": "https://ops.example.com/api/commander/notification_platform/events",
                     "callback_url_public": True,
                     "verification_token_configured": True,
                     "platform_ready": True,
                     "ready": False,
                 },
                 {
                     "callback_url": "https://ops.example.com/api/commander/notification_platform/events",
                     "callback_url_public": True,
                     "verification_token_configured": True,
                     "platform_ready": True,
                     "external_connected": False,
                     "ready": False,
                 },
             ]) as mock_get_overview, \
             patch("routers.commander.httpx.AsyncClient", FakeAsyncClient), \
             patch("routers.commander.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token"):
            data = asyncio.run(commander_chatops_external_self_check())
        assert data["status"] == "success", data
        assert data["callback_url"] == "https://ops.example.com/api/commander/notification_platform/events"
        assert data["challenge"] == "external-self-check-abcd1234"
        assert data["challenge_check"]["ok"] is True
        assert data["challenge_check"]["challenge_matched"] is True
        assert data["message_check"]["ok"] is True
        assert data["message_check"]["delivery"]["delivered"] == 1
        assert "Agent fleet status" in data["message_check"]["command_response"]
        assert data["overview"]["callback_url"] == "https://ops.example.com/api/commander/notification_platform/events"
        assert mock_get_overview.call_count == 2

    def test_notification_platform_message_event_ignores_non_text_messages(self):
        resp = client.post("/api/commander/notification_platform/events", json={
            "schema": "2.0",
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "message": {
                    "message_type": "image",
                    "chat_id": "oc_demo",
                    "content": "{}",
                },
            },
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ignored"
        assert data["reason"] == "unsupported_message_type"


# ============================================================
# /api/start + /api/stop — Execution lifecycle
# ============================================================
class TestStartStopLifecycle:
    """Test task start/stop endpoint behavior.
    Note: /api/start starts the actual orchestrator and Playwright browser thread,
    so it cannot be called safely through TestClient. The complete start lifecycle
    is covered with a real httpx connection in test_execution_lifecycle.py.
    """

    def test_start_missing_requirement(self):
        """A missing requirement field should return 422."""
        resp = client.post("/api/start", json={})
        assert resp.status_code == 422

    def test_stop_always_returns_stopped(self):
        """The stop endpoint should always return stopped status."""
        resp = client.post("/api/stop")
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"


# ============================================================
# /api/status — System status
# ============================================================
class TestStatusEndpoint:

    def test_status_returns_all_fields(self):
        """The status endpoint should return all required fields."""
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        for field in ("status", "signal", "is_running", "has_browser", "active_task_id"):
            assert field in data, f"Missing field: {field}"

    def test_status_signal_valid_values(self):
        """Signal values should remain within the valid range."""
        resp = client.get("/api/status")
        data = resp.json()
        assert data["signal"] in ("RUNNING", "PAUSED", "STOPPED", "INTERVENTION")


# ============================================================
# /api/stream — SSE log stream
# ============================================================
class TestStreamEndpoint:

    def test_stream_content_type(self):
        """The SSE endpoint should return text/event-stream."""
        resp = client.get("/api/stream")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_stream_with_last_event_id(self):
        """Support reconnection with Last-Event-ID."""
        resp = client.get("/api/stream", headers={"Last-Event-ID": "5"})
        assert resp.status_code == 200


# ============================================================
# /api/control/* — Control endpoints
# ============================================================
class TestControlEndpoints:

    def test_pause(self):
        """Pause should return the PAUSED signal."""
        resp = client.post("/api/control/pause")
        assert resp.status_code == 200
        assert resp.json()["signal"] == "PAUSED"
        assert client.get("/api/status").json()["signal"] == "PAUSED"

    def test_resume(self):
        """Resume should return the RUNNING signal."""
        resp = client.post("/api/control/resume")
        assert resp.status_code == 200
        assert resp.json()["signal"] == "RUNNING"
        assert client.get("/api/status").json()["signal"] == "RUNNING"

    def test_suspend_with_reason(self):
        """Suspend should accept the reason parameter."""
        resp = client.post("/api/control/suspend", json={"reason": "Paused for a CAPTCHA scenario"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["signal"] == "PAUSED"
        assert "CAPTCHA" in data["reason"]
        assert client.get("/api/status").json()["pause_reason"] == "Paused for a CAPTCHA scenario"

    def test_control_stop(self):
        """Control stop should return the STOPPED signal."""
        resp = client.post("/api/control/stop")
        assert resp.status_code == 200
        assert resp.json()["signal"] == "STOPPED"

    def test_pause_resume_lifecycle(self):
        """Complete pause/resume lifecycle."""
        client.post("/api/control/pause")
        assert client.get("/api/status").json()["signal"] == "PAUSED"
        client.post("/api/control/resume")
        assert client.get("/api/status").json()["signal"] == "RUNNING"



# ============================================================
# /api/session/bootstrap-auth — Session preauthentication injection
# ============================================================
class TestSessionBootstrapAPI:
    @patch("routers.session_bootstrap.session_manager")
    @patch("routers.session_bootstrap.apply_auth_bootstrap")
    def test_bootstrap_auth_store_only(self, mock_apply, mock_sm):
        session = MagicMock()
        session.get_page.return_value = None
        mock_sm.get_session.return_value = session

        resp = client.post("/api/session/bootstrap-auth", json={
            "session_id": "svc-test",
            "base_url": "http://127.0.0.1:81",
            "username": "example-org",
            "password": "123456"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["data"]["stored"] is True
        assert data["data"]["applied"] is False
        mock_apply.assert_not_called()

    @patch("routers.session_bootstrap.session_manager")
    @patch("routers.session_bootstrap.apply_auth_bootstrap")
    def test_bootstrap_auth_apply_now(self, mock_apply, mock_sm):
        session = MagicMock()
        session.get_page.return_value = object()
        session.run_browser = AsyncMock(return_value={"target_url": "http://127.0.0.1:81/unifiedGoodService/uniProductService"})
        mock_sm.get_session.return_value = session

        resp = client.post("/api/session/bootstrap-auth", json={
            "session_id": "svc-test",
            "base_url": "http://127.0.0.1:81",
            "username": "example-org",
            "password": "123456",
            "apply_now": True,
            "target_path": "/unifiedGoodService/uniProductService"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["applied"] is True
        assert data["data"]["result"]["target_url"].endswith("/unifiedGoodService/uniProductService")
        session.run_browser.assert_awaited_once()
