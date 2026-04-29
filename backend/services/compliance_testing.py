# -*- coding: utf-8 -*-
"""
合规测试服务 — GDPR / SOC2 / PCI-DSS 自动化合规检查
基于 HTTP 响应头分析 + Playwright 页面检测
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


# GDPR 页面检查 JS
GDPR_CHECK_SCRIPT = """
() => {
    const issues = [];
    const bodyText = (document.body.innerText || '').toLowerCase();
    const bodyHtml = (document.body.innerHTML || '').toLowerCase();
    
    // 1. Cookie 同意横幅检查
    const cookieIndicators = ['cookie', 'consent', '同意', 'cookie policy', 'accept cookies', 'cookie设置'];
    const hasCookieBanner = cookieIndicators.some(kw => bodyText.includes(kw)) ||
        document.querySelector('[class*="cookie"], [id*="cookie"], [class*="consent"], [id*="consent"]');
    if (!hasCookieBanner) {
        issues.push({
            rule_id: 'gdpr-cookie-consent',
            standard: 'GDPR',
            description: '未检测到 Cookie 同意横幅',
            severity: 'critical',
            suggestion: '添加 Cookie 同意管理组件，在用户同意前不设置非必要 Cookie'
        });
    }
    
    // 2. 隐私政策链接检查
    const privacyLinks = document.querySelectorAll('a[href*="privacy"], a[href*="隐私"]');
    const privacyTextLinks = Array.from(document.querySelectorAll('a')).filter(a => {
        const text = (a.textContent || '').toLowerCase();
        return text.includes('privacy') || text.includes('隐私') || text.includes('privacy policy');
    });
    if (privacyLinks.length === 0 && privacyTextLinks.length === 0) {
        issues.push({
            rule_id: 'gdpr-privacy-policy',
            standard: 'GDPR',
            description: '未检测到隐私政策链接',
            severity: 'major',
            suggestion: '在页脚或明显位置添加隐私政策页面链接'
        });
    }
    
    // 3. 数据删除/导出入口检查
    const dataRightsKeywords = ['delete account', 'export data', '删除账号', '导出数据', 'data request', '注销'];
    const hasDataRights = dataRightsKeywords.some(kw => bodyText.includes(kw));
    if (!hasDataRights) {
        issues.push({
            rule_id: 'gdpr-data-rights',
            standard: 'GDPR',
            description: '未检测到数据删除/导出入口',
            severity: 'minor',
            suggestion: '提供用户数据导出和账号删除功能的入口'
        });
    }
    
    // 4. 表单数据收集声明检查
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
                description: `表单 ${i + 1} 收集个人数据但未包含隐私声明`,
                severity: 'major',
                suggestion: '在收集个人数据的表单中添加隐私声明和同意复选框'
            });
        }
    });
    
    return issues;
}
"""

# PCI-DSS 页面检查 JS
PCIDSS_CHECK_SCRIPT = """
() => {
    const issues = [];
    
    // 1. 信用卡字段 autocomplete 检查
    const ccFields = document.querySelectorAll('input[type="text"][name*="card"], input[type="text"][name*="credit"], input[name*="cc-number"], input[autocomplete*="cc-"]');
    ccFields.forEach(field => {
        if (field.getAttribute('autocomplete') !== 'off') {
            issues.push({
                rule_id: 'pci-autocomplete',
                standard: 'PCI-DSS',
                description: '信用卡字段未禁用 autocomplete',
                severity: 'critical',
                suggestion: '设置 autocomplete="off" 防止浏览器保存敏感卡号信息'
            });
        }
    });
    
    // 2. 密码字段安全检查
    const passwordFields = document.querySelectorAll('input[type="password"]');
    passwordFields.forEach(field => {
        if (field.getAttribute('autocomplete') === 'on') {
            issues.push({
                rule_id: 'pci-password-autocomplete',
                standard: 'PCI-DSS',
                description: '密码字段启用了 autocomplete',
                severity: 'major',
                suggestion: '设置 autocomplete="new-password" 或 "current-password"'
            });
        }
    });
    
    return issues;
}
"""


class ComplianceTestService:
    """合规测试服务"""
    
    async def audit(self, url: str, standards: Optional[List[str]] = None) -> ComplianceReport:
        """执行合规审计"""
        if standards is None:
            standards = ["GDPR", "SOC2", "PCI-DSS"]
        
        report = ComplianceReport(url=url, standards_checked=standards)
        all_issues = []
        total_checks = 0
        
        # 1. HTTP 响应头安全检查 (SOC2 / PCI-DSS)
        if "SOC2" in standards or "PCI-DSS" in standards:
            header_issues, header_checks = await self._check_security_headers(url)
            all_issues.extend(header_issues)
            total_checks += header_checks
        
        # 2. 页面内容检查 (GDPR + PCI-DSS) — 使用线程运行 Playwright
        if "GDPR" in standards or "PCI-DSS" in standards:
            page_issues, page_checks = await asyncio.to_thread(self._check_page_compliance_sync, url, standards)
            all_issues.extend(page_issues)
            total_checks += page_checks
        
        # 统计
        report.issues = [i if isinstance(i, dict) else i.to_dict() for i in all_issues]
        report.total_issues = len(report.issues)
        report.critical = sum(1 for i in report.issues if i.get("severity") == "critical")
        report.major = sum(1 for i in report.issues if i.get("severity") == "major")
        report.minor = sum(1 for i in report.issues if i.get("severity") == "minor")
        report.failed_checks = report.total_issues
        report.passed_checks = max(0, total_checks - report.failed_checks)
        
        deduction = report.critical * 15 + report.major * 8 + report.minor * 3
        report.score = max(0, min(100, 100 - deduction))
        report.summary = f"合规审计完成 ({', '.join(standards)}): {report.total_issues} 个问题, 评分 {report.score}/100"
        
        return report
    
    async def _check_security_headers(self, url: str) -> tuple:
        """检查安全响应头"""
        import aiohttp
        
        issues = []
        checks = 0
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=True) as resp:
                    headers = dict(resp.headers)
            
            # HTTPS 检查
            checks += 1
            if not url.startswith("https://"):
                issues.append({
                    "rule_id": "sec-https",
                    "standard": "SOC2",
                    "description": "页面未使用 HTTPS",
                    "severity": "critical",
                    "suggestion": "强制使用 HTTPS 并配置 HSTS"
                })
            
            # HSTS
            checks += 1
            if "strict-transport-security" not in {k.lower(): v for k, v in headers.items()}:
                issues.append({
                    "rule_id": "sec-hsts",
                    "standard": "SOC2",
                    "description": "缺少 Strict-Transport-Security 头",
                    "severity": "major",
                    "suggestion": "添加 Strict-Transport-Security: max-age=31536000; includeSubDomains"
                })
            
            headers_lower = {k.lower(): v for k, v in headers.items()}
            
            # CSP
            checks += 1
            if "content-security-policy" not in headers_lower:
                issues.append({
                    "rule_id": "sec-csp",
                    "standard": "SOC2",
                    "description": "缺少 Content-Security-Policy 头",
                    "severity": "major",
                    "suggestion": "配置 CSP 以防止 XSS 和注入攻击"
                })
            
            # X-Frame-Options
            checks += 1
            if "x-frame-options" not in headers_lower:
                issues.append({
                    "rule_id": "sec-xfo",
                    "standard": "SOC2",
                    "description": "缺少 X-Frame-Options 头",
                    "severity": "major",
                    "suggestion": "添加 X-Frame-Options: DENY 或 SAMEORIGIN"
                })
            
            # X-Content-Type-Options
            checks += 1
            if "x-content-type-options" not in headers_lower:
                issues.append({
                    "rule_id": "sec-xcto",
                    "standard": "SOC2",
                    "description": "缺少 X-Content-Type-Options 头",
                    "severity": "minor",
                    "suggestion": "添加 X-Content-Type-Options: nosniff"
                })
            
            # Referrer-Policy
            checks += 1
            if "referrer-policy" not in headers_lower:
                issues.append({
                    "rule_id": "sec-referrer",
                    "standard": "SOC2",
                    "description": "缺少 Referrer-Policy 头",
                    "severity": "minor",
                    "suggestion": "添加 Referrer-Policy: strict-origin-when-cross-origin"
                })
            
            # Cookie 安全标志
            checks += 1
            set_cookie_headers = [v for k, v in headers.items() if k.lower() == "set-cookie"]
            for cookie in set_cookie_headers:
                cookie_lower = cookie.lower()
                if "secure" not in cookie_lower and url.startswith("https"):
                    issues.append({
                        "rule_id": "sec-cookie-secure",
                        "standard": "PCI-DSS",
                        "description": f"Cookie 缺少 Secure 标志",
                        "severity": "major",
                        "suggestion": "为所有 Cookie 设置 Secure 标志"
                    })
                if "httponly" not in cookie_lower:
                    issues.append({
                        "rule_id": "sec-cookie-httponly",
                        "standard": "PCI-DSS",
                        "description": f"Cookie 缺少 HttpOnly 标志",
                        "severity": "major",
                        "suggestion": "为敏感 Cookie 设置 HttpOnly 标志"
                    })
        
        except Exception as e:
            issues.append({
                "rule_id": "sec-error",
                "standard": "GENERAL",
                "description": f"安全头检查失败: {str(e)}",
                "severity": "major"
            })
        
        return issues, checks
    
    def _check_page_compliance_sync(self, url: str, standards: List[str]) -> tuple:
        """同步版本：使用 Playwright 检查页面合规性"""
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
                "description": "Playwright 未安装，页面合规检查跳过",
                "severity": "minor",
                "suggestion": "pip install playwright && playwright install chromium"
            })
        except Exception as e:
            issues.append({
                "rule_id": "page-check-error",
                "standard": "GENERAL",
                "description": f"页面合规检查失败: {repr(e)}",
                "severity": "major"
            })
        
        return issues, checks


def create_compliance_service():
    return ComplianceTestService()
