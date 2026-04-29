"""
ComplianceTestService 单元测试
覆盖: 数据类, _check_security_headers (aiohttp mock),
      _check_page_compliance (Playwright mock/ImportError),
      audit 总流程, create_compliance_service
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from services.compliance_testing import (
    ComplianceIssue, ComplianceReport,
    ComplianceTestService, create_compliance_service
)


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------
class TestComplianceIssue:
    def test_creation(self):
        ci = ComplianceIssue(rule_id="sec-https", standard="SOC2",
                             description="Not HTTPS", severity="critical")
        assert ci.to_dict()["standard"] == "SOC2"


class TestComplianceReport:
    def test_defaults(self):
        r = ComplianceReport(url="http://x.com")
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
# _check_security_headers 测试
# ---------------------------------------------------------------------------
class TestCheckSecurityHeaders:
    @pytest.mark.asyncio
    async def test_all_headers_missing(self):
        """所有安全头都缺失时应报告多个问题"""
        svc = ComplianceTestService()

        mock_resp = MagicMock()
        mock_resp.headers = {}  # 空头
        mock_session = MagicMock()
        mock_session.get.return_value = _make_aiohttp_ctx(mock_resp)
        mock_session_ctx = _make_aiohttp_ctx(mock_session)

        with patch("aiohttp.ClientSession", return_value=mock_session_ctx):
            issues, checks = await svc._check_security_headers("http://example.com")

        rule_ids = [i["rule_id"] for i in issues]
        assert "sec-https" in rule_ids  # 非 HTTPS
        assert "sec-hsts" in rule_ids
        assert "sec-csp" in rule_ids
        assert checks >= 6

    @pytest.mark.asyncio
    async def test_https_no_issue(self):
        """HTTPS URL 不应报告 sec-https"""
        svc = ComplianceTestService()

        mock_resp = MagicMock()
        mock_resp.headers = {
            "Strict-Transport-Security": "max-age=31536000",
            "Content-Security-Policy": "default-src 'self'",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "strict-origin"
        }
        mock_session = MagicMock()
        mock_session.get.return_value = _make_aiohttp_ctx(mock_resp)
        mock_session_ctx = _make_aiohttp_ctx(mock_session)

        with patch("aiohttp.ClientSession", return_value=mock_session_ctx):
            issues, checks = await svc._check_security_headers("https://secure-site.com")

        rule_ids = [i["rule_id"] for i in issues]
        assert "sec-https" not in rule_ids
        assert "sec-hsts" not in rule_ids

    @pytest.mark.asyncio
    async def test_connection_error(self):
        """连接失败应返回 error issue"""
        svc = ComplianceTestService()

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(side_effect=Exception("refused"))
        mock_session_ctx.__aexit__ = AsyncMock()

        with patch("aiohttp.ClientSession", return_value=mock_session_ctx):
            issues, checks = await svc._check_security_headers("http://example.com")
        assert any(i["rule_id"] == "sec-error" for i in issues)


# ---------------------------------------------------------------------------
# _check_page_compliance 测试
# ---------------------------------------------------------------------------
class TestCheckPageCompliance:
    @pytest.mark.asyncio
    async def test_playwright_not_installed(self):
        """Playwright 不可用时应返回提示 issue"""
        svc = ComplianceTestService()
        # 选择性 mock: 仅拦截 playwright 相关的 import
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__
        def selective_import(name, *args, **kwargs):
            if 'playwright' in name:
                raise ImportError("no playwright")
            return original_import(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=selective_import):
            issues, checks = svc._check_page_compliance_sync("http://x.com", ["GDPR"])
        rule_ids = [i["rule_id"] for i in issues]
        assert "playwright-missing" in rule_ids


# ---------------------------------------------------------------------------
# audit 总流程
# ---------------------------------------------------------------------------
class TestAudit:
    @pytest.mark.asyncio
    async def test_audit_computes_score(self):
        """审计应计算评分和统计"""
        svc = ComplianceTestService()

        # Mock 两个子方法
        header_issues = [
            {"rule_id": "sec-https", "standard": "SOC2", "description": "no https", "severity": "critical"},
            {"rule_id": "sec-csp", "standard": "SOC2", "description": "no csp", "severity": "major"}
        ]
        page_issues = [
            {"rule_id": "gdpr-cookie-consent", "standard": "GDPR", "description": "no cookie", "severity": "critical"}
        ]

        async def mock_to_thread(func, *args, **kwargs):
            return (page_issues, 6)

        with patch.object(svc, "_check_security_headers", new_callable=AsyncMock,
                          return_value=(header_issues, 7)), \
             patch("services.compliance_testing.asyncio.to_thread", side_effect=mock_to_thread):
            report = await svc.audit("http://example.com")

        assert report.total_issues == 3
        assert report.critical == 2
        assert report.major == 1
        # 评分: 100 - (2*15 + 1*8) = 62
        assert report.score == 62.0
        assert "合规审计完成" in report.summary

    @pytest.mark.asyncio
    async def test_audit_custom_standards(self):
        """仅选择 SOC2 时不应检查 GDPR 页面内容"""
        svc = ComplianceTestService()

        with patch.object(svc, "_check_security_headers", new_callable=AsyncMock,
                          return_value=([], 7)):
            report = await svc.audit("http://example.com", standards=["SOC2"])

        assert "SOC2" in report.standards_checked
        assert report.score == 100.0


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
class TestFactory:
    def test_create(self):
        svc = create_compliance_service()
        assert isinstance(svc, ComplianceTestService)
