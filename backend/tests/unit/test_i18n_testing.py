"""
I18nTestService 单元测试
覆盖: 数据类, quick_check (aiohttp mock), test_locale(Playwright ImportError 回退), 工厂
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from services.i18n_testing import (
    I18nIssue, I18nReport, I18nTestService, create_i18n_service
)


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------
class TestI18nIssue:
    def test_creation(self):
        issue = I18nIssue(rule_id="html-lang", description="缺少lang", severity="major")
        d = issue.to_dict()
        assert d["rule_id"] == "html-lang"


class TestI18nReport:
    def test_defaults(self):
        r = I18nReport(url="http://x.com")
        assert r.score == 100.0
        assert r.total_issues == 0
        assert r.to_dict()["url"] == "http://x.com"


# ---------------------------------------------------------------------------
# aiohttp mock 辅助
# ---------------------------------------------------------------------------
def _make_ctx(mock_resp):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


# ---------------------------------------------------------------------------
# quick_check
# ---------------------------------------------------------------------------
class TestQuickCheck:
    @pytest.mark.asyncio
    async def test_missing_charset_and_lang(self):
        svc = I18nTestService()
        html = '<html><head><meta name="x"></head><body>Hello</body></html>'

        mock_resp = MagicMock()
        mock_resp.text = AsyncMock(return_value=html)
        mock_session = MagicMock()
        mock_session.get.return_value = _make_ctx(mock_resp)

        with patch("aiohttp.ClientSession", return_value=_make_ctx(mock_session)):
            result = await svc.quick_check("http://example.com", "zh-CN")

        assert result["status"] == "success"
        rule_ids = [i["rule_id"] for i in result["issues"]]
        assert "charset-missing" in rule_ids
        assert "html-lang" in rule_ids

    @pytest.mark.asyncio
    async def test_good_page(self):
        svc = I18nTestService()
        html = '<html lang="zh-CN"><head><meta charset="utf-8"></head><body>ok</body></html>'

        mock_resp = MagicMock()
        mock_resp.text = AsyncMock(return_value=html)
        mock_session = MagicMock()
        mock_session.get.return_value = _make_ctx(mock_resp)

        with patch("aiohttp.ClientSession", return_value=_make_ctx(mock_session)):
            result = await svc.quick_check("http://example.com")

        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_error(self):
        svc = I18nTestService()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(side_effect=Exception("timeout"))
        ctx.__aexit__ = AsyncMock()
        with patch("aiohttp.ClientSession", return_value=ctx):
            result = await svc.quick_check("http://x.com")
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# test_locale (Playwright ImportError 回退)
# ---------------------------------------------------------------------------
class TestLocale:
    @pytest.mark.asyncio
    async def test_playwright_not_installed(self):
        svc = I18nTestService()
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__
        def selective_import(name, *args, **kwargs):
            if 'playwright' in name:
                raise ImportError("no playwright")
            return original_import(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=selective_import):
            report = await svc.test_locale("http://x.com", ["zh-CN", "en-US"])
        assert "Playwright" in report.summary
        assert report.score == -1


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
class TestFactory:
    def test_create(self):
        svc = create_i18n_service()
        assert isinstance(svc, I18nTestService)
