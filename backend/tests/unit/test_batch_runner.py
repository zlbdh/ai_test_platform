"""
BatchRunner 单元测试
覆盖: 数据结构 (BatchStatus/TaskStatus/TestCase/BatchResult),
      run_batch (并发控制/错误隔离/取消/进度回调),
      cancel_batch, get_batch_status, load_from_csv,
      create_from_data_factory, get_batch_runner 单例
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import tempfile
import os

from services.batch_runner import (
    BatchStatus, TaskStatus, TestCase, BatchResult,
    BatchRunner, get_batch_runner
)
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# 数据结构测试
# ---------------------------------------------------------------------------
class TestBatchStatus:
    def test_enum_values(self):
        assert BatchStatus.PENDING == "pending"
        assert BatchStatus.RUNNING == "running"
        assert BatchStatus.COMPLETED == "completed"
        assert BatchStatus.FAILED == "failed"
        assert BatchStatus.CANCELLED == "cancelled"


class TestTaskStatus:
    def test_enum_values(self):
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.SUCCESS == "success"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.SKIPPED == "skipped"


class TestTestCase:
    def test_defaults(self):
        tc = TestCase()
        assert tc.name == ""
        assert tc.instruction == ""
        assert tc.url == ""
        assert tc.data == {}
        assert tc.status == TaskStatus.PENDING
        assert tc.result is None
        assert tc.error is None
        assert tc.duration is None

    def test_custom_fields(self):
        tc = TestCase(id="t1", name="登录测试", instruction="测试登录", url="https://x.com")
        assert tc.id == "t1"
        assert tc.name == "登录测试"

    def test_duration_with_timestamps(self):
        t1 = datetime(2026, 1, 1, 0, 0, 0)
        t2 = datetime(2026, 1, 1, 0, 0, 5)
        tc = TestCase(started_at=t1, completed_at=t2)
        assert tc.duration == 5.0

    def test_duration_without_timestamps(self):
        tc = TestCase()
        assert tc.duration is None

    def test_auto_id_generation(self):
        tc1 = TestCase()
        tc2 = TestCase()
        assert len(tc1.id) == 8
        assert tc1.id != tc2.id


class TestBatchResult:
    def _make_result(self, **kwargs):
        defaults = {
            "batch_id": "test-001",
            "status": BatchStatus.COMPLETED,
            "total": 10,
            "success": 8,
            "failed": 2,
            "skipped": 0,
            "started_at": datetime(2026, 1, 1, 0, 0, 0),
            "completed_at": datetime(2026, 1, 1, 0, 1, 0),
        }
        defaults.update(kwargs)
        return BatchResult(**defaults)

    def test_duration(self):
        br = self._make_result()
        assert br.duration == 60.0

    def test_duration_without_completed(self):
        br = self._make_result(completed_at=None)
        assert br.duration is None

    def test_success_rate(self):
        br = self._make_result(total=10, success=8)
        assert br.success_rate == 80.0

    def test_success_rate_zero_total(self):
        br = self._make_result(total=0, success=0)
        assert br.success_rate == 0.0

    def test_to_dict(self):
        tc = TestCase(id="t1", name="测试1", status=TaskStatus.SUCCESS)
        br = self._make_result(tasks=[tc])
        d = br.to_dict()
        assert d["batch_id"] == "test-001"
        assert d["status"] == "completed"
        assert d["success_rate"] == "80.0%"
        assert d["duration"] == "60.00s"
        assert len(d["tasks"]) == 1
        assert d["tasks"][0]["id"] == "t1"

    def test_to_dict_without_completed(self):
        br = self._make_result(completed_at=None)
        d = br.to_dict()
        assert d["duration"] is None
        assert d["completed_at"] is None


# ---------------------------------------------------------------------------
# BatchRunner 初始化
# ---------------------------------------------------------------------------
class TestBatchRunnerInit:
    def test_default_concurrency(self):
        runner = BatchRunner()
        assert runner.max_concurrency == 3

    def test_custom_concurrency(self):
        runner = BatchRunner(max_concurrency=10)
        assert runner.max_concurrency == 10


# ---------------------------------------------------------------------------
# run_batch 核心测试
# ---------------------------------------------------------------------------
class TestRunBatch:
    @pytest.mark.asyncio
    async def test_all_success(self):
        """所有任务成功"""
        runner = BatchRunner(max_concurrency=2)
        cases = [TestCase(id=f"t{i}", name=f"测试{i}") for i in range(3)]

        async def executor(tc):
            return {"ok": True}

        result = await runner.run_batch(cases, executor)
        assert result.status == BatchStatus.COMPLETED
        assert result.success == 3
        assert result.failed == 0
        assert result.total == 3
        for tc in cases:
            assert tc.status == TaskStatus.SUCCESS
            assert tc.result == {"ok": True}
            assert tc.started_at is not None
            assert tc.completed_at is not None

    @pytest.mark.asyncio
    async def test_partial_failure(self):
        """部分任务失败应标记 batch 为 FAILED"""
        runner = BatchRunner()
        cases = [TestCase(id="ok"), TestCase(id="fail")]

        async def executor(tc):
            if tc.id == "fail":
                raise RuntimeError("模拟失败")
            return {"ok": True}

        result = await runner.run_batch(cases, executor)
        assert result.status == BatchStatus.FAILED
        assert result.success == 1
        assert result.failed == 1

    @pytest.mark.asyncio
    async def test_error_isolation(self):
        """一个任务失败不应影响其他任务"""
        runner = BatchRunner(max_concurrency=1)
        cases = [TestCase(id="a"), TestCase(id="b"), TestCase(id="c")]

        async def executor(tc):
            if tc.id == "b":
                raise ValueError("任务 B 失败")
            return {"ok": True}

        result = await runner.run_batch(cases, executor)
        assert cases[0].status == TaskStatus.SUCCESS
        assert cases[1].status == TaskStatus.FAILED
        assert cases[1].error == "任务 B 失败"
        assert cases[2].status == TaskStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_sync_executor(self):
        """支持同步 executor (自动 to_thread)"""
        runner = BatchRunner()
        cases = [TestCase(id="t1")]

        def sync_executor(tc):
            return {"sync": True}

        result = await runner.run_batch(cases, sync_executor)
        assert result.success == 1
        assert cases[0].result == {"sync": True}

    @pytest.mark.asyncio
    async def test_progress_callback(self):
        """进度回调应被调用"""
        runner = BatchRunner()
        cases = [TestCase(id="t1"), TestCase(id="t2")]
        progress_calls = []

        def on_progress(tc, br):
            progress_calls.append(tc.id)

        async def executor(tc):
            return {}

        await runner.run_batch(cases, executor, on_progress=on_progress)
        assert len(progress_calls) == 2

    @pytest.mark.asyncio
    async def test_progress_callback_error_is_graceful(self):
        """进度回调异常不应影响执行"""
        runner = BatchRunner()
        cases = [TestCase(id="t1")]

        def on_progress(tc, br):
            raise RuntimeError("回调崩溃")

        async def executor(tc):
            return {"ok": True}

        result = await runner.run_batch(cases, executor, on_progress=on_progress)
        assert result.success == 1

    @pytest.mark.asyncio
    async def test_concurrency_limit(self):
        """并发数应被信号量限制"""
        runner = BatchRunner(max_concurrency=2)
        cases = [TestCase(id=f"t{i}") for i in range(5)]
        max_concurrent = 0
        current = 0
        lock = asyncio.Lock()

        async def executor(tc):
            nonlocal max_concurrent, current
            async with lock:
                current += 1
                if current > max_concurrent:
                    max_concurrent = current
            await asyncio.sleep(0.05)
            async with lock:
                current -= 1
            return {}

        await runner.run_batch(cases, executor)
        assert max_concurrent <= 2

    @pytest.mark.asyncio
    async def test_empty_batch(self):
        """空批量应正常完成"""
        runner = BatchRunner()
        async def executor(tc): return {}
        result = await runner.run_batch([], executor)
        assert result.status == BatchStatus.COMPLETED
        assert result.total == 0
        assert result.success == 0

    @pytest.mark.asyncio
    async def test_batch_cleanup(self):
        """batch 完成后应清理 _running_batches"""
        runner = BatchRunner()
        cases = [TestCase(id="t1")]
        async def executor(tc): return {}
        await runner.run_batch(cases, executor)
        assert len(runner._running_batches) == 0


# ---------------------------------------------------------------------------
# cancel_batch 测试
# ---------------------------------------------------------------------------
class TestCancelBatch:
    def test_cancel_unknown_batch(self):
        runner = BatchRunner()
        assert runner.cancel_batch("unknown") is False

    def test_cancel_running_batch(self):
        runner = BatchRunner()
        # 模拟一个正在运行的 batch
        runner._running_batches["b1"] = MagicMock()
        assert runner.cancel_batch("b1") is True
        assert "b1" in runner._cancelled


# ---------------------------------------------------------------------------
# get_batch_status 测试
# ---------------------------------------------------------------------------
class TestGetBatchStatus:
    def test_unknown_batch(self):
        runner = BatchRunner()
        assert runner.get_batch_status("unknown") is None

    def test_running_batch(self):
        runner = BatchRunner()
        mock_result = MagicMock()
        runner._running_batches["b1"] = mock_result
        assert runner.get_batch_status("b1") is mock_result


# ---------------------------------------------------------------------------
# load_from_csv 测试
# ---------------------------------------------------------------------------
class TestLoadFromCsv:
    def test_csv_loading(self, tmp_path):
        csv_file = tmp_path / "tests.csv"
        csv_file.write_text(
            "name,url,username\n"
            "登录测试,https://example.com,admin\n"
            "注册测试,https://example.com/reg,user1\n",
            encoding="utf-8"
        )
        cases = BatchRunner.load_from_csv(
            str(csv_file),
            instruction_template="在{url}上用{username}登录",
            url_field="url"
        )
        assert len(cases) == 2
        assert cases[0].id == "csv_1"
        assert cases[0].name == "登录测试"
        assert cases[0].url == "https://example.com"
        assert cases[0].instruction == "在https://example.com上用admin登录"
        assert cases[1].instruction == "在https://example.com/reg上用user1登录"


# ---------------------------------------------------------------------------
# create_from_data_factory 测试
# ---------------------------------------------------------------------------
class TestCreateFromDataFactory:
    def test_factory_generation(self):
        mock_factory = MagicMock()
        mock_factory.generate.return_value = {"name": "张三", "email": "zs@test.com"}

        with patch("core.data_factory.get_data_factory", return_value=mock_factory):
            cases = BatchRunner.create_from_data_factory(
                template={"name": "string", "email": "email"},
                instruction_template="用{name}({email})注册",
                count=3,
                base_url="https://x.com"
            )
        assert len(cases) == 3
        assert cases[0].id == "gen_1"
        assert cases[0].url == "https://x.com"
        assert cases[0].instruction == "用张三(zs@test.com)注册"
        assert mock_factory.generate.call_count == 3


# ---------------------------------------------------------------------------
# 全局单例测试
# ---------------------------------------------------------------------------
class TestGetBatchRunner:
    def test_singleton(self):
        # 重置单例
        import services.batch_runner as mod
        mod._runner = None
        r1 = get_batch_runner()
        r2 = get_batch_runner()
        assert r1 is r2
        # 清理
        mod._runner = None

    def test_default_concurrency(self):
        import services.batch_runner as mod
        mod._runner = None
        r = get_batch_runner()
        assert r.max_concurrency == 3
        mod._runner = None

    def test_custom_concurrency(self):
        import services.batch_runner as mod
        mod._runner = None
        r = get_batch_runner(max_concurrency=5)
        assert r.max_concurrency == 5
        mod._runner = None
