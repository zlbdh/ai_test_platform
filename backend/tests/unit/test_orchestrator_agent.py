"""
Orchestrator unit tests
Coverage: __init__, start_task (busy/zombie detection), stop_task.
"""
import pytest
from unittest.mock import patch, MagicMock
import threading
from contextlib import contextmanager


@pytest.fixture(autouse=True)
def _patch_deps():
    """Mock all external dependencies."""
    mock_session = MagicMock()
    mock_session.set_status = MagicMock()
    mock_session.set_signal = MagicMock()
    mock_session.clear_logs = MagicMock()
    mock_session.set_page_state = MagicMock()
    mock_session.get_logs = MagicMock(return_value=[])
    mock_session.get_page = MagicMock(return_value=None)

    with patch("agents.orchestrator.PlannerAgent") as mock_pa, \
         patch("agents.orchestrator.ExecutorAgent") as mock_ea, \
         patch("agents.orchestrator.session_manager") as mock_sm, \
         patch("agents.orchestrator.EventBus") as mock_bus, \
         patch("agents.orchestrator.get_connection"), \
         patch("agents.orchestrator.get_execution_center_service") as mock_exec_center:
        mock_pa.return_value = MagicMock()
        mock_ea.return_value = MagicMock()
        mock_bus.return_value = MagicMock()
        mock_sm.get_session.return_value = mock_session
        mock_exec_center.return_value = MagicMock()
        yield {
            "PlannerAgent": mock_pa,
            "ExecutorAgent": mock_ea,
            "session_manager": mock_sm,
            "session": mock_session,
            "EventBus": mock_bus,
            "execution_center": mock_exec_center,
        }


def _make_orchestrator():
    from agents.orchestrator import Orchestrator
    return Orchestrator(session_id="test_session")


# ---------------------------------------------------------------------------
# Initialization tests
# ---------------------------------------------------------------------------
class TestInit:
    def test_default_state(self):
        orch = _make_orchestrator()
        assert orch.is_running is False
        assert orch.planner is None
        assert orch.executor is None
        assert orch.active_task_id == ""

    def test_not_running_initially(self):
        orch = _make_orchestrator()
        assert orch._executor_error is None
        assert orch._task_requirement == ""


# ---------------------------------------------------------------------------
# start_task tests
# ---------------------------------------------------------------------------
class TestStartTask:
    def test_start_returns_task_id(self):
        orch = _make_orchestrator()
        # Mock asyncio.create_task because there is no event loop.
        with patch("asyncio.create_task") as mock_ct:
            def fake_create_task(coro):
                coro.close()
                return MagicMock()
            mock_ct.side_effect = fake_create_task
            task_id = orch.start_task("Test login functionality", mode="quick", target_url="http://example.com")
        assert task_id.startswith("task_")
        assert orch.is_running is True
        assert orch._task_requirement == "Test login functionality"
        assert orch._task_target_url == "http://example.com"
        assert orch._task_mode == "quick"

    def test_start_uses_target_url_as_display_requirement_when_text_is_broken(self, _patch_deps):
        orch = _make_orchestrator()
        with patch("asyncio.create_task") as mock_ct:
            def fake_create_task(coro):
                coro.close()
                return MagicMock()
            mock_ct.side_effect = fake_create_task
            task_id = orch.start_task("??????? API ??????? UI ??", mode="quick", target_url="http://example.com/health")
        assert task_id.startswith("task_")
        assert orch._task_requirement == "http://example.com/health"
        _patch_deps["session"].set_status.assert_called_with("RUNNING", task="http://example.com/health")

    def test_busy_when_already_running(self):
        orch = _make_orchestrator()
        orch.is_running = True
        # Simulate a still-running e_thread.
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        orch.e_thread = mock_thread
        # Simulate an unfinished planner_task.
        mock_task = MagicMock()
        mock_task.done.return_value = False
        orch._planner_task = mock_task

        result = orch.start_task("New task")
        assert result == "Busy"

    def test_zombie_detection_dead_thread(self):
        orch = _make_orchestrator()
        orch.is_running = True
        # Simulate a stopped e_thread: a zombie task.
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = False
        orch.e_thread = mock_thread
        orch._planner_task = None

        with patch("asyncio.create_task") as mock_ct:
            def fake_create_task(coro):
                coro.close()
                return MagicMock()
            mock_ct.side_effect = fake_create_task
            task_id = orch.start_task("Resume task")
        assert task_id.startswith("task_")
        assert orch.is_running is True

    def test_zombie_detection_done_planner(self):
        orch = _make_orchestrator()
        orch.is_running = True
        orch.e_thread = None
        # Simulate a completed planner_task: a zombie task.
        mock_task = MagicMock()
        mock_task.done.return_value = True
        orch._planner_task = mock_task

        with patch("asyncio.create_task") as mock_ct:
            def fake_create_task(coro):
                coro.close()
                return MagicMock()
            mock_ct.side_effect = fake_create_task
            task_id = orch.start_task("Resume task")
        assert task_id.startswith("task_")


# ---------------------------------------------------------------------------
# stop_task tests
# ---------------------------------------------------------------------------
class TestStopTask:
    def test_stop_resets_state(self, _patch_deps):
        orch = _make_orchestrator()
        orch.is_running = True
        orch.planner = MagicMock()
        orch.executor = MagicMock()
        orch._planner_task = MagicMock()
        orch._planner_task.done.return_value = False

        orch.stop_task()

        assert orch.is_running is False
        orch.planner.stop.assert_called_once()
        orch.executor.stop.assert_called_once()
        orch._planner_task.cancel.assert_called_once()
        _patch_deps["session"].set_status.assert_called_with("IDLE")

    def test_stop_when_no_agents(self):
        orch = _make_orchestrator()
        orch.planner = None
        orch.executor = None
        orch._planner_task = None
        # Should not raise
        orch.stop_task()
        assert orch.is_running is False


class TestPersistRun:
    def test_persist_generates_task_scoped_report(self, _patch_deps):
        orch = _make_orchestrator()
        orch.active_task_id = "task_123"
        orch._task_requirement = "测试服务商品中心"
        orch._task_requirement_display = "测试服务商品中心"
        orch._task_target_url = "http://127.0.0.1:81/unifiedGoodService/uniProductService"
        orch._task_mode = "quick"
        orch._start_time = 100.0
        _patch_deps["session"].get_logs.return_value = [
            {"type": "system", "content": "Mission Accomplished"},
            {"type": "result", "event": "step_result", "status": "success", "content": "✅ success"},
        ]

        conn = MagicMock()

        @contextmanager
        def fake_connection():
            yield conn

        reporter = MagicMock()
        execution_center = MagicMock()

        def fake_asyncio_run(coro):
            coro.close()
            return None

        with patch("agents.orchestrator.get_connection", side_effect=fake_connection), \
             patch("agents.orchestrator.get_execution_center_service", return_value=execution_center), \
             patch("agents.orchestrator.get_reporter", return_value=reporter), \
             patch("agents.orchestrator.time.time", return_value=101.0), \
             patch("agents.orchestrator.asyncio.get_running_loop", side_effect=RuntimeError), \
             patch("agents.orchestrator.asyncio.run", side_effect=fake_asyncio_run), \
             patch("core.notify_helper.send_completion_notification", return_value=None):
            orch._persist_test_run()

        reporter.generate_report.assert_called_once_with(task_id="task_123")
        _, kwargs = execution_center.upsert_run.call_args
        assert kwargs["requirement"] == "测试服务商品中心"
        assert kwargs["requirement_display"] == "测试服务商品中心"
        assert kwargs["requirement_raw"] == "测试服务商品中心"
        assert kwargs["task_text_state"] == "normal"
