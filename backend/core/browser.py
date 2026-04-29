from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from core.prompts import SOM_VISION_PROMPT, FIND_SELECTOR_PROMPT
from bs4 import BeautifulSoup
import base64
import asyncio
import logging
from core.llm_manager import get_vision_llm
from core.shared import SharedBrowserState

logger = logging.getLogger(__name__)

# JavaScript 脚本：用于注入 Set-of-Marks (SoM) 标记
# ... (Script remains unchanged)
SOM_JS = """
(function() {
    window.som_markers = [];
    const elements = document.querySelectorAll('button, a, input, [role="button"]');
    let counter = 1;
    
    // 清理旧标记
    document.querySelectorAll('.som-marker').forEach(e => e.remove());
    
    elements.forEach(el => {
        const rect = el.getBoundingClientRect();
        // 过滤不可见元素
        if (rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden') {
            el.setAttribute('data-som-id', counter);
            
            // 创建并样式化数字标记
            const marker = document.createElement('div');
            marker.className = 'som-marker';
            marker.textContent = counter;
            marker.style.position = 'absolute';
            marker.style.left = (rect.left + window.scrollX) + 'px';
            marker.style.top = (rect.top + window.scrollY) + 'px';
            marker.style.backgroundColor = '#ff0000'; // 醒目的红色
            marker.style.color = 'white';
            marker.style.fontSize = '12px';
            marker.style.fontWeight = 'bold';
            marker.style.padding = '2px 4px';
            marker.style.zIndex = '999999';
            marker.style.border = '1px solid white';
            marker.style.borderRadius = '3px';
            document.body.appendChild(marker);
            
            window.som_markers.push({id: counter, el: el});
            counter++;
        }
    });
})();
"""

async def analyze_with_som(page, task_desc):
    """
    使用 Set-of-Marks (SoM) 视觉技术定位元素 ID (Async Version)。
    """
    logger.info(f"[SoM] Starting analysis: {task_desc}")
    
    vision_llm = get_vision_llm()
    if not vision_llm:
        logger.info("[SoM] Vision model unavailable, skipping.")
        return None
        
    try:
        # 1. 注入标记 (Inject Markers)
        await page.evaluate(SOM_JS)
        await asyncio.sleep(0.5) # 等待渲染完成
        
        # 2. 截图 (Screenshot)
        screenshot_bytes = await page.screenshot(type="jpeg", quality=50)
        base64_image = base64.b64encode(screenshot_bytes).decode('utf-8')
        
        # 3. 构造视觉提示词 (Vision Prompt)
        msg = HumanMessage(
            content=[
                {"type": "text", "text": SOM_VISION_PROMPT.format(task_desc=task_desc)},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        )
        
        # 4. 调用视觉大模型 (Invoke Vision LLM)
        try:
            res = await asyncio.wait_for(vision_llm.ainvoke([msg]), timeout=60)
        except Exception as e_vision:
            logger.warning(f"[SoM] Vision model call failed: {e_vision}")
            return None

        content = res.content.strip().replace("```json", "").replace("```", "")
        
        import json
        result = json.loads(content)
        som_id = result.get("id")
        
        # 5. 清理标记 (Cleanup)
        await page.evaluate("document.querySelectorAll('.som-marker').forEach(e => e.remove());")
        
        if som_id:
            logger.info(f"[SoM] Target identified: ID {som_id}")
            return som_id
            
    except Exception as e:
        logger.warning(f"[SoM] Analysis failed: {e}")
        try:
             await page.evaluate("document.querySelectorAll('.som-marker').forEach(e => e.remove());")
        except Exception:
            pass  # Cleanup failure is not critical
    
    return None


def sync_analyze_with_som(page, task_desc):
    """
    使用 Set-of-Marks (SoM) 视觉技术定位元素 ID (Sync Version)。
    用于 sync_playwright executor 线程。
    """
    import json as _json
    import time as _time
    
    logger.info(f"[SoM/Sync] Starting analysis: {task_desc}")
    
    vision_llm = get_vision_llm()
    if not vision_llm:
        logger.info("[SoM/Sync] Vision model unavailable, skipping.")
        return None
        
    try:
        # 1. 注入标记 (Inject Markers) — 同步调用
        page.evaluate(SOM_JS)
        _time.sleep(0.5)  # 等待渲染完成
        
        # 2. 截图 (Screenshot) — 同步调用
        screenshot_bytes = page.screenshot(type="jpeg", quality=50)
        base64_image = base64.b64encode(screenshot_bytes).decode('utf-8')
        
        # 3. 构造视觉提示词 (Vision Prompt)
        msg = HumanMessage(
            content=[
                {"type": "text", "text": SOM_VISION_PROMPT.format(task_desc=task_desc)},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        )
        
        # 4. 调用视觉大模型 (Invoke Vision LLM) — 同步调用
        try:
            res = vision_llm.invoke([msg])
        except Exception as e_vision:
            logger.warning(f"[SoM/Sync] Vision model call failed: {e_vision}")
            return None

        content = res.content.strip().replace("```json", "").replace("```", "")
        
        result = _json.loads(content)
        som_id = result.get("id")
        
        # 5. 清理标记 (Cleanup) — 同步调用
        page.evaluate("document.querySelectorAll('.som-marker').forEach(e => e.remove());")
        
        if som_id:
            logger.info(f"[SoM/Sync] Target identified: ID {som_id}")
            return som_id
            
    except Exception as e:
        logger.warning(f"[SoM/Sync] Analysis failed: {e}")
        try:
             page.evaluate("document.querySelectorAll('.som-marker').forEach(e => e.remove());")
        except Exception:
            pass  # Cleanup failure is not critical
    
    return None

async def get_clean_html(page):
    """
    Get a CLEAN and VISIBLE-ONLY DOM snapshot using JavaScript.
    This avoids sending hidden elements (like old compatibility inputs) to the LLM.
    """
    VISIBILITY_JS = """
    (function() {
        function isVisible(el) {
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
        }

        function traverse(node, depth) {
            if (depth > 20) return ''; // Prevent deep recursion
            
            if (node.nodeType === Node.TEXT_NODE) {
                const text = node.textContent.trim();
                return text ? text + ' ' : '';
            }
            
            if (node.nodeType !== Node.ELEMENT_NODE) return '';
            
            const el = node;
            if (!isVisible(el)) return '';

            let tagName = el.tagName.toLowerCase();
            
            // Skip irrelevant tags
            if (['script', 'style', 'svg', 'noscript', 'meta', 'link'].includes(tagName)) return '';

            let attrs = '';
            if (el.id) attrs += ` id="${el.id}"`;
            if (el.className) attrs += ` class="${el.className}"`; // Keep class for context
            if (el.name) attrs += ` name="${el.name}"`;
            if (el.placeholder) attrs += ` placeholder="${el.placeholder}"`;
            if (el.type) attrs += ` type="${el.type}"`;
            if (el.value && tagName === 'input') attrs += ` value="${el.value}"`; // Critical for inputs
            if (el.getAttribute('role')) attrs += ` role="${el.getAttribute('role')}"`;
            if (el.getAttribute('aria-label')) attrs += ` aria-label="${el.getAttribute('aria-label')}"`;
            
            // Interaction Check
            const isInteractive = ['a', 'button', 'input', 'textarea', 'select', 'form'].includes(tagName) || 
                                  el.onclick != null || 
                                  el.getAttribute('role') === 'button';
            
            // Recursive Traversal
            let inner = '';
            el.childNodes.forEach(child => {
                inner += traverse(child, depth + 1);
            });
            
            // Optimization: Strip layout tags if no semantic value
            if (!isInteractive && ['div', 'span', 'section', 'ul', 'li', 'td'].includes(tagName)) {
                 if (!el.id && !el.getAttribute('aria-label') && !el.className.includes('wrapper') && !el.className.includes('container')) {
                     return inner;
                 }
            }

            // Cleanup empty tags
            if (!isInteractive && !inner.trim()) return '';

            return `<${tagName}${attrs}>${inner}</${tagName}>`;
        }
        return traverse(document.body, 0);
    })();
    """
    
    try:
        html = await page.evaluate(VISIBILITY_JS)
        # Post-processing
        import re
        html = re.sub(r'\s+', ' ', html).strip()
        return html[:15000] # Token limit
    except Exception as e:
        logger.warning(f"[Browser] JS DOM Snapshot failed: {e}")
        # Fallback
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        for s in soup(["script", "style", "svg", "head"]):
            s.extract()
        return soup.prettify()[:15000]

async def find_selector(html, desc):
    """Use LLM to find the CSS selector (Async)"""
    prompt = ChatPromptTemplate.from_template(FIND_SELECTOR_PROMPT)
    try:
        from core.llm_manager import get_llm_for_role
        llm = get_llm_for_role("executor")
        chain = prompt | llm
        result = await chain.ainvoke({"html": html[:5000], "desc": desc})
        selector = result.content.strip().strip('`').strip('"').strip("'")
        if selector == "NOT_FOUND":
            return None
    except Exception as e:
        logger.warning(f"[Browser] find_selector failed: {e}")
        return None
    
    # Heuristic Validation & Correction
    if ("按钮" in desc or "点击" in desc or "提交" in desc) and selector == "#kw":
        logger.warning(f"[Browser] Heuristic: desc contains 'button' but selector is search box #{selector}, correcting...")
        if "百度" in desc or "baidu" in desc.lower():
            selector = "#su"
            logger.info(f"[Browser] Corrected to Baidu button: {selector}")
        else:
            if "一下" in desc or "搜索" in desc:
                selector = "#su"
                logger.info(f"[Browser] Corrected to button selector: {selector}")
    
    return selector


# ============================================================
# Phase 3: 页面状态感知增强
# ============================================================

# --- 共享 JS 脚本常量（sync/async 共用）---

_VISIBLE_TEXT_JS = """
() => {
    const walker = document.createTreeWalker(
        document.body, NodeFilter.SHOW_TEXT,
        { acceptNode: function(node) {
            const p = node.parentElement;
            if (!p) return NodeFilter.FILTER_REJECT;
            const tag = p.tagName.toLowerCase();
            if (['script','style','noscript'].includes(tag)) return NodeFilter.FILTER_REJECT;
            const s = window.getComputedStyle(p);
            if (s.display === 'none' || s.visibility === 'hidden') return NodeFilter.FILTER_REJECT;
            if (!node.textContent.trim() || node.textContent.trim().length < 2) return NodeFilter.FILTER_REJECT;
            return NodeFilter.FILTER_ACCEPT;
        }}
    );
    const texts = []; let total = 0;
    while (walker.nextNode() && total < 2000) {
        const t = walker.currentNode.textContent.trim();
        texts.push(t); total += t.length;
    }
    return texts.join(' | ');
}
"""

_SCROLL_JS = """
() => {
    const docH = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
    const viewH = window.innerHeight;
    const scrollT = window.scrollY || document.documentElement.scrollTop;
    const below = Math.max(0, docH - viewH - scrollT);
    return {
        can_scroll_down: below > 50,
        can_scroll_up: scrollT > 50,
        pixels_below: Math.round(below),
        scroll_percent: Math.round((scrollT / Math.max(1, docH - viewH)) * 100)
    };
}
"""

_ALERTS_JS = """
() => {
    const alerts = [];
    document.querySelectorAll('dialog[open], [role="dialog"], [role="alertdialog"]')
        .forEach(el => {
            const t = (el.textContent || '').trim().substring(0, 80);
            if (t) alerts.push('弹窗: ' + t);
        });
    document.querySelectorAll('.modal.show, .modal.active, [class*="modal"][style*="display: block"]')
        .forEach(el => {
            const t = (el.textContent || '').trim().substring(0, 80);
            if (t && !alerts.some(a => a.includes(t.substring(0, 20))))
                alerts.push('模态框: ' + t);
        });
    return alerts;
}
"""


def _new_page_state() -> dict:
    """创建空白的页面状态字典。"""
    return {
        "url": "", "title": "",
        "interactive_elements": "", "element_count": 0,
        "visible_text": "", "scroll_info": {},
        "alerts": [], "new_elements": [],
    }


def _process_dom_indexer(state: dict, dom_indexer, label: str = "PageState") -> None:
    """将 dom_indexer 的扫描结果填充到 state 中（scan 需在调用前完成）。"""
    try:
        state["interactive_elements"] = dom_indexer.format_for_llm()
        state["element_count"] = len(dom_indexer._index_map)
        new_els = dom_indexer.get_new_elements()
        if new_els:
            state["new_elements"] = [
                f"*[{el['idx']}]<{el['tag']}>{el['text']}"
                for el in new_els[:10]
            ]
    except Exception as e:
        logger.warning(f"[{label}] Element indexing failed: {e}")


def _fill_evaluate_results(state: dict, visible_text, scroll, alerts) -> None:
    """将 JS evaluate 结果填充到 state 中。"""
    state["visible_text"] = (visible_text or "")[:800]
    state["scroll_info"] = scroll or {}
    state["alerts"] = alerts or []


def get_page_state(page) -> dict:
    """
    获取结构化页面状态（sync 版本）。
    集成 DomIndexer 的元素索引 + 页面元信息 + 弹窗/滚动检测。
    """
    from core.dom_indexer import dom_indexer

    state = _new_page_state()

    try:
        state["url"] = page.url
        state["title"] = page.title()
    except Exception:
        pass

    # 交互元素索引
    try:
        dom_indexer.scan(page)
        _process_dom_indexer(state, dom_indexer, "PageState")
    except Exception as e:
        logger.warning(f"[PageState] Element scan failed: {e}")

    # JS evaluate: 可见文本 / 滚动 / 弹窗
    visible_text = scroll = alerts = None
    try:
        visible_text = page.evaluate(_VISIBLE_TEXT_JS)
    except Exception as e:
        logger.warning(f"[PageState] Text extraction failed: {e}")
    try:
        scroll = page.evaluate(_SCROLL_JS)
    except Exception:
        pass
    try:
        alerts = page.evaluate(_ALERTS_JS)
    except Exception:
        pass

    _fill_evaluate_results(state, visible_text, scroll, alerts)
    return state


def format_page_state_for_log(state: dict) -> str:
    """将页面状态格式化为简洁的日志文本"""
    lines = [
        f"📍 URL: {state.get('url', 'N/A')}",
        f"📄 Title: {state.get('title', 'N/A')}",
        f"🔢 可交互元素: {state.get('element_count', 0)} 个",
    ]
    scroll = state.get('scroll_info', {})
    if scroll:
        s = f"↕ 滚动: {scroll.get('scroll_percent', 0)}%"
        if scroll.get('can_scroll_down'):
            s += f" (下方 {scroll.get('pixels_below', '?')}px)"
        lines.append(s)
    alerts = state.get('alerts', [])
    if alerts:
        lines.append(f"⚠️ 弹窗: {', '.join(alerts[:3])}")
    new_els = state.get('new_elements', [])
    if new_els:
        lines.append(f"✨ 新元素: {', '.join(new_els[:5])}")
    return "\n".join(lines)


# ============================================================
# Phase 5: Async 版页面状态获取
# ============================================================

async def async_get_page_state(page) -> dict:
    """
    获取结构化页面状态（async 版本，Phase 5）。
    使用 await page.evaluate() 适配 async Playwright。
    """
    from core.dom_indexer import dom_indexer

    state = _new_page_state()

    try:
        state["url"] = page.url
        state["title"] = await page.title()
    except Exception:
        pass

    # 交互元素索引
    try:
        await dom_indexer.async_scan(page)
        _process_dom_indexer(state, dom_indexer, "PageState/Async")
    except Exception as e:
        logger.warning(f"[PageState/Async] Element scan failed: {e}")

    # JS evaluate: 可见文本 / 滚动 / 弹窗
    visible_text = scroll = alerts = None
    try:
        visible_text = await page.evaluate(_VISIBLE_TEXT_JS)
    except Exception as e:
        logger.warning(f"[PageState/Async] Text extraction failed: {e}")
    try:
        scroll = await page.evaluate(_SCROLL_JS)
    except Exception:
        pass
    try:
        alerts = await page.evaluate(_ALERTS_JS)
    except Exception:
        pass

    _fill_evaluate_results(state, visible_text, scroll, alerts)
    return state


class SharedBrowser:
    """
    Singleton wrapper for accessing the shared browser instance from tools.
    Compatible with skills.core_browser_client.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            # SharedBrowser inherits from object by default in Py3
            cls._instance = super(SharedBrowser, cls).__new__(cls)
        return cls._instance

    def _resolve_session_id(self, session_id: str = "default_session") -> str:
        from core.session_manager import SessionManager
        if not session_id or session_id == "default":
            return SessionManager.DEFAULT_SESSION_ID
        return session_id
    
    async def get_page(self, session_id: str = "default_session"):
        """Get the current active page from SessionManager"""
        from core.session_manager import session_manager
        return session_manager.get_session(self._resolve_session_id(session_id)).get_page()

    async def run_browser(self, callback, session_id: str = "default_session", timeout: float = 10.0):
        """Safely execute browser operations via SessionState bridge."""
        from core.session_manager import session_manager
        session = session_manager.get_session(self._resolve_session_id(session_id))
        return await session.run_browser(callback, timeout=timeout)


class BridgedBrowserLocator:
    """通过 SessionState 桥接执行 locator 操作。"""

    def __init__(self, browser: SharedBrowser, session_id: str, selector: str):
        self.browser = browser
        self.session_id = browser._resolve_session_id(session_id)
        self.selector = selector

    @property
    def first(self):
        return self

    async def fill(self, value, timeout: int = 5000):
        return await self.browser.run_browser(
            lambda page: page.locator(self.selector).first.fill(value, timeout=timeout),
            session_id=self.session_id,
            timeout=max(10.0, timeout / 1000 + 5),
        )

    async def click(self, timeout: int = 5000):
        return await self.browser.run_browser(
            lambda page: page.locator(self.selector).first.click(timeout=timeout),
            session_id=self.session_id,
            timeout=max(10.0, timeout / 1000 + 5),
        )

    async def input_value(self):
        return await self.browser.run_browser(
            lambda page: page.locator(self.selector).first.input_value(),
            session_id=self.session_id,
            timeout=10.0,
        )

    async def inner_text(self):
        return await self.browser.run_browser(
            lambda page: page.locator(self.selector).first.inner_text(),
            session_id=self.session_id,
            timeout=10.0,
        )

    async def get_attribute(self, name: str):
        return await self.browser.run_browser(
            lambda page: page.locator(self.selector).first.get_attribute(name),
            session_id=self.session_id,
            timeout=10.0,
        )


class BridgedElementHandle:
    """使用 selector + index 重建 element 操作，避免跨线程传递真实句柄。"""

    def __init__(self, browser: SharedBrowser, session_id: str, selector: str, index: int = 0):
        self.browser = browser
        self.session_id = browser._resolve_session_id(session_id)
        self.selector = selector
        self.index = index

    def _with_locator(self, page):
        return page.locator(self.selector).nth(self.index)

    async def get_attribute(self, name: str):
        return await self.browser.run_browser(
            lambda page: self._with_locator(page).get_attribute(name),
            session_id=self.session_id,
            timeout=10.0,
        )

    async def inner_text(self):
        return await self.browser.run_browser(
            lambda page: self._with_locator(page).inner_text(),
            session_id=self.session_id,
            timeout=10.0,
        )

    async def click(self, timeout: int = 5000):
        return await self.browser.run_browser(
            lambda page: self._with_locator(page).click(timeout=timeout),
            session_id=self.session_id,
            timeout=max(10.0, timeout / 1000 + 5),
        )

    async def fill(self, value, timeout: int = 5000):
        return await self.browser.run_browser(
            lambda page: self._with_locator(page).fill(value, timeout=timeout),
            session_id=self.session_id,
            timeout=max(10.0, timeout / 1000 + 5),
        )


class BridgedBrowserPage:
    """为 legacy async 工具提供 page-like 接口，但底层走 SessionState 桥接。"""

    def __init__(self, session_id: str = "default_session", browser: SharedBrowser | None = None):
        self.browser = browser or SharedBrowser()
        self.session_id = self.browser._resolve_session_id(session_id)
        self._last_known_url = ""

    def locator(self, selector: str) -> BridgedBrowserLocator:
        return BridgedBrowserLocator(self.browser, self.session_id, selector)

    async def goto(self, url: str, wait_until: str = "load", timeout: int = 30000):
        current_url = await self.browser.run_browser(
            lambda page: (page.goto(url, wait_until=wait_until, timeout=timeout), page.url)[1],
            session_id=self.session_id,
            timeout=max(30.0, timeout / 1000 + 5),
        )
        self._last_known_url = current_url or url
        return current_url

    async def click(self, selector: str):
        return await self.browser.run_browser(
            lambda page: page.click(selector),
            session_id=self.session_id,
            timeout=10.0,
        )

    async def fill(self, selector: str, value):
        return await self.browser.run_browser(
            lambda page: page.fill(selector, value),
            session_id=self.session_id,
            timeout=10.0,
        )

    async def title(self):
        return await self.browser.run_browser(
            lambda page: page.title(),
            session_id=self.session_id,
            timeout=10.0,
        )

    async def current_url(self):
        current_url = await self.browser.run_browser(
            lambda page: page.url,
            session_id=self.session_id,
            timeout=10.0,
        )
        self._last_known_url = current_url or self._last_known_url
        return self._last_known_url

    @property
    def url(self):
        return self._last_known_url

    async def inner_text(self, selector: str):
        return await self.browser.run_browser(
            lambda page: page.inner_text(selector),
            session_id=self.session_id,
            timeout=10.0,
        )

    async def evaluate(self, script):
        return await self.browser.run_browser(
            lambda page: page.evaluate(script),
            session_id=self.session_id,
            timeout=20.0,
        )

    async def wait_for_selector(self, selector: str, timeout: int = 5000):
        return await self.browser.run_browser(
            lambda page: page.wait_for_selector(selector, timeout=timeout),
            session_id=self.session_id,
            timeout=max(10.0, timeout / 1000 + 5),
        )

    async def go_back(self):
        return await self.browser.run_browser(
            lambda page: page.go_back(),
            session_id=self.session_id,
            timeout=10.0,
        )

    async def reload(self):
        return await self.browser.run_browser(
            lambda page: page.reload(),
            session_id=self.session_id,
            timeout=10.0,
        )

    async def is_visible(self, selector: str):
        return await self.browser.run_browser(
            lambda page: page.is_visible(selector),
            session_id=self.session_id,
            timeout=10.0,
        )

    async def content(self):
        return await self.browser.run_browser(
            lambda page: page.content(),
            session_id=self.session_id,
            timeout=10.0,
        )

    async def screenshot(self, **kwargs):
        timeout = kwargs.get("timeout", 5000)
        return await self.browser.run_browser(
            lambda page: page.screenshot(**kwargs),
            session_id=self.session_id,
            timeout=max(20.0, timeout / 1000 + 5),
        )

    async def query_selector(self, selector: str):
        count = await self.browser.run_browser(
            lambda page: page.locator(selector).count(),
            session_id=self.session_id,
            timeout=10.0,
        )
        if not count:
            return None
        return BridgedElementHandle(self.browser, self.session_id, selector, 0)

    async def query_selector_all(self, selector: str):
        count = await self.browser.run_browser(
            lambda page: page.locator(selector).count(),
            session_id=self.session_id,
            timeout=10.0,
        )
        return [
            BridgedElementHandle(self.browser, self.session_id, selector, index)
            for index in range(count or 0)
        ]


async def get_bridged_page(session_id: str = "default_session") -> BridgedBrowserPage | None:
    browser = SharedBrowser()
    if await browser.get_page(session_id=session_id) is None:
        return None
    return BridgedBrowserPage(session_id=session_id, browser=browser)
