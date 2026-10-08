"""
API fuzzing subgraph - LangGraph subgraph
Automatically generate attack payloads and continue testing until a vulnerability is found
"""
import logging
from typing import TypedDict, Annotated, Literal

logger = logging.getLogger(__name__)
from langgraph.graph import StateGraph, END
from skills.api_tools import call_api, generate_test_data
from skills.schemathesis_integration import fuzz_with_schemathesis


class FuzzingState(TypedDict):
    """Fuzzing state"""
    endpoint: Annotated[str, "API endpoint"]
    method: Annotated[str, "HTTP method"]
    base_params: Annotated[dict, "Base parameters"]
    attack_payloads: Annotated[list, "Attack payload list"]
    current_payload_index: Annotated[int, "Current payload index"]
    test_results: Annotated[list, "Test result list"]
    vulnerabilities: Annotated[list, "Discovered vulnerability list"]
    max_iterations: Annotated[int, "Maximum iterations"]
    current_iteration: Annotated[int, "Current iteration"]


class APIFuzzingSubgraph:
    """API fuzzing subgraph"""
    
    def __init__(self):
        """Initialize the fuzzing subgraph"""
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the fuzzing subgraph"""
        workflow = StateGraph(FuzzingState)
        
        # Add nodes
        workflow.add_node("generate_payloads", self._generate_payloads_node)
        workflow.add_node("execute_attack", self._execute_attack_node)
        workflow.add_node("analyze_response", self._analyze_response_node)
        workflow.add_node("record_vulnerability", self._record_vulnerability_node)
        
        # Set the entry point
        workflow.set_entry_point("generate_payloads")
        
        # Add edges
        workflow.add_edge("generate_payloads", "execute_attack")
        workflow.add_edge("execute_attack", "analyze_response")
        
        # Conditional edges: choose the next step based on response analysis
        workflow.add_conditional_edges(
            "analyze_response",
            self._should_record_vulnerability,
            {
                "record": "record_vulnerability",
                "continue": "execute_attack",
                "end": END
            }
        )
        
        workflow.add_conditional_edges(
            "record_vulnerability",
            self._should_continue_attacking,
            {
                "continue": "execute_attack",
                "end": END
            }
        )
        
        return workflow.compile()
    
    def _generate_payloads_node(self, state: FuzzingState) -> FuzzingState:
        """Attack payload generation node"""
        logger.info("[Fuzzing] Generate attack payloads...")
        
        # Generate different types of attack payloads
        payload_types = ["sql_injection", "xss", "number", "string"]
        attack_payloads = []
        
        for payload_type in payload_types:
            test_data = generate_test_data.invoke({
                "data_type": payload_type,
                "count": 2,
                "include_boundary": True
            })
            
            for item in test_data:
                if item.get("type") in ["attack", "boundary", "invalid"]:
                    attack_payloads.append({
                        "type": payload_type,
                        "value": item.get("value"),
                        "payload_type": item.get("type")
                    })
        
        # Add more attack payloads
        attack_payloads.extend([
            {"type": "command_injection", "value": "; ls -la", "payload_type": "attack"},
            {"type": "path_traversal", "value": "../../../etc/passwd", "payload_type": "attack"},
            {"type": "null_byte", "value": "\x00", "payload_type": "attack"},
            {"type": "overflow", "value": "A" * 10000, "payload_type": "attack"},
            {"type": "json_injection", "value": '{"__proto__": {"isAdmin": true}}', "payload_type": "attack"},
        ])
        
        state["attack_payloads"] = attack_payloads
        state["current_payload_index"] = 0
        state["test_results"] = []
        state["vulnerabilities"] = []
        state["current_iteration"] = 0
        
        if "max_iterations" not in state:
            state["max_iterations"] = len(attack_payloads)
        
        return state
    
    def _execute_attack_node(self, state: FuzzingState) -> FuzzingState:
        """Attack execution node"""
        payloads = state.get("attack_payloads", [])
        current_index = state.get("current_payload_index", 0)
        
        if current_index >= len(payloads):
            return state
        
        payload = payloads[current_index]
        endpoint = state.get("endpoint", "")
        method = state.get("method", "POST")
        base_params = state.get("base_params", {})
        
        logger.info(f"[Fuzzing] Test payload {current_index + 1}/{len(payloads)}: {payload.get('type')}")
        
        # Build test parameters
        test_params = {**base_params}
        
        # Inject the attack payload into each parameter
        for key in test_params.keys():
            test_params[key] = payload.get("value")
        
        # Call the API
        try:
            response = call_api.invoke({
                "method": method,
                "endpoint": endpoint,
                "body": test_params if method in ["POST", "PUT", "PATCH"] else None,
                "params": test_params if method == "GET" else None
            })
            
            state["test_results"].append({
                "payload": payload,
                "response": response,
                "iteration": state.get("current_iteration", 0)
            })
        except Exception as e:
            state["test_results"].append({
                "payload": payload,
                "error": str(e),
                "iteration": state.get("current_iteration", 0)
            })
        
        state["current_payload_index"] = current_index + 1
        state["current_iteration"] = state.get("current_iteration", 0) + 1
        
        return state
    
    def _analyze_response_node(self, state: FuzzingState) -> FuzzingState:
        """Response analysis node"""
        if not state.get("test_results"):
            return state
        
        last_result = state["test_results"][-1]
        response = last_result.get("response", {})
        payload = last_result.get("payload", {})
        
        status_code = response.get("status_code", 0)
        response_body = str(response.get("body", ""))
        
        # Determine whether a vulnerability was found
        is_vulnerable = False
        vulnerability_type = None
        
        # Check for 500 errors
        if status_code >= 500:
            is_vulnerable = True
            vulnerability_type = "server_error"
        
        # Check for signs of SQL injection
        elif payload.get("type") == "sql_injection":
            sql_errors = ["sql syntax", "mysql", "postgresql", "database", "sql error"]
            if any(error in response_body.lower() for error in sql_errors):
                is_vulnerable = True
                vulnerability_type = "sql_injection"
        
        # Check for signs of XSS
        elif payload.get("type") == "xss":
            if payload.get("value") in response_body:
                is_vulnerable = True
                vulnerability_type = "xss"
        
        # Check for command injection
        elif payload.get("type") == "command_injection":
            if status_code != 200 or "error" in response_body.lower():
                is_vulnerable = True
                vulnerability_type = "command_injection"
        
        if is_vulnerable:
            state["vulnerabilities"].append({
                "type": vulnerability_type,
                "payload": payload,
                "response": response,
                "severity": "high" if status_code >= 500 else "medium"
            })
        
        return state
    
    def _record_vulnerability_node(self, state: FuzzingState) -> FuzzingState:
        """Vulnerability recording node"""
        vulnerabilities = state.get("vulnerabilities", [])
        if vulnerabilities:
            last_vuln = vulnerabilities[-1]
            logger.warning(f"[Fuzzing] Vulnerability found: {last_vuln.get('type')} (Severity: {last_vuln.get('severity')})")
        
        return state
    
    def _should_record_vulnerability(self, state: FuzzingState) -> Literal["record", "continue", "end"]:
        """Determine whether to record a vulnerability"""
        vulnerabilities = state.get("vulnerabilities", [])
        if vulnerabilities and len(vulnerabilities) > len(state.get("test_results", [])) - 1:
            return "record"
        
        current_iteration = state.get("current_iteration", 0)
        max_iterations = state.get("max_iterations", 50)
        
        if current_iteration >= max_iterations:
            return "end"
        
        current_index = state.get("current_payload_index", 0)
        payloads = state.get("attack_payloads", [])
        
        if current_index >= len(payloads):
            return "end"
        
        return "continue"
    
    def _should_continue_attacking(self, state: FuzzingState) -> Literal["continue", "end"]:
        """Determine whether to continue testing attacks"""
        current_iteration = state.get("current_iteration", 0)
        max_iterations = state.get("max_iterations", 50)
        
        if current_iteration >= max_iterations:
            return "end"
        
        current_index = state.get("current_payload_index", 0)
        payloads = state.get("attack_payloads", [])
        
        if current_index >= len(payloads):
            return "end"
        
        return "continue"
    
    def run(self, endpoint: str, method: str = "POST", base_params: dict = None, max_iterations: int = 50) -> dict:
        """
        Run fuzz testing
        
        Args:
            endpoint: API endpoint
            method: HTTP method
            base_params: Base parameters
            max_iterations: Maximum iterations
            
        Returns:
            Fuzz testing results
        """
        initial_state: FuzzingState = {
            "endpoint": endpoint,
            "method": method,
            "base_params": base_params or {},
            "attack_payloads": [],
            "current_payload_index": 0,
            "test_results": [],
            "vulnerabilities": [],
            "max_iterations": max_iterations,
            "current_iteration": 0
        }
        
        final_state = self.graph.invoke(initial_state)
        
        return {
            "endpoint": endpoint,
            "method": method,
            "total_tests": len(final_state.get("test_results", [])),
            "vulnerabilities_found": len(final_state.get("vulnerabilities", [])),
            "vulnerabilities": final_state.get("vulnerabilities", []),
            "test_results": final_state.get("test_results", [])
        }


# Global instance
_fuzzing_subgraph = None

def get_fuzzing_subgraph() -> APIFuzzingSubgraph:
    """Get the fuzzing subgraph singleton"""
    global _fuzzing_subgraph
    if _fuzzing_subgraph is None:
        _fuzzing_subgraph = APIFuzzingSubgraph()
    return _fuzzing_subgraph
