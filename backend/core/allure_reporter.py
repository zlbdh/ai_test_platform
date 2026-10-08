# -*- coding: utf-8 -*-
"""
Test report generator v3 — Playwright style
Generate HTML reports from test_runs with screenshots, step timelines, and highlighted errors
"""
import os
import json
import shutil
import subprocess
import uuid
import html as html_mod
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class TestStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    BROKEN = "broken"
    SKIPPED = "skipped"


@dataclass
class TestResult:
    name: str
    status: TestStatus
    duration: float
    description: str = ""
    steps: List[Dict] = field(default_factory=list)
    attachments: List[Dict] = field(default_factory=list)
    error_message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TestSuite:
    name: str
    results: List[TestResult] = field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    @property
    def total(self): return len(self.results)
    @property
    def passed(self): return sum(1 for r in self.results if r.status == TestStatus.PASSED)
    @property
    def failed(self): return sum(1 for r in self.results if r.status == TestStatus.FAILED)
    @property
    def success_rate(self): return (self.passed / self.total * 100) if self.total > 0 else 0
    @property
    def duration(self): return sum(r.duration for r in self.results)


def _esc(text) -> str:
    """Escape HTML to prevent XSS"""
    if text is None:
        return ""
    return html_mod.escape(str(text))


def _fmt_ms(ms) -> str:
    """Format milliseconds"""
    try:
        ms = int(ms)
    except (TypeError, ValueError):
        return "N/A"
    if ms < 1000:
        return f"{ms}ms"
    if ms < 60000:
        return f"{ms / 1000:.1f}s"
    return f"{ms / 60000:.1f}min"


def _fmt_sec(sec) -> str:
    """Format seconds"""
    try:
        sec = float(sec)
    except (TypeError, ValueError):
        return ""
    if sec < 1:
        return f"{sec * 1000:.0f}ms"
    if sec < 60:
        return f"{sec:.1f}s"
    return f"{sec / 60:.1f}min"


def _looks_broken_text(value: Optional[str]) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    if "�" in text:
        return True
    if text.startswith("http://") or text.startswith("https://"):
        return False
    return text.count("?") >= 2


def _compact_target_label(target_url: Optional[str]) -> str:
    raw = str(target_url or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
        if parsed.scheme and parsed.netloc:
            path = parsed.path if parsed.path and parsed.path != "/" else ""
            return f"{parsed.netloc}{path}"
    except Exception:
        pass
    return raw


def _build_report_title(
    scope: str,
    *,
    target_url: Optional[str] = None,
    base_name: Optional[str] = None,
    task_id: Optional[str] = None,
    record_count: int = 0,
) -> str:
    target_label = _compact_target_label(target_url)
    fallback_label = _short_text(base_name or task_id or "Test Record", 32)
    if scope == "batch":
        label = target_label or fallback_label or "Test Batch"
        return f"Specialized Test · {label} · Batch Report"
    if scope == "summary":
        if record_count > 0:
            return f"Recent {record_count} Test Records Summary"
        return "Recent Test Records Summary"
    label = target_label or fallback_label or "Test Record"
    return f"Test Record · {label} · Record Report"


_ACTION_LABELS = {
    "assert": "Assert",
    "check": "Check",
    "click": "Click",
    "fill": "Fill",
    "goto": "Visit",
    "hover": "Hover",
    "press": "Press key",
    "select": "Select",
    "wait": "Wait",
}

_INTERNAL_ISSUE_KEYWORDS = (
    "not enough balance",
    "quota",
    "api key",
    "llm",
    "推理失败",
    "预认证失败",
    "会话预认证失败",
    "浏览器已就绪",
    "browser",
    "model",
    "reasoning failed",
    "preauthentication failed",
    "pre-authentication failed",
)

_PRECONDITION_TARGET_KEYWORDS = (
    "登录",
    "重新登录",
    "切换站点",
    "站点",
    "城市",
    "北京市",
    "朝阳区",
    "sign in",
    "sign-in",
    "login",
    "switch site",
    "select city",
    "city selector",
    "Beijing",
    "Chaoyang",
)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _short_text(value: Any, limit: int = 48) -> str:
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    return f"{text[:max(limit - 3, 1)]}..."


def _contains_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _normalize_case_status(value: Any) -> str:
    lowered = str(value or "").strip().lower()
    if lowered in ("pass", "passed", "success", "ok"):
        return "pass"
    if lowered in ("fail", "failed", "error", "broken"):
        return "fail"
    return "unknown"


def _humanize_step(action: Any, target: Any, step: Any, fallback: Any = "") -> str:
    action_text = _clean_text(action).lower()
    target_text = _clean_text(target)
    step_text = _clean_text(step)
    fallback_text = _clean_text(fallback)

    if action_text == "assert":
        label = target_text or step_text.replace("assert(", "").rstrip(")")
        return f"Assertion: {label}" if label else "Assert"

    if target_text and action_text:
        return f"{_ACTION_LABELS.get(action_text, action_text)}: {target_text}"

    if step_text:
        return step_text

    if target_text:
        return target_text

    return fallback_text or "Untitled Test Case"


def _extract_missing_target(content: str) -> str:
    for marker in ("Could not find element:", "未找到元素:", "找不到元素:"):
        if marker in content:
            return _clean_text(content.split(marker, 1)[1])
    return ""


def _extract_test_cases(logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cases: Dict[str, Dict[str, Any]] = {}
    has_assertions = False

    for log in logs:
        if not isinstance(log, dict) or log.get("type") != "assertion":
            continue

        has_assertions = True
        key = f"assert:{log.get('step_index', '?')}:{log.get('step') or log.get('target') or log.get('content')}"
        cases[key] = {
            "title": _humanize_step(log.get("action"), log.get("target"), log.get("step"), log.get("content")),
            "status": _normalize_case_status(log.get("status")),
            "evidence": _clean_text(log.get("content")),
            "step": _clean_text(log.get("step")),
            "target": _clean_text(log.get("target")),
            "action": _clean_text(log.get("action")),
            "step_index": log.get("step_index"),
        }

    if has_assertions:
        return list(cases.values())

    for log in logs:
        if not isinstance(log, dict):
            continue
        if log.get("type") != "result" or log.get("event") != "step_result":
            continue
        if _clean_text(log.get("action")).lower() in ("goto", "wait"):
            continue

        status = _normalize_case_status(log.get("status"))
        if status == "unknown":
            continue

        key = f"result:{log.get('step_index', '?')}:{log.get('step') or log.get('target') or log.get('content')}"
        cases[key] = {
            "title": _humanize_step(log.get("action"), log.get("target"), log.get("step"), log.get("content")),
            "status": status,
            "evidence": _clean_text(log.get("content")),
            "step": _clean_text(log.get("step")),
            "target": _clean_text(log.get("target")),
            "action": _clean_text(log.get("action")),
            "step_index": log.get("step_index"),
        }

    return list(cases.values())


def _classify_issue_source(log: Dict[str, Any], content: str) -> str:
    raw_text = " ".join(
        part for part in (
            _clean_text(content),
            _clean_text(log.get("step")),
            _clean_text(log.get("target")),
            _clean_text(log.get("action")),
        ) if part
    )

    if _contains_keyword(raw_text, _INTERNAL_ISSUE_KEYWORDS):
        return "execution"

    if _contains_keyword(raw_text, _PRECONDITION_TARGET_KEYWORDS) and (
        "could not find element" in raw_text.lower()
        or "timeout" in raw_text.lower()
        or "未找到元素" in raw_text
        or "找不到元素" in raw_text
    ):
        return "execution"

    if log.get("type") == "assertion":
        return "platform"

    if (
        "could not find element" in raw_text.lower()
        or "timeout" in raw_text.lower()
        or "未找到元素" in raw_text
        or "找不到元素" in raw_text
        or "locator." in raw_text.lower()
    ):
        return "platform"

    return "execution"


def _build_issue_from_log(log: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    log_type = _clean_text(log.get("type"))
    content = _clean_text(log.get("content"))
    status = _normalize_case_status(log.get("status"))

    if log_type == "assertion" and status == "pass":
        return None

    if log_type == "error":
        if content.startswith("🧠 [Planner] Step "):
            return None
    elif log_type == "result":
        if status != "fail":
            return None
        if content.startswith("❌ error"):
            return None
    elif log_type != "assertion":
        return None

    step_title = _humanize_step(log.get("action"), log.get("target"), log.get("step"), content)
    missing_target = _extract_missing_target(content)
    source = _classify_issue_source(log, content)

    if log_type == "assertion":
        category = "Assertion Failed"
        target_text = missing_target or _clean_text(log.get("target")) or step_title.replace("Assertion: ", "", 1)
        summary = f"Assertion failed: {target_text}"
    elif "could not find element" in content.lower() or "未找到元素" in content or "找不到元素" in content:
        category = "Missing Page Element"
        target_text = missing_target or _clean_text(log.get("target")) or step_title
        summary = f"Expected page element is missing: {target_text}"
    elif "timeout" in content.lower():
        category = "Page Interaction Timeout"
        summary = f"Page interaction timed out: {step_title}"
    elif source == "execution":
        category = "Execution Infrastructure Error"
        summary = f"Execution infrastructure error: {_short_text(content, 28) or step_title}"
    else:
        category = "Execution Error"
        summary = f"Execution error: {step_title}"

    return {
        "summary": summary,
        "category": category,
        "source": source,
        "source_label": "Tested Platform" if source == "platform" else "Execution Infrastructure",
        "evidence": content or step_title,
        "related_step": step_title,
        "count": 1,
    }


def _extract_issues(logs: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    issue_map: Dict[tuple[str, str], Dict[str, Any]] = {}

    for log in logs:
        if not isinstance(log, dict):
            continue
        issue = _build_issue_from_log(log)
        if not issue:
            continue

        issue_key = (issue["source"], issue["summary"])
        if issue_key in issue_map:
            issue_map[issue_key]["count"] += 1
            continue

        issue_map[issue_key] = issue

    platform_issues = [issue for issue in issue_map.values() if issue["source"] == "platform"]
    execution_issues = [issue for issue in issue_map.values() if issue["source"] == "execution"]
    return platform_issues, execution_issues


def analyze_test_run(run: Dict[str, Any]) -> Dict[str, Any]:
    logs = run.get("logs") or []
    test_cases = _extract_test_cases(logs)
    platform_issues, execution_issues = _extract_issues(logs)
    case_passed = sum(1 for case in test_cases if case["status"] == "pass")
    case_failed = sum(1 for case in test_cases if case["status"] == "fail")

    return {
        "test_cases": test_cases,
        "case_count": len(test_cases),
        "case_passed": case_passed,
        "case_failed": case_failed,
        "platform_issues": platform_issues,
        "platform_issue_count": len(platform_issues),
        "execution_issues": execution_issues,
        "execution_issue_count": len(execution_issues),
    }


# ─────────────── Step parsing ───────────────
def _parse_execution_steps(logs: List[Dict]) -> List[Dict]:
    """
    Extract structured steps from raw execution logs.
    Organize thought→action→result→observation→assertion chains into readable steps.
    """
    steps = []
    step_num = 0

    for log in logs:
        log_type = log.get("type", "")
        content = log.get("content", "")

        if log_type == "thought":
            # AI reasoning: retain only key reasoning and filter out status messages
            if content.startswith("\U0001f4ad") or "正在推理" in content or "Reasoning..." in content:
                step_num += 1
                steps.append({
                    "num": step_num,
                    "type": "thought",
                    "icon": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>',
                    "label": "AI Reasoning",
                    "content": content,
                    "status": "info",
                    "screenshot": None,
                    "duration": None,
                })

        elif log_type == "action":
            step_num += 1
            steps.append({
                "num": step_num,
                "type": "action",
                "icon": '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>',
                "label": "Action",
                "content": log.get("step", content),
                "status": "running",
                "screenshot": None,
                "duration": None,
            })

        elif log_type == "result":
            status = log.get("status", "unknown")
            duration = log.get("duration")
            screenshot = log.get("screenshot")
            step_num += 1
            _icon_pass = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'
            _icon_fail = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>'
            steps.append({
                "num": step_num,
                "type": "result",
                "icon": _icon_pass if status == "success" else _icon_fail,
                "label": "Result",
                "content": log.get("step", content),
                "status": "pass" if status == "success" else "fail",
                "screenshot": screenshot,
                "duration": duration,
            })

        elif log_type == "assertion":
            status = log.get("status", "fail")
            step_num += 1
            _icon_pass = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'
            _icon_fail = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>'
            steps.append({
                "num": step_num,
                "type": "assertion",
                "icon": _icon_pass if status == "pass" else _icon_fail,
                "label": "Assertion Check",
                "content": content,
                "status": status,
                "screenshot": None,
                "duration": None,
            })

        elif log_type == "observation":
            step_num += 1
            steps.append({
                "num": step_num,
                "type": "observation",
                "icon": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>',
                "label": "Observation",
                "content": content,
                "status": "info",
                "screenshot": None,
                "duration": None,
            })

        elif log_type == "error":
            step_num += 1
            steps.append({
                "num": step_num,
                "type": "error",
                "icon": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
                "label": "Error",
                "content": content,
                "status": "fail",
                "screenshot": log.get("screenshot"),
                "duration": None,
            })

        elif log_type == "system":
            step_num += 1
            steps.append({
                "num": step_num,
                "type": "system",
                "icon": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/></svg>',
                "label": "System",
                "content": content,
                "status": "info",
                "screenshot": None,
                "duration": None,
            })

        elif log_type == "heal":
            step_num += 1
            steps.append({
                "num": step_num,
                "type": "heal",
                "icon": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>',
                "label": "Healing",
                "content": content,
                "status": "warn",
                "screenshot": None,
                "duration": None,
            })

    return steps


# ─────────────── HTML template ───────────────

_CSS = """
:root {
    --bg: #f8fafc;
    --surface: #ffffff;
    --surface-2: #f1f5f9;
    --surface-hover: #f8fafc;
    --border: #e2e8f0;
    --text: #1e293b;
    --text-2: #475569;
    --text-3: #64748b;
    --accent: #4f46e5;
    --accent-glow: rgba(79, 70, 229, 0.1);
    --pass: #16a34a;
    --pass-bg: rgba(22, 163, 74, 0.1);
    --pass-border: rgba(22, 163, 74, 0.2);
    --fail: #dc2626;
    --fail-bg: rgba(220, 38, 38, 0.1);
    --fail-border: rgba(220, 38, 38, 0.2);
    --warn: #d97706;
    --warn-bg: rgba(217, 119, 6, 0.1);
    --info-bg: rgba(79, 70, 229, 0.05);
}

[data-theme="dark"] {
    --bg: #0a0a1a;
    --surface: #12122a;
    --surface-2: #1a1a3a;
    --surface-hover: #22224a;
    --border: #2a2a4a;
    --text: #e8e8f0;
    --text-2: #a0a0c0;
    --text-3: #6060a0;
    --accent: #6366f1;
    --accent-glow: rgba(99,102,241,0.15);
    --pass: #22c55e;
    --pass-bg: rgba(34,197,94,0.08);
    --pass-border: rgba(34,197,94,0.25);
    --fail: #ef4444;
    --fail-bg: rgba(239,68,68,0.08);
    --fail-border: rgba(239,68,68,0.25);
    --warn: #f59e0b;
    --warn-bg: rgba(245,158,11,0.08);
    --info-bg: rgba(99,102,241,0.05);
}

* { margin:0; padding:0; box-sizing:border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
    transition: background 0.3s, color 0.3s;
}
.container { max-width: 1000px; margin: 0 auto; padding: 32px 24px; }

/* Header & Controls */
.report-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--border);
}
.header-left h1 {
    font-size: 1.6rem;
    font-weight: 700;
    background: linear-gradient(135deg, #6366f1, #a855f7);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 6px;
}
.header-left .subtitle { font-size: 0.8rem; color: var(--text-3); }
.header-right {
    display: flex;
    gap: 12px;
}
.icon-btn {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    width: 36px; height: 36px;
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
}
.icon-btn:hover { background: var(--surface-hover); }
.btn-primary {
    background: var(--accent);
    color: #fff;
    border: none;
    padding: 0 16px;
    height: 36px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    display: flex; align-items: center; gap: 6px;
    transition: opacity 0.2s;
}
.btn-primary:hover { opacity: 0.9; }

/* Control Bar (Search & Filter) */
.control-bar {
    display: flex;
    gap: 16px;
    margin-bottom: 24px;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
}
.search-box {
    position: relative;
    flex: 1;
    min-width: 200px;
    max-width: 320px;
}
.search-box input {
    width: 100%;
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 8px 12px 8px 32px;
    border-radius: 8px;
    font-size: 0.85rem;
    outline: none;
    transition: border-color 0.2s;
}
.search-box input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-glow); }
.search-box svg {
    position: absolute;
    left: 10px; top: 10px;
    width: 14px; height: 14px;
    fill: var(--text-3);
}

.filter-group {
    display: flex;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
}
.filter-btn {
    background: transparent;
    border: none;
    color: var(--text-2);
    padding: 6px 14px;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    border-right: 1px solid var(--border);
    transition: all 0.2s;
}
.filter-btn:last-child { border-right: none; }
.filter-btn:hover { background: var(--surface-hover); }
.filter-btn.active { background: var(--info-bg); color: var(--accent); }

/* Stats */
.stats-row {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 12px;
    margin-bottom: 30px;
}
.stat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px 12px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.02);
    transition: transform 0.2s, box-shadow 0.2s, background 0.2s;
    backdrop-filter: blur(8px);
}
.stat-card[data-filter-trigger]:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 20px rgba(0,0,0,0.08);
    background: var(--surface-hover);
}
.stat-value {
    font-size: 1.8rem;
    font-weight: 800;
    line-height: 1;
}
.stat-label {
    font-size: 0.68rem;
    color: var(--text-3);
    margin-top: 6px;
    text-transform: uppercase;
    letter-spacing: 1px;
}
.stat-total .stat-value { color: var(--accent); }
.stat-pass .stat-value { color: var(--pass); }
.stat-fail .stat-value { color: var(--fail); }
.stat-cases .stat-value { color: var(--accent); }
.stat-platform .stat-value { color: var(--fail); }
.stat-execution .stat-value { color: var(--warn); }
.stat-rate .stat-value { color: var(--warn); }
.stat-time .stat-value { color: #0ea5e9; font-size: 1.3rem; }

/* Scope & Insights */
.scope-note {
    margin: -8px 0 18px;
    padding: 12px 14px;
    background: var(--info-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    font-size: 0.78rem;
    color: var(--text-2);
    line-height: 1.6;
}

.insight-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
    margin-bottom: 24px;
}

.insight-panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}

.section-heading {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
}

.section-heading h2 {
    font-size: 0.9rem;
    font-weight: 700;
}

.section-heading p,
.section-empty {
    font-size: 0.75rem;
    color: var(--text-3);
    line-height: 1.6;
}

.section-meta {
    font-size: 0.72rem;
    color: var(--text-3);
    white-space: nowrap;
}

.issue-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.issue-item {
    border: 1px solid var(--border);
    border-left-width: 4px;
    border-radius: 10px;
    padding: 12px;
    background: var(--surface-2);
}

.issue-item.platform { border-left-color: var(--fail); }
.issue-item.execution { border-left-color: var(--warn); }

.issue-header {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: flex-start;
}

.issue-title {
    font-size: 0.8rem;
    font-weight: 700;
    line-height: 1.5;
}

.issue-tags {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    justify-content: flex-end;
}

.issue-tag {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 2px 8px;
    font-size: 0.64rem;
    font-weight: 700;
    border: 1px solid var(--border);
    white-space: nowrap;
}

.issue-tag.platform {
    color: var(--fail);
    background: var(--fail-bg);
    border-color: var(--fail-border);
}

.issue-tag.execution {
    color: var(--warn);
    background: var(--warn-bg);
}

.issue-tag.neutral {
    color: var(--text-2);
    background: var(--surface);
}

.issue-evidence,
.issue-records {
    font-size: 0.72rem;
    color: var(--text-2);
    line-height: 1.6;
    margin-top: 8px;
    word-break: break-word;
}

.records-label {
    font-size: 0.8rem;
    font-weight: 700;
    color: var(--text-2);
    margin: 6px 0 12px;
}

/* Detail blocks */
.detail-block {
    margin: 0 20px 16px;
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    background: var(--surface);
}

.detail-block-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 10px 12px;
    background: var(--surface-2);
    border-bottom: 1px solid var(--border);
    font-size: 0.76rem;
    font-weight: 700;
}

.detail-block-header .meta {
    font-size: 0.68rem;
    color: var(--text-3);
    font-weight: 500;
}

.case-list {
    display: flex;
    flex-direction: column;
}

.case-item {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 10px 12px;
    border-top: 1px solid var(--border);
}

.case-item:first-child {
    border-top: none;
}

.case-status {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 48px;
    height: 22px;
    border-radius: 999px;
    font-size: 0.65rem;
    font-weight: 700;
    border: 1px solid var(--border);
}

.case-status.pass {
    color: var(--pass);
    background: var(--pass-bg);
    border-color: var(--pass-border);
}

.case-status.fail {
    color: var(--fail);
    background: var(--fail-bg);
    border-color: var(--fail-border);
}

.case-status.unknown {
    color: var(--text-2);
    background: var(--surface-2);
}

.case-body {
    min-width: 0;
    flex: 1;
}

.case-title {
    font-size: 0.78rem;
    font-weight: 600;
    line-height: 1.5;
    color: var(--text);
}

.case-meta {
    font-size: 0.7rem;
    color: var(--text-2);
    margin-top: 4px;
    line-height: 1.5;
}

/* Test Case Cards */
.test-cases { display: flex; flex-direction: column; gap: 16px; }
.test-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 2px 6px rgba(0,0,0,0.02);
    transition: display 0.2s, box-shadow 0.3s, transform 0.3s;
    backdrop-filter: blur(4px);
}
.test-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.06); transform: translateY(-1px); }
.test-card.hidden { display: none !important; }
.test-card.pass { border-left: 4px solid var(--pass); }
.test-card.fail { border-left: 4px solid var(--fail); }

/* Card Header */
.tc-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    cursor: pointer;
    gap: 12px;
}
.tc-header:hover { background: var(--surface-hover); }
.tc-left { display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1; }
.tc-icon { font-size: 1.3rem; flex-shrink: 0; }
.tc-info { min-width: 0; }
.tc-name { font-size: 0.92rem; font-weight: 600; word-break: break-word; }
.tc-desc { font-size: 0.75rem; color: var(--text-2); margin-top: 2px; }
.tc-right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.tc-badge {
    font-size: 0.65rem;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 6px;
    letter-spacing: 0.5px;
}
.tc-badge.pass { background: var(--pass-bg); color: var(--pass); border: 1px solid var(--pass-border); }
.tc-badge.fail { background: var(--fail-bg); color: var(--fail); border: 1px solid var(--fail-border); }
.tc-dur { font-size: 0.72rem; color: var(--text-3); }
.tc-toggle { font-size: 0.8rem; color: var(--text-3); transition: transform 0.2s; }
.test-card.open .tc-toggle { transform: rotate(90deg); }

/* Card Body (steps) */
.tc-body { display: none; border-top: 1px solid var(--border); }
.test-card.open .tc-body { display: block; }

/* Timeline */
.timeline { padding: 16px 20px; }
.step {
    display: flex;
    gap: 12px;
    padding: 10px 0;
    border-bottom: 1px solid var(--border);
    align-items: flex-start;
}
.step:last-child { border-bottom: none; }
.step-dot {
    width: 32px; height: 32px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.85rem;
    flex-shrink: 0;
    background: var(--surface-2);
    border: 2px solid var(--border);
}
.step.pass .step-dot { border-color: var(--pass); background: var(--pass-bg); }
.step.fail .step-dot { border-color: var(--fail); background: var(--fail-bg); }
.step.warn .step-dot { border-color: var(--warn); background: var(--warn-bg); }
.step-content { flex: 1; min-width: 0; }
.step-header {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}
.step-num {
    font-size: 0.65rem;
    color: var(--text-3);
    font-family: monospace;
    min-width: 24px;
}
.step-label {
    font-size: 0.68rem;
    font-weight: 600;
    padding: 1px 6px;
    border-radius: 4px;
    background: var(--info-bg);
    color: var(--accent);
}
.step.fail .step-label { background: var(--fail-bg); color: var(--fail); }
.step.pass .step-label { background: var(--pass-bg); color: var(--pass); }
.step-dur {
    font-size: 0.65rem;
    color: var(--text-3);
    margin-left: auto;
}
.step-text {
    font-size: 0.78rem;
    color: var(--text-2);
    margin-top: 4px;
    word-break: break-word;
    line-height: 1.5;
}

/* Screenshot */
.step-screenshot {
    margin-top: 8px;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid var(--border);
    background: #000;
    max-width: 480px;
    cursor: pointer;
    position: relative;
}
.step-screenshot img {
    width: 100%;
    height: auto;
    display: block;
    opacity: 0.9;
    transition: opacity 0.2s;
}
.step-screenshot:hover img { opacity: 1; }
.step-screenshot .zoom-hint {
    position: absolute;
    top: 6px; right: 6px;
    background: rgba(0,0,0,0.7);
    color: #fff;
    font-size: 0.6rem;
    padding: 2px 6px;
    border-radius: 4px;
}

/* Error Block */
.error-block {
    margin: 0 20px 16px;
    background: var(--fail-bg);
    border: 1px solid var(--fail-border);
    border-radius: 8px;
    overflow: hidden;
}
.error-block-header {
    font-size: 0.75rem; font-weight: 600;
    padding: 8px 12px;
    background: rgba(239,68,68,0.08); /* fallback for dark mode adjust */
    color: var(--fail);
    background-color: var(--fail-bg);
}
.error-block-body {
    padding: 10px 12px;
    font-size: 0.72rem;
    font-family: 'Consolas', 'Monaco', monospace;
    color: var(--fail);
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 150px;
    overflow-y: auto;
    line-height: 1.5;
}

/* Lightbox */
.lightbox {
    display: none;
    position: fixed;
    top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0,0,0,0.85);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    z-index: 9999;
    cursor: zoom-out;
    align-items: center;
    justify-content: center;
    animation: fadeIn 0.3s ease;
}
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
.lightbox.active { display: flex; }
.lightbox img {
    max-width: 95%; max-height: 95%;
    border-radius: 12px;
    box-shadow: 0 0 80px rgba(99,102,241,0.3), 0 20px 60px rgba(0,0,0,0.5);
    animation: zoomIn 0.3s ease;
}
@keyframes zoomIn { from { transform: scale(0.9); opacity: 0; } to { transform: scale(1); opacity: 1; } }

/* Empty */
.empty-state { text-align: center; padding: 60px 20px; color: var(--text-3); }
.empty-icon { font-size: 3rem; margin-bottom: 12px; opacity: 0.3; }

/* Footer */
.report-footer {
    margin-top: 40px;
    padding-top: 16px;
    border-top: 1px solid var(--border);
    font-size: 0.7rem;
    color: var(--text-3);
    display: flex;
    justify-content: space-between;
}

@media (max-width: 768px) {
    .stats-row { grid-template-columns: repeat(2, 1fr); gap: 8px; }
    .insight-grid { grid-template-columns: 1fr; }
    .tc-header { flex-direction: column; align-items: flex-start; }
    .tc-right { margin-top: 8px; }
    .step { gap: 8px; }
    .step-screenshot { max-width: 100%; }
    .control-bar { flex-direction: column; align-items: stretch; }
}
"""

_JS = """
// Init theme based on system preference
if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    document.documentElement.setAttribute('data-theme', 'dark');
}
const toggleThemeBtn = document.getElementById('toggle-theme');
if (toggleThemeBtn) {
    toggleThemeBtn.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme');
        document.documentElement.setAttribute('data-theme', current === 'dark' ? 'light' : 'dark');
    });
}

// Expand/Collapse Cards
document.querySelectorAll('.tc-header').forEach(h => {
    h.addEventListener('click', () => {
        h.closest('.test-card').classList.toggle('open');
    });
});
const toggleAllBtn = document.getElementById('toggle-all');
let allExpanded = false;
if (toggleAllBtn) {
    toggleAllBtn.addEventListener('click', () => {
        allExpanded = !allExpanded;
        document.querySelectorAll('.test-card').forEach(c => {
            if (allExpanded) c.classList.add('open');
            else c.classList.remove('open');
        });
    });
}

// Lightbox
const lb = document.getElementById('lightbox');
const lbImg = document.getElementById('lb-img');
document.querySelectorAll('.step-screenshot').forEach(el => {
    el.addEventListener('click', () => {
        lbImg.src = el.querySelector('img').src;
        lb.classList.add('active');
    });
});
lb && lb.addEventListener('click', () => lb.classList.remove('active'));

// Search and Filter
const searchInput = document.getElementById('search-input');
const filterBtns = document.querySelectorAll('.filter-btn');
let currentFilter = 'all';
let currentSearch = '';

function updateView() {
    let visibleCount = 0;
    document.querySelectorAll('.test-card').forEach(card => {
        const title = (card.getAttribute('data-title') || '').toLowerCase();
        const status = card.getAttribute('data-status');
        
        const matchSearch = title.includes(currentSearch);
        const matchFilter = currentFilter === 'all' || status === currentFilter;
        
        if (matchSearch && matchFilter) {
            card.classList.remove('hidden');
            visibleCount++;
        } else {
            card.classList.add('hidden');
        }
    });
    const emptyHint = document.getElementById('filter-empty');
    if (emptyHint) {
        emptyHint.style.display = visibleCount === 0 ? 'block' : 'none';
    }
}

if (searchInput) {
    searchInput.addEventListener('input', (e) => {
        currentSearch = e.target.value.toLowerCase();
        updateView();
    });
}

filterBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
        filterBtns.forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        currentFilter = e.target.getAttribute('data-filter');
        updateView();
    });
});

document.querySelectorAll('[data-filter-trigger]').forEach(card => {
    card.addEventListener('click', (e) => {
        const targetFilter = card.getAttribute('data-filter-trigger');
        if (!targetFilter) return;
        
        filterBtns.forEach(b => {
            if (b.getAttribute('data-filter') === targetFilter) {
                b.classList.add('active');
            } else {
                b.classList.remove('active');
            }
        });
        currentFilter = targetFilter;
        updateView();
        
        // smooth scroll to cases if needed
        document.querySelector('.control-bar').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
});

// Download Report
const downloadBtn = document.getElementById('download-btn');
if (downloadBtn) {
    downloadBtn.addEventListener('click', () => {
        const html = document.documentElement.outerHTML;
        const blob = new Blob([html], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'AI_Test_Report_' + new Date().toISOString().slice(0,10) + '.html';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });
}

// Expand the first item by default
const first = document.querySelector('.test-card');
if (first) first.classList.add('open');
"""


class AllureReporter:
    """Playwright-style test report generator"""

    def __init__(self, results_dir: str = "allure-results", report_dir: str = "allure-report"):
        self.results_dir = Path(results_dir)
        self.report_dir = Path(report_dir)
        self._history_file = self.report_dir / "report_history.json"
        self._current_suite: Optional[TestSuite] = None
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    # ── Allure-compatible interface used by the orchestrator ──

    def start_suite(self, name: str):
        self._current_suite = TestSuite(name=name, started_at=datetime.now())

    def add_result(self, result: TestResult):
        if self._current_suite is None:
            self.start_suite("Default Suite")
        self._current_suite.results.append(result)
        self._write_allure_result(result)

    def _write_allure_result(self, result: TestResult):
        allure_result = {
            "uuid": str(uuid.uuid4()),
            "name": result.name,
            "status": result.status.value,
            "statusDetails": {"message": result.error_message} if result.error_message else {},
            "description": result.description,
            "steps": [
                {"name": s.get("name", "Step"), "status": s.get("status", "passed"), "details": s.get("details", "")}
                for s in result.steps
            ],
            "start": int(datetime.fromisoformat(result.timestamp).timestamp() * 1000),
            "stop": int((datetime.fromisoformat(result.timestamp).timestamp() + result.duration) * 1000),
        }
        f = self.results_dir / f"{allure_result['uuid']}-result.json"
        with open(f, 'w', encoding='utf-8') as fp:
            json.dump(allure_result, fp, ensure_ascii=False, indent=2)

    def finish_suite(self):
        if self._current_suite:
            self._current_suite.finished_at = datetime.now()

    # ── Report generation (core) ──

    def generate_report(self, open_browser: bool = False, task_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate Playwright-style HTML reports from test_runs"""
        start_time = datetime.now()
        try:
            runs = [self._decorate_run(run) for run in self._load_test_runs(task_id=task_id)]
            # Generate rid early to use as the file identifier
            rid = str(uuid.uuid4())[:8]
            html = self._build_full_report(runs, rid)
            
            # Write the latest report to index.html for quick access
            report_file = self.report_dir / "index.html"
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(html)
                
            # Write the historical snapshot to ${rid}.html
            snapshot_file = self.report_dir / f"{rid}.html"
            with open(snapshot_file, 'w', encoding='utf-8') as f:
                f.write(html)

            stats = self._calc_stats(runs)
            record = self._build_report_record(stats, start_time, rid, runs, selected_id=task_id)
            self._save_to_history(record)
            return record
        except Exception as e:
            logger.error(f"Report generation failed: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def _load_test_runs(self, limit: int = 20, task_id: Optional[str] = None) -> List[Dict]:
        """Load test_runs from business.db; task_id can identify one record or an entire group."""
        from core.db_helper import get_connection
        runs = []
        try:
            with get_connection() as conn:
                group_selected = False
                group_title = ""
                if task_id:
                    try:
                        group_row = conn.execute(
                            "SELECT title FROM execution_groups WHERE group_id = ?",
                            (task_id,),
                        ).fetchone()
                        group_selected = bool(group_row)
                        group_title = str(group_row[0] or "") if group_row else ""
                    except Exception:
                        group_selected = False
                        group_title = ""
                base_query = (
                    "SELECT task_id, requirement, status, log_count, error_count, "
                    "duration_ms, target_url, mode, logs_json, created_at, "
                    "COALESCE(execution_group_id, task_id) AS execution_group_id, "
                    "COALESCE(record_kind, 'child') AS record_kind "
                    "FROM test_runs "
                )
                if task_id:
                    if group_selected:
                        rows = conn.execute(
                            base_query + "WHERE execution_group_id = ? ORDER BY CASE WHEN COALESCE(record_kind, 'child') = 'root' THEN 0 ELSE 1 END, created_at ASC",
                            (task_id,),
                        ).fetchall()
                    else:
                        rows = conn.execute(
                            base_query + "WHERE task_id = ?",
                            (task_id,)
                        ).fetchall()
                else:
                    rows = conn.execute(
                        base_query + "ORDER BY created_at DESC LIMIT ?",
                        (limit,)
                    ).fetchall()
                for row in rows:
                    logs_json = row[8] or "[]"
                    try:
                        logs = json.loads(logs_json)
                    except json.JSONDecodeError:
                        logs = []
                    runs.append({
                        "task_id": row[0],
                        "requirement": row[1] or "Unknown",
                        "status": row[2] or "unknown",
                        "log_count": row[3] or 0,
                        "error_count": row[4] or 0,
                        "duration_ms": row[5] or 0,
                        "target_url": row[6] or "",
                        "mode": row[7] or "smart",
                        "logs": logs,
                        "created_at": row[9] or "",
                        "execution_group_id": row[10] or row[0],
                        "record_kind": row[11] or "child",
                        "group_title": group_title,
                    })
        except Exception as e:
            logger.warning(f"Failed to load test_runs: {e}")
        return runs

    def _decorate_run(self, run: Dict[str, Any]) -> Dict[str, Any]:
        enriched = dict(run)
        enriched.update(analyze_test_run(run))
        return enriched

    def _calc_stats(self, runs: List[Dict]) -> Dict:
        total = len(runs)
        passed = sum(1 for r in runs if r["status"] in ("success", "recovered", "healed"))
        failed = sum(1 for r in runs if r["status"] not in ("success", "recovered", "healed"))
        healed = sum(1 for r in runs if r["status"] == "healed")
        recovered = sum(1 for r in runs if r["status"] == "recovered")
        total_ms = sum(r.get("duration_ms", 0) or 0 for r in runs)
        step_total = 0
        step_passed = 0
        step_failed = 0
        case_total = 0
        case_passed = 0
        case_failed = 0
        platform_issue_total = 0
        execution_issue_total = 0

        for run in runs:
            run_step_total, run_step_passed, run_step_failed = self._calc_step_stats(run)
            step_total += run_step_total
            step_passed += run_step_passed
            step_failed += run_step_failed
            case_total += int(run.get("case_count", 0) or 0)
            case_passed += int(run.get("case_passed", 0) or 0)
            case_failed += int(run.get("case_failed", 0) or 0)
            platform_issue_total += int(run.get("platform_issue_count", 0) or 0)
            execution_issue_total += int(run.get("execution_issue_count", 0) or 0)

        return {
            "total": total, "passed": passed, "failed": failed,
            "healed": healed, "recovered": recovered,
            "duration_ms": total_ms,
            "case_total": case_total,
            "case_passed": case_passed,
            "case_failed": case_failed,
            "platform_issue_total": platform_issue_total,
            "execution_issue_total": execution_issue_total,
            "total_steps": step_total,
            "step_passed": step_passed,
            "step_failed": step_failed,
        }

    def _calc_step_stats(self, run: Dict) -> tuple[int, int, int]:
        logs = run.get("logs") or []
        step_results = []

        for log in logs:
            if log.get("event") == "step_result":
                step_results.append(log)
                continue
            if log.get("type") == "result" and log.get("step"):
                step_results.append(log)

        if step_results:
            failed = 0
            for log in step_results:
                status = str(log.get("status", "")).lower()
                content = str(log.get("content", ""))
                if status and status != "success":
                    failed += 1
                elif content.startswith("❌"):
                    failed += 1
            total = len(step_results)
            passed = max(total - failed, 0)
            return total, passed, failed

        total = int(run.get("log_count", 0) or 0)
        failed = int(run.get("error_count", 0) or 0)
        passed = max(total - failed, 0)
        return total, passed, failed

    def _build_report_record(self, stats: Dict, start_time: datetime, rid: str, runs: List[Dict[str, Any]], selected_id: Optional[str] = None) -> Dict:
        if selected_id:
            first_run = runs[0] if runs else {}
            base_name = first_run.get("group_title") or first_run.get("requirement") or first_run.get("task_id") or selected_id
            is_group_report = bool(
                runs
                and (
                    any((run.get("execution_group_id") or run.get("task_id")) == selected_id for run in runs)
                    or all((run.get("task_id") or "") != selected_id for run in runs)
                )
                and (
                    len(runs) > 1
                    or any((run.get("task_id") or "") != selected_id for run in runs)
                    or first_run.get("group_title")
                )
            )
            scope = "batch" if is_group_report else "record"
            task_id = selected_id
            target_url = first_run.get("target_url", "")
            title = _build_report_title(
                scope,
                target_url=target_url,
                base_name=str(base_name or ""),
                task_id=str(task_id or ""),
                record_count=int(stats.get("total", 0) or 0),
            )
        elif len(runs) == 1:
            run = runs[0]
            scope = "record"
            task_id = run.get("task_id")
            target_url = run.get("target_url", "")
            title = _build_report_title(
                scope,
                target_url=target_url,
                base_name=str(run.get("requirement") or ""),
                task_id=str(task_id or ""),
                record_count=int(stats.get("total", 0) or 0),
            )
        else:
            scope = "summary"
            task_id = None
            target_url = ""
            title = _build_report_title(
                scope,
                record_count=int(len(runs) or stats.get("total", 0) or 0),
            )

        return {
            "status": "success", "id": rid,
            "timestamp": start_time.isoformat(),
            "title": title,
            "report_url": f"/api/report/view/{rid}",
            "report_scope": scope,
            "task_id": task_id,
            "target_url": target_url,
            "record_count": stats.get("total", 0),
            "case_count": stats.get("case_total", 0),
            "platform_issue_count": stats.get("platform_issue_total", 0),
            "execution_issue_count": stats.get("execution_issue_total", 0),
            "total_steps": stats.get("total_steps", 0),
            "passed": stats.get("case_passed", 0),
            "failed": stats.get("case_failed", 0),
            "duration_ms": stats.get("duration_ms", 0),
            "message": "Report generated successfully",
        }

    # ── HTML generation ──

    def _build_full_report(self, runs: List[Dict], rid: str) -> str:
        stats = self._calc_stats(runs)
        record_total = stats["total"]
        record_passed = stats["passed"]
        record_failed = stats["failed"]
        case_total = stats["case_total"]
        platform_issue_total = stats["platform_issue_total"]
        execution_issue_total = stats["execution_issue_total"]
        rate = (record_passed / record_total * 100) if record_total > 0 else 0
        total_ms = stats["duration_ms"]
        platform_issue_groups = self._aggregate_issue_groups(runs, "platform_issues")
        execution_issue_groups = self._aggregate_issue_groups(runs, "execution_issues")

        # Build test record cards
        cards_html = ""
        for run in runs:
            cards_html += self._build_test_card(run)

        if not runs:
            cards_html = '''
            <div class="empty-state">
                <div class="empty-icon"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity:0.3"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg></div>
                <p>No test records yet</p>
                <p style="font-size:0.75rem;margin-top:6px;">Reports will appear here after tests run</p>
            </div>'''

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        return f'''<!DOCTYPE html>
<html lang="en-US" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Test Platform - Test Report</title>
<style>{_CSS}</style>
</head>
<body>
<div class="container">
    <div class="report-header">
        <div class="header-left">
            <h1><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="url(#grad)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:6px;"><defs><linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#6366f1"/><stop offset="100%" stop-color="#a855f7"/></linearGradient></defs><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>AI Test Platform Test Report</h1>
            <div class="subtitle">ID: #{rid} · Generated: {now} · {record_total} test records / {case_total} test cases</div>
        </div>
        <div class="header-right">
            <button class="icon-btn" id="toggle-theme" title="Toggle theme"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg></button>
            <button class="btn-primary" id="download-btn">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
                Download offline report
            </button>
        </div>
    </div>

    <div class="scope-note">
        Definitions: a <strong>test record</strong> represents one complete execution; a <strong>test case</strong> represents an assertion or check in that record.
        <strong>Tested platform issues</strong> cover errors directly related to business pages or features; model, preauthentication, browser, and other infrastructure issues are counted separately.
    </div>

    <div class="control-bar">
        <div class="search-box">
            <svg viewBox="0 0 24 24"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            <input type="text" id="search-input" placeholder="Search test records or test case names..." />
        </div>
        <div style="display: flex; gap: 12px; align-items: center;">
            <div class="filter-group">
                <button class="filter-btn active" data-filter="all">All Records ({record_total})</button>
                <button class="filter-btn" data-filter="pass" style="color:var(--pass)">Passed Records ({record_passed})</button>
                <button class="filter-btn" data-filter="fail" style="color:var(--fail)">Failed Records ({record_failed})</button>
            </div>
            <button class="icon-btn" id="toggle-all" title="Expand/collapse all" style="width:auto;padding:0 12px;font-size:0.8rem;">Collapse/expand</button>
        </div>
    </div>

    <div class="stats-row">
        <div class="stat-card stat-total" data-filter-trigger="all" style="cursor: pointer;" title="Click to view all test records">
            <div class="stat-value">{record_total}</div>
            <div class="stat-label">Test Record</div>
        </div>
        <div class="stat-card stat-cases">
            <div class="stat-value">{case_total}</div>
            <div class="stat-label">Test Case</div>
        </div>
        <div class="stat-card stat-platform">
            <div class="stat-value">{platform_issue_total}</div>
            <div class="stat-label">Tested Platform Issues</div>
        </div>
        <div class="stat-card stat-execution">
            <div class="stat-value">{execution_issue_total}</div>
            <div class="stat-label">Execution Infrastructure Issues</div>
        </div>
        <div class="stat-card stat-rate">
            <div class="stat-value">{rate:.0f}%</div>
            <div class="stat-label">Record Pass Rate</div>
        </div>
        <div class="stat-card stat-time">
            <div class="stat-value">{_fmt_ms(total_ms)}</div>
            <div class="stat-label">Total Duration</div>
        </div>
    </div>

    <div class="insight-grid">
        {self._build_global_issue_panel(
            "Tested Platform Issues",
            "Summaries of issues directly affecting tested pages, interactions, or business outcomes.",
            platform_issue_groups,
            "This report found no clear issues in the tested platform."
        )}
        {self._build_global_issue_panel(
            "Execution Infrastructure Issues",
            "Separates model, preauthentication, browser, and automation infrastructure issues from business issues.",
            execution_issue_groups,
            "This report found no execution infrastructure issues."
        )}
    </div>

    <div class="records-label">Test Record Details</div>
    <div class="test-cases">
        {cards_html}
        <div id="filter-empty" class="empty-state" style="display:none;">
            <div class="empty-icon"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity:0.3"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></div>
            <p>No matching test records</p>
            <p style="font-size:0.75rem;margin-top:6px;">Adjust the search or choose a different filter</p>
        </div>
    </div>

    <div class="report-footer">
        <span>AI Test Platform v2.0</span>
        <span>Playwright-Style Report Engine</span>
    </div>
</div>

<div class="lightbox" id="lightbox">
    <img id="lb-img" src="" alt="Screenshot">
</div>

<script>{_JS}</script>
</body>
</html>'''

    def _build_test_card(self, run: Dict) -> str:
        """Build a test record card containing test cases and issue summaries"""
        name = _esc(run["requirement"])
        status = run["status"]
        duration_ms = run.get("duration_ms", 0) or 0
        target_url = _esc(run.get("target_url", ""))
        mode = _esc(run.get("mode", ""))
        created_at = _esc(run.get("created_at", ""))
        logs = run.get("logs", [])
        test_cases = run.get("test_cases", [])
        platform_issues = run.get("platform_issues", [])
        execution_issues = run.get("execution_issues", [])
        case_count = int(run.get("case_count", 0) or 0)
        platform_issue_count = int(run.get("platform_issue_count", 0) or 0)
        execution_issue_count = int(run.get("execution_issue_count", 0) or 0)

        status_class = "pass" if status in ("success", "recovered", "healed") else "fail"
        _svg_pass = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'
        _svg_heal = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>'
        _svg_fail = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>'
        status_icon = _svg_pass if status == "success" else (_svg_heal if status in ("healed", "recovered") else _svg_fail)
        status_label = {"success": "Passed", "failed": "Failed", "healed": "Healed", "recovered": "Recovered"}.get(status, status)

        # Description line
        desc_parts = []
        if target_url:
            desc_parts.append(f"Target: {target_url}")
        if mode:
            desc_parts.append(f"Mode: {mode}")
        desc_parts.append(f"Test cases: {case_count}")
        desc_parts.append(f"Platform issues: {platform_issue_count}")
        if execution_issue_count:
            desc_parts.append(f"Infrastructure issues: {execution_issue_count}")
        if created_at:
            desc_parts.append(created_at)
        desc_text = " · ".join(desc_parts)

        # Parse steps
        steps = _parse_execution_steps(logs)
        case_summary_html = self._build_case_summary(test_cases)
        platform_issue_html = self._build_issue_block(
            "Tested Platform Issues",
            platform_issues,
            "This record found no clear issues in the tested platform."
        )
        execution_issue_html = ""
        if execution_issues:
            execution_issue_html = self._build_issue_block(
                "Execution Infrastructure Issues",
                execution_issues,
                "This record found no execution infrastructure issues."
            )
        steps_html = self._build_timeline(steps)
        search_blob = _esc(" ".join(
            [run.get("requirement", "")]
            + [case.get("title", "") for case in test_cases]
            + [issue.get("summary", "") for issue in platform_issues]
            + [issue.get("summary", "") for issue in execution_issues]
        ))

        return f'''
        <div class="test-card {status_class}" data-status="{status_class}" data-title="{search_blob}">
            <div class="tc-header">
                <div class="tc-left">
                    <span class="tc-icon">{status_icon}</span>
                    <div class="tc-info">
                        <div class="tc-name">{name}</div>
                        <div class="tc-desc">{desc_text}</div>
                    </div>
                </div>
                <div class="tc-right">
                    <span class="tc-badge {status_class}">{status_label}</span>
                    <span class="tc-dur"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:2px;"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>{_fmt_ms(duration_ms)}</span>
                    <span class="tc-toggle">▶</span>
                </div>
            </div>
            <div class="tc-body">
                {case_summary_html}
                {platform_issue_html}
                {execution_issue_html}
                {steps_html}
            </div>
        </div>'''

    def _aggregate_issue_groups(self, runs: List[Dict[str, Any]], issue_field: str) -> List[Dict[str, Any]]:
        groups: Dict[tuple[str, str], Dict[str, Any]] = {}

        for run in runs:
            record_label = _short_text(run.get("requirement") or run.get("task_id") or "Untitled Record", 28)
            for issue in run.get(issue_field, []) or []:
                key = (issue.get("source", ""), issue.get("summary", ""))
                if key not in groups:
                    groups[key] = {
                        **issue,
                        "occurrences": int(issue.get("count", 1) or 1),
                        "records": [record_label],
                    }
                    continue

                groups[key]["occurrences"] += int(issue.get("count", 1) or 1)
                if record_label not in groups[key]["records"]:
                    groups[key]["records"].append(record_label)

        return sorted(
            groups.values(),
            key=lambda item: (-int(item.get("occurrences", 1) or 1), item.get("summary", "")),
        )

    def _build_global_issue_panel(
        self,
        title: str,
        description: str,
        issues: List[Dict[str, Any]],
        empty_text: str,
    ) -> str:
        if issues:
            items_html = self._build_issue_items(issues, show_records=True)
        else:
            items_html = f'<div class="section-empty">{_esc(empty_text)}</div>'

        return f'''
        <section class="insight-panel">
            <div class="section-heading">
                <div>
                    <h2>{_esc(title)}</h2>
                    <p>{_esc(description)}</p>
                </div>
                <div class="section-meta">{len(issues)} issue categories</div>
            </div>
            <div class="issue-list">{items_html}</div>
        </section>'''

    def _build_case_summary(self, test_cases: List[Dict[str, Any]]) -> str:
        passed = sum(1 for case in test_cases if case.get("status") == "pass")
        failed = sum(1 for case in test_cases if case.get("status") == "fail")

        if test_cases:
            items = ""
            for case in test_cases:
                status = case.get("status", "unknown")
                status_label = {"pass": "Passed", "fail": "Failed", "unknown": "Unknown"}.get(status, "Unknown")
                meta_parts = []
                step_index = case.get("step_index")
                if isinstance(step_index, int):
                    meta_parts.append(f"Related step #{step_index + 1}")
                if status != "pass" and case.get("evidence"):
                    meta_parts.append(f"Evidence: {_short_text(case['evidence'], 120)}")
                meta_html = f'<div class="case-meta">{_esc(" · ".join(meta_parts))}</div>' if meta_parts else ""
                items += f'''
                <div class="case-item">
                    <span class="case-status {status}">{_esc(status_label)}</span>
                    <div class="case-body">
                        <div class="case-title">{_esc(case.get("title", "Untitled Test Case"))}</div>
                        {meta_html}
                    </div>
                </div>'''
        else:
            items = '<div class="section-empty" style="padding: 14px 12px;">This record produced no identifiable test cases, usually because execution ended during planning or preconditions.</div>'

        return f'''
        <div class="detail-block">
            <div class="detail-block-header">
                <span>Test Case</span>
                <span class="meta">{len(test_cases)} total; {passed} passed / {failed} failed</span>
            </div>
            <div class="case-list">{items}</div>
        </div>'''

    def _build_issue_items(self, issues: List[Dict[str, Any]], show_records: bool = False) -> str:
        items = ""
        for issue in issues:
            source = issue.get("source", "execution")
            occurrence = int(issue.get("occurrences", issue.get("count", 1)) or 1)
            tags = [
                f'<span class="issue-tag {source}">{_esc(issue.get("source_label", ""))}</span>',
                f'<span class="issue-tag neutral">{_esc(issue.get("category", "Error"))}</span>',
            ]
            if occurrence > 1:
                tags.append(f'<span class="issue-tag neutral">x{occurrence}</span>')

            records_html = ""
            if show_records and issue.get("records"):
                records = issue["records"]
                record_text = ", ".join(records[:3])
                if len(records) > 3:
                    record_text += f" and others ({len(records)} records total)"
                records_html = f'<div class="issue-records">Affected records: {_esc(record_text)}</div>'

            items += f'''
            <div class="issue-item {source}">
                <div class="issue-header">
                    <div class="issue-title">{_esc(issue.get("summary", "Untitled Issue"))}</div>
                    <div class="issue-tags">{"".join(tags)}</div>
                </div>
                <div class="issue-evidence">{_esc(issue.get("evidence", ""))}</div>
                {records_html}
            </div>'''

        return items

    def _build_issue_block(self, title: str, issues: List[Dict[str, Any]], empty_text: str) -> str:
        if issues:
            items_html = self._build_issue_items(issues)
        else:
            items_html = f'<div class="section-empty" style="padding: 14px 12px;">{_esc(empty_text)}</div>'

        return f'''
        <div class="detail-block">
            <div class="detail-block-header">
                <span>{_esc(title)}</span>
                <span class="meta">{len(issues)} total</span>
            </div>
            <div class="issue-list" style="padding: 12px;">{items_html}</div>
        </div>'''

    def _build_timeline(self, steps: List[Dict]) -> str:
        """Build the step timeline"""
        if not steps:
            return '<div class="timeline" style="color:var(--text-3);font-size:0.78rem;padding:20px;">No detailed steps</div>'

        # Statistics
        pass_count = sum(1 for s in steps if s["status"] == "pass")
        fail_count = sum(1 for s in steps if s["status"] == "fail")
        screenshot_count = sum(1 for s in steps if s.get("screenshot"))

        items = ""
        for s in steps:
            status_class = {"pass": "pass", "fail": "fail", "warn": "warn"}.get(s["status"], "info")
            content = _esc(s["content"])
            # Truncate overly long content
            if len(content) > 200:
                content = content[:200] + "..."

            dur_html = ""
            if s.get("duration"):
                dur_html = f'<span class="step-dur">{_fmt_sec(s["duration"])}</span>'

            screenshot_html = ""
            if s.get("screenshot"):
                sc = s["screenshot"]
                # Ensure plain base64 and truncate oversized data to the first 100K
                if len(sc) > 100000:
                    sc = sc[:100000]
                screenshot_html = f'''
                <div class="step-screenshot">
                    <img src="data:image/jpeg;base64,{sc}" alt="Screenshot" loading="lazy">
                    <span class="zoom-hint"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:2px;"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>Click to enlarge</span>
                </div>'''

            items += f'''
            <div class="step {status_class}">
                <div class="step-dot">{s["icon"]}</div>
                <div class="step-content">
                    <div class="step-header">
                        <span class="step-num">#{s["num"]}</span>
                        <span class="step-label">{_esc(s["label"])}</span>
                        {dur_html}
                    </div>
                    <div class="step-text">{content}</div>
                    {screenshot_html}
                </div>
            </div>'''

        header = f'''
        <div style="padding:10px 20px;display:flex;justify-content:space-between;align-items:center;
                    border-bottom:1px solid var(--border);font-size:0.75rem;color:var(--text-2);">
            <span><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:3px;"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>Execution Steps ({len(steps)} steps)</span>
            <span>
                <span style="color:var(--pass);"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:1px;"><polyline points="20 6 9 17 4 12"/></svg>{pass_count}</span>
                <span style="color:var(--fail);margin-left:8px;"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:1px;"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>{fail_count}</span>
                <span style="color:var(--text-3);margin-left:8px;"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:1px;"><path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"/><circle cx="12" cy="13" r="4"/></svg>{screenshot_count}</span>
            </span>
        </div>'''

        return f'{header}<div class="timeline">{items}</div>'

    # ── History management ──

    def _save_to_history(self, record: Dict):
        history = self._load_history_file()
        history.insert(0, {
            "id": record.get("id"), "timestamp": record.get("timestamp"),
            "title": record.get("title"),
            "report_scope": record.get("report_scope"),
            "task_id": record.get("task_id"),
            "target_url": record.get("target_url"),
            "record_count": record.get("record_count"),
            "case_count": record.get("case_count"),
            "platform_issue_count": record.get("platform_issue_count"),
            "execution_issue_count": record.get("execution_issue_count"),
            "total_steps": record.get("total_steps"),
            "passed": record.get("passed"), "failed": record.get("failed"),
            "duration_ms": record.get("duration_ms"), "report_url": record.get("report_url"),
        })
        history = history[:50]
        try:
            with open(self._history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def _load_history_file(self) -> List[Dict]:
        stats = self.repair_history(include_items=True)
        return list(stats.get("history", []))

    def get_history(self, limit: int = 10) -> List[Dict]:
        return self._load_history_file()[:limit]

    def repair_history(self, include_items: bool = False) -> Dict[str, Any]:
        if not self._history_file.exists():
            return {
                "history_entries": 0,
                "updated_entries": 0,
                **({"history": []} if include_items else {}),
            }
        try:
            with open(self._history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            sanitized = [self._sanitize_history_entry(item) for item in history]
            updated_entries = sum(1 for before, after in zip(history, sanitized) if before != after)
            if sanitized != history:
                with open(self._history_file, 'w', encoding='utf-8') as f:
                    json.dump(sanitized, f, ensure_ascii=False, indent=2)
            payload: Dict[str, Any] = {
                "history_entries": len(sanitized),
                "updated_entries": updated_entries,
            }
            if include_items:
                payload["history"] = sanitized
            return payload
        except Exception:
            logger.exception("Failed to repair report history")
            payload = {"history_entries": 0, "updated_entries": 0}
            if include_items:
                payload["history"] = []
            return payload

    def _sanitize_history_entry(self, item: Dict[str, Any]) -> Dict[str, Any]:
        entry = dict(item or {})
        title = str(entry.get("title") or "")
        target_url = str(entry.get("target_url") or "").strip()
        scope = str(entry.get("report_scope") or "record")
        record_count = int(entry.get("record_count") or 0)
        base_name = str(entry.get("title") or "")
        if scope == "batch":
            suffix = "Batch Report"
        elif scope == "summary":
            suffix = "Summary Report"
        else:
            suffix = "Record Report"
        expected_title = _build_report_title(
            scope,
            target_url=target_url,
            base_name=base_name,
            task_id=str(entry.get("task_id") or ""),
            record_count=record_count,
        )
        has_known_prefix = title.startswith(("Specialized Test ·", "Test Record ·", "Test Report ·", "专项测试 ·", "测试记录 ·", "测试报告 ·"))
        if scope == "summary":
            should_rebuild = (
                _looks_broken_text(title)
                or "Summary" not in title
                or title.startswith("Test Report ·")
            )
        else:
            should_rebuild = (
                _looks_broken_text(title)
                or not title.endswith(suffix)
                or (scope == "batch" and not title.startswith("Specialized Test ·"))
                or (
                    scope == "record"
                    and (
                        target_url
                        or (has_known_prefix and not title.startswith("Test Record ·"))
                    )
                    and title != expected_title
                )
            )
        if should_rebuild:
            entry["title"] = expected_title
        return entry

    def get_report_path(self, report_id: Optional[str] = None) -> Optional[Path]:
        if report_id:
            if any(sep in report_id for sep in ("/", "\\")):
                return None
            candidate = self.report_dir / f"{report_id}.html"
        else:
            candidate = self.report_dir / "index.html"
        return candidate if candidate.exists() else None

    def delete_report(self, report_id: str) -> bool:
        history = self._load_history_file()
        new_history = [r for r in history if r.get("id") != report_id]
        if len(history) == len(new_history):
            return False
        try:
            # Clean up snapshot files
            snapshot_file = self.report_dir / f"{report_id}.html"
            if snapshot_file.exists():
                snapshot_file.unlink()
                
            with open(self._history_file, 'w', encoding='utf-8') as f:
                json.dump(new_history, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to delete report: {e}")
            return False

    def clear_results(self):
        if self.results_dir.exists():
            shutil.rmtree(self.results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        for html_file in self.report_dir.glob("*.html"):
            try:
                html_file.unlink()
            except OSError as e:
                logger.warning(f"Failed to remove report snapshot {html_file}: {e}")
        if self._history_file.exists():
            self._history_file.unlink()

    def _preserve_history(self):
        src = self.report_dir / "history"
        if src.exists():
            dst = self.results_dir / "history"
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)


# ── Global instance ──
_reporter: Optional[AllureReporter] = None

def get_reporter() -> AllureReporter:
    global _reporter
    if _reporter is None:
        from core.config import Config
        results_dir = os.path.join(Config.PROJECT_ROOT, "data", "allure-results")
        report_dir = os.path.join(Config.PROJECT_ROOT, "data", "allure-report")
        _reporter = AllureReporter(results_dir, report_dir)
    return _reporter
