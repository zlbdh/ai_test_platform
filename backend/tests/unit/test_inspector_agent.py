# -*- coding: utf-8 -*-
"""
Inspector Agent 单元测试
覆盖：should_inspect / inspect 通过&驳回 / JSON解析异常 / VLM不可用降级
"""
import pytest
import json
from unittest.mock import MagicMock, patch

from agents.inspector_agent import InspectorAgent, SKIP_ACTIONS
from core.models import InspectionResult


# ============================================================================
# should_inspect 白名单测试
# ============================================================================

class TestShouldInspect:
    """动作白名单判定"""

    @pytest.mark.parametrize("action", ["goto", "wait", "scroll", "screenshot", "set_var", "done"])
    def test_skip_actions(self, action):
        assert InspectorAgent.should_inspect(action) is False

    @pytest.mark.parametrize("action", ["click", "fill", "select", "hover", "key", "assert", "extract", "api_call", "db_query", "visual_check", "mock"])
    def test_inspectable_actions(self, action):
        assert InspectorAgent.should_inspect(action) is True

    def test_unknown_action_is_inspectable(self):
        assert InspectorAgent.should_inspect("some_new_action") is True


# ============================================================================
# _parse_result JSON 解析
# ============================================================================

class TestParseResult:
    """VLM 返回文本解析"""

    def test_parse_valid_passed(self):
        raw = json.dumps({"passed": True, "confidence": 0.95, "reason": "OK", "anomalies": []})
        r = InspectorAgent._parse_result(raw)
        assert r.passed is True
        assert r.confidence == 0.95
        assert r.reason == "OK"
        assert r.anomalies == []

    def test_parse_valid_failed(self):
        raw = json.dumps({
            "passed": False,
            "confidence": 0.8,
            "reason": "Red error banner visible",
            "anomalies": ["Error toast", "Form not cleared"]
        })
        r = InspectorAgent._parse_result(raw)
        assert r.passed is False
        assert r.confidence == 0.8
        assert len(r.anomalies) == 2

    def test_parse_with_code_fence(self):
        raw = '```json\n{"passed": false, "confidence": 0.7, "reason": "fail", "anomalies": ["x"]}\n```'
        r = InspectorAgent._parse_result(raw)
        assert r.passed is False
        assert r.confidence == 0.7

    def test_parse_with_bare_code_fence(self):
        raw = '```\n{"passed": true, "confidence": 1.0, "reason": "ok", "anomalies": []}\n```'
        r = InspectorAgent._parse_result(raw)
        assert r.passed is True

    def test_parse_bad_json_auto_passes(self):
        r = InspectorAgent._parse_result("This is not JSON at all.")
        assert r.passed is True
        assert r.confidence == 0.0
        assert "JSON parse error" in r.reason

    def test_parse_missing_fields_uses_defaults(self):
        raw = json.dumps({"passed": False})
        r = InspectorAgent._parse_result(raw)
        assert r.passed is False
        assert r.confidence == 0.5  # default
        assert r.reason == ""
        assert r.anomalies == []

    def test_parse_empty_string(self):
        r = InspectorAgent._parse_result("")
        assert r.passed is True
        assert r.confidence == 0.0


# ============================================================================
# inspect() 完整调用测试 (使用 fake VLM)
# ============================================================================

def _make_fake_vlm(response_text: str):
    """构造一个 fake VLM，invoke() 返回固定 content"""
    fake = MagicMock()
    fake_response = MagicMock()
    fake_response.content = response_text
    fake.invoke = MagicMock(return_value=fake_response)
    return fake


class TestInspect:
    """inspect() 端到端测试"""

    SAMPLE_PAGE_STATE = {
        "url": "https://example.com/dashboard",
        "title": "Dashboard",
        "visible_text": "Welcome to Dashboard | Total: 42 | Status: Active",
    }

    SAMPLE_SCREENSHOT = "iVBORw0KGgoAAAANSUhEUg=="  # tiny fake base64

    def test_inspect_passed(self):
        vlm_response = json.dumps({
            "passed": True,
            "confidence": 0.95,
            "reason": "Page shows success message",
            "anomalies": []
        })
        agent = InspectorAgent(vlm=_make_fake_vlm(vlm_response))
        result = agent.inspect(
            screenshot_b64=self.SAMPLE_SCREENSHOT,
            step_desc="click(提交按钮)",
            expected_outcome="应显示提交成功",
            page_state=self.SAMPLE_PAGE_STATE,
        )
        assert result.passed is True
        assert result.confidence == 0.95
        assert result.anomalies == []

    def test_inspect_rejected(self):
        vlm_response = json.dumps({
            "passed": False,
            "confidence": 0.85,
            "reason": "Red error banner: insufficient balance",
            "anomalies": ["Error toast visible", "Submit button still active"]
        })
        agent = InspectorAgent(vlm=_make_fake_vlm(vlm_response))
        result = agent.inspect(
            screenshot_b64=self.SAMPLE_SCREENSHOT,
            step_desc="click(付款按钮)",
            expected_outcome="应显示付款成功",
            page_state=self.SAMPLE_PAGE_STATE,
        )
        assert result.passed is False
        assert result.confidence == 0.85
        assert len(result.anomalies) == 2

    def test_inspect_vlm_returns_bad_json(self):
        """VLM 返回非 JSON 时自动 pass"""
        agent = InspectorAgent(vlm=_make_fake_vlm("I cannot analyze this image"))
        result = agent.inspect(
            screenshot_b64=self.SAMPLE_SCREENSHOT,
            step_desc="click(按钮)",
            expected_outcome="",
            page_state=self.SAMPLE_PAGE_STATE,
        )
        assert result.passed is True
        assert result.confidence == 0.0

    def test_inspect_vlm_none_auto_passes(self):
        """VLM 不可用时自动 pass"""
        agent = InspectorAgent(vlm=None)
        # Force vlm property to return None
        agent._vlm = None
        with patch("agents.inspector_agent.get_vision_llm", return_value=None):
            result = agent.inspect(
                screenshot_b64=self.SAMPLE_SCREENSHOT,
                step_desc="click(按钮)",
                expected_outcome="",
                page_state=self.SAMPLE_PAGE_STATE,
            )
        assert result.passed is True
        assert "unavailable" in result.reason.lower()

    def test_inspect_vlm_raises_exception(self):
        """VLM 调用抛异常时自动 pass"""
        fake_vlm = MagicMock()
        fake_vlm.invoke = MagicMock(side_effect=RuntimeError("API timeout"))
        agent = InspectorAgent(vlm=fake_vlm)
        result = agent.inspect(
            screenshot_b64=self.SAMPLE_SCREENSHOT,
            step_desc="click(按钮)",
            expected_outcome="",
            page_state=self.SAMPLE_PAGE_STATE,
        )
        assert result.passed is True
        assert result.confidence == 0.0
        assert "VLM error" in result.reason

    def test_inspect_page_state_with_list_visible_text(self):
        """visible_text 为 list 时正确拼接"""
        vlm_response = json.dumps({"passed": True, "confidence": 0.9, "reason": "ok", "anomalies": []})
        agent = InspectorAgent(vlm=_make_fake_vlm(vlm_response))
        result = agent.inspect(
            screenshot_b64=self.SAMPLE_SCREENSHOT,
            step_desc="fill(搜索框)",
            expected_outcome="",
            page_state={"url": "http://test.com", "visible_text": ["Hello", "World"]},
        )
        assert result.passed is True
        # Verify VLM was called (the message was constructed)
        agent.vlm.invoke.assert_called_once()

    def test_inspect_empty_expected_outcome(self):
        """expected_outcome 为空时使用默认文本"""
        vlm_response = json.dumps({"passed": True, "confidence": 1.0, "reason": "ok", "anomalies": []})
        fake_vlm = _make_fake_vlm(vlm_response)
        agent = InspectorAgent(vlm=fake_vlm)
        agent.inspect(
            screenshot_b64=self.SAMPLE_SCREENSHOT,
            step_desc="click(按钮)",
            expected_outcome="",
            page_state=self.SAMPLE_PAGE_STATE,
        )
        # Check the prompt contains the default text
        call_args = fake_vlm.invoke.call_args[0][0]  # first positional arg: messages list
        prompt_content = call_args[0].content[0]["text"]  # HumanMessage -> content[0] -> text
        assert "The action should complete normally" in prompt_content


# ============================================================================
# InspectionResult 数据类测试
# ============================================================================

class TestInspectionResult:
    """InspectionResult Pydantic 模型"""

    def test_minimal(self):
        r = InspectionResult(passed=True)
        assert r.passed is True
        assert r.confidence == 1.0
        assert r.reason == ""
        assert r.anomalies == []

    def test_full(self):
        r = InspectionResult(
            passed=False,
            confidence=0.75,
            reason="Error detected",
            anomalies=["red banner", "empty list"]
        )
        assert r.passed is False
        assert r.confidence == 0.75
        assert len(r.anomalies) == 2

    def test_json_roundtrip(self):
        r = InspectionResult(passed=True, confidence=0.9, reason="ok", anomalies=[])
        data = r.model_dump()
        r2 = InspectionResult(**data)
        assert r2.passed == r.passed
        assert r2.confidence == r.confidence
