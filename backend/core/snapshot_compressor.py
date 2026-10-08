# -*- coding: utf-8 -*-
"""
Snapshot compressor — compact page state with minimal tokens
Inspired by agent-browser accessibility tree compression
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class SnapshotCompressor:
    """
    Compress the DomIndexer element list and page state into a compact snapshot.
    Use as Smart Mode Planner input to further reduce token usage.

    Example output:
        URL: https://example.com | Example search
        ---
        [1] input "Search" (focused)
        [2] button "Search"
        [3] link "News"
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
        Generate a highly compressed page snapshot.

        Args:
            elements_text: Output from DomIndexer.format_for_llm()
            page_state: Dictionary containing url, title, visible_text, scroll_info, and alerts
            max_visible_text: Length of the visible_text summary

        Returns:
            Compressed snapshot string
        """
        url = page_state.get("url", "(Unknown)")
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
        if elements_text and elements_text.strip() not in ("(Page not loaded)", "（页面未加载）"):
            lines.append("---")
            lines.append(elements_text.strip())
            lines.append("---")
        else:
            lines.append("(Page not loaded or no interactive elements)")

        # Footer: scroll, alerts, and visible_text summary
        footer_parts = []

        scroll_pct = scroll_info.get("percent", 0) if isinstance(scroll_info, dict) else 0
        footer_parts.append(f"Scroll: {scroll_pct}%")

        if alerts:
            footer_parts.append(f"Alerts: {len(alerts)}")

        lines.append(" | ".join(footer_parts))
        
        if alerts:
            for a in alerts[:3]:
                lines.append(f"  ⚠ {str(a)[:60]}")

        # Optional minimal visible_text summary, useful only when elements are absent
        if visible_text and (not elements_text or elements_text.strip() in ("(Page not loaded)", "（页面未加载）")):
            summary = visible_text[:max_visible_text].replace("\n", " ").strip()
            if summary:
                lines.append(f"Text: {summary}")

        return "\n".join(lines)

    def estimate_tokens(self, snapshot: str) -> int:
        """Estimate tokens roughly (1 token ≈ 4 characters / 1.5 CJK characters)"""
        ascii_count = sum(1 for c in snapshot if ord(c) < 128)
        cjk_count = len(snapshot) - ascii_count
        return int(ascii_count / 4 + cjk_count / 1.5)


# Module singleton
snapshot_compressor = SnapshotCompressor()
