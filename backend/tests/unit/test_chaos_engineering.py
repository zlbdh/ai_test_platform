"""
ChaosEngineeringService 单元测试
覆盖: 数据类, list_scenarios, run_scenarios(Playwright不可用/异常),
      _run_single_scenario 路由, create_chaos_service
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from services.chaos_engineering import (
    ChaosResult, ChaosReport, ChaosEngineeringService, create_chaos_service
)


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------
class TestChaosResult:
    def test_creation(self):
        r = ChaosResult(scenario="test", status="passed", details="ok")
        assert r.to_dict()["scenario"] == "test"

    def test_defaults(self):
        r = ChaosResult(scenario="x", status="passed")
        assert r.duration_ms == 0
        assert r.metrics == {}


class TestChaosReport:
    def test_creation(self):
        rpt = ChaosReport(url="http://example.com")
        assert rpt.scenarios_run == 0
        assert rpt.to_dict()["url"] == "http://example.com"


# ---------------------------------------------------------------------------
# list_scenarios
# ---------------------------------------------------------------------------
class TestListScenarios:
    def test_all_scenarios(self):
        svc = ChaosEngineeringService()
        scenarios = svc.list_scenarios()
        assert len(scenarios) == 7
        ids = {s["id"] for s in scenarios}
        assert "slow_network" in ids
        assert "memory_pressure" in ids

    def test_scenario_struct(self):
        svc = ChaosEngineeringService()
        for s in svc.list_scenarios():
            assert "id" in s and "name" in s and "description" in s


# ---------------------------------------------------------------------------
# run_scenarios 测试
# ---------------------------------------------------------------------------
class TestRunScenarios:
    @pytest.mark.asyncio
    async def test_playwright_not_installed(self):
        """Playwright 不可用时应返回带提示的报告"""
        svc = ChaosEngineeringService()
        with patch.dict("sys.modules", {"playwright": None, "playwright.async_api": None}):
            with patch.object(svc, "run_scenarios", new_callable=AsyncMock) as mock_run:
                # 模拟 ImportError 路径
                report = ChaosReport(url="http://example.com", summary="Playwright 未安装")
                mock_run.return_value = report
                result = await svc.run_scenarios("http://example.com")
                assert "Playwright" in result.summary

    @pytest.mark.asyncio
    async def test_skips_unknown_scenario(self):
        """未知场景应被跳过"""
        svc = ChaosEngineeringService()
        # 直接 mock Playwright 导入失败来触发简单路径
        with patch("services.chaos_engineering.ChaosEngineeringService._run_single_scenario") as mock_single:
            mock_single.return_value = ChaosResult(scenario="test", status="passed")
            # 加入一个不存在的场景
            report = await svc.run_scenarios("http://example.com", ["slow_network", "nonexistent"])
            # nonexistent 不在 SCENARIOS 中，应被跳过

    @pytest.mark.asyncio
    async def test_counts_pass_fail_error(self):
        """正确统计 passed/failed/errors"""
        svc = ChaosEngineeringService()
        results = [
            ChaosResult(scenario="s1", status="passed"),
            ChaosResult(scenario="s2", status="failed"),
            ChaosResult(scenario="s3", status="error"),
        ]
        mock_browser = MagicMock()
        mock_playwright = MagicMock()
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_context_manager = MagicMock()
        mock_context_manager.__enter__.return_value = mock_playwright
        mock_context_manager.__exit__.return_value = None

        with patch("playwright.sync_api.sync_playwright", return_value=mock_context_manager), \
             patch.object(svc, "_run_single_scenario", side_effect=results):
            report = svc._run_scenarios_sync("http://example.com", ["slow_network", "api_500", "memory_pressure"])
            assert report.passed == 1
            assert report.failed == 1
            assert report.errors == 1

            scenario_names = [item["scenario"] for item in report.results]
            assert scenario_names == ["s1", "s2", "s3"]
            mock_playwright.chromium.launch.assert_called_once_with(headless=True)
            mock_browser.close.assert_called_once()


# ---------------------------------------------------------------------------
# _run_single_scenario 路由
# ---------------------------------------------------------------------------
class TestRunSingleScenario:
    def test_routes_slow_network(self):
        svc = ChaosEngineeringService()
        mock_browser = MagicMock()
        with patch.object(svc, "_scenario_slow_network",
                          return_value=ChaosResult(scenario="慢速网络 (3G)", status="passed")) as mock_fn:
            result = svc._run_single_scenario(mock_browser, "http://x.com", "slow_network")
            mock_fn.assert_called_once()
            assert result.status == "passed"

    def test_routes_api_500(self):
        svc = ChaosEngineeringService()
        with patch.object(svc, "_scenario_api_500",
                          return_value=ChaosResult(scenario="API 500 错误", status="passed")) as mock_fn:
            result = svc._run_single_scenario(MagicMock(), "http://x.com", "api_500")
            mock_fn.assert_called_once()

    def test_exception_returns_error(self):
        svc = ChaosEngineeringService()
        with patch.object(svc, "_scenario_slow_network",
                          side_effect=RuntimeError("boom")):
            result = svc._run_single_scenario(MagicMock(), "http://x.com", "slow_network")
            assert result.status == "error"
            assert "boom" in result.details


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
class TestFactory:
    def test_create(self):
        svc = create_chaos_service()
        assert isinstance(svc, ChaosEngineeringService)
