# -*- coding: utf-8 -*-
"""
UI Tools (Agent Browser Version)
Manage browser interactions centrally through the agent-browser CLI without maintaining a separate Playwright session.
"""
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
from skills.core_browser_client import execute_browser_command
import logging

logger = logging.getLogger(__name__)

# Global Vision Mode flag (retained for interface compatibility)
VISION_MODE_ENABLED = True

async def get_page(url: str = None, session_id: str = "default"):
    """
    Compatibility interface: ensure the browser has launched and navigated.
    Return (None, None) because the raw page object is no longer exposed.
    """
    if url:
        await execute_browser_command("open", [url], session_id)
    else:
        # If there is no URL, only ensure the browser has launched
        await execute_browser_command("launch", [], session_id)
    return None, None

@tool
async def navigate(url: str, session_id: str = "default") -> Dict[str, Any]:
    """
    Navigate to the specified URL
    """
    return await execute_browser_command("open", [url], session_id)

@tool
async def click_element(selector: str, session_id: str = "default") -> Dict[str, Any]:
    """
    Click an element
    selector: A CSS selector or reference ID (such as @e12)
    """
    # agent-browser click [selector]
    return await execute_browser_command("click", [selector], session_id)

@tool
async def fill_input(selector: str, text: str, session_id: str = "default") -> Dict[str, Any]:
    """
    Fill an input field
    """
    return await execute_browser_command("fill", [selector, text], session_id)

@tool
async def get_element_text(selector: str, session_id: str = "default") -> Dict[str, Any]:
    """
    Get element text
    Note: the agent-browser CLI does not expose a top-level 'get-text' command,
    but text can be obtained through evaluate or the side effects of get-by-text.
    Use evaluate for now.
    """
    # JS: document.querySelector('...').innerText
    # The selector may be a reference. For @e12, agent-browser cannot handle document.querySelector('@e12')

    # Strategy: for @Ref, direct text access through the CLI requires an internal reference mapping.
    # See actions.js: handleGetText, handleInnerText
    # agent-browser command: "innertext" action
    # CLI mapping: agent-browser innertext [selector]
    # Assume actions are called through the general 'execute_command' interface

    # The CLI parses `action arg1 arg2`; confirm that its parser supports `innertext`
    # Call the internal action directly
    return await execute_browser_command("innertext", [selector], session_id)

@tool
async def take_screenshot(session_id: str = "default") -> Dict[str, Any]:
    """
    Take a screenshot
    """
    return await execute_browser_command("screenshot", [], session_id)

@tool
async def get_interactable_elements(session_id: str = "default") -> Dict[str, Any]:
    """
    Get interactive page elements (snapshot with references)
    """
    # Corresponds to agent-browser snapshot
    result = await execute_browser_command("snapshot", [], session_id)

    # Format the return value to match the structure expected by UIAgent
    # BrowserSkills returns {snapshot: tree, refs: {...}}
    # UIAgent expects {elements: [], refs: []}

    if result.get("status") == "error":
        return {"status": "error", "error": result.get("error")}

    data = result.get("result", result) # Support potentially nested results

    # Convert the references dictionary to a list
    refs_list = []
    raw_refs = data.get("refs", {})
    if raw_refs:
        for k, v in raw_refs.items():
            refs_list.append({
                "index": k,
                "tagName": v.get("role", "element"), # Simplified
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
    Wait for an element to appear
    """
    # agent-browser wait [selector]
    # CLI arguments may not support the timeout keyword argument
    # Try: agent-browser wait selector
    return await execute_browser_command("wait", [selector], session_id)

@tool
async def go_back(session_id: str = "default") -> Dict[str, Any]:
    """Go back"""
    return await execute_browser_command("back", [], session_id)

@tool
async def refresh_page(session_id: str = "default") -> Dict[str, Any]:
    """Refresh"""
    return await execute_browser_command("reload", [], session_id)

# Compatibility functions (not tools)
async def extract_dom_structure(session_id: str = "default") -> Dict[str, Any]:
    """
    Get the DOM structure (async)
    """
    # Simply call the snapshot command
    res = await execute_browser_command("snapshot", [], session_id)
    if res.get("status") == "success":
        return res.get("result", {}).get("snapshot", {})
    return {}

@tool
async def get_dom_snapshot(session_id: str = "default") -> Dict[str, Any]:
    """
    Get a DOM snapshot (tool version)
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

# Export the tool list
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
