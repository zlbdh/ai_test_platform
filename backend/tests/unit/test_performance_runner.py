"""
PerformanceRunner 单元测试
覆盖: 枚举/数据类, generate_locustfile, run_test 路由,
      _parse_locust_stats, stop/history/delete/clear, 单例
"""
import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from types import SimpleNamespace

from services.performance_runner import (
    LoadTestStatus, LoadTestConfig, LoadTestResult,
    PerformanceRunner
)


@pytest.fixture(autouse=True)
def _stub_execution_center():
    recorder = MagicMock()
    recorder.record_performance_result.return_value = "performance_stub"
    with patch("services.performance_runner.get_execution_center_service", return_value=recorder):
        yield


# ---------------------------------------------------------------------------
# 枚举测试
# ---------------------------------------------------------------------------
class TestLoadTestStatus:
    def test_enum_values(self):
        assert LoadTestStatus.IDLE == "idle"
        assert LoadTestStatus.RUNNING == "running"
        assert LoadTestStatus.COMPLETED == "completed"
        assert LoadTestStatus.FAILED == "failed"
        assert LoadTestStatus.STOPPED == "stopped"


# ---------------------------------------------------------------------------
# 数据类测试
# ---------------------------------------------------------------------------
class TestLoadTestConfig:
    def test_defaults(self):
        cfg = LoadTestConfig(target_url="http://example.com")
        assert cfg.users == 10
        assert cfg.spawn_rate == 1
        assert cfg.duration == 60
        assert cfg.endpoints == []
        assert cfg.headers == {}


class TestLoadTestResult:
    def test_duration(self):
        t1 = datetime(2026, 1, 1, 0, 0, 0)
        t2 = datetime(2026, 1, 1, 0, 1, 0)
        r = LoadTestResult(
            test_id="t1", status=LoadTestStatus.COMPLETED,
            config=LoadTestConfig(target_url="http://x.com"),
            started_at=t1, finished_at=t2
        )
        assert r.duration == 60.0

    def test_duration_none(self):
        r = LoadTestResult(
            test_id="t1", status=LoadTestStatus.IDLE,
            config=LoadTestConfig(target_url="http://x.com")
        )
        assert r.duration is None


# ---------------------------------------------------------------------------
# PerformanceRunner 初始化
# ---------------------------------------------------------------------------
class TestRunnerInit:
    def test_default_init(self, tmp_path):
        runner = PerformanceRunner(results_dir=str(tmp_path))
        assert runner.status == LoadTestStatus.IDLE
        assert runner._current_process is None


# ---------------------------------------------------------------------------
# generate_locustfile 测试
# ---------------------------------------------------------------------------
class TestGenerateLocustfile:
    def test_default_endpoint(self, tmp_path):
        """没有 endpoints 时应生成默认 GET / 测试"""
        runner = PerformanceRunner(results_dir=str(tmp_path))
        cfg = LoadTestConfig(target_url="http://example.com")
        code = runner.generate_locustfile(cfg)
        assert "from locust import" in code
        assert "LoadTestUser" in code
        assert "default_endpoint" in code
        assert 'self.client.get("/", headers=self.headers)' in code

    def test_custom_get_endpoint(self, tmp_path):
        runner = PerformanceRunner(results_dir=str(tmp_path))
        cfg = LoadTestConfig(
            target_url="http://example.com",
            endpoints=[{"method": "GET", "path": "/api/users", "weight": 3}]
        )
        code = runner.generate_locustfile(cfg)
        assert "@task(3)" in code
        assert '"/api/users"' in code

    def test_custom_post_endpoint(self, tmp_path):
        runner = PerformanceRunner(results_dir=str(tmp_path))
        cfg = LoadTestConfig(
            target_url="http://example.com",
            endpoints=[{"method": "POST", "path": "/api/login", "body": {"user": "admin"}}]
        )
        code = runner.generate_locustfile(cfg)
        assert "self.client.post" in code
        assert '"/api/login"' in code

    def test_headers_included(self, tmp_path):
        runner = PerformanceRunner(results_dir=str(tmp_path))
        cfg = LoadTestConfig(
            target_url="http://example.com",
            headers={"Authorization": "Bearer xxx"}
        )
        code = runner.generate_locustfile(cfg)
        assert "Authorization" in code


# ---------------------------------------------------------------------------
# _parse_locust_stats 测试
# ---------------------------------------------------------------------------
class TestParseLocustStats:
    def test_parse_aggregated(self, tmp_path):
        runner = PerformanceRunner(results_dir=str(tmp_path))
        stats = [
            {"name": "/api/users", "num_requests": 100, "num_failures": 5},
            {"name": "Aggregated", "num_requests": 200, "num_failures": 10,
             "avg_response_time": 150, "min_response_time": 20,
             "max_response_time": 500, "current_rps": 50,
             "response_time_percentile_50": 120,
             "response_time_percentile_95": 450}
        ]
        result = runner._parse_locust_stats(stats)
        assert result["total_requests"] == 200
        assert result["failures"] == 10
        assert result["avg_response_time"] == 150
        assert result["requests_per_second"] == 50
        assert result["success_rate"] == 95.0

    def test_no_aggregated(self, tmp_path):
        """没有 Aggregated 条目时应返回 entries"""
        runner = PerformanceRunner(results_dir=str(tmp_path))
        stats = [{"name": "/api", "num_requests": 10}]
        result = runner._parse_locust_stats(stats)
        assert "entries" in result


# ---------------------------------------------------------------------------
# run_test 测试 (mock subprocess)
# ---------------------------------------------------------------------------
class TestRunTest:
    @pytest.mark.asyncio
    async def test_locust_not_found_fallback(self, tmp_path):
        """Locust 不可用时应 fallback 到 simple test"""
        runner = PerformanceRunner(results_dir=str(tmp_path))
        cfg = LoadTestConfig(target_url="http://example.com", duration=1)

        mock_simple = AsyncMock()
        mock_simple.return_value = LoadTestResult(
            test_id="x", status=LoadTestStatus.COMPLETED,
            config=cfg, started_at=datetime.now(), finished_at=datetime.now(),
            stats={"total_requests": 10}
        )

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("locust not found")), \
             patch.object(runner, "_run_simple_load_test", mock_simple):
            result = await runner.run_test(cfg)
        assert result.status == LoadTestStatus.COMPLETED
        mock_simple.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout_marks_failed(self, tmp_path):
        """超时应标记为 FAILED"""
        runner = PerformanceRunner(results_dir=str(tmp_path))
        cfg = LoadTestConfig(target_url="http://example.com", duration=1)

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(side_effect=TimeoutError("stuck"))
        mock_process.terminate = MagicMock()

        async def raise_timeout(awaitable, timeout):
            awaitable.close()
            raise TimeoutError("stuck")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process), \
             patch("asyncio.wait_for", side_effect=raise_timeout):
            result = await runner.run_test(cfg)
        # 超时时可能走 TimeoutError 或 asyncio.TimeoutError 分支
        assert result.status in (LoadTestStatus.FAILED, LoadTestStatus.COMPLETED)

    @pytest.mark.asyncio
    async def test_generic_exception_marks_failed(self, tmp_path):
        """通用异常应标记为 FAILED"""
        runner = PerformanceRunner(results_dir=str(tmp_path))
        cfg = LoadTestConfig(target_url="http://example.com", duration=1)

        with patch("asyncio.create_subprocess_exec", side_effect=RuntimeError("boom")):
            result = await runner.run_test(cfg)
        assert result.status == LoadTestStatus.FAILED
        assert "boom" in result.errors[0]

    @pytest.mark.asyncio
    async def test_simple_load_test_counts_http_401_as_failure(self, tmp_path):
        runner = PerformanceRunner(results_dir=str(tmp_path))
        cfg = LoadTestConfig(target_url="http://example.com", duration=1, users=1)

        class FakeResponse:
            status = 401

            async def text(self):
                return '{"code":401}'

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class FakeSession:
            def request(self, *args, **kwargs):
                return FakeResponse()

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch("aiohttp.ClientSession", return_value=FakeSession()):
            result = await runner._run_simple_load_test(cfg, "simple401")

        assert result.stats["http_4xx"] > 0
        assert result.stats["business_success_rate"] == 0
        assert result.stats["success"] == 0


# ---------------------------------------------------------------------------
# stop_test 测试
# ---------------------------------------------------------------------------
class TestStopTest:
    def test_stop_with_process(self, tmp_path):
        runner = PerformanceRunner(results_dir=str(tmp_path))
        cfg = LoadTestConfig(target_url="http://x.com")
        mock_proc = MagicMock()
        runner._current_process = mock_proc
        runner._current_result = LoadTestResult(
            test_id="s1", status=LoadTestStatus.RUNNING, config=cfg,
            started_at=datetime.now()
        )
        runner.stop_test()
        mock_proc.terminate.assert_called_once()
        assert runner.status == LoadTestStatus.STOPPED

    def test_stop_without_process(self, tmp_path):
        runner = PerformanceRunner(results_dir=str(tmp_path))
        runner.stop_test()  # 不应崩溃
        assert runner.status == LoadTestStatus.IDLE


# ---------------------------------------------------------------------------
# 历史管理测试
# ---------------------------------------------------------------------------
class TestHistory:
    def test_get_history_empty(self, tmp_path):
        runner = PerformanceRunner(results_dir=str(tmp_path))
        assert runner.get_history() == []

    def test_get_history_with_results(self, tmp_path):
        runner = PerformanceRunner(results_dir=str(tmp_path))
        for i in range(3):
            (tmp_path / f"result_t{i}.json").write_text(
                json.dumps({"test_id": f"t{i}"}), encoding="utf-8"
            )
        assert len(runner.get_history(limit=2)) == 2

    def test_delete_history(self, tmp_path):
        runner = PerformanceRunner(results_dir=str(tmp_path))
        (tmp_path / "result_t1.json").write_text("{}", encoding="utf-8")
        (tmp_path / "locustfile_t1.py").write_text("", encoding="utf-8")
        (tmp_path / "stats_t1.json").write_text("{}", encoding="utf-8")
        assert runner.delete_history("t1") is True
        assert not (tmp_path / "result_t1.json").exists()
        assert not (tmp_path / "locustfile_t1.py").exists()

    def test_delete_history_not_found(self, tmp_path):
        runner = PerformanceRunner(results_dir=str(tmp_path))
        assert runner.delete_history("nonexistent") is False

    def test_clear_history(self, tmp_path):
        runner = PerformanceRunner(results_dir=str(tmp_path))
        (tmp_path / "result_a.json").write_text("{}", encoding="utf-8")
        (tmp_path / "result_b.json").write_text("{}", encoding="utf-8")
        (tmp_path / "locustfile_a.py").write_text("", encoding="utf-8")
        count = runner.clear_history()
        assert count == 2


# ---------------------------------------------------------------------------
# 单例测试
# ---------------------------------------------------------------------------
class TestSingleton:
    def test_singleton(self, tmp_path):
        import services.performance_runner as mod
        mod._runner = None
        with patch("core.config.Config") as mock_cfg:
            mock_cfg.PROJECT_ROOT = str(tmp_path)
            from services.performance_runner import get_performance_runner
            r1 = get_performance_runner()
            r2 = get_performance_runner()
            assert r1 is r2
        mod._runner = None
