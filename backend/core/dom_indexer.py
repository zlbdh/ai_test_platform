"""
智能 DOM 元素索引器 (Phase 1)
参考 browser-use 的 AX Tree 索引设计。
扫描页面所有可交互元素，给每个元素编号。
Executor 通过索引号或语义文本匹配来定位元素，而非依赖 CSS Selector。
"""
import json
import logging
import time
import re
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


# ============================================================
# JS：注入到页面中，扫描所有可交互元素并返回索引
# ============================================================
SCAN_JS = """
() => {
    // 所有可交互元素的选择器
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

        // 过滤不可见元素
        if (rect.width <= 0 || rect.height <= 0) return;
        if (style.display === 'none' || style.visibility === 'hidden') return;
        if (style.opacity === '0') return;

        // 过滤视口之外的元素 (允许一定容差)
        if (rect.bottom < -50 || rect.top > window.innerHeight + 50) return;
        if (rect.right < -50 || rect.left > window.innerWidth + 50) return;

        index++;

        // 提取语义信息
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

        // 构造最佳描述
        let description = ariaLabel || text || placeholder || title || alt || name || id;
        if (!description && tag === 'input') {
            description = type ? `${type} input` : 'input';
        }
        if (!description && href) {
            description = href.substring(0, 60);
        }

        // 标记索引到元素上（供后续定位使用）
        el.setAttribute('data-ai-idx', index);

        // 生成一个足够唯一的 CSS Selector 作为后备
        let cssSelector = '';
        if (id) {
            cssSelector = '#' + CSS.escape(id);
        } else if (name && tag === 'input') {
            cssSelector = `${tag}[name="${name}"]`;
        } else {
            // 使用 data-ai-idx
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
            // 额外属性用于模糊匹配
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
    页面可交互元素索引器。
    每次调用 scan(page) 会为页面中所有可交互元素生成带编号的索引，
    并支持通过索引号或语义文本来定位元素。
    """

    def __init__(self):
        self._index_map = {}      # {idx: element_info}
        self._prev_index_map = {} # 上一次的索引（用于检测新元素）
        self._scan_time = 0

    def scan(self, page) -> dict:
        """
        扫描页面，建立元素索引。
        返回索引映射 {idx: {tag, type, text, selector, ...}}
        """
        try:
            elements = page.evaluate(SCAN_JS)
        except Exception as e:
            logger.error(f"[DomIndexer] 扫描失败: {e}")
            return self._index_map

        # 保存上一次的索引
        self._prev_index_map = dict(self._index_map)

        # 构建新索引
        self._index_map = {}
        for el in (elements or []):
            self._index_map[el['idx']] = el

        self._scan_time = time.time()
        if not self._index_map:
            logger.warning("[DomIndexer] 扫描完成但未发现任何可交互元素，页面可能未完全加载或无交互控件")
        return self._index_map

    def get_new_elements(self) -> list:
        """检测与上次扫描相比新出现的元素（通过文本比较）"""
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
        生成适合 LLM 消费的元素列表（紧凑格式，优化 Token）。
        格式参考 browser-use / agent-browser:
        [1] input "搜索关键词" (type='text')
        [2] button "百度一下"
        *[3] div "新出现的弹窗"
        """
        if not self._index_map:
            return "(页面无可交互元素)"

        new_elements = self.get_new_elements()
        new_idxs = {el['idx'] for el in new_elements}

        lines = []
        items = sorted(self._index_map.items())[:max_items]

        for idx, el in items:
            prefix = "*" if idx in new_idxs else ""  # 新元素标 *
            tag = el['tag']
            text = el['text']

            # 附加属性（紧凑格式）
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
            lines.append(f"... (共 {len(self._index_map)} 个元素, 已显示前 {max_items} 个)")

        return "\n".join(lines)

    def find_by_index(self, idx: int) -> dict | None:
        """通过索引号获取元素信息"""
        return self._index_map.get(idx)

    def find_by_text(self, text: str, threshold: float = 0.4) -> dict | None:
        """
        通过语义文本模糊匹配元素。
        用于当 LLM 给出描述性文本（如 "搜索框"、"百度一下"）时定位。
        
        匹配策略：
        1. 精确子串匹配
        2. 模糊匹配 (SequenceMatcher)
        3. 语义角色匹配（根据中文关键词推断元素类型）
        """
        text_lower = text.lower().strip()

        # 1. 精确子串匹配
        for idx, el in self._index_map.items():
            all_text = el.get('_all_text', '')
            if text_lower in all_text:
                return el

        # 2. 模糊匹配
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

        # 3. 语义角色匹配
        # 根据中文描述推断目标元素类型（一个关键词可匹配多种 tag）
        role_keywords = {
            ('input', 'textarea'): ['输入框', '搜索框', '文本框', '输入', '填写', '搜索栏', '搜索'],
            ('button',): ['按钮', '点击', '提交', '确定', '确认', '搜索按钮'],
            ('a',): ['链接', '跳转', '导航'],
            ('select',): ['下拉框', '选择框', '下拉', '选择'],
            ('textarea',): ['文本域', '多行输入', '评论框', '留言框'],
        }
        
        target_tags = set()
        for tags, keywords in role_keywords.items():
            for kw in keywords:
                if kw in text_lower:
                    target_tags.update(tags)
                    break
        
        if target_tags:
            # 在匹配类型的元素中找最佳候选
            candidates = [
                el for el in self._index_map.values()
                if el.get('tag') in target_tags
            ]
            
            if len(candidates) == 1:
                return candidates[0]
            
            # 如果有多个同类型候选，用文本打分
            if candidates:
                # 特殊处理：如果描述中含有"搜索"且有搜索输入框
                for c in candidates:
                    c_text = c.get('_all_text', '')
                    c_selector = c.get('selector', '')
                    # 检查 placeholder/id/class 是否暗示搜索功能
                    if '搜索' in text_lower and any(
                        kw in (c_text + ' ' + c_selector).lower() 
                        for kw in ['搜索', 'search', '请输入', '关键词', 'query', 'keyword', 'chat-textarea', 'kw']
                    ):
                        return c
                
                # 退而求其次：选择最显眼的（面积最大的）同类型元素
                best_candidate = max(candidates, key=lambda c: (
                    c.get('rect', {}).get('w', 0) * c.get('rect', {}).get('h', 0)
                ))
                return best_candidate

        return None

    def resolve_target(self, target: str) -> tuple[str, str]:
        """
        智能解析 target 字段，返回 (selector, method)。
        
        支持四种定位方式：
        1. 索引号: "[5]" 或 "5" (纯数字) → 用 data-ai-idx
        2. CSS Selector: "#id" 或 ".class" → 直接透传
        3. 描述性文本: "搜索框" "百度一下" → 语义匹配
        4. Fallback: 原样返回，executor 会尝试 Playwright 语义定位器

        返回: (css_selector, "index" | "selector" | "text" | "fallback")
        """
        target = target.strip()

        # 1. 索引号格式: [5] 或纯数字
        idx_match = re.match(r'^\[?(\d+)\]?$', target)
        if idx_match:
            idx = int(idx_match.group(1))
            el = self.find_by_index(idx)
            if el:
                return el['selector'], "index"
            else:
                # 即使不在索引中，也将其作为 index 选择器返回，由 Playwright 处理找不到的异常
                # 这样可以避免 fallthrough 后被误认为是非法的 CSS Selector
                return f'[data-ai-idx="{idx}"]', "index"

        # 2. CSS Selector 格式（以 # . [ 开头 或含有 = 等）
        if re.match(r'^[#.\[]', target) or (re.match(r'^[a-z]', target) and any(c in target for c in '[]=>')):
            return target, "selector"

        # 3. 描述性文本 → 多层语义匹配
        el = self.find_by_text(target)
        if el:
            return el['selector'], "text"

        # 4. Fallback: 原样返回（executor 会尝试 Playwright 语义定位器）
        return target, "fallback"

    async def async_scan(self, page) -> dict:
        """
        异步版扫描（Phase 5），适配 async Playwright。
        """
        try:
            elements = await page.evaluate(SCAN_JS)
        except Exception as e:
            logger.error(f"[DomIndexer] 异步扫描失败: {e}")
            return self._index_map

        self._prev_index_map = dict(self._index_map)
        self._index_map = {}
        for el in (elements or []):
            self._index_map[el['idx']] = el

        self._scan_time = time.time()
        return self._index_map


# 全局单例
dom_indexer = DomIndexer()
