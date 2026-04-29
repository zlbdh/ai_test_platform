"""
SecurityScanner 单元测试
覆盖: 枚举/数据类, ScanResult 属性,
      scan (ZAP/simple 路由), _check_security_headers, _check_ssl,
      _check_sensitive_files, stop/history/report, 单例
"""
import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from services.security_scanner import (
    ScanType, ScanStatus, AlertRisk,
    SecurityAlert, ScanConfig, ScanResult,
    SecurityScanner
)


@pytest.fixture(autouse=True)
def _stub_execution_center():
    recorder = MagicMock()
    recorder.record_security_result.return_value = "security_stub"
    with patch("services.security_scanner.get_execution_center_service", return_value=recorder):
        yield


# ---------------------------------------------------------------------------
# 枚举测试
# ---------------------------------------------------------------------------
class TestEnums:
    def test_scan_type(self):
        assert ScanType.QUICK == "quick"
        assert ScanType.STANDARD == "standard"
        assert ScanType.FULL == "full"

    def test_scan_status(self):
        assert ScanStatus.IDLE == "idle"
        assert ScanStatus.RUNNING == "running"
        assert ScanStatus.COMPLETED == "completed"
        assert ScanStatus.FAILED == "failed"
        assert ScanStatus.STOPPED == "stopped"

    def test_alert_risk(self):
        assert AlertRisk.HIGH == "High"
        assert AlertRisk.MEDIUM == "Medium"
        assert AlertRisk.LOW == "Low"
        assert AlertRisk.INFO == "Informational"


# ---------------------------------------------------------------------------
# 数据类测试
# ---------------------------------------------------------------------------
class TestSecurityAlert:
    def test_creation(self):
        alert = SecurityAlert(
            name="XSS", risk=AlertRisk.HIGH, confidence="High",
            url="http://x.com", description="XSS漏洞", solution="过滤输入"
        )
        assert alert.name == "XSS"
        assert alert.risk == AlertRisk.HIGH
        assert alert.evidence == ""
        assert alert.cweid == ""


class TestScanConfig:
    def test_defaults(self):
        cfg = ScanConfig(target_url="http://example.com")
        assert cfg.scan_type == ScanType.STANDARD
        assert cfg.max_depth == 5
        assert cfg.max_children == 10
        assert cfg.ajax_spider is False
        assert cfg.auth is None


class TestScanResult:
    def _make_result(self, alerts=None, started_at=None, finished_at=None):
        cfg = ScanConfig(target_url="http://x.com")
        return ScanResult(
            scan_id="s1", status=ScanStatus.COMPLETED, config=cfg,
            started_at=started_at, finished_at=finished_at,
            alerts=alerts or []
        )

    def test_duration(self):
        t1 = datetime(2026, 1, 1, 0, 0, 0)
        t2 = datetime(2026, 1, 1, 0, 0, 30)
        r = self._make_result(started_at=t1, finished_at=t2)
        assert r.duration == 30.0

    def test_duration_none(self):
        r = self._make_result()
        assert r.duration is None

    def test_alert_counts(self):
        alerts = [
            SecurityAlert(name="a", risk=AlertRisk.HIGH, confidence="H", url="", description="", solution=""),
            SecurityAlert(name="b", risk=AlertRisk.HIGH, confidence="H", url="", description="", solution=""),
            SecurityAlert(name="c", risk=AlertRisk.MEDIUM, confidence="M", url="", description="", solution=""),
            SecurityAlert(name="d", risk=AlertRisk.LOW, confidence="L", url="", description="", solution=""),
        ]
        r = self._make_result(alerts=alerts)
        assert r.high_count == 2
        assert r.medium_count == 1
        assert r.low_count == 1


# ---------------------------------------------------------------------------
# SecurityScanner 初始化
# ---------------------------------------------------------------------------
class TestScannerInit:
    def test_default_init(self, tmp_path):
        scanner = SecurityScanner(results_dir=str(tmp_path))
        assert scanner.status == ScanStatus.IDLE
        assert scanner._current_result is None


# ---------------------------------------------------------------------------
# scan (路由 ZAP vs simple)
# ---------------------------------------------------------------------------
class TestScan:
    @pytest.mark.asyncio
    async def test_scan_falls_back_to_simple(self, tmp_path):
        """ZAP 不可用时应回退到简化扫描"""
        scanner = SecurityScanner(results_dir=str(tmp_path))
        config = ScanConfig(target_url="http://example.com")

        with patch.object(scanner, "_check_zap_available", new_callable=AsyncMock, return_value=False), \
             patch.object(scanner, "_run_simple_scan", new_callable=AsyncMock) as mock_simple:
            mock_simple.return_value = ScanResult(
                scan_id="x", status=ScanStatus.COMPLETED, config=config
            )
            result = await scanner.scan(config)
            mock_simple.assert_called_once()

    @pytest.mark.asyncio
    async def test_scan_uses_zap_when_available(self, tmp_path):
        """ZAP 可用时应使用 ZAP 扫描"""
        scanner = SecurityScanner(results_dir=str(tmp_path))
        config = ScanConfig(target_url="http://example.com")

        with patch.object(scanner, "_check_zap_available", new_callable=AsyncMock, return_value=True), \
             patch.object(scanner, "_run_zap_scan", new_callable=AsyncMock) as mock_zap:
            mock_zap.return_value = ScanResult(
                scan_id="x", status=ScanStatus.COMPLETED, config=config
            )
            result = await scanner.scan(config)
            mock_zap.assert_called_once()

    @pytest.mark.asyncio
    async def test_scan_exception_marks_failed(self, tmp_path):
        """扫描异常应标记为 FAILED"""
        scanner = SecurityScanner(results_dir=str(tmp_path))
        config = ScanConfig(target_url="http://example.com")

        with patch.object(scanner, "_check_zap_available", new_callable=AsyncMock,
                          side_effect=RuntimeError("boom")):
            result = await scanner.scan(config)
        assert result.status == ScanStatus.FAILED
        assert "boom" in result.errors[0]


# ---------------------------------------------------------------------------
# _check_ssl 测试
# ---------------------------------------------------------------------------
class TestCheckSsl:
    @pytest.mark.asyncio
    async def test_http_url_triggers_alert(self, tmp_path):
        scanner = SecurityScanner(results_dir=str(tmp_path))
        alerts = await scanner._check_ssl(MagicMock(), "http://insecure.com")
        assert len(alerts) == 1
        assert alerts[0].risk == AlertRisk.HIGH
        assert "HTTPS" in alerts[0].name or "HTTPS" in alerts[0].description

    @pytest.mark.asyncio
    async def test_https_url_no_alert(self, tmp_path):
        scanner = SecurityScanner(results_dir=str(tmp_path))
        alerts = await scanner._check_ssl(MagicMock(), "https://secure.com")
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# _check_security_headers 测试
# ---------------------------------------------------------------------------
def _make_aiohttp_ctx(mock_resp):
    """创建兼容 aiohttp 'async with session.get()' 的 mock"""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


class TestCheckSecurityHeaders:
    @pytest.mark.asyncio
    async def test_missing_headers(self, tmp_path):
        """缺少安全头应生成告警"""
        scanner = SecurityScanner(results_dir=str(tmp_path))

        mock_resp = MagicMock()
        mock_resp.headers = {}  # 没有安全头
        mock_resp.status = 200

        mock_session = MagicMock()
        mock_session.get.return_value = _make_aiohttp_ctx(mock_resp)

        alerts = await scanner._check_security_headers(mock_session, "http://example.com")
        assert len(alerts) >= 3  # 至少缺少 CSP, X-Frame, HSTS 等

    @pytest.mark.asyncio
    async def test_all_headers_present(self, tmp_path):
        """所有安全头都存在时不应告警"""
        scanner = SecurityScanner(results_dir=str(tmp_path))

        mock_resp = MagicMock()
        mock_resp.headers = {
            "Content-Security-Policy": "default-src 'self'",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Strict-Transport-Security": "max-age=31536000",
            "X-XSS-Protection": "1; mode=block"
        }
        mock_resp.status = 200

        mock_session = MagicMock()
        mock_session.get.return_value = _make_aiohttp_ctx(mock_resp)

        alerts = await scanner._check_security_headers(mock_session, "http://example.com")
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# _check_sensitive_files 测试
# ---------------------------------------------------------------------------
class TestCheckSensitiveFiles:
    @pytest.mark.asyncio
    async def test_html_fallback_not_treated_as_exposed_file(self, tmp_path):
        """HTML fallback 页面不应被判定为敏感文件泄露"""
        scanner = SecurityScanner(results_dir=str(tmp_path))

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_resp.text = AsyncMock(return_value="<html><body>SPA fallback</body></html>")

        mock_session = MagicMock()
        mock_session.get.return_value = _make_aiohttp_ctx(mock_resp)

        alerts = await scanner._check_sensitive_files(mock_session, "http://example.com")
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_real_sensitive_file_content_triggers_alert(self, tmp_path):
        """真实敏感文件内容应被识别"""
        scanner = SecurityScanner(results_dir=str(tmp_path))

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.headers = {"Content-Type": "text/plain"}
        mock_resp.text = AsyncMock(return_value="[core]\nrepositoryformatversion = 0\n")

        mock_session = MagicMock()
        mock_session.get.return_value = _make_aiohttp_ctx(mock_resp)

        alerts = await scanner._check_sensitive_files(mock_session, "http://example.com")
        assert len(alerts) >= 1

    @pytest.mark.asyncio
    async def test_no_exposed_files(self, tmp_path):
        """敏感文件返回 404 时不应告警"""
        scanner = SecurityScanner(results_dir=str(tmp_path))

        mock_resp = MagicMock()
        mock_resp.status = 404
        mock_resp.headers = {"Content-Type": "text/plain"}
        mock_resp.text = AsyncMock(return_value="")

        mock_session = MagicMock()
        mock_session.get.return_value = _make_aiohttp_ctx(mock_resp)

        alerts = await scanner._check_sensitive_files(mock_session, "http://example.com")
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# stop_scan 测试
# ---------------------------------------------------------------------------
class TestStopScan:
    def test_stop_scan(self, tmp_path):
        scanner = SecurityScanner(results_dir=str(tmp_path))
        cfg = ScanConfig(target_url="http://x.com")
        scanner._current_result = ScanResult(
            scan_id="s1", status=ScanStatus.RUNNING, config=cfg,
            started_at=datetime.now()
        )
        scanner.stop_scan()
        assert scanner.status == ScanStatus.STOPPED
        assert scanner._current_result.status == ScanStatus.STOPPED

    def test_stop_scan_no_current(self, tmp_path):
        scanner = SecurityScanner(results_dir=str(tmp_path))
        scanner.stop_scan()
        assert scanner.status == ScanStatus.STOPPED


# ---------------------------------------------------------------------------
# 历史管理测试
# ---------------------------------------------------------------------------
class TestHistory:
    def test_get_history_empty(self, tmp_path):
        scanner = SecurityScanner(results_dir=str(tmp_path))
        assert scanner.get_history() == []

    def test_get_history_with_results(self, tmp_path):
        scanner = SecurityScanner(results_dir=str(tmp_path))
        # 写入模拟数据
        for i in range(3):
            (tmp_path / f"result_s{i}.json").write_text(
                json.dumps({"scan_id": f"s{i}"}), encoding="utf-8"
            )
        history = scanner.get_history(limit=2)
        assert len(history) == 2

    def test_delete_history(self, tmp_path):
        scanner = SecurityScanner(results_dir=str(tmp_path))
        (tmp_path / "result_s1.json").write_text("{}", encoding="utf-8")
        (tmp_path / "report_s1.html").write_text("<html>", encoding="utf-8")
        assert scanner.delete_history("s1") is True
        assert not (tmp_path / "result_s1.json").exists()
        assert not (tmp_path / "report_s1.html").exists()

    def test_delete_history_not_found(self, tmp_path):
        scanner = SecurityScanner(results_dir=str(tmp_path))
        assert scanner.delete_history("nonexistent") is False

    def test_clear_history(self, tmp_path):
        scanner = SecurityScanner(results_dir=str(tmp_path))
        (tmp_path / "result_a.json").write_text("{}", encoding="utf-8")
        (tmp_path / "result_b.json").write_text("{}", encoding="utf-8")
        (tmp_path / "report_a.html").write_text("", encoding="utf-8")
        count = scanner.clear_history()
        assert count == 2


# ---------------------------------------------------------------------------
# 报告生成测试
# ---------------------------------------------------------------------------
class TestGenerateReport:
    def test_report_not_found(self, tmp_path):
        scanner = SecurityScanner(results_dir=str(tmp_path))
        result = scanner.generate_report("nonexistent")
        assert result["status"] == "error"

    def test_report_generation(self, tmp_path):
        scanner = SecurityScanner(results_dir=str(tmp_path))
        data = {
            "scan_id": "s1",
            "finished_at": "2026-01-01T00:00:00",
            "stats": {"high": 1, "medium": 0, "low": 0, "info": 0},
            "alerts": [
                {"name": "XSS", "risk": "High", "url": "http://x.com", "description": "desc"}
            ]
        }
        (tmp_path / "result_s1.json").write_text(json.dumps(data), encoding="utf-8")
        result = scanner.generate_report("s1")
        assert result["status"] == "success"
        assert (tmp_path / "report_s1.html").exists()


# ---------------------------------------------------------------------------
# 单例测试
# ---------------------------------------------------------------------------
class TestSingleton:
    def test_singleton(self, tmp_path):
        import services.security_scanner as mod
        mod._scanner = None
        with patch("core.config.Config") as mock_cfg:
            mock_cfg.PROJECT_ROOT = str(tmp_path)
            from services.security_scanner import get_security_scanner
            s1 = get_security_scanner()
            s2 = get_security_scanner()
            assert s1 is s2
        mod._scanner = None
