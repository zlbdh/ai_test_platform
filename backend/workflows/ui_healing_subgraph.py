"""
UI healing subgraph - LangGraph subgraph
Automatically attempt recovery when a UI action fails
"""
import logging
from typing import TypedDict, Annotated, Literal

logger = logging.getLogger(__name__)
from langgraph.graph import StateGraph, END
from skills.vision_tools import analyze_screenshot, find_element_by_description
from skills.ui_tools import extract_dom_structure, take_screenshot, get_dom_snapshot
from core.config import Config
import os

# =============================================================================
# Approach 3: Visual Self-Healing System - SoM hybrid implementation
# =============================================================================
# Core principles:
# Activate this healing subgraph when an invalid conventional DOM selector causes an action to fail.
# It uses a hybrid strategy that prioritizes the DOM and supplements it with vision:
# 1. Capture: Capture the current page's visual snapshot (screenshot) and structural snapshot (DOM).
# 2. Analyze: Use a vision-language model (VLM) to examine the image and locate the target element.
# 3. Map: Map the visual location to a new selector that code can execute.
# 4. Retry: Retry the action with the new selector.
# =============================================================================


class HealingState(TypedDict):
    """Healing state"""
    failed_action: Annotated[dict, "Failed action"]
    original_selector: Annotated[str, "Original selector"]
    url: Annotated[str, "Page URL"]
    screenshot_path: Annotated[str, "Screenshot path"]
    dom_structure: Annotated[dict, "DOM structure"]
    analysis_result: Annotated[dict, "LLM analysis result"]
    new_selector: Annotated[str, "New selector"]
    retry_result: Annotated[dict, "Retry result"]
    healing_attempts: Annotated[int, "Healing attempt count"]
    max_attempts: Annotated[int, "Maximum attempts"]
    session_id: Annotated[str, "Session ID"]


class UIHealingSubgraph:
    """UI healing subgraph"""
    
    def __init__(self):
        """Initialize the healing subgraph"""
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """
        Build the healing workflow graph (DAG)
        
        Workflow nodes:
        1. capture_context:       [Perception] Capture a screenshot and DOM for analysis.
        2. analyze_with_llm:      [Reasoning] Use VLM visual analysis to locate elements (SoM visual localization).
        3. generate_new_selector: [Decision] Convert the visual result into a Playwright selector.
        4. retry_action:          [Action] Execute the repaired action.
        """
        workflow = StateGraph(HealingState)
        
        # Add nodes
        workflow.add_node("capture_context", self._capture_context_node)
        workflow.add_node("analyze_with_llm", self._analyze_with_llm_node)
        workflow.add_node("generate_new_selector", self._generate_new_selector_node)
        workflow.add_node("retry_action", self._retry_action_node)
        
        # Set the entry point
        workflow.set_entry_point("capture_context")
        
        # Add edges
        workflow.add_edge("capture_context", "analyze_with_llm")
        workflow.add_edge("analyze_with_llm", "generate_new_selector")
        
        # Conditional edges: decide whether to continue based on the retry result
        workflow.add_conditional_edges(
            "generate_new_selector",
            self._should_retry,
            {
                "retry": "retry_action",
                "give_up": END
            }
        )
        
        workflow.add_conditional_edges(
            "retry_action",
            self._should_continue,
            {
                "success": END,
                "retry_again": "analyze_with_llm",
                "give_up": END
            }
        )
        
        workflow.compile()
        return workflow.compile()
    
    def _capture_context_node(self, state: HealingState) -> HealingState:
        """
        [Node 1] Context capture
        
        This is the first healing step. Collect multimodal data so the AI can understand what happened:
        1. Visual data (screenshot): page layout, colors, occlusion, and other information the DOM cannot capture.
        2. Structural data (DOM snapshot): tags, attributes, text, and other code-level information.
        
        Together, these two data sources form the basis of SoM (Set-of-Mark) analysis.
        """
        logger.info("[Healing] Capture page context...")
        
        url = state.get("url", "")
        os.makedirs(Config.SCREENSHOT_DIR, exist_ok=True)
        
        # Take a screenshot with session_id
        session_id = state.get("session_id")
        # take_screenshot tool usage: await take_screenshot.ainvoke(...)
        # But here we are in a synchronous graph node? LangGraph nodes can be sync or async.
        # If we use sync graph runner, we need sync tools. The tools defined are async.
        # We might need to run this graph asynchronously.
        
        # TEMPORARY FIX: using ad-hoc sync execution or assuming this graph will be run via ainvoke.
        # For now, let's assume we can call invoke if tool supports it, OR we need the agent to be async.
        # Since logic in UiAgent is async, we should use async methods if possible.
        # But this class method structure suggests sync. 
        # Let's import the async runner or use ainvoke for tools if we are in async context.
        # Wait, the tools are defined as @tool which wraps them. invoke() is sync, ainvoke() is async.
        # If I call .invoke() on an async tool, LangChain might error or run it in a loop?
        # Actually our tools in ui_tools.py are async functions decorated with @tool.
        # Standard LangChain tools are run via invoke/ainvoke.
        
        # Let's switch to async def for nodes to be safe and use await.
        # But StateGraph needs to know if it's async. 
        # If I define nodes as async def, StateGraph handles it? Yes.
        # I need to change these methods to async def.
        return state # Placeholder for async conversion below
    
    # Redefining methods as async for proper tool usage
    async def _capture_context_node(self, state: HealingState) -> HealingState:
        logger.info("[Healing] Capture page context...")
        url = state.get("url", "")
        os.makedirs(Config.SCREENSHOT_DIR, exist_ok=True)
        
        session_id = state.get("session_id")
        
        try:
            screenshot_result = await take_screenshot.ainvoke({"session_id": session_id})
            # extract path
            res_data = screenshot_result.get("result", {})
            screenshot_path = res_data.get("path") if isinstance(res_data, dict) else ""
            state["screenshot_path"] = screenshot_path
            
            dom_info = await get_dom_snapshot.ainvoke({"session_id": session_id})
            state["dom_structure"] = dom_info
        except Exception as e:
            logger.warning(f"[Healing] Context capture failed: {e}")

        # Initialize the attempt count
        if "healing_attempts" not in state:
            state["healing_attempts"] = 0
        if "max_attempts" not in state:
            state["max_attempts"] = 3
        
        return state

    async def _analyze_with_llm_node(self, state: HealingState) -> HealingState:
        logger.info("[Healing] Analyze the page with the LLM...")
        failed_action = state.get("failed_action", {})
        original_selector = state.get("original_selector", "")
        screenshot_path = state.get("screenshot_path", "")
        
        question = f"""
The original selector '{original_selector}' failed.
Failed action: {failed_action.get('action', 'unknown')}
Analyze the page and find a similar element.
"""
        # analyze_screenshot is sync in vision_tools.py?
        # Let's check vision_tools.py. It is defined as `def analyze_screenshot`.
        # So we can call .invoke()
        analysis = analyze_screenshot.invoke({
            "screenshot_path": screenshot_path,
            "question": question
        })
        
        state["analysis_result"] = analysis
        state["healing_attempts"] = state.get("healing_attempts", 0) + 1
        return state

    async def _generate_new_selector_node(self, state: HealingState) -> HealingState:
        logger.info("[Healing] Generate a new selector...")
        analysis = state.get("analysis_result", {})
        dom_structure = state.get("dom_structure", {})
        original_selector = state.get("original_selector", "")
        
        analysis_text = str(analysis.get("analysis", ""))
        
        # Try to find a similar element in the DOM structure
        elements = dom_structure.get("elements", [])
        
        new_selector = None
        if elements:
            for element in elements:
                element_text = element.get("text", "").lower()
                element_selector = element.get("selector", "")
                
                if original_selector.lower() in element_text or element_text in original_selector.lower():
                    new_selector = element_selector or f"text={element.get('text', '')}"
                    break
        
        if not new_selector:
            if "button" in analysis_text.lower():
                new_selector = "button"
            elif "input" in analysis_text.lower():
                new_selector = "input"
            else:
                new_selector = original_selector.replace("#", "").replace(".", "") 
        
        state["new_selector"] = new_selector
        return state

    async def _retry_action_node(self, state: HealingState) -> HealingState:
        logger.info(f"[Healing] Retry with the new selector: {state.get('new_selector')}")
        failed_action = state.get("failed_action", {})
        new_selector = state.get("new_selector", "")
        url = state.get("url", "")
        session_id = state.get("session_id")
        
        action_type = failed_action.get("action", "click")
        
        try:
            from skills.ui_tools import click_element, fill_input
            
            if action_type == "click":
                result = await click_element.ainvoke({
                    "selector": new_selector,
                    "session_id": session_id
                })
            elif action_type == "fill":
                result = await fill_input.ainvoke({
                    "selector": new_selector,
                    "text": failed_action.get("text", failed_action.get("value", "")),
                    "session_id": session_id
                })
            else:
                result = {"status": "error", "error": f"Unsupported action type: {action_type}"}
            
            state["retry_result"] = result
            
        except Exception as e:
            state["retry_result"] = {"status": "error", "error": str(e)}
        
        return state

    def _should_retry(self, state: HealingState) -> Literal["retry", "give_up"]:
        attempts = state.get("healing_attempts", 0)
        max_attempts = state.get("max_attempts", 3)
        if attempts < max_attempts and state.get("new_selector"):
            return "retry"
        return "give_up"
    
    def _should_continue(self, state: HealingState) -> Literal["success", "retry_again", "give_up"]:
        retry_result = state.get("retry_result", {})
        if retry_result.get("success") == True or retry_result.get("status") == "success":
            return "success"
        
        attempts = state.get("healing_attempts", 0)
        max_attempts = state.get("max_attempts", 3)
        if attempts < max_attempts:
            return "retry_again"
        return "give_up"

    async def run(self, failed_action: dict, original_selector: str, url: str, session_id: str = None) -> dict:
        initial_state: HealingState = {
            "failed_action": failed_action,
            "original_selector": original_selector,
            "url": url,
            "session_id": session_id,
            "screenshot_path": "",
            "dom_structure": {},
            "analysis_result": {},
            "new_selector": "",
            "retry_result": {},
            "healing_attempts": 0,
            "max_attempts": 3
        }
        
        final_state = await self.graph.ainvoke(initial_state)
        
        retry_res = final_state.get("retry_result", {})
        healed = retry_res.get("success") == True or retry_res.get("status") == "success"
        
        return {
            "healed": healed,
            "new_selector": final_state.get("new_selector", ""),
            "retry_result": retry_res,
            "attempts": final_state.get("healing_attempts", 0)
        }


# Global instance
_healing_subgraph = None

def get_healing_subgraph() -> UIHealingSubgraph:
    """Get the healing subgraph singleton"""
    global _healing_subgraph
    if _healing_subgraph is None:
        _healing_subgraph = UIHealingSubgraph()
    return _healing_subgraph
