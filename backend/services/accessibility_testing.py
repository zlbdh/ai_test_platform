# -*- coding: utf-8 -*-
"""
无障碍测试服务 — WCAG 2.1 AA 级别自动化审计
基于 Playwright + JS 注入实现规则检测
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


# JS 注入脚本：在浏览器中执行无障碍检查
A11Y_CHECK_SCRIPT = """
() => {
    const issues = [];
    
    // 1. 图片 alt 属性检查 (WCAG 1.1.1 - Level A)
    document.querySelectorAll('img').forEach((img, i) => {
        if (!img.alt && !img.getAttribute('aria-label') && !img.getAttribute('aria-labelledby') && img.getAttribute('role') !== 'presentation') {
            issues.push({
                rule_id: 'img-alt',
                description: '图片缺少 alt 属性',
                severity: 'critical',
                wcag_level: 'A',
                element: img.outerHTML.substring(0, 120),
                selector: img.id ? `#${img.id}` : `img:nth-of-type(${i + 1})`,
                suggestion: '为图片添加描述性 alt 文本，或设置 role="presentation" 标记装饰性图片'
            });
        }
    });
    
    // 2. 表单 label 关联检查 (WCAG 1.3.1 - Level A)
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
                description: '表单控件缺少关联 label',
                severity: 'major',
                wcag_level: 'A',
                element: el.outerHTML.substring(0, 120),
                selector: id ? `#${id}` : `${el.tagName.toLowerCase()}:nth-of-type(${i + 1})`,
                suggestion: '使用 <label for="id"> 或 aria-label 关联表单控件'
            });
        }
    });
    
    // 3. 颜色对比度检查 (WCAG 1.4.3 - Level AA) - 采样检查文本元素
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
                    description: `颜色对比度不足: ${ratio.toFixed(2)}:1 (最低要求 ${minRatio}:1)`,
                    severity: 'major',
                    wcag_level: 'AA',
                    element: el.textContent.substring(0, 60),
                    selector: el.id ? `#${el.id}` : el.tagName.toLowerCase(),
                    suggestion: `调整前景色或背景色以达到 ${minRatio}:1 的对比度`
                });
            }
        }
    }
    
    // 4. 页面标题检查 (WCAG 2.4.2 - Level A)
    if (!document.title || document.title.trim() === '') {
        issues.push({
            rule_id: 'page-title',
            description: '页面缺少 title 标签',
            severity: 'major',
            wcag_level: 'A',
            element: '<head>',
            selector: 'head > title',
            suggestion: '添加描述性的 <title> 标签'
        });
    }
    
    // 5. 标题层级检查 (WCAG 1.3.1 - Level A)
    const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
    let lastLevel = 0;
    headings.forEach(h => {
        const level = parseInt(h.tagName[1]);
        if (level > lastLevel + 1 && lastLevel > 0) {
            issues.push({
                rule_id: 'heading-order',
                description: `标题层级跳跃: h${lastLevel} → h${level}`,
                severity: 'minor',
                wcag_level: 'A',
                element: h.textContent.substring(0, 60),
                selector: h.tagName.toLowerCase(),
                suggestion: '确保标题层级连续递增，不跳过层级'
            });
        }
        lastLevel = level;
    });
    
    // 6. 语言属性检查 (WCAG 3.1.1 - Level A)
    if (!document.documentElement.lang) {
        issues.push({
            rule_id: 'html-lang',
            description: 'HTML 元素缺少 lang 属性',
            severity: 'major',
            wcag_level: 'A',
            element: '<html>',
            selector: 'html',
            suggestion: '在 <html> 标签上添加 lang 属性，如 lang="zh-CN"'
        });
    }
    
    // 7. ARIA 角色检查
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
                description: `无效的 ARIA role: "${role}"`,
                severity: 'minor',
                wcag_level: 'A',
                element: el.outerHTML.substring(0, 120),
                selector: el.id ? `#${el.id}` : el.tagName.toLowerCase(),
                suggestion: '使用有效的 WAI-ARIA role 值'
            });
        }
    });
    
    // 8. 链接文本检查 (WCAG 2.4.4 - Level A)
    document.querySelectorAll('a').forEach(a => {
        const text = (a.textContent || '').trim();
        const ariaLabel = a.getAttribute('aria-label');
        if (!text && !ariaLabel && !a.querySelector('img[alt]')) {
            issues.push({
                rule_id: 'link-text',
                description: '链接缺少可访问文本',
                severity: 'critical',
                wcag_level: 'A',
                element: a.outerHTML.substring(0, 120),
                selector: a.id ? `#${a.id}` : 'a',
                suggestion: '为链接添加描述性文本或 aria-label'
            });
        }
    });
    
    // 9. Tab 键可聚焦检查 (WCAG 2.1.1 - Level A) - interactive elements
    document.querySelectorAll('a[href], button, input, select, textarea, [tabindex]').forEach(el => {
        const tabindex = el.getAttribute('tabindex');
        if (tabindex && parseInt(tabindex) > 0) {
            issues.push({
                rule_id: 'tabindex-positive',
                description: `tabindex 为正数 (${tabindex})，可能导致焦点顺序混乱`,
                severity: 'minor',
                wcag_level: 'A',
                element: el.outerHTML.substring(0, 120),
                selector: el.id ? `#${el.id}` : el.tagName.toLowerCase(),
                suggestion: '将 tabindex 设为 0（使用 DOM 顺序）或 -1（仅编程可聚焦）'
            });
        }
    });
    
    return issues;
    
    // 辅助函数：解析颜色
    function parseColor(c) {
        const m = c.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
        return m ? { r: parseInt(m[1]), g: parseInt(m[2]), b: parseInt(m[3]) } : { r: 0, g: 0, b: 0 };
    }
    
    // 辅助函数：计算对比度
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
    """WCAG 2.1 无障碍测试服务"""
    
    async def audit(self, url: str, level: str = "AA") -> AccessibilityReport:
        """对指定 URL 执行无障碍审计"""
        return await asyncio.to_thread(self._audit_sync, url, level)

    def _audit_sync(self, url: str, level: str = "AA") -> AccessibilityReport:
        """同步版本：对指定 URL 执行无障碍审计"""
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
            
            report.summary = f"审计完成: 共发现 {report.total_issues} 个问题 (严重 {report.critical}, 重要 {report.major}, 轻微 {report.minor}), 无障碍评分 {report.score}/100"
            
        except ImportError:
            report.summary = "Playwright 未安装，请执行: pip install playwright && playwright install chromium"
            report.score = -1
        except Exception as e:
            logger.error(f"无障碍审计失败: {repr(e)}")
            report.summary = f"审计失败: {repr(e)}"
            report.score = -1
        
        return report
    
    async def quick_check(self, url: str) -> Dict[str, Any]:
        """快速检查（不使用 Playwright，通过 HTTP 获取 HTML 分析）"""
        import aiohttp
        
        issues = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    html = await resp.text()
            
            # 基础 HTML 静态分析
            if '<html' in html.lower() and 'lang=' not in html[:200].lower():
                issues.append({"rule_id": "html-lang", "description": "HTML 缺少 lang 属性", "severity": "major", "wcag_level": "A"})
            
            if '<title>' not in html.lower() or '<title></title>' in html.lower():
                issues.append({"rule_id": "page-title", "description": "页面缺少 title", "severity": "major", "wcag_level": "A"})
            
            # 检查 img 标签
            import re
            imgs_no_alt = re.findall(r'<img(?![^>]*alt=)[^>]*>', html, re.IGNORECASE)
            for img in imgs_no_alt[:5]:
                if 'role="presentation"' not in img.lower():
                    issues.append({"rule_id": "img-alt", "description": "图片缺少 alt 属性", "severity": "critical", "wcag_level": "A", "element": img[:100]})
            
            return {"status": "success", "url": url, "issues": issues, "total": len(issues), "mode": "quick"}
        except Exception as e:
            return {"status": "error", "url": url, "error": str(e)}


def create_accessibility_service():
    return AccessibilityTestService()
