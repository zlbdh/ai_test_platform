from typing import List, Dict, Any
import logging
import asyncio
from agents.state import EngineState
from core.config import Config as settings
from skills.react_tools import tool_goto, tool_click, tool_fill, tool_assert, tool_extract, tool_api_call, tool_db_query, tool_snapshot_db, tool_backup_db, tool_assert_db
from core.llm_manager import get_llm_for_role, invoke_with_fallback
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.runnables import RunnablePassthrough
from core.browser import get_bridged_page
from agents.judge import semantic_judge
from core.models import LogType, LogEntry
from core.log_tools import read_server_logs
from core.prompts import REACT_AGENT_PROMPT
import json
import traceback
import time

logger = logging.getLogger(__name__)

class ReActAgent:
    """
    Single-step ReAct Agent (Reasoning + Acting)
    Responsibilities:
    1. Receive the current state
    2. Observe the page
    3. Reason about the next action
    4. Select a tool (Action), supporting SQL/API/Browser/ServerLog tools
    5. Return execution results

    Ref: https://react-lm.github.io/
    """

    def __init__(self):
        # Explicitly define the tool list for LLM binding
        self.tools = [
            tool_goto, tool_click, tool_fill, tool_assert,
            tool_extract, tool_api_call, tool_db_query,
            tool_snapshot_db, tool_backup_db, tool_assert_db
        ]

        # Bind tools to the LLM
        # Use the configured PROVIDER and MODEL; support temperature=0 for precision
        self.llm = get_llm_for_role("executor", temperature=0).bind_tools(self.tools)

    def route(self, state: EngineState) -> EngineState:
        """
        Main entry point for agent logic
        """
        # 1. Build the prompt
        messages = self._construct_messages(state)

        # 2. Call the LLM
        try:
            response = invoke_with_fallback(self.llm, messages)

            # Update state
            state["logs"].append({
                "role": "ai",
                "content": str(response.content),
                "timestamp": time.time()
            })

            # 3. Process tool calls
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]

                    # Record the thought
                    log_entry = LogEntry(
                        step=f"Step-{state['current_step_index']}",
                        type=LogType.THOUGHT,
                        content=f"Decided to call {tool_name} with {tool_args}",
                        timestamp=time.time()
                    )
                    state["logs"].append(log_entry.dict())

                    # Execute the tool
                    try:
                        result = self._execute_tool(tool_name, tool_args, state)

                        # Record the observation
                        obs_entry = LogEntry(
                            step=f"Step-{state['current_step_index']}",
                            type=LogType.OBSERVATION,
                            content=f"Result: {result}",
                            tool_name=tool_name,
                            timestamp=time.time()
                        )
                        state["logs"].append(obs_entry.dict())

                    except Exception as e:
                        # Ops Agent intervention - read and analyze server logs
                        server_logs = read_server_logs(lines=50)

                        err_msg = f"Tool Execution Failed: {str(e)}\n\n[Server Logs Context]\n{server_logs}"

                        state["error"] = err_msg
                        state["logs"].append({
                            "type": "error",
                            "content": err_msg,
                            "timestamp": time.time()
                        })
                        logger.error(f"[ReAct] Error with Ops Context: {err_msg}")

            else:
                # Plain chat or completion
                state["scratchpad"] += f"\nAI: {response.content}"

        except Exception as e:
            state["error"] = f"LLM Invocation Failed: {str(e)}"
            logger.exception(f"[ReAct] LLM Invocation Failed: {e}")

        return state

    def _construct_messages(self, state: EngineState) -> List[Any]:
        """Build a context-aware prompt"""

        # Get the current task
        current_step = state["plan"][state["current_step_index"]] if state["current_step_index"] < len(state["plan"]) else None
        task_desc = f"Execute Step: {current_step['action']} -> {current_step['target']}" if current_step else "Task Completed"

        # Get page context (simplified HTML)
        page_context = "No Browser Page"
        if state["current_url"] and state["current_url"] != "about:blank":
             # Assume the browser module provides a simplified page representation or receives one through context
             # Use the URL for now
             page_context = f"Current URL: {state['current_url']}"

        system_prompt = REACT_AGENT_PROMPT.format(
            task_desc=task_desc,
            page_context=page_context,
            context=str(state['context'])
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Please execute: {task_desc}")
        ]

        return messages

    def _execute_tool(self, name: str, args: Dict, state: EngineState) -> str:
        """Tool dispatcher — handle async and sync tool calls consistently"""
        context = state.get("context", {})

        def _run_async(coro):
            """Run async tools safely in a synchronous context"""
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        return pool.submit(asyncio.run, coro).result(timeout=30)
                return loop.run_until_complete(coro)
            except RuntimeError:
                return asyncio.run(coro)

        page = _run_async(get_bridged_page())

        # Browser Tools (async, requires page)
        if name == "tool_goto":
            return _run_async(tool_goto(page, args.get("url", args.get("target", "")), context))
        elif name == "tool_click":
            return _run_async(tool_click(page, args.get("selector", args.get("target", ""))))
        elif name == "tool_fill":
            return _run_async(tool_fill(page, args.get("selector", args.get("target", "")), args.get("value", ""), context))
        elif name == "tool_assert":
            return _run_async(tool_assert(page, args.get("expected_text", args.get("target", ""))))
        elif name == "tool_extract":
            var_name = args.get("variable_name", args.get("var_name", "result"))
            selector = args.get("selector", "")
            val = _run_async(tool_extract(page, var_name, selector, context))
            state["context"][var_name] = val
            return f"Extracted {val} to ${{{var_name}}}"

        # API Tools (async)
        elif name == "tool_api_call":
            method = args.get("method", "GET")
            url = args.get("url", "")
            value = args.get("value", args.get("body", None))
            return json.dumps(_run_async(tool_api_call(method, url, value, context)))

        # DB Tools (async)
        elif name == "tool_db_query":
            return json.dumps(_run_async(tool_db_query(args.get("query", args.get("sql", "")), context)))
        elif name == "tool_snapshot_db":
            return json.dumps(_run_async(tool_snapshot_db(args.get("table_name", ""), args.get("snapshot_name", ""))))
        elif name == "tool_assert_db":
            return _run_async(tool_assert_db(args.get("table", ""), args.get("condition", ""), args.get("expected_count", None)))
        elif name == "tool_backup_db":
            return _run_async(tool_backup_db(args.get("table_name", "all")))

        else:
            raise ValueError(f"Unknown Tool: {name}")

# Singleton pattern
react_agent = ReActAgent()
