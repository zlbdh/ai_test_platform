# -*- coding: utf-8 -*-
"""
Commander 命令网关服务

为 Web / ChatOps / 通知平台提供统一命令注册、权限判定、审批与受控执行入口。
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from typing import Any, Awaitable, Callable, Dict, List, Optional
import uuid

from core.db_helper import get_connection
from services.auth_service import Permission, User, get_auth_service
from services.deploy_service import get_deploy_service


Handler = Callable[["CommandExecutionContext"], Awaitable[Dict[str, Any]]]


class CommandGatewayError(Exception):
    """命令网关基类异常。"""


class CommandNotFoundError(CommandGatewayError):
    """未找到命令。"""


class CommandPermissionError(CommandGatewayError):
    """无权限执行命令。"""


class CommandValidationError(CommandGatewayError):
    """命令参数不合法。"""


class CommandConfirmationRequiredError(CommandGatewayError):
    """命令需要显式确认。"""


class CommandRunNotFoundError(CommandGatewayError):
    """未找到命令运行记录。"""


class CommandApprovalError(CommandGatewayError):
    """命令审批状态异常。"""


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _json_dump(payload: Any) -> str:
    return json.dumps(payload if payload is not None else {}, ensure_ascii=False, default=str)


def _json_load(payload: Optional[str], default: Any) -> Any:
    raw = str(payload or "").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


@dataclass(frozen=True)
class CommandArgumentSpec:
    name: str
    type: str
    required: bool = False
    description: str = ""
    default: Any = None


@dataclass(frozen=True)
class CommandDefinition:
    command_id: str
    summary: str
    description: str
    permission: Optional[Permission]
    risk_level: str
    read_only: bool
    requires_confirmation: bool = False
    approval_required: bool = False
    sandbox_required: bool = False
    approval_permission: Optional[Permission] = None
    project_scope: str = "user"
    env_scope: str = "default"
    approval_policy: str = "none"
    sandbox_profile: str = "none"
    timeout_s: int = 60
    aliases: List[str] = field(default_factory=list)
    arguments: List[CommandArgumentSpec] = field(default_factory=list)
    handler: Optional[Handler] = None


@dataclass
class CommandExecutionContext:
    command: CommandDefinition
    arguments: Dict[str, Any]
    user: Optional[User]
    confirm: bool = False
    source: str = "api"
    run_id: str = ""
    approval_id: str = ""
    project_key: str = ""
    source_context: Dict[str, Any] = field(default_factory=dict)


class CommanderCommandGatewayService:
    """统一命令注册表、审批队列与受控执行入口。"""

    def __init__(self):
        self._commands: Dict[str, CommandDefinition] = {}
        self._ensure_schema()
        self._register_defaults()

    def _ensure_schema(self):
        with get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS command_runs (
                    run_id TEXT PRIMARY KEY,
                    command_id TEXT NOT NULL,
                    requester_id TEXT DEFAULT '',
                    source TEXT DEFAULT 'api',
                    project_key TEXT DEFAULT '',
                    args_json TEXT DEFAULT '{}',
                    source_context_json TEXT DEFAULT '{}',
                    status TEXT DEFAULT 'created',
                    risk_level TEXT DEFAULT 'low',
                    approval_status TEXT DEFAULT 'not_required',
                    approval_id TEXT DEFAULT '',
                    sandbox_profile TEXT DEFAULT 'none',
                    result_json TEXT DEFAULT '',
                    error_json TEXT DEFAULT '',
                    command_summary TEXT DEFAULT '',
                    read_only INTEGER DEFAULT 1,
                    env_scope TEXT DEFAULT '',
                    project_scope TEXT DEFAULT '',
                    requires_confirmation INTEGER DEFAULT 0,
                    approval_policy TEXT DEFAULT 'none',
                    timeout_s INTEGER DEFAULT 60,
                    created_at TEXT DEFAULT '',
                    started_at TEXT DEFAULT '',
                    finished_at TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS command_approvals (
                    approval_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    command_id TEXT NOT NULL,
                    requester_id TEXT DEFAULT '',
                    approver_id TEXT DEFAULT '',
                    project_key TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    reason TEXT DEFAULT '',
                    comment TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    decided_at TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_command_runs_created ON command_runs(created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_command_runs_command ON command_runs(command_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_command_runs_source ON command_runs(source, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_command_approvals_run ON command_approvals(run_id)"
            )
            existing_columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(command_runs)").fetchall()
            }
            if "source_context_json" not in existing_columns:
                conn.execute(
                    "ALTER TABLE command_runs ADD COLUMN source_context_json TEXT DEFAULT '{}'"
                )

    def _register(self, definition: CommandDefinition):
        self._commands[definition.command_id] = definition

    def _register_defaults(self):
        self._register(
            CommandDefinition(
                command_id="platform.status",
                summary="查询平台状态",
                description="返回 Agent 军团、ChatOps 双向链路与平台摘要状态。",
                permission=Permission.VIEW_RESULTS,
                risk_level="low",
                read_only=True,
                project_scope="platform",
                env_scope="all",
                sandbox_profile="read_only",
                aliases=["状态", "status", "health"],
                handler=self._handle_platform_status,
            )
        )
        self._register(
            CommandDefinition(
                command_id="commander.mission.start",
                summary="启动蜂群测试任务",
                description="创建一个 Commander 蜂群测试任务，并在后台执行。",
                permission=Permission.RUN_TEST,
                risk_level="medium",
                read_only=False,
                project_scope="project",
                env_scope="testing",
                sandbox_profile="mission_control",
                timeout_s=30,
                aliases=["测试", "test"],
                arguments=[
                    CommandArgumentSpec("project_key", "string", description="项目标识", default=""),
                    CommandArgumentSpec("user_input", "string", required=True, description="自然语言测试需求"),
                    CommandArgumentSpec("target_url", "string", description="目标 URL", default=""),
                    CommandArgumentSpec("diff_text", "string", description="变更 diff", default=""),
                    CommandArgumentSpec("mode", "string", description="发现模式", default=""),
                    CommandArgumentSpec("parallel", "boolean", description="是否并行执行", default=True),
                ],
                handler=self._handle_commander_mission_start,
            )
        )
        self._register(
            CommandDefinition(
                command_id="commander.mission.cancel",
                summary="停止测试任务",
                description="取消一个仍在执行中的 Commander 任务。",
                permission=Permission.RUN_TEST,
                risk_level="medium",
                read_only=False,
                project_scope="mission",
                env_scope="testing",
                sandbox_profile="mission_control",
                timeout_s=30,
                aliases=["停止", "cancel"],
                arguments=[
                    CommandArgumentSpec("mission_id", "string", required=True, description="任务 ID"),
                ],
                handler=self._handle_commander_mission_cancel,
            )
        )
        self._register(
            CommandDefinition(
                command_id="commander.mission.report",
                summary="查询任务报告",
                description="按 mission_id 返回 Commander 任务摘要。",
                permission=Permission.VIEW_RESULTS,
                risk_level="low",
                read_only=True,
                project_scope="mission",
                env_scope="all",
                sandbox_profile="read_only",
                aliases=["报告", "report"],
                arguments=[
                    CommandArgumentSpec("mission_id", "string", required=True, description="任务 ID"),
                ],
                handler=self._handle_mission_report,
            )
        )
        self._register(
            CommandDefinition(
                command_id="exploration.session.create",
                summary="启动探索性测试会话",
                description="按测试章程生成探索性测试会话与结构化发现。",
                permission=Permission.RUN_TEST,
                risk_level="medium",
                read_only=False,
                project_scope="project",
                env_scope="testing",
                sandbox_profile="exploration",
                timeout_s=120,
                arguments=[
                    CommandArgumentSpec("project_key", "string", description="项目标识", default=""),
                    CommandArgumentSpec("group_id", "string", description="执行分组", default=""),
                    CommandArgumentSpec("target_url", "string", required=True, description="目标 URL"),
                    CommandArgumentSpec("charter", "string", required=True, description="探索性测试章程"),
                ],
                handler=self._handle_exploration_session_create,
            )
        )
        self._register(
            CommandDefinition(
                command_id="exploration.findings.list",
                summary="查询探索性测试发现",
                description="按会话查询探索性测试的结构化发现列表。",
                permission=Permission.VIEW_RESULTS,
                risk_level="low",
                read_only=True,
                project_scope="project",
                env_scope="testing",
                sandbox_profile="read_only",
                arguments=[
                    CommandArgumentSpec("session_id", "string", required=True, description="探索会话 ID"),
                    CommandArgumentSpec("severity", "string", description="严重级别筛选", default=""),
                    CommandArgumentSpec("review_only", "boolean", description="仅看待人工复核", default=False),
                    CommandArgumentSpec("review_status", "string", description="复核状态筛选", default=""),
                ],
                handler=self._handle_exploration_findings_list,
            )
        )
        self._register(
            CommandDefinition(
                command_id="exploration.review.queue.list",
                summary="查询人工复核队列",
                description="返回探索发现里的人工复核队列，用于 Legion 统一处理证据。",
                permission=Permission.VIEW_RESULTS,
                risk_level="low",
                read_only=True,
                project_scope="project",
                env_scope="testing",
                sandbox_profile="read_only",
                arguments=[
                    CommandArgumentSpec("project_key", "string", description="项目筛选", default=""),
                    CommandArgumentSpec("severity", "string", description="严重级别筛选", default=""),
                    CommandArgumentSpec("review_status", "string", description="复核状态筛选", default="pending"),
                    CommandArgumentSpec("limit", "integer", description="返回条数", default=20),
                ],
                handler=self._handle_exploration_review_queue_list,
            )
        )
        self._register(
            CommandDefinition(
                command_id="exploration.finding.review",
                summary="处理探索发现复核",
                description="对一条探索发现给出 confirmed 或 dismissed 复核结论。",
                permission=Permission.RUN_TEST,
                risk_level="medium",
                read_only=False,
                project_scope="project",
                env_scope="testing",
                sandbox_profile="review_control",
                timeout_s=30,
                arguments=[
                    CommandArgumentSpec("finding_id", "string", required=True, description="探索发现 ID"),
                    CommandArgumentSpec("decision", "string", required=True, description="复核结论"),
                    CommandArgumentSpec("comment", "string", description="复核备注", default=""),
                ],
                handler=self._handle_exploration_finding_review,
            )
        )
        self._register(
            CommandDefinition(
                command_id="release.risk.assess",
                summary="生成发布风险评估",
                description="聚合探索性发现和测试信号，生成发布风险结论。",
                permission=Permission.DEPLOY_VIEW,
                risk_level="medium",
                read_only=False,
                project_scope="project",
                env_scope="release",
                sandbox_profile="risk_assessment",
                timeout_s=60,
                arguments=[
                    CommandArgumentSpec("project_key", "string", description="项目标识", default=""),
                    CommandArgumentSpec("environment", "string", description="环境标识", default="test"),
                    CommandArgumentSpec("exploration_session_ids", "csv", description="探索会话 ID 列表", default=[]),
                    CommandArgumentSpec("required_tests_passed", "boolean", description="所需测试是否通过", default=True),
                    CommandArgumentSpec("change_summary", "string", description="变更摘要", default=""),
                ],
                handler=self._handle_release_risk_assess,
            )
        )
        self._register(
            CommandDefinition(
                command_id="release.risk.get",
                summary="查询发布风险评估",
                description="按 assessment_id 查询发布风险评估详情。",
                permission=Permission.DEPLOY_VIEW,
                risk_level="low",
                read_only=True,
                project_scope="project",
                env_scope="release",
                sandbox_profile="read_only",
                arguments=[
                    CommandArgumentSpec("assessment_id", "string", required=True, description="评估 ID"),
                ],
                handler=self._handle_release_risk_get,
            )
        )
        self._register(
            CommandDefinition(
                command_id="release.deploy.request",
                summary="按发布评估发起受控发布",
                description="复用 Deploy 审批与作业链路，按当前 assessment 创建受控发布动作。",
                permission=Permission.DEPLOY_REQUEST,
                risk_level="high",
                read_only=False,
                requires_confirmation=True,
                approval_required=False,
                project_scope="project",
                env_scope="deploy",
                approval_policy="deploy_approval_chain",
                sandbox_profile="release_deploy",
                timeout_s=60,
                arguments=[
                    CommandArgumentSpec("assessment_id", "string", required=True, description="发布风险评估 ID"),
                    CommandArgumentSpec("target_type", "string", required=True, description="发布目标类型 repo 或 project"),
                    CommandArgumentSpec("repo_id", "string", description="仓库发布时的 repo_id", default=""),
                    CommandArgumentSpec("branch", "string", description="仓库发布分支", default=""),
                    CommandArgumentSpec("comment", "string", description="发布申请备注", default=""),
                ],
                handler=self._handle_release_deploy_request,
            )
        )
        self._register(
            CommandDefinition(
                command_id="deploy.approvals.list",
                summary="查询部署审批",
                description="按状态筛选部署审批单列表。",
                permission=Permission.DEPLOY_VIEW,
                risk_level="low",
                read_only=True,
                project_scope="project",
                env_scope="deploy",
                sandbox_profile="read_only",
                arguments=[
                    CommandArgumentSpec("status", "string", description="审批状态筛选", default=""),
                    CommandArgumentSpec("limit", "integer", description="返回条数", default=10),
                ],
                handler=self._handle_deploy_approvals_list,
            )
        )
        self._register(
            CommandDefinition(
                command_id="deploy.jobs.list",
                summary="查询部署作业",
                description="按状态筛选后台部署作业列表。",
                permission=Permission.DEPLOY_VIEW,
                risk_level="low",
                read_only=True,
                project_scope="project",
                env_scope="deploy",
                sandbox_profile="read_only",
                arguments=[
                    CommandArgumentSpec("status", "string", description="作业状态筛选", default=""),
                    CommandArgumentSpec("limit", "integer", description="返回条数", default=10),
                ],
                handler=self._handle_deploy_jobs_list,
            )
        )
        self._register(
            CommandDefinition(
                command_id="deploy.history.list",
                summary="查询部署历史",
                description="返回最近部署历史记录。",
                permission=Permission.DEPLOY_VIEW,
                risk_level="low",
                read_only=True,
                project_scope="project",
                env_scope="deploy",
                sandbox_profile="read_only",
                arguments=[
                    CommandArgumentSpec("limit", "integer", description="返回条数", default=10),
                    CommandArgumentSpec("status", "string", description="记录状态筛选", default=""),
                ],
                handler=self._handle_deploy_history_list,
            )
        )
        self._register(
            CommandDefinition(
                command_id="deploy.audit.list",
                summary="查询部署审计",
                description="返回最近部署审计日志。",
                permission=Permission.DEPLOY_VIEW,
                risk_level="low",
                read_only=True,
                project_scope="project",
                env_scope="deploy",
                sandbox_profile="read_only",
                arguments=[
                    CommandArgumentSpec("limit", "integer", description="返回条数", default=10),
                    CommandArgumentSpec("action", "string", description="审计动作筛选", default=""),
                    CommandArgumentSpec("project_key", "string", description="项目筛选", default=""),
                    CommandArgumentSpec("user_id", "string", description="操作人筛选", default=""),
                ],
                handler=self._handle_deploy_audit_list,
            )
        )
        self._register(
            CommandDefinition(
                command_id="deploy.job.cancel",
                summary="取消部署作业",
                description="取消一个仍在运行或排队中的部署作业。",
                permission=Permission.ADMIN,
                risk_level="high",
                read_only=False,
                requires_confirmation=True,
                approval_required=True,
                approval_permission=Permission.DEPLOY_APPROVE,
                project_scope="project",
                env_scope="nonprod",
                approval_policy="required",
                sandbox_profile="deploy_control",
                timeout_s=30,
                arguments=[
                    CommandArgumentSpec("job_id", "string", required=True, description="部署作业 ID"),
                ],
                handler=self._handle_deploy_job_cancel,
            )
        )

    def list_commands(self, user: Optional[User] = None) -> List[Dict[str, Any]]:
        auth = get_auth_service()
        commands: List[Dict[str, Any]] = []
        for definition in sorted(self._commands.values(), key=lambda item: item.command_id):
            allowed = bool(user)
            denial_reason = ""
            if definition.permission and user:
                allowed = auth.check_permission(user, definition.permission)
                if not allowed:
                    denial_reason = f"缺少权限 {definition.permission.value}"
            elif not user:
                allowed = False
                denial_reason = "需要登录态"

            commands.append(
                {
                    "command_id": definition.command_id,
                    "summary": definition.summary,
                    "description": definition.description,
                    "permission": definition.permission.value if definition.permission else "",
                    "risk_level": definition.risk_level,
                    "read_only": definition.read_only,
                    "requires_confirmation": definition.requires_confirmation,
                    "approval_required": definition.approval_required,
                    "approval_permission": (
                        definition.approval_permission.value if definition.approval_permission else ""
                    ),
                    "approval_policy": definition.approval_policy,
                    "sandbox_required": definition.sandbox_required,
                    "sandbox_profile": definition.sandbox_profile,
                    "project_scope": definition.project_scope,
                    "env_scope": definition.env_scope,
                    "timeout_s": definition.timeout_s,
                    "aliases": list(definition.aliases),
                    "arguments": [asdict(spec) for spec in definition.arguments],
                    "allowed": allowed,
                    "denial_reason": denial_reason,
                }
            )
        return commands

    async def execute_command(
        self,
        command_id: str,
        arguments: Optional[Dict[str, Any]],
        *,
        user: Optional[User],
        confirm: bool = False,
        source: str = "api",
        source_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        definition = self._get_command_definition(command_id)
        if not user:
            raise CommandPermissionError("需要登录态")

        auth = get_auth_service()
        if definition.permission and not auth.check_permission(user, definition.permission):
            raise CommandPermissionError(
                f"执行命令 {definition.command_id} 需要权限 {definition.permission.value}"
            )

        if definition.requires_confirmation and not confirm:
            raise CommandConfirmationRequiredError(
                f"命令 {definition.command_id} 为高风险动作，需显式确认 confirm=true"
            )

        normalized_arguments = self._normalize_arguments(definition, arguments or {})
        project_key = self._resolve_project_key(definition, normalized_arguments, user=user)
        if project_key and not self._is_scope_allowed(user, project_key):
            raise CommandPermissionError(f"当前账号无权操作项目 {project_key}")

        run_id = self._create_command_run(
            definition=definition,
            arguments=normalized_arguments,
            user=user,
            source=source,
            project_key=project_key,
            source_context=source_context or {},
        )

        if definition.approval_required:
            approval_id = self._create_command_approval(
                run_id=run_id,
                definition=definition,
                user=user,
                project_key=project_key,
            )
            self._update_run_approval(run_id, approval_id, "pending")
            self._record_command_requested_audit(
                definition=definition,
                run_id=run_id,
                user=user,
                source=source,
                project_key=project_key,
                approval_id=approval_id,
            )
            self._record_command_approval_requested_audit(
                definition=definition,
                run_id=run_id,
                approval_id=approval_id,
                user=user,
                source=source,
                project_key=project_key,
            )
            return {
                "command_id": definition.command_id,
                "risk_level": definition.risk_level,
                "read_only": definition.read_only,
                "run": self.get_command_run(run_id, user=user),
                "approval": self._get_command_approval(approval_id),
                "result": None,
            }

        result = await self._execute_existing_run(
            run_id=run_id,
            definition=definition,
            arguments=normalized_arguments,
            user=user,
            confirm=confirm,
            source=source,
            approval_id="",
            project_key=project_key,
        )
        return {
            "command_id": definition.command_id,
            "risk_level": definition.risk_level,
            "read_only": definition.read_only,
            "run": self.get_command_run(run_id, user=user),
            "approval": None,
            "result": result,
        }

    def list_command_runs(
        self,
        *,
        user: Optional[User],
        status: str = "",
        approval_status: str = "",
        command_id: str = "",
        project_key: str = "",
        source: str = "",
        limit: int = 20,
    ) -> Dict[str, Any]:
        if not user:
            raise CommandPermissionError("需要登录态")
        if project_key and not self._is_scope_allowed(user, project_key):
            raise CommandPermissionError(f"当前账号无权查看项目 {project_key}")

        sql = [
            "SELECT * FROM command_runs",
            "WHERE 1=1",
        ]
        params: List[Any] = []
        if status:
            sql.append("AND status = ?")
            params.append(status)
        if approval_status:
            sql.append("AND approval_status = ?")
            params.append(approval_status)
        if command_id:
            sql.append("AND command_id = ?")
            params.append(command_id)
        if project_key:
            sql.append("AND project_key = ?")
            params.append(project_key)
        if source:
            sql.append("AND source = ?")
            params.append(source)
        sql.append("ORDER BY created_at DESC")
        sql.append("LIMIT ?")
        params.append(max(1, min(int(limit), 200)))

        with get_connection() as conn:
            rows = conn.execute(" ".join(sql), tuple(params)).fetchall()

        runs = []
        for row in rows:
            payload = self._serialize_run_row(dict(row))
            if self._can_access_run(user, payload):
                runs.append(payload)
        return {"runs": runs, "count": len(runs)}

    def get_command_run(self, run_id: str, *, user: Optional[User]) -> Dict[str, Any]:
        payload = self._get_command_run_payload(run_id)
        if not user:
            raise CommandPermissionError("需要登录态")
        if not self._can_access_run(user, payload):
            raise CommandPermissionError(f"当前账号无权查看命令运行 {run_id}")
        return payload

    async def approve_command_run(
        self,
        run_id: str,
        *,
        user: Optional[User],
        comment: str = "",
        confirm: bool = True,
        source: str = "api",
    ) -> Dict[str, Any]:
        if not user:
            raise CommandPermissionError("需要登录态")

        run = self._get_command_run_payload(run_id)
        definition = self._get_command_definition(run["command_id"])
        approval = self._require_pending_approval(run)
        self._ensure_approval_permission(user, definition)
        project_key = str(run.get("project_key") or "")
        if project_key and not self._is_scope_allowed(user, project_key):
            raise CommandPermissionError(f"当前账号无权审批项目 {project_key}")

        self._mark_approval_decision(
            approval_id=approval["approval_id"],
            status="approved",
            approver_id=getattr(user, "user_id", ""),
            comment=comment,
        )
        self._update_run_status(
            run_id,
            status="approved_pending_execution",
            approval_status="approved",
        )
        self._record_command_approval_decision_audit(
            definition=definition,
            run_id=run_id,
            approval_id=approval["approval_id"],
            user=user,
            source=source,
            project_key=project_key,
            decision="approved",
            comment=comment,
        )

        result = await self._execute_existing_run(
            run_id=run_id,
            definition=definition,
            arguments=dict(run.get("arguments") or {}),
            user=user,
            confirm=confirm,
            source=source,
            approval_id=approval["approval_id"],
            project_key=project_key,
        )
        return {
            "run": self.get_command_run(run_id, user=user),
            "approval": self._get_command_approval(approval["approval_id"]),
            "result": result,
        }

    def reject_command_run(
        self,
        run_id: str,
        *,
        user: Optional[User],
        reason: str = "",
        source: str = "api",
    ) -> Dict[str, Any]:
        if not user:
            raise CommandPermissionError("需要登录态")

        run = self._get_command_run_payload(run_id)
        definition = self._get_command_definition(run["command_id"])
        approval = self._require_pending_approval(run)
        self._ensure_approval_permission(user, definition)
        project_key = str(run.get("project_key") or "")
        if project_key and not self._is_scope_allowed(user, project_key):
            raise CommandPermissionError(f"当前账号无权审批项目 {project_key}")

        self._mark_approval_decision(
            approval_id=approval["approval_id"],
            status="rejected",
            approver_id=getattr(user, "user_id", ""),
            comment=reason,
        )
        self._update_run_status(
            run_id,
            status="rejected",
            approval_status="rejected",
            finished_at=_now_iso(),
            error_json={"reason": reason or "审批已拒绝"},
        )
        self._record_command_approval_decision_audit(
            definition=definition,
            run_id=run_id,
            approval_id=approval["approval_id"],
            user=user,
            source=source,
            project_key=project_key,
            decision="rejected",
            comment=reason,
        )
        return {
            "run": self.get_command_run(run_id, user=user),
            "approval": self._get_command_approval(approval["approval_id"]),
        }

    def _get_command_definition(self, command_id: str) -> CommandDefinition:
        definition = self._commands.get(str(command_id or "").strip())
        if not definition or not definition.handler:
            raise CommandNotFoundError(f"未找到命令 {command_id}")
        return definition

    async def _execute_existing_run(
        self,
        *,
        run_id: str,
        definition: CommandDefinition,
        arguments: Dict[str, Any],
        user: Optional[User],
        confirm: bool,
        source: str,
        approval_id: str,
        project_key: str,
    ) -> Dict[str, Any]:
        context = CommandExecutionContext(
            command=definition,
            arguments=arguments,
            user=user,
            confirm=confirm,
            source=source,
            run_id=run_id,
            approval_id=approval_id,
            project_key=project_key,
            source_context=self._get_run_source_context(run_id),
        )
        self._update_run_status(run_id, status="running", started_at=_now_iso())
        try:
            result = await definition.handler(context)
        except CommandGatewayError as exc:
            self._update_run_status(
                run_id,
                status="failed",
                finished_at=_now_iso(),
                error_json={"message": str(exc), "type": exc.__class__.__name__},
            )
            if not definition.read_only:
                self._record_command_execution_audit(
                    definition=definition,
                    run_id=run_id,
                    user=user,
                    source=source,
                    project_key=project_key,
                    status="failed",
                    error={"message": str(exc), "type": exc.__class__.__name__},
                )
            raise
        except Exception as exc:
            self._update_run_status(
                run_id,
                status="failed",
                finished_at=_now_iso(),
                error_json={"message": str(exc), "type": exc.__class__.__name__},
            )
            if not definition.read_only:
                self._record_command_execution_audit(
                    definition=definition,
                    run_id=run_id,
                    user=user,
                    source=source,
                    project_key=project_key,
                    status="failed",
                    error={"message": str(exc), "type": exc.__class__.__name__},
                )
            raise CommandGatewayError(f"命令执行失败: {exc}") from exc

        self._update_run_status(
            run_id,
            status="succeeded",
            finished_at=_now_iso(),
            result_json=result,
        )
        if not definition.read_only:
            self._record_command_execution_audit(
                definition=definition,
                run_id=run_id,
                user=user,
                source=source,
                project_key=project_key,
                status="succeeded",
                result=result,
            )
        return result

    def _normalize_arguments(
        self,
        definition: CommandDefinition,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        for spec in definition.arguments:
            raw_value = arguments.get(spec.name, spec.default)
            if spec.required and (raw_value is None or raw_value == ""):
                raise CommandValidationError(f"缺少必填参数 {spec.name}")
            if raw_value is None:
                normalized[spec.name] = raw_value
                continue
            normalized[spec.name] = self._coerce_argument(spec, raw_value)
        return normalized

    def _coerce_argument(self, spec: CommandArgumentSpec, value: Any) -> Any:
        if spec.type == "csv":
            if value is None or value == "":
                return []
            if isinstance(value, (list, tuple, set)):
                return [str(item).strip() for item in value if str(item).strip()]
            return [item.strip() for item in str(value).split(",") if item.strip()]
        if spec.type == "integer":
            try:
                number = int(value)
            except (TypeError, ValueError) as exc:
                raise CommandValidationError(f"参数 {spec.name} 必须是整数") from exc
            if number < 0:
                raise CommandValidationError(f"参数 {spec.name} 不能小于 0")
            return number
        if spec.type == "boolean":
            if isinstance(value, bool):
                return value
            text = str(value).strip().lower()
            if text in {"1", "true", "yes", "y", "on"}:
                return True
            if text in {"0", "false", "no", "n", "off"}:
                return False
            raise CommandValidationError(f"参数 {spec.name} 必须是布尔值")
        return str(value).strip()

    def _get_project_scope(self, user: Optional[User]) -> Optional[set[str]]:
        raw_scope = getattr(user, "project_ids", None)
        if not raw_scope:
            return None
        scope = {str(item).strip() for item in raw_scope if str(item).strip()}
        return scope or None

    def _is_scope_allowed(self, user: Optional[User], project_key: str) -> bool:
        if not user or not project_key:
            return True
        role_value = getattr(getattr(user, "role", None), "value", getattr(user, "role", ""))
        if role_value == "admin":
            return True
        scope = self._get_project_scope(user)
        if not scope or "*" in scope:
            return True
        return project_key in scope

    def _filter_scoped_items(
        self,
        user: Optional[User],
        items: List[Dict[str, Any]],
        *,
        field: str = "project_key",
    ) -> List[Dict[str, Any]]:
        if not user:
            return []
        role_value = getattr(getattr(user, "role", None), "value", getattr(user, "role", ""))
        scope = self._get_project_scope(user)
        if role_value == "admin" or not scope or "*" in scope:
            return items
        return [item for item in items if str(item.get(field) or "") in scope]

    def _resolve_project_key(
        self,
        definition: CommandDefinition,
        arguments: Dict[str, Any],
        *,
        user: Optional[User],
    ) -> str:
        direct = str(arguments.get("project_key") or "").strip()
        if direct:
            return direct
        if definition.command_id in {"release.risk.get", "release.deploy.request"}:
            assessment_id = str(arguments.get("assessment_id") or "").strip()
            if not assessment_id:
                return ""
            from services.release_risk_service import get_release_risk_service

            assessment = get_release_risk_service().get_assessment(
                user=user,
                assessment_id=assessment_id,
            )
            return str(assessment.get("project_key") or "").strip()
        if definition.command_id == "deploy.job.cancel":
            job_id = str(arguments.get("job_id") or "").strip()
            if not job_id:
                return ""
            current = get_deploy_service().get_job_detail(job_id)
            if not current:
                raise CommandValidationError(f"未找到部署作业 {job_id}")
            return str(current.get("project_key") or "").strip()
        return ""

    def _create_command_run(
        self,
        *,
        definition: CommandDefinition,
        arguments: Dict[str, Any],
        user: Optional[User],
        source: str,
        project_key: str,
        source_context: Dict[str, Any],
    ) -> str:
        run_id = f"cmdrun_{uuid.uuid4().hex[:12]}"
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO command_runs (
                    run_id, command_id, requester_id, source, project_key, args_json, source_context_json, status,
                    risk_level, approval_status, approval_id, sandbox_profile, result_json,
                    error_json, command_summary, read_only, env_scope, project_scope,
                    requires_confirmation, approval_policy, timeout_s, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    definition.command_id,
                    getattr(user, "user_id", ""),
                    source,
                    project_key,
                    _json_dump(arguments),
                    _json_dump(source_context),
                    "approval_pending" if definition.approval_required else "created",
                    definition.risk_level,
                    "pending" if definition.approval_required else "not_required",
                    "",
                    definition.sandbox_profile,
                    "",
                    "",
                    definition.summary,
                    1 if definition.read_only else 0,
                    definition.env_scope,
                    definition.project_scope,
                    1 if definition.requires_confirmation else 0,
                    definition.approval_policy,
                    int(definition.timeout_s),
                    _now_iso(),
                ),
            )
        return run_id

    def _create_command_approval(
        self,
        *,
        run_id: str,
        definition: CommandDefinition,
        user: Optional[User],
        project_key: str,
    ) -> str:
        approval_id = f"cmdapproval_{uuid.uuid4().hex[:12]}"
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO command_approvals (
                    approval_id, run_id, command_id, requester_id, approver_id, project_key,
                    status, reason, comment, created_at, decided_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval_id,
                    run_id,
                    definition.command_id,
                    getattr(user, "user_id", ""),
                    "",
                    project_key,
                    "pending",
                    "",
                    "",
                    _now_iso(),
                    "",
                ),
            )
        return approval_id

    def _update_run_approval(self, run_id: str, approval_id: str, approval_status: str):
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE command_runs
                SET approval_id = ?, approval_status = ?, status = ?
                WHERE run_id = ?
                """,
                (
                    approval_id,
                    approval_status,
                    "approval_pending" if approval_status == "pending" else approval_status,
                    run_id,
                ),
            )

    def _update_run_status(
        self,
        run_id: str,
        *,
        status: str,
        approval_status: Optional[str] = None,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
        result_json: Any = None,
        error_json: Any = None,
    ):
        assignments = ["status = ?"]
        params: List[Any] = [status]
        if approval_status is not None:
            assignments.append("approval_status = ?")
            params.append(approval_status)
        if started_at is not None:
            assignments.append("started_at = ?")
            params.append(started_at)
        if finished_at is not None:
            assignments.append("finished_at = ?")
            params.append(finished_at)
        if result_json is not None:
            assignments.append("result_json = ?")
            params.append(_json_dump(result_json))
        if error_json is not None:
            assignments.append("error_json = ?")
            params.append(_json_dump(error_json))
        params.append(run_id)

        with get_connection() as conn:
            conn.execute(
                f"UPDATE command_runs SET {', '.join(assignments)} WHERE run_id = ?",
                tuple(params),
            )

    def _load_run_row(self, run_id: str) -> Dict[str, Any]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM command_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if not row:
            raise CommandRunNotFoundError(f"未找到命令运行 {run_id}")
        return dict(row)

    def _load_approval_row(self, approval_id: str) -> Dict[str, Any]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM command_approvals WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()
        if not row:
            raise CommandApprovalError(f"未找到命令审批 {approval_id}")
        return dict(row)

    def _serialize_approval_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "approval_id": str(row.get("approval_id") or ""),
            "run_id": str(row.get("run_id") or ""),
            "command_id": str(row.get("command_id") or ""),
            "requester_id": str(row.get("requester_id") or ""),
            "approver_id": str(row.get("approver_id") or ""),
            "project_key": str(row.get("project_key") or ""),
            "status": str(row.get("status") or ""),
            "reason": str(row.get("reason") or ""),
            "comment": str(row.get("comment") or ""),
            "created_at": str(row.get("created_at") or ""),
            "decided_at": str(row.get("decided_at") or ""),
        }

    def _serialize_run_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        approval_id = str(row.get("approval_id") or "")
        approval = self._get_command_approval(approval_id) if approval_id else None
        return {
            "run_id": str(row.get("run_id") or ""),
            "command_id": str(row.get("command_id") or ""),
            "requester_id": str(row.get("requester_id") or ""),
            "source": str(row.get("source") or ""),
            "project_key": str(row.get("project_key") or ""),
            "arguments": _json_load(row.get("args_json"), {}),
            "source_context": _json_load(row.get("source_context_json"), {}),
            "status": str(row.get("status") or ""),
            "risk_level": str(row.get("risk_level") or ""),
            "approval_status": str(row.get("approval_status") or ""),
            "approval_id": approval_id,
            "sandbox_profile": str(row.get("sandbox_profile") or ""),
            "result": _json_load(row.get("result_json"), None),
            "error": _json_load(row.get("error_json"), None),
            "command_summary": str(row.get("command_summary") or ""),
            "read_only": bool(row.get("read_only")),
            "env_scope": str(row.get("env_scope") or ""),
            "project_scope": str(row.get("project_scope") or ""),
            "requires_confirmation": bool(row.get("requires_confirmation")),
            "approval_policy": str(row.get("approval_policy") or ""),
            "timeout_s": int(row.get("timeout_s") or 0),
            "created_at": str(row.get("created_at") or ""),
            "started_at": str(row.get("started_at") or ""),
            "finished_at": str(row.get("finished_at") or ""),
            "approval": approval,
        }

    def _get_command_run_payload(self, run_id: str) -> Dict[str, Any]:
        return self._serialize_run_row(self._load_run_row(run_id))

    def _get_run_source_context(self, run_id: str) -> Dict[str, Any]:
        row = self._load_run_row(run_id)
        return _json_load(row.get("source_context_json"), {})

    def _get_command_approval(self, approval_id: str) -> Dict[str, Any]:
        if not approval_id:
            return {}
        return self._serialize_approval_row(self._load_approval_row(approval_id))

    def _can_access_run(self, user: Optional[User], run: Dict[str, Any]) -> bool:
        if not user:
            return False
        project_key = str(run.get("project_key") or "")
        if project_key and not self._is_scope_allowed(user, project_key):
            return False

        requester_id = str(run.get("requester_id") or "")
        if requester_id and requester_id == getattr(user, "user_id", ""):
            return True

        definition = self._commands.get(str(run.get("command_id") or ""))
        auth = get_auth_service()
        if definition and definition.permission and auth.check_permission(user, definition.permission):
            return True
        return auth.check_permission(user, Permission.ADMIN)

    def _require_pending_approval(self, run: Dict[str, Any]) -> Dict[str, Any]:
        if str(run.get("approval_status") or "") != "pending":
            raise CommandApprovalError(f"命令运行 {run['run_id']} 当前不处于待审批状态")
        approval_id = str(run.get("approval_id") or "")
        if not approval_id:
            raise CommandApprovalError(f"命令运行 {run['run_id']} 缺少审批单")
        approval = self._get_command_approval(approval_id)
        if approval.get("status") != "pending":
            raise CommandApprovalError(f"命令审批 {approval_id} 当前状态不是 pending")
        return approval

    def _ensure_approval_permission(self, user: Optional[User], definition: CommandDefinition):
        if not user:
            raise CommandPermissionError("需要登录态")
        permission = definition.approval_permission or Permission.ADMIN
        auth = get_auth_service()
        if not auth.check_permission(user, permission):
            raise CommandPermissionError(
                f"审批命令 {definition.command_id} 需要权限 {permission.value}"
            )

    def _mark_approval_decision(
        self,
        *,
        approval_id: str,
        status: str,
        approver_id: str,
        comment: str,
    ):
        decided_at = _now_iso()
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE command_approvals
                SET status = ?, approver_id = ?, comment = ?, reason = ?, decided_at = ?
                WHERE approval_id = ?
                """,
                (
                    status,
                    approver_id,
                    comment,
                    comment,
                    decided_at,
                    approval_id,
                ),
            )

    def _record_command_requested_audit(
        self,
        *,
        definition: CommandDefinition,
        run_id: str,
        user: Optional[User],
        source: str,
        project_key: str,
        approval_id: str,
    ):
        get_auth_service().record_audit_event(
            action="commander_command_requested",
            resource_type="command_run",
            resource_id=run_id,
            details={
                "command_id": definition.command_id,
                "project_key": project_key,
                "source": source,
                "risk_level": definition.risk_level,
                "approval_required": definition.approval_required,
                "approval_id": approval_id,
            },
            user_id=getattr(user, "user_id", None),
        )

    def _record_command_approval_requested_audit(
        self,
        *,
        definition: CommandDefinition,
        run_id: str,
        approval_id: str,
        user: Optional[User],
        source: str,
        project_key: str,
    ):
        get_auth_service().record_audit_event(
            action="commander_command_approval_requested",
            resource_type="command_approval",
            resource_id=approval_id,
            details={
                "run_id": run_id,
                "command_id": definition.command_id,
                "project_key": project_key,
                "source": source,
            },
            user_id=getattr(user, "user_id", None),
        )

    def _record_command_approval_decision_audit(
        self,
        *,
        definition: CommandDefinition,
        run_id: str,
        approval_id: str,
        user: Optional[User],
        source: str,
        project_key: str,
        decision: str,
        comment: str,
    ):
        get_auth_service().record_audit_event(
            action=f"commander_command_approval_{decision}",
            resource_type="command_approval",
            resource_id=approval_id,
            details={
                "run_id": run_id,
                "command_id": definition.command_id,
                "project_key": project_key,
                "source": source,
                "decision": decision,
                "comment": comment,
            },
            user_id=getattr(user, "user_id", None),
        )

    def _record_command_execution_audit(
        self,
        *,
        definition: CommandDefinition,
        run_id: str,
        user: Optional[User],
        source: str,
        project_key: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[Dict[str, Any]] = None,
    ):
        details = {
            "command_id": definition.command_id,
            "project_key": project_key,
            "source": source,
            "status": status,
        }
        if result is not None:
            details["result"] = result
        if error is not None:
            details["error"] = error
        get_auth_service().record_audit_event(
            action="commander_command_executed",
            resource_type="command_run",
            resource_id=run_id,
            details=details,
            user_id=getattr(user, "user_id", None),
        )

    def _serialize_deploy_audit_log(self, log) -> Dict[str, Any]:
        auth = get_auth_service()
        user = auth.users.get(log.user_id)
        details = dict(log.details or {})
        return {
            "log_id": log.log_id,
            "user_id": log.user_id,
            "username": getattr(user, "username", "") if user else "",
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "project_key": str(details.get("project_key") or ""),
            "details": details,
            "timestamp": log.timestamp,
            "ip_address": log.ip_address,
        }

    async def _handle_platform_status(self, context: CommandExecutionContext) -> Dict[str, Any]:
        from agents.commander import get_commander
        from core.agent_bus import get_agent_bus
        from core.agent_profile import get_profile_manager
        from services.commander_chatops_service import get_commander_chatops_service

        get_commander()
        bus = get_agent_bus()
        health = bus.get_health()
        profiles = get_profile_manager().list_all()
        registered = max(len(health), len(profiles))
        healthy = sum(1 for agent in health if agent.get("healthy"))
        active = sum(1 for agent in health if agent.get("active"))
        chatops = get_commander_chatops_service().get_overview(allow_live_probe=False)

        return {
            "summary": {
                "registered_agents": registered,
                "healthy_agents": healthy,
                "active_agents": active,
                "chatops_ready": bool(chatops.get("ready")),
                "chatops_platform_ready": bool(chatops.get("platform_ready")),
            },
            "agents": health,
            "chatops": chatops,
        }

    async def _handle_commander_mission_start(self, context: CommandExecutionContext) -> Dict[str, Any]:
        from agents.commander import get_commander

        user_input = str(context.arguments.get("user_input") or "").strip()
        if not user_input:
            raise CommandValidationError("缺少测试需求 user_input")

        target_url = str(context.arguments.get("target_url") or "").strip()
        diff_text = str(context.arguments.get("diff_text") or "").strip()
        mode = str(context.arguments.get("mode") or "").strip() or None
        parallel = bool(context.arguments.get("parallel", True))

        commander = get_commander()
        mission_id = uuid.uuid4().hex[:8]
        mission = {
            "mission_id": mission_id,
            "user_input": user_input,
            "target_url": target_url,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "strategy": None,
            "test_tasks_count": 0,
            "test_results_count": 0,
            "report": None,
            "logs": [],
            "trace_id": None,
            "execution_group_id": mission_id,
            "execution_center_path": f"/history?group={mission_id}",
            "bug_summary": [],
        }
        commander._missions[mission_id] = mission

        async def _run_in_background():
            try:
                await commander.run_swarm(
                    user_input=user_input,
                    target_url=target_url,
                    diff_text=diff_text,
                    mode=mode,
                    mission_id=mission_id,
                )
            except Exception as exc:
                mission_obj = commander._missions.get(mission_id)
                if isinstance(mission_obj, dict):
                    mission_obj["status"] = "failed"
                    mission_obj.setdefault("logs", []).append(
                        {
                            "timestamp": datetime.now().isoformat(),
                            "level": "error",
                            "message": f"❌ 任务异常: {exc}",
                            "data": {},
                        }
                    )

        asyncio.create_task(_run_in_background())
        return {
            "mission_id": mission_id,
            "mission": mission,
            "parallel": parallel,
        }

    async def _handle_commander_mission_cancel(self, context: CommandExecutionContext) -> Dict[str, Any]:
        from agents.commander import get_commander

        mission_id = str(context.arguments.get("mission_id") or "").strip()
        if not mission_id:
            raise CommandValidationError("缺少任务 ID")

        commander = get_commander()
        cancelled = commander.cancel_mission(mission_id)
        if not cancelled:
            raise CommandValidationError(f"任务 {mission_id} 不存在或当前不可取消")
        mission = commander.get_mission(mission_id)
        return {
            "mission_id": mission_id,
            "cancelled": True,
            "mission": mission,
        }

    async def _handle_mission_report(self, context: CommandExecutionContext) -> Dict[str, Any]:
        from agents.commander import get_commander

        mission_id = context.arguments["mission_id"]
        commander = get_commander()
        mission = commander.get_mission(mission_id)
        if not mission:
            raise CommandValidationError(f"未找到任务 {mission_id}")

        report = mission.get("report") if isinstance(mission, dict) else {}
        summary = report.get("summary", {}) if isinstance(report, dict) else {}
        return {
            "mission_id": mission_id,
            "mission": mission,
            "summary": {
                "total_tests": summary.get(
                    "total_tests",
                    mission.get("test_results_count", 0) if isinstance(mission, dict) else 0,
                ),
                "completed": summary.get("completed", 0),
                "failed": summary.get("failed", 0),
                "success_rate": summary.get("success_rate", 0),
            },
        }

    async def _handle_exploration_session_create(self, context: CommandExecutionContext) -> Dict[str, Any]:
        from services.exploration_service import get_exploration_service

        session = get_exploration_service().create_session(
            user=context.user,
            group_id=context.arguments.get("group_id", ""),
            project_key=context.arguments.get("project_key", ""),
            target_url=context.arguments["target_url"],
            charter=context.arguments["charter"],
        )
        return {"session": session}

    async def _handle_exploration_findings_list(self, context: CommandExecutionContext) -> Dict[str, Any]:
        from services.exploration_service import get_exploration_service

        return get_exploration_service().list_findings(
            user=context.user,
            session_id=context.arguments["session_id"],
            severity=context.arguments.get("severity", ""),
            review_only=bool(context.arguments.get("review_only")),
            review_status=context.arguments.get("review_status", ""),
        )

    async def _handle_exploration_review_queue_list(self, context: CommandExecutionContext) -> Dict[str, Any]:
        from services.exploration_service import get_exploration_service

        return get_exploration_service().list_review_queue(
            user=context.user,
            project_key=context.arguments.get("project_key", ""),
            severity=context.arguments.get("severity", ""),
            review_status=context.arguments.get("review_status", ""),
            limit=context.arguments.get("limit", 20),
        )

    async def _handle_exploration_finding_review(self, context: CommandExecutionContext) -> Dict[str, Any]:
        from services.exploration_service import get_exploration_service

        finding = get_exploration_service().review_finding(
            user=context.user,
            finding_id=context.arguments["finding_id"],
            decision=context.arguments["decision"],
            comment=context.arguments.get("comment", ""),
        )
        return {"finding": finding}

    async def _handle_release_risk_assess(self, context: CommandExecutionContext) -> Dict[str, Any]:
        from services.release_risk_service import get_release_risk_service

        assessment = get_release_risk_service().create_assessment(
            user=context.user,
            project_key=context.arguments.get("project_key", ""),
            environment=context.arguments.get("environment", "test"),
            exploration_session_ids=list(context.arguments.get("exploration_session_ids", [])),
            required_tests_passed=bool(context.arguments.get("required_tests_passed", True)),
            change_summary=context.arguments.get("change_summary", ""),
        )
        return {"assessment": assessment}

    async def _handle_release_risk_get(self, context: CommandExecutionContext) -> Dict[str, Any]:
        from services.release_risk_service import get_release_risk_service

        assessment = get_release_risk_service().get_assessment(
            user=context.user,
            assessment_id=context.arguments["assessment_id"],
        )
        return {"assessment": assessment}

    async def _handle_release_deploy_request(self, context: CommandExecutionContext) -> Dict[str, Any]:
        from services.release_risk_service import get_release_risk_service

        assessment = get_release_risk_service().get_assessment(
            user=context.user,
            assessment_id=context.arguments["assessment_id"],
        )
        project_key = str(assessment.get("project_key") or "").strip()
        if project_key and not self._is_scope_allowed(context.user, project_key):
            raise CommandPermissionError(f"当前账号无权操作项目 {project_key}")

        target_type = str(context.arguments.get("target_type") or "").strip().lower()
        if target_type not in {"repo", "project"}:
            raise CommandValidationError("target_type 必须是 repo 或 project")

        repo_id = str(context.arguments.get("repo_id") or "").strip()
        branch = str(context.arguments.get("branch") or "").strip()
        comment = str(context.arguments.get("comment") or "").strip()
        if target_type == "repo" and not repo_id:
            raise CommandValidationError("target_type=repo 时必须提供 repo_id")

        environment = str(
            assessment.get("environment")
            or (assessment.get("input") or {}).get("environment")
            or ""
        ).strip().lower()
        auto_release_eligible = bool(assessment.get("auto_release_eligible"))
        blockers = list(assessment.get("blockers") or [])
        policy_hit = dict(assessment.get("policy_hit") or {})
        review_blocked = bool(policy_hit.get("review_blocked"))
        non_production = environment not in {"prod", "production", "online"}
        should_auto_execute = bool(non_production and auto_release_eligible)

        svc = get_deploy_service()
        action = "full_deploy" if target_type == "repo" else "full_deploy_all"
        approval = svc.create_deploy_approval(
            action=action,
            project_key=project_key,
            repo_id=repo_id if target_type == "repo" else "",
            branch=branch if target_type == "repo" else "",
            request_comment=comment,
            requested_by=getattr(context.user, "user_id", "unknown"),
            requested_by_name=getattr(context.user, "username", "") or getattr(context.user, "user_id", "unknown"),
        )
        release_decision = "approval_created"
        approval_id = str(approval.get("id") or "")
        job = None

        self._record_release_deploy_audit(
            action="deploy_approval_request_create",
            approval_id=approval_id,
            user_id=getattr(context.user, "user_id", None),
            assessment_id=str(assessment.get("assessment_id") or ""),
            command_run_id=context.run_id,
            release_decision=release_decision,
            project_key=project_key,
            repo_id=repo_id if target_type == "repo" else "",
            branch=branch if target_type == "repo" else "",
            job_id="",
            comment=comment,
            blockers=blockers,
            review_blocked=review_blocked,
        )

        if should_auto_execute:
            release_decision = "auto_executed"
            auto_comment_parts = [
                f"assessment={assessment.get('assessment_id')}",
                f"environment={environment or 'unknown'}",
                "policy=auto_release_eligible",
            ]
            if review_blocked:
                auto_comment_parts.append("review_blocked=true")
            auto_comment = " | ".join(auto_comment_parts)
            approval = svc.review_approval(
                approval_id,
                approved=True,
                reviewed_by="system:auto-release",
                reviewed_by_name="Auto Release Policy",
                comment=auto_comment,
            )
            job = approval.get("job") if isinstance(approval, dict) else None
            if not job and approval.get("job_id"):
                job = svc.get_job_detail(str(approval.get("job_id") or ""))
            self._record_release_deploy_audit(
                action="deploy_approval_approve",
                approval_id=approval_id,
                user_id="system:auto-release",
                assessment_id=str(assessment.get("assessment_id") or ""),
                command_run_id=context.run_id,
                release_decision=release_decision,
                project_key=project_key,
                repo_id=repo_id if target_type == "repo" else "",
                branch=branch if target_type == "repo" else "",
                job_id=str(approval.get("job_id") or ""),
                comment=auto_comment,
                blockers=blockers,
                review_blocked=review_blocked,
            )

        result = {
            "assessment_id": str(assessment.get("assessment_id") or ""),
            "assessment": assessment,
            "release_decision": release_decision,
            "approval_id": approval_id,
            "job_id": str((approval or {}).get("job_id") or ""),
            "approval": approval,
            "job": job,
            "deploy_target": {
                "target_type": target_type,
                "project_key": project_key,
                "repo_id": repo_id if target_type == "repo" else "",
                "branch": branch if target_type == "repo" else "",
            },
        }
        return result

    async def _handle_deploy_approvals_list(self, context: CommandExecutionContext) -> Dict[str, Any]:
        svc = get_deploy_service()
        approvals = svc.list_approvals(
            limit=context.arguments.get("limit", 10),
            status=context.arguments.get("status", ""),
        )
        scoped = self._filter_scoped_items(context.user, approvals)
        return {"approvals": scoped, "count": len(scoped)}

    async def _handle_deploy_jobs_list(self, context: CommandExecutionContext) -> Dict[str, Any]:
        svc = get_deploy_service()
        jobs = svc.list_jobs(
            limit=context.arguments.get("limit", 10),
            status=context.arguments.get("status", ""),
        )
        scoped = self._filter_scoped_items(context.user, jobs)
        return {"jobs": scoped, "count": len(scoped)}

    async def _handle_deploy_history_list(self, context: CommandExecutionContext) -> Dict[str, Any]:
        svc = get_deploy_service()
        limit = context.arguments.get("limit", 10)
        status = context.arguments.get("status", "")
        items = []
        for record in reversed(svc.history):
            payload = asdict(record)
            if status and payload.get("status") != status:
                continue
            items.append(payload)
            if len(items) >= limit:
                break
        scoped = self._filter_scoped_items(context.user, items)
        return {"history": scoped, "count": len(scoped)}

    async def _handle_deploy_audit_list(self, context: CommandExecutionContext) -> Dict[str, Any]:
        auth = get_auth_service()
        limit = context.arguments.get("limit", 10)
        action = context.arguments.get("action", "")
        project_key = context.arguments.get("project_key", "")
        user_id = context.arguments.get("user_id", "")

        logs = auth.get_audit_logs(
            user_id=user_id or None,
            action=action or None,
            action_prefix="deploy_",
            limit=limit * 5,
        )
        payloads = [self._serialize_deploy_audit_log(item) for item in logs]
        payloads = self._filter_scoped_items(context.user, payloads)
        if project_key:
            payloads = [item for item in payloads if item.get("project_key") == project_key]
        return {"logs": payloads[:limit], "count": len(payloads[:limit])}

    async def _handle_deploy_job_cancel(self, context: CommandExecutionContext) -> Dict[str, Any]:
        svc = get_deploy_service()
        job_id = context.arguments["job_id"]
        current = svc.get_job_detail(job_id)
        if not current:
            raise CommandValidationError(f"未找到部署作业 {job_id}")
        project_key = str(current.get("project_key") or "")
        if not self._is_scope_allowed(context.user, project_key):
            raise CommandPermissionError(f"当前账号无权操作项目 {project_key}")

        job = svc.cancel_job(job_id)
        return {"job": job}

    def _record_release_deploy_audit(
        self,
        *,
        action: str,
        approval_id: str,
        user_id: Optional[str],
        assessment_id: str,
        command_run_id: str,
        release_decision: str,
        project_key: str,
        repo_id: str,
        branch: str,
        job_id: str,
        comment: str,
        blockers: List[Dict[str, Any]],
        review_blocked: bool,
    ):
        get_auth_service().record_audit_event(
            action=action,
            resource_type="deploy_approval",
            resource_id=approval_id,
            details={
                "approval_id": approval_id,
                "assessment_id": assessment_id,
                "command_run_id": command_run_id,
                "release_decision": release_decision,
                "project_key": project_key,
                "repo_id": repo_id,
                "branch": branch,
                "job_id": job_id,
                "comment": comment,
                "review_blocked": review_blocked,
                "blocker_types": [str(item.get("type") or "") for item in blockers if isinstance(item, dict)],
            },
            user_id=user_id,
        )


_service_instance: Optional[CommanderCommandGatewayService] = None


def get_commander_command_gateway() -> CommanderCommandGatewayService:
    global _service_instance
    if _service_instance is None:
        _service_instance = CommanderCommandGatewayService()
    return _service_instance
