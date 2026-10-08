"""
ExecutorAgent 单元测试
覆盖: __init__, _check_signal, stop, _execute_action (13 branches), _take_screenshot
"""
import pytest
from unittest.mock import patch, MagicMock
import time


@pytest.fixture(autouse=True)
def _patch_deps():
    mock_session = MagicMock()
    mock_session.get_signal.return_value = "RUNNING"
    mock_session.set_context = MagicMock()
    mock_session.set_frame = MagicMock()
    mock_session.set_page = MagicMock()
    mock_session.set_status = MagicMock()
    mock_session.set_page_state = MagicMock()
    mock_session.set_intervention_screenshot = MagicMock()
    mock_session.get_page_state = MagicMock(return_value={})
    mock_session.get_context = MagicMock(return_value=None)

    with patch("agents.executor_agent.session_manager") as mock_sm, \
         patch("core.session_manager.session_manager") as mock_sm2, \
         patch("agents.executor_agent.dom_indexer") as mock_di, \
         patch("agents.executor_agent.http_request"), \
         patch("agents.executor_agent.execute_sql") as mock_sql, \
         patch("agents.executor_agent.snapshot_db") as mock_snap, \
         patch("agents.executor_agent.diff_db"), \
         patch("agents.executor_agent.backup_db") as mock_backup:
        mock_sm.get_session.return_value = mock_session
        mock_sm2.get_session.return_value = mock_session
        mock_di.resolve_target.return_value = ("#btn", "selector")
        mock_di.format_for_llm.return_value = ""
        mock_sql.return_value = {"status": "success", "data": [{"id": 1}]}
        mock_snap.return_value = {"status": "success", "data": []}
        mock_backup.return_value = {"status": "success", "message": "backed up"}
        yield mock_session, mock_di


def _make_executor():
    from agents.executor_agent import ExecutorAgent
    bus = MagicMock()
    bus.get_task_sync = MagicMock(return_value=None)
    bus.publish_result_sync = MagicMock()
    return ExecutorAgent(bus=bus, session_id="test_session")


def _make_page():
    page = MagicMock()
    page.goto = MagicMock()
    page.wait_for_load_state = MagicMock()
    page.content = MagicMock(return_value="<html>content</html>")
    page.url = "http://example.com"
    page.evaluate = MagicMock(return_value="")
    loc = MagicMock()
    loc.first = MagicMock()
    loc.first.click = MagicMock()
    loc.first.fill = MagicMock()
    loc.first.text_content = MagicMock(return_value="text")
    loc.first.scroll_into_view_if_needed = MagicMock()
    loc.first.hover = MagicMock()
    loc.first.select_option = MagicMock()
    page.locator = MagicMock(return_value=loc)
    page.get_by_role = MagicMock(return_value=loc)
    page.get_by_text = MagicMock(return_value=loc)
    page.get_by_placeholder = MagicMock(return_value=loc)
    page.get_by_label = MagicMock(return_value=loc)
    page.keyboard = MagicMock()
    page.screenshot = MagicMock(return_value=b"\x89PNG")
    page.route = MagicMock()
    return page


class TestInit:
    def test_default_attributes(self):
        executor = _make_executor()
        assert executor.running is True
        assert executor.bus is not None

    def test_bus_reference(self):
        bus = MagicMock()
        from agents.executor_agent import ExecutorAgent
        executor = ExecutorAgent(bus=bus)
        assert executor.bus is bus


class TestCheckSignal:
    def test_running_signal(self, _patch_deps):
        mock_sbs, _ = _patch_deps
        mock_sbs.get_signal.return_value = "RUNNING"
        executor = _make_executor()
        executor._check_signal()
        assert executor.running is True

    def test_stopped_signal(self, _patch_deps):
        mock_session, _ = _patch_deps
        mock_session.get_signal.return_value = "STOPPED"
        executor = _make_executor()
        with pytest.raises(Exception, match="Task stopped by user"):
            executor._check_signal()
        assert executor.running is False

    def test_paused_then_running(self, _patch_deps):
        mock_session, _ = _patch_deps
        call_count = 0
        def get_signal_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return "PAUSED"
            return "RUNNING"
        mock_session.get_signal.side_effect = get_signal_side_effect

        executor = _make_executor()
        with patch("agents.executor_agent.time.sleep"):
            executor._check_signal()
        assert executor.running is True


class TestStop:
    def test_stop_sets_running_false(self):
        executor = _make_executor()
        assert executor.running is True
        executor.stop()
        assert executor.running is False


class TestCaptchaAutoResolve:
    def test_is_captcha_blocking_step_only_for_submit_paths(self, _patch_deps):
        executor = _make_executor()

        assert executor._is_captcha_blocking_step("click", "登录按钮") is True
        assert executor._is_captcha_blocking_step("fill", "验证码输入框") is True
        assert executor._is_captcha_blocking_step("fill", "密码输入框") is False
        assert executor._is_captcha_blocking_step("assert", "登录页") is False

    def test_try_auto_resolve_captcha_success(self, _patch_deps):
        mock_session, _ = _patch_deps
        executor = _make_executor()
        page = _make_page()

        with patch("core.auth_interceptor.fill_captcha_if_present", return_value="ABCD"):
            screenshot = executor._try_auto_resolve_captcha(page)

        assert screenshot is not None
        executor.bus.publish_log_sync.assert_called_once()
        mock_session.set_intervention_screenshot.assert_called_once_with(None)
        mock_session.set_page_state.assert_called()

    def test_try_auto_resolve_captcha_returns_none_when_unsolved(self, _patch_deps):
        mock_session, _ = _patch_deps
        executor = _make_executor()
        page = _make_page()

        with patch("core.auth_interceptor.fill_captcha_if_present", return_value=None):
            screenshot = executor._try_auto_resolve_captcha(page)

        assert screenshot is None
        executor.bus.publish_log_sync.assert_not_called()
        mock_session.set_intervention_screenshot.assert_not_called()


class TestStructuredStepTracking:
    def test_resolve_step_index_prefers_task_value(self):
        executor = _make_executor()
        assert executor._resolve_step_index({"id": "t1", "step_index": 4}) == 4
        assert executor._step_sequence == 5

    def test_resolve_step_index_falls_back_to_sequence(self):
        executor = _make_executor()
        assert executor._resolve_step_index({"id": "t1"}) == 0
        assert executor._resolve_step_index({"id": "t2"}) == 1

    def test_build_step_log_includes_structured_fields(self):
        executor = _make_executor()
        log_entry = executor._build_step_log(
            log_type="result",
            event="step_result",
            step_desc="click(#submit)",
            content="success",
            task_id="task-1",
            action="click",
            target="#submit",
            value="",
            step_index=2,
            status="success",
            duration=1.25,
        )

        assert log_entry["type"] == "result"
        assert log_entry["event"] == "step_result"
        assert log_entry["task_id"] == "task-1"
        assert log_entry["step_index"] == 2
        assert log_entry["status"] == "success"
        assert log_entry["duration"] == 1.25


class TestProbePolicy:
    def test_probe_block_reason_blocks_fill_action(self, _patch_deps):
        from agents.executor_agent import ExecutorAgent

        executor = ExecutorAgent(
            bus=MagicMock(),
            session_id="test_session",
            execution_profile={"execution_mode": "probe", "interaction_policy": "read_only"},
        )

        reason = executor._probe_block_reason("fill", "用户名", "admin")
        assert "Read-only probe prohibits fill" in reason

    def test_probe_block_reason_allows_assert_action(self, _patch_deps):
        from agents.executor_agent import ExecutorAgent

        executor = ExecutorAgent(
            bus=MagicMock(),
            session_id="test_session",
            execution_profile={"execution_mode": "probe", "interaction_policy": "read_only"},
        )

        reason = executor._probe_block_reason("assert", "登录", "")
        assert reason == ""


# ═══════════════════════════════════════════════════
# _execute_action 分支测试
# ═══════════════════════════════════════════════════

class TestExecuteActionGoto:
    def test_goto_with_http(self, _patch_deps):
        executor = _make_executor()
        page = _make_page()
        result = executor._execute_action(page, {"action": "goto", "target": "http://example.com"})
        page.goto.assert_called_once()
        assert "Navigated" in result

    def test_goto_without_http(self, _patch_deps):
        executor = _make_executor()
        page = _make_page()
        result = executor._execute_action(page, {"action": "goto", "target": "example.com"})
        page.goto.assert_called_once()
        call_args = page.goto.call_args[0][0]
        assert call_args.startswith("https://")


class TestExecuteActionClick:
    def test_click_via_selector(self, _patch_deps):
        _, mock_di = _patch_deps
        mock_di.resolve_target.return_value = ("#btn", "selector")
        executor = _make_executor()
        page = _make_page()
        result = executor._execute_action(page, {"action": "click", "target": "#btn"})
        assert "Clicked" in result

    def test_click_via_text(self, _patch_deps):
        _, mock_di = _patch_deps
        mock_di.resolve_target.return_value = ("text=Login", "text")
        executor = _make_executor()
        page = _make_page()
        result = executor._execute_action(page, {"action": "click", "target": "Login"})
        assert "Clicked" in result


class TestExecuteActionFill:
    def test_fill_success(self, _patch_deps):
        executor = _make_executor()
        page = _make_page()
        result = executor._execute_action(page, {"action": "fill", "target": "username", "value": "admin"})
        assert "Filled" in result
        assert "admin" in result

    def test_fill_fallback_to_type(self, _patch_deps):
        _, mock_di = _patch_deps
        mock_di.resolve_target.return_value = ("#input", "selector")
        executor = _make_executor()
        page = _make_page()
        loc = page.locator.return_value.first
        loc.fill.side_effect = Exception("fill failed")
        loc.click = MagicMock()
        result = executor._execute_action(page, {"action": "fill", "target": "input", "value": "val"})
        assert "Filled" in result


class TestExecuteActionWait:
    def test_wait_default(self, _patch_deps):
        executor = _make_executor()
        page = _make_page()
        with patch("agents.executor_agent.time.sleep"):
            with patch("agents.executor_agent.time.time") as mock_time:
                mock_time.side_effect = [0.0, 0.5, 1.1]
                executor._execute_action(page, {"action": "wait", "target": "1"})


class TestExecuteActionKey:
    def test_key_enter(self, _patch_deps):
        executor = _make_executor()
        page = _make_page()
        executor._execute_action(page, {"action": "key", "target": "Enter"})
        page.keyboard.press.assert_called_with("Enter")

    def test_key_chinese_alias(self, _patch_deps):
        executor = _make_executor()
        page = _make_page()
        executor._execute_action(page, {"action": "key", "target": "回车"})
        page.keyboard.press.assert_called_with("Enter")


class TestExecuteActionAssert:
    def test_assert_text_match(self, _patch_deps):
        executor = _make_executor()
        page = _make_page()
        page.content.return_value = "Welcome to the dashboard"
        result = executor._execute_action(page, {"action": "assert", "target": "Welcome"})
        assert "Assert Passed" in result

    def test_assert_text_not_found(self, _patch_deps):
        executor = _make_executor()
        page = _make_page()
        page.content.return_value = "Nothing here"
        with patch("agents.executor_agent.planner_service") if False else patch("services.planner_service.planner_service") as mock_ps:
            mock_ps.semantic_verify.return_value = {"passed": False, "reason": "not found"}
            with pytest.raises(Exception, match="Assertion Failed"):
                executor._execute_action(page, {"action": "assert", "target": "Login"})


class TestExecuteActionDbQuery:
    def test_db_query_success(self, _patch_deps):
        executor = _make_executor()
        page = _make_page()
        result = executor._execute_action(page, {"action": "db_query", "target": "SELECT 1"})
        assert isinstance(result, list)

    def test_db_query_error(self, _patch_deps):
        with patch("core.db_tools.execute_sql", return_value={"status": "error", "message": "syntax error"}):
            executor = _make_executor()
            page = _make_page()
            with pytest.raises(Exception, match="syntax error"):
                executor._execute_action(page, {"action": "db_query", "target": "BAD SQL"})


class TestExecuteActionScroll:
    def test_scroll_down(self, _patch_deps):
        executor = _make_executor()
        page = _make_page()
        result = executor._execute_action(page, {"action": "scroll", "target": "", "value": "down"})
        page.evaluate.assert_called()
        assert "Scrolled" in result

    def test_scroll_chinese(self, _patch_deps):
        executor = _make_executor()
        page = _make_page()
        result = executor._execute_action(page, {"action": "scroll", "target": "顶部", "value": ""})
        assert "Scrolled" in result


class TestExecuteActionMock:
    def test_mock_route(self, _patch_deps):
        executor = _make_executor()
        page = _make_page()
        result = executor._execute_action(page, {"action": "mock", "target": "**/api/users", "value": '{"users": []}'})
        page.route.assert_called_once()
        assert "Route mocked" in result


class TestExecuteActionSetVar:
    def test_set_var(self, _patch_deps):
        mock_session, _ = _patch_deps
        executor = _make_executor()
        page = _make_page()
        result = executor._execute_action(page, {"action": "set_var", "target": "myvar", "value": "myval"})
        mock_session.set_context.assert_called_with("myvar", "myval")
        assert result == "myval"


class TestExecuteActionDone:
    def test_done(self, _patch_deps):
        executor = _make_executor()
        page = _make_page()
        result = executor._execute_action(page, {"action": "done", "target": ""})
        assert result == "Done"


class TestExecuteActionUnknown:
    def test_unknown_action(self, _patch_deps):
        executor = _make_executor()
        page = _make_page()
        with pytest.raises(Exception, match="Unknown action"):
            executor._execute_action(page, {"action": "unknown_xyz", "target": ""})


class TestExecuteActionHover:
    def test_hover_via_selector(self, _patch_deps):
        _, mock_di = _patch_deps
        mock_di.resolve_target.return_value = ("#menu", "selector")
        executor = _make_executor()
        page = _make_page()
        result = executor._execute_action(page, {"action": "hover", "target": "#menu"})
        assert "Hovered" in result


class TestExecuteActionSelect:
    def test_select_via_selector(self, _patch_deps):
        _, mock_di = _patch_deps
        mock_di.resolve_target.return_value = ("#dropdown", "selector")
        executor = _make_executor()
        page = _make_page()
        result = executor._execute_action(page, {"action": "select", "target": "#dropdown", "value": "option1"})
        assert "Selected" in result


class TestExecuteActionScreenshot:
    def test_screenshot(self, _patch_deps):
        executor = _make_executor()
        page = _make_page()
        with patch("os.makedirs"):
            result = executor._execute_action(page, {"action": "screenshot", "target": ""})
        assert "Screenshot saved" in result


class TestExecuteActionExtract:
    def test_extract_via_selector(self, _patch_deps):
        mock_sbs, mock_di = _patch_deps
        mock_di.resolve_target.return_value = ("#price", "selector")
        executor = _make_executor()
        page = _make_page()
        result = executor._execute_action(page, {"action": "extract", "target": "#price", "value": "price_var"})
        assert result is not None


# ═══════════════════════════════════════════════════
# _take_screenshot
# ═══════════════════════════════════════════════════

class TestTakeScreenshot:
    def test_success(self, _patch_deps):
        mock_session, _ = _patch_deps
        executor = _make_executor()
        page = _make_page()
        page.screenshot.return_value = b"\x89PNG"
        result = executor._take_screenshot(page)
        assert result is not None
        mock_session.set_frame.assert_called()

    def test_failure_returns_none(self, _patch_deps):
        executor = _make_executor()
        page = _make_page()
        page.screenshot.side_effect = Exception("timeout")
        result = executor._take_screenshot(page)
        assert result is None



class TestSessionBootstrap:
    def test_apply_session_bootstrap_returns_none_without_payload(self, _patch_deps):
        mock_session, _ = _patch_deps
        mock_session.get_context.return_value = None
        executor = _make_executor()
        page = _make_page()

        assert executor._apply_session_bootstrap(page) is None

    def test_apply_session_bootstrap_uses_cached_result(self, _patch_deps):
        mock_session, _ = _patch_deps
        mock_session.get_context.side_effect = lambda key=None: {
            "auth_bootstrap": {"base_url": "http://127.0.0.1:81"},
            "auth_bootstrap_applied": True,
            "auth_bootstrap_result": {"target_url": "http://127.0.0.1:81/unifiedGoodService/uniProductService"},
        }.get(key)
        executor = _make_executor()
        page = _make_page()

        result = executor._apply_session_bootstrap(page)

        assert result["target_url"].endswith("/unifiedGoodService/uniProductService")
        executor.bus.publish_log_sync.assert_not_called()

    def test_apply_session_bootstrap_calls_helper_and_persists_result(self, _patch_deps):
        mock_session, _ = _patch_deps
        mock_session.get_context.side_effect = lambda key=None: {
            "auth_bootstrap": {"base_url": "http://127.0.0.1:81", "username": "example-org", "password": "123456"},
            "auth_bootstrap_applied": False,
            "auth_bootstrap_result": {},
        }.get(key)
        executor = _make_executor()
        page = _make_page()

        with patch("agents.executor_agent.apply_auth_bootstrap", return_value={"target_url": "http://127.0.0.1:81/unifiedGoodService/uniProductService"}) as mock_apply:
            result = executor._apply_session_bootstrap(page)

        assert result["target_url"].endswith("/unifiedGoodService/uniProductService")
        mock_apply.assert_called_once_with(page, {"base_url": "http://127.0.0.1:81", "username": "example-org", "password": "123456"})
        mock_session.set_context.assert_any_call("auth_bootstrap_applied", True)
        mock_session.set_context.assert_any_call("auth_bootstrap_result", result)
        executor.bus.publish_log_sync.assert_called_once()
