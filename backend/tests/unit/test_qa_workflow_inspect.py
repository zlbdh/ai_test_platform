# -*- coding: utf-8 -*-
"""
Phase 2 单元测试 — QAState, inspect 节点, 报告集成
"""
import pytest
import json
from unittest.mock import MagicMock, patch

from core.state import QAState
from core.models import InspectionResult
from agents.inspector_agent import InspectorAgent
from agents.master_agent import MasterAgent


# ============================================================================
# QAState 新字段测试
# ============================================================================

class TestQAStateInspectionField:
    """QAState 新增 inspection_results 字段"""

    def test_field_exists(self):
        assert "inspection_results" in QAState.__annotations__

    def test_initial_state_accepts_inspection_results(self):
        state: QAState = {
            "test_scenario": "test",
            "task_description": "",
            "ui_results": [],
            "api_results": [],
            "data_results": [],
            "ops_results": [],
            "current_step": "start",
            "completed_steps": [],
            "failed_steps": [],
            "messages": [],
            "errors": [],
            "warnings": [],
            "test_data": {},
            "final_report": None,
            "subgraph_states": {},
            "inspection_results": [],
            "healing_context": None,
        }
        assert state["inspection_results"] == []


# ============================================================================
# inspect 节点测试 (从 QAWorkflow 类中提取方法测试)
# ============================================================================

def _make_workflow_with_fake_inspector(vlm_response: str):
    """构造一个带 fake Inspector 的 QAWorkflow（不编译图）"""
    from workflows.qa_workflow import QAWorkflow

    wf = QAWorkflow.__new__(QAWorkflow)
    fake_vlm = MagicMock()
    fake_resp = MagicMock()
    fake_resp.content = vlm_response
    fake_vlm.invoke = MagicMock(return_value=fake_resp)
    wf.inspector = InspectorAgent(vlm=fake_vlm)
    return wf


class TestInspectNode:
    """_inspect_node 方法测试"""

    BASE_STATE = {
        "test_scenario": "test",
        "task_description": "",
        "ui_results": [],
        "api_results": [],
        "data_results": [],
        "ops_results": [],
        "current_step": "ui_test",
        "completed_steps": ["ui_test"],
        "failed_steps": [],
        "messages": [],
        "errors": [],
        "warnings": [],
        "test_data": {},
        "final_report": None,
        "subgraph_states": {},
        "inspection_results": [],
        "healing_context": None,
    }

    def _make_state(self, **overrides):
        import copy
        state = copy.deepcopy(self.BASE_STATE)
        state.update(overrides)
        return state

    def test_no_screenshots_skips(self):
        """无截图时跳过审查"""
        wf = _make_workflow_with_fake_inspector('{}')
        state = self._make_state(ui_results=[{"action": "click", "status": "success"}])
        result = wf._inspect_node(state)
        assert result["inspection_results"] == []

    def test_inspect_passed(self):
        """VLM 判定通过"""
        vlm_resp = json.dumps({"passed": True, "confidence": 0.95, "reason": "OK", "anomalies": []})
        wf = _make_workflow_with_fake_inspector(vlm_resp)
        state = self._make_state(
            ui_results=[{
                "action": "click",
                "screenshot": "fakebase64==",
                "url": "http://test.com",
                "visible_text": "Success",
                "step_desc": "click(提交)",
                "expected_outcome": "提交成功",
            }]
        )
        result = wf._inspect_node(state)
        assert len(result["inspection_results"]) == 1
        assert result["inspection_results"][0]["passed"] is True
        assert result["inspection_results"][0]["confidence"] == 0.95
        assert len(result["errors"]) == 0

    def test_inspect_rejected_adds_error(self):
        """VLM 判定驳回 → errors 追加"""
        vlm_resp = json.dumps({
            "passed": False, "confidence": 0.8,
            "reason": "Red error banner", "anomalies": ["toast visible"]
        })
        wf = _make_workflow_with_fake_inspector(vlm_resp)
        state = self._make_state(
            ui_results=[{
                "action": "click",
                "screenshot": "fakebase64==",
                "url": "http://test.com",
                "visible_text": "",
                "step_desc": "click(按钮)",
            }]
        )
        result = wf._inspect_node(state)
        assert len(result["inspection_results"]) == 1
        assert result["inspection_results"][0]["passed"] is False
        assert len(result["errors"]) == 1
        assert "驳回" in result["errors"][0]["error"]

    def test_inspect_multiple_results(self):
        """多个截图结果同时审查"""
        vlm_resp = json.dumps({"passed": True, "confidence": 0.9, "reason": "ok", "anomalies": []})
        wf = _make_workflow_with_fake_inspector(vlm_resp)
        state = self._make_state(
            ui_results=[
                {"action": "click", "screenshot": "a==", "url": "http://a.com", "visible_text": ""},
                {"action": "fill", "screenshot": "b==", "url": "http://b.com", "visible_text": ""},
            ],
            api_results=[
                {"action": "api_call", "screenshot": "c==", "url": "http://c.com", "visible_text": ""},
            ]
        )
        result = wf._inspect_node(state)
        assert len(result["inspection_results"]) == 3

    def test_inspect_vlm_exception_auto_passes(self):
        """VLM 异常时自动放行"""
        wf = _make_workflow_with_fake_inspector("")
        wf.inspector._vlm.invoke.side_effect = RuntimeError("API timeout")
        state = self._make_state(
            ui_results=[{"action": "click", "screenshot": "x==", "url": "http://x.com", "visible_text": ""}]
        )
        result = wf._inspect_node(state)
        assert len(result["inspection_results"]) == 1
        assert result["inspection_results"][0]["passed"] is True
        assert result["inspection_results"][0]["confidence"] == 0.0


# ============================================================================
# _route_after_inspect 路由测试
# ============================================================================

class TestRouteAfterInspect:
    """inspect 后路由逻辑"""

    def _make_wf(self):
        from workflows.qa_workflow import QAWorkflow
        wf = QAWorkflow.__new__(QAWorkflow)
        wf.inspector = InspectorAgent()
        return wf

    def test_route_to_rca_on_reject(self):
        """有 inspect 错误 → 路由到 rca"""
        wf = self._make_wf()
        state = {
            "errors": [{"step": "inspect", "error": "Inspector 驳回: ..."}],
            "ops_results": [],
            "completed_steps": ["ui_test"],
            "planned_steps": ["ui_test", "api_test"],
        }
        assert wf._route_after_inspect(state) == "rca"

    def test_route_to_api_after_ui(self):
        """ui_test 通过 → 继续 api_test"""
        wf = self._make_wf()
        state = {
            "errors": [],
            "ops_results": [],
            "completed_steps": ["ui_test"],
            "planned_steps": ["ui_test", "api_test"],
        }
        assert wf._route_after_inspect(state) == "next"

    def test_route_to_data_after_api(self):
        """api_test 通过 → 继续 data_verification"""
        wf = self._make_wf()
        state = {
            "errors": [],
            "ops_results": [],
            "completed_steps": ["ui_test", "api_test"],
            "planned_steps": ["ui_test", "api_test", "data_verification"],
        }
        assert wf._route_after_inspect(state) == "data"

    def test_route_to_end_when_done(self):
        """所有计划步骤完成 → end"""
        wf = self._make_wf()
        state = {
            "errors": [],
            "ops_results": [],
            "completed_steps": ["api_test"],
            "planned_steps": ["api_test"],
        }
        assert wf._route_after_inspect(state) == "end"

    def test_skip_rca_if_already_done(self):
        """已有 RCA 报告 → 不再路由到 rca"""
        wf = self._make_wf()
        state = {
            "errors": [{"step": "inspect", "error": "..."}],
            "ops_results": [{"type": "rca_report", "report": {}}],
            "completed_steps": ["ui_test"],
            "planned_steps": ["ui_test"],
        }
        assert wf._route_after_inspect(state) == "end"


# ============================================================================
# 报告集成测试
# ============================================================================

class TestReportInspectionIntegration:
    """generate_report 包含 Inspector 结果"""

    def _make_master(self):
        m = MasterAgent.__new__(MasterAgent)
        return m

    def test_report_includes_inspection_results(self):
        m = self._make_master()
        state = {
            "test_scenario": "login test",
            "task_description": "test login",
            "completed_steps": ["ui_test"],
            "failed_steps": [],
            "ui_results": [],
            "api_results": [],
            "data_results": [],
            "ops_results": [],
            "errors": [],
            "warnings": [],
            "inspection_results": [
                {"step": "click(login)", "passed": True, "confidence": 0.95, "reason": "OK", "anomalies": []},
            ],
        }
        report = m.generate_report(state)
        assert "inspection_results" in report
        assert report["summary"]["inspection_total"] == 1
        assert report["summary"]["inspection_passed"] == 1
        assert report["summary"]["inspection_rejected"] == 0

    def test_report_with_rejections(self):
        m = self._make_master()
        state = {
            "test_scenario": "payment test",
            "task_description": "",
            "completed_steps": ["ui_test"],
            "failed_steps": [],
            "ui_results": [],
            "api_results": [],
            "data_results": [],
            "ops_results": [],
            "errors": [{"step": "inspect", "error": "驳回"}],
            "warnings": [],
            "inspection_results": [
                {"step": "click(pay)", "passed": False, "confidence": 0.8, "reason": "Red error", "anomalies": ["err"]},
                {"step": "fill(amount)", "passed": True, "confidence": 0.9, "reason": "ok", "anomalies": []},
            ],
        }
        report = m.generate_report(state)
        assert report["summary"]["inspection_rejected"] == 1
        assert any("驳回" in r for r in report["recommendations"])

    def test_report_empty_inspection(self):
        m = self._make_master()
        state = {
            "test_scenario": "test",
            "task_description": "",
            "completed_steps": [],
            "failed_steps": [],
            "ui_results": [],
            "api_results": [],
            "data_results": [],
            "ops_results": [],
            "errors": [],
            "warnings": [],
            "inspection_results": [],
        }
        report = m.generate_report(state)
        assert report["summary"]["inspection_total"] == 0
        assert report["inspection_results"] == []
        assert any("通过" in r for r in report["recommendations"])
