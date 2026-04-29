# -*- coding: utf-8 -*-
"""
单元测试: Orchestrator 生命周期
测试任务状态管理和异常处理
"""
import asyncio
import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from agents.orchestrator import Orchestrator


class TestOrchestratorLifecycle:
    """测试 Orchestrator 基本生命周期"""

    def test_initial_state(self):
        orch = Orchestrator()
        assert orch.is_running == False
        assert orch.active_task_id == ""
        assert orch._executor_error is None

    def test_zombie_detection(self):
        """测试僵尸状态检测"""
        orch = Orchestrator()
        orch.is_running = True
        orch.e_thread = None  # No thread
        orch._planner_task = None  # No task
        
        # 没有线程引用时不应该判定为 zombie
        result = orch.start_task("test")
        assert result == "Busy"

    def test_stop_when_not_running(self):
        """停止未运行的任务不应抛异常"""
        orch = Orchestrator()
        orch.stop_task()  # Should not raise
        assert orch.is_running == False

    def test_persist_test_run_no_db(self):
        """持久化在数据库不可访问时应优雅失败"""
        orch = Orchestrator()
        orch.active_task_id = "test_999"
        orch._task_requirement = "sample test"
        # 这应该不会抛异常（即使 DB 不存在）
        with patch("agents.orchestrator.get_execution_center_service", return_value=MagicMock()):
            orch._persist_test_run()

    def test_persist_test_run_runs_notification_without_loop(self):
        """在无运行事件循环时，应同步完成通知而不是泄漏 coroutine。"""
        orch = Orchestrator()
        orch.active_task_id = "test_notify"
        orch._task_requirement = "sample test"
        orch._task_target_url = "https://example.com"
        orch._task_mode = "smart"
        orch.session.append_log({"type": "system", "content": "Mission Accomplished."})

        notified = {"called": False}

        async def fake_notify(**kwargs):
            await asyncio.sleep(0)
            notified["called"] = True

        class _FakeConn:
            def execute(self, *args, **kwargs):
                return None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        fake_reporter = MagicMock()
        fake_execution_center = MagicMock()

        with patch("agents.orchestrator.get_connection", return_value=_FakeConn()), \
             patch("agents.orchestrator.get_execution_center_service", return_value=fake_execution_center), \
             patch("agents.orchestrator.get_reporter", return_value=fake_reporter), \
             patch("core.notify_helper.send_completion_notification", side_effect=fake_notify):
            orch._persist_test_run()

        assert notified["called"] is True

    def test_start_task_augments_goal_with_auth_bootstrap_context(self):
        orch = Orchestrator(session_id="auth_bootstrap_goal_test")
        orch.session.clear_context()
        orch.session.set_context("auth_bootstrap", {
            "city": "北京市",
            "station_id": "528",
        })
        orch.session.set_context("auth_bootstrap_applied", True)
        orch.session.set_context("auth_bootstrap_result", {
            "city": "北京市",
            "station_id": "528",
        })

        fake_thread = MagicMock()
        fake_thread.is_alive.return_value = True
        fake_planner_task = MagicMock()
        fake_planner_task.done.return_value = False

        def fake_create_task(coro):
            coro.close()
            return fake_planner_task

        with patch("agents.orchestrator.EventBus") as mock_bus, \
             patch("agents.orchestrator.get_execution_center_service", return_value=MagicMock()), \
             patch("agents.orchestrator.PlannerAgent") as mock_planner_cls, \
             patch("agents.orchestrator.ExecutorAgent"), \
             patch("agents.orchestrator.threading.Thread", return_value=fake_thread), \
             patch("agents.orchestrator.asyncio.create_task", side_effect=fake_create_task), \
             patch.object(orch, "_run_planner", new=AsyncMock()):
            task_id = orch.start_task(
                "进入统一商品服务中心-服务商品中心并校验搜索能力",
                mode="quick",
                target_url="http://127.0.0.1:81/unifiedGoodService/uniProductService",
            )

        assert task_id.startswith("task_")
        planner_goal = mock_planner_cls.call_args.kwargs["task_goal"]
        assert "会话预认证已完成" in planner_goal
        assert "已切换到北京市-528" in planner_goal
        assert "不要再执行登录、点击城市/站点或切换站点动作" in planner_goal
        assert "必须首先访问目标地址 http://127.0.0.1:81/unifiedGoodService/uniProductService" in planner_goal

    def test_start_task_uses_fallback_display_requirement_but_keeps_raw_goal(self):
        orch = Orchestrator(session_id="broken_requirement_test")
        fake_thread = MagicMock()
        fake_thread.is_alive.return_value = True
        fake_planner_task = MagicMock()
        fake_planner_task.done.return_value = False

        def fake_create_task(coro):
            coro.close()
            return fake_planner_task

        with patch("agents.orchestrator.EventBus") as mock_bus, \
             patch("agents.orchestrator.get_execution_center_service", return_value=MagicMock()), \
             patch("agents.orchestrator.PlannerAgent") as mock_planner_cls, \
             patch("agents.orchestrator.ExecutorAgent"), \
             patch("agents.orchestrator.threading.Thread", return_value=fake_thread), \
             patch("agents.orchestrator.asyncio.create_task", side_effect=fake_create_task), \
             patch.object(orch, "_run_planner", new=AsyncMock()):
            task_id = orch.start_task(
                "??????? API ??????? UI ??",
                mode="quick",
                target_url="http://127.0.0.1:8020/api/health",
            )

        assert task_id.startswith("task_")
        assert orch._task_requirement == "http://127.0.0.1:8020/api/health"
        assert orch._task_requirement_raw == "??????? API ??????? UI ??"
        assert orch._task_requirement_display == "http://127.0.0.1:8020/api/health"
        assert orch._task_text_state == "broken_fallback"
        planner_goal = mock_planner_cls.call_args.kwargs["task_goal"]
        assert "??????? API ??????? UI ??" in planner_goal
        assert "必须首先访问目标地址 http://127.0.0.1:8020/api/health" in planner_goal
        mock_bus.return_value.publish_log_sync.assert_called_once()

    def test_start_task_auto_enables_probe_profile_for_readonly_requirement(self):
        orch = Orchestrator(session_id="probe_requirement_test")
        fake_thread = MagicMock()
        fake_thread.is_alive.return_value = True
        fake_planner_task = MagicMock()
        fake_planner_task.done.return_value = False

        def fake_create_task(coro):
            coro.close()
            return fake_planner_task

        with patch("agents.orchestrator.EventBus"), \
             patch("agents.orchestrator.get_execution_center_service", return_value=MagicMock()), \
             patch("agents.orchestrator.PlannerAgent") as mock_planner_cls, \
             patch("agents.orchestrator.ExecutorAgent") as mock_executor_cls, \
             patch("agents.orchestrator.threading.Thread", return_value=fake_thread), \
             patch("agents.orchestrator.asyncio.create_task", side_effect=fake_create_task), \
             patch.object(orch, "_run_planner", new=AsyncMock()):
            task_id = orch.start_task(
                "打开登录页，不要登录，不要输入，只验证可访问性",
                mode="smart",
                target_url="https://example.com/login",
            )

        assert task_id.startswith("task_")
        assert orch._execution_mode == "probe"
        assert orch._interaction_policy == "read_only"
        assert orch._step_budget == 8
        assert orch.session.get_context("execution_mode") == "probe"
        assert orch.session.get_context("interaction_policy") == "read_only"
        assert "只读探针模式" in mock_planner_cls.call_args.kwargs["task_goal"]
        assert mock_planner_cls.call_args.kwargs["execution_profile"]["execution_mode"] == "probe"
        assert mock_executor_cls.call_args.kwargs["execution_profile"]["interaction_policy"] == "read_only"
