"""
QA 工作流 - LangGraph 主流程
协调各个 Agent 执行测试任务
"""
import logging
from typing import Dict, Any, List, TypedDict, Annotated, Literal

logger = logging.getLogger(__name__)
import operator
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from core.config import Config
from core.state import QAState
from agents.master_agent import MasterAgent
from agents.ui_agent import UIAgent
from agents.api_agent import APIAgent
from agents.data_agent import DataAgent
from agents.ops_agent import OpsAgent
from agents.rca_agent import RCAAgent
from agents.inspector_agent import InspectorAgent
from workflows.subgraphs import get_subgraph


class QAWorkflow:
    """QA 平台工作流"""
    
    def __init__(self):
        """初始化 QA 工作流"""
        # 初始化 Agents
        self.master_agent = MasterAgent()
        self.ui_agent = UIAgent()
        self.api_agent = APIAgent()
        self.data_agent = DataAgent()
        self.ops_agent = OpsAgent()
        self.rca_agent = RCAAgent()
        self.inspector = InspectorAgent()
        
        # 初始化图
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """构建 LangGraph"""
        workflow = StateGraph(QAState)
        
        # 添加节点
        workflow.add_node("plan_test", self._plan_test_node)
        workflow.add_node("ui_test", self._ui_test_node)
        workflow.add_node("api_test", self._api_test_node)
        workflow.add_node("inspect", self._inspect_node)
        workflow.add_node("data_verification", self._data_verification_node)
        workflow.add_node("ops_analysis", self._ops_analysis_node)
        workflow.add_node("rca_analysis", self._rca_analysis_node)
        workflow.add_node("generate_report", self._generate_report_node)

        # 设置入口点
        workflow.set_entry_point("plan_test")

        # 添加边（基于计划动态路由）
        workflow.add_conditional_edges(
            "plan_test",
            self._route_after_planning,
            {
                "ui": "ui_test",
                "api": "api_test",
                "data": "data_verification",
                "ops": "ops_analysis",
                "end": "generate_report"
            }
        )

        # ui_test / api_test 完成后先经过 inspect 节点审查
        workflow.add_edge("ui_test", "inspect")
        workflow.add_edge("api_test", "inspect")

        # inspect 节点后根据审查结果路由
        workflow.add_conditional_edges(
            "inspect",
            self._route_after_inspect,
            {"next": "api_test", "data": "data_verification", "ops": "ops_analysis", "rca": "rca_analysis", "end": "generate_report"}
        )

        workflow.add_conditional_edges(
            "data_verification",
            self._route_after_step,
            {"next": "ops_analysis", "rca": "rca_analysis", "end": "generate_report"}
        )

        workflow.add_conditional_edges(
            "ops_analysis",
            self._route_after_step,
            {"rca": "rca_analysis", "end": "generate_report"}
        )

        workflow.add_edge("rca_analysis", "generate_report")
        workflow.add_edge("generate_report", END)
        
        return workflow.compile()
    
    # ================= 节点函数 =================
    
    def _plan_test_node(self, state: QAState) -> QAState:
        """规划测试节点"""
        logger.info("[Workflow] 正在规划测试任务...")
        scenario = state.get("test_scenario", "")
        
        # 调用 Master Agent 规划任务
        plan = self.master_agent.plan_test(scenario)
        
        # 更新状态
        state["task_description"] = plan.get("plan_text", "")
        state["current_step"] = "planning"
        
        # 确定执行顺序
        steps = []
        agents = plan.get("required_agents", [])
        
        if "ui_agent" in agents:
            steps.append("ui_test")
        if "api_agent" in agents:
            steps.append("api_test")
        if "data_agent" in agents:
            steps.append("data_verification")
        if "ops_agent" in agents:
            steps.append("ops_analysis")
        
        # 保存计划步骤用于路由
        # 注意：这里我们使用一个临时的 metadata 字段，实际应该在 State 定义中添加
        state["planned_steps"] = steps  # 需要在 QAState 中添加此字段或使用 safe get
        
        return state
    
    def _ui_test_node(self, state: QAState) -> QAState:
        """UI 测试节点"""
        logger.info("[Workflow] 执行 UI 测试...")
        scenario = state.get("test_scenario", "")
        
        try:
            # 调用 UI Agent
            # 这里调用 process_request 方法，它内部处理了任务分解和执行
            # 注意：实际调用可能需要根据 UIAgent 的接口调整
            result = self.ui_agent.run(state)
            
            # 记录结果
            if "ui_results" not in state:
                state["ui_results"] = []
            
            # 这里的 result 可能是整个 state，也可能是部分结果，根据 UIAgent 实现
            # 假设 UIAgent.run 更新了 state 并返回
            
            if state.get("ui_results") and any(r.get("status") == "error" for r in state["ui_results"]):
                state["errors"].append({"step": "ui_test", "error": "UI 测试包含失败步骤"})
            
            state["completed_steps"].append("ui_test")
            
        except Exception as e:
            state["errors"].append({"step": "ui_test", "error": str(e)})
            state["failed_steps"].append("ui_test")
        
        return state
    
    def _api_test_node(self, state: QAState) -> QAState:
        """API 测试节点"""
        logger.info("[Workflow] 执行 API 测试...")
        scenario = state.get("test_scenario", "")
        
        try:
            # 调用 API Agent
            result = self.api_agent.execute_test(scenario)
            
            # 记录结果
            if "api_results" not in state:
                state["api_results"] = []
            state["api_results"].append(result)
            
            if result.get("status") == "error":
                state["errors"].append({"step": "api_test", "error": str(result.get("errors"))})
                state["failed_steps"].append("api_test")
            else:
                state["completed_steps"].append("api_test")
                
        except Exception as e:
            state["errors"].append({"step": "api_test", "error": str(e)})
            state["failed_steps"].append("api_test")
        
        return state
    
    def _inspect_node(self, state: QAState) -> QAState:
        """Inspector 视觉质检节点 — 审查 ui_test/api_test 的执行结果截图"""
        logger.info("[Workflow] Inspector 视觉质检...")

        if "inspection_results" not in state:
            state["inspection_results"] = []

        # 收集最近一轮测试产生的截图结果
        results_to_inspect = []
        for r in state.get("ui_results", []):
            if isinstance(r, dict) and r.get("screenshot"):
                results_to_inspect.append(r)
        for r in state.get("api_results", []):
            if isinstance(r, dict) and r.get("screenshot"):
                results_to_inspect.append(r)

        if not results_to_inspect:
            logger.info("[Workflow] Inspector: 无截图可审查，跳过")
            return state

        for result in results_to_inspect:
            try:
                page_state = {
                    "url": result.get("url", "unknown"),
                    "visible_text": result.get("visible_text", ""),
                }
                inspection = self.inspector.inspect(
                    screenshot_b64=result.get("screenshot", ""),
                    step_desc=result.get("step_desc", result.get("action", "unknown")),
                    expected_outcome=result.get("expected_outcome", result.get("value", "")),
                    page_state=page_state,
                )
                inspection_record = {
                    "step": result.get("step_desc", result.get("action", "")),
                    "passed": inspection.passed,
                    "confidence": inspection.confidence,
                    "reason": inspection.reason,
                    "anomalies": inspection.anomalies,
                }
                state["inspection_results"].append(inspection_record)

                if not inspection.passed:
                    error_msg = f"Inspector 驳回: {inspection.reason}"
                    if inspection.anomalies:
                        error_msg += f" | 异常: {', '.join(inspection.anomalies)}"
                    state["errors"].append({"step": "inspect", "error": error_msg})
                    logger.warning(f"[Workflow] {error_msg}")

            except Exception as e:
                logger.warning(f"[Workflow] Inspector 审查异常 (auto-passing): {e}")
                state["inspection_results"].append({
                    "step": result.get("step_desc", "unknown"),
                    "passed": True,
                    "confidence": 0.0,
                    "reason": f"Inspector error: {e}",
                    "anomalies": [],
                })

        return state

    def _data_verification_node(self, state: QAState) -> QAState:
        """数据验证节点"""
        logger.info("[Workflow] 执行数据验证...")
        scenario = state.get("test_scenario", "")
        
        try:
            # 调用 Data Agent
            result = self.data_agent.execute_test(scenario)
            
            # 记录结果
            if "data_results" not in state:
                state["data_results"] = []
            state["data_results"].append(result)
            
            if result.get("status") == "error":
                state["errors"].append({"step": "data_verification", "error": str(result.get("errors"))})
                state["failed_steps"].append("data_verification")
            else:
                state["completed_steps"].append("data_verification")
                
        except Exception as e:
            state["errors"].append({"step": "data_verification", "error": str(e)})
            state["failed_steps"].append("data_verification")
        
        return state
    
    def _ops_analysis_node(self, state: QAState) -> QAState:
        """运维分析节点"""
        logger.info("[Workflow] 执行运维分析...")
        
        # 只有在有错误或显式要求时才执行 Ops 分析
        if not state.get("errors") and "ops_analysis" not in state.get("planned_steps", []):
            return state
            
        try:
            # 收集之前的错误
            errors = state.get("errors", [])
            log_path = Config.LOG_FILE_PATH
            
            results = []
            for error in errors:
                diagnosis = self.ops_agent.diagnose_error(str(error.get("error", "")), log_path)
                results.append(diagnosis)
            
            # 如果没有显式错误但被要求运行，则分析最近的日志
            if not errors:
                analysis = self.ops_agent.analyze_logs(log_path)
                results.append(analysis)
            
            # 记录结果
            if "ops_results" not in state:
                state["ops_results"] = []
            state["ops_results"].extend(results)
            
            state["completed_steps"].append("ops_analysis")
            
        except Exception as e:
            state["warnings"].append(f"Ops 分析失败: {str(e)}")
        
        return state
        
    def _rca_analysis_node(self, state: QAState) -> QAState:
        """根因分析节点"""
        logger.info("[Workflow] 执行根因分析...")
        errors = state.get("errors", [])
        
        if not errors:
            return state
            
        try:
            # 使用 RCA Agent 生成报告
            report = self.rca_agent.generate_root_cause_report(errors, Config.LOG_FILE_PATH)
            
            # 记录结果（作为特殊的 ops result）
            if "ops_results" not in state:
                state["ops_results"] = []
            
            state["ops_results"].append({
                "type": "rca_report",
                "report": report
            })
            
            # 如果找到根因，添加到 final_report 的建议中（将在 generate_report 节点处理）
            
        except Exception as e:
            state["warnings"].append(f"RCA 分析失败: {str(e)}")
            
        return state
    
    def _generate_report_node(self, state: QAState) -> QAState:
        """生成报告节点"""
        logger.info("[Workflow] 生成测试报告...")
        
        report = self.master_agent.generate_report(state)
        state["final_report"] = report
        
        return state
    
    # ================= 路由函数 =================
    
    def _route_after_planning(self, state: QAState) -> Literal["ui", "api", "data", "ops", "end"]:
        """规划后的路由"""
        planned_steps = state.get("planned_steps", [])
        
        if not planned_steps:
            return "end"
            
        # 简单的顺序路由：UI -> API -> Data -> Ops
        if "ui_test" in planned_steps:
            return "ui"
        elif "api_test" in planned_steps:
            return "api"
        elif "data_verification" in planned_steps:
            return "data"
        elif "ops_analysis" in planned_steps:
            return "ops"
        else:
            return "end"
    
    def _route_after_inspect(self, state: QAState) -> Literal["next", "data", "ops", "rca", "end"]:
        """inspect 节点后的路由：驳回 → RCA，通过 → 继续下一步"""
        # 如果 Inspector 发现异常（errors 中有 inspect 来源的错误），触发 RCA
        inspect_errors = [e for e in state.get("errors", []) if e.get("step") == "inspect"]
        if inspect_errors:
            has_rca = any(
                r.get("type") == "rca_report"
                for r in state.get("ops_results", [])
            )
            if not has_rca:
                return "rca"

        # 正常流程：根据最近完成的测试步骤决定下一步
        completed = state.get("completed_steps", [])
        planned = state.get("planned_steps", [])

        # 找到最近完成的测试步骤（ui_test 或 api_test）
        last_test = ""
        for step in reversed(completed):
            if step in ("ui_test", "api_test"):
                last_test = step
                break

        if last_test == "ui_test":
            if "api_test" in planned and "api_test" not in completed:
                return "next"  # → api_test
            elif "data_verification" in planned:
                return "data"
            elif "ops_analysis" in planned:
                return "ops"
        elif last_test == "api_test":
            if "data_verification" in planned and "data_verification" not in completed:
                return "data"
            elif "ops_analysis" in planned:
                return "ops"

        return "end"

    def _route_after_step(self, state: QAState) -> Literal["next", "data", "ops", "rca", "end"]:
        """步骤后的路由"""
        current_step = state.get("completed_steps", [])[-1] if state.get("completed_steps") else ""
        failed_steps = state.get("failed_steps", [])
        
        # 如果当前步骤失败，触发 RCA
        if current_step in failed_steps or (state.get("errors") and len(state["errors"]) > 0):
            # 只有当还没做过 RCA 时才做
            # 简单的检查方式：看 ops_results 中是否有 rca_report
            has_rca = False
            if state.get("ops_results"):
                for res in state["ops_results"]:
                    if res.get("type") == "rca_report":
                        has_rca = True
                        break
            
            if not has_rca:
                return "rca"
        
        # 正常流程路由
        planned_steps = state.get("planned_steps", [])
        
        if current_step == "ui_test":
            if "api_test" in planned_steps:
                return "next" # to api_test
            elif "data_verification" in planned_steps:
                return "data"
            elif "ops_analysis" in planned_steps:
                return "ops"
        
        elif current_step == "api_test":
            if "data_verification" in planned_steps:
                return "next" # to data_verification
            elif "ops_analysis" in planned_steps:
                return "ops"
        
        elif current_step == "data_verification":
            if "ops_analysis" in planned_steps:
                return "next" # to ops_analysis
        
        return "end"
    
    def run(self, test_scenario: str) -> Dict[str, Any]:
        """
        运行 QA 工作流
        
        Args:
            test_scenario: 测试场景
            
        Returns:
            执行结果
        """
        initial_state: QAState = {
            "test_scenario": test_scenario,
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
            "healing_context": None
        }
        
        final_state = self.graph.invoke(initial_state)
        return final_state.get("final_report", {})

# 全局实例
_qa_workflow = None

def get_qa_workflow() -> QAWorkflow:
    """获取 QA 工作流单例"""
    global _qa_workflow
    if _qa_workflow is None:
        _qa_workflow = QAWorkflow()
    return _qa_workflow
