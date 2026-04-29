# -*- coding: utf-8 -*-
"""
国际化 (i18n) 测试服务
检测多语言支持、文本截断、RTL 布局、编码问题
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


# JS 注入：检测文本截断和编码问题
I18N_CHECK_SCRIPT = """
(locale) => {
    const issues = [];
    
    // 1. 文本截断检测 — 检查 overflow
    document.querySelectorAll('*').forEach(el => {
        const style = window.getComputedStyle(el);
        if (style.overflow === 'hidden' || style.textOverflow === 'ellipsis') {
            if (el.scrollWidth > el.clientWidth + 2) {
                const text = (el.textContent || '').trim().substring(0, 50);
                if (text) {
                    issues.push({
                        rule_id: 'text-truncation',
                        description: `文本被截断: "${text}..."`,
                        severity: 'major',
                        locale: locale,
                        element: el.tagName.toLowerCase() + (el.className ? '.' + el.className.split(' ')[0] : ''),
                        suggestion: '增大容器宽度或使用自适应布局'
                    });
                }
            }
        }
    });
    
    // 2. 编码问题检测 — 替代字符
    const bodyText = document.body.innerText || '';
    const replacementChars = (bodyText.match(/[\\ufffd\\u25a1\\?]{2,}/g) || []);
    if (replacementChars.length > 0) {
        issues.push({
            rule_id: 'encoding-issue',
            description: `发现 ${replacementChars.length} 处可能的编码问题（替代字符 □ 或 ?）`,
            severity: 'critical',
            locale: locale,
            suggestion: '确保页面使用 UTF-8 编码，检查字体是否支持目标语言字符集'
        });
    }
    
    // 3. 硬编码文本检测 — 检查常见的未翻译模式
    const hardcodedPatterns = [
        { pattern: /\\b(OK|Cancel|Submit|Loading|Error|Success|Warning|Delete|Save|Edit|Back|Next|Previous|Close)\\b/g, lang: 'en' },
    ];
    
    const textNodes = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
    while (walker.nextNode()) {
        const text = walker.currentNode.textContent.trim();
        if (text.length > 2 && text.length < 100) textNodes.push(text);
    }
    
    // 仅当 locale 不是英语时检查英文硬编码
    if (locale && !locale.startsWith('en')) {
        const englishMatches = textNodes.filter(t => /^[A-Za-z\\s]{3,}$/.test(t));
        if (englishMatches.length > 5) {
            issues.push({
                rule_id: 'hardcoded-text',
                description: `发现 ${englishMatches.length} 处可能的硬编码英文文本`,
                severity: 'minor',
                locale: locale,
                element: englishMatches.slice(0, 3).join(', '),
                suggestion: '将硬编码文本替换为 i18n 翻译函数调用'
            });
        }
    }
    
    // 4. RTL 布局检查
    const dir = document.documentElement.dir || document.body.dir || '';
    const isRTL = ['ar', 'he', 'fa', 'ur'].some(l => locale.startsWith(l));
    if (isRTL && dir !== 'rtl') {
        issues.push({
            rule_id: 'rtl-missing',
            description: 'RTL 语言但页面未设置 dir="rtl"',
            severity: 'critical',
            locale: locale,
            suggestion: '为 RTL 语言设置 <html dir="rtl"> 或使用 CSS logical properties'
        });
    }
    
    // 5. 日期格式检测
    const datePatterns = bodyText.match(/\\d{1,2}\\/\\d{1,2}\\/\\d{2,4}/g) || [];
    if (datePatterns.length > 0 && locale && !locale.startsWith('en')) {
        issues.push({
            rule_id: 'date-format',
            description: `发现 ${datePatterns.length} 处可能的非本地化日期格式 (MM/DD/YYYY)`,
            severity: 'minor',
            locale: locale,
            element: datePatterns.slice(0, 2).join(', '),
            suggestion: '使用 Intl.DateTimeFormat 或 locale-aware 日期格式化'
        });
    }
    
    return issues;
}
"""


class I18nTestService:
    """国际化测试服务"""
    
    async def test_locale(self, url: str, locales: List[str]) -> I18nReport:
        """测试多个 locale 下的页面表现"""
        return await asyncio.to_thread(self._test_locale_sync, url, locales)

    def _test_locale_sync(self, url: str, locales: List[str]) -> I18nReport:
        """同步版本：测试多个 locale 下的页面表现"""
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
                            "description": f"Locale {locale} 测试失败: {str(e)}",
                            "severity": "major",
                            "locale": locale
                        })
                
                browser.close()
            
        except ImportError:
            report.summary = "Playwright 未安装，请执行: pip install playwright && playwright install chromium"
            report.score = -1
            return report
        except Exception as e:
            report.summary = f"测试失败: {repr(e)}"
            report.score = -1
            return report
        
        report.issues = all_issues
        report.total_issues = len(all_issues)
        critical = sum(1 for i in all_issues if i.get("severity") == "critical")
        major = sum(1 for i in all_issues if i.get("severity") == "major")
        minor = sum(1 for i in all_issues if i.get("severity") == "minor")
        deduction = critical * 20 + major * 10 + minor * 3
        report.score = max(0, min(100, 100 - deduction))
        report.summary = f"测试了 {len(locales)} 个语言: 发现 {report.total_issues} 个问题, 评分 {report.score}/100"
        
        return report
    
    async def quick_check(self, url: str, locale: str = "zh-CN") -> Dict[str, Any]:
        """快速检查（HTTP 获取 HTML 静态分析）"""
        import aiohttp
        
        issues = []
        try:
            headers = {"Accept-Language": locale}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    html = await resp.text()
            
            # 编码检查
            if '<meta' in html.lower() and 'charset' not in html[:500].lower():
                issues.append({"rule_id": "charset-missing", "description": "未声明字符编码", "severity": "major", "locale": locale})
            
            # lang 属性
            if 'lang=' not in html[:300].lower():
                issues.append({"rule_id": "html-lang", "description": "HTML 缺少 lang 属性", "severity": "major", "locale": locale})
            
            return {"status": "success", "url": url, "locale": locale, "issues": issues, "total": len(issues), "mode": "quick"}
        except Exception as e:
            return {"status": "error", "url": url, "error": str(e)}


def create_i18n_service():
    return I18nTestService()
