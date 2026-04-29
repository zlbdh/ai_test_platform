# -*- coding: utf-8 -*-
"""
Semantic Actions — 语义操作 API

提供类 Midscene.js 风格的语义化测试操作：
- ai_action(page, instruction) → "点击登录按钮"
- ai_assert(page, assertion)   → "页面显示欢迎消息"
- ai_query(page, query)        → "获取表格第一行数据"
- ai_wait(page, condition)     → "等待加载完成"
"""

from typing import Dict, Any, Optional
import asyncio
import inspect
import json
import logging
import time

logger = logging.getLogger(__name__)


async def _run_callable(fn, *args, **kwargs):
    """兼容 sync/async Playwright 调用。"""
    if inspect.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)

    result = await asyncio.to_thread(fn, *args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


async def ai_action(page, instruction: str, timeout: float = 30.0) -> Dict[str, Any]:
    """
    执行语义化操作。

    Examples:
        await ai_action(page, "点击登录按钮")
        await ai_action(page, "在搜索框中输入'AI测试'")
        await ai_action(page, "选择下拉菜单中的'中文'选项")
    """
    start = time.time()
    logger.info(f"🎯 Semantic Action: {instruction}")

    try:
        from core.semantic_engine import get_semantic_locator

        locator = get_semantic_locator()

        # 解析操作类型和目标
        action_type, target_desc, value = _parse_instruction(instruction)

        # 语义定位元素
        element = await locator.locate(page, target_desc or instruction)

        if not element:
            return {
                "success": False,
                "error": f"无法找到匹配的元素: {instruction}",
                "duration_ms": (time.time() - start) * 1000,
            }

        # 执行操作
        result = await _execute_semantic_action(page, element, action_type, value)

        elapsed = (time.time() - start) * 1000
        result["duration_ms"] = round(elapsed, 1)
        result["element"] = element.to_dict()
        result["instruction"] = instruction

        logger.info(f"✅ Semantic Action 完成: {instruction} ({elapsed:.0f}ms)")
        return result

    except Exception as e:
        elapsed = (time.time() - start) * 1000
        logger.error(f"❌ Semantic Action 失败: {instruction} - {e}")
        return {
            "success": False,
            "error": str(e),
            "duration_ms": round(elapsed, 1),
            "instruction": instruction,
        }


async def ai_assert(page, assertion: str) -> Dict[str, Any]:
    """
    执行语义化断言。

    Examples:
        await ai_assert(page, "页面显示'登录成功'")
        await ai_assert(page, "搜索结果包含至少5条记录")
        await ai_assert(page, "当前URL包含'/dashboard'")
    """
    start = time.time()
    logger.info(f"🔍 Semantic Assert: {assertion}")

    try:
        from core.llm_manager import get_llm_for_role

        # 获取页面信息
        page_text = await _run_callable(page.evaluate, "() => document.body.innerText.substring(0, 3000)")
        url = page.url
        title = await _run_callable(page.title)

        prompt = f"""判断以下断言是否成立：

## 断言
{assertion}

## 页面信息
- URL: {url}
- 标题: {title}
- 页面文本（前3000字符）:
{page_text}

请输出JSON格式（不要markdown包裹）：
{{
    "passed": true/false,
    "reasoning": "<判断理由>",
    "evidence": "<支持判断的页面内容>"
}}"""

        llm = get_llm_for_role("executor", temperature=0.0)
        result = await asyncio.to_thread(llm.invoke, prompt)
        content = result.content if hasattr(result, "content") else str(result)

        # 解析结果
        text = content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]

        data = json.loads(text.strip())
        elapsed = (time.time() - start) * 1000

        passed = data.get("passed", False)
        logger.info(f"{'✅' if passed else '❌'} Semantic Assert {'通过' if passed else '失败'}: {assertion}")

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
        logger.error(f"断言执行失败: {e}")
        return {
            "success": False,
            "passed": False,
            "error": str(e),
            "assertion": assertion,
            "duration_ms": round(elapsed, 1),
        }


async def ai_query(page, query: str) -> Dict[str, Any]:
    """
    从页面提取数据。

    Examples:
        data = await ai_query(page, "获取搜索结果的标题列表")
        data = await ai_query(page, "获取表格第一行的所有数据")
        data = await ai_query(page, "获取购物车中的商品数量")
    """
    start = time.time()
    logger.info(f"📊 Semantic Query: {query}")

    try:
        from core.llm_manager import get_llm_for_role

        page_text = await _run_callable(page.evaluate, "() => document.body.innerText.substring(0, 5000)")
        url = page.url

        prompt = f"""从页面中提取以下信息：

## 查询
{query}

## 页面 URL
{url}

## 页面文本内容
{page_text}

请输出JSON格式（不要markdown包裹）：
{{
    "data": <提取到的数据，可以是字符串、数组或对象>,
    "source": "<数据来源描述>",
    "confidence": <0.0-1.0的置信度>
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

        logger.info(f"✅ Semantic Query 完成: {query} ({elapsed:.0f}ms)")

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
        logger.error(f"数据提取失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "query": query,
            "duration_ms": round(elapsed, 1),
        }


async def ai_wait(page, condition: str, timeout: float = 30.0, interval: float = 1.0) -> Dict[str, Any]:
    """
    等待页面满足某个语义条件。

    Examples:
        await ai_wait(page, "页面加载完成")
        await ai_wait(page, "弹窗出现")
        await ai_wait(page, "表格数据显示至少3行")
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
                logger.info(f"✅ Semantic Wait 满足: {condition} ({elapsed:.0f}ms, {attempts+1}次检查)")
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
    logger.warning(f"⏰ Semantic Wait 超时: {condition} ({elapsed:.0f}ms)")
    return {
        "success": True,
        "met": False,
        "condition": condition,
        "attempts": attempts,
        "duration_ms": round(elapsed, 1),
    }


# ── 辅助函数 ──────────────────────────────────────────────────────────────────

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
    """解析自然语言指令为 (action_type, target, value)"""
    inst_lower = instruction.lower()

    # 输入/填写
    for keyword in ["输入", "填写", "type", "input", "fill"]:
        if keyword in inst_lower:
            value = _extract_quoted_value(instruction)
            target = instruction
            for quote in ("'", '"', "“", "”", "‘", "’"):
                if quote in target:
                    target = target.split(quote, 1)[0]
            return "fill", target.strip(), value

    # 点击
    for keyword in ["点击", "click", "按", "press", "tap"]:
        if keyword in inst_lower:
            return "click", instruction, ""

    # 选择
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

    # 导航
    for keyword in ["打开", "访问", "navigate", "open", "go to"]:
        if keyword in inst_lower:
            return "navigate", instruction, ""

    # 默认为点击
    return "click", instruction, ""


async def _execute_semantic_action(page, element, action_type: str, value: str = "") -> Dict:
    """执行具体的语义操作"""
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
            # 回退到坐标点击
            await _run_callable(page.mouse.click, x, y)
            return {"success": True, "method": "coordinate_click"}

        elif action_type == "fill":
            if selector:
                try:
                    await _run_callable(page.locator(selector).first.fill, value, timeout=5000)
                    return {"success": True, "method": "selector_fill", "value": value}
                except Exception:
                    pass
            # 回退：点击 + 键盘输入
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
            return {"success": False, "error": f"无法选择选项: {value}"}

        elif action_type == "navigate":
            return {"success": True, "method": "skipped", "note": "导航由外层处理"}

        else:
            return {"success": False, "error": f"未知操作类型: {action_type}"}

    except Exception as e:
        return {"success": False, "error": str(e)}
