"""
ComplianceTestService unit tests
Coverage: data classes, _check_security_headers (aiohttp mock),
      _check_page_compliance (Playwright mock/ImportError),
      complete audit flow, create_compliance_service
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from services.compliance_testing import (
    ComplianceIssue, ComplianceReport,
    ComplianceTestService, create_compliance_service
)


# ---------------------------------------------------------------------------
# Data classes
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
# aiohttp mock helpers
# ---------------------------------------------------------------------------
def _make_aiohttp_ctx(mock_resp):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


# ---------------------------------------------------------------------------
# _check_security_headers tests
# ---------------------------------------------------------------------------
class TestCheckSecurityHeaders:
    @pytest.mark.asyncio
    async def test_all_headers_missing(self):
        """Report multiple issues when all security headers are missing."""
        svc = ComplianceTestService()

        mock_resp = MagicMock()
        mock_resp.headers = {}  # Empty headers
        mock_session = MagicMock()
        mock_session.get.return_value = _make_aiohttp_ctx(mock_resp)
        mock_session_ctx = _make_aiohttp_ctx(mock_session)

        with patch("aiohttp.ClientSession", return_value=mock_session_ctx):
            issues, checks = await svc._check_security_headers("http://example.com")

        rule_ids = [i["rule_id"] for i in issues]
        assert "sec-https" in rule_ids  # Not HTTPS
        assert "sec-hsts" in rule_ids
        assert "sec-csp" in rule_ids
        assert checks >= 6

    @pytest.mark.asyncio
    async def test_https_no_issue(self):
        """Do not report sec-https for an HTTPS URL."""
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
        """Return an error issue when the connection fails."""
        svc = ComplianceTestService()

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(side_effect=Exception("refused"))
        mock_session_ctx.__aexit__ = AsyncMock()

        with patch("aiohttp.ClientSession", return_value=mock_session_ctx):
            issues, checks = await svc._check_security_headers("http://example.com")
        assert any(i["rule_id"] == "sec-error" for i in issues)


# ---------------------------------------------------------------------------
# _check_page_compliance tests
# ---------------------------------------------------------------------------
class TestCheckPageCompliance:
    @pytest.mark.asyncio
    async def test_playwright_not_installed(self):
        """Return an informative issue when Playwright is unavailable."""
        svc = ComplianceTestService()
        # Selective mock: intercept only Playwright imports.
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
# Complete audit flow
# ---------------------------------------------------------------------------
class TestAudit:
    @pytest.mark.asyncio
    async def test_audit_computes_score(self):
        """Compute the audit score and statistics."""
        svc = ComplianceTestService()

        # Mock both component methods.
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
        # Score: 100 - (2*15 + 1*8) = 62
        assert report.score == 62.0
        assert "Compliance audit completed" in report.summary

    @pytest.mark.asyncio
    async def test_audit_custom_standards(self):
        """Skip GDPR page content checks when only SOC2 is selected."""
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
