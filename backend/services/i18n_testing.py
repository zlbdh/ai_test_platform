# -*- coding: utf-8 -*-
"""
Internationalization testing service.
Checks multilingual support, text truncation, RTL layout, and encoding problems.
"""
import asyncio
import logging
import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class I18nIssue:
    rule_id: str
    description: str
    severity: str  # "critical", "major", "minor"
    locale: str = ""
    element: str = ""
    suggestion: str = ""
    
    def to_dict(self):
        return asdict(self)


@dataclass
class I18nReport:
    url: str
    locales_tested: List[str] = field(default_factory=list)
    total_issues: int = 0
    issues: List[Dict] = field(default_factory=list)
    score: float = 100.0
    summary: str = ""
    
    def to_dict(self):
        return asdict(self)


# Injected JavaScript for text truncation and encoding checks
I18N_CHECK_SCRIPT = """
(locale) => {
    const issues = [];
    
    // 1. Check text truncation and overflow
    document.querySelectorAll('*').forEach(el => {
        const style = window.getComputedStyle(el);
        if (style.overflow === 'hidden' || style.textOverflow === 'ellipsis') {
            if (el.scrollWidth > el.clientWidth + 2) {
                const text = (el.textContent || '').trim().substring(0, 50);
                if (text) {
                    issues.push({
                        rule_id: 'text-truncation',
                        description: `Text is truncated: "${text}..."`,
                        severity: 'major',
                        locale: locale,
                        element: el.tagName.toLowerCase() + (el.className ? '.' + el.className.split(' ')[0] : ''),
                        suggestion: 'Increase the container width or use an adaptive layout'
                    });
                }
            }
        }
    });
    
    // 2. Check encoding issues using replacement characters
    const bodyText = document.body.innerText || '';
    const replacementChars = (bodyText.match(/[\\ufffd\\u25a1\\?]{2,}/g) || []);
    if (replacementChars.length > 0) {
        issues.push({
            rule_id: 'encoding-issue',
            description: `Found ${replacementChars.length} possible encoding issues (replacement characters □ or ?)`,
            severity: 'critical',
            locale: locale,
            suggestion: 'Use UTF-8 encoding and verify font support for the target character set'
        });
    }
    
    // 3. Check common untranslated, hardcoded text patterns
    const hardcodedPatterns = [
        { pattern: /\\b(OK|Cancel|Submit|Loading|Error|Success|Warning|Delete|Save|Edit|Back|Next|Previous|Close)\\b/g, lang: 'en' },
    ];
    
    const textNodes = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
    while (walker.nextNode()) {
        const text = walker.currentNode.textContent.trim();
        if (text.length > 2 && text.length < 100) textNodes.push(text);
    }
    
    // Check hardcoded English text only when the locale is not English
    if (locale && !locale.startsWith('en')) {
        const englishMatches = textNodes.filter(t => /^[A-Za-z\\s]{3,}$/.test(t));
        if (englishMatches.length > 5) {
            issues.push({
                rule_id: 'hardcoded-text',
                description: `Found ${englishMatches.length} possible instances of hardcoded English text`,
                severity: 'minor',
                locale: locale,
                element: englishMatches.slice(0, 3).join(', '),
                suggestion: 'Replace hardcoded text with i18n translation calls'
            });
        }
    }
    
    // 4. Check RTL layout
    const dir = document.documentElement.dir || document.body.dir || '';
    const isRTL = ['ar', 'he', 'fa', 'ur'].some(l => locale.startsWith(l));
    if (isRTL && dir !== 'rtl') {
        issues.push({
            rule_id: 'rtl-missing',
            description: 'An RTL language is in use, but the page has no dir="rtl"',
            severity: 'critical',
            locale: locale,
            suggestion: 'Use <html dir="rtl"> or CSS logical properties for RTL languages'
        });
    }
    
    // 5. Check date formatting
    const datePatterns = bodyText.match(/\\d{1,2}\\/\\d{1,2}\\/\\d{2,4}/g) || [];
    if (datePatterns.length > 0 && locale && !locale.startsWith('en')) {
        issues.push({
            rule_id: 'date-format',
            description: `Found ${datePatterns.length} possibly unlocalized dates (MM/DD/YYYY)`,
            severity: 'minor',
            locale: locale,
            element: datePatterns.slice(0, 2).join(', '),
            suggestion: 'Use Intl.DateTimeFormat or locale-aware date formatting'
        });
    }
    
    return issues;
}
"""


class I18nTestService:
    """Internationalization testing service"""
    
    async def test_locale(self, url: str, locales: List[str]) -> I18nReport:
        """Test page behavior across multiple locales"""
        return await asyncio.to_thread(self._test_locale_sync, url, locales)

    def _test_locale_sync(self, url: str, locales: List[str]) -> I18nReport:
        """Synchronous implementation of testing page behavior across multiple locales"""
        import time
        report = I18nReport(url=url, locales_tested=locales)
        all_issues = []
        
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                
                for locale in locales:
                    try:
                        context = browser.new_context(
                            locale=locale,
                            extra_http_headers={"Accept-Language": locale}
                        )
                        page = context.new_page()
                        page.goto(url, wait_until='networkidle', timeout=30000)
                        time.sleep(0.5)
                        
                        issues = page.evaluate(I18N_CHECK_SCRIPT, locale)
                        all_issues.extend(issues)
                        
                        context.close()
                    except Exception as e:
                        all_issues.append({
                            "rule_id": "locale-error",
                            "description": f"Locale {locale} test failed: {str(e)}",
                            "severity": "major",
                            "locale": locale
                        })
                
                browser.close()
            
        except ImportError:
            report.summary = "Playwright is not installed. Run: pip install playwright && playwright install chromium"
            report.score = -1
            return report
        except Exception as e:
            report.summary = f"Test failed: {repr(e)}"
            report.score = -1
            return report
        
        report.issues = all_issues
        report.total_issues = len(all_issues)
        critical = sum(1 for i in all_issues if i.get("severity") == "critical")
        major = sum(1 for i in all_issues if i.get("severity") == "major")
        minor = sum(1 for i in all_issues if i.get("severity") == "minor")
        deduction = critical * 20 + major * 10 + minor * 3
        report.score = max(0, min(100, 100 - deduction))
        report.summary = f"Tested {len(locales)} locales: found {report.total_issues} issues, score {report.score}/100"
        
        return report
    
    async def quick_check(self, url: str, locale: str = "en-US") -> Dict[str, Any]:
        """Quick check using HTTP and static HTML analysis"""
        import aiohttp
        
        issues = []
        try:
            headers = {"Accept-Language": locale}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    html = await resp.text()
            
            # Check encoding
            if '<meta' in html.lower() and 'charset' not in html[:500].lower():
                issues.append({"rule_id": "charset-missing", "description": "Character encoding is not declared", "severity": "major", "locale": locale})
            
            # lang attribute
            if 'lang=' not in html[:300].lower():
                issues.append({"rule_id": "html-lang", "description": "HTML is missing the lang attribute", "severity": "major", "locale": locale})
            
            return {"status": "success", "url": url, "locale": locale, "issues": issues, "total": len(issues), "mode": "quick"}
        except Exception as e:
            return {"status": "error", "url": url, "error": str(e)}


def create_i18n_service():
    return I18nTestService()
