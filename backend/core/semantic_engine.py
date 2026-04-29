# -*- coding: utf-8 -*-
"""
Semantic Engine — 语义驱动测试引擎

核心组件：
- SemanticLocator: 基于自然语言意图定位元素
- VisualContextAnalyzer: 截图→元素语义理解
- ElementRelationGraph: 元素关系图谱
- SemanticCache: 视觉特征缓存加速

对标 Midscene.js 的三层架构：
1. 底层视觉特征提取
2. 中层语义理解
3. 顶层任务规划
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import asyncio
import time
import json
import hashlib
import os
import sqlite3
import logging
import base64
import inspect

logger = logging.getLogger(__name__)


async def _run_page_callable(fn, *args, **kwargs):
    """兼容 sync/async Playwright API，统一在 async 代码里调用。"""
    if inspect.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)

    result = await asyncio.to_thread(fn, *args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


# ── 数据结构 ──────────────────────────────────────────────────────────────────

@dataclass
class SemanticElement:
    """语义化的页面元素"""
    element_id: str = ""
    text: str = ""
    role: str = ""                  # button, input, link, heading, etc.
    description: str = ""           # LLM 生成的语义描述
    selector: str = ""              # CSS/XPath 选择器
    bounding_box: Dict[str, float] = field(default_factory=dict)  # x, y, width, height
    visual_hash: str = ""           # 视觉特征哈希
    attributes: Dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0         # 匹配置信度

    def to_dict(self) -> Dict:
        return {
            "element_id": self.element_id,
            "text": self.text,
            "role": self.role,
            "description": self.description,
            "selector": self.selector,
            "bounding_box": self.bounding_box,
            "confidence": round(self.confidence, 3),
        }


@dataclass
class SemanticContext:
    """页面语义上下文"""
    page_title: str = ""
    page_url: str = ""
    elements: List[SemanticElement] = field(default_factory=list)
    screenshot_b64: str = ""
    dom_summary: str = ""
    timestamp: float = field(default_factory=time.time)


# ── 语义缓存 ──────────────────────────────────────────────────────────────────

class SemanticCache:
    """
    语义特征缓存 — 避免重复调用 LLM 分析相同页面。

    缓存策略：
    - 以 URL + DOM hash 为键
    - 有效期 300 秒（5分钟）
    - 最多缓存 100 条
    """

    def __init__(self, max_entries: int = 100, ttl_seconds: float = 300):
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._max_entries = max_entries
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry:
            ts, value = entry
            if time.time() - ts < self._ttl:
                self._hits += 1
                return value
            else:
                del self._cache[key]
        self._misses += 1
        return None

    def set(self, key: str, value: Any):
        if len(self._cache) >= self._max_entries:
            # 淘汰最旧的
            oldest = min(self._cache, key=lambda k: self._cache[k][0])
            del self._cache[oldest]
        self._cache[key] = (time.time(), value)

    @staticmethod
    def make_key(url: str, dom_hash: str) -> str:
        return hashlib.md5(f"{url}:{dom_hash}".encode()).hexdigest()

    @property
    def stats(self) -> Dict:
        return {"hits": self._hits, "misses": self._misses, "size": len(self._cache)}


# ── 语义定位器 ────────────────────────────────────────────────────────────────

class SemanticLocator:
    """
    基于自然语言意图定位页面元素。

    工作流程：
    1. 接收自然语言描述（如"点击登录按钮"）
    2. 截图 + 获取 DOM
    3. 调用 VLM 理解页面布局
    4. 匹配最佳元素
    5. 返回坐标或选择器
    """

    LOCATE_PROMPT = """你是一个精确的UI元素定位专家。

## 任务
根据用户的自然语言描述，在页面中找到目标元素。

## 用户描述
{instruction}

## 当前页面信息
- URL: {url}
- Title: {title}

## 页面可交互元素列表
{elements_list}

## 要求
请找到最匹配用户描述的元素，输出JSON格式（不要markdown包裹）：
{{
    "element_index": <元素索引号，从0开始>,
    "confidence": <0.0-1.0的置信度>,
    "reasoning": "<选择该元素的理由>"
}}

如果没有匹配的元素，输出：
{{
    "element_index": -1,
    "confidence": 0.0,
    "reasoning": "<没找到的原因>"
}}"""

    def __init__(self):
        self._cache = SemanticCache()

    async def locate(
        self,
        page,
        instruction: str,
        use_vision: bool = True,
    ) -> Optional[SemanticElement]:
        """
        在页面中定位匹配自然语言描述的元素。

        Args:
            page: Playwright Page 对象
            instruction: 自然语言描述
            use_vision: 是否使用视觉模型

        Returns:
            匹配的 SemanticElement，或 None
        """
        try:
            # 1. 收集页面元素
            elements = await self._extract_elements(page)
            if not elements:
                logger.warning("页面无可交互元素")
                return None

            # 2. 检查缓存
            url = page.url
            dom_hash = hashlib.md5(str([e.text + e.role for e in elements]).encode()).hexdigest()[:8]
            cache_key = f"{SemanticCache.make_key(url, dom_hash)}:{instruction}"
            cached = self._cache.get(cache_key)
            if cached:
                logger.info(f"语义缓存命中: {instruction}")
                return cached

            # 3. LLM 语义匹配
            page_title = await _run_page_callable(page.title)
            matched = await self._llm_match(instruction, url, page_title, elements)

            if matched:
                self._cache.set(cache_key, matched)

            return matched

        except Exception as e:
            logger.error(f"语义定位失败: {e}")
            return None

    async def _extract_elements(self, page) -> List[SemanticElement]:
        """从页面提取可交互元素"""
        try:
            elements_data = await _run_page_callable(page.evaluate, """() => {
                const interactive = document.querySelectorAll(
                    'a, button, input, select, textarea, [role="button"], [onclick], [tabindex]'
                );
                const results = [];
                interactive.forEach((el, idx) => {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0 && rect.top >= 0) {
                        results.push({
                            index: idx,
                            tag: el.tagName.toLowerCase(),
                            text: (el.textContent || '').trim().substring(0, 100),
                            placeholder: el.getAttribute('placeholder') || '',
                            ariaLabel: el.getAttribute('aria-label') || '',
                            role: el.getAttribute('role') || el.tagName.toLowerCase(),
                            type: el.getAttribute('type') || '',
                            id: el.id || '',
                            name: el.getAttribute('name') || '',
                            className: el.className ? el.className.toString().substring(0, 100) : '',
                            href: el.getAttribute('href') || '',
                            x: rect.x + rect.width / 2,
                            y: rect.y + rect.height / 2,
                            width: rect.width,
                            height: rect.height,
                        });
                    }
                });
                return results.slice(0, 50);  // 限制数量
            }""")

            elements = []
            for data in elements_data:
                el = SemanticElement(
                    element_id=f"el_{data['index']}",
                    text=data.get("text", "") or data.get("placeholder", "") or data.get("ariaLabel", ""),
                    role=data.get("role", data.get("tag", "")),
                    selector=self._build_selector(data),
                    bounding_box={
                        "x": data["x"], "y": data["y"],
                        "width": data["width"], "height": data["height"],
                    },
                    attributes={k: v for k, v in data.items() if v and k not in ("x", "y", "width", "height", "index")},
                )
                elements.append(el)

            return elements
        except Exception as e:
            logger.error(f"元素提取失败: {e}")
            return []

    async def _llm_match(
        self,
        instruction: str,
        url: str,
        title: str,
        elements: List[SemanticElement],
    ) -> Optional[SemanticElement]:
        """使用 LLM 进行语义匹配"""
        try:
            from core.llm_manager import get_llm_for_role
            llm = get_llm_for_role("executor", temperature=0.0)

            # 构建元素列表文本
            el_lines = []
            for i, el in enumerate(elements):
                label = el.text or el.attributes.get("placeholder", "") or el.attributes.get("ariaLabel", "")
                el_lines.append(
                    f"[{i}] <{el.role}> text=\"{label}\" id=\"{el.attributes.get('id', '')}\" "
                    f"name=\"{el.attributes.get('name', '')}\" pos=({el.bounding_box.get('x', 0):.0f}, {el.bounding_box.get('y', 0):.0f})"
                )

            prompt = self.LOCATE_PROMPT.format(
                instruction=instruction,
                url=url,
                title=title,
                elements_list="\n".join(el_lines),
            )

            import asyncio
            result = await asyncio.to_thread(llm.invoke, prompt)
            content = result.content if hasattr(result, "content") else str(result)

            # 解析
            text = content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]

            data = json.loads(text.strip())
            idx = data.get("element_index", -1)
            confidence = data.get("confidence", 0)

            if 0 <= idx < len(elements):
                matched = elements[idx]
                matched.confidence = confidence
                matched.description = data.get("reasoning", "")
                logger.info(f"语义匹配成功: '{instruction}' → [{idx}] {matched.text} (置信度: {confidence})")
                return matched
            else:
                logger.warning(f"语义匹配失败: {data.get('reasoning', 'unknown')}")
                return None

        except Exception as e:
            logger.error(f"LLM 语义匹配失败: {e}")
            return None

    @staticmethod
    def _build_selector(data: Dict) -> str:
        """构建最佳选择器"""
        if data.get("id"):
            return f"#{data['id']}"
        if data.get("name"):
            return f"[name='{data['name']}']"
        tag = data.get("tag", "")
        text = data.get("text", "")
        if tag and text:
            return f"{tag}:has-text('{text[:50]}')"
        return ""


# ── 视觉上下文分析器 ──────────────────────────────────────────────────────────

class VisualContextAnalyzer:
    """
    截图→语义理解。

    使用多模态LLM分析页面截图，提取：
    - 页面类型（登录、搜索、列表等）
    - 主要功能区域
    - 关键UI元素描述
    """

    ANALYSIS_PROMPT = """分析这个网页截图，简洁输出JSON格式（不要markdown包裹）：
{{
    "page_type": "<页面类型：login/search/dashboard/form/list/article/other>",
    "main_actions": ["<可执行的主要操作1>", "<操作2>"],
    "key_elements": ["<关键UI元素描述1>", "<描述2>"],
    "state": "<页面当前状态描述>"
}}"""

    async def analyze(self, screenshot_b64: str) -> Dict[str, Any]:
        """分析页面截图"""
        try:
            from core.llm_manager import LLMManager
            from langchain_core.messages import HumanMessage

            llm_mgr = LLMManager()
            vlm = llm_mgr.get_vision_llm()

            message = HumanMessage(
                content=[
                    {"type": "text", "text": self.ANALYSIS_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{screenshot_b64}"}},
                ]
            )

            import asyncio
            result = await asyncio.to_thread(vlm.invoke, [message])
            content = result.content if hasattr(result, "content") else str(result)

            text = content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]

            return json.loads(text.strip())
        except Exception as e:
            logger.error(f"视觉上下文分析失败: {e}")
            return {"page_type": "unknown", "error": str(e)}


# ── 单例 ──────────────────────────────────────────────────────────────────────

_locator: Optional[SemanticLocator] = None
_visual_analyzer: Optional[VisualContextAnalyzer] = None


def get_semantic_locator() -> SemanticLocator:
    global _locator
    if _locator is None:
        _locator = SemanticLocator()
    return _locator


def get_visual_analyzer() -> VisualContextAnalyzer:
    global _visual_analyzer
    if _visual_analyzer is None:
        _visual_analyzer = VisualContextAnalyzer()
    return _visual_analyzer
