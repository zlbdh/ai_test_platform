"""
CICDIntegrationService 单元测试
覆盖: 数据类, 配置管理, Webhook验证, 触发器/历史,
      JUnit XML/HTML 报告生成, 单例
"""
import asyncio
import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path
from xml.etree import ElementTree as ET

from services.cicd_integration import (
    CICDConfig, TriggerRecord, TestCaseResult,
    CICDIntegrationService
)


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------
class TestCICDConfig:
    def test_defaults(self):
        cfg = CICDConfig()
        assert cfg.enabled is True
        assert cfg.notify_on_complete is True
        assert len(cfg.webhook_secret) > 10


class TestTriggerRecord:
    def test_defaults(self):
        r = TriggerRecord()
        assert r.status == "pending"
        assert r.source == "manual"


class TestTestCaseResult:
    def test_creation(self):
        tc = TestCaseResult(name="test1", classname="Module", time=0.5, status="passed")
        assert tc.name == "test1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def svc(tmp_path):
    """隔离的 CICDIntegrationService"""
    with patch("services.cicd_integration.CONFIG_FILE", tmp_path / "cfg.json"), \
         patch("services.cicd_integration.HISTORY_FILE", tmp_path / "history.json"), \
         patch("services.cicd_integration.REPORTS_DIR", tmp_path / "reports"), \
         patch("asyncio.ensure_future") as mock_ensure_future:
        (tmp_path / "reports").mkdir(exist_ok=True)
        def schedule_stub(coro):
            task = MagicMock()
            task.cancel = MagicMock()
            task.done.return_value = False
            coro.close()
            return task
        mock_ensure_future.side_effect = schedule_stub
        s = CICDIntegrationService()
        yield s


@pytest.fixture
def svc_with_reports(tmp_path):
    """包含报告目录 patch 的 service"""
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(exist_ok=True)
    with patch("services.cicd_integration.CONFIG_FILE", tmp_path / "cfg.json"), \
         patch("services.cicd_integration.HISTORY_FILE", tmp_path / "history.json"), \
         patch("services.cicd_integration.REPORTS_DIR", reports_dir), \
         patch("asyncio.ensure_future") as mock_ensure_future:
        def schedule_stub(coro):
            task = MagicMock()
            task.cancel = MagicMock()
            task.done.return_value = False
            coro.close()
            return task
        mock_ensure_future.side_effect = schedule_stub
        s = CICDIntegrationService()
        yield s, reports_dir


# ---------------------------------------------------------------------------
# 配置管理
# ---------------------------------------------------------------------------
class TestConfigManagement:
    def test_get_config(self, svc):
        cfg = svc.get_config()
        assert "webhook_url" in cfg
        assert cfg["enabled"] is True
        assert "..." in cfg["webhook_secret"]  # 掩码

    def test_update_config(self, svc):
        cfg = svc.update_config({"enabled": False})
        assert cfg["enabled"] is False

    def test_regenerate_secret(self, svc):
        old = svc.config.webhook_secret
        svc.update_config({"regenerate_secret": True})
        assert svc.config.webhook_secret != old

    def test_get_full_secret(self, svc):
        secret = svc.get_full_secret()
        assert len(secret) > 10
        assert "..." not in secret


# ---------------------------------------------------------------------------
# Webhook 验证
# ---------------------------------------------------------------------------
class TestWebhookVerification:
    def test_verify_valid(self, svc):
        import hashlib
        payload = '{"action":"test"}'
        sig = hashlib.sha256(
            (svc.config.webhook_secret + payload).encode()
        ).hexdigest()
        assert svc.verify_webhook(sig, payload) is True

    def test_verify_invalid(self, svc):
        assert svc.verify_webhook("bad_sig", "payload") is False

    def test_verify_empty_secret(self, svc):
        svc.config.webhook_secret = ""
        assert svc.verify_webhook("anything", "payload") is True


# ---------------------------------------------------------------------------
# 触发器 / 历史
# ---------------------------------------------------------------------------
class TestTrigger:
    def test_trigger_test(self, svc):
        record = svc.trigger_test("jenkins", ref="main", commit="abc123")
        assert record.source == "jenkins"
        assert record.status == "running"
        assert len(svc.history) == 1

    def test_update_status(self, svc):
        record = svc.trigger_test("manual")
        updated = svc.update_trigger_status(record.id, "passed", {
            "total": 10, "passed": 9, "failed": 1, "duration_ms": 500
        })
        assert updated.status == "passed"
        assert updated.test_count == 10

    def test_update_nonexistent(self, svc):
        assert svc.update_trigger_status("none", "passed") is None

    def test_get_trigger(self, svc):
        record = svc.trigger_test("github")
        found = svc.get_trigger(record.id)
        assert found is not None
        assert found["source"] == "github"

    def test_get_trigger_not_found(self, svc):
        assert svc.get_trigger("none") is None

    def test_get_history(self, svc):
        svc.trigger_test("a")
        svc.trigger_test("b")
        svc.trigger_test("c")
        history = svc.get_trigger_history(limit=2)
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_run_commander_uses_supported_signature(self, svc):
        record = svc.trigger_test("manual")
        commander = MagicMock()
        commander.run = AsyncMock(return_value={
            "mission_id": "mission-1",
            "summary": {"total": 4, "passed": 4, "failed": 0, "duration_ms": 321},
        })

        with patch("agents.commander.get_commander", return_value=commander):
            await svc._run_commander(record, {
                "requirement": "回归测试",
                "target_url": "http://example.com",
                "parallel": False,
                "timeout_seconds": 321,
            })

        commander.run.assert_awaited_once_with(
            user_input="回归测试",
            target_url="http://example.com",
            parallel=False,
            timeout_seconds=321,
        )
        assert record.status == "completed"
        assert record.task_id == "mission-1"


# ---------------------------------------------------------------------------
# 报告生成
# ---------------------------------------------------------------------------
class TestReportGeneration:
    def _make_test_results(self):
        return [
            TestCaseResult("test_login", "Auth", 0.1, "passed"),
            TestCaseResult("test_fail", "Auth", 0.2, "failed", message="fail msg", stacktrace="trace"),
            TestCaseResult("test_error", "Auth", 0.3, "error", message="err msg"),
            TestCaseResult("test_skip", "Auth", 0.0, "skipped", message="skip reason")
        ]

    def test_junit_xml(self, svc_with_reports):
        svc, reports_dir = svc_with_reports
        record = svc.trigger_test("manual")
        results = self._make_test_results()
        xml_path = svc.generate_junit_xml(record.id, results)
        assert Path(xml_path).exists()
        tree = ET.parse(xml_path)
        root = tree.getroot()
        assert root.tag == "testsuite"
        assert root.attrib["tests"] == "4"
        assert root.attrib["failures"] == "1"

    def test_html_summary(self, svc_with_reports):
        svc, reports_dir = svc_with_reports
        record = svc.trigger_test("manual")
        results = self._make_test_results()
        html_path = svc.generate_html_summary(record.id, results)
        assert Path(html_path).exists()
        with open(html_path, encoding="utf-8") as f:
            content = f.read()
        assert "Test Report" in content
        assert record.id in content

    def test_get_report_path_exists(self, svc_with_reports):
        svc, reports_dir = svc_with_reports
        record = svc.trigger_test("manual")
        svc.generate_junit_xml(record.id, self._make_test_results())
        path = svc.get_report_path(record.id, "junit")
        assert path is not None

    def test_get_report_path_not_exists(self, svc):
        assert svc.get_report_path("none", "junit") is None

    def test_get_report_unknown_type(self, svc):
        assert svc.get_report_path("x", "unknown") is None


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------
class TestSingleton:
    def test_singleton(self):
        import services.cicd_integration as mod
        mod._service_instance = None
        s1 = mod.get_cicd_service()
        s2 = mod.get_cicd_service()
        assert s1 is s2
        mod._service_instance = None
