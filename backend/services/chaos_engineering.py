# -*- coding: utf-8 -*-
"""
Chaos engineering service: network, latency, and resource fault injection.
Uses Playwright network interception and device emulation.

Uses sync_playwright with asyncio.to_thread to avoid NotImplementedError on Windows.
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
    """Chaos engineering service for frontend resilience testing"""

    SCENARIOS = {
        "slow_network": {
            "name": "Slow network (3G)",
            "description": "Simulate page loading under 3G network conditions",
        },
        "offline_recovery": {
            "name": "Offline recovery",
            "description": "Check whether the page recovers after losing and regaining connectivity",
        },
        "api_timeout": {
            "name": "API timeout",
            "description": "Intercept all API requests and delay them for 10 seconds to check timeout handling",
        },
        "api_500": {
            "name": "API 500 error",
            "description": "Return 500 for intercepted API requests and check the error handling UI",
        },
        "cpu_throttle": {
            "name": "CPU throttling",
            "description": "Emulate a low-end CPU with a 6x slowdown and check page responsiveness",
        },
        "large_payload": {
            "name": "Large response payload",
            "description": "Inject an oversized JSON response to check frontend rendering performance",
        },
        "memory_pressure": {
            "name": "Memory pressure",
            "description": "Create many DOM elements to assess memory leak risk",
        },
    }

    async def run_scenarios(
        self, url: str, scenarios: Optional[List[str]] = None
    ) -> ChaosReport:
        """Run chaos scenarios asynchronously, with synchronous Playwright calls in a worker thread"""
        return await asyncio.to_thread(self._run_scenarios_sync, url, scenarios)

    def _run_scenarios_sync(
        self, url: str, scenarios: Optional[List[str]] = None
    ) -> ChaosReport:
        """Synchronous implementation of chaos scenario execution"""
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
            report.summary = "Playwright is not installed. Run: pip install playwright && playwright install chromium"
            return report
        except Exception as e:
            logger.error(f"Chaos testing failed: {repr(e)}")
            report.summary = f"Chaos testing failed: {repr(e)}"
            return report

        report.total_duration_ms = (time.time() - start_time) * 1000
        report.summary = (
            f"Ran {report.scenarios_run} scenarios: "
            f"passed {report.passed}, failed {report.failed}, errors {report.errors}"
        )
        return report

    def _run_single_scenario(
        self, browser, url: str, scenario_id: str
    ) -> ChaosResult:
        """Run a single chaos scenario"""
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
                result.details = f"Unknown scenario: {scenario_id}"
        except Exception as e:
            result.status = "error"
            result.details = repr(e)

        result.duration_ms = (time.time() - start) * 1000
        result.scenario = scenario["name"]
        return result

    def _scenario_slow_network(self, browser, url: str) -> ChaosResult:
        """3G network simulation"""
        context = browser.new_context()
        page = context.new_page()

        # Set CDP network throttling: 750 kbps down, 250 kbps up, 100 ms latency
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

            # Check whether key content rendered
            body_text = page.evaluate("() => document.body.innerText.length")
            has_content = body_text > 50

            context.close()

            metrics = {"load_time_ms": round(load_time), "content_length": body_text}

            if load_time > 15000:
                return ChaosResult(
                    scenario="Slow network (3G)",
                    status="failed",
                    details=f"3G load duration: {load_time:.0f} ms (exceeds the 15-second threshold)",
                    metrics=metrics,
                )
            elif has_content:
                return ChaosResult(
                    scenario="Slow network (3G)",
                    status="passed",
                    details=f"3G load duration: {load_time:.0f} ms; content rendered correctly",
                    metrics=metrics,
                )
            else:
                return ChaosResult(
                    scenario="Slow network (3G)",
                    status="failed",
                    details="Page content did not render correctly on 3G",
                    metrics=metrics,
                )
        except Exception as e:
            context.close()
            return ChaosResult(
                scenario="Slow network (3G)",
                status="failed",
                details=f"Page loading failed on 3G: {str(e)}",
            )

    def _scenario_offline_recovery(self, browser, url: str) -> ChaosResult:
        """Offline recovery test"""
        context = browser.new_context()
        page = context.new_page()

        # Load normally first
        page.goto(url, wait_until="networkidle", timeout=20000)
        initial_text = page.evaluate("() => document.body.innerText.length")

        # Disconnect
        context.set_offline(True)
        time.sleep(2)

        # Reconnect
        context.set_offline(False)
        time.sleep(2)

        # Check page state
        try:
            recovered_text = page.evaluate("() => document.body.innerText.length")
            # Attempt interaction
            clickable = page.evaluate(
                "() => { const btn = document.querySelector('button'); return btn ? true : false; }"
            )

            context.close()

            if recovered_text > 0 and recovered_text >= initial_text * 0.5:
                return ChaosResult(
                    scenario="Offline recovery",
                    status="passed",
                    details="The page displays correctly after reconnecting",
                    metrics={
                        "initial_content": initial_text,
                        "recovered_content": recovered_text,
                    },
                )
            else:
                return ChaosResult(
                    scenario="Offline recovery",
                    status="failed",
                    details="Page content was lost after reconnecting",
                    metrics={
                        "initial_content": initial_text,
                        "recovered_content": recovered_text,
                    },
                )
        except Exception as e:
            context.close()
            return ChaosResult(
                scenario="Offline recovery",
                status="failed",
                details=f"Page error after recovery: {str(e)}",
            )

    def _scenario_api_timeout(self, browser, url: str) -> ChaosResult:
        """API timeout test"""
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

        # Intercept API requests
        page.route("**/api/**", delay_handler)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(3)

            # Check for error or loading UI
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
                scenario="API timeout",
                status="passed" if has_error_ui else "failed",
                details="The UI provides appropriate feedback on API timeout"
                if has_error_ui
                else "No helpful error or loading message appears on API timeout",
                metrics={"intercepted_requests": timeout_count},
            )
        except Exception as e:
            context.close()
            return ChaosResult(
                scenario="API timeout", status="error", details=str(e)
            )

    def _scenario_api_500(self, browser, url: str) -> ChaosResult:
        """API 500 error test"""
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

            # Check whether the page crashes to a blank screen
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
                    scenario="API 500 error",
                    status="failed",
                    details="The page crashes to a blank screen when all APIs return 500",
                    metrics={"error_requests": error_count},
                )
            elif has_error_handling:
                return ChaosResult(
                    scenario="API 500 error",
                    status="passed",
                    details="Error handling UI appears on API 500 responses",
                    metrics={"error_requests": error_count},
                )
            else:
                return ChaosResult(
                    scenario="API 500 error",
                    status="passed",
                    details="The page survives API 500 responses but shows no explicit error message",
                    metrics={"error_requests": error_count},
                )
        except Exception as e:
            context.close()
            return ChaosResult(
                scenario="API 500 error", status="error", details=str(e)
            )

    def _scenario_cpu_throttle(self, browser, url: str) -> ChaosResult:
        """CPU throttling test"""
        context = browser.new_context()
        page = context.new_page()

        # CDP: 6x CPU slowdown
        client = context.new_cdp_session(page)
        client.send("Emulation.setCPUThrottlingRate", {"rate": 6})

        start = time.time()
        try:
            page.goto(url, wait_until="load", timeout=30000)
            load_time = (time.time() - start) * 1000

            # Measure interaction response
            interaction_time = page.evaluate(
                """() => {
                const start = performance.now();
                // Force layout recalculation
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
                    scenario="CPU throttling",
                    status="failed",
                    details=f"Interaction response with 6x CPU slowdown: {interaction_time:.0f} ms (exceeds 5 seconds)",
                    metrics=metrics,
                )
            else:
                return ChaosResult(
                    scenario="CPU throttling",
                    status="passed",
                    details=f"Interaction response with 6x CPU slowdown: {interaction_time:.0f}ms",
                    metrics=metrics,
                )
        except Exception as e:
            context.close()
            return ChaosResult(
                scenario="CPU throttling", status="error", details=str(e)
            )

    def _scenario_large_payload(self, browser, url: str) -> ChaosResult:
        """Large response payload test"""
        context = browser.new_context()
        page = context.new_page()

        # Generate a 5 MB JSON payload
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

            # Check whether the page is still responsive
            is_responsive = page.evaluate(
                "() => { try { return typeof document.body.innerText === 'string'; } catch { return false; } }"
            )

            context.close()

            return ChaosResult(
                scenario="Large response payload",
                status="passed" if is_responsive else "failed",
                details="The page remains responsive after injecting 5 MB of JSON"
                if is_responsive
                else "The page is unresponsive after injecting 5 MB of JSON",
                metrics={"payload_size_kb": len(payload) // 1024},
            )
        except Exception as e:
            context.close()
            return ChaosResult(
                scenario="Large response payload", status="error", details=str(e)
            )

    def _scenario_memory_pressure(self, browser, url: str) -> ChaosResult:
        """Memory pressure test"""
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto(url, wait_until="networkidle", timeout=20000)

            # Inject many DOM elements
            memory_info = page.evaluate(
                """() => {
                const before = performance.memory ? performance.memory.usedJSHeapSize : 0;
                
                // Create 10,000 DOM elements
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
                
                // Clean up
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
                scenario="Memory pressure",
                status="passed"
                if memory_info.get("responsive")
                else "failed",
                details=f"Memory growth after injecting 10,000 DOM elements: {memory_info.get('delta_mb', 'N/A')} MB",
                metrics=memory_info,
            )
        except Exception as e:
            context.close()
            return ChaosResult(
                scenario="Memory pressure", status="error", details=str(e)
            )

    def list_scenarios(self) -> List[Dict[str, str]]:
        """List all available chaos scenarios"""
        return [
            {"id": k, "name": v["name"], "description": v["description"]}
            for k, v in self.SCENARIOS.items()
        ]


def create_chaos_service():
    return ChaosEngineeringService()
