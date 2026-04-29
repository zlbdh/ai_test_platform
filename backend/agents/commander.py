# -*- coding: utf-8 -*-
"""
Commander — 总指挥编排引擎

核心职责：
    用户一句话 → 自动解析需求 → 选择策略 → 分发任务 → 并行执行 → 汇总报告

设计原则：
    1. Commander 本身 **不执行测试**，只做编排调度
    2. 串联 5 个已有模块（RequirementParser / StrategySelector / TestScheduler / AgentBus / MasterAgent）
    3. 所有旧路由不动，Commander 加旁路（/api/commander/...），零迁移风险

支持的测试线：
    - UI E2E:       Orchestrator → PlannerAgent + ExecutorAgent
    - API REST:     APIAgent / api_workbench
    - Security:     SecurityScanner / EnhancedSecurity
    - Performance:  PerformanceRunner
    - Database:     DataAgent / DatabaseManager
    - Accessibility: AccessibilityTesting
    - Visual:       VisualRegression
"""

import asyncio
import json as _json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 持久化目录
_MISSIONS_DIR = Path(__file__).resolve().parent.parent / "data"
_MISSIONS_FILE = _MISSIONS_DIR / "commander_missions.json"


# ── 数据结构 ──────────────────────────────────────────────────────────────────


class MissionStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    PARSING = "parsing"       # 解析需求中
    PLANNING = "planning"     # 选择策略中
    DISPATCHING = "dispatching"  # 分发任务中
    EXECUTING = "executing"   # 执行测试中
    REPORTING = "reporting"   # 生成报告中
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class MissionLog:
    """任务日志条目"""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    level: str = "info"       # info / warn / error / progress
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Mission:
    """一次 Commander 任务"""
    mission_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    mission_kind: str = "commander"
    task_kind: str = "general"
    unified_task: bool = False
    user_input: str = ""
    target_url: str = ""
    status: MissionStatus = MissionStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # 中间产物
    parsed_requirement: Optional[Dict] = None
    strategy: Optional[Dict] = None
    source_context: Dict[str, Any] = field(default_factory=dict)
    agent_states: Dict[str, str] = field(default_factory=dict)
    test_tasks: List[Dict] = field(default_factory=list)
    test_results: List[Dict] = field(default_factory=list)
    report: Optional[Dict] = None

    # 日志
    logs: List[MissionLog] = field(default_factory=list)

    # 追踪
    trace_id: Optional[str] = None
    execution_group_id: str = ""

    def log(self, message: str, level: str = "info", data: Dict = None):
        entry = MissionLog(
            level=level,
            message=message,
            data=data or {},
        )
        self.logs.append(entry)
        logger.info(f"[Commander][{self.mission_id}] {message}")

        # SSE 推送：发布到 EventBus，供前端 NotificationCenter 消费
        try:
            from core.event_bus import EventBus
            EventBus.instance().put({
                "type": "commander_log",
                "mission_id": self.mission_id,
                "level": level,
                "message": message,
                "data": data or {},
                "timestamp": entry.timestamp,
            })
        except Exception:
            pass  # EventBus 未初始化时静默

    def to_dict(self) -> dict:
        bug_summary = []
        if isinstance(self.report, dict):
            bug_summary = self.report.get("bug_summary", []) or []
        return {
            "mission_id": self.mission_id,
            "mission_kind": self.mission_kind,
            "task_kind": self.task_kind,
            "unified_task": self.unified_task,
            "user_input": self.user_input,
            "target_url": self.target_url,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "strategy": self.strategy,
            "source_context": self.source_context,
            "agent_states": self.agent_states,
            "test_tasks_count": len(self.test_tasks),
            "test_results_count": len(self.test_results),
            "report": self.report,
            "logs": [asdict(l) for l in self.logs[-20:]],  # 最近 20 条
            "trace_id": self.trace_id,
            "execution_group_id": self.execution_group_id or self.mission_id,
            "execution_center_path": f"/history?group={self.execution_group_id or self.mission_id}",
            "bug_summary": bug_summary,
        }


# ── 测试线映射 ────────────────────────────────────────────────────────────────

# StrategySelector 返回的 TestType.value → 具体执行方法名
_TEST_LINE_MAP = {
    "ui_e2e": "_run_ui_test",
    "api_rest": "_run_api_test",
    "api_graphql": "_run_api_test",
    "security": "_run_security_test",
    "performance": "_run_performance_test",
    "database": "_run_database_test",
    "accessibility": "_run_accessibility_test",
    "visual_regression": "_run_visual_test",
}

_TEST_TYPE_LABELS = {
    "ui_e2e": "UI 自动化",
    "api_rest": "API 测试",
    "api_graphql": "GraphQL 测试",
    "security": "安全扫描",
    "performance": "性能测试",
    "database": "数据库测试",
    "accessibility": "无障碍测试",
    "visual_regression": "视觉回归",
}

_SUCCESS_RESULT_STATUSES = {"completed", "success", "healed", "recovered"}
_FAILED_RESULT_STATUSES = {"error", "failed", "timeout", "cancelled"}


# ── Commander 核心 ───────────────────────────────────────────────────────────


class Commander:
    """
    总指挥编排引擎

    一句话输入 → 自动多线执行 → 汇总报告
    """

    def __init__(self):
        # 延迟导入，避免循环依赖
        self._missions: Dict[str, Mission] = {}
        _MISSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self._load_missions()
        self._register_profiles()
        logger.info(f"[Commander] 初始化完成，已加载 {len(self._missions)} 条历史任务")

    def _register_profiles(self):
        """启动时自动将所有 Agent Profile 注册到 AgentBus"""
        try:
            from core.agent_profile import get_profile_manager
            from core.agent_bus import get_agent_bus

            pm = get_profile_manager()
            bus = get_agent_bus()

            for profile in pm.list_all():
                bus.register_agent(
                    agent_name=profile.agent_id,
                    agent_type=profile.role,
                    supported_test_types=profile.supported_types,
                    description=profile.description,
                    profile_id=profile.agent_id,
                )
            logger.info(f"[Commander] 注册 {len(pm.list_all())} 个 Agent Profile 到 AgentBus")
        except Exception as e:
            logger.warning(f"[Commander] Profile 注册失败（非阻塞）: {e}")

    def _save_missions(self):
        """持久化 missions 到磁盘 JSON"""
        try:
            data = {}
            for mid, m in self._missions.items():
                if isinstance(m, Mission):
                    d = m.to_dict()
                    # to_dict 已处理了 logs 截断，这里保留全部
                    d["logs"] = [asdict(l) for l in m.logs]
                    data[mid] = d
                elif isinstance(m, dict):
                    data[mid] = m
            # 只保留最近 100 条任务
            if len(data) > 100:
                sorted_items = sorted(data.items(), key=lambda x: x[1].get("created_at", ""), reverse=True)
                data = dict(sorted_items[:100])
            _MISSIONS_FILE.write_text(_json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        except Exception as e:
            logger.warning(f"[Commander] 持久化失败: {e}")

    def _load_missions(self):
        """从磁盘 JSON 加载历史 missions"""
        if not _MISSIONS_FILE.exists():
            return
        try:
            raw = _json.loads(_MISSIONS_FILE.read_text(encoding="utf-8"))
            for mid, data in raw.items():
                self._missions[mid] = data  # 以 dict 形式保留历史
            logger.info(f"[Commander] 从磁盘加载 {len(raw)} 条任务")
        except Exception as e:
            logger.warning(f"[Commander] 加载历史失败: {e}")

    @staticmethod
    def _build_group_title(user_input: str, target_url: str = "") -> str:
        label = (user_input or "").strip() or (target_url or "").strip() or "未命名军团任务"
        return f"军团测试 · {label[:48]}"

    @staticmethod
    def _build_system_log(content: str) -> Dict[str, Any]:
        return {"type": "system", "content": content}

    @staticmethod
    def _build_observation_log(content: str) -> Dict[str, Any]:
        return {"type": "observation", "content": content}

    @staticmethod
    def _build_error_log(content: str) -> Dict[str, Any]:
        return {"type": "error", "content": content}

    @staticmethod
    def _build_assertion_log(target: str, passed: bool, content: str) -> Dict[str, Any]:
        return {
            "type": "assertion",
            "status": "pass" if passed else "fail",
            "action": "assert",
            "step": target,
            "target": target,
            "content": content,
        }

    @staticmethod
    def _is_result_success(status: str) -> bool:
        return str(status or "").lower() in _SUCCESS_RESULT_STATUSES

    @staticmethod
    def _is_result_failure(status: str) -> bool:
        return str(status or "").lower() in _FAILED_RESULT_STATUSES

    @staticmethod
    def _label_for_test_type(test_type: str) -> str:
        return _TEST_TYPE_LABELS.get(test_type, str(test_type or "未命名测试").replace("_", " ").strip() or "未命名测试")

    def _sync_execution_group(self, mission: Mission, status: Optional[str] = None) -> None:
        try:
            from services.execution_center_service import get_execution_center_service

            get_execution_center_service().ensure_group(
                group_id=mission.execution_group_id or mission.mission_id,
                title=self._build_group_title(mission.user_input, mission.target_url),
                requirement=mission.user_input or mission.target_url or mission.mission_id,
                target_url=mission.target_url or "",
                mode="commander",
                source="commander",
                root_task_id=mission.mission_id,
                session_id=f"commander_mission_{mission.mission_id}",
                created_at=mission.started_at or mission.created_at,
                status=status or mission.status.value,
            )
        except Exception as exc:
            logger.warning("[Commander] 同步执行中心批次失败: %s", exc)

    def _decorate_tasks(self, mission: Mission, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        group_id = mission.execution_group_id or mission.mission_id
        group_title = self._build_group_title(mission.user_input, mission.target_url)
        mission_session_id = f"commander_mission_{mission.mission_id}"
        for index, task in enumerate(tasks, start=1):
            test_type = str(task.get("test_type") or "unknown")
            task["mission_id"] = mission.mission_id
            task["execution_group_id"] = group_id
            task["group_title"] = group_title
            task["mission_session_id"] = mission_session_id
            task["execution_record_id"] = task.get("execution_record_id") or f"commander_{mission.mission_id}_{test_type}_{index}"
        return tasks

    def _extract_duration_ms(self, result: Dict[str, Any]) -> int:
        payload = result.get("result") if isinstance(result.get("result"), dict) else {}
        duration_s = payload.get("duration_s")
        if isinstance(duration_s, (int, float)):
            return int(float(duration_s) * 1000)
        duration_ms = payload.get("duration_ms")
        if isinstance(duration_ms, (int, float)):
            return int(duration_ms)
        duration = payload.get("duration")
        if isinstance(duration, (int, float)):
            return int(float(duration) * 1000)
        return 0

    def _build_task_summary(self, task: Dict[str, Any], result: Dict[str, Any]) -> str:
        test_type = str(task.get("test_type") or "")
        payload = result.get("result") if isinstance(result.get("result"), dict) else {}
        error = str(result.get("error") or "").strip()
        if error:
            return error

        if test_type == "ui_e2e":
            errors = payload.get("errors") or []
            if errors:
                return str(errors[0])
            return f"执行 {payload.get('total_steps', 0)} 步，发现 {payload.get('error_count', 0)} 个错误"

        if test_type == "security":
            alerts = payload.get("alerts") or []
            if alerts:
                first = alerts[0]
                return f"[{first.get('risk', '风险未知')}] {first.get('name') or first.get('description') or '发现安全问题'}"
            return f"安全扫描完成，告警 {len(alerts)} 个"

        if test_type == "performance":
            stats = payload.get("stats") or {}
            failures = int(stats.get("failures", 0) or 0)
            http_5xx = int(stats.get("http_5xx", 0) or 0)
            if failures or http_5xx:
                return f"性能测试失败：失败请求 {failures} 个，HTTP 5xx {http_5xx} 个"
            return f"业务成功率 {float(stats.get('business_success_rate', stats.get('success_rate', 0)) or 0):.2f}%"

        if test_type == "accessibility":
            issues = payload.get("issues") or []
            if issues:
                first = issues[0]
                if isinstance(first, dict):
                    return str(first.get("description") or first.get("rule_id") or "发现无障碍问题")
                return str(first)
            return str(payload.get("summary") or "无障碍检查通过")

        if test_type == "visual_regression":
            return str(payload.get("note") or f"已发现 {payload.get('baselines_count', 0)} 个视觉基线")

        for key in ("summary", "message", "detail", "note"):
            value = payload.get(key)
            if value:
                return str(value)

        errors = payload.get("errors") or []
        if errors:
            return str(errors[0])
        return f"{self._label_for_test_type(test_type)}执行完成"

    def _build_task_detail_items(self, task: Dict[str, Any], result: Dict[str, Any]) -> List[Dict[str, Any]]:
        test_type = str(task.get("test_type") or "")
        payload = result.get("result") if isinstance(result.get("result"), dict) else {}
        items: List[Dict[str, Any]] = []

        error = str(result.get("error") or "").strip()
        if error:
            items.append({"target": self._label_for_test_type(test_type), "passed": False, "content": error})

        for message in payload.get("errors") or []:
            items.append({"target": self._label_for_test_type(test_type), "passed": False, "content": str(message)})

        if test_type == "security":
            for alert in payload.get("alerts") or []:
                items.append({
                    "target": str(alert.get("name") or alert.get("risk") or "security-alert"),
                    "passed": False,
                    "content": str(alert.get("description") or alert),
                })
        elif test_type == "accessibility":
            for issue in payload.get("issues") or []:
                if isinstance(issue, dict):
                    items.append({
                        "target": str(issue.get("rule_id") or "a11y-issue"),
                        "passed": False,
                        "content": str(issue.get("description") or issue),
                    })
                else:
                    items.append({"target": "a11y-issue", "passed": False, "content": str(issue)})
        elif test_type == "visual_regression":
            for baseline in payload.get("baselines") or []:
                items.append({"target": str(baseline), "passed": True, "content": "已存在视觉基线"})

        if not items:
            items.append({
                "target": self._label_for_test_type(test_type),
                "passed": self._is_result_success(result.get("status", "")),
                "content": self._build_task_summary(task, result),
            })
        return items[:6]

    def _persist_missing_task_record(self, mission: Mission, task: Dict[str, Any], result: Dict[str, Any]) -> Optional[str]:
        test_type = str(task.get("test_type") or "")
        if test_type in {"ui_e2e", "security", "performance"}:
            return None

        try:
            from services.execution_center_service import get_execution_center_service

            summary = self._build_task_summary(task, result)
            detail_items = self._build_task_detail_items(task, result)
            success = self._is_result_success(result.get("status", ""))
            title = f"{self._label_for_test_type(test_type)} · {task.get('target_url') or mission.target_url or task.get('user_input') or '-'}"
            logs: List[Dict[str, Any]] = [
                self._build_system_log(f"{self._label_for_test_type(test_type)}完成：{task.get('target_url') or mission.target_url or '-'}"),
                self._build_assertion_log(self._label_for_test_type(test_type), success, summary),
            ]
            for item in detail_items:
                logs.append(
                    self._build_assertion_log(
                        str(item.get("target") or self._label_for_test_type(test_type)),
                        bool(item.get("passed", False)),
                        str(item.get("content") or summary),
                    )
                )
            if not success and summary:
                logs.append(self._build_error_log(summary))

            record_id = task.get("execution_record_id") or f"commander_{mission.mission_id}_{test_type}"
            get_execution_center_service().upsert_run(
                task_id=record_id,
                requirement=title,
                status="success" if success else "failed",
                target_url=task.get("target_url", "") or mission.target_url,
                mode=test_type,
                logs=logs,
                duration_ms=self._extract_duration_ms(result),
                execution_group_id=mission.execution_group_id or mission.mission_id,
                session_id=task.get("mission_session_id"),
                group_title=task.get("group_title"),
                record_kind="child",
            )
            return record_id
        except Exception as exc:
            logger.warning("[Commander] 持久化子任务结果失败: %s", exc)
            return None

    def _infer_existing_execution_record_id(self, result: Dict[str, Any]) -> Optional[str]:
        payload = result.get("result") if isinstance(result.get("result"), dict) else {}
        if result.get("test_type") == "ui_e2e":
            return str(payload.get("task_id") or "") or None
        if result.get("test_type") == "security":
            scan_id = payload.get("scan_id")
            return f"security_{scan_id}" if scan_id else None
        if result.get("test_type") == "performance":
            test_id = payload.get("test_id")
            return f"performance_{test_id}" if test_id else None
        return None

    def _collect_bug_summary(self, mission: Mission) -> List[Dict[str, Any]]:
        bug_items: List[Dict[str, Any]] = []
        for result in mission.test_results:
            status = str(result.get("status") or "")
            if self._is_result_success(status):
                continue
            test_type = str(result.get("test_type") or "")
            bug_items.append(
                {
                    "test_type": test_type,
                    "title": self._label_for_test_type(test_type),
                    "status": status or "unknown",
                    "summary": self._build_task_summary(
                        {
                            "test_type": test_type,
                            "target_url": mission.target_url,
                            "user_input": mission.user_input,
                        },
                        result,
                    ),
                    "execution_record_id": result.get("execution_record_id"),
                }
            )
        return bug_items[:8]

    def _persist_commander_summary_record(self, mission: Mission) -> None:
        try:
            from services.execution_center_service import get_execution_center_service

            bug_summary = self._collect_bug_summary(mission)
            summary = (mission.report or {}).get("summary", {}) if isinstance(mission.report, dict) else {}
            success = len(bug_summary) == 0 and mission.status not in {MissionStatus.FAILED, MissionStatus.CANCELLED}
            content = (
                f"总测试线 {summary.get('total_tests', len(mission.test_results))}，"
                f"通过 {summary.get('completed', 0)}，失败 {summary.get('failed', 0)}，"
                f"跳过 {summary.get('skipped', 0)}，成功率 {summary.get('success_rate', 0)}%"
            )
            logs: List[Dict[str, Any]] = [
                self._build_system_log(f"Commander 任务完成：{mission.user_input}"),
                self._build_assertion_log("军团任务总览", success, content),
            ]
            for bug in bug_summary:
                logs.append(self._build_assertion_log(str(bug.get("title") or "问题"), False, str(bug.get("summary") or "发现失败项")))
            for mission_log in mission.logs[-10:]:
                logs.append(
                    self._build_error_log(mission_log.message)
                    if mission_log.level == "error"
                    else self._build_observation_log(mission_log.message)
                )

            get_execution_center_service().upsert_run(
                task_id=mission.mission_id,
                requirement=f"军团任务 · {mission.user_input}",
                status="success" if success else "failed",
                target_url=mission.target_url or "",
                mode="commander",
                logs=logs,
                duration_ms=int(self._calc_duration(mission) * 1000),
                execution_group_id=mission.execution_group_id or mission.mission_id,
                session_id=f"commander_mission_{mission.mission_id}",
                group_title=self._build_group_title(mission.user_input, mission.target_url),
                record_kind="child",
            )
        except Exception as exc:
            logger.warning("[Commander] 持久化军团任务摘要失败: %s", exc)

    # ── 对外接口 ──────────────────────────────────────────────────────────

    async def run(
        self,
        user_input: str,
        target_url: str = "",
        parallel: bool = True,
        timeout_seconds: int = 900,
        mission_id: Optional[str] = None,
        mission_kind: str = "commander",
        task_kind: str = "general",
        source_context: Optional[Dict[str, Any]] = None,
        unified_task: bool = False,
    ) -> Dict[str, Any]:
        """
        一句话启动全面测试。

        Args:
            user_input: 用户的自然语言测试需求
            target_url: 目标 URL（可选）
            parallel: 是否并行执行多条测试线
            timeout_seconds: 全局超时（秒），默认 15 分钟

        Returns:
            任务结果 dict
        """
        mission = Mission(
            mission_id=mission_id or str(uuid.uuid4())[:8],
            mission_kind=mission_kind,
            task_kind=task_kind,
            unified_task=unified_task,
            user_input=user_input,
            target_url=target_url,
            source_context=dict(source_context or {}),
        )
        mission.execution_group_id = mission.mission_id
        self._missions[mission.mission_id] = mission
        mission.started_at = datetime.now().isoformat()
        self._sync_execution_group(mission, status=MissionStatus.PENDING.value)

        # 启动追踪
        from core.tracing import get_tracer
        tracer = get_tracer()
        mission.trace_id = tracer.start_trace()

        mission.log("🚀 Commander 任务启动", data={
            "user_input": user_input,
            "target_url": target_url,
        })

        try:
            await asyncio.wait_for(
                self._run_pipeline(mission, parallel),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            mission.status = MissionStatus.FAILED
            mission.completed_at = datetime.now().isoformat()
            mission.log(f"⏰ 任务超时 ({timeout_seconds}s)", level="error")
            logger.error(f"[Commander] Mission {mission.mission_id} timed out after {timeout_seconds}s")
        except asyncio.CancelledError:
            mission.status = MissionStatus.CANCELLED
            mission.completed_at = datetime.now().isoformat()
            mission.log("⚠️ 任务已取消", level="warn")
        except Exception as e:
            mission.status = MissionStatus.FAILED
            mission.completed_at = datetime.now().isoformat()
            mission.log(f"❌ 任务失败: {e}", level="error")
            logger.error(f"[Commander] Mission failed: {e}", exc_info=True)
        finally:
            self._sync_execution_group(mission)
            self._persist_commander_summary_record(mission)
            tracer.end_trace()
            self._save_missions()  # 持久化到磁盘

        return mission.to_dict()

    async def _run_pipeline(self, mission: "Mission", parallel: bool):
        """内部执行管道 — 被 run() 包在 wait_for 超时中"""
        # ① 解析需求
        mission.status = MissionStatus.PARSING
        self._sync_execution_group(mission)
        mission.log("📋 解析需求...")
        parsed = await self._parse_requirement(mission)
        mission.parsed_requirement = parsed

        # ② 选择策略
        mission.status = MissionStatus.PLANNING
        self._sync_execution_group(mission)
        mission.log("🧠 选择测试策略...")
        strategy = await self._select_strategy(mission)
        mission.strategy = strategy

        # ③ 构建测试任务
        mission.status = MissionStatus.DISPATCHING
        self._sync_execution_group(mission)
        mission.log("📦 构建测试任务...")
        tasks = self._decorate_tasks(mission, self._build_tasks(mission, strategy))
        mission.test_tasks = tasks
        mission.log(f"📊 共 {len(tasks)} 条测试线待执行", data={
            "test_types": [t.get("test_type") for t in tasks],
        })

        # ④ 分发执行
        mission.status = MissionStatus.EXECUTING
        self._sync_execution_group(mission)
        mission.log(f"⚡ {'并行' if parallel else '串行'}执行测试...")
        results = await self._execute_tasks(mission, tasks, parallel)
        mission.test_results = results

        # ⑤ 生成报告
        mission.status = MissionStatus.REPORTING
        self._sync_execution_group(mission)
        mission.log("📝 生成测试报告...")
        report = await self._generate_report(mission)
        mission.report = report

        # ⑥ 发送通知
        await self._notify(mission)

        # 完成
        mission.status = MissionStatus.COMPLETED
        mission.completed_at = datetime.now().isoformat()
        self._sync_execution_group(mission)
        mission.log("✅ Commander 任务完成", data={
            "duration_s": self._calc_duration(mission),
        })

    # ── 蜂群模式 ──────────────────────────────────────────────────────────

    async def run_swarm(
        self,
        user_input: str,
        target_url: str = "",
        diff_text: str = "",
        alert_data: Optional[Dict] = None,
        mode: Optional[str] = None,
        mission_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        蜂群模式：战略层分析 → 智能任务分解 → 并行执行。

        与 run() 的区别：
        - run()  用 RequirementParser + StrategySelector（战术层直达）
        - run_swarm() 先经过 TestArchitect（战略层 5 种发现模式）

        Args:
            user_input: 用户需求
            target_url: 目标 URL
            diff_text: Git diff（变更驱动模式）
            alert_data: 告警数据（故障驱动模式）
            mode: 强制指定发现模式（留空则自动推断）
        """
        mission = Mission(
            mission_id=mission_id or str(uuid.uuid4())[:8],
            user_input=user_input,
            target_url=target_url,
        )
        mission.execution_group_id = mission.mission_id
        self._missions[mission.mission_id] = mission
        mission.started_at = datetime.now().isoformat()
        self._sync_execution_group(mission, status=MissionStatus.PENDING.value)

        from core.tracing import get_tracer
        tracer = get_tracer()
        mission.trace_id = tracer.start_trace()

        mission.log("🐝 蜂群模式启动", data={
            "user_input": user_input,
            "target_url": target_url,
            "mode": mode or "auto",
        })

        try:
            # ① 战略层：TestArchitect 分析
            mission.status = MissionStatus.PARSING
            mission.log("🎯 TestArchitect 战略分析...")

            from agents.test_architect import get_test_architect
            architect = get_test_architect()
            plan = await architect.analyze(
                input_text=user_input,
                target_url=target_url,
                mode=mode,
                diff_text=diff_text,
                alert_data=alert_data,
            )

            mission.parsed_requirement = plan.to_dict()
            mission.log(
                f"📋 发现 {len(plan.test_needs)} 条测试需求 ({plan.discovery_mode.value} 模式)",
                data={"test_needs": [n.title for n in plan.test_needs]},
            )

            # ② 将 TestNeed 转为可执行任务
            mission.status = MissionStatus.DISPATCHING
            tasks = []
            for need in plan.test_needs:
                for test_type in (need.test_types or ["ui_e2e"]):
                    tasks.append({
                        "test_type": test_type,
                        "mission_id": mission.mission_id,
                        "user_input": need.description or need.title,
                        "target_url": need.target_url or target_url,
                        "timeout": 300,
                        "retry_count": 3,
                        "parsed_requirement": mission.parsed_requirement,
                        "source_need": need.title,
                        "priority": need.priority,
                    })

            mission.test_tasks = self._decorate_tasks(mission, tasks)
            mission.log(f"📦 共 {len(tasks)} 条测试线待执行")

            # ③ 并行执行（复用已有逻辑）
            mission.status = MissionStatus.EXECUTING
            mission.log("⚡ 蜂群并行执行...")
            results = await self._execute_tasks(mission, mission.test_tasks, parallel=True)
            mission.test_results = results

            # ④ 报告 + 通知（复用已有逻辑）
            mission.status = MissionStatus.REPORTING
            mission.log("📝 生成蜂群报告...")
            report = await self._generate_report(mission)
            mission.report = report
            await self._notify(mission)

            mission.status = MissionStatus.COMPLETED
            mission.completed_at = datetime.now().isoformat()
            mission.log("✅ 蜂群任务完成", data={
                "duration_s": self._calc_duration(mission),
                "discovery_mode": plan.discovery_mode.value,
            })

        except asyncio.CancelledError:
            mission.status = MissionStatus.CANCELLED
            mission.completed_at = datetime.now().isoformat()
            mission.log("⚠️ 蜂群任务已取消", level="warn")
        except Exception as e:
            mission.status = MissionStatus.FAILED
            mission.completed_at = datetime.now().isoformat()
            mission.log(f"❌ 蜂群任务失败: {e}", level="error")
            logger.error(f"[Commander] Swarm mission failed: {e}", exc_info=True)
        finally:
            self._sync_execution_group(mission)
            self._persist_commander_summary_record(mission)
            tracer.end_trace()
            self._save_missions()

        return mission.to_dict()

    def get_mission(self, mission_id: str) -> Optional[Dict]:
        """获取任务状态"""
        mission = self._missions.get(mission_id)
        return mission.to_dict() if mission else None

    def cancel_mission(self, mission_id: str) -> bool:
        """取消任务"""
        mission = self._missions.get(mission_id)
        if mission and mission.status in (
            MissionStatus.PENDING, MissionStatus.PARSING,
            MissionStatus.PLANNING, MissionStatus.DISPATCHING,
            MissionStatus.EXECUTING,
        ):
            mission.status = MissionStatus.CANCELLED
            mission.completed_at = datetime.now().isoformat()
            mission.log("⚠️ 任务被用户取消", level="warn")
            return True
        return False

    def list_missions(self, limit: int = 20) -> List[Dict]:
        """获取最近的任务列表"""
        missions = sorted(
            self._missions.values(),
            key=lambda m: m.created_at,
            reverse=True,
        )[:limit]
        return [m.to_dict() for m in missions]

    def get_mission_logs(self, mission_id: str, since_index: int = 0) -> List[Dict]:
        """获取任务日志（支持增量获取，用于 SSE）"""
        mission = self._missions.get(mission_id)
        if not mission:
            return []
        return [asdict(l) for l in mission.logs[since_index:]]

    # ── 内部流程 ──────────────────────────────────────────────────────────

    async def _parse_requirement(self, mission: Mission) -> Dict:
        """步骤①：调用已有的 RequirementParser"""
        from core.requirement_parser import get_requirement_parser
        from core.tracing import get_tracer
        import json

        parser = get_requirement_parser()

        with get_tracer().span("commander", "parse_requirement"):
            result = parser.parse_text(mission.user_input)

        parsed_str = parser.to_json(result)
        return json.loads(parsed_str) if isinstance(parsed_str, str) else parsed_str

    async def _select_strategy(self, mission: Mission) -> Dict:
        """步骤②：调用已有的 StrategySelector"""
        from core.strategy_selector import get_strategy_selector
        from core.tracing import get_tracer

        selector = get_strategy_selector()

        with get_tracer().span("commander", "select_strategy"):
            strategy = selector.select_strategy(
                requirement=mission.user_input,
                target_url=mission.target_url or None,
                context={"parsed": mission.parsed_requirement},
            )

        return {
            "test_types": [t.value for t in strategy.test_types],
            "priority": strategy.priority.value,
            "parallel": strategy.parallel,
            "timeout_seconds": strategy.timeout_seconds,
            "retry_count": strategy.retry_count,
            "ai_confidence": strategy.ai_confidence,
            "reasoning": strategy.reasoning,
            "recommended_agents": strategy.recommended_agents,
        }

    def _build_tasks(self, mission: Mission, strategy: Dict) -> List[Dict]:
        """步骤③：根据策略构建具体测试任务"""
        tasks = []
        for test_type in strategy.get("test_types", []):
            task = {
                "test_type": test_type,
                "mission_id": mission.mission_id,
                "user_input": mission.user_input,
                "target_url": mission.target_url,
                "timeout": strategy.get("timeout_seconds", 300),
                "retry_count": strategy.get("retry_count", 3),
                "parsed_requirement": mission.parsed_requirement,
            }
            tasks.append(task)
        return tasks

    async def _execute_tasks(
        self,
        mission: Mission,
        tasks: List[Dict],
        parallel: bool,
    ) -> List[Dict]:
        """步骤④：分发并执行测试任务"""
        results = []

        if parallel:
            coros = [self._execute_single_task(mission, task) for task in tasks]
            gathered = await asyncio.gather(*coros, return_exceptions=True)
            for i, res in enumerate(gathered):
                if isinstance(res, Exception):
                    results.append({
                        "test_type": tasks[i].get("test_type", ""),
                        "status": "error",
                        "error": str(res),
                    })
                else:
                    results.append(res)
        else:
            for task in tasks:
                try:
                    res = await self._execute_single_task(mission, task)
                    results.append(res)
                except Exception as e:
                    results.append({
                        "test_type": task.get("test_type", ""),
                        "status": "error",
                        "error": str(e),
                    })

        return results

    async def _execute_single_task(self, mission: Mission, task: Dict) -> Dict:
        """执行单条测试线"""
        test_type = task.get("test_type", "")
        method_name = _TEST_LINE_MAP.get(test_type)

        mission.log(f"🔄 执行测试线: {test_type}")

        from core.tracing import get_tracer

        with get_tracer().span("commander", f"execute_{test_type}"):
            if method_name and hasattr(self, method_name):
                method = getattr(self, method_name)
                result = await method(task)
            else:
                # 通用执行方式 — 通过 AgentBus 分发
                result = await self._run_via_agent_bus(task)

        record_id = self._infer_existing_execution_record_id(result)
        if not record_id:
            record_id = self._persist_missing_task_record(mission, task, result)
        if record_id:
            result["execution_record_id"] = record_id

        mission.log(f"✅ 测试线完成: {test_type}", data={
            "status": result.get("status", "unknown"),
            "execution_record_id": result.get("execution_record_id"),
        })
        self._sync_execution_group(mission)

        return result

    # ── 各测试线实现 ──────────────────────────────────────────────────────

    async def _run_ui_test(self, task: Dict) -> Dict:
        """UI E2E 测试线 — 启动 Orchestrator → 轮询等待完成 → 收集结果"""
        try:
            import uuid
            from agents.orchestrator import Orchestrator

            # 为 Commander 分配独立 session，避免干扰用户手动会话
            session_id = f"commander_{uuid.uuid4().hex[:8]}"
            orchestrator = Orchestrator(session_id=session_id)

            task_id = orchestrator.start_task(
                task_requirement=task.get("user_input", ""),
                target_url=task.get("target_url", ""),
                mode="smart",
                browser_mode="chromium",
                execution_group_id=task.get("execution_group_id", ""),
            )

            if task_id == "Busy":
                return {"test_type": "ui_e2e", "status": "skipped", "error": "Orchestrator busy"}

            # 轮询等待完成（最长 timeout 秒）
            timeout = task.get("timeout", 300)
            start_time = time.time()
            while orchestrator.is_running:
                if time.time() - start_time > timeout:
                    orchestrator.stop_task()
                    return {"test_type": "ui_e2e", "status": "timeout", "error": f"UI test timed out after {timeout}s"}
                await asyncio.sleep(2)

            # 收集结果
            logs = orchestrator.session.get_logs()
            error_count = sum(1 for l in logs if l.get("type") == "error")
            step_count = sum(1 for l in logs if l.get("type") in ("step", "action", "plan"))
            duration_s = round(time.time() - start_time, 1)

            status = "completed" if error_count == 0 else "error"

            return {
                "test_type": "ui_e2e",
                "status": status,
                "result": {
                    "task_id": task_id,
                    "session_id": session_id,
                    "total_steps": step_count,
                    "error_count": error_count,
                    "log_count": len(logs),
                    "duration_s": duration_s,
                    "errors": [
                        l.get("content", "") for l in logs
                        if l.get("type") == "error"
                    ][:5],  # 最多 5 条错误
                },
            }
        except Exception as e:
            return {
                "test_type": "ui_e2e",
                "status": "error",
                "error": str(e),
            }

    async def _run_api_test(self, task: Dict) -> Dict:
        """API 测试线 — 调用现有 APIAgent.execute_test()"""
        try:
            from agents.api_agent import APIAgent

            agent = APIAgent()
            result = agent.execute_test(
                test_scenario=task.get("user_input", ""),
                swagger_url=task.get("target_url") if task.get("target_url", "").endswith(("/swagger", "/openapi.json")) else None,
            )
            return {
                "test_type": task.get("test_type", "api_rest"),
                "status": result.get("status", "completed") if isinstance(result, dict) else "completed",
                "result": result if isinstance(result, dict) else {"raw": str(result)},
            }
        except Exception as e:
            return {
                "test_type": task.get("test_type", "api_rest"),
                "status": "error",
                "error": str(e),
            }

    async def _run_security_test(self, task: Dict) -> Dict:
        """安全测试线 — 调用现有 SecurityScanner.scan()"""
        try:
            from services.security_scanner import SecurityScanner, ScanConfig, ScanType

            scanner = SecurityScanner()
            config = ScanConfig(
                target_url=task.get("target_url", ""),
                scan_type=ScanType.QUICK,
                session_id=task.get("mission_session_id", "default_session"),
                execution_group_id=task.get("execution_group_id"),
                group_title=task.get("group_title"),
            )
            result = await scanner.scan(config)
            alerts = result.alerts or []
            success = result.status.value == "completed" and not alerts and not result.errors
            return {
                "test_type": "security",
                "status": "completed" if success else "error",
                "result": asdict(result) if hasattr(result, '__dataclass_fields__') else (result if isinstance(result, dict) else {"raw": str(result)}),
            }
        except Exception as e:
            return {
                "test_type": "security",
                "status": "error",
                "error": str(e),
            }

    async def _run_performance_test(self, task: Dict) -> Dict:
        """性能测试线 — 调用现有 PerformanceRunner.run_test()"""
        try:
            from services.performance_runner import PerformanceRunner, LoadTestConfig

            runner = PerformanceRunner()
            config = LoadTestConfig(
                target_url=task.get("target_url", ""),
                users=5,
                spawn_rate=1,
                duration=10,
                session_id=task.get("mission_session_id", "default_session"),
                execution_group_id=task.get("execution_group_id"),
                group_title=task.get("group_title"),
            )
            result = await runner.run_test(config)
            stats = result.stats or {}
            failures = int(stats.get("failures", 0) or 0)
            http_5xx = int(stats.get("http_5xx", 0) or 0)
            success = result.status.value == "completed" and failures == 0 and http_5xx == 0 and not result.errors
            return {
                "test_type": "performance",
                "status": "completed" if success else "error",
                "result": asdict(result) if hasattr(result, '__dataclass_fields__') else (result if isinstance(result, dict) else {"raw": str(result)}),
            }
        except Exception as e:
            return {
                "test_type": "performance",
                "status": "error",
                "error": str(e),
            }

    async def _run_database_test(self, task: Dict) -> Dict:
        """数据库测试线 — 调用 DataAgent.execute_test()"""
        try:
            from agents.data_agent import DataAgent

            agent = DataAgent()
            result = agent.execute_test(task.get("user_input", ""))
            return {
                "test_type": "database",
                "status": result.get("status", "completed") if isinstance(result, dict) else "completed",
                "result": result if isinstance(result, dict) else {"raw": str(result)},
            }
        except Exception as e:
            return {
                "test_type": "database",
                "status": "error",
                "error": str(e),
            }

    async def _run_accessibility_test(self, task: Dict) -> Dict:
        """无障碍测试线 — 调用 AccessibilityTestService.audit()"""
        try:
            from services.accessibility_testing import AccessibilityTestService

            service = AccessibilityTestService()
            result = await service.audit(task.get("target_url", ""))
            payload = result.to_dict() if hasattr(result, 'to_dict') else (result if isinstance(result, dict) else {"raw": str(result)})
            issues = payload.get("issues", []) or []
            success = payload.get("status", "success") != "error" and len(issues) == 0
            return {
                "test_type": "accessibility",
                "status": "completed" if success else "error",
                "result": payload,
            }
        except Exception as e:
            return {
                "test_type": "accessibility",
                "status": "error",
                "error": str(e),
            }

    async def _run_visual_test(self, task: Dict) -> Dict:
        """视觉回归测试线 — 调用 VisualRegressionTester.list_baselines()"""
        try:
            from services.visual_regression import get_visual_tester

            tester = get_visual_tester()
            baselines = tester.list_baselines()
            return {
                "test_type": "visual_regression",
                "status": "completed",
                "result": {
                    "baselines_count": len(baselines),
                    "baselines": baselines[:10],
                    "note": "视觉回归需要先建立基线截图才能对比",
                },
            }
        except Exception as e:
            return {
                "test_type": "visual_regression",
                "status": "error",
                "error": str(e),
            }

    async def _run_via_agent_bus(self, task: Dict) -> Dict:
        """通过 AgentBus 分发到注册的 Agent"""
        from core.agent_bus import get_agent_bus

        bus = get_agent_bus()
        test_type = task.get("test_type", "")

        result = await bus.request(
            receiver=test_type,
            payload=task,
            sender="commander",
            timeout=task.get("timeout", 300),
        )

        return result or {
            "test_type": test_type,
            "status": "timeout",
            "error": "AgentBus request timed out",
        }

    # ── 报告与通知 ────────────────────────────────────────────────────────

    async def _generate_report(self, mission: Mission) -> Dict:
        """步骤⑤：生成汇总报告"""
        total = len(mission.test_results)
        completed = sum(1 for r in mission.test_results if self._is_result_success(r.get("status", "")))
        failed = sum(1 for r in mission.test_results if self._is_result_failure(r.get("status", "")))
        skipped = sum(1 for r in mission.test_results if str(r.get("status") or "").lower() == "skipped")
        bug_summary = self._collect_bug_summary(mission)

        # 获取追踪成本摘要
        from core.tracing import get_tracer
        cost_summary = get_tracer().get_trace_summary(mission.trace_id)

        report = {
            "mission_id": mission.mission_id,
            "user_input": mission.user_input,
            "target_url": mission.target_url,
            "summary": {
                "total_tests": total,
                "completed": completed,
                "failed": failed,
                "skipped": skipped,
                "success_rate": round(completed / total * 100, 1) if total > 0 else 0,
            },
            "strategy": mission.strategy,
            "results": mission.test_results,
            "bug_summary": bug_summary,
            "cost": cost_summary,
            "duration_s": self._calc_duration(mission),
            "generated_at": datetime.now().isoformat(),
        }

        return report

    async def _notify(self, mission: Mission) -> None:
        """步骤⑥：发送通知"""
        try:
            from core.notify_gateway import get_notify_gateway

            gateway = get_notify_gateway()
            report = mission.report or {}
            summary = report.get("summary", {})

            await gateway.send(
                level="info",
                title=f"🧪 测试完成: {mission.user_input[:50]}",
                body=(
                    f"任务 {mission.mission_id} 已完成\n"
                    f"成功率: {summary.get('success_rate', 0)}%\n"
                    f"通过 {summary.get('completed', 0)}/{summary.get('total_tests', 0)}"
                ),
                data={"mission_id": mission.mission_id},
            )
        except ImportError:
            mission.log("⚠️ NotifyGateway 未就绪，跳过通知", level="warn")
        except Exception as e:
            mission.log(f"⚠️ 通知发送失败: {e}", level="warn")

    # ── 工具方法 ──────────────────────────────────────────────────────────

    @staticmethod
    def _calc_duration(mission: Mission) -> float:
        """计算任务耗时（秒）"""
        if mission.started_at and mission.completed_at:
            start = datetime.fromisoformat(mission.started_at)
            end = datetime.fromisoformat(mission.completed_at)
            return round((end - start).total_seconds(), 2)
        return 0.0

    # ── 查询/管理方法 ──────────────────────────────────────────────────────

    def get_mission(self, mission_id: str) -> Optional[Dict]:
        """获取任务详情"""
        mission = self._missions.get(mission_id)
        if mission is None:
            return None
        if isinstance(mission, dict):
            return mission
        return mission.to_dict()

    def list_missions(self, limit: int = 20) -> List[Dict]:
        """列出最近的任务（按创建时间倒序）"""
        missions = []
        for m in self._missions.values():
            if isinstance(m, dict):
                missions.append(m)
            else:
                missions.append(m.to_dict())
        missions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return missions[:limit]

    def cancel_mission(self, mission_id: str) -> bool:
        """取消任务"""
        mission = self._missions.get(mission_id)
        if mission is None:
            return False
        if isinstance(mission, dict):
            mission["status"] = "cancelled"
        else:
            mission.status = MissionStatus.CANCELLED
            mission.completed_at = datetime.now().isoformat()
            mission.log("⚠️ 任务已取消", level="warn")
        return True

    def get_mission_logs(self, mission_id: str, since_index: int = 0) -> List[Dict]:
        """获取任务日志（支持增量查询）"""
        mission = self._missions.get(mission_id)
        if mission is None:
            return []
        if isinstance(mission, dict):
            logs = mission.get("logs", [])
        else:
            logs = [asdict(l) for l in mission.logs]
        return logs[since_index:]


# ── 单例 ─────────────────────────────────────────────────────────────────────

_commander: Optional[Commander] = None


def get_commander() -> Commander:
    """获取 Commander 单例"""
    global _commander
    if _commander is None:
        _commander = Commander()
    return _commander
