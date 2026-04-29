import asyncio
import logging
from typing import Dict
from agents.state import EngineState, TestStep
from agents.judge import semantic_judge
from agents.healer import self_heal
from core.browser import get_clean_html, find_selector, analyze_with_som
from core.visual_tools import assert_visual_snapshot
import traceback
import time

logger = logging.getLogger(__name__)

class ExecutorNode:
    """
    执行 Agent (Executor)
    负责：
    1. 接收单个 Step
    2. 执行动作 (Playwright / API / SQL)
    3. 自愈逻辑 (Self-Correction)
    4. 结果验证 (Judge)
    """

    async def execute_step(self, state: EngineState) -> EngineState:
        idx = state["current_step_index"]
        if idx >= len(state["plan"]):
            return state
            
        step: TestStep = state["plan"][idx]
        logger.info(f"[Executor] Executing Step {idx+1}: {step['action']} -> {step['target']}")
        
        try:
            # 执行逻辑
            result = await self._perform_action(step, state)
            
            # 记录成功日志
            state["logs"].append({
                "type": "success",
                "action": step['action'],
                "content": result
            })
            
            # 步进
            state["current_step_index"] += 1
            state["retry_count"] = 0
            
        except Exception as e:
            logger.warning(f"[Executor] Execution Failed: {e}")
            
            # 自愈尝试
            if state["retry_count"] < 2:
                logger.info("[Executor] Triggering Self-Heal...")
                healed_step = self_heal(step, str(e), get_clean_html())
                if healed_step:
                    logger.info(f"[Executor] Self-Healed Step: {healed_step}")
                    state["plan"][idx] = healed_step
                    state["retry_count"] += 1
                    # Stay on same index to retry
                    return state
            
            # 最终失败
            state["error"] = str(e)
            
        return state

    async def _perform_action(self, step: TestStep, state: EngineState) -> str:
        action = step['action']
        target = step['target']
        val = step['value']

        from skills.react_tools import (
            tool_goto, tool_click, tool_fill, tool_assert,
            tool_api_call, tool_db_query, tool_visual_check
        )

        # 获取当前页面对象
        page = None
        try:
            from core.shared import SharedBrowserState
            page = SharedBrowserState.get_page()
        except Exception:
            pass

        context = state.get("context", {})

        if action == "goto":
            return await tool_goto(page, target, context)
        elif action == "click":
            # 尝试自动定位 selector
            if not step['selector']:
                step['selector'] = await find_selector(target) if target else ""
            return await tool_click(page, step['selector'] or target)
        elif action == "fill":
            if not step['selector']:
                step['selector'] = await find_selector(target) if target else ""
            return await tool_fill(page, step['selector'] or target, val, context)
        elif action == "assert":
            # 使用语义裁判
            page_content = get_clean_html()
            passed = semantic_judge(target, page_content)
            if not passed:
                raise Exception(f"Assertion Failed: {target}")
            return "Assertion Passed"
        elif action == "visual_check":
            if page:
                result = await tool_visual_check(page, target or "default")
                return str(result)
            return "Skipped: No page available for visual check"
        elif action == "api_call":
            method = val.split(" ", 1)[0] if val else "GET"
            return str(await tool_api_call(method, target, val, context))
        elif action == "db_query":
            return str(await tool_db_query(target, context))
        elif action == "wait":
            import asyncio
            await asyncio.sleep(int(val) if val and val.isdigit() else 2)
            return f"Waited {val or 2} seconds"

        return f"Action '{action}' completed"
