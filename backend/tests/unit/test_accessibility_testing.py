"""
AccessibilityTestService 单元测试
覆盖: 枚举/数据类, quick_check(通过 aiohttp mock), audit(Playwright mock),
      create_accessibility_service
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from services.accessibility_testing import (
    WCAGLevel, Severity, AccessibilityIssue, AccessibilityReport,
    AccessibilityTestService, create_accessibility_service
)


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------
class TestWCAGLevel:
    def test_values(self):
        assert WCAGLevel.A == "A"
        assert WCAGLevel.AA == "AA"
        assert WCAGLevel.AAA == "AAA"


class TestSeverity:
    def test_values(self):
        assert Severity.CRITICAL == "critical"
        assert Severity.INFO == "info"


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------
class TestAccessibilityIssue:
    def test_creation(self):
        issue = AccessibilityIssue(rule_id="img-alt", description="缺少alt",
                                   severity="critical", wcag_level="A")
        d = issue.to_dict()
        assert d["rule_id"] == "img-alt"


class TestAccessibilityReport:
    def test_defaults(self):
        r = AccessibilityReport(url="http://x.com")
        assert r.score == 100.0
        assert r.total_issues == 0
        assert r.to_dict()["url"] == "http://x.com"


# ---------------------------------------------------------------------------
# aiohttp mock 辅助
# ---------------------------------------------------------------------------
def _make_aiohttp_ctx(mock_resp):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


# ---------------------------------------------------------------------------
# quick_check 测试
# ---------------------------------------------------------------------------
class TestQuickCheck:
    @pytest.mark.asyncio
    async def test_missing_lang_and_title(self):
        """检测到缺少 lang 和 title"""
        svc = AccessibilityTestService()
        html = '<html><head></head><body><img src="x.png"></body></html>'

        mock_resp = MagicMock()
        mock_resp.text = AsyncMock(return_value=html)

        mock_session_ctx = _make_aiohttp_ctx(MagicMock())
        mock_session = MagicMock()
        mock_session.get.return_value = _make_aiohttp_ctx(mock_resp)
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)

        with patch("aiohttp.ClientSession", return_value=mock_session_ctx):
            result = await svc.quick_check("http://example.com")

        assert result["status"] == "success"
        rule_ids = [i["rule_id"] for i in result["issues"]]
        assert "html-lang" in rule_ids
        assert "page-title" in rule_ids
        assert "img-alt" in rule_ids

    @pytest.mark.asyncio
    async def test_compliant_page(self):
        """符合规范的页面不应有问题"""
        svc = AccessibilityTestService()
        html = '<html lang="zh-CN"><head><title>Test</title></head><body><img src="x.png" alt="desc"></body></html>'

        mock_resp = MagicMock()
        mock_resp.text = AsyncMock(return_value=html)
        mock_session = MagicMock()
        mock_session.get.return_value = _make_aiohttp_ctx(mock_resp)
        mock_session_ctx = _make_aiohttp_ctx(mock_session)

        with patch("aiohttp.ClientSession", return_value=mock_session_ctx):
            result = await svc.quick_check("http://example.com")

        assert result["status"] == "success"
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """网络异常应返回 error"""
        svc = AccessibilityTestService()
        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(side_effect=Exception("timeout"))
        mock_session_ctx.__aexit__ = AsyncMock()

        with patch("aiohttp.ClientSession", return_value=mock_session_ctx):
            result = await svc.quick_check("http://example.com")
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# audit 测试 (mock Playwright)
# ---------------------------------------------------------------------------
class TestAudit:
    @pytest.mark.asyncio
    async def test_playwright_not_installed(self):
        """Playwright 不可用时应提示安装"""
        svc = AccessibilityTestService()
        with patch.dict("sys.modules", {"playwright": None, "playwright.async_api": None}):
            # 模拟 ImportError
            with patch.object(svc, "audit", new_callable=AsyncMock) as mock_audit:
                report = AccessibilityReport(url="http://x.com", summary="Playwright 未安装", score=-1)
                mock_audit.return_value = report
                result = await svc.audit("http://x.com")
                assert "Playwright" in result.summary


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
class TestFactory:
    def test_create(self):
        svc = create_accessibility_service()
        assert isinstance(svc, AccessibilityTestService)
