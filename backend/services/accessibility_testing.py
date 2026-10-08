# -*- coding: utf-8 -*-
"""
Accessibility testing service: automated WCAG 2.1 AA audits.
Checks rules using Playwright and injected JavaScript.
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class WCAGLevel(str, Enum):
    A = "A"
    AA = "AA"
    AAA = "AAA"


class Severity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


@dataclass
class AccessibilityIssue:
    rule_id: str
    description: str
    severity: str
    wcag_level: str
    element: str = ""
    selector: str = ""
    suggestion: str = ""
    
    def to_dict(self):
        return asdict(self)


@dataclass
class AccessibilityReport:
    url: str
    total_issues: int = 0
    critical: int = 0
    major: int = 0
    minor: int = 0
    passed_rules: int = 0
    failed_rules: int = 0
    score: float = 100.0
    issues: List[Dict] = field(default_factory=list)
    summary: str = ""
    
    def to_dict(self):
        return asdict(self)


# JavaScript injected into the browser to run accessibility checks
A11Y_CHECK_SCRIPT = """
() => {
    const issues = [];
    
    // 1. Check image alt attributes (WCAG 1.1.1 - Level A)
    document.querySelectorAll('img').forEach((img, i) => {
        if (!img.alt && !img.getAttribute('aria-label') && !img.getAttribute('aria-labelledby') && img.getAttribute('role') !== 'presentation') {
            issues.push({
                rule_id: 'img-alt',
                description: 'Image is missing an alt attribute',
                severity: 'critical',
                wcag_level: 'A',
                element: img.outerHTML.substring(0, 120),
                selector: img.id ? `#${img.id}` : `img:nth-of-type(${i + 1})`,
                suggestion: 'Add descriptive alt text, or use role="presentation" for decorative images'
            });
        }
    });
    
    // 2. Check form label associations (WCAG 1.3.1 - Level A)
    document.querySelectorAll('input, select, textarea').forEach((el, i) => {
        const type = el.getAttribute('type');
        if (type === 'hidden' || type === 'submit' || type === 'button' || type === 'reset') return;
        const id = el.id;
        const hasLabel = id && document.querySelector(`label[for="${id}"]`);
        const hasAriaLabel = el.getAttribute('aria-label') || el.getAttribute('aria-labelledby');
        const parentLabel = el.closest('label');
        if (!hasLabel && !hasAriaLabel && !parentLabel) {
            issues.push({
                rule_id: 'form-label',
                description: 'Form control has no associated label',
                severity: 'major',
                wcag_level: 'A',
                element: el.outerHTML.substring(0, 120),
                selector: id ? `#${id}` : `${el.tagName.toLowerCase()}:nth-of-type(${i + 1})`,
                suggestion: 'Associate the form control with <label for="id"> or aria-label'
            });
        }
    });
    
    // 3. Check color contrast (WCAG 1.4.3 - Level AA) - Sample text elements
    const textElements = document.querySelectorAll('p, span, a, h1, h2, h3, h4, h5, h6, li, td, th, label, button');
    const sampleSize = Math.min(textElements.length, 50);
    for (let i = 0; i < sampleSize; i++) {
        const el = textElements[i];
        const style = window.getComputedStyle(el);
        const color = style.color;
        const bgColor = style.backgroundColor;
        if (color && bgColor && bgColor !== 'rgba(0, 0, 0, 0)') {
            const ratio = getContrastRatio(parseColor(color), parseColor(bgColor));
            const fontSize = parseFloat(style.fontSize);
            const isBold = parseInt(style.fontWeight) >= 700;
            const isLargeText = fontSize >= 18 || (fontSize >= 14 && isBold);
            const minRatio = isLargeText ? 3.0 : 4.5;
            if (ratio < minRatio) {
                issues.push({
                    rule_id: 'color-contrast',
                    description: `Insufficient color contrast: ${ratio.toFixed(2)}:1 (minimum ${minRatio}:1)`,
                    severity: 'major',
                    wcag_level: 'AA',
                    element: el.textContent.substring(0, 60),
                    selector: el.id ? `#${el.id}` : el.tagName.toLowerCase(),
                    suggestion: `Adjust foreground or background colors to reach a ${minRatio}:1 contrast ratio`
                });
            }
        }
    }
    
    // 4. Check page title (WCAG 2.4.2 - Level A)
    if (!document.title || document.title.trim() === '') {
        issues.push({
            rule_id: 'page-title',
            description: 'Page has no title element',
            severity: 'major',
            wcag_level: 'A',
            element: '<head>',
            selector: 'head > title',
            suggestion: 'Add a descriptive <title> element'
        });
    }
    
    // 5. Check heading order (WCAG 1.3.1 - Level A)
    const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
    let lastLevel = 0;
    headings.forEach(h => {
        const level = parseInt(h.tagName[1]);
        if (level > lastLevel + 1 && lastLevel > 0) {
            issues.push({
                rule_id: 'heading-order',
                description: `Heading level skipped: h${lastLevel} → h${level}`,
                severity: 'minor',
                wcag_level: 'A',
                element: h.textContent.substring(0, 60),
                selector: h.tagName.toLowerCase(),
                suggestion: 'Keep heading levels sequential without skipping levels'
            });
        }
        lastLevel = level;
    });
    
    // 6. Check language attribute (WCAG 3.1.1 - Level A)
    if (!document.documentElement.lang) {
        issues.push({
            rule_id: 'html-lang',
            description: 'HTML element has no lang attribute',
            severity: 'major',
            wcag_level: 'A',
            element: '<html>',
            selector: 'html',
            suggestion: 'Add a lang attribute to <html>, such as lang="en-US"'
        });
    }
    
    // 7. Check ARIA roles
    document.querySelectorAll('[role]').forEach(el => {
        const role = el.getAttribute('role');
        const validRoles = ['alert','alertdialog','application','article','banner','button','cell',
            'checkbox','columnheader','combobox','complementary','contentinfo','definition','dialog',
            'directory','document','feed','figure','form','grid','gridcell','group','heading','img',
            'link','list','listbox','listitem','log','main','marquee','math','menu','menubar',
            'menuitem','menuitemcheckbox','menuitemradio','navigation','none','note','option',
            'presentation','progressbar','radio','radiogroup','region','row','rowgroup','rowheader',
            'scrollbar','search','searchbox','separator','slider','spinbutton','status','switch',
            'tab','table','tablist','tabpanel','term','textbox','timer','toolbar','tooltip','tree',
            'treegrid','treeitem'];
        if (!validRoles.includes(role)) {
            issues.push({
                rule_id: 'aria-role',
                description: `Invalid ARIA role: "${role}"`,
                severity: 'minor',
                wcag_level: 'A',
                element: el.outerHTML.substring(0, 120),
                selector: el.id ? `#${el.id}` : el.tagName.toLowerCase(),
                suggestion: 'Use a valid WAI-ARIA role'
            });
        }
    });
    
    // 8. Check link text (WCAG 2.4.4 - Level A)
    document.querySelectorAll('a').forEach(a => {
        const text = (a.textContent || '').trim();
        const ariaLabel = a.getAttribute('aria-label');
        if (!text && !ariaLabel && !a.querySelector('img[alt]')) {
            issues.push({
                rule_id: 'link-text',
                description: 'Link has no accessible text',
                severity: 'critical',
                wcag_level: 'A',
                element: a.outerHTML.substring(0, 120),
                selector: a.id ? `#${a.id}` : 'a',
                suggestion: 'Add descriptive link text or aria-label'
            });
        }
    });
    
    // 9. Check keyboard focus (WCAG 2.1.1 - Level A) - interactive elements
    document.querySelectorAll('a[href], button, input, select, textarea, [tabindex]').forEach(el => {
        const tabindex = el.getAttribute('tabindex');
        if (tabindex && parseInt(tabindex) > 0) {
            issues.push({
                rule_id: 'tabindex-positive',
                description: `Positive tabindex (${tabindex}) may disrupt focus order`,
                severity: 'minor',
                wcag_level: 'A',
                element: el.outerHTML.substring(0, 120),
                selector: el.id ? `#${el.id}` : el.tagName.toLowerCase(),
                suggestion: 'Set tabindex to 0 for DOM order or -1 for programmatic focus only'
            });
        }
    });
    
    return issues;
    
    // Helper: parse a color
    function parseColor(c) {
        const m = c.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
        return m ? { r: parseInt(m[1]), g: parseInt(m[2]), b: parseInt(m[3]) } : { r: 0, g: 0, b: 0 };
    }
    
    // Helper: calculate contrast
    function getContrastRatio(c1, c2) {
        const l1 = getLuminance(c1);
        const l2 = getLuminance(c2);
        const lighter = Math.max(l1, l2);
        const darker = Math.min(l1, l2);
        return (lighter + 0.05) / (darker + 0.05);
    }
    
    function getLuminance(c) {
        const rs = c.r / 255, gs = c.g / 255, bs = c.b / 255;
        const r = rs <= 0.03928 ? rs / 12.92 : Math.pow((rs + 0.055) / 1.055, 2.4);
        const g = gs <= 0.03928 ? gs / 12.92 : Math.pow((gs + 0.055) / 1.055, 2.4);
        const b = bs <= 0.03928 ? bs / 12.92 : Math.pow((bs + 0.055) / 1.055, 2.4);
        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    }
}
"""


class AccessibilityTestService:
    """WCAG 2.1 accessibility testing service"""
    
    async def audit(self, url: str, level: str = "AA") -> AccessibilityReport:
        """Run an accessibility audit for the specified URL"""
        return await asyncio.to_thread(self._audit_sync, url, level)

    def _audit_sync(self, url: str, level: str = "AA") -> AccessibilityReport:
        """Synchronous implementation of the URL accessibility audit"""
        import time
        report = AccessibilityReport(url=url)
        
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                
                page.goto(url, wait_until='networkidle', timeout=30000)
                time.sleep(1)
                
                issues_data = page.evaluate(A11Y_CHECK_SCRIPT)
                
                browser.close()
            
            level_order = {"A": 1, "AA": 2, "AAA": 3}
            max_level = level_order.get(level, 2)
            
            filtered = []
            for issue in issues_data:
                issue_level = level_order.get(issue.get("wcag_level", "A"), 1)
                if issue_level <= max_level:
                    filtered.append(issue)
            
            report.issues = filtered
            report.total_issues = len(filtered)
            report.critical = sum(1 for i in filtered if i.get("severity") == "critical")
            report.major = sum(1 for i in filtered if i.get("severity") == "major")
            report.minor = sum(1 for i in filtered if i.get("severity") == "minor")
            
            total_rules = 9
            failed_rule_ids = set(i.get("rule_id") for i in filtered)
            report.failed_rules = len(failed_rule_ids)
            report.passed_rules = total_rules - report.failed_rules
            
            deduction = report.critical * 15 + report.major * 8 + report.minor * 3
            report.score = max(0, min(100, 100 - deduction))
            
            report.summary = f"Audit completed: found {report.total_issues} issues (critical {report.critical}, major {report.major}, minor {report.minor}), accessibility score {report.score}/100"
            
        except ImportError:
            report.summary = "Playwright is not installed. Run: pip install playwright && playwright install chromium"
            report.score = -1
        except Exception as e:
            logger.error(f"Accessibility audit failed: {repr(e)}")
            report.summary = f"Audit failed: {repr(e)}"
            report.score = -1
        
        return report
    
    async def quick_check(self, url: str) -> Dict[str, Any]:
        """Quick check using HTTP and static HTML analysis without Playwright"""
        import aiohttp
        
        issues = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    html = await resp.text()
            
            # Basic static HTML analysis
            if '<html' in html.lower() and 'lang=' not in html[:200].lower():
                issues.append({"rule_id": "html-lang", "description": "HTML is missing the lang attribute", "severity": "major", "wcag_level": "A"})
            
            if '<title>' not in html.lower() or '<title></title>' in html.lower():
                issues.append({"rule_id": "page-title", "description": "The page is missing a title", "severity": "major", "wcag_level": "A"})
            
            # Check img elements
            import re
            imgs_no_alt = re.findall(r'<img(?![^>]*alt=)[^>]*>', html, re.IGNORECASE)
            for img in imgs_no_alt[:5]:
                if 'role="presentation"' not in img.lower():
                    issues.append({"rule_id": "img-alt", "description": "Image is missing an alt attribute", "severity": "critical", "wcag_level": "A", "element": img[:100]})
            
            return {"status": "success", "url": url, "issues": issues, "total": len(issues), "mode": "quick"}
        except Exception as e:
            return {"status": "error", "url": url, "error": str(e)}


def create_accessibility_service():
    return AccessibilityTestService()
