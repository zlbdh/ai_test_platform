from __future__ import annotations

from typing import Any, Dict, Tuple

DEFAULT_EXECUTION_MODE = "default"
PROBE_EXECUTION_MODE = "probe"
DEFAULT_INTERACTION_POLICY = "default"
READ_ONLY_INTERACTION_POLICY = "read_only"

PROBE_MAX_SCENARIOS = 1
PROBE_STEP_BUDGET = 8
PROBE_TIMEOUT_SECONDS = 45

READ_ONLY_HINTS = (
    "不要登录",
    "不要输入",
    "不要提交",
    "只验证可访问性",
    "只读",
    "冒烟",
    "探针",
    "不要点击",
    "不要写入",
    "不做新增",
    "不做编辑",
    "不做删除",
    "不做发布",
    "read-only",
    "read only",
    "smoke",
    "probe",
)

SAFE_PROBE_ACTIONS = {
    "assert",
    "extract",
    "goto",
    "screenshot",
    "scroll",
    "visual_check",
    "wait",
}

BLOCKED_PROBE_ACTIONS = {
    "api_call",
    "assert_db",
    "click",
    "db_query",
    "fill",
    "hover",
    "key",
    "mock",
    "select",
    "set_var",
    "snapshot_db",
}


def looks_like_probe_requirement(requirement: str = "") -> bool:
    normalized = str(requirement or "").strip().lower()
    if not normalized:
        return False
    return any(token.lower() in normalized for token in READ_ONLY_HINTS)


def resolve_execution_profile(
    requirement: str = "",
    execution_mode: str = "",
    interaction_policy: str = "",
) -> Dict[str, Any]:
    explicit_mode = (execution_mode or "").strip().lower()
    explicit_policy = (interaction_policy or "").strip().lower()

    auto_probe = looks_like_probe_requirement(requirement)
    is_probe = (
        explicit_mode == PROBE_EXECUTION_MODE
        or explicit_policy == READ_ONLY_INTERACTION_POLICY
        or auto_probe
    )

    if not is_probe:
        return {
            "execution_mode": DEFAULT_EXECUTION_MODE,
            "interaction_policy": DEFAULT_INTERACTION_POLICY,
            "max_scenarios": None,
            "max_steps": None,
            "step_budget": None,
            "timeout_seconds": None,
            "detected_from_text": auto_probe,
        }

    return {
        "execution_mode": PROBE_EXECUTION_MODE,
        "interaction_policy": READ_ONLY_INTERACTION_POLICY,
        "max_scenarios": PROBE_MAX_SCENARIOS,
        "max_steps": PROBE_STEP_BUDGET,
        "step_budget": PROBE_STEP_BUDGET,
        "timeout_seconds": PROBE_TIMEOUT_SECONDS,
        "detected_from_text": auto_probe,
    }


def build_probe_goal_hint(target_url: str = "") -> str:
    target_hint = f"Limit the target page to {target_url}. " if target_url else "If no target URL is provided, perform only read-only checks on the current page. "
    return (
        "[Read-only probe mode] "
        "This task is low-risk, read-only verification, not a full business regression. "
        f"{target_hint}"
        "Strict limits: at most 1 scenario and 8 steps; "
        "do not log in, type, submit, publish, delete, export, upload, or log out; "
        "only verify page accessibility and visibility of its title, text, and elements, then finish promptly after confirmation."
    )


def describe_probe_block(action: str, target: str = "", value: str = "") -> str:
    action_name = str(action or "").strip() or "unknown"
    target_name = str(target or "").strip()
    suffix = f" ({target_name})" if target_name else ""
    return f"Read-only probe prohibits {action_name}{suffix}"


def should_block_probe_action(action: str, target: str = "", value: str = "") -> Tuple[bool, str]:
    normalized_action = str(action or "").strip().lower()
    if not normalized_action:
        return False, ""

    if normalized_action in BLOCKED_PROBE_ACTIONS:
        return True, describe_probe_block(action, target, value)

    if normalized_action not in SAFE_PROBE_ACTIONS:
        return True, describe_probe_block(action, target, value)

    if normalized_action == "goto":
        target_text = str(target or "").strip().lower()
        if not target_text:
            return True, "Read-only probe does not allow navigation without a target URL"

    return False, ""
