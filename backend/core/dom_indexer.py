"""
Intelligent DOM element indexer (Phase 1)
Based on the browser-use AX Tree indexing design.
Scan all interactive page elements and assign each an index.
The executor locates elements by index or semantic text matching without relying on CSS selectors.
"""
import json
import logging
import time
import re
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


# ============================================================
# JavaScript injected into the page to scan interactive elements and return indexes
# ============================================================
SCAN_JS = """
() => {
    // Selectors for all interactive elements
    const interactiveSelectors = [
        'a[href]',
        'button',
        'input:not([type="hidden"])',
        'textarea',
        'select',
        '[role="button"]',
        '[role="link"]',
        '[role="tab"]',
        '[role="menuitem"]',
        '[role="checkbox"]',
        '[role="radio"]',
        '[role="switch"]',
        '[role="combobox"]',
        '[role="searchbox"]',
        '[role="textbox"]',
        '[onclick]',
        '[tabindex]:not([tabindex="-1"])',
        'label[for]',
        'summary',
        '[contenteditable="true"]',
    ];

    const allSelector = interactiveSelectors.join(', ');
    const elements = document.querySelectorAll(allSelector);

    const results = [];
    let index = 0;

    elements.forEach(el => {
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);

        // Filter out invisible elements
        if (rect.width <= 0 || rect.height <= 0) return;
        if (style.display === 'none' || style.visibility === 'hidden') return;
        if (style.opacity === '0') return;

        // Filter out elements outside the viewport, with some tolerance
        if (rect.bottom < -50 || rect.top > window.innerHeight + 50) return;
        if (rect.right < -50 || rect.left > window.innerWidth + 50) return;

        index++;

        // Extract semantic information
        const tag = el.tagName.toLowerCase();
        const type = el.getAttribute('type') || '';
        const text = (el.innerText || '').trim().substring(0, 100);
        const ariaLabel = el.getAttribute('aria-label') || '';
        const placeholder = el.getAttribute('placeholder') || '';
        const title = el.getAttribute('title') || '';
        const value = el.value || '';
        const name = el.getAttribute('name') || '';
        const id = el.id || '';
        const role = el.getAttribute('role') || '';
        const href = el.getAttribute('href') || '';
        const alt = el.getAttribute('alt') || '';

        // Build the best description
        let description = ariaLabel || text || placeholder || title || alt || name || id;
        if (!description && tag === 'input') {
            description = type ? `${type} input` : 'input';
        }
        if (!description && href) {
            description = href.substring(0, 60);
        }

        // Mark the element with its index for subsequent location
        el.setAttribute('data-ai-idx', index);

        // Generate a sufficiently unique fallback CSS selector
        let cssSelector = '';
        if (id) {
            cssSelector = '#' + CSS.escape(id);
        } else if (name && tag === 'input') {
            cssSelector = `${tag}[name="${name}"]`;
        } else {
            // Use data-ai-idx
            cssSelector = `[data-ai-idx="${index}"]`;
        }

        results.push({
            idx: index,
            tag: tag,
            type: type,
            text: description.substring(0, 100),
            value: value.substring(0, 50),
            selector: cssSelector,
            role: role,
            rect: {
                x: Math.round(rect.x),
                y: Math.round(rect.y),
                w: Math.round(rect.width),
                h: Math.round(rect.height)
            },
            // Additional attributes for fuzzy matching
            _all_text: [text, ariaLabel, placeholder, title, name, id, alt]
                .filter(Boolean)
                .join(' ')
                .toLowerCase()
        });
    });

    return results;
}
"""


class DomIndexer:
    """
    Indexer for interactive page elements.
    Each scan(page) call creates numbered indexes for all interactive page elements,
    and supports element location by index or semantic text.
    """

    def __init__(self):
        self._index_map = {}      # {idx: element_info}
        self._prev_index_map = {} # Previous indexes, for detecting new elements
        self._scan_time = 0

    def scan(self, page) -> dict:
        """
        Scan the page and build element indexes.
        Return the index mapping {idx: {tag, type, text, selector, ...}}
        """
        try:
            elements = page.evaluate(SCAN_JS)
        except Exception as e:
            logger.error(f"[DomIndexer] Scan failed: {e}")
            return self._index_map

        # Save the previous indexes
        self._prev_index_map = dict(self._index_map)

        # Build new indexes
        self._index_map = {}
        for el in (elements or []):
            self._index_map[el['idx']] = el

        self._scan_time = time.time()
        if not self._index_map:
            logger.warning("[DomIndexer] Scan completed without interactive elements; the page may still be loading or have no interactive controls")
        return self._index_map

    def get_new_elements(self) -> list:
        """Detect newly appearing elements by comparing text with the previous scan"""
        if not self._prev_index_map:
            return []

        prev_texts = set(
            el.get('_all_text', '')
            for el in self._prev_index_map.values()
        )
        new_elements = []
        for idx, el in self._index_map.items():
            if el.get('_all_text', '') not in prev_texts:
                new_elements.append(el)
        return new_elements

    def format_for_llm(self, max_items: int = 80) -> str:
        """
        Generate a compact element list for LLM input, minimizing tokens.
        Format based on browser-use / agent-browser:
        [1] input "Search keywords" (type='text')
        [2] button "Search"
        *[3] div "New alert"
        """
        if not self._index_map:
            return "(No interactive page elements)"

        new_elements = self.get_new_elements()
        new_idxs = {el['idx'] for el in new_elements}

        lines = []
        items = sorted(self._index_map.items())[:max_items]

        for idx, el in items:
            prefix = "*" if idx in new_idxs else ""  # Mark new elements with *
            tag = el['tag']
            text = el['text']

            # Additional attributes in compact form
            attrs = []
            if el.get('type'):
                attrs.append(f"type='{el['type']}'")
            if el.get('role'):
                attrs.append(f"role='{el['role']}'")
            if el.get('value'):
                val = el['value'][:20]
                attrs.append(f"value='{val}'")

            attr_str = f" ({', '.join(attrs)})" if attrs else ''
            text_repr = f' "{text}"' if text else ''

            lines.append(f"{prefix}[{idx}] {tag}{text_repr}{attr_str}")

        if len(self._index_map) > max_items:
            lines.append(f"... ({len(self._index_map)} elements total; showing the first {max_items})")

        return "\n".join(lines)

    def find_by_index(self, idx: int) -> dict | None:
        """Get element information by index"""
        return self._index_map.get(idx)

    def find_by_text(self, text: str, threshold: float = 0.4) -> dict | None:
        """
        Fuzzy-match elements using semantic text.
        Locate elements when the LLM supplies descriptive text such as "Search field" or "Search".
        
        Matching strategies:
        1. Exact substring matching
        2. Fuzzy matching (SequenceMatcher)
        3. Semantic role matching (infer element types from descriptive keywords)
        """
        text_lower = text.lower().strip()

        # 1. Exact substring matching
        for idx, el in self._index_map.items():
            all_text = el.get('_all_text', '')
            if text_lower in all_text:
                return el

        # 2. Fuzzy matching
        best_match = None
        best_score = threshold
        for idx, el in self._index_map.items():
            all_text = el.get('_all_text', '')
            score = SequenceMatcher(None, text_lower, all_text).ratio()
            if score > best_score:
                best_score = score
                best_match = el

        if best_match:
            return best_match

        # 3. Semantic role matching
        # Infer target element types from descriptions; one keyword may match multiple tags
        role_keywords = {
            ('input', 'textarea'): ['输入框', '搜索框', '文本框', '输入', '填写', '搜索栏', '搜索', 'input', 'search field', 'text field', 'fill'],
            ('button',): ['按钮', '点击', '提交', '确定', '确认', '搜索按钮', 'button', 'click', 'submit', 'confirm'],
            ('a',): ['链接', '跳转', '导航', 'link', 'navigate'],
            ('select',): ['下拉框', '选择框', '下拉', '选择', 'dropdown', 'select'],
            ('textarea',): ['文本域', '多行输入', '评论框', '留言框', 'textarea', 'comment box', 'multiline'],
        }
        
        target_tags = set()
        for tags, keywords in role_keywords.items():
            for kw in keywords:
                if kw in text_lower:
                    target_tags.update(tags)
                    break
        
        if target_tags:
            # Find the best candidate among matching element types
            candidates = [
                el for el in self._index_map.values()
                if el.get('tag') in target_tags
            ]
            
            if len(candidates) == 1:
                return candidates[0]
            
            # Score by text when several candidates share the same type
            if candidates:
                # Special handling for search descriptions when a search input is available
                for c in candidates:
                    c_text = c.get('_all_text', '')
                    c_selector = c.get('selector', '')
                    # Check whether placeholder/id/class suggests search functionality
                    if ('搜索' in text_lower or 'search' in text_lower) and any(
                        kw in (c_text + ' ' + c_selector).lower() 
                        for kw in ['搜索', 'search', '请输入', '关键词', 'query', 'keyword', 'chat-textarea', 'kw']
                    ):
                        return c
                
                # Fallback: choose the most prominent matching element by area
                best_candidate = max(candidates, key=lambda c: (
                    c.get('rect', {}).get('w', 0) * c.get('rect', {}).get('h', 0)
                ))
                return best_candidate

        return None

    def resolve_target(self, target: str) -> tuple[str, str]:
        """
        Parse the target field and return (selector, method).
        
        Support four location methods:
        1. Index: "[5]" or "5" (digits only) → use data-ai-idx
        2. CSS selector: "#id" or ".class" → pass through directly
        3. Descriptive text: "Search field" or "Search" → semantic matching
        4. Fallback: return unchanged for the executor to try Playwright semantic locators

        Return: (css_selector, "index" | "selector" | "text" | "fallback")
        """
        target = target.strip()

        # 1. Index format: [5] or digits only
        idx_match = re.match(r'^\[?(\d+)\]?$', target)
        if idx_match:
            idx = int(idx_match.group(1))
            el = self.find_by_index(idx)
            if el:
                return el['selector'], "index"
            else:
                # Return an index selector even if absent from the index; let Playwright handle not-found errors
                # This prevents fallthrough from treating the input as an invalid CSS selector
                return f'[data-ai-idx="{idx}"]', "index"

        # 2. CSS selector format (starts with # . [ or contains =, etc.)
        if re.match(r'^[#.\[]', target) or (re.match(r'^[a-z]', target) and any(c in target for c in '[]=>')):
            return target, "selector"

        # 3. Descriptive text → layered semantic matching
        el = self.find_by_text(target)
        if el:
            return el['selector'], "text"

        # 4. Fallback: return unchanged for the executor to try Playwright semantic locators
        return target, "fallback"

    async def async_scan(self, page) -> dict:
        """
        Async scan (Phase 5) for async Playwright.
        """
        try:
            elements = await page.evaluate(SCAN_JS)
        except Exception as e:
            logger.error(f"[DomIndexer] Async scan failed: {e}")
            return self._index_map

        self._prev_index_map = dict(self._index_map)
        self._index_map = {}
        for el in (elements or []):
            self._index_map[el['idx']] = el

        self._scan_time = time.time()
        return self._index_map


# Global singleton
dom_indexer = DomIndexer()
