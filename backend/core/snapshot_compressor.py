# -*- coding: utf-8 -*-
"""
Snapshot 压缩器 — 将页面状态压缩为最小 Token 的紧凑格式
借鉴 agent-browser 的可访问性树压缩技术
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class SnapshotCompressor:
    """
    将 DomIndexer 的元素列表 + 页面状态压缩为紧凑的 Snapshot 格式。
    用于 Smart Mode Planner 的输入，进一步减少 Token 消耗。

    输出示例:
        URL: https://baidu.com | 百度一下
        ---
        [1] input "搜索" (focused)
        [2] button "百度一下"
        [3] link "新闻"
        ---
        Scroll: 0% | Alerts: 0
    """

    def compress(
        self,
        elements_text: str,
        page_state: Dict[str, Any],
        max_visible_text: int = 200
    ) -> str:
        """
        生成超压缩页面快照。

        Args:
            elements_text: DomIndexer.format_for_llm() 输出
            page_state: 包含 url, title, visible_text, scroll_info, alerts 的字典
            max_visible_text: visible_text 摘要长度

        Returns:
            压缩后的 snapshot 字符串
        """
        url = page_state.get("url", "（未知）")
        title = page_state.get("title", "")
        scroll_info = page_state.get("scroll_info", {})
        alerts = page_state.get("alerts", [])
        visible_text = page_state.get("visible_text", "")

        lines = []

        # Header: URL + Title
        header = f"URL: {url}"
        if title:
            header += f" | {title}"
        lines.append(header)

        # Elements
        if elements_text and elements_text.strip() != "（页面未加载）":
            lines.append("---")
            lines.append(elements_text.strip())
            lines.append("---")
        else:
            lines.append("（页面未加载或无可交互元素）")

        # Footer: Scroll + Alerts + visible_text 摘要
        footer_parts = []

        scroll_pct = scroll_info.get("percent", 0) if isinstance(scroll_info, dict) else 0
        footer_parts.append(f"Scroll: {scroll_pct}%")

        if alerts:
            footer_parts.append(f"Alerts: {len(alerts)}")

        lines.append(" | ".join(footer_parts))
        
        if alerts:
            for a in alerts[:3]:
                lines.append(f"  ⚠ {str(a)[:60]}")

        # 可选: 极简 visible_text 摘要（只在没有 elements 时才有用）
        if visible_text and (not elements_text or elements_text.strip() == "（页面未加载）"):
            summary = visible_text[:max_visible_text].replace("\n", " ").strip()
            if summary:
                lines.append(f"Text: {summary}")

        return "\n".join(lines)

    def estimate_tokens(self, snapshot: str) -> int:
        """粗略估算 Token 数（1 token ≈ 4 字符 / 1.5 中文字）"""
        ascii_count = sum(1 for c in snapshot if ord(c) < 128)
        cjk_count = len(snapshot) - ascii_count
        return int(ascii_count / 4 + cjk_count / 1.5)


# 模块级单例
snapshot_compressor = SnapshotCompressor()
