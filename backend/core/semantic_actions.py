# -*- coding: utf-8 -*-
"""
Semantic Actions — semantic interaction API

Provide semantic test operations in the style of Midscene.js:
- ai_action(page, instruction) → "Click the sign-in button"
- ai_assert(page, assertion)   → "The page displays a welcome message"
- ai_query(page, query)        → "Get data from the first table row"
- ai_wait(page, condition)     → "Wait for loading to finish"
"""

from typing import Dict, Any, Optional
import asyncio
import inspect
import json
import logging
import time

logger = logging.getLogger(__name__)


async def _run_callable(fn, *args, **kwargs):
    """Support sync and async Playwright calls."""
    if inspect.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)

    result = await asyncio.to_thread(fn, *args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


async def ai_action(page, instruction: str, timeout: float = 30.0) -> Dict[str, Any]:
    """
    Execute a semantic action.

    Examples:
        await ai_action(page, "Click the sign-in button")
        await ai_action(page, "Fill the search field with 'AI testing'")
        await ai_action(page, "Select 'English' in the dropdown")
    """
    start = time.time()
    logger.info(f"🎯 Semantic Action: {instruction}")

    try:
        from core.semantic_engine import get_semantic_locator

        locator = get_semantic_locator()

        # Parse the action type and target
        action_type, target_desc, value = _parse_instruction(instruction)

        # Locate the element semantically
        element = await locator.locate(page, target_desc or instruction)

        if not element:
            return {
                "success": False,
                "error": f"Cannot find a matching element: {instruction}",
                "duration_ms": (time.time() - start) * 1000,
            }

        # Execute the action
        result = await _execute_semantic_action(page, element, action_type, value)

        elapsed = (time.time() - start) * 1000
        result["duration_ms"] = round(elapsed, 1)
        result["element"] = element.to_dict()
        result["instruction"] = instruction

        logger.info(f"✅ Semantic Action completed: {instruction} ({elapsed:.0f}ms)")
        return result

    except Exception as e:
        elapsed = (time.time() - start) * 1000
        logger.error(f"❌ Semantic Action failed: {instruction} - {e}")
        return {
            "success": False,
            "error": str(e),
            "duration_ms": round(elapsed, 1),
            "instruction": instruction,
        }


async def ai_assert(page, assertion: str) -> Dict[str, Any]:
    """
    Execute a semantic assertion.

    Examples:
        await ai_assert(page, "The page displays 'Signed in successfully'")
        await ai_assert(page, "Search results contain at least 5 records")
        await ai_assert(page, "The current URL contains '/dashboard'")
    """
    start = time.time()
    logger.info(f"🔍 Semantic Assert: {assertion}")

    try:
        from core.llm_manager import get_llm_for_role

        # Get page information
        page_text = await _run_callable(page.evaluate, "() => document.body.innerText.substring(0, 3000)")
        url = page.url
        title = await _run_callable(page.title)

        prompt = f"""Determine whether the following assertion holds:

## Assertion
{assertion}

## Page information
- URL: {url}
- Title: {title}
- Page text (first 3,000 characters):
{page_text}

Return JSON without Markdown fences:
{{
    "passed": true/false,
    "reasoning": "<reasoning>",
    "evidence": "<page content supporting the judgment>"
}}"""

        llm = get_llm_for_role("executor", temperature=0.0)
        result = await asyncio.to_thread(llm.invoke, prompt)
        content = result.content if hasattr(result, "content") else str(result)

        # Parse the result
        text = content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]

        data = json.loads(text.strip())
        elapsed = (time.time() - start) * 1000

        passed = data.get("passed", False)
        logger.info(f"{'✅' if passed else '❌'} Semantic Assert {'passed' if passed else 'failed'}: {assertion}")

        return {
            "success": True,
            "passed": passed,
            "reasoning": data.get("reasoning", ""),
            "evidence": data.get("evidence", ""),
            "assertion": assertion,
            "duration_ms": round(elapsed, 1),
        }

    except Exception as e:
        elapsed = (time.time() - start) * 1000
        logger.error(f"Assertion execution failed: {e}")
        return {
            "success": False,
            "passed": False,
            "error": str(e),
            "assertion": assertion,
            "duration_ms": round(elapsed, 1),
        }


async def ai_query(page, query: str) -> Dict[str, Any]:
    """
    Extract data from the page.

    Examples:
        data = await ai_query(page, "Get the list of search result titles")
        data = await ai_query(page, "Get all data from the first table row")
        data = await ai_query(page, "Get the number of items in the shopping cart")
    """
    start = time.time()
    logger.info(f"📊 Semantic Query: {query}")

    try:
        from core.llm_manager import get_llm_for_role

        page_text = await _run_callable(page.evaluate, "() => document.body.innerText.substring(0, 5000)")
        url = page.url

        prompt = f"""Extract the following information from the page:

## Query
{query}

## Page URL
{url}

## Page text content
{page_text}

Return JSON without Markdown fences:
{{
    "data": <extracted data: a string, array, or object>,
    "source": "<description of the data source>",
    "confidence": <confidence from 0.0 to 1.0>
}}"""

        llm = get_llm_for_role("executor", temperature=0.0)
        result = await asyncio.to_thread(llm.invoke, prompt)
        content = result.content if hasattr(result, "content") else str(result)

        text = content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]

        data = json.loads(text.strip())
        elapsed = (time.time() - start) * 1000

        logger.info(f"✅ Semantic Query completed: {query} ({elapsed:.0f}ms)")

        return {
            "success": True,
            "data": data.get("data"),
            "source": data.get("source", ""),
            "confidence": data.get("confidence", 0.5),
            "query": query,
            "duration_ms": round(elapsed, 1),
        }

    except Exception as e:
        elapsed = (time.time() - start) * 1000
        logger.error(f"Data extraction failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "query": query,
            "duration_ms": round(elapsed, 1),
        }


async def ai_wait(page, condition: str, timeout: float = 30.0, interval: float = 1.0) -> Dict[str, Any]:
    """
    Wait for the page to satisfy a semantic condition.

    Examples:
        await ai_wait(page, "The page has finished loading")
        await ai_wait(page, "An alert appears")
        await ai_wait(page, "The table displays at least 3 rows")
    """
    start = time.time()
    logger.info(f"⏳ Semantic Wait: {condition}")

    attempts = 0
    max_attempts = int(timeout / interval)

    while attempts < max_attempts:
        try:
            result = await ai_assert(page, condition)
            if result.get("passed"):
                elapsed = (time.time() - start) * 1000
                logger.info(f"✅ Semantic Wait satisfied: {condition} ({elapsed:.0f}ms, {attempts+1} checks)")
                return {
                    "success": True,
                    "met": True,
                    "condition": condition,
                    "attempts": attempts + 1,
                    "duration_ms": round(elapsed, 1),
                }
        except Exception:
            pass
        attempts += 1
        await asyncio.sleep(interval)

    elapsed = (time.time() - start) * 1000
    logger.warning(f"⏰ Semantic Wait timed out: {condition} ({elapsed:.0f}ms)")
    return {
        "success": True,
        "met": False,
        "condition": condition,
        "attempts": attempts,
        "duration_ms": round(elapsed, 1),
    }


# ── Helper functions ──────────────────────────────────────────────────────────────────

def _extract_quoted_value(text: str) -> str:
    for open_quote, close_quote in (("'", "'"), ('"', '"'), ("“", "”"), ("‘", "’")):
        if open_quote not in text:
            continue
        start = text.index(open_quote) + 1
        if close_quote not in text[start:]:
            continue
        end = text.index(close_quote, start)
        return text[start:end]
    return ""


def _parse_instruction(instruction: str):
    """Parse a natural-language instruction into (action_type, target, value)"""
    inst_lower = instruction.lower()

    # Input/fill
    for keyword in ["输入", "填写", "type", "input", "fill"]:
        if keyword in inst_lower:
            value = _extract_quoted_value(instruction)
            target = instruction
            for quote in ("'", '"', "“", "”", "‘", "’"):
                if quote in target:
                    target = target.split(quote, 1)[0]
            return "fill", target.strip(), value

    # Click
    for keyword in ["点击", "click", "按", "press", "tap"]:
        if keyword in inst_lower:
            return "click", instruction, ""

    # Select
    for keyword in ["选择", "select", "choose"]:
        if keyword in inst_lower:
            value = ""
            for qp in [("'", "'"), ('"', '"')]:
                if qp[0] in instruction:
                    s = instruction.index(qp[0]) + 1
                    e = instruction.index(qp[1], s) if qp[1] in instruction[s:] else len(instruction)
                    value = instruction[s:e]
                    break
            return "select", instruction, value

    # Navigate
    for keyword in ["打开", "访问", "navigate", "open", "go to"]:
        if keyword in inst_lower:
            return "navigate", instruction, ""

    # Default to click
    return "click", instruction, ""


async def _execute_semantic_action(page, element, action_type: str, value: str = "") -> Dict:
    """Execute the specific semantic action"""
    bbox = element.bounding_box
    x = bbox.get("x", 0)
    y = bbox.get("y", 0)
    selector = element.selector

    try:
        if action_type == "click":
            if selector:
                try:
                    await _run_callable(page.locator(selector).first.click, timeout=5000)
                    return {"success": True, "method": "selector_click"}
                except Exception:
                    pass
            # Fall back to clicking coordinates
            await _run_callable(page.mouse.click, x, y)
            return {"success": True, "method": "coordinate_click"}

        elif action_type == "fill":
            if selector:
                try:
                    await _run_callable(page.locator(selector).first.fill, value, timeout=5000)
                    return {"success": True, "method": "selector_fill", "value": value}
                except Exception:
                    pass
            # Fallback: click and keyboard input
            await _run_callable(page.mouse.click, x, y)
            await asyncio.sleep(0.3)
            await _run_callable(page.keyboard.type, value)
            return {"success": True, "method": "coordinate_type", "value": value}

        elif action_type == "select":
            if selector:
                try:
                    await _run_callable(page.locator(selector).first.select_option, label=value, timeout=5000)
                    return {"success": True, "method": "select_option", "value": value}
                except Exception:
                    pass
            return {"success": False, "error": f"Cannot select option: {value}"}

        elif action_type == "navigate":
            return {"success": True, "method": "skipped", "note": "Navigation is handled by the caller"}

        else:
            return {"success": False, "error": f"Unknown action type: {action_type}"}

    except Exception as e:
        return {"success": False, "error": str(e)}
