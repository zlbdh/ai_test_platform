# -*- coding: utf-8 -*-
"""
统一任务前门服务

第一阶段目标：
1. 统一 general / prototype / exploration 的入口协议
2. 统一任务读模型、证据摘要、门禁摘要和结果骨架
3. 保持底层执行器不重写，旧页面与旧接口继续可用
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from services.execution_center_service import get_execution_center_service
from services.prototype_agents import get_prototype_agents_service

logger = logging.getLogger(__name__)

SUPPORTED_TASK_KINDS = {"general", "prototype", "exploration"}


def _now_iso() -> str:
    return datetime.now().isoformat()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


class UnifiedTaskService:
    """统一任务门面。"""

    def create_task(
        self,
        *,
        commander: Any,
        task_kind: str,
        user_goal: str,
        source_context: Optional[Dict[str, Any]] = None,
        strategy: Optional[Dict[str, Any]] = None,
        lineage_root_id: str = "",
        rerun_from_task_id: str = "",
    ) -> Dict[str, Any]:
        normalized_kind = str(task_kind or "").strip().lower()
        if normalized_kind not in SUPPORTED_TASK_KINDS:
            raise ValueError(f"不支持的 task_kind: {task_kind}")

        if normalized_kind == "general":
            return self._create_general_task(
                commander=commander,
                user_goal=user_goal,
                source_context=source_context or {},
                strategy=strategy or {},
                lineage_root_id=lineage_root_id,
                rerun_from_task_id=rerun_from_task_id,
            )
        if normalized_kind == "prototype":
            return self._create_prototype_task(
                commander=commander,
                user_goal=user_goal,
                source_context=source_context or {},
                strategy=strategy or {},
                lineage_root_id=lineage_root_id,
                rerun_from_task_id=rerun_from_task_id,
            )
        return self._create_exploration_task(
            commander=commander,
            user_goal=user_goal,
            source_context=source_context or {},
            strategy=strategy or {},
            lineage_root_id=lineage_root_id,
            rerun_from_task_id=rerun_from_task_id,
        )

    def list_tasks(
        self,
        *,
        commander: Any,
        limit: int = 20,
        task_kind: str = "",
        status: str = "",
        lineage_root_id: str = "",
    ) -> List[Dict[str, Any]]:
        missions = []
        normalized_kind = str(task_kind or "").strip().lower()
        normalized_status = str(status or "").strip().lower()
        normalized_lineage_root_id = str(lineage_root_id or "").strip()
        for item in getattr(commander, "_missions", {}).values():
            if isinstance(item, dict):
                mission = item
            else:
                mission = item.to_dict()
            if not mission.get("unified_task"):
                continue
            normalized = self._normalize_task(mission)
            if normalized_kind and str(normalized.get("task_kind") or "").lower() != normalized_kind:
                continue
            if normalized_status and str(normalized.get("status") or "").lower() != normalized_status:
                continue
            if normalized_lineage_root_id and str(normalized.get("lineage_root_id") or "") != normalized_lineage_root_id:
                continue
            missions.append(normalized)
        missions.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return missions[:limit]

    def get_task(self, *, commander: Any, task_id: str) -> Optional[Dict[str, Any]]:
        mission = commander.get_mission(task_id)
        if mission is None:
            return None
        if not mission.get("unified_task"):
            return None
        return self._normalize_task(mission)

    def get_task_result(self, *, commander: Any, task_id: str) -> Optional[Dict[str, Any]]:
        task = self.get_task(commander=commander, task_id=task_id)
        if task is None:
            return None
        return {
            "task_id": task["task_id"],
            "task_kind": task["task_kind"],
            "status": task["status"],
            "result_summary": task["result_summary"],
            "findings": task["findings"],
            "gate_summary": task["gate_summary"],
            "evidence_summary": task["evidence_summary"],
            "recommendations": task["recommendations"],
            "logs": task["logs"],
            "execution_group_id": task["execution_group_id"],
            "lineage_root_id": task["lineage_root_id"],
            "rerun_from_task_id": task["rerun_from_task_id"],
            "verification_state": task["verification_state"],
            "execution_center_path": task["execution_center_path"],
            "quality_gate_path": task["quality_gate_path"],
            "expert_path": task["expert_path"],
            "raw_report": task["raw_report"],
        }

    def cancel_task(self, *, commander: Any, task_id: str) -> Dict[str, Any]:
        mission = getattr(commander, "_missions", {}).get(task_id)
        if mission is None:
            raise KeyError(task_id)
        if not self._is_unified_mission(mission):
            raise KeyError(task_id)

        task_kind = str(self._mission_value(mission, "task_kind") or "general").strip().lower()
        current_status = str(self._mission_value(mission, "status") or "").strip().lower()
        if current_status in {"completed", "failed", "cancelled"}:
            return {
                "task_id": task_id,
                "cancelled": False,
                "status": current_status or "unknown",
                "message": "当前任务已结束，无法再次停止。",
            }

        cancelled = False
        message = "当前任务暂不支持停止。"
        if task_kind == "exploration":
            cancelled = self._cancel_exploration_task(mission)
            message = "探索任务已停止。" if cancelled else "探索任务当前无法可靠停止。"
        else:
            cancelled = bool(getattr(commander, "cancel_mission")(task_id))
            message = "任务已停止。" if cancelled else "当前任务停止失败。"

        if cancelled:
            self._set_mission_value(mission, "status", "cancelled")
            self._set_mission_value(mission, "completed_at", _now_iso())
            agent_states = self._mission_value(mission, "agent_states")
            if not isinstance(agent_states, dict):
                agent_states = {}
                self._set_mission_value(mission, "agent_states", agent_states)
            for agent_id in list(agent_states.keys()):
                if str(agent_states.get(agent_id) or "").lower() in {
                    "running", "pending", "executing", "planning", "dispatching", "reporting", "parsing",
                }:
                    agent_states[agent_id] = "cancelled"
            self._append_log(
                mission,
                "统一前门已停止任务",
                level="warn",
                data={"task_kind": task_kind, "agent_id": "commander"},
            )
            self._save(commander)

        return {
            "task_id": task_id,
            "cancelled": cancelled,
            "status": str(self._mission_value(mission, "status") or current_status or "unknown"),
            "message": message,
        }

    def rerun_task(self, *, commander: Any, task_id: str) -> Dict[str, Any]:
        mission = getattr(commander, "_missions", {}).get(task_id)
        if mission is None:
            raise KeyError(task_id)
        if not self._is_unified_mission(mission):
            raise KeyError(task_id)

        task_kind = str(self._mission_value(mission, "task_kind") or "general").strip().lower()
        user_goal = str(self._mission_value(mission, "user_input") or "").strip()
        source_context = dict(self._mission_value(mission, "source_context") or {})
        strategy = dict(self._mission_value(mission, "strategy") or {})
        lineage_root_id = str(self._mission_value(mission, "lineage_root_id") or self._mission_value(mission, "mission_id") or "").strip()
        rerun_task = self.create_task(
            commander=commander,
            task_kind=task_kind,
            user_goal=user_goal,
            source_context=source_context,
            strategy=strategy,
            lineage_root_id=lineage_root_id,
            rerun_from_task_id=str(self._mission_value(mission, "mission_id") or "").strip(),
        )
        previous_logs = self._mission_value(mission, "logs")
        if isinstance(previous_logs, list):
            self._append_log(
                mission,
                f"统一前门已基于当前任务重新运行，新任务 {rerun_task['task_id']}",
                data={"task_kind": task_kind, "agent_id": "commander", "rerun_task_id": rerun_task["task_id"]},
            )
            self._save(commander)
        return rerun_task

    def _create_general_task(
        self,
        *,
        commander: Any,
        user_goal: str,
        source_context: Dict[str, Any],
        strategy: Dict[str, Any],
        lineage_root_id: str,
        rerun_from_task_id: str,
    ) -> Dict[str, Any]:
        mission_id = uuid.uuid4().hex[:8]
        target_url = str(source_context.get("target_url") or "").strip()
        mission = {
            "mission_id": mission_id,
            "mission_kind": "commander",
            "task_kind": "general",
            "unified_task": True,
            "user_input": user_goal,
            "target_url": target_url,
            "status": "pending",
            "created_at": _now_iso(),
            "started_at": None,
            "completed_at": None,
            "strategy": strategy,
            "source_context": source_context,
            "agent_states": {
                "orchestrator": "idle",
                "planner": "idle",
                "executor": "idle",
                "commander": "idle",
            },
            "report": None,
            "logs": [],
            "execution_group_id": mission_id,
            "lineage_root_id": lineage_root_id or mission_id,
            "rerun_from_task_id": rerun_from_task_id,
            "execution_center_path": f"/history?group={mission_id}",
            "bug_summary": [],
        }
        getattr(commander, "_missions", {})[mission_id] = mission
        self._append_log(
            mission,
            "统一前门已创建通用任务",
            data={"task_kind": "general", "agent_id": "commander"},
        )
        self._save(commander)

        async def _run_in_background() -> None:
            try:
                await commander.run(
                    user_input=user_goal,
                    target_url=target_url,
                    parallel=_safe_bool(strategy.get("parallel"), True),
                    mission_id=mission_id,
                    mission_kind="commander",
                    task_kind="general",
                    source_context=source_context,
                    unified_task=True,
                )
            except Exception as exc:
                logger.error("Unified general task %s failed: %s", mission_id, exc, exc_info=True)
                failed_mission = getattr(commander, "_missions", {}).get(mission_id)
                if isinstance(failed_mission, dict):
                    failed_mission["status"] = "failed"
                    failed_mission["completed_at"] = _now_iso()
                    failed_mission.setdefault("agent_states", {})
                    failed_mission["agent_states"]["commander"] = "error"
                    self._append_log(
                        failed_mission,
                        f"通用任务异常: {exc}",
                        level="error",
                        data={"task_kind": "general", "agent_id": "commander"},
                    )
                    self._save(commander)

        asyncio.create_task(_run_in_background())
        return self.get_task(commander=commander, task_id=mission_id) or self._normalize_task(mission)

    def _create_prototype_task(
        self,
        *,
        commander: Any,
        user_goal: str,
        source_context: Dict[str, Any],
        strategy: Dict[str, Any],
        lineage_root_id: str,
        rerun_from_task_id: str,
    ) -> Dict[str, Any]:
        mission_id = uuid.uuid4().hex[:8]
        payload = {
            "source_type": str(source_context.get("source_type") or "url"),
            "source": str(source_context.get("source") or "").strip(),
            "compare_source": str(source_context.get("compare_source") or "").strip(),
            "playbook_id": str(source_context.get("playbook_id") or "").strip(),
            "wcag_level": str(strategy.get("wcag_level") or "AA"),
            "worker_switches": dict(strategy.get("worker_switches") or {}),
            "providers": dict(strategy.get("providers") or {}),
        }
        service = get_prototype_agents_service()
        mission = service.create_mission(payload, mission_id=mission_id)
        mission["unified_task"] = True
        mission["task_kind"] = "prototype"
        mission["user_input"] = user_goal or mission.get("user_input") or "原型测试"
        mission["source_context"] = source_context
        mission["strategy"] = {
            **(mission.get("strategy") or {}),
            "user_goal": user_goal,
        }
        mission["lineage_root_id"] = lineage_root_id or mission_id
        mission["rerun_from_task_id"] = rerun_from_task_id
        getattr(commander, "_missions", {})[mission_id] = mission
        self._append_log(
            mission,
            "统一前门已创建原型任务",
            data={"task_kind": "prototype", "agent_id": "orchestrator"},
        )
        self._save(commander)

        async def _run_in_background() -> None:
            try:
                await service.run_mission(commander, mission_id, payload)
            except Exception as exc:
                logger.error("Unified prototype task %s failed: %s", mission_id, exc, exc_info=True)
                failed_mission = getattr(commander, "_missions", {}).get(mission_id)
                if isinstance(failed_mission, dict):
                    failed_mission["status"] = "failed"
                    failed_mission["completed_at"] = _now_iso()
                    failed_mission.setdefault("agent_states", {})
                    failed_mission["agent_states"]["orchestrator"] = "error"
                    failed_mission["agent_states"]["reporter"] = "error"
                    self._append_log(
                        failed_mission,
                        f"原型任务异常: {exc}",
                        level="error",
                        data={"task_kind": "prototype", "agent_id": "orchestrator"},
                    )
                    self._save(commander)

        asyncio.create_task(_run_in_background())
        return self.get_task(commander=commander, task_id=mission_id) or self._normalize_task(mission)

    def _create_exploration_task(
        self,
        *,
        commander: Any,
        user_goal: str,
        source_context: Dict[str, Any],
        strategy: Dict[str, Any],
        lineage_root_id: str,
        rerun_from_task_id: str,
    ) -> Dict[str, Any]:
        mission_id = uuid.uuid4().hex[:8]
        target_url = str(source_context.get("target_url") or "").strip()
        mission = {
            "mission_id": mission_id,
            "mission_kind": "exploration_frontdoor",
            "task_kind": "exploration",
            "unified_task": True,
            "user_input": user_goal or f"探索性测试 · {target_url or '未命名目标'}",
            "target_url": target_url,
            "status": "pending",
            "created_at": _now_iso(),
            "started_at": None,
            "completed_at": None,
            "strategy": strategy,
            "source_context": source_context,
            "agent_states": {
                "orchestrator": "idle",
                "planner": "idle",
                "executor": "idle",
            },
            "report": None,
            "logs": [],
            "execution_group_id": mission_id,
            "lineage_root_id": lineage_root_id or mission_id,
            "rerun_from_task_id": rerun_from_task_id,
            "execution_center_path": f"/history?group={mission_id}",
            "bug_summary": [],
        }
        getattr(commander, "_missions", {})[mission_id] = mission
        self._append_log(
            mission,
            "统一前门已创建探索任务",
            data={"task_kind": "exploration", "agent_id": "orchestrator"},
        )
        self._save(commander)

        async def _run_in_background() -> None:
            try:
                await self._run_exploration_pipeline(
                    commander=commander,
                    mission_id=mission_id,
                    user_goal=user_goal,
                    source_context=source_context,
                    strategy=strategy,
                )
            except Exception as exc:
                logger.error("Unified exploration task %s failed: %s", mission_id, exc, exc_info=True)
                failed_mission = getattr(commander, "_missions", {}).get(mission_id)
                if isinstance(failed_mission, dict):
                    failed_mission["status"] = "failed"
                    failed_mission["completed_at"] = _now_iso()
                    failed_mission.setdefault("agent_states", {})
                    failed_mission["agent_states"]["orchestrator"] = "error"
                    self._append_log(
                        failed_mission,
                        f"探索任务异常: {exc}",
                        level="error",
                        data={"task_kind": "exploration", "agent_id": "orchestrator"},
                    )
                    self._save(commander)

        asyncio.create_task(_run_in_background())
        return self.get_task(commander=commander, task_id=mission_id) or self._normalize_task(mission)

    async def _run_exploration_pipeline(
        self,
        *,
        commander: Any,
        mission_id: str,
        user_goal: str,
        source_context: Dict[str, Any],
        strategy: Dict[str, Any],
    ) -> None:
        from main import get_orchestrator

        mission = getattr(commander, "_missions", {}).get(mission_id)
        if not isinstance(mission, dict):
            raise ValueError(f"未找到统一探索任务: {mission_id}")

        session_id = f"frontdoor_{mission_id}"
        target_url = str(source_context.get("target_url") or "").strip()
        max_steps = _safe_int(strategy.get("max_steps"), 20)
        click_depth = _safe_int(strategy.get("click_depth"), 3)
        planner_mode = str(strategy.get("planner_mode") or "smart")
        execution_mode = str(strategy.get("execution_mode") or "default")
        interaction_policy = str(strategy.get("interaction_policy") or "default")
        exclusion = str(strategy.get("exclude_paths") or "").strip()
        hint_parts = [
            f"探索性测试: 自动探索 {target_url or '目标页面'}",
            f"目标={user_goal or '发现潜在问题'}",
            f"最大步骤={max_steps}",
            f"点击深度={click_depth}",
        ]
        if exclusion:
            hint_parts.append(f"排除路径={exclusion}")
        task_requirement = "，".join(hint_parts)

        orch = get_orchestrator(session_id)
        mission["started_at"] = _now_iso()
        mission["status"] = "executing"
        mission["agent_states"] = {
            "orchestrator": "running",
            "planner": "running",
            "executor": "running",
        }
        self._append_log(
            mission,
            "探索任务已进入编排主链",
            data={
                "task_kind": "exploration",
                "session_id": session_id,
                "agent_id": "orchestrator",
            },
        )
        self._save(commander)

        orch.start_task(
            task_requirement,
            mode=planner_mode,
            target_url=target_url,
            browser_mode=str(strategy.get("browser_mode") or "chromium"),
            execution_group_id=mission_id,
            execution_mode=execution_mode,
            interaction_policy=interaction_policy,
        )
        mission["source_context"] = {
            **source_context,
            "session_id": session_id,
            "active_task_id": getattr(orch, "active_task_id", ""),
        }
        self._save(commander)

        session = orch.session
        last_index = 0
        while True:
            logs = session.get_logs()
            if last_index < len(logs):
                for log in logs[last_index:]:
                    self._append_session_log(mission, log)
                last_index = len(logs)
                self._save(commander)

            if not orch.is_running:
                break
            await asyncio.sleep(1)

        logs = session.get_logs()
        if last_index < len(logs):
            for log in logs[last_index:]:
                self._append_session_log(mission, log)

        group_detail = get_execution_center_service().get_group_detail(mission_id) or {}
        findings = self._build_exploration_findings(logs)
        error_count = len(findings)
        record_count = len(group_detail.get("records") or [])
        group_status = str(group_detail.get("status") or "").lower()
        completed_status = "completed"
        if group_status in {"failed", "error", "cancelled"}:
            completed_status = "failed"

        mission["report"] = {
            "summary": {
                "task_kind": "exploration",
                "target_url": target_url,
                "log_count": len(logs),
                "error_count": error_count,
                "record_count": record_count,
                "group_status": group_detail.get("status") or completed_status,
                "session_id": session_id,
                "active_task_id": getattr(orch, "active_task_id", ""),
            },
            "findings": findings,
            "recommendations": self._build_exploration_recommendations(findings),
            "quality_gate_metrics": {
                "blocking_gap_count": 1 if error_count > 0 else 0,
                "cross_module_chain_gap_count": 0,
                "static_unprovable_count": 1,
                "log_count": len(logs),
                "error_count": error_count,
            },
        }
        mission["bug_summary"] = [
            {
                "test_type": "exploration",
                "title": item.get("title") or "探索性问题",
                "status": "failed",
                "summary": item.get("summary") or "",
            }
            for item in findings[:10]
        ]
        mission["status"] = completed_status
        mission["completed_at"] = _now_iso()
        mission["agent_states"] = {
            "orchestrator": "success" if completed_status == "completed" else "error",
            "planner": "success" if completed_status == "completed" else "error",
            "executor": "success" if completed_status == "completed" else "error",
        }
        self._append_log(
            mission,
            "探索任务已完成",
            data={
                "task_kind": "exploration",
                "agent_id": "orchestrator",
                "finding_count": len(findings),
                "group_status": group_detail.get("status") or completed_status,
            },
        )
        self._save(commander)

    def _append_session_log(self, mission: Dict[str, Any], log: Dict[str, Any]) -> None:
        log_type = str(log.get("type") or "observation").lower()
        level = "info"
        if log_type in {"error", "fatal"}:
            level = "error"
        elif log_type in {"warning", "warn"}:
            level = "warn"
        elif log_type == "assertion" and str(log.get("status") or "").lower() == "fail":
            level = "error"
        message = str(log.get("content") or log.get("message") or log_type or "日志")
        self._append_log(
            mission,
            message,
            level=level,
            data={"task_kind": "exploration", "log_type": log_type},
        )

    def _build_exploration_findings(self, logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        for index, log in enumerate(logs, start=1):
            log_type = str(log.get("type") or "").lower()
            if log_type == "error":
                findings.append(
                    {
                        "finding_id": f"explore-error-{index}",
                        "severity": "major",
                        "title": "探索过程中发现错误日志",
                        "summary": str(log.get("content") or "执行过程中出现错误"),
                        "category": "broken_flow",
                        "agent_id": "executor",
                    }
                )
            elif log_type == "assertion" and str(log.get("status") or "").lower() == "fail":
                findings.append(
                    {
                        "finding_id": f"explore-assert-{index}",
                        "severity": "major",
                        "title": "探索过程中出现断言失败",
                        "summary": str(log.get("content") or "断言失败"),
                        "category": "broken_flow",
                        "agent_id": "executor",
                    }
                )
        return findings[:20]

    def _build_exploration_recommendations(self, findings: List[Dict[str, Any]]) -> List[str]:
        if not findings:
            return ["当前探索性测试未发现明显阻断问题，建议继续补充真实业务路径和异常边界复核。"]
        return [
            "优先复核探索过程中出现的错误日志和断言失败，确认是否为真实流程断点。",
            "将探索结果回灌为场景链或显式测试用例，避免问题只停留在一次性探索发现。",
            "对静态或当前上下文无法证明的点，安排真实账号、真实数据或更完整环境复测。",
        ]

    def _normalize_task(self, mission: Dict[str, Any]) -> Dict[str, Any]:
        task_kind = str(self._mission_value(mission, "task_kind") or "general")
        report = self._mission_value(mission, "report") or {}
        findings = self._normalize_findings(self._extract_findings(mission), mission=mission)
        evidence_summary = self._build_evidence_summary(mission, findings)
        gate_summary = self._build_gate_summary(task_kind=task_kind, mission=mission, findings=findings, report=report)
        verification_state = self._build_verification_state(task_kind=task_kind, gate_summary=gate_summary, findings=findings)
        recommendations = self._build_recommendations(task_kind=task_kind, mission=mission, findings=findings, report=report)
        return {
            "task_id": self._mission_value(mission, "mission_id") or "",
            "mission_kind": self._mission_value(mission, "mission_kind") or "",
            "task_kind": task_kind,
            "user_goal": self._mission_value(mission, "user_input") or "",
            "status": self._mission_value(mission, "status") or "unknown",
            "created_at": self._mission_value(mission, "created_at"),
            "started_at": self._mission_value(mission, "started_at"),
            "completed_at": self._mission_value(mission, "completed_at"),
            "source_context": self._mission_value(mission, "source_context") or {},
            "strategy": self._mission_value(mission, "strategy") or {},
            "agent_states": self._mission_value(mission, "agent_states") or {},
            "evidence_summary": evidence_summary,
            "findings": findings,
            "gate_summary": gate_summary,
            "verification_state": verification_state,
            "recommendations": recommendations,
            "result_summary": report.get("summary") or {},
            "logs": self._mission_value(mission, "logs") or [],
            "execution_group_id": self._mission_value(mission, "execution_group_id") or self._mission_value(mission, "mission_id") or "",
            "lineage_root_id": self._mission_value(mission, "lineage_root_id") or self._mission_value(mission, "mission_id") or "",
            "rerun_from_task_id": self._mission_value(mission, "rerun_from_task_id") or "",
            "execution_center_path": self._build_execution_center_path(mission),
            "quality_gate_path": self._build_quality_gate_path(mission=mission, task_kind=task_kind),
            "expert_path": self._resolve_expert_path(task_kind),
            "raw_report": report,
        }

    def _build_execution_center_path(self, mission: Dict[str, Any]) -> str:
        mission_id = str(self._mission_value(mission, "mission_id") or "").strip()
        execution_group_id = str(
            self._mission_value(mission, "execution_group_id")
            or mission_id
            or ""
        ).strip()
        lineage_root_id = str(self._mission_value(mission, "lineage_root_id") or mission_id or "").strip()
        params = {"group": execution_group_id}
        if mission_id:
            params["record"] = mission_id
            params["task_id"] = mission_id
        if lineage_root_id:
            params["lineage_root_id"] = lineage_root_id
        return f"/history?{urlencode(params)}"

    def _build_quality_gate_path(self, *, mission: Dict[str, Any], task_kind: str) -> str:
        mission_id = str(self._mission_value(mission, "mission_id") or "").strip()
        status = str(self._mission_value(mission, "status") or "").strip()
        if not mission_id:
            return "/quality-gate"
        return (
            f"/quality-gate?task_id={mission_id}"
            f"&run_id={mission_id}"
            f"&task_kind={task_kind}"
            f"&status={status}"
            f"&focus=history"
        )

    def _build_evidence_summary(self, mission: Dict[str, Any], findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        report = self._mission_value(mission, "report") or {}
        summary = report.get("summary") or {}
        logs = self._mission_value(mission, "logs") or []
        evidence_ids = [str(item.get("evidence_id") or item.get("finding_id") or "") for item in findings if item.get("evidence_id") or item.get("finding_id")]
        return {
            "log_count": len(logs),
            "finding_count": len(findings),
            "has_report": bool(report),
            "worker_count": len(report.get("worker_results") or []),
            "execution_group_id": self._mission_value(mission, "execution_group_id") or self._mission_value(mission, "mission_id") or "",
            "summary_keys": sorted(summary.keys())[:12],
            "evidence_ids": evidence_ids[:12],
            "latest_log_at": logs[-1].get("timestamp") if logs else None,
            "static_unprovable_count": _safe_int((report.get("quality_gate_metrics") or {}).get("static_unprovable_count")),
        }

    def _build_gate_summary(
        self,
        *,
        task_kind: str,
        mission: Dict[str, Any],
        findings: List[Dict[str, Any]],
        report: Dict[str, Any],
    ) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}
        status = "passed"
        summary = "当前任务已通过统一门面校验。"

        if task_kind == "prototype":
            metrics = dict(report.get("quality_gate_metrics") or {})
            blocking_count = _safe_int(metrics.get("blocking_prototype_gap_count"))
            critical_page_missing = _safe_int(metrics.get("critical_page_missing_count"))
            if blocking_count > 0 or critical_page_missing > 0:
                status = "failed"
                summary = "原型门禁未通过，存在阻断级差异或关键页面缺口。"
            elif findings:
                status = "warning"
                summary = "原型门禁通过，但仍有需复核的结构或流程差异。"
        elif task_kind == "exploration":
            metrics = dict(report.get("quality_gate_metrics") or {})
            error_count = _safe_int(metrics.get("error_count"), len(findings))
            static_unprovable = _safe_int(metrics.get("static_unprovable_count"), 1)
            if error_count > 0:
                status = "failed"
                summary = "探索任务发现错误日志或断言失败，建议进入专家页深挖。"
            elif static_unprovable > 0:
                status = "warning"
                summary = "探索任务完成，但仍有当前上下文无法证明的点。"
        else:
            summary_block = report.get("summary") or {}
            failed_count = _safe_int(summary_block.get("failed"))
            metrics = {
                "total_tests": _safe_int(summary_block.get("total_tests")),
                "failed": failed_count,
                "completed": _safe_int(summary_block.get("completed")),
            }
            if failed_count > 0:
                status = "failed"
                summary = "通用编排存在失败测试线，建议进入执行中心复核。"
            elif findings:
                status = "warning"
                summary = "通用编排已完成，但仍有需要人工确认的失败摘要。"

        return {
            "status": status,
            "summary": summary,
            "metrics": metrics,
            "decision_reason": summary,
        }

    def _build_verification_state(
        self,
        *,
        task_kind: str,
        gate_summary: Dict[str, Any],
        findings: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        gate_status = str(gate_summary.get("status") or "pending").strip().lower()
        static_unprovable = _safe_int((gate_summary.get("metrics") or {}).get("static_unprovable_count"))
        if gate_status == "failed":
            return {
                "status": "issues_found",
                "label": "有明确问题",
                "summary": "当前任务已发现明确问题，需要进入执行中心、专家页或质量门禁继续处理。",
            }
        if static_unprovable > 0:
            return {
                "status": "context_unprovable",
                "label": "当前上下文无法证明",
                "summary": "当前会话、静态原型或当前环境仍无法证明全部关键点，不能视为完全通过。",
            }
        if gate_status == "warning" or findings:
            return {
                "status": "issues_found",
                "label": "有明确问题",
                "summary": "当前任务虽未命中阻断失败，但仍存在需人工确认或复核的问题。",
            }
        if gate_status == "passed":
            return {
                "status": "verified_passed",
                "label": "已验证通过",
                "summary": "当前任务在现有上下文下未发现明确问题，且没有未证明项残留。",
            }
        return {
            "status": "pending",
            "label": "待判定",
            "summary": "当前任务还没有形成稳定结论，建议等待执行完成或补充上下文。",
        }

    def _build_recommendations(
        self,
        *,
        task_kind: str,
        mission: Dict[str, Any],
        findings: List[Dict[str, Any]],
        report: Dict[str, Any],
    ) -> List[str]:
        recommendations = list(report.get("recommendations") or [])
        if recommendations:
            return recommendations[:6]
        if task_kind == "prototype":
            if findings:
                return [
                    "优先处理阻断级原型差异和关键页面映射问题，再进入视觉或样式细节复核。",
                    "对嵌入式承接与独立页面边界不清的地方，先补页面映射依据，避免误判为已覆盖。",
                ]
            return ["当前原型任务未发现明显问题，建议继续补充真实 provider 与门禁规则以提高可信度。"]
        if task_kind == "exploration":
            return self._build_exploration_recommendations(findings)
        if findings:
            return [
                "优先复核失败测试线和失败摘要，确认是否为真实缺陷还是环境/数据波动。",
                "将高频失败模式沉淀成专项 workflow 或 quality gate，避免重复人工判断。",
            ]
        return ["当前通用任务已完成，建议把稳定路径沉淀成场景链和门禁规则。"]

    def _extract_findings(self, mission: Dict[str, Any]) -> List[Dict[str, Any]]:
        report = self._mission_value(mission, "report") or {}
        if isinstance(report.get("findings"), list):
            return list(report.get("findings") or [])

        findings: List[Dict[str, Any]] = []
        for index, item in enumerate(self._mission_value(mission, "bug_summary") or [], start=1):
            findings.append(
                {
                    "finding_id": f"summary-{index}",
                    "severity": "major",
                    "title": str(item.get("title") or "问题摘要"),
                    "summary": str(item.get("summary") or ""),
                    "category": "broken_flow",
                    "agent_id": str(item.get("test_type") or "commander"),
                }
            )
        return findings

    def _normalize_findings(self, findings: List[Dict[str, Any]], *, mission: Dict[str, Any]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        mission_id = str(self._mission_value(mission, "mission_id") or "").strip()
        for index, item in enumerate(findings or [], start=1):
            severity = str(item.get("severity") or "normal")
            finding_id = str(item.get("finding_id") or f"{mission_id}-finding-{index}")
            normalized.append(
                {
                    "finding_id": finding_id,
                    "evidence_id": str(item.get("evidence_id") or finding_id),
                    "severity": severity,
                    "title": str(item.get("title") or "问题发现"),
                    "summary": str(item.get("summary") or ""),
                    "category": str(item.get("category") or "scope_gap"),
                    "agent_id": str(item.get("agent_id") or "unknown"),
                    "source_type": str(item.get("source_type") or "mission"),
                    "locator": str(item.get("locator") or mission_id),
                }
            )
        return normalized[:20]

    def _resolve_expert_path(self, task_kind: str) -> str:
        if task_kind == "prototype":
            return "/prototype-agents"
        if task_kind == "exploration":
            return "/exploratory"
        return "/orchestrator"

    def _append_log(
        self,
        mission: Any,
        message: str,
        *,
        level: str = "info",
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        logs = self._mission_value(mission, "logs")
        if not isinstance(logs, list):
            logs = []
            self._set_mission_value(mission, "logs", logs)
        logs.append(
            {
                "timestamp": _now_iso(),
                "level": level,
                "message": message,
                "data": data or {},
            }
        )

    def _mission_value(self, mission: Any, key: str) -> Any:
        if isinstance(mission, dict):
            return mission.get(key)
        return getattr(mission, key, None)

    def _set_mission_value(self, mission: Any, key: str, value: Any) -> None:
        if isinstance(mission, dict):
            mission[key] = value
        else:
            setattr(mission, key, value)

    def _is_unified_mission(self, mission: Any) -> bool:
        return bool(self._mission_value(mission, "unified_task"))

    def _cancel_exploration_task(self, mission: Any) -> bool:
        try:
            from main import get_orchestrator

            source_context = self._mission_value(mission, "source_context") or {}
            session_id = str(source_context.get("session_id") or "").strip()
            if not session_id:
                return False
            orch = get_orchestrator(session_id)
            if getattr(orch, "is_running", False):
                orch.stop_task()
            return True
        except Exception:
            logger.warning("探索任务停止失败", exc_info=True)
            return False

    def _save(self, commander: Any) -> None:
        save_fn = getattr(commander, "_save_missions", None)
        if callable(save_fn):
            try:
                save_fn()
            except Exception:
                logger.debug("UnifiedTaskService save skipped", exc_info=True)


_service: Optional[UnifiedTaskService] = None


def get_unified_task_service() -> UnifiedTaskService:
    global _service
    if _service is None:
        _service = UnifiedTaskService()
    return _service
