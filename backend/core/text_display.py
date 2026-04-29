# -*- coding: utf-8 -*-
"""
中文任务文本展示辅助。

区分：
1. raw：原始输入，保留给诊断与 planner
2. display：用户可见标题，避免把明显损坏的文本继续扩散到状态、历史和通知
"""
from __future__ import annotations

import re
from typing import Optional, Tuple


BROKEN_TEXT_STATE = "broken_fallback"
NORMAL_TEXT_STATE = "normal"


def looks_broken_text(value: Optional[str]) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    if "�" in text:
        return True
    if text.startswith("http://") or text.startswith("https://"):
        return False

    if re.search(r"\?{3,}", text):
        return True

    non_whitespace = [char for char in text if not char.isspace()]
    if not non_whitespace:
        return True

    question_count = text.count("?")
    if question_count <= 0:
        return False

    question_ratio = question_count / len(non_whitespace)
    return question_count >= 4 and question_ratio >= 0.2


def resolve_display_text(
    raw_text: Optional[str],
    target_url: str = "",
    fallback: str = "未命名测试",
) -> Tuple[str, str]:
    raw = str(raw_text or "").strip()
    if not looks_broken_text(raw):
        return raw, NORMAL_TEXT_STATE

    display = str(target_url or "").strip() or fallback
    return display, BROKEN_TEXT_STATE


def build_broken_text_notice() -> str:
    return "需求文本疑似编码损坏，已回退为可读标题。"
