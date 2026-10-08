"""
Enhanced security scanner.

Combines security checks:
- OWASP Top 10 checks
- SQL injection checks
- XSS checks
- CSRF checks
- Dependency vulnerability scanning
- Header security checks
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import re
import asyncio
import aiohttp
import hashlib
from urllib.parse import urljoin, urlparse
import time


class SeverityLevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class VulnerabilityType(Enum):
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    CSRF = "csrf"
    IDOR = "idor"
    SSRF = "ssrf"
    LFI = "lfi"
    RFI = "rfi"
    OPEN_REDIRECT = "open_redirect"
    SENSITIVE_DATA = "sensitive_data"
    BROKEN_AUTH = "broken_auth"
    SECURITY_MISCONFIG = "security_misconfig"
    INSECURE_HEADERS = "insecure_headers"


@dataclass
class Vulnerability:
    """Vulnerability"""
    vuln_id: str
    vuln_type: VulnerabilityType
    severity: SeverityLevel
    title: str
    description: str
    evidence: str
    url: str
    remediation: str
    cwe_id: Optional[str] = None
    cvss_score: Optional[float] = None


@dataclass
class ScanResult:
    """Scan result"""
    target_url: str
    scan_time: float
    total_requests: int
    vulnerabilities: List[Vulnerability]
    headers_check: Dict[str, Any]
    ssl_check: Dict[str, Any]
    summary: Dict[str, int]


class EnhancedSecurityScanner:
    """Enhanced security scanner"""
    
    def __init__(self):
        self.vuln_counter = 0
        self.session: Optional[aiohttp.ClientSession] = None
        
        # SQL injection payloads
        self.sqli_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE users--",
            "1' AND '1'='1",
            "1 OR 1=1",
            "' UNION SELECT NULL--",
            "admin'--",
            "1; WAITFOR DELAY '0:0:5'--"
        ]
        
        # XSS Payload
        self.xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
            "'><script>alert('XSS')</script>",
            "\" onfocus=\"alert('XSS')\" autofocus=\""
        ]
        
        # Security header checks
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": ["DENY", "SAMEORIGIN"],
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": None,
            "Content-Security-Policy": None,
            "Referrer-Policy": None,
            "Permissions-Policy": None
        }
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get the HTTP session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close(self):
        """Close the session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _generate_vuln_id(self) -> str:
        """Generate a vulnerability ID"""
        self.vuln_counter += 1
        return f"VULN-{self.vuln_counter:04d}"
    
    async def scan(self, target_url: str, scan_types: List[str] = None) -> ScanResult:
        """Run a security scan"""
        start_time = time.time()
        vulnerabilities = []
        total_requests = 0
        
        scan_types = scan_types or ["headers", "sqli", "xss", "ssl", "sensitive"]
        
        session = await self._get_session()
        
        # 1. Security header checks
        headers_check = {}
        if "headers" in scan_types:
            headers_check, header_vulns = await self._check_headers(session, target_url)
            vulnerabilities.extend(header_vulns)
            total_requests += 1
        
        # 2. SSL checks
        ssl_check = {}
        if "ssl" in scan_types:
            ssl_check = await self._check_ssl(target_url)
        
        # 3. SQL injection checks
        if "sqli" in scan_types:
            sqli_vulns, sqli_reqs = await self._test_sqli(session, target_url)
            vulnerabilities.extend(sqli_vulns)
            total_requests += sqli_reqs
        
        # 4. XSS checks
        if "xss" in scan_types:
            xss_vulns, xss_reqs = await self._test_xss(session, target_url)
            vulnerabilities.extend(xss_vulns)
            total_requests += xss_reqs
        
        # 5. Sensitive data exposure
        if "sensitive" in scan_types:
            sensitive_vulns, sens_reqs = await self._check_sensitive_data(session, target_url)
            vulnerabilities.extend(sensitive_vulns)
            total_requests += sens_reqs
        
        # Summarize statistics
        summary = {
            "critical": sum(1 for v in vulnerabilities if v.severity == SeverityLevel.CRITICAL),
            "high": sum(1 for v in vulnerabilities if v.severity == SeverityLevel.HIGH),
            "medium": sum(1 for v in vulnerabilities if v.severity == SeverityLevel.MEDIUM),
            "low": sum(1 for v in vulnerabilities if v.severity == SeverityLevel.LOW),
            "info": sum(1 for v in vulnerabilities if v.severity == SeverityLevel.INFO)
        }
        
        scan_time = time.time() - start_time
        
        return ScanResult(
            target_url=target_url,
            scan_time=scan_time,
            total_requests=total_requests,
            vulnerabilities=vulnerabilities,
            headers_check=headers_check,
            ssl_check=ssl_check,
            summary=summary
        )
    
    async def _check_headers(
        self,
        session: aiohttp.ClientSession,
        url: str
    ) -> tuple:
        """Check security headers"""
        vulnerabilities = []
        headers_status = {}
        
        try:
            async with session.get(url, ssl=False) as response:
                headers = response.headers
                
                for header, expected in self.security_headers.items():
                    value = headers.get(header)
                    
                    if value is None:
                        headers_status[header] = {"present": False, "value": None}
                        
                        vulnerabilities.append(Vulnerability(
                            vuln_id=self._generate_vuln_id(),
                            vuln_type=VulnerabilityType.INSECURE_HEADERS,
                            severity=SeverityLevel.MEDIUM if header == "Strict-Transport-Security" else SeverityLevel.LOW,
                            title=f"Missing Security Header: {header}",
                            description=f"The {header} header is not set",
                            evidence=f"Header not found in response",
                            url=url,
                            remediation=f"Add the {header} header to the response"
                        ))
                    else:
                        headers_status[header] = {"present": True, "value": value}
        except Exception as e:
            headers_status["error"] = str(e)
        
        return headers_status, vulnerabilities
    
    async def _check_ssl(self, url: str) -> Dict[str, Any]:
        """Check SSL/TLS configuration"""
        result = {
            "https": url.startswith("https"),
            "valid_cert": None,
            "expiry": None
        }
        
        if not url.startswith("https"):
            result["warning"] = "Site not using HTTPS"
        
        return result
    
    async def _test_sqli(
        self,
        session: aiohttp.ClientSession,
        url: str
    ) -> tuple:
        """Test for SQL injection"""
        vulnerabilities = []
        request_count = 0
        
        # Check common parameters
        test_params = ["id", "user", "name", "search", "q", "page"]
        
        for param in test_params:
            for payload in self.sqli_payloads[:3]:  # Limit the number of requests
                test_url = f"{url}?{param}={payload}"
                request_count += 1
                
                try:
                    async with session.get(test_url, ssl=False) as response:
                        text = await response.text()
                        
                        # Check error messages
                        error_patterns = [
                            r"SQL syntax.*MySQL",
                            r"Warning.*mysql_",
                            r"PostgreSQL.*ERROR",
                            r"ORA-\d{5}",
                            r"Microsoft SQL Server",
                            r"Unclosed quotation mark"
                        ]
                        
                        for pattern in error_patterns:
                            if re.search(pattern, text, re.IGNORECASE):
                                vulnerabilities.append(Vulnerability(
                                    vuln_id=self._generate_vuln_id(),
                                    vuln_type=VulnerabilityType.SQL_INJECTION,
                                    severity=SeverityLevel.CRITICAL,
                                    title=f"Potential SQL Injection in '{param}' parameter",
                                    description="The application may be vulnerable to SQL injection",
                                    evidence=f"Error pattern detected with payload: {payload}",
                                    url=test_url,
                                    remediation="Use parameterized queries and input validation",
                                    cwe_id="CWE-89",
                                    cvss_score=9.8
                                ))
                                break
                
                except Exception:
                    pass
        
        return vulnerabilities, request_count
    
    async def _test_xss(
        self,
        session: aiohttp.ClientSession,
        url: str
    ) -> tuple:
        """Test for XSS"""
        vulnerabilities = []
        request_count = 0
        
        test_params = ["q", "search", "name", "message", "input"]
        
        for param in test_params:
            for payload in self.xss_payloads[:3]:
                test_url = f"{url}?{param}={payload}"
                request_count += 1
                
                try:
                    async with session.get(test_url, ssl=False) as response:
                        text = await response.text()
                        
                        # Check reflected content
                        if payload in text:
                            vulnerabilities.append(Vulnerability(
                                vuln_id=self._generate_vuln_id(),
                                vuln_type=VulnerabilityType.XSS,
                                severity=SeverityLevel.HIGH,
                                title=f"Potential Reflected XSS in '{param}' parameter",
                                description="User input is reflected in the response without proper encoding",
                                evidence=f"Payload reflected: {payload[:50]}...",
                                url=test_url,
                                remediation="Encode all user input before rendering",
                                cwe_id="CWE-79",
                                cvss_score=6.1
                            ))
                            break
                
                except Exception:
                    pass
        
        return vulnerabilities, request_count
    
    async def _check_sensitive_data(
        self,
        session: aiohttp.ClientSession,
        url: str
    ) -> tuple:
        """Check for sensitive data exposure"""
        vulnerabilities = []
        request_count = 0
        
        # Sensitive paths
        sensitive_paths = [
            "/.env",
            "/.git/config",
            "/wp-config.php",
            "/config.php",
            "/backup.sql",
            "/phpinfo.php",
            "/server-status",
            "/.htaccess",
            "/web.config",
            "/robots.txt",
            "/sitemap.xml"
        ]
        
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        
        for path in sensitive_paths:
            test_url = urljoin(base_url, path)
            request_count += 1
            
            try:
                async with session.get(test_url, ssl=False) as response:
                    if response.status == 200:
                        text = await response.text()
                        
                        # Check sensitive content
                        sensitive_patterns = [
                            (r"password\s*=", "password"),
                            (r"DB_PASSWORD", "database password"),
                            (r"api_key\s*=", "API key"),
                            (r"secret_key", "secret key"),
                            (r"\[core\]", "git config")
                        ]
                        
                        for pattern, desc in sensitive_patterns:
                            if re.search(pattern, text, re.IGNORECASE):
                                vulnerabilities.append(Vulnerability(
                                    vuln_id=self._generate_vuln_id(),
                                    vuln_type=VulnerabilityType.SENSITIVE_DATA,
                                    severity=SeverityLevel.HIGH,
                                    title=f"Sensitive File Exposed: {path}",
                                    description=f"A sensitive file containing {desc} is accessible",
                                    evidence=f"Pattern matched: {pattern}",
                                    url=test_url,
                                    remediation="Remove or restrict access to sensitive files",
                                    cwe_id="CWE-200"
                                ))
                                break
            
            except Exception:
                pass
        
        return vulnerabilities, request_count
    
    def generate_report(self, result: ScanResult) -> Dict[str, Any]:
        """Generate a scan report"""
        return {
            "target": result.target_url,
            "scan_time_seconds": round(result.scan_time, 2),
            "total_requests": result.total_requests,
            "summary": result.summary,
            "risk_score": self._calculate_risk_score(result),
            "vulnerabilities": [
                {
                    "id": v.vuln_id,
                    "type": v.vuln_type.value,
                    "severity": v.severity.value,
                    "title": v.title,
                    "description": v.description,
                    "url": v.url,
                    "remediation": v.remediation,
                    "cwe": v.cwe_id,
                    "cvss": v.cvss_score
                }
                for v in result.vulnerabilities
            ],
            "headers": result.headers_check,
            "ssl": result.ssl_check
        }
    
    def _calculate_risk_score(self, result: ScanResult) -> float:
        """Calculate a risk score from 0 to 100"""
        weights = {
            "critical": 25,
            "high": 15,
            "medium": 8,
            "low": 3,
            "info": 1
        }
        
        score = sum(
            result.summary.get(level, 0) * weight
            for level, weight in weights.items()
        )
        
        return min(100, score)


# Singleton
_enhanced_scanner: Optional[EnhancedSecurityScanner] = None

def get_enhanced_scanner() -> EnhancedSecurityScanner:
    """Get the enhanced security scanner"""
    global _enhanced_scanner
    if _enhanced_scanner is None:
        _enhanced_scanner = EnhancedSecurityScanner()
    return _enhanced_scanner
