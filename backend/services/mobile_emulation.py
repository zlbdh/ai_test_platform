# -*- coding: utf-8 -*-
"""
移动端模拟测试服务
基于 Playwright 设备描述符模拟多种移动设备，检测响应式布局问题
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


# 预定义设备配置
DEVICE_PRESETS = {
    "iphone_14": {
        "name": "iPhone 14",
        "viewport": {"width": 390, "height": 844},
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "device_scale_factor": 3,
        "is_mobile": True,
        "has_touch": True,
    },
    "iphone_se": {
        "name": "iPhone SE",
        "viewport": {"width": 375, "height": 667},
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
        "device_scale_factor": 2,
        "is_mobile": True,
        "has_touch": True,
    },
    "pixel_7": {
        "name": "Pixel 7",
        "viewport": {"width": 412, "height": 915},
        "user_agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36",
        "device_scale_factor": 2.625,
        "is_mobile": True,
        "has_touch": True,
    },
    "galaxy_s21": {
        "name": "Galaxy S21",
        "viewport": {"width": 360, "height": 800},
        "user_agent": "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Mobile Safari/537.36",
        "device_scale_factor": 3,
        "is_mobile": True,
        "has_touch": True,
    },
    "ipad_pro": {
        "name": "iPad Pro 11",
        "viewport": {"width": 834, "height": 1194},
        "user_agent": "Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "device_scale_factor": 2,
        "is_mobile": True,
        "has_touch": True,
    },
    "galaxy_tab_s8": {
        "name": "Galaxy Tab S8",
        "viewport": {"width": 753, "height": 1205},
        "user_agent": "Mozilla/5.0 (Linux; Android 12; SM-X700) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
        "device_scale_factor": 2,
        "is_mobile": True,
        "has_touch": True,
    },
}

# 显示名 -> 内部 ID 反查映射（支持前端使用显示名或内部 ID）
DEVICE_NAME_MAP = {}
for _id, _preset in DEVICE_PRESETS.items():
    DEVICE_NAME_MAP[_id] = _id
    DEVICE_NAME_MAP[_preset["name"]] = _id
    DEVICE_NAME_MAP[_preset["name"].lower()] = _id

# 前端常用别名 → 后端设备 ID
_ALIASES = {
    "iPhone 14 Pro": "iphone_14",
    "iPhone 14": "iphone_14",
    "iPad Air": "ipad_pro",
    "iPad": "ipad_pro",
    "Galaxy Tab S8": "galaxy_tab_s8",
    "Desktop 1920": None,  # 桌面分辨率无需移动端模拟
}
for _alias, _target in _ALIASES.items():
    if _target:
        DEVICE_NAME_MAP[_alias] = _target
        DEVICE_NAME_MAP[_alias.lower()] = _target


# 移动端检查 JS
MOBILE_CHECK_SCRIPT = """
(deviceName) => {
    const issues = [];
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    
    // 1. 水平溢出检查 — 页面是否可横向滚动
    if (document.documentElement.scrollWidth > vw + 5) {
        issues.push({
            rule_id: 'horizontal-overflow',
            description: `页面存在水平溢出 (页面宽 ${document.documentElement.scrollWidth}px > 视口 ${vw}px)`,
            severity: 'major',
            device: deviceName,
            suggestion: '检查是否有元素设置了固定宽度或 min-width 超出视口'
        });
    }
    
    // 2. 触控目标尺寸检查 (最小 44x44px)
    const interactive = document.querySelectorAll('a, button, input, select, textarea, [role="button"], [onclick]');
    let smallTargets = 0;
    interactive.forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0 && (rect.width < 44 || rect.height < 44)) {
            smallTargets++;
        }
    });
    if (smallTargets > 3) {
        issues.push({
            rule_id: 'touch-target',
            description: `发现 ${smallTargets} 个触控目标小于 44x44px`,
            severity: 'major',
            device: deviceName,
            suggestion: '增大按钮和链接的可点击区域至少 44x44px (WCAG 2.5.5)'
        });
    }
    
    // 3. 文字大小检查 — 小于 12px 的文本
    const textElements = document.querySelectorAll('p, span, a, li, td, th, label, div');
    let smallText = 0;
    const sampleSize = Math.min(textElements.length, 100);
    for (let i = 0; i < sampleSize; i++) {
        const el = textElements[i];
        const computedFont = parseFloat(window.getComputedStyle(el).fontSize);
        if (computedFont < 12 && (el.textContent || '').trim().length > 0) {
            smallText++;
        }
    }
    if (smallText > 5) {
        issues.push({
            rule_id: 'font-size',
            description: `发现 ${smallText} 处文字小于 12px`,
            severity: 'minor',
            device: deviceName,
            suggestion: '移动端文字大小建议不小于 14px，最低 12px'
        });
    }
    
    // 4. Viewport meta 标签检查
    const viewportMeta = document.querySelector('meta[name="viewport"]');
    if (!viewportMeta) {
        issues.push({
            rule_id: 'viewport-meta',
            description: '缺少 viewport meta 标签',
            severity: 'critical',
            device: deviceName,
            suggestion: '添加 <meta name="viewport" content="width=device-width, initial-scale=1">'
        });
    } else {
        const content = viewportMeta.getAttribute('content') || '';
        if (content.includes('user-scalable=no') || content.includes('maximum-scale=1')) {
            issues.push({
                rule_id: 'viewport-zoom',
                description: '禁用了用户缩放 (user-scalable=no)',
                severity: 'major',
                device: deviceName,
                suggestion: '允许用户缩放以提升无障碍性'
            });
        }
    }
    
    // 5. 固定定位元素检查 — 是否遮挡内容
    const fixedElements = document.querySelectorAll('*');
    let fixedCount = 0;
    let fixedHeight = 0;
    fixedElements.forEach(el => {
        const pos = window.getComputedStyle(el).position;
        if (pos === 'fixed' || pos === 'sticky') {
            const rect = el.getBoundingClientRect();
            if (rect.height > 0) {
                fixedCount++;
                fixedHeight += rect.height;
            }
        }
    });
    if (fixedHeight > vh * 0.3) {
        issues.push({
            rule_id: 'fixed-elements',
            description: `固定定位元素占视口高度 ${Math.round(fixedHeight / vh * 100)}%`,
            severity: 'major',
            device: deviceName,
            suggestion: '减少固定定位元素面积，在移动端考虑隐藏非关键固定栏'
        });
    }
    
    // 6. 媒体查询响应式检查
    const hasMediaQueries = Array.from(document.styleSheets).some(sheet => {
        try {
            return Array.from(sheet.cssRules || []).some(rule => rule instanceof CSSMediaRule);
        } catch { return false; }
    });
    if (!hasMediaQueries) {
        issues.push({
            rule_id: 'no-media-queries',
            description: '未检测到 CSS 媒体查询',
            severity: 'minor',
            device: deviceName,
            suggestion: '使用 @media 媒体查询实现响应式布局'
        });
    }
    
    return {
        issues,
        metrics: {
            viewport: { width: vw, height: vh },
            scrollWidth: document.documentElement.scrollWidth,
            interactiveElements: interactive.length,
            smallTouchTargets: smallTargets,
            smallTextElements: smallText,
            fixedElements: fixedCount,
            fixedHeightPercent: Math.round(fixedHeight / vh * 100)
        }
    };
}
"""


@dataclass
class DeviceTestResult:
    device: str
    viewport: str
    issues: List[Dict] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    screenshot_base64: str = ""  # 可选截图

    def to_dict(self):
        return asdict(self)


@dataclass
class MobileReport:
    url: str
    devices_tested: int = 0
    total_issues: int = 0
    score: float = 100.0
    results: List[Dict] = field(default_factory=list)
    summary: str = ""

    def to_dict(self):
        return asdict(self)


class MobileEmulationService:
    """移动端模拟测试服务"""

    async def test_devices(
        self, url: str, devices: Optional[List[str]] = None, screenshot: bool = False
    ) -> MobileReport:
        """在多种设备上测试页面"""
        # 使用 sync_playwright 在线程中运行 (避免 Windows asyncio 兼容性问题)
        return await asyncio.to_thread(self._test_devices_sync, url, devices, screenshot)

    def _test_devices_sync(
        self, url: str, devices: Optional[List[str]] = None, screenshot: bool = False
    ) -> MobileReport:
        """同步版本：在多种设备上测试页面"""
        if devices is None:
            devices = ["iphone_14", "pixel_7", "ipad_pro"]

        report = MobileReport(url=url)
        all_issues = []

        try:
            from playwright.sync_api import sync_playwright
            import base64

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)

                for device_id in devices:
                    # 支持显示名和内部 ID 两种查找方式
                    resolved_id = DEVICE_NAME_MAP.get(device_id) or DEVICE_NAME_MAP.get(device_id.lower())
                    preset = DEVICE_PRESETS.get(resolved_id) if resolved_id else None
                    if not preset:
                        logger.warning(f"未知设备: {device_id}，跳过")
                        continue

                    context = browser.new_context(
                        viewport=preset["viewport"],
                        user_agent=preset["user_agent"],
                        device_scale_factor=preset["device_scale_factor"],
                        is_mobile=preset["is_mobile"],
                        has_touch=preset["has_touch"],
                    )
                    page = context.new_page()

                    try:
                        page.goto(url, wait_until="networkidle", timeout=20000)
                        time.sleep(1)

                        # 执行移动端检查
                        result_data = page.evaluate(MOBILE_CHECK_SCRIPT, preset["name"])

                        # 可选截图
                        screenshot_b64 = ""
                        if screenshot:
                            buf = page.screenshot(full_page=False)
                            screenshot_b64 = base64.b64encode(buf).decode("utf-8")

                        device_result = DeviceTestResult(
                            device=preset["name"],
                            viewport=f'{preset["viewport"]["width"]}x{preset["viewport"]["height"]}',
                            issues=result_data.get("issues", []),
                            metrics=result_data.get("metrics", {}),
                            screenshot_base64=screenshot_b64,
                        )
                        report.results.append(device_result.to_dict())
                        all_issues.extend(result_data.get("issues", []))
                        report.devices_tested += 1

                    except Exception as e:
                        logger.warning(f"设备 {preset['name']} 测试失败: {repr(e)}")
                        report.results.append(
                            {
                                "device": preset["name"],
                                "viewport": f'{preset["viewport"]["width"]}x{preset["viewport"]["height"]}',
                                "issues": [
                                    {
                                        "rule_id": "device-error",
                                        "description": f"测试失败: {repr(e)}",
                                        "severity": "major",
                                        "device": preset["name"],
                                    }
                                ],
                                "metrics": {},
                            }
                        )
                        all_issues.append(
                            {"severity": "major", "description": str(e)}
                        )
                    finally:
                        context.close()

                browser.close()

        except ImportError as e:
            logger.error(f"Playwright 未安装: {repr(e)}")
            report.summary = "Playwright 未安装，请运行 pip install playwright && playwright install chromium"
            report.score = -1
            return report
        except Exception as e:
            import traceback
            err_msg = repr(e) or str(type(e).__name__)
            logger.error(f"移动端测试失败: {err_msg}\n{traceback.format_exc()}")
            report.summary = f"移动端测试失败: {err_msg}"
            report.score = -1
            return report

        report.total_issues = len(all_issues)
        critical = sum(1 for i in all_issues if i.get("severity") == "critical")
        major = sum(1 for i in all_issues if i.get("severity") == "major")
        minor = sum(1 for i in all_issues if i.get("severity") == "minor")
        deduction = critical * 20 + major * 10 + minor * 3
        report.score = max(0, min(100, 100 - deduction))
        report.summary = (
            f"测试 {report.devices_tested} 个设备: "
            f"{report.total_issues} 个问题, 评分 {report.score}/100"
        )
        return report

    def list_devices(self) -> List[Dict[str, Any]]:
        """列出所有预定义设备"""
        return [
            {
                "id": k,
                "name": v["name"],
                "viewport": f'{v["viewport"]["width"]}x{v["viewport"]["height"]}',
                "type": "tablet" if v["viewport"]["width"] > 600 else "phone",
            }
            for k, v in DEVICE_PRESETS.items()
        ]


def create_mobile_service():
    return MobileEmulationService()
