# -*- coding: utf-8 -*-
"""
Compliance testing service: automated GDPR, SOC 2, and PCI DSS checks.
Uses HTTP response header analysis and Playwright page inspection.
"""
import asyncio
import logging
import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ComplianceIssue:
    rule_id: str
    standard: str  # "GDPR", "SOC2", "PCI-DSS", "GENERAL"
    description: str
    severity: str
    suggestion: str = ""
    details: str = ""
    
    def to_dict(self):
        return asdict(self)


@dataclass
class ComplianceReport:
    url: str
    standards_checked: List[str] = field(default_factory=list)
    total_issues: int = 0
    critical: int = 0
    major: int = 0
    minor: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    score: float = 100.0
    issues: List[Dict] = field(default_factory=list)
    summary: str = ""
    
    def to_dict(self):
        return asdict(self)


# JavaScript for GDPR page checks
GDPR_CHECK_SCRIPT = """
() => {
    const issues = [];
    const bodyText = (document.body.innerText || '').toLowerCase();
    const bodyHtml = (document.body.innerHTML || '').toLowerCase();
    
    // 1. Check cookie consent banners
    const cookieIndicators = ['cookie', 'consent', '同意', 'cookie policy', 'accept cookies', 'cookie设置'];
    const hasCookieBanner = cookieIndicators.some(kw => bodyText.includes(kw)) ||
        document.querySelector('[class*="cookie"], [id*="cookie"], [class*="consent"], [id*="consent"]');
    if (!hasCookieBanner) {
        issues.push({
            rule_id: 'gdpr-cookie-consent',
            standard: 'GDPR',
            description: 'No cookie consent banner detected',
            severity: 'critical',
            suggestion: 'Add cookie consent management and do not set nonessential cookies before consent'
        });
    }
    
    // 2. Check privacy policy links
    const privacyLinks = document.querySelectorAll('a[href*="privacy"], a[href*="隐私"]');
    const privacyTextLinks = Array.from(document.querySelectorAll('a')).filter(a => {
        const text = (a.textContent || '').toLowerCase();
        return text.includes('privacy') || text.includes('隐私') || text.includes('privacy policy');
    });
    if (privacyLinks.length === 0 && privacyTextLinks.length === 0) {
        issues.push({
            rule_id: 'gdpr-privacy-policy',
            standard: 'GDPR',
            description: 'No privacy policy link detected',
            severity: 'major',
            suggestion: 'Add a privacy policy link in the footer or another visible location'
        });
    }
    
    // 3. Check data deletion and export access
    const dataRightsKeywords = ['delete account', 'export data', '删除账号', '导出数据', 'data request', '注销'];
    const hasDataRights = dataRightsKeywords.some(kw => bodyText.includes(kw));
    if (!hasDataRights) {
        issues.push({
            rule_id: 'gdpr-data-rights',
            standard: 'GDPR',
            description: 'No data deletion or export entry point detected',
            severity: 'minor',
            suggestion: 'Provide access to data export and account deletion'
        });
    }
    
    // 4. Check form data collection notices
    const forms = document.querySelectorAll('form');
    forms.forEach((form, i) => {
        const formText = (form.textContent || '').toLowerCase();
        const hasPrivacyNote = formText.includes('privacy') || formText.includes('隐私') || 
            formText.includes('agree') || formText.includes('同意') || formText.includes('terms');
        const hasInputs = form.querySelectorAll('input[type="email"], input[type="tel"], input[name*="phone"], input[name*="address"]').length > 0;
        if (hasInputs && !hasPrivacyNote) {
            issues.push({
                rule_id: 'gdpr-form-consent',
                standard: 'GDPR',
                description: `Form ${i + 1} collects personal data without a privacy notice`,
                severity: 'major',
                suggestion: 'Add a privacy notice and consent checkbox to forms that collect personal data'
            });
        }
    });
    
    return issues;
}
"""

# JavaScript for PCI DSS page checks
PCIDSS_CHECK_SCRIPT = """
() => {
    const issues = [];
    
    // 1. Check credit card field autocomplete
    const ccFields = document.querySelectorAll('input[type="text"][name*="card"], input[type="text"][name*="credit"], input[name*="cc-number"], input[autocomplete*="cc-"]');
    ccFields.forEach(field => {
        if (field.getAttribute('autocomplete') !== 'off') {
            issues.push({
                rule_id: 'pci-autocomplete',
                standard: 'PCI-DSS',
                description: 'Autocomplete is not disabled for a credit card field',
                severity: 'critical',
                suggestion: 'Set autocomplete="off" to prevent browser storage of sensitive card numbers'
            });
        }
    });
    
    // 2. Check password field security
    const passwordFields = document.querySelectorAll('input[type="password"]');
    passwordFields.forEach(field => {
        if (field.getAttribute('autocomplete') === 'on') {
            issues.push({
                rule_id: 'pci-password-autocomplete',
                standard: 'PCI-DSS',
                description: 'Autocomplete is enabled for a password field',
                severity: 'major',
                suggestion: 'Set autocomplete="new-password" or "current-password"'
            });
        }
    });
    
    return issues;
}
"""


class ComplianceTestService:
    """Compliance testing service"""
    
    async def audit(self, url: str, standards: Optional[List[str]] = None) -> ComplianceReport:
        """Run a compliance audit"""
        if standards is None:
            standards = ["GDPR", "SOC2", "PCI-DSS"]
        
        report = ComplianceReport(url=url, standards_checked=standards)
        all_issues = []
        total_checks = 0
        
        # 1. HTTP response security header checks for SOC 2 and PCI DSS
        if "SOC2" in standards or "PCI-DSS" in standards:
            header_issues, header_checks = await self._check_security_headers(url)
            all_issues.extend(header_issues)
            total_checks += header_checks
        
        # 2. Page content checks for GDPR and PCI DSS; run Playwright in a worker thread
        if "GDPR" in standards or "PCI-DSS" in standards:
            page_issues, page_checks = await asyncio.to_thread(self._check_page_compliance_sync, url, standards)
            all_issues.extend(page_issues)
            total_checks += page_checks
        
        # Summarize statistics
        report.issues = [i if isinstance(i, dict) else i.to_dict() for i in all_issues]
        report.total_issues = len(report.issues)
        report.critical = sum(1 for i in report.issues if i.get("severity") == "critical")
        report.major = sum(1 for i in report.issues if i.get("severity") == "major")
        report.minor = sum(1 for i in report.issues if i.get("severity") == "minor")
        report.failed_checks = report.total_issues
        report.passed_checks = max(0, total_checks - report.failed_checks)
        
        deduction = report.critical * 15 + report.major * 8 + report.minor * 3
        report.score = max(0, min(100, 100 - deduction))
        report.summary = f"Compliance audit completed ({', '.join(standards)}): {report.total_issues} issues, score {report.score}/100"
        
        return report
    
    async def _check_security_headers(self, url: str) -> tuple:
        """Check security response headers"""
        import aiohttp
        
        issues = []
        checks = 0
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=True) as resp:
                    headers = dict(resp.headers)
            
            # Check HTTPS
            checks += 1
            if not url.startswith("https://"):
                issues.append({
                    "rule_id": "sec-https",
                    "standard": "SOC2",
                    "description": "The page does not use HTTPS",
                    "severity": "critical",
                    "suggestion": "Require HTTPS and configure HSTS"
                })
            
            # HSTS
            checks += 1
            if "strict-transport-security" not in {k.lower(): v for k, v in headers.items()}:
                issues.append({
                    "rule_id": "sec-hsts",
                    "standard": "SOC2",
                    "description": "Missing Strict-Transport-Security header",
                    "severity": "major",
                    "suggestion": "Add Strict-Transport-Security: max-age=31536000; includeSubDomains"
                })
            
            headers_lower = {k.lower(): v for k, v in headers.items()}
            
            # CSP
            checks += 1
            if "content-security-policy" not in headers_lower:
                issues.append({
                    "rule_id": "sec-csp",
                    "standard": "SOC2",
                    "description": "Missing Content-Security-Policy header",
                    "severity": "major",
                    "suggestion": "Configure CSP to prevent XSS and injection attacks"
                })
            
            # X-Frame-Options
            checks += 1
            if "x-frame-options" not in headers_lower:
                issues.append({
                    "rule_id": "sec-xfo",
                    "standard": "SOC2",
                    "description": "Missing X-Frame-Options header",
                    "severity": "major",
                    "suggestion": "Add X-Frame-Options: DENY or SAMEORIGIN"
                })
            
            # X-Content-Type-Options
            checks += 1
            if "x-content-type-options" not in headers_lower:
                issues.append({
                    "rule_id": "sec-xcto",
                    "standard": "SOC2",
                    "description": "Missing X-Content-Type-Options header",
                    "severity": "minor",
                    "suggestion": "Add X-Content-Type-Options: nosniff"
                })
            
            # Referrer-Policy
            checks += 1
            if "referrer-policy" not in headers_lower:
                issues.append({
                    "rule_id": "sec-referrer",
                    "standard": "SOC2",
                    "description": "Missing Referrer-Policy header",
                    "severity": "minor",
                    "suggestion": "Add Referrer-Policy: strict-origin-when-cross-origin"
                })
            
            # Cookie security flags
            checks += 1
            set_cookie_headers = [v for k, v in headers.items() if k.lower() == "set-cookie"]
            for cookie in set_cookie_headers:
                cookie_lower = cookie.lower()
                if "secure" not in cookie_lower and url.startswith("https"):
                    issues.append({
                        "rule_id": "sec-cookie-secure",
                        "standard": "PCI-DSS",
                        "description": f"Cookie is missing the Secure flag",
                        "severity": "major",
                        "suggestion": "Set the Secure flag on all cookies"
                    })
                if "httponly" not in cookie_lower:
                    issues.append({
                        "rule_id": "sec-cookie-httponly",
                        "standard": "PCI-DSS",
                        "description": f"Cookie is missing the HttpOnly flag",
                        "severity": "major",
                        "suggestion": "Set the HttpOnly flag on sensitive cookies"
                    })
        
        except Exception as e:
            issues.append({
                "rule_id": "sec-error",
                "standard": "GENERAL",
                "description": f"Security header check failed: {str(e)}",
                "severity": "major"
            })
        
        return issues, checks
    
    def _check_page_compliance_sync(self, url: str, standards: List[str]) -> tuple:
        """Synchronous implementation of Playwright page compliance checks"""
        import time
        issues = []
        checks = 0
        
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until='networkidle', timeout=30000)
                time.sleep(1)
                
                if "GDPR" in standards:
                    gdpr_issues = page.evaluate(GDPR_CHECK_SCRIPT)
                    issues.extend(gdpr_issues)
                    checks += 4
                
                if "PCI-DSS" in standards:
                    pci_issues = page.evaluate(PCIDSS_CHECK_SCRIPT)
                    issues.extend(pci_issues)
                    checks += 2
                
                browser.close()
        
        except ImportError:
            issues.append({
                "rule_id": "playwright-missing",
                "standard": "GENERAL",
                "description": "Playwright is not installed; skipping page compliance checks",
                "severity": "minor",
                "suggestion": "pip install playwright && playwright install chromium"
            })
        except Exception as e:
            issues.append({
                "rule_id": "page-check-error",
                "standard": "GENERAL",
                "description": f"Page compliance check failed: {repr(e)}",
                "severity": "major"
            })
        
        return issues, checks


def create_compliance_service():
    return ComplianceTestService()
