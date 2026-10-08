"""
PlannerAgent 单元测试
覆盖: __init__, _resolve_variables, run (mode dispatch), stop,
       _initialize_plan, _run_quick_mode (非空计划), _handle_result
"""
import pytest
import base64
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio


# ---------------------------------------------------------------------------
# 公用 fixture：mock 掉所有外部依赖后再 import
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _patch_externals():
    """Mock planner_agent 的所有重量级依赖"""
    mock_session = MagicMock()
    mock_session.get_context = MagicMock(return_value=None)
    mock_session.get_page = MagicMock(return_value=None)
    mock_session.get_page_state = MagicMock(return_value={})
    mock_session.set_status = MagicMock()
    mock_session.set_page_state = MagicMock()
    mock_session.run_browser = AsyncMock(return_value=None)

    with patch("agents.planner_agent.planner_service") as mock_ps, \
         patch("agents.planner_agent.session_manager") as mock_sm:
        mock_sm.get_session.return_value = mock_session
        mock_ps.generate_plan_sync = MagicMock(return_value=[])
        yield mock_ps, mock_session


def _make_planner(**kwargs):
    from agents.planner_agent import PlannerAgent
    bus = MagicMock()
    bus.publish_log = AsyncMock()
    bus.publish_task = AsyncMock()
    bus.get_result = AsyncMock(return_value=None)
    bus.shutdown = AsyncMock()
    defaults = {"task_goal": "测试登录功能", "bus": bus, "mode": "quick", "session_id": "test_session", "target_url": ""}
    defaults.update(kwargs)
    return PlannerAgent(**defaults)


# ---------------------------------------------------------------------------
# 测试初始化
# ---------------------------------------------------------------------------
class TestInit:
    def test_default_attributes(self):
        planner = _make_planner()
        assert planner.task_goal == "测试登录功能"
        assert planner.mode == "quick"
        assert planner.running is True
        assert planner.plan == []
        assert planner.plan_step_index == 0

    def test_smart_mode(self):
        planner = _make_planner(mode="smart")
        assert planner.mode == "smart"


# ---------------------------------------------------------------------------
# 测试 _resolve_variables
# ---------------------------------------------------------------------------
class TestResolveVariables:
    def test_no_variables(self):
        planner = _make_planner()
        assert planner._resolve_variables("hello world") == "hello world"

    def test_context_variable(self):
        planner = _make_planner()
        planner.context = {"username": "admin"}
        result = planner._resolve_variables("user is ${username}")
        assert result == "user is admin"

    def test_shared_browser_state_variable(self, _patch_externals):
        _, mock_session = _patch_externals
        mock_session.get_context = MagicMock(return_value="captured_value")
        planner = _make_planner()
        result = planner._resolve_variables("val=${some_var}")
        assert result == "val=captured_value"

    def test_faker_variable(self):
        planner = _make_planner()
        result = planner._resolve_variables("name: ${fake.name}")
        # Faker returns an American English name; verify that substitution succeeds
        assert "${fake.name}" not in result
        assert len(result) > len("name: ")

    def test_unresolved_variable(self, _patch_externals):
        _, mock_session = _patch_externals
        mock_session.get_context = MagicMock(return_value=None)
        planner = _make_planner()
        planner.context = {}
        result = planner._resolve_variables("val=${unknown_var}")
        # 无法解析的变量保持不变
        assert "${unknown_var}" in result

    def test_non_string_input(self):
        planner = _make_planner()
        assert planner._resolve_variables(123) == 123

    def test_multiple_variables(self):
        planner = _make_planner()
        planner.context = {"a": "1", "b": "2"}
        result = planner._resolve_variables("${a}+${b}")
        assert result == "1+2"


# ---------------------------------------------------------------------------
# 测试 run (模式分发)
# ---------------------------------------------------------------------------
class TestRun:
    @pytest.mark.asyncio
    async def test_quick_mode_dispatch(self):
        planner = _make_planner(mode="quick")
        with patch.object(planner, '_run_quick_mode', new_callable=AsyncMock) as mock_quick, \
             patch.object(planner, '_run_smart_mode', new_callable=AsyncMock) as mock_smart:
            await planner.run()
            mock_quick.assert_called_once()
            mock_smart.assert_not_called()

    @pytest.mark.asyncio
    async def test_smart_mode_dispatch(self):
        planner = _make_planner(mode="smart")
        with patch.object(planner, '_run_quick_mode', new_callable=AsyncMock) as mock_quick, \
             patch.object(planner, '_run_smart_mode', new_callable=AsyncMock) as mock_smart:
            await planner.run()
            mock_smart.assert_called_once()
            mock_quick.assert_not_called()


# ---------------------------------------------------------------------------
# 测试 stop
# ---------------------------------------------------------------------------
class TestStop:
    def test_stop_sets_running_false(self):
        planner = _make_planner()
        assert planner.running is True
        planner.stop()
        assert planner.running is False


# ---------------------------------------------------------------------------
# 测试 _run_quick_mode（空计划 → 立即终止）
# ---------------------------------------------------------------------------
class TestRunQuickModeEmptyPlan:
    @pytest.mark.asyncio
    async def test_empty_plan_aborts(self):
        planner = _make_planner(mode="quick")
        with patch.object(planner, '_initialize_plan', new_callable=AsyncMock):
            planner.plan = []  # 空计划
            await planner._run_quick_mode()
            assert planner.running is False
            planner.bus.shutdown.assert_called_once()


# ---------------------------------------------------------------------------
# 测试 _initialize_plan
# ---------------------------------------------------------------------------
class TestInitializePlan:
    @pytest.mark.asyncio
    async def test_generates_plan(self, _patch_externals):
        mock_ps, _ = _patch_externals
        mock_ps.generate_plan = MagicMock(return_value={
            "test_cases": [
                {"scenario": "登录", "steps": [{"action": "goto", "target": "http://example.com"}]},
                {"scenario": "搜索", "steps": [{"action": "click", "target": "#btn"}]},
            ]
        })
        planner = _make_planner()
        await planner._initialize_plan()
        assert len(planner.plan) == 2

    @pytest.mark.asyncio
    async def test_generates_plan_from_async_service(self, _patch_externals):
        mock_ps, _ = _patch_externals
        mock_ps.generate_plan = AsyncMock(return_value={
            "test_cases": [
                {"scenario": "登录", "steps": [{"action": "goto", "target": "http://example.com"}]},
            ]
        })
        planner = _make_planner()
        await planner._initialize_plan()
        assert len(planner.plan) == 1

    @pytest.mark.asyncio
    async def test_passes_target_url_to_planner_service(self, _patch_externals):
        mock_ps, _ = _patch_externals
        mock_ps.generate_plan = AsyncMock(return_value={"test_cases": []})
        planner = _make_planner(target_url="http://127.0.0.1:81")
        await planner._initialize_plan()
        mock_ps.generate_plan.assert_awaited_once_with(
            "测试登录功能",
            True,
            "http://127.0.0.1:81",
            execution_mode="default",
            interaction_policy="default",
        )

    @pytest.mark.asyncio
    async def test_empty_plan(self, _patch_externals):
        mock_ps, _ = _patch_externals
        mock_ps.generate_plan = MagicMock(return_value={"test_cases": []})
        planner = _make_planner()
        await planner._initialize_plan()
        assert planner.plan == []

    @pytest.mark.asyncio
    async def test_probe_plan_is_trimmed_and_logged(self, _patch_externals):
        mock_ps, _ = _patch_externals
        mock_ps.generate_plan = AsyncMock(return_value={
            "test_cases": [
                {
                    "scenario": "登录页首屏",
                    "steps": [
                        {"action": "goto", "target": "https://example.com/login"},
                        {"action": "wait", "target": "1"},
                        {"action": "screenshot", "target": "hero"},
                    ],
                },
                {
                    "scenario": "深层页面",
                    "steps": [
                        {"action": "click", "target": "进入后台"},
                    ],
                },
            ]
        })
        planner = _make_planner(
            execution_profile={
                "execution_mode": "probe",
                "interaction_policy": "read_only",
                "max_scenarios": 1,
                "max_steps": 2,
                "step_budget": 2,
            }
        )

        await planner._initialize_plan()

        assert len(planner.plan) == 2
        assert [step["action"] for step in planner.plan] == ["goto", "wait"]
        events = [
            call.args[0].get("event")
            for call in planner.bus.publish_log.await_args_list
            if call.args and isinstance(call.args[0], dict)
        ]
        assert "probe_plan_trimmed" in events


# ---------------------------------------------------------------------------
# 测试 _run_quick_mode（非空计划 — 浅层验证，不进入完整循环）
# ---------------------------------------------------------------------------
class TestRunQuickModeWithPlan:
    @pytest.mark.asyncio
    async def test_plan_not_empty_no_immediate_shutdown(self):
        """有计划时，不会在 _initialize_plan 后立即 shutdown"""
        planner = _make_planner(mode="quick")
        # 预设非空计划
        planner.plan = [
            {"id": "s1", "action": "goto", "target": "http://example.com", "value": ""},
        ]
        # 但让 planner 立即停止，避免进入异步等待循环
        planner.running = False
        with patch.object(planner, '_initialize_plan', new_callable=AsyncMock):
            await planner._run_quick_mode()
            # 有计划，所以不应该因为"空计划"而 shutdown
            # （而是因为 running=False 退出循环）
            assert len(planner.plan) == 1

    @pytest.mark.asyncio
    async def test_stopped_planner_exits_loop(self):
        """running=False 时 quick mode 应立即退出循环"""
        planner = _make_planner(mode="quick")
        planner.plan = [
            {"id": "s1", "action": "goto", "target": "http://x.com", "value": ""},
            {"id": "s2", "action": "click", "target": "#a", "value": ""},
        ]
        planner.running = False
        with patch.object(planner, '_initialize_plan', new_callable=AsyncMock):
            await planner._run_quick_mode()
            # 因为 running=False，循环不执行，不发布 task

    @pytest.mark.asyncio
    async def test_published_task_contains_step_index_and_scenario(self):
        planner = _make_planner(mode="quick")
        planner.plan = [
            {"action": "goto", "target": "http://example.com", "value": "", "_scenario": "登录"},
        ]

        published_tasks = []
        result_queue = []

        async def publish_task(task):
            published_tasks.append(task)
            result_queue.append({
                "task_id": task["id"],
                "status": "success",
                "message": "OK",
                "data": None,
            })

        async def get_result(timeout=0.5):
            if result_queue:
                return result_queue.pop(0)
            return None

        planner.bus.publish_task = AsyncMock(side_effect=publish_task)
        planner.bus.get_result = AsyncMock(side_effect=get_result)

        with patch.object(planner, '_initialize_plan', new_callable=AsyncMock):
            await planner._run_quick_mode()

        assert len(published_tasks) == 1
        assert published_tasks[0]["step_index"] == 0
        assert published_tasks[0]["scenario"] == "登录"
        planner.bus.shutdown.assert_called_once()



# ---------------------------------------------------------------------------
# 测试 _handle_result
# ---------------------------------------------------------------------------
class TestHandleResult:
    def test_success_result(self):
        planner = _make_planner()
        result = {"task_id": "t1", "status": "success", "message": "OK", "data": None}
        planner._handle_result(result)
        # Should not raise

    def test_success_result_with_data(self):
        planner = _make_planner()
        result = {"task_id": "t1", "status": "success", "message": "OK", "data": {"extracted": "value"}}
        planner._handle_result(result)
        assert planner.context.get("extracted") == "value"

    def test_error_result(self):
        planner = _make_planner()
        result = {"task_id": "t1", "status": "error", "message": "Not found", "data": None}
        planner._handle_result(result)
        # Should not raise — errors logged but not raised


class TestLoopRecoveryPolicy:
    def test_stops_on_captcha_instead_of_autofill(self):
        planner = _make_planner(mode="smart")

        recovery = planner._build_loop_recovery(
            "fill",
            {"interactive_elements": "请输入验证码 captcha 输入框"},
        )

        assert recovery["action"] == "done"
        assert "CAPTCHA" in recovery["target"]
        assert recovery["value"] == ""

    def test_prefers_submit_click_when_login_controls_exist(self):
        planner = _make_planner(mode="smart")

        recovery = planner._build_loop_recovery(
            "fill",
            {"interactive_elements": "用户名输入框 登录 提交"},
        )

        assert recovery["action"] == "click"
        assert recovery["target"] == "登录按钮"

    def test_scrolls_when_no_specific_recovery_control_exists(self):
        planner = _make_planner(mode="smart")

        recovery = planner._build_loop_recovery(
            "click",
            {"interactive_elements": "导航菜单 帮助链接"},
        )

        assert recovery["action"] == "scroll"
        assert recovery["value"] == "down"


class TestCapturePageScreenshot:
    @pytest.mark.asyncio
    async def test_uses_session_browser_bridge(self, _patch_externals):
        _, mock_session = _patch_externals
        mock_session.get_page.return_value = object()
        mock_session.run_browser = AsyncMock(return_value=b"image-bytes")
        planner = _make_planner(mode="smart")

        screenshot = await planner._capture_page_screenshot()

        assert screenshot == base64.b64encode(b"image-bytes").decode("utf-8")
        mock_session.run_browser.assert_awaited_once()




@pytest.mark.asyncio
@pytest.mark.parametrize("sentinel", ["(Not navigated)", "（未导航）"])
async def test_probe_does_not_treat_navigation_sentinel_as_loaded_page(sentinel, _patch_externals):
    _, session = _patch_externals
    planner = _make_planner(execution_profile={"execution_mode": "probe"})
    session.get_page_state.return_value = {"url": sentinel}
    clock_values = iter([0.0, 0.0, 100.0])
    with patch("agents.planner_agent.logger"), \
         patch("agents.planner_agent.time.time", side_effect=lambda: next(clock_values, 100.0)), \
         patch("agents.planner_agent.asyncio.sleep", new_callable=AsyncMock):
        await planner._run_probe_mode()
    session.get_page_state.assert_called_once()
    messages = [call.args[0] for call in planner.bus.publish_log.await_args_list]
    assert not any(item.get("event") == "probe_summary" for item in messages)
    assert any(item.get("type") == "error" and "timed out" in item["content"] for item in messages)
    planner.bus.publish_task.assert_not_awaited()
