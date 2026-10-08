"""
EnhancedSecurityScanner unit tests.
Covers enums, data classes, vulnerability IDs, SSL and header checks with mocked
aiohttp, risk scoring, report generation, and the singleton.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from services.enhanced_security import (
    SeverityLevel, VulnerabilityType, Vulnerability, ScanResult,
    EnhancedSecurityScanner, get_enhanced_scanner
)


# ---------------------------------------------------------------------------
# Enums.
# ---------------------------------------------------------------------------
class TestSeverityLevel:
    def test_values(self):
        assert SeverityLevel.CRITICAL.value == "critical"
        assert SeverityLevel.INFO.value == "info"


class TestVulnerabilityType:
    def test_values(self):
        assert VulnerabilityType.SQL_INJECTION.value == "sql_injection"
        assert VulnerabilityType.XSS.value == "xss"
        assert VulnerabilityType.INSECURE_HEADERS.value == "insecure_headers"


# ---------------------------------------------------------------------------
# Data classes.
# ---------------------------------------------------------------------------
class TestVulnerability:
    def test_creation(self):
        v = Vulnerability(
            vuln_id="VULN-0001",
            vuln_type=VulnerabilityType.XSS,
            severity=SeverityLevel.HIGH,
            title="XSS Found",
            description="Reflected XSS",
            evidence="<script>",
            url="http://x.com",
            remediation="Encode output"
        )
        assert v.cwe_id is None
        assert v.cvss_score is None


class TestScanResult:
    def test_creation(self):
        r = ScanResult(
            target_url="http://x.com",
            scan_time=1.5,
            total_requests=10,
            vulnerabilities=[],
            headers_check={},
            ssl_check={},
            summary={"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        )
        assert r.total_requests == 10


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def scanner():
    return EnhancedSecurityScanner()


# ---------------------------------------------------------------------------
# _generate_vuln_id
# ---------------------------------------------------------------------------
class TestGenerateVulnId:
    def test_increment(self, scanner):
        id1 = scanner._generate_vuln_id()
        id2 = scanner._generate_vuln_id()
        assert id1 == "VULN-0001"
        assert id2 == "VULN-0002"


# ---------------------------------------------------------------------------
# _check_ssl
# ---------------------------------------------------------------------------
class TestCheckSSL:
    @pytest.mark.asyncio
    async def test_https(self, scanner):
        result = await scanner._check_ssl("https://secure.com")
        assert result["https"] is True
        assert "warning" not in result

    @pytest.mark.asyncio
    async def test_http(self, scanner):
        result = await scanner._check_ssl("http://insecure.com")
        assert result["https"] is False
        assert result["warning"] == "Site not using HTTPS"


# ---------------------------------------------------------------------------
# aiohttp mock helpers.
# ---------------------------------------------------------------------------
def _make_ctx(obj):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=obj)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


# ---------------------------------------------------------------------------
# _check_headers
# ---------------------------------------------------------------------------
class TestCheckHeaders:
    @pytest.mark.asyncio
    async def test_all_missing(self, scanner):
        mock_resp = MagicMock()
        mock_resp.headers = {}

        mock_session = MagicMock()
        mock_session.get.return_value = _make_ctx(mock_resp)

        headers_status, vulns = await scanner._check_headers(mock_session, "http://x.com")
        assert len(vulns) == 7  # Seven security headers.
        for v in vulns:
            assert v.vuln_type == VulnerabilityType.INSECURE_HEADERS

    @pytest.mark.asyncio
    async def test_all_present(self, scanner):
        mock_resp = MagicMock()
        mock_resp.headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin",
            "Permissions-Policy": "camera=()"
        }

        mock_session = MagicMock()
        mock_session.get.return_value = _make_ctx(mock_resp)

        headers_status, vulns = await scanner._check_headers(mock_session, "http://x.com")
        assert len(vulns) == 0

    @pytest.mark.asyncio
    async def test_hsts_severity_medium(self, scanner):
        """Missing HSTS should be MEDIUM; the others should be LOW."""
        mock_resp = MagicMock()
        # Only HSTS is missing.
        mock_resp.headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin",
            "Permissions-Policy": "camera=()"
        }
        mock_session = MagicMock()
        mock_session.get.return_value = _make_ctx(mock_resp)

        _, vulns = await scanner._check_headers(mock_session, "http://x.com")
        assert len(vulns) == 1
        assert vulns[0].severity == SeverityLevel.MEDIUM


# ---------------------------------------------------------------------------
# _calculate_risk_score
# ---------------------------------------------------------------------------
class TestRiskScore:
    def test_no_vulns(self, scanner):
        result = ScanResult("u", 0, 0, [], {}, {},
                            {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0})
        assert scanner._calculate_risk_score(result) == 0

    def test_max_score(self, scanner):
        result = ScanResult("u", 0, 0, [], {}, {},
                            {"critical": 10, "high": 10, "medium": 10, "low": 10, "info": 10})
        assert scanner._calculate_risk_score(result) == 100  # Clamp values above 100 to 100.


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------
class TestGenerateReport:
    def test_report_structure(self, scanner):
        vuln = Vulnerability(
            vuln_id="V-1", vuln_type=VulnerabilityType.XSS,
            severity=SeverityLevel.HIGH, title="XSS", description="d",
            evidence="e", url="u", remediation="r", cwe_id="CWE-79", cvss_score=6.1
        )
        result = ScanResult("http://x.com", 1.0, 5, [vuln], {"h": "v"}, {"https": True},
                            {"critical": 0, "high": 1, "medium": 0, "low": 0, "info": 0})
        report = scanner.generate_report(result)
        assert report["target"] == "http://x.com"
        assert len(report["vulnerabilities"]) == 1
        assert report["vulnerabilities"][0]["cwe"] == "CWE-79"
        assert report["risk_score"] == 15  # 1 high * 15


# ---------------------------------------------------------------------------
# payloads
# ---------------------------------------------------------------------------
class TestPayloads:
    def test_sqli_payloads(self, scanner):
        assert len(scanner.sqli_payloads) > 0

    def test_xss_payloads(self, scanner):
        assert len(scanner.xss_payloads) > 0


# ---------------------------------------------------------------------------
# Singleton.
# ---------------------------------------------------------------------------
class TestSingleton:
    def test_same_instance(self):
        import services.enhanced_security as mod
        mod._enhanced_scanner = None
        s1 = get_enhanced_scanner()
        s2 = get_enhanced_scanner()
        assert s1 is s2
        mod._enhanced_scanner = None
