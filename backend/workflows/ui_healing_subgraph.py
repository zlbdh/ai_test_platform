"""
UI 自愈子图 - LangGraph 子图
当 UI 操作失败时，自动尝试修复
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
# 方案 3: 视觉自愈系统 (Visual Self-Healing System) - SoM Hybrid 实现
# =============================================================================
# 核心原理:
# 当常规的 DOM 选择器 (Selector) 失效导致操作失败时，激活此"自愈子图"。
# 它采用 "DOM 为主，视觉为辅" 的混合策略：
# 1. Capture: 捕获当前页面的"视觉快照"(截图)和"结构快照"(DOM)。
# 2. Analyze: 利用视觉大模型 (VLM) 像人类一样"看"图，定位目标元素。
# 3. Map: 将视觉定位结果映射回代码可执行的新选择器。
# 4. Retry: 使用新选择器重试操作。
# =============================================================================


class HealingState(TypedDict):
    """自愈状态"""
    failed_action: Annotated[dict, "失败的操作"]
    original_selector: Annotated[str, "原始选择器"]
    url: Annotated[str, "页面 URL"]
    screenshot_path: Annotated[str, "截图路径"]
    dom_structure: Annotated[dict, "DOM 结构"]
    analysis_result: Annotated[dict, "LLM 分析结果"]
    new_selector: Annotated[str, "新的选择器"]
    retry_result: Annotated[dict, "重试结果"]
    healing_attempts: Annotated[int, "自愈尝试次数"]
    max_attempts: Annotated[int, "最大尝试次数"]
    session_id: Annotated[str, "会话ID"]


class UIHealingSubgraph:
    """UI 自愈子图"""
    
    def __init__(self):
        """初始化自愈子图"""
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """
        构建自愈工作流图 (DAG)
        
        工作流节点说明:
        1. capture_context:       [感知] 获取截图和 DOM，为分析做准备。
        2. analyze_with_llm:      [认知] VLM 视觉分析，寻找元素 (SoM 视觉定位)。
        3. generate_new_selector: [决策] 将视觉结果翻译为 Playwright 选择器。
        4. retry_action:          [行动] 执行修复后的操作。
        """
        workflow = StateGraph(HealingState)
        
        # 添加节点
        workflow.add_node("capture_context", self._capture_context_node)
        workflow.add_node("analyze_with_llm", self._analyze_with_llm_node)
        workflow.add_node("generate_new_selector", self._generate_new_selector_node)
        workflow.add_node("retry_action", self._retry_action_node)
        
        # 设置入口点
        workflow.set_entry_point("capture_context")
        
        # 添加边
        workflow.add_edge("capture_context", "analyze_with_llm")
        workflow.add_edge("analyze_with_llm", "generate_new_selector")
        
        # 条件边：根据重试结果决定是否继续
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
        [节点 1] 捕获上下文 (Context Capture)
        
        这是自愈的第一步。为了让 AI "看懂" 发生了什么，我们需要采集多模态数据：
        1. 视觉数据 (Screenshot): 包含页面布局、颜色、遮挡关系等 DOM 无法体现的信息。
        2. 结构数据 (DOM Snapshot): 包含页面标签、属性、文本等代码层面的信息。
        
        这两种数据将共同构成 "SoM (Set-of-Mark)" 分析的基础。
        """
        logger.info("[自愈] 捕获页面上下文...")
        
        url = state.get("url", "")
        os.makedirs(Config.SCREENSHOT_DIR, exist_ok=True)
        
        # 截图 (传入 session_id)
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
        logger.info("[自愈] 捕获页面上下文...")
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
            logger.warning(f"[自愈] 上下文捕获失败: {e}")

        # 初始化尝试次数
        if "healing_attempts" not in state:
            state["healing_attempts"] = 0
        if "max_attempts" not in state:
            state["max_attempts"] = 3
        
        return state

    async def _analyze_with_llm_node(self, state: HealingState) -> HealingState:
        logger.info("[自愈] 使用 LLM 分析页面...")
        failed_action = state.get("failed_action", {})
        original_selector = state.get("original_selector", "")
        screenshot_path = state.get("screenshot_path", "")
        
        question = f"""
原始选择器 '{original_selector}' 失败了。
失败的操作：{failed_action.get('action', 'unknown')}
请分析页面，找到相似的元素。
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
        logger.info("[自愈] 生成新的选择器...")
        analysis = state.get("analysis_result", {})
        dom_structure = state.get("dom_structure", {})
        original_selector = state.get("original_selector", "")
        
        analysis_text = str(analysis.get("analysis", ""))
        
        # 尝试从 DOM 结构中找到相似元素
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
        logger.info(f"[自愈] 使用新选择器重试: {state.get('new_selector')}")
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
                result = {"status": "error", "error": f"不支持的操作类型: {action_type}"}
            
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


# 全局实例
_healing_subgraph = None

def get_healing_subgraph() -> UIHealingSubgraph:
    """获取自愈子图单例"""
    global _healing_subgraph
    if _healing_subgraph is None:
        _healing_subgraph = UIHealingSubgraph()
    return _healing_subgraph
