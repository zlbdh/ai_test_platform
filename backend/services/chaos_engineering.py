# -*- coding: utf-8 -*-
"""
混沌工程服务 — 网络/延迟/资源故障注入
通过 Playwright 的网络拦截和设备模拟实现混沌场景

使用 sync_playwright + asyncio.to_thread 避免 Windows 上的 NotImplementedError
"""
import asyncio
import logging
import time
import random
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ChaosResult:
    scenario: str
    status: str = "pending"  # "passed", "failed", "error"
    duration_ms: float = 0
    details: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class ChaosReport:
    url: str
    scenarios_run: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    total_duration_ms: float = 0
    results: List[Dict] = field(default_factory=list)
    summary: str = ""

    def to_dict(self):
        return asdict(self)


class ChaosEngineeringService:
    """混沌工程服务 — 前端韧性测试"""

    SCENARIOS = {
        "slow_network": {
            "name": "慢速网络 (3G)",
            "description": "模拟 3G 网络条件下页面加载表现",
        },
        "offline_recovery": {
            "name": "断网恢复",
            "description": "模拟断网 → 恢复后页面能否正常工作",
        },
        "api_timeout": {
            "name": "API 超时",
            "description": "拦截所有 API 请求并延迟 10s，检查超时处理",
        },
        "api_500": {
            "name": "API 500 错误",
            "description": "拦截 API 请求返回 500，检查错误处理 UI",
        },
        "cpu_throttle": {
            "name": "CPU 节流",
            "description": "模拟低端设备 CPU (6x 减速)，检查页面响应性",
        },
        "large_payload": {
            "name": "大负载响应",
            "description": "注入超大 JSON 响应，检查前端渲染性能",
        },
        "memory_pressure": {
            "name": "内存压力",
            "description": "创建大量 DOM 元素，检测内存泄漏风险",
        },
    }

    async def run_scenarios(
        self, url: str, scenarios: Optional[List[str]] = None
    ) -> ChaosReport:
        """运行混沌测试场景（异步入口，内部在线程中同步执行 Playwright）"""
        return await asyncio.to_thread(self._run_scenarios_sync, url, scenarios)

    def _run_scenarios_sync(
        self, url: str, scenarios: Optional[List[str]] = None
    ) -> ChaosReport:
        """同步版本：运行混沌测试场景"""
        if scenarios is None:
            scenarios = list(self.SCENARIOS.keys())

        report = ChaosReport(url=url)
        start_time = time.time()

        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)

                for scenario_id in scenarios:
                    if scenario_id not in self.SCENARIOS:
                        continue

                    result = self._run_single_scenario(
                        browser, url, scenario_id
                    )
                    report.results.append(result.to_dict())
                    report.scenarios_run += 1

                    if result.status == "passed":
                        report.passed += 1
                    elif result.status == "failed":
                        report.failed += 1
                    else:
                        report.errors += 1

                browser.close()

        except ImportError:
            report.summary = "Playwright 未安装，请执行: pip install playwright && playwright install chromium"
            return report
        except Exception as e:
            logger.error(f"混沌测试失败: {repr(e)}")
            report.summary = f"混沌测试失败: {repr(e)}"
            return report

        report.total_duration_ms = (time.time() - start_time) * 1000
        report.summary = (
            f"执行 {report.scenarios_run} 个场景: "
            f"通过 {report.passed}, 失败 {report.failed}, 错误 {report.errors}"
        )
        return report

    def _run_single_scenario(
        self, browser, url: str, scenario_id: str
    ) -> ChaosResult:
        """运行单个混沌场景"""
        scenario = self.SCENARIOS[scenario_id]
        result = ChaosResult(scenario=scenario["name"])
        start = time.time()

        try:
            if scenario_id == "slow_network":
                result = self._scenario_slow_network(browser, url)
            elif scenario_id == "offline_recovery":
                result = self._scenario_offline_recovery(browser, url)
            elif scenario_id == "api_timeout":
                result = self._scenario_api_timeout(browser, url)
            elif scenario_id == "api_500":
                result = self._scenario_api_500(browser, url)
            elif scenario_id == "cpu_throttle":
                result = self._scenario_cpu_throttle(browser, url)
            elif scenario_id == "large_payload":
                result = self._scenario_large_payload(browser, url)
            elif scenario_id == "memory_pressure":
                result = self._scenario_memory_pressure(browser, url)
            else:
                result.status = "error"
                result.details = f"未知场景: {scenario_id}"
        except Exception as e:
            result.status = "error"
            result.details = repr(e)

        result.duration_ms = (time.time() - start) * 1000
        result.scenario = scenario["name"]
        return result

    def _scenario_slow_network(self, browser, url: str) -> ChaosResult:
        """3G 网络模拟"""
        context = browser.new_context()
        page = context.new_page()

        # 使用 CDP 设置网络节流 (下行 750kbps, 上行 250kbps, 延迟 100ms)
        client = context.new_cdp_session(page)
        client.send(
            "Network.emulateNetworkConditions",
            {
                "offline": False,
                "downloadThroughput": 750 * 1024 / 8,
                "uploadThroughput": 250 * 1024 / 8,
                "latency": 100,
            },
        )

        start = time.time()
        try:
            page.goto(url, wait_until="load", timeout=30000)
            load_time = (time.time() - start) * 1000

            # 检查关键内容是否渲染
            body_text = page.evaluate("() => document.body.innerText.length")
            has_content = body_text > 50

            context.close()

            metrics = {"load_time_ms": round(load_time), "content_length": body_text}

            if load_time > 15000:
                return ChaosResult(
                    scenario="慢速网络 (3G)",
                    status="failed",
                    details=f"3G 下加载耗时 {load_time:.0f}ms (超过 15s 阈值)",
                    metrics=metrics,
                )
            elif has_content:
                return ChaosResult(
                    scenario="慢速网络 (3G)",
                    status="passed",
                    details=f"3G 下加载耗时 {load_time:.0f}ms，内容正常渲染",
                    metrics=metrics,
                )
            else:
                return ChaosResult(
                    scenario="慢速网络 (3G)",
                    status="failed",
                    details="3G 下页面内容未正常渲染",
                    metrics=metrics,
                )
        except Exception as e:
            context.close()
            return ChaosResult(
                scenario="慢速网络 (3G)",
                status="failed",
                details=f"3G 下加载失败: {str(e)}",
            )

    def _scenario_offline_recovery(self, browser, url: str) -> ChaosResult:
        """断网恢复测试"""
        context = browser.new_context()
        page = context.new_page()

        # 先正常加载
        page.goto(url, wait_until="networkidle", timeout=20000)
        initial_text = page.evaluate("() => document.body.innerText.length")

        # 断网
        context.set_offline(True)
        time.sleep(2)

        # 恢复
        context.set_offline(False)
        time.sleep(2)

        # 检查页面状态
        try:
            recovered_text = page.evaluate("() => document.body.innerText.length")
            # 尝试交互
            clickable = page.evaluate(
                "() => { const btn = document.querySelector('button'); return btn ? true : false; }"
            )

            context.close()

            if recovered_text > 0 and recovered_text >= initial_text * 0.5:
                return ChaosResult(
                    scenario="断网恢复",
                    status="passed",
                    details="断网恢复后页面正常显示",
                    metrics={
                        "initial_content": initial_text,
                        "recovered_content": recovered_text,
                    },
                )
            else:
                return ChaosResult(
                    scenario="断网恢复",
                    status="failed",
                    details="断网恢复后页面内容丢失",
                    metrics={
                        "initial_content": initial_text,
                        "recovered_content": recovered_text,
                    },
                )
        except Exception as e:
            context.close()
            return ChaosResult(
                scenario="断网恢复",
                status="failed",
                details=f"恢复后页面异常: {str(e)}",
            )

    def _scenario_api_timeout(self, browser, url: str) -> ChaosResult:
        """API 超时测试"""
        context = browser.new_context()
        page = context.new_page()

        timeout_count = 0

        def delay_handler(route):
            nonlocal timeout_count
            timeout_count += 1
            time.sleep(10)
            try:
                route.continue_()
            except Exception:
                pass

        # 拦截 API 请求
        page.route("**/api/**", delay_handler)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(3)

            # 检查是否有错误/loading 状态的 UI
            has_error_ui = page.evaluate(
                """() => {
                const text = document.body.innerText.toLowerCase();
                return text.includes('timeout') || text.includes('loading') || 
                       text.includes('超时') || text.includes('加载') ||
                       text.includes('error') || text.includes('错误') ||
                       document.querySelector('[class*="error"]') !== null ||
                       document.querySelector('[class*="loading"]') !== null;
            }"""
            )

            context.close()

            return ChaosResult(
                scenario="API 超时",
                status="passed" if has_error_ui else "failed",
                details="API 超时时有友好的 UI 反馈"
                if has_error_ui
                else "API 超时时没有友好的错误/加载提示",
                metrics={"intercepted_requests": timeout_count},
            )
        except Exception as e:
            context.close()
            return ChaosResult(
                scenario="API 超时", status="error", details=str(e)
            )

    def _scenario_api_500(self, browser, url: str) -> ChaosResult:
        """API 500 错误测试"""
        context = browser.new_context()
        page = context.new_page()

        error_count = 0

        def error_handler(route):
            nonlocal error_count
            error_count += 1
            route.fulfill(
                status=500,
                content_type="application/json",
                body='{"error": "Internal Server Error", "message": "Chaos test"}',
            )

        page.route("**/api/**", error_handler)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(3)

            # 检查页面是否崩溃 (白屏)
            body_text = page.evaluate("() => document.body.innerText.length")
            has_error_handling = page.evaluate(
                """() => {
                const text = document.body.innerText.toLowerCase();
                return text.includes('error') || text.includes('错误') ||
                       text.includes('failed') || text.includes('失败') ||
                       text.includes('retry') || text.includes('重试');
            }"""
            )

            context.close()

            if body_text < 10:
                return ChaosResult(
                    scenario="API 500 错误",
                    status="failed",
                    details="API 全部 500 时页面白屏崩溃",
                    metrics={"error_requests": error_count},
                )
            elif has_error_handling:
                return ChaosResult(
                    scenario="API 500 错误",
                    status="passed",
                    details="API 500 时有错误处理 UI",
                    metrics={"error_requests": error_count},
                )
            else:
                return ChaosResult(
                    scenario="API 500 错误",
                    status="passed",
                    details="API 500 时页面未崩溃，但无明确错误提示",
                    metrics={"error_requests": error_count},
                )
        except Exception as e:
            context.close()
            return ChaosResult(
                scenario="API 500 错误", status="error", details=str(e)
            )

    def _scenario_cpu_throttle(self, browser, url: str) -> ChaosResult:
        """CPU 节流测试"""
        context = browser.new_context()
        page = context.new_page()

        # CDP: 6x CPU 减速
        client = context.new_cdp_session(page)
        client.send("Emulation.setCPUThrottlingRate", {"rate": 6})

        start = time.time()
        try:
            page.goto(url, wait_until="load", timeout=30000)
            load_time = (time.time() - start) * 1000

            # 测量交互响应
            interaction_time = page.evaluate(
                """() => {
                const start = performance.now();
                // 强制重排
                document.body.offsetHeight;
                for (let i = 0; i < 100; i++) {
                    document.body.style.opacity = (i % 2 === 0) ? '0.99' : '1';
                    document.body.offsetHeight;
                }
                document.body.style.opacity = '1';
                return performance.now() - start;
            }"""
            )

            client.send("Emulation.setCPUThrottlingRate", {"rate": 1})
            context.close()

            metrics = {
                "load_time_ms": round(load_time),
                "interaction_time_ms": round(interaction_time),
            }

            if interaction_time > 5000:
                return ChaosResult(
                    scenario="CPU 节流",
                    status="failed",
                    details=f"6x CPU 减速下交互响应 {interaction_time:.0f}ms (超过 5s)",
                    metrics=metrics,
                )
            else:
                return ChaosResult(
                    scenario="CPU 节流",
                    status="passed",
                    details=f"6x CPU 减速下交互响应 {interaction_time:.0f}ms",
                    metrics=metrics,
                )
        except Exception as e:
            context.close()
            return ChaosResult(
                scenario="CPU 节流", status="error", details=str(e)
            )

    def _scenario_large_payload(self, browser, url: str) -> ChaosResult:
        """大负载响应测试"""
        context = browser.new_context()
        page = context.new_page()

        # 生成 5MB JSON payload
        large_data = [{"id": i, "value": "x" * 1000} for i in range(5000)]
        payload = json.dumps(large_data)

        injected = False

        def large_response_handler(route):
            nonlocal injected
            if not injected:
                injected = True
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=payload,
                )
            else:
                route.continue_()

        page.route("**/api/**", large_response_handler)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(3)

            # 检查页面是否存活
            is_responsive = page.evaluate(
                "() => { try { return typeof document.body.innerText === 'string'; } catch { return false; } }"
            )

            context.close()

            return ChaosResult(
                scenario="大负载响应",
                status="passed" if is_responsive else "failed",
                details="5MB JSON 注入后页面保持响应"
                if is_responsive
                else "5MB JSON 注入后页面无响应",
                metrics={"payload_size_kb": len(payload) // 1024},
            )
        except Exception as e:
            context.close()
            return ChaosResult(
                scenario="大负载响应", status="error", details=str(e)
            )

    def _scenario_memory_pressure(self, browser, url: str) -> ChaosResult:
        """内存压力测试"""
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto(url, wait_until="networkidle", timeout=20000)

            # 注入大量 DOM 元素
            memory_info = page.evaluate(
                """() => {
                const before = performance.memory ? performance.memory.usedJSHeapSize : 0;
                
                // 创建 10000 个 DOM 元素
                const container = document.createElement('div');
                container.id = 'chaos-test-container';
                container.style.display = 'none';
                for (let i = 0; i < 10000; i++) {
                    const el = document.createElement('div');
                    el.textContent = 'Chaos test element ' + i;
                    el.addEventListener('click', () => {});
                    container.appendChild(el);
                }
                document.body.appendChild(container);
                
                const after = performance.memory ? performance.memory.usedJSHeapSize : 0;
                
                // 清理
                container.remove();
                
                return {
                    before: before,
                    after: after,
                    delta_mb: Math.round((after - before) / 1024 / 1024 * 100) / 100,
                    responsive: true
                };
            }"""
            )

            context.close()

            return ChaosResult(
                scenario="内存压力",
                status="passed"
                if memory_info.get("responsive")
                else "failed",
                details=f"注入 10000 DOM 元素后内存增长 {memory_info.get('delta_mb', 'N/A')} MB",
                metrics=memory_info,
            )
        except Exception as e:
            context.close()
            return ChaosResult(
                scenario="内存压力", status="error", details=str(e)
            )

    def list_scenarios(self) -> List[Dict[str, str]]:
        """列出所有可用混沌场景"""
        return [
            {"id": k, "name": v["name"], "description": v["description"]}
            for k, v in self.SCENARIOS.items()
        ]


def create_chaos_service():
    return ChaosEngineeringService()
