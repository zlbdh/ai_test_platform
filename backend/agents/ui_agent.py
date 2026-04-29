# -*- coding: utf-8 -*-
"""
UI Agent - 前端测试 Agent
负责 UI 自动化测试、视觉回归、兼容性测试
"""
from typing import Dict, Any, List
import os
import json
import time
import uuid
import asyncio
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from core.config import Config
from core.llm_manager import get_llm_for_role
from core.prompts import UI_AGENT_SYSTEM_PROMPT
from skills.ui_tools import UI_TOOLS, navigate, take_screenshot, get_interactable_elements
from skills.registry import registry
import logging

logger = logging.getLogger(__name__)


class UIAgent:
    """UI 测试 Agent"""
    
    def __init__(self):
        """初始化 UI Agent"""
        self.llm = get_llm_for_role("executor")
        
        # 创建 Agent Prompt
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", UI_AGENT_SYSTEM_PROMPT),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        self.tools = UI_TOOLS
    
    async def execute_test(self, test_scenario: str, url: str = None) -> Dict[str, Any]:
        """
        执行 UI 测试
        """
        target_url = url or Config.TARGET_URL
        results = {
            "agent": "ui_agent",
            "scenario": test_scenario,
            "url": target_url,
            "actions": [],
            "screenshots": [],
            "status": "pending",
            "errors": []
        }
        
        try:
            return await self._run_autonomous_loop(test_scenario, target_url)
        except Exception as e:
            results["status"] = "error"
            results["errors"].append(str(e))
            return results

    def _format_history(self, actions: List[Dict[str, Any]]) -> str:
        """格式化操作历史"""
        if not actions:
            return "无历史记录"
        
        history_lines = []
        recent_actions = actions[-5:]
        for action in recent_actions:
            step = action.get("step", "?")
            thought = action.get("thought", "No thought")
            tool = action.get("tool", "Unknown")
            args = action.get("args", {})
            args_str = str(args)
            if len(args_str) > 100: args_str = args_str[:100] + "..."
            history_lines.append(f"Step {step}: Thought: {thought}\n  Action: {tool}({args_str})")
        return "\n".join(history_lines)

    def _format_dom_summary(self, dom_info: Dict[str, Any]) -> str:
        """Format the DOM information for the LLM"""
        if dom_info.get("refs"):
             refs = dom_info.get("refs", [])
             summary_lines = ["--- Agent Browser Refs ---"]
             for ref in refs:
                 summary_lines.append(f"{ref.get('index', '')} [{ref.get('tagName', '')}] {ref.get('text', '')}")
             return "\n".join(summary_lines)

        if dom_info.get("status") == "error":
            return f"DOM extraction failed: {dom_info.get('error')}"
        
        elements = dom_info.get("elements", [])
        if not elements:
            return "No interactable elements found."
            
        summary_lines = []
        # Limit to top 50 elements to save tokens
        for i, el in enumerate(elements[:50]):
            tag = el.get("tag")
            text = el.get("text", "").strip().replace('\n', ' ')[:50]
            role = el.get("role", "")
            rect = el.get("rect", {})
            xpath = el.get("xpath")
            
            attrs = f"role='{role}'" if role else ""
            if text: attrs += f" text='{text}'"
            loc = f"[{rect.get('x')},{rect.get('y')},{rect.get('w')},{rect.get('h')}]"
            attrs += f" rect={loc}"
            if xpath: attrs += f" xpath='{xpath}'"
            
            summary_lines.append(f"<{tag} {attrs} />")
            
        return "\n".join(summary_lines)

    async def _run_autonomous_loop(self, step_description: str, start_url: str) -> Dict[str, Any]:
        """
        运行自主测试循环 (Phase 4 - Agent Browser Engine)
        """
        
        # 简单实现 MessageManager
        class MessageManager:
            def __init__(self, system_prompt, max_history_steps=10):
                self.messages = [("system", system_prompt)]
                self.max_history_steps = max_history_steps
            
            def add_state_message(self, screenshot_path, state_desc, vision_enabled=False):
                # 简单实现，暂时忽略 vision_enabled 的多模态构建细节
                self.messages.append(("human", state_desc))
                
            def add_assistant_message(self, thought, action_map):
                self.messages.append(("assistant", f"Thought: {thought}\nAction: {json.dumps(action_map)}"))
                
            def add_tool_result_message(self, result):
                self.messages.append(("human", f"Tool Result: {result}"))
                
            def get_messages(self):
                return self.messages

        logger.info(f"Start Autonomous Loop: {step_description}")
        
        # 初始化
        tool_desc = registry.get_prompt_description()
        # 这里 system_prompt 格式化需要和 self.prompt 配合，暂时手动构建
        system_prompt = self.prompt.format(tool_definitions=tool_desc, input="", agent_scratchpad=[])[0].content
        
        message_manager = MessageManager(system_prompt=system_prompt)
        session_id = str(uuid.uuid4())
        
        # 打开页面
        nav_result = await navigate.ainvoke({"url": start_url, "session_id": session_id})
        logger.info(f"Navigation result: {nav_result}")
        
        results = {
            "step_description": step_description,
            "actions": [],
            "final_status": "success",
            "error": None,
            "screenshots": []
        }
        
        if nav_result.get("success") == False:
            results["final_status"] = "error"
            results["error"] = nav_result.get("error")
            return results
        
        current_url = start_url # update from nav result if possible
        MAX_STEPS = 15
        consecutive_errors = 0
        
        for i in range(MAX_STEPS):
            try:
                timestamp = int(time.time())
                screenshot_result = await take_screenshot.ainvoke({"session_id": session_id})
                res_data = screenshot_result.get("result", {})
                screenshot_path = res_data.get("path") if isinstance(res_data, dict) else ""
                if screenshot_path:
                    results["screenshots"].append(screenshot_path)
                
                dom_result = await get_interactable_elements.ainvoke({"session_id": session_id})
                dom_summary = self._format_dom_summary(dom_result)
                
            except Exception as e:
                logger.error(f"Observation failed: {e}")
                screenshot_path = None
                dom_summary = f"Error: {str(e)}"

            history_sum = self._format_history(results["actions"])
            
            state_desc = f"""
Current Step: {i+1}/{MAX_STEPS}
Goal: {step_description}
URL: {current_url}

Observation:
{dom_summary}

History:
{history_sum}

IMPORTANT: You must return a valid JSON object. Format: {{"thought": "...", "action": {{"tool_name": {{"arg": "val"}}}}}}
"""
            message_manager.add_state_message(screenshot_path, state_desc)
            
            # LLM Call — 接入 Tracing
            try:
                messages = message_manager.get_messages()
                from core.llm_manager import invoke_with_fallback
                response = await asyncio.get_event_loop().run_in_executor(
                    None, invoke_with_fallback, self.llm, messages
                )
                content = response.content
            except Exception as e:
                results["error"] = f"LLM Error: {e}"
                break
                
            # Parse
            try:
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                action_data = json.loads(content)
                thought = action_data.get("thought", "No thought")
                action_map = action_data.get("action", {})
                
                message_manager.add_assistant_message(thought, action_map)
                
                step_record = {
                    "step": i + 1,
                    "thought": thought,
                    "action": action_map,
                    "result": None
                }
                results["actions"].append(step_record)
                
                if not action_map:
                    message_manager.add_tool_result_message("Error: No action.")
                    continue
                    
                tool_name = list(action_map.keys())[0]
                tool_args = action_map[tool_name]
                tool_args["session_id"] = session_id
                
                logger.info(f"Executing {tool_name}: {tool_args}")
                
                # Execute Tool
                target_tool = next((t for t in UI_TOOLS if t.name == tool_name), None)
                
                if target_tool:
                    try:
                        tool_result = await target_tool.ainvoke(tool_args)
                        step_record["result"] = tool_result
                        message_manager.add_tool_result_message(str(tool_result))
                        
                    except Exception as te:
                        # Attempt Healing logic here if it's a selector error?
                        # Or let the healing wrapper handle it?
                        # Incorporating heal_and_retry
                        tool_result = f"Error invoking tool: {te}"
                        
                        if "Timeout" in str(te) or "Element" in str(te):
                             # Try healing
                             retry_data = {
                                 "action": tool_name.replace("_element", "").replace("fill_", "fill"), # rough map
                                 "text": tool_args.get("text"),
                                 "value": tool_args.get("text")
                             }
                             heal_res = await self.heal_and_retry(retry_data, {
                                 "url": current_url,
                                 "session_id": session_id,
                                 "selector": tool_args.get("selector")
                             })
                             
                             if heal_res.get("healed"):
                                 tool_result = heal_res.get("retry_result")
                                 step_record["healed"] = True
                                 step_record["result"] = tool_result
                                 message_manager.add_tool_result_message(f"Healed and retried: {tool_result}")
                             else:
                                 tool_result = f"Error invoking tool: {te} (Healing failed with {heal_res})"
                                 message_manager.add_tool_result_message(tool_result)
                        else:
                             message_manager.add_tool_result_message(tool_result)
                else:
                    tool_result = f"Error: Tool '{tool_name}' not found."
                    step_record["result"] = tool_result
                    message_manager.add_tool_result_message(str(tool_result))
                
                
                if "test complete" in thought.lower() or "测试完成" in thought:
                     results["final_status"] = "success"
                     break
                     
            except json.JSONDecodeError:
                message_manager.add_tool_result_message("Error: Invalid JSON.")
            except Exception as e:
                message_manager.add_tool_result_message(f"Execution Error: {e}")
        
        return results

    async def heal_and_retry(self, failed_action: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        自愈和重试机制（使用自愈子图）
        """
        from workflows.ui_healing_subgraph import get_healing_subgraph
        
        healing_subgraph = get_healing_subgraph()
        
        # 运行自愈流程
        # Need to ensure this is awaited properly
        result = await healing_subgraph.run(
            failed_action=failed_action,
            original_selector=context.get("selector", ""),
            url=context.get("url", Config.TARGET_URL),
            session_id=context.get("session_id")
        )
        return result
