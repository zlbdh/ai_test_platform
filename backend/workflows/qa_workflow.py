"""
QA workflow - main LangGraph flow
Coordinate agents to execute testing tasks
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
    """QA platform workflow"""
    
    def __init__(self):
        """Initialize the QA workflow"""
        # Initialize agents
        self.master_agent = MasterAgent()
        self.ui_agent = UIAgent()
        self.api_agent = APIAgent()
        self.data_agent = DataAgent()
        self.ops_agent = OpsAgent()
        self.rca_agent = RCAAgent()
        self.inspector = InspectorAgent()
        
        # Initialize the graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph"""
        workflow = StateGraph(QAState)
        
        # Add nodes
        workflow.add_node("plan_test", self._plan_test_node)
        workflow.add_node("ui_test", self._ui_test_node)
        workflow.add_node("api_test", self._api_test_node)
        workflow.add_node("inspect", self._inspect_node)
        workflow.add_node("data_verification", self._data_verification_node)
        workflow.add_node("ops_analysis", self._ops_analysis_node)
        workflow.add_node("rca_analysis", self._rca_analysis_node)
        workflow.add_node("generate_report", self._generate_report_node)

        # Set the entry point
        workflow.set_entry_point("plan_test")

        # Add edges with dynamic routing based on the plan
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

        # Review completed ui_test / api_test results in the inspect node
        workflow.add_edge("ui_test", "inspect")
        workflow.add_edge("api_test", "inspect")

        # Route after the inspect node based on the review result
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
    
    # ================= Node functions =================
    
    def _plan_test_node(self, state: QAState) -> QAState:
        """Test planning node"""
        logger.info("[Workflow] Planning the test task...")
        scenario = state.get("test_scenario", "")
        
        # Call the Master Agent to plan the task
        plan = self.master_agent.plan_test(scenario)
        
        # Update state
        state["task_description"] = plan.get("plan_text", "")
        state["current_step"] = "planning"
        
        # Determine execution order
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
        
        # Save planned steps for routing
        # Note: this uses a temporary metadata field that should be added to the State definition
        state["planned_steps"] = steps  # Add this field to QAState or use a safe get
        
        return state
    
    def _ui_test_node(self, state: QAState) -> QAState:
        """UI testing node"""
        logger.info("[Workflow] Run UI tests...")
        scenario = state.get("test_scenario", "")
        
        try:
            # Call the UI Agent
            # Call process_request, which handles task decomposition and execution internally
            # Note: the actual call may need adjustment to match the UIAgent interface
            result = self.ui_agent.run(state)
            
            # Record results
            if "ui_results" not in state:
                state["ui_results"] = []
            
            # Depending on the UIAgent implementation, result may contain the entire state or a partial result
            # Assume UIAgent.run updates and returns state
            
            if state.get("ui_results") and any(r.get("status") == "error" for r in state["ui_results"]):
                state["errors"].append({"step": "ui_test", "error": "UI tests contain failed steps"})
            
            state["completed_steps"].append("ui_test")
            
        except Exception as e:
            state["errors"].append({"step": "ui_test", "error": str(e)})
            state["failed_steps"].append("ui_test")
        
        return state
    
    def _api_test_node(self, state: QAState) -> QAState:
        """API testing node"""
        logger.info("[Workflow] Run API tests...")
        scenario = state.get("test_scenario", "")
        
        try:
            # Call the API Agent
            result = self.api_agent.execute_test(scenario)
            
            # Record results
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
        """Inspector visual quality node — review screenshots from ui_test/api_test execution"""
        logger.info("[Workflow] Inspector visual quality review...")

        if "inspection_results" not in state:
            state["inspection_results"] = []

        # Collect screenshots from the latest round of tests
        results_to_inspect = []
        for r in state.get("ui_results", []):
            if isinstance(r, dict) and r.get("screenshot"):
                results_to_inspect.append(r)
        for r in state.get("api_results", []):
            if isinstance(r, dict) and r.get("screenshot"):
                results_to_inspect.append(r)

        if not results_to_inspect:
            logger.info("[Workflow] Inspector: No screenshots to review; skipping")
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
                    error_msg = f"Inspector rejected: {inspection.reason}"
                    if inspection.anomalies:
                        error_msg += f" | Anomalies: {', '.join(inspection.anomalies)}"
                    state["errors"].append({"step": "inspect", "error": error_msg})
                    logger.warning(f"[Workflow] {error_msg}")

            except Exception as e:
                logger.warning(f"[Workflow] Inspector review error (auto-passing): {e}")
                state["inspection_results"].append({
                    "step": result.get("step_desc", "unknown"),
                    "passed": True,
                    "confidence": 0.0,
                    "reason": f"Inspector error: {e}",
                    "anomalies": [],
                })

        return state

    def _data_verification_node(self, state: QAState) -> QAState:
        """Data validation node"""
        logger.info("[Workflow] Run data validation...")
        scenario = state.get("test_scenario", "")
        
        try:
            # Call the Data Agent
            result = self.data_agent.execute_test(scenario)
            
            # Record results
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
        """Operations analysis node"""
        logger.info("[Workflow] Run operations analysis...")
        
        # Run Ops analysis only when errors exist or it is explicitly requested
        if not state.get("errors") and "ops_analysis" not in state.get("planned_steps", []):
            return state
            
        try:
            # Collect previous errors
            errors = state.get("errors", [])
            log_path = Config.LOG_FILE_PATH
            
            results = []
            for error in errors:
                diagnosis = self.ops_agent.diagnose_error(str(error.get("error", "")), log_path)
                results.append(diagnosis)
            
            # If analysis is requested without explicit errors, analyze the latest logs
            if not errors:
                analysis = self.ops_agent.analyze_logs(log_path)
                results.append(analysis)
            
            # Record results
            if "ops_results" not in state:
                state["ops_results"] = []
            state["ops_results"].extend(results)
            
            state["completed_steps"].append("ops_analysis")
            
        except Exception as e:
            state["warnings"].append(f"Ops analysis failed: {str(e)}")
        
        return state
        
    def _rca_analysis_node(self, state: QAState) -> QAState:
        """Root cause analysis node"""
        logger.info("[Workflow] Run root cause analysis...")
        errors = state.get("errors", [])
        
        if not errors:
            return state
            
        try:
            # Use the RCA Agent to generate a report
            report = self.rca_agent.generate_root_cause_report(errors, Config.LOG_FILE_PATH)
            
            # Record the result as a special ops result
            if "ops_results" not in state:
                state["ops_results"] = []
            
            state["ops_results"].append({
                "type": "rca_report",
                "report": report
            })
            
            # If a root cause is found, add it to final_report recommendations in the generate_report node
            
        except Exception as e:
            state["warnings"].append(f"RCA analysis failed: {str(e)}")
            
        return state
    
    def _generate_report_node(self, state: QAState) -> QAState:
        """Report generation node"""
        logger.info("[Workflow] Generate the test report...")
        
        report = self.master_agent.generate_report(state)
        state["final_report"] = report
        
        return state
    
    # ================= Routing functions =================
    
    def _route_after_planning(self, state: QAState) -> Literal["ui", "api", "data", "ops", "end"]:
        """Route after planning"""
        planned_steps = state.get("planned_steps", [])
        
        if not planned_steps:
            return "end"
            
        # Simple sequential routing: UI -> API -> Data -> Ops
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
        """Route after inspection: rejection → RCA; approval → next step"""
        # Trigger RCA if Inspector detects anomalies (errors contains an inspect error)
        inspect_errors = [e for e in state.get("errors", []) if e.get("step") == "inspect"]
        if inspect_errors:
            has_rca = any(
                r.get("type") == "rca_report"
                for r in state.get("ops_results", [])
            )
            if not has_rca:
                return "rca"

        # Normal flow: choose the next step based on the most recently completed test step
        completed = state.get("completed_steps", [])
        planned = state.get("planned_steps", [])

        # Find the most recently completed test step (ui_test or api_test)
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
        """Route after a step"""
        current_step = state.get("completed_steps", [])[-1] if state.get("completed_steps") else ""
        failed_steps = state.get("failed_steps", [])
        
        # Trigger RCA if the current step failed
        if current_step in failed_steps or (state.get("errors") and len(state["errors"]) > 0):
            # Run RCA only if it has not already run
            # Simple check: look for rca_report in ops_results
            has_rca = False
            if state.get("ops_results"):
                for res in state["ops_results"]:
                    if res.get("type") == "rca_report":
                        has_rca = True
                        break
            
            if not has_rca:
                return "rca"
        
        # Normal flow routing
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
        Run the QA workflow
        
        Args:
            test_scenario: Test scenario
            
        Returns:
            Execution result
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

# Global instance
_qa_workflow = None

def get_qa_workflow() -> QAWorkflow:
    """Get the QA workflow singleton"""
    global _qa_workflow
    if _qa_workflow is None:
        _qa_workflow = QAWorkflow()
    return _qa_workflow
