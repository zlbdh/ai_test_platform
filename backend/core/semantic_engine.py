# -*- coding: utf-8 -*-
"""
Semantic Engine — semantic testing engine

Core components:
- SemanticLocator: Locate elements from natural-language intent
- VisualContextAnalyzer: Screenshot-to-element semantic understanding
- ElementRelationGraph: Element relationship graph
- SemanticCache: Acceleration through visual feature caching

Three-layer architecture comparable to Midscene.js:
1. Low-level visual feature extraction
2. Intermediate semantic understanding
3. High-level task planning
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
    """Call both sync and async Playwright APIs from async code."""
    if inspect.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)

    result = await asyncio.to_thread(fn, *args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


# ── Data structures ──────────────────────────────────────────────────────────────────

@dataclass
class SemanticElement:
    """Semantic page element"""
    element_id: str = ""
    text: str = ""
    role: str = ""                  # button, input, link, heading, etc.
    description: str = ""           # LLM-generated semantic description
    selector: str = ""              # CSS/XPath selector
    bounding_box: Dict[str, float] = field(default_factory=dict)  # x, y, width, height
    visual_hash: str = ""           # Visual feature hash
    attributes: Dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0         # Match confidence

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
    """Page semantic context"""
    page_title: str = ""
    page_url: str = ""
    elements: List[SemanticElement] = field(default_factory=list)
    screenshot_b64: str = ""
    dom_summary: str = ""
    timestamp: float = field(default_factory=time.time)


# ── Semantic cache ──────────────────────────────────────────────────────────────────

class SemanticCache:
    """
    Semantic feature cache that avoids repeated LLM analysis of the same page.

    Cache policy:
    - Keyed by URL + DOM hash
    - Valid for 300 seconds (5 minutes)
    - Cache at most 100 entries
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
            # Evict the oldest entry
            oldest = min(self._cache, key=lambda k: self._cache[k][0])
            del self._cache[oldest]
        self._cache[key] = (time.time(), value)

    @staticmethod
    def make_key(url: str, dom_hash: str) -> str:
        return hashlib.md5(f"{url}:{dom_hash}".encode()).hexdigest()

    @property
    def stats(self) -> Dict:
        return {"hits": self._hits, "misses": self._misses, "size": len(self._cache)}


# ── Semantic locator ────────────────────────────────────────────────────────────────

class SemanticLocator:
    """
    Locate page elements from natural-language intent.

    Workflow:
    1. Receive a natural-language description such as "Click the sign-in button"
    2. Take a screenshot and retrieve the DOM
    3. Use a VLM to understand the page layout
    4. Match the best element
    5. Return coordinates or a selector
    """

    LOCATE_PROMPT = """You are an expert in precise UI element location.

## Task
Find the target page element from the user's natural-language description.

## User description
{instruction}

## Current page information
- URL: {url}
- Title: {title}

## Interactive page elements
{elements_list}

## Requirements
Find the element that best matches the description and return JSON without Markdown fences:
{{
    "element_index": <zero-based element index>,
    "confidence": <confidence from 0.0 to 1.0>,
    "reasoning": "<reason for selecting this element>"
}}

If no element matches, return:
{{
    "element_index": -1,
    "confidence": 0.0,
    "reasoning": "<reason no match was found>"
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
        Locate a page element matching the natural-language description.

        Args:
            page: Playwright Page object
            instruction: Natural-language description
            use_vision: Whether to use a vision model

        Returns:
            Matching SemanticElement, or None
        """
        try:
            # 1. Collect page elements
            elements = await self._extract_elements(page)
            if not elements:
                logger.warning("No interactive page elements")
                return None

            # 2. Check the cache
            url = page.url
            dom_hash = hashlib.md5(str([e.text + e.role for e in elements]).encode()).hexdigest()[:8]
            cache_key = f"{SemanticCache.make_key(url, dom_hash)}:{instruction}"
            cached = self._cache.get(cache_key)
            if cached:
                logger.info(f"Semantic cache hit: {instruction}")
                return cached

            # 3. LLM semantic matching
            page_title = await _run_page_callable(page.title)
            matched = await self._llm_match(instruction, url, page_title, elements)

            if matched:
                self._cache.set(cache_key, matched)

            return matched

        except Exception as e:
            logger.error(f"Semantic location failed: {e}")
            return None

    async def _extract_elements(self, page) -> List[SemanticElement]:
        """Extract interactive elements from the page"""
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
                return results.slice(0, 50);  // Limit the count
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
            logger.error(f"Element extraction failed: {e}")
            return []

    async def _llm_match(
        self,
        instruction: str,
        url: str,
        title: str,
        elements: List[SemanticElement],
    ) -> Optional[SemanticElement]:
        """Use an LLM for semantic matching"""
        try:
            from core.llm_manager import get_llm_for_role
            llm = get_llm_for_role("executor", temperature=0.0)

            # Build the element list text
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

            # Parse
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
                logger.info(f"Semantic match succeeded: '{instruction}' → [{idx}] {matched.text} (confidence: {confidence})")
                return matched
            else:
                logger.warning(f"Semantic matching failed: {data.get('reasoning', 'unknown')}")
                return None

        except Exception as e:
            logger.error(f"LLM semantic matching failed: {e}")
            return None

    @staticmethod
    def _build_selector(data: Dict) -> str:
        """Build the best selector"""
        if data.get("id"):
            return f"#{data['id']}"
        if data.get("name"):
            return f"[name='{data['name']}']"
        tag = data.get("tag", "")
        text = data.get("text", "")
        if tag and text:
            return f"{tag}:has-text('{text[:50]}')"
        return ""


# ── Visual context analyzer ──────────────────────────────────────────────────────────

class VisualContextAnalyzer:
    """
    Screenshot-to-semantic understanding.

    Analyze a page screenshot with a multimodal LLM and extract:
    - Page type (sign-in, search, list, and others)
    - Main functional areas
    - Key UI element descriptions
    """

    ANALYSIS_PROMPT = """Analyze this webpage screenshot and return concise JSON without Markdown fences:
{{
    "page_type": "<page type: login/search/dashboard/form/list/article/other>",
    "main_actions": ["<main available action 1>", "<action 2>"],
    "key_elements": ["<key UI element description 1>", "<description 2>"],
    "state": "<description of the current page state>"
}}"""

    async def analyze(self, screenshot_b64: str) -> Dict[str, Any]:
        """Analyze a page screenshot"""
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
            logger.error(f"Visual context analysis failed: {e}")
            return {"page_type": "unknown", "error": str(e)}


# ── Singleton ──────────────────────────────────────────────────────────────────────

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
