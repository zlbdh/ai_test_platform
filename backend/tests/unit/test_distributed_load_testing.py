"""
DistributedLoadTester 单元测试
覆盖: 枚举, 数据类, generate_locustfile, stop_test, add_worker,
      get_status, start_test(locust不可用回退), 单例
"""
import pytest
from unittest.mock import patch, MagicMock

from services.distributed_load_testing import (
    LoadTestStatus, LoadTestConfig, LoadTestMetrics, WorkerNode,
    DistributedLoadTester, get_load_tester
)


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------
class TestLoadTestStatus:
    def test_values(self):
        assert LoadTestStatus.IDLE.value == "idle"
        assert LoadTestStatus.COMPLETED.value == "completed"


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------
class TestLoadTestConfig:
    def test_creation(self):
        c = LoadTestConfig(target_url="http://x.com", users=10, spawn_rate=2.0,
                          duration_seconds=60)
        assert c.locustfile is None


class TestLoadTestMetrics:
    def test_creation(self):
        m = LoadTestMetrics(total_requests=100, failures=5, avg_response_time=50.0,
                           min_response_time=10.0, max_response_time=200.0, rps=10.0,
                           percentile_50=45.0, percentile_95=150.0, percentile_99=190.0)
        assert m.rps == 10.0


class TestWorkerNode:
    def test_creation(self):
        w = WorkerNode(node_id="w-1", host="192.168.1.10", port=5557, status="ready")
        assert w.node_id == "w-1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def tester():
    with patch("shutil.which", return_value=None):
        t = DistributedLoadTester()
    return t


@pytest.fixture
def tester_with_locust():
    with patch("shutil.which", return_value="/usr/bin/locust"):
        t = DistributedLoadTester()
    return t


# ---------------------------------------------------------------------------
# generate_locustfile
# ---------------------------------------------------------------------------
class TestGenerateLocustfile:
    def test_generates_file(self, tester, tmp_path):
        config = LoadTestConfig(target_url="http://example.com", users=5,
                               spawn_rate=1.0, duration_seconds=10)
        with patch("services.distributed_load_testing.os.makedirs"):
            with patch("builtins.open", MagicMock()):
                path = tester.generate_locustfile(config)
        assert path.startswith("./data/locustfile_")
        assert path.endswith(".py")


# ---------------------------------------------------------------------------
# stop_test
# ---------------------------------------------------------------------------
class TestStopTest:
    def test_stop_no_process(self, tester):
        tester.stop_test()
        assert tester.status == LoadTestStatus.STOPPED

    def test_stop_with_process(self, tester):
        tester._process = MagicMock()
        tester.stop_test()
        tester._process.terminate.assert_called_once()
        assert tester.status == LoadTestStatus.STOPPED


# ---------------------------------------------------------------------------
# add_worker
# ---------------------------------------------------------------------------
class TestAddWorker:
    def test_add(self, tester):
        w = tester.add_worker("192.168.1.10")
        assert w.node_id == "worker-1"
        assert w.host == "192.168.1.10"
        assert len(tester.workers) == 1

    def test_add_multiple(self, tester):
        tester.add_worker("h1")
        tester.add_worker("h2")
        assert len(tester.workers) == 2
        assert tester.workers[1].node_id == "worker-2"


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------
class TestGetStatus:
    def test_idle_no_config(self, tester):
        status = tester.get_status()
        assert status["status"] == "idle"
        assert status["config"] is None

    def test_with_config(self, tester):
        tester.current_config = LoadTestConfig("http://x.com", 5, 1.0, 30)
        status = tester.get_status()
        assert status["config"]["users"] == 5


# ---------------------------------------------------------------------------
# start_test (locust 不可用 → 回退到简单压测)
# ---------------------------------------------------------------------------
class TestStartTest:
    @pytest.mark.asyncio
    async def test_no_locust_fallback(self, tester):
        """Locust 不可用时应使用简单压测"""
        config = LoadTestConfig("http://example.com", 1, 1.0, 1)
        with patch.object(tester, "_run_simple_load_test", return_value={"status": "completed"}) as mock:
            result = await tester.start_test(config)
        mock.assert_called_once_with(config)
        assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------
class TestSingleton:
    def test_same_instance(self):
        import services.distributed_load_testing as mod
        mod._load_tester = None
        with patch("shutil.which", return_value=None):
            s1 = get_load_tester()
            s2 = get_load_tester()
        assert s1 is s2
        mod._load_tester = None
