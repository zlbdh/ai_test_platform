# -*- coding: utf-8 -*-
"""
Unified task entry service.

Phase one goals:
1. Unify the general / prototype / exploration entry protocol.
2. Unify task read models, evidence summaries, gate summaries, and result structures.
3. Keep existing executors, pages, and APIs operational without rewriting them.
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
    """Unified task facade."""

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
            raise ValueError(f"Unsupported task_kind: {task_kind}")

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
                "message": "This task has already finished and cannot be stopped again.",
            }

        cancelled = False
        message = "Stopping is not currently supported for this task."
        if task_kind == "exploration":
            cancelled = self._cancel_exploration_task(mission)
            message = "Exploration task stopped." if cancelled else "The exploration task cannot currently be stopped reliably."
        else:
            cancelled = bool(getattr(commander, "cancel_mission")(task_id))
            message = "Task stopped." if cancelled else "Failed to stop the current task."

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
                "The unified entry service stopped the task",
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
                f"The unified entry service reran this task as new task {rerun_task['task_id']}",
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
            "The unified entry service created a general task",
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
                        f"General task error: {exc}",
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
        mission["user_input"] = user_goal or mission.get("user_input") or "Prototype testing"
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
            "The unified entry service created a prototype task",
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
                        f"Prototype task error: {exc}",
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
            "user_input": user_goal or f"Exploratory testing · {target_url or 'Unnamed target'}",
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
            "The unified entry service created an exploration task",
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
                        f"Exploration task error: {exc}",
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
            raise ValueError(f"Unified exploration task not found: {mission_id}")

        session_id = f"frontdoor_{mission_id}"
        target_url = str(source_context.get("target_url") or "").strip()
        max_steps = _safe_int(strategy.get("max_steps"), 20)
        click_depth = _safe_int(strategy.get("click_depth"), 3)
        planner_mode = str(strategy.get("planner_mode") or "smart")
        execution_mode = str(strategy.get("execution_mode") or "default")
        interaction_policy = str(strategy.get("interaction_policy") or "default")
        exclusion = str(strategy.get("exclude_paths") or "").strip()
        hint_parts = [
            f"Exploratory testing: automatically explore {target_url or 'the target page'}",
            f"Goal={user_goal or 'Find potential issues'}",
            f"Maximum steps={max_steps}",
            f"Click depth={click_depth}",
        ]
        if exclusion:
            hint_parts.append(f"Excluded paths={exclusion}")
        task_requirement = ", ".join(hint_parts)

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
            "Exploration task entered the main orchestration workflow",
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
                "title": item.get("title") or "Exploratory finding",
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
            "Exploration task completed",
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
        message = str(log.get("content") or log.get("message") or log_type or "Log")
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
                        "title": "Error log detected during exploration",
                        "summary": str(log.get("content") or "An error occurred during execution"),
                        "category": "broken_flow",
                        "agent_id": "executor",
                    }
                )
            elif log_type == "assertion" and str(log.get("status") or "").lower() == "fail":
                findings.append(
                    {
                        "finding_id": f"explore-assert-{index}",
                        "severity": "major",
                        "title": "Assertion failed during exploration",
                        "summary": str(log.get("content") or "Assertion failed"),
                        "category": "broken_flow",
                        "agent_id": "executor",
                    }
                )
        return findings[:20]

    def _build_exploration_recommendations(self, findings: List[Dict[str, Any]]) -> List[str]:
        if not findings:
            return ["This exploratory test found no obvious blocking issues. Add real business paths and review exception boundaries."]
        return [
            "First review error logs and assertion failures from exploration to determine whether they indicate actual workflow failures.",
            "Convert exploratory findings into scenario chains or explicit test cases so they become repeatable checks.",
            "For points that static evidence or the current context cannot prove, retest with real accounts, real data, or a more complete environment.",
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
        summary = "This task passed the unified facade checks."

        if task_kind == "prototype":
            metrics = dict(report.get("quality_gate_metrics") or {})
            blocking_count = _safe_int(metrics.get("blocking_prototype_gap_count"))
            critical_page_missing = _safe_int(metrics.get("critical_page_missing_count"))
            if blocking_count > 0 or critical_page_missing > 0:
                status = "failed"
                summary = "The prototype gate failed because of blocking discrepancies or missing critical pages."
            elif findings:
                status = "warning"
                summary = "The prototype gate passed, but structural or workflow discrepancies still need review."
        elif task_kind == "exploration":
            metrics = dict(report.get("quality_gate_metrics") or {})
            error_count = _safe_int(metrics.get("error_count"), len(findings))
            static_unprovable = _safe_int(metrics.get("static_unprovable_count"), 1)
            if error_count > 0:
                status = "failed"
                summary = "The exploration task found error logs or assertion failures. Investigate further on the expert page."
            elif static_unprovable > 0:
                status = "warning"
                summary = "The exploration task completed, but some points cannot be proven in the current context."
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
                summary = "General orchestration has failed test tracks. Review them in the execution center."
            elif findings:
                status = "warning"
                summary = "General orchestration completed, but some failure summaries still require human confirmation."

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
                "label": "Issues found",
                "summary": "This task found definite issues. Continue investigating in the execution center, expert page, or quality gate.",
            }
        if static_unprovable > 0:
            return {
                "status": "context_unprovable",
                "label": "Cannot be proven in the current context",
                "summary": "The current session, static prototype, or environment cannot prove all key points, so this is not a complete pass.",
            }
        if gate_status == "warning" or findings:
            return {
                "status": "issues_found",
                "label": "Issues found",
                "summary": "This task has no blocking failure, but some issues still need human confirmation or review.",
            }
        if gate_status == "passed":
            return {
                "status": "verified_passed",
                "label": "Verified pass",
                "summary": "This task found no definite issues in the current context and has no remaining unproven items.",
            }
        return {
            "status": "pending",
            "label": "Pending assessment",
            "summary": "This task has no stable conclusion yet. Wait for execution to finish or provide more context.",
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
                    "Resolve blocking prototype discrepancies and critical page-mapping issues before reviewing visual or styling details.",
                    "Where embedded destinations and standalone pages are hard to distinguish, document the mapping evidence first to avoid false coverage.",
                ]
            return ["This prototype task found no obvious issues. Add real providers and gate rules to increase confidence."]
        if task_kind == "exploration":
            return self._build_exploration_recommendations(findings)
        if findings:
            return [
                "First review failed test tracks and failure summaries to distinguish actual defects from environment or data variability.",
                "Turn recurring failure patterns into dedicated workflows or quality gates to avoid repeated manual judgments.",
            ]
        return ["This general task is complete. Capture stable paths as scenario chains and gate rules."]

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
                    "title": str(item.get("title") or "Issue summary"),
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
                    "title": str(item.get("title") or "Finding"),
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
            logger.warning("Failed to stop the exploration task", exc_info=True)
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
