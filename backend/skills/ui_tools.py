# -*- coding: utf-8 -*-
"""
UI Tools (Agent Browser Version)
使用 agent-browser CLI 统一管理浏览器交互，不再独立维护 Playwright 会话。
"""
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
from skills.core_browser_client import execute_browser_command
import logging

logger = logging.getLogger(__name__)

# 全局开启 Vision Mode 标识 (保留接口兼容性)
VISION_MODE_ENABLED = True 

async def get_page(url: str = None, session_id: str = "default"):
    """
    兼容性接口：确保浏览器已启动并导航。
    返回 (None, None) 因为不再暴露 raw page 对象。
    """
    if url:
        await execute_browser_command("open", [url], session_id)
    else:
        # 如果没有 URL，只需确保 launch
        await execute_browser_command("launch", [], session_id)
    return None, None

@tool
async def navigate(url: str, session_id: str = "default") -> Dict[str, Any]:
    """
    访问指定 URL
    """
    return await execute_browser_command("open", [url], session_id)

@tool
async def click_element(selector: str, session_id: str = "default") -> Dict[str, Any]:
    """
    点击元素
    selector: 可以是 CSS 选择器，也可以是 Ref ID (如 @e12)
    """
    # agent-browser click [selector]
    return await execute_browser_command("click", [selector], session_id)

@tool
async def fill_input(selector: str, text: str, session_id: str = "default") -> Dict[str, Any]:
    """
    填写输入框
    """
    return await execute_browser_command("fill", [selector, text], session_id)

@tool
async def get_element_text(selector: str, session_id: str = "default") -> Dict[str, Any]:
    """
    获取元素文本
    注: agent-browser CLI 没有直接的 'get-text' 命令暴露在顶层，
    但可以通过 evaluate 或 get-by-text 的副作用获得。
    暂时使用 evaluate 获取。
    """
    # JS: document.querySelector('...').innerText
    # 但我们不知道它是不是 Ref。如果是 @e12，agent-browser 处理不了 document.querySelector('@e12')
    
    # 策略：如果是 @Ref，尚不支持 direct text via CLI easily unless we map refs internally.
    # 查阅 actions.js: handleGetText, handleInnerText
    # agent-browser command: "innertext" action
    # CLI 映射: agent-browser innertext [selector]
    # 假设我们通过通用 'execute_command' 接口调用 action
    
    # 由于 CLI 参数解析是 `action arg1 arg2`，我们需要确认 `innertext` 是否被 CLI parser 支持
    # 简单调用 internal action
    return await execute_browser_command("innertext", [selector], session_id)

@tool
async def take_screenshot(session_id: str = "default") -> Dict[str, Any]:
    """
    截图
    """
    return await execute_browser_command("screenshot", [], session_id)

@tool
async def get_interactable_elements(session_id: str = "default") -> Dict[str, Any]:
    """
    获取页面可交互元素 (Snapshot with Refs)
    """
    # 对应 agent-browser snapshot
    result = await execute_browser_command("snapshot", [], session_id)
    
    # 格式化返回值以匹配 UIAgent 期望的结构
    # BrowserSkills 返回 {snapshot: tree, refs: {...}}
    # UIAgent 期望 {elements: [], refs: []}
    
    if result.get("status") == "error":
        return {"status": "error", "error": result.get("error")}
        
    data = result.get("result", result) # 兼容可能的嵌套
    
    # 转换 Refs 字典为 List
    refs_list = []
    raw_refs = data.get("refs", {})
    if raw_refs:
        for k, v in raw_refs.items():
            refs_list.append({
                "index": k,
                "tagName": v.get("role", "element"), # 简化
                "text": v.get("name", "")
            })
            
    return {
        "status": "success",
        "refs": refs_list,
        "tree": data.get("snapshot"),
        "elements": data.get("elements", []) # Pass flattening elements
    }

@tool
async def wait_for_element(selector: str, timeout: int = 5000, session_id: str = "default") -> Dict[str, Any]:
    """
    等待元素出现
    """
    # agent-browser wait [selector]
    # CLI 传参可能不支持 kwargs timeout
    # 尝试: agent-browser wait selector
    return await execute_browser_command("wait", [selector], session_id)

@tool
async def go_back(session_id: str = "default") -> Dict[str, Any]:
    """后退"""
    return await execute_browser_command("back", [], session_id)

@tool
async def refresh_page(session_id: str = "default") -> Dict[str, Any]:
    """刷新"""
    return await execute_browser_command("reload", [], session_id)

# 兼容性函数 (非 Tool)
async def extract_dom_structure(session_id: str = "default") -> Dict[str, Any]:
    """
    获取 DOM 结构 (Async)
    """
    # Simply call the snapshot command
    res = await execute_browser_command("snapshot", [], session_id)
    if res.get("status") == "success":
        return res.get("result", {}).get("snapshot", {})
    return {}

@tool
async def get_dom_snapshot(session_id: str = "default") -> Dict[str, Any]:
    """
    获取 DOM 快照 (Tool Version)
    """
    res = await execute_browser_command("snapshot", [], session_id)
    if res.get("status") == "success":
        data = res.get("result", {})
        return {
            "type": "dom_snapshot",
            "snapshot": data.get("snapshot"),
            "refs": data.get("refs")
        }
    return {"error": res.get("error")}

# 导出工具列表
UI_TOOLS = [
    navigate,
    click_element,
    fill_input,
    get_element_text,
    take_screenshot,
    get_interactable_elements,
    wait_for_element,
    go_back,
    refresh_page,
    get_dom_snapshot # Added to tools list
]
