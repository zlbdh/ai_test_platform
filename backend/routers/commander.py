# -*- coding: utf-8 -*-
"""
Commander API 路由

提供 Commander 总指挥的 REST API：
- POST /api/commander/run       一句话启动全面测试
- GET  /api/commander/status    查询任务状态
- POST /api/commander/cancel    取消任务
- GET  /api/commander/missions  历史任务列表
- GET  /api/commander/stream    SSE 流式进度
- POST /api/commander/architect 测试架构师分析
"""

import asyncio
import json
import logging
import os
import re
import secrets
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, Literal, Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
import httpx
from core.config import Config
from core.db_helper import get_connection, query_all, execute
from core.models import (
    CommanderChatOpsAppBotConfigRequest,
    CommanderChatOpsAppBotUnbindRequest,
    CommanderChatOpsCallbackConfigRequest,
    CommanderChatOpsSimulateRequest,
    CommanderChatOpsSubscriptionSelfCheckRequest,
    CommanderChatOpsTokenConfigRequest,
)
from core.auth_dependencies import require_authenticated_user
from services.auth_service import UserRole, get_auth_service
from services.commander_chatops_service import get_commander_chatops_service
from services.commander_chatops_binding_service import (
    ChatOpsBindingValidationError,
    get_commander_chatops_binding_service,
)
from services.commander_command_gateway_service import (
    CommandApprovalError,
    CommandConfirmationRequiredError,
    CommandGatewayError,
    CommandPermissionError,
    CommandRunNotFoundError,
    CommandValidationError,
    get_commander_command_gateway,
)
from services.prototype_agents import get_prototype_agents_service
from services.unified_task_service import get_unified_task_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/commander", tags=["Commander 总指挥"])


def _init_chatops_table():
    with get_connection() as conn:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS commander_chatops_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT DEFAULT 'generic',
                source TEXT DEFAULT 'manual',
                event_type TEXT DEFAULT 'message',
                message TEXT DEFAULT '',
                from_user TEXT DEFAULT '',
                chat_id TEXT DEFAULT '',
                response TEXT DEFAULT '',
                status TEXT DEFAULT 'ok',
                delivery_configured INTEGER DEFAULT 0,
                delivery_delivered INTEGER DEFAULT 0,
                delivery_failed INTEGER DEFAULT 0,
                run_id TEXT DEFAULT '',
                command_id TEXT DEFAULT '',
                requester_id TEXT DEFAULT '',
                binding_status TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            )
            '''
        )
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS commander_chatops_chat_bindings (
                chat_id TEXT PRIMARY KEY,
                channel TEXT DEFAULT 'notification_platform',
                source TEXT DEFAULT 'event_subscription',
                last_from_user TEXT DEFAULT '',
                last_message TEXT DEFAULT '',
                last_seen_at TEXT DEFAULT (datetime('now')),
                last_reply_mode TEXT DEFAULT '',
                last_delivery_ok INTEGER DEFAULT 0,
                last_run_id TEXT DEFAULT '',
                last_command_id TEXT DEFAULT '',
                last_requester_id TEXT DEFAULT '',
                binding_status TEXT DEFAULT ''
            )
            '''
        )
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS commander_chatops_app_bot_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                success INTEGER DEFAULT 0,
                message TEXT DEFAULT '',
                status_code INTEGER,
                source TEXT DEFAULT 'manual',
                app_id_masked TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            )
            '''
        )
        event_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(commander_chatops_events)").fetchall()
        }
        for column_name, column_sql in (
            ("run_id", "TEXT DEFAULT ''"),
            ("command_id", "TEXT DEFAULT ''"),
            ("requester_id", "TEXT DEFAULT ''"),
            ("binding_status", "TEXT DEFAULT ''"),
        ):
            if column_name not in event_columns:
                conn.execute(
                    f"ALTER TABLE commander_chatops_events ADD COLUMN {column_name} {column_sql}"
                )

        binding_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(commander_chatops_chat_bindings)").fetchall()
        }
        for column_name, column_sql in (
            ("last_run_id", "TEXT DEFAULT ''"),
            ("last_command_id", "TEXT DEFAULT ''"),
            ("last_requester_id", "TEXT DEFAULT ''"),
            ("binding_status", "TEXT DEFAULT ''"),
        ):
            if column_name not in binding_columns:
                conn.execute(
                    f"ALTER TABLE commander_chatops_chat_bindings ADD COLUMN {column_name} {column_sql}"
                )


_init_chatops_table()


# ── 请求模型 ─────────────────────────────────────────────────────────────────


from pydantic import BaseModel, Field


class CommanderRunRequest(BaseModel):
    """Commander 运行请求"""
    user_input: str = Field(..., description="自然语言测试需求")
    target_url: str = Field("", description="目标 URL（可选）")
    parallel: bool = Field(True, description="是否并行执行测试线")


class PrototypeWorkerSwitches(BaseModel):
    visual: bool = Field(True, description="是否启用 Visual Worker")
    flow: bool = Field(True, description="是否启用 Flow Worker")
    ab: bool = Field(True, description="是否启用 A/B Worker")
    a11y: bool = Field(True, description="是否启用 A11y Worker")
    perf: bool = Field(True, description="是否启用 Perf Worker")


class PrototypeProviders(BaseModel):
    visual: Optional[str] = Field(None, description="Visual Worker Provider")
    flow: Optional[str] = Field(None, description="Flow Worker Provider")
    ab: Optional[str] = Field(None, description="A/B Worker Provider")
    a11y: Optional[str] = Field(None, description="A11y Worker Provider")
    perf: Optional[str] = Field(None, description="Perf Worker Provider")


class PrototypeRunRequest(BaseModel):
    source_type: str = Field(..., description="来源类型: url | file | directory")
    source: str = Field(..., description="原型 URL / 文件路径 / 目录路径")
    compare_source: str = Field("", description="可选的 A/B 对比来源")
    playbook_id: str = Field("", description="可选项目包 ID")
    worker_switches: PrototypeWorkerSwitches = Field(default_factory=PrototypeWorkerSwitches)
    providers: PrototypeProviders = Field(default_factory=PrototypeProviders)
    wcag_level: str = Field("AA", description="A11y 目标级别")


class UnifiedTaskRequest(BaseModel):
    """统一任务前门请求"""
    task_kind: Literal["general", "prototype", "exploration"] = Field(..., description="任务类型")
    user_goal: str = Field(..., description="用户目标/任务意图")
    source_context: Dict[str, Any] = Field(default_factory=dict, description="输入上下文")
    strategy: Dict[str, Any] = Field(default_factory=dict, description="执行策略")


class UnifiedTaskActionResponse(BaseModel):
    task_id: str
    cancelled: bool = Field(False, description="是否已停止")
    status: str = Field(..., description="任务当前状态")
    message: str = Field(..., description="动作反馈")


class ArchitectRequest(BaseModel):
    """TestArchitect 分析请求"""
    input_text: str = Field("", description="需求描述/PRD")
    target_url: str = Field("", description="目标 URL")
    mode: Optional[str] = Field(None, description="发现模式: requirement/change/exploration/coverage/fault")
    diff_text: str = Field("", description="Git diff 文本（变更驱动）")


class CancelRequest(BaseModel):
    """取消请求"""
    mission_id: str = Field(..., description="任务 ID")


class CommanderCommandExecuteRequest(BaseModel):
    """统一命令网关执行请求"""
    command_id: str = Field(..., description="命令 ID")
    arguments: dict = Field(default_factory=dict, description="命令参数")
    confirm: bool = Field(False, description="高风险命令显式确认")


class CommanderCommandApprovalDecisionRequest(BaseModel):
    """统一命令审批决策请求"""
    comment: str = Field("", description="审批备注/驳回原因")
    confirm: bool = Field(True, description="审批执行时的显式确认")


def _build_streaming_response(commander, mission_id: str) -> StreamingResponse:
    async def event_generator():
        last_index = 0
        heartbeat_count = 0

        while True:
            logs = commander.get_mission_logs(mission_id, since_index=last_index)

            for log_entry in logs:
                data = json.dumps(log_entry, ensure_ascii=False)
                yield f"data: {data}\n\n"
                last_index += 1

            mission = commander.get_mission(mission_id)
            if mission and mission.get("status") in ("completed", "failed", "cancelled"):
                yield f"data: {json.dumps({'level': 'end', 'message': '任务结束'}, ensure_ascii=False)}\n\n"
                break

            heartbeat_count += 1
            if heartbeat_count % 5 == 0:
                yield ": heartbeat\n\n"

            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── API 端点 ─────────────────────────────────────────────────────────────────


@router.post("/run")
async def commander_run(req: CommanderRunRequest):
    """
    🚀 一句话启动全面测试（非阻塞）

    立即返回 mission_id，任务在后台执行。
    前端通过 GET /stream/{mission_id} 实时跟踪进度。
    """
    from agents.commander import get_commander

    commander = get_commander()
    
    # 先创建任务记录，获取 mission_id
    import uuid
    import datetime
    mission_id = uuid.uuid4().hex[:8]
    mission = {
        "mission_id": mission_id,
        "user_input": req.user_input,
        "target_url": req.target_url,
        "status": "pending",
        "created_at": datetime.datetime.now().isoformat(),
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
    
    # 后台执行任务
    async def _run_in_background():
        try:
            result = await commander.run(
                user_input=req.user_input,
                target_url=req.target_url,
                parallel=req.parallel,
                mission_id=mission_id,
            )
        except Exception as e:
            logger.error(f"Background mission {mission_id} failed: {e}")
            mission_obj = commander._missions.get(mission_id)
            if isinstance(mission_obj, dict):
                mission_obj["status"] = "failed"
                mission_obj.setdefault("logs", []).append({
                    "timestamp": datetime.datetime.now().isoformat(),
                    "level": "error",
                    "message": f"❌ 任务异常: {e}",
                    "data": {},
                })
            elif mission_obj is not None:
                from agents.commander import MissionStatus

                mission_obj.status = MissionStatus.FAILED
                mission_obj.log(f"❌ 任务异常: {e}", level="error")
    
    asyncio.create_task(_run_in_background())
    
    return mission


@router.post("/prototype/run")
async def commander_prototype_run(req: PrototypeRunRequest):
    """启动原型测试 7 Agent 编排链。"""
    from agents.commander import get_commander

    commander = get_commander()
    service = get_prototype_agents_service()
    mission = service.create_mission(req.model_dump())
    mission_id = mission["mission_id"]
    commander._missions[mission_id] = mission

    async def _run_in_background():
        try:
            await service.run_mission(commander, mission_id, req.model_dump())
        except Exception as exc:
            logger.error("Prototype mission %s failed: %s", mission_id, exc, exc_info=True)
            mission_obj = commander._missions.get(mission_id)
            if isinstance(mission_obj, dict):
                mission_obj["status"] = "failed"
                mission_obj["completed_at"] = datetime.now().isoformat()
                mission_obj.setdefault("logs", []).append(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "level": "error",
                        "message": f"❌ 原型任务异常: {exc}",
                        "data": {"agent_id": "orchestrator", "agent_status": "error"},
                    }
                )
                mission_obj.setdefault("agent_states", {})
                mission_obj["agent_states"]["orchestrator"] = "error"
                mission_obj["agent_states"]["reporter"] = "error"
                try:
                    commander._save_missions()
                except Exception:
                    pass

    asyncio.create_task(_run_in_background())
    return mission


@router.post("/tasks")
async def commander_create_unified_task(req: UnifiedTaskRequest):
    """统一前门任务入口。"""
    from agents.commander import get_commander

    commander = get_commander()
    service = get_unified_task_service()
    return service.create_task(
        commander=commander,
        task_kind=req.task_kind,
        user_goal=req.user_goal,
        source_context=req.source_context,
        strategy=req.strategy,
    )


@router.get("/tasks")
async def commander_list_unified_tasks(
    limit: int = Query(20, ge=1, le=100),
    task_kind: str = Query("", description="可选任务类型过滤"),
    status: str = Query("", description="可选状态过滤"),
    lineage_root_id: str = Query("", description="可选复跑链根任务过滤"),
):
    """列出统一前门任务。"""
    from agents.commander import get_commander

    commander = get_commander()
    service = get_unified_task_service()
    return service.list_tasks(
        commander=commander,
        limit=limit,
        task_kind=task_kind,
        status=status,
        lineage_root_id=lineage_root_id,
    )


@router.get("/tasks/{task_id}")
async def commander_get_unified_task(task_id: str):
    """查询统一前门任务详情。"""
    from agents.commander import get_commander

    commander = get_commander()
    service = get_unified_task_service()
    task = service.get_task(commander=commander, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Unified task not found")
    return task


@router.get("/tasks/{task_id}/result")
async def commander_get_unified_task_result(task_id: str):
    """查询统一前门任务结果。"""
    from agents.commander import get_commander

    commander = get_commander()
    service = get_unified_task_service()
    task = service.get_task_result(commander=commander, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Unified task not found")
    return task


@router.post("/tasks/{task_id}/cancel", response_model=UnifiedTaskActionResponse)
async def commander_cancel_unified_task(task_id: str):
    """停止统一前门任务。"""
    from agents.commander import get_commander

    commander = get_commander()
    service = get_unified_task_service()
    try:
        return service.cancel_task(commander=commander, task_id=task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unified task not found") from exc


@router.post("/tasks/{task_id}/rerun")
async def commander_rerun_unified_task(task_id: str):
    """按原任务上下文重新运行统一前门任务。"""
    from agents.commander import get_commander

    commander = get_commander()
    service = get_unified_task_service()
    try:
        return service.rerun_task(commander=commander, task_id=task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unified task not found") from exc


@router.get("/tasks/{task_id}/stream")
async def commander_stream_unified_task(task_id: str):
    """SSE 推送统一前门任务日志。"""
    from agents.commander import get_commander

    commander = get_commander()
    service = get_unified_task_service()
    task = service.get_task(commander=commander, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Unified task not found")
    return _build_streaming_response(commander, task_id)


@router.get("/status/{mission_id}")
async def commander_status(mission_id: str):
    """查询任务状态"""
    from agents.commander import get_commander

    commander = get_commander()
    mission = commander.get_mission(mission_id)
    if mission is None:
        return {"error": "Mission not found", "mission_id": mission_id}
    return mission


@router.get("/prototype/status/{mission_id}")
async def commander_prototype_status(mission_id: str):
    """查询原型测试任务状态。"""
    from agents.commander import get_commander

    commander = get_commander()
    mission = commander.get_mission(mission_id)
    if mission is None or mission.get("mission_kind") != "prototype_agents":
        return {"error": "Prototype mission not found", "mission_id": mission_id}
    return mission


@router.post("/cancel")
async def commander_cancel(req: CancelRequest):
    """取消任务"""
    from agents.commander import get_commander

    commander = get_commander()
    success = commander.cancel_mission(req.mission_id)
    return {
        "mission_id": req.mission_id,
        "cancelled": success,
    }


@router.get("/missions")
async def commander_missions(limit: int = Query(20, ge=1, le=100)):
    """获取最近的任务列表"""
    from agents.commander import get_commander

    commander = get_commander()
    return commander.list_missions(limit=limit)


@router.get("/prototype/missions")
async def commander_prototype_missions(limit: int = Query(20, ge=1, le=100)):
    """获取最近的原型测试任务列表。"""
    from agents.commander import get_commander

    commander = get_commander()
    return get_prototype_agents_service().list_missions(commander, limit=limit)


@router.delete("/missions/{mission_id}")
async def delete_mission(mission_id: str):
    """删除单条任务记录"""
    from agents.commander import get_commander

    commander = get_commander()
    if mission_id in commander._missions:
        del commander._missions[mission_id]
        return {"deleted": True, "mission_id": mission_id}
    return {"deleted": False, "error": "Mission not found"}


@router.delete("/missions")
async def clear_all_missions():
    """清空全部任务记录"""
    from agents.commander import get_commander

    commander = get_commander()
    count = len(commander._missions)
    commander._missions.clear()
    return {"cleared": True, "count": count}


@router.get("/stream/{mission_id}")
async def commander_stream(mission_id: str):
    """
    SSE 流式推送任务进度日志

    前端连接此端点后，会收到实时日志推送。
    """
    from agents.commander import get_commander

    commander = get_commander()

    return _build_streaming_response(commander, mission_id)


@router.get("/prototype/stream/{mission_id}")
async def commander_prototype_stream(mission_id: str):
    """SSE 推送原型测试任务日志。"""
    from agents.commander import get_commander

    commander = get_commander()
    mission = commander.get_mission(mission_id)
    if mission is None or mission.get("mission_kind") != "prototype_agents":
        raise HTTPException(status_code=404, detail="Prototype mission not found")
    return _build_streaming_response(commander, mission_id)


@router.post("/architect")
async def architect_analyze(req: ArchitectRequest):
    """
    🧠 测试架构师分析

    输入需求/URL/diff → 自动发现测试需求列表
    """
    from agents.test_architect import get_test_architect

    architect = get_test_architect()
    plan = await architect.analyze(
        input_text=req.input_text,
        target_url=req.target_url,
        mode=req.mode,
        diff_text=req.diff_text,
    )
    return plan.to_dict()


@router.get("/agents")
async def list_agents():
    """列出 AgentBus 上所有注册的 Agent"""
    from core.agent_bus import get_agent_bus

    bus = get_agent_bus()
    return {
        "agents": bus.list_agents(),
        "statistics": bus.get_statistics(),
    }


@router.get("/commands")
async def list_commander_commands(
    request: Request,
    user=Depends(require_authenticated_user),
):
    """列出统一命令网关中可用的命令定义。"""
    _ = request
    gateway = get_commander_command_gateway()
    return {
        "status": "success",
        "commands": gateway.list_commands(user=user),
    }


@router.post("/commands/execute")
async def execute_commander_command(
    req: CommanderCommandExecuteRequest,
    request: Request,
    user=Depends(require_authenticated_user),
):
    """通过统一命令网关执行一个受控命令。"""
    gateway = get_commander_command_gateway()
    try:
        result = await gateway.execute_command(
            req.command_id,
            req.arguments,
            user=user,
            confirm=bool(req.confirm),
            source="web",
        )
    except CommandPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CommandConfirmationRequiredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (CommandValidationError, CommandGatewayError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "success",
        "command_id": req.command_id,
        "result": result,
        "requested_by": getattr(user, "user_id", ""),
        "source": "web",
    }


@router.get("/commands/runs")
async def list_commander_command_runs(
    status: str = Query("", description="运行状态筛选"),
    approval_status: str = Query("", description="审批状态筛选"),
    command_id: str = Query("", description="命令 ID 筛选"),
    project_key: str = Query("", description="项目筛选"),
    source: str = Query("", description="来源筛选"),
    limit: int = Query(20, ge=1, le=200),
    user=Depends(require_authenticated_user),
):
    """列出统一命令运行记录。"""
    gateway = get_commander_command_gateway()
    try:
        payload = gateway.list_command_runs(
            user=user,
            status=status,
            approval_status=approval_status,
            command_id=command_id,
            project_key=project_key,
            source=source,
            limit=limit,
        )
    except CommandPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    return {"status": "success", **payload}


@router.get("/commands/runs/{run_id}")
async def get_commander_command_run(
    run_id: str,
    user=Depends(require_authenticated_user),
):
    """获取单条统一命令运行详情。"""
    gateway = get_commander_command_gateway()
    try:
        payload = gateway.get_command_run(run_id, user=user)
    except CommandRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CommandPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    return {"status": "success", "run": payload}


@router.post("/commands/runs/{run_id}/approve")
async def approve_commander_command_run(
    run_id: str,
    req: CommanderCommandApprovalDecisionRequest,
    user=Depends(require_authenticated_user),
):
    """审批并执行一条待审批命令。"""
    gateway = get_commander_command_gateway()
    try:
        payload = await gateway.approve_command_run(
            run_id,
            user=user,
            comment=req.comment,
            confirm=bool(req.confirm),
            source="web",
        )
    except CommandRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CommandPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (CommandApprovalError, CommandValidationError, CommandGatewayError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"status": "success", **payload}


@router.post("/commands/runs/{run_id}/reject")
async def reject_commander_command_run(
    run_id: str,
    req: CommanderCommandApprovalDecisionRequest,
    user=Depends(require_authenticated_user),
):
    """驳回一条待审批命令。"""
    gateway = get_commander_command_gateway()
    try:
        payload = gateway.reject_command_run(
            run_id,
            user=user,
            reason=req.comment,
            source="web",
        )
    except CommandRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CommandPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (CommandApprovalError, CommandValidationError, CommandGatewayError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"status": "success", **payload}


@router.get("/chatops/bindings/me")
async def get_commander_chatops_binding_me(user=Depends(require_authenticated_user)):
    """获取当前登录用户的通知平台绑定状态与最新绑定码。"""
    service = get_commander_chatops_binding_service()
    return {
        "status": "success",
        "binding": service.get_binding_for_user(user),
        "pending_code": service.get_latest_issued_code_for_user(user),
    }


@router.post("/chatops/bindings/me/issue")
async def issue_commander_chatops_binding_code(user=Depends(require_authenticated_user)):
    """为当前登录用户签发一个一次性通知平台绑定码。"""
    service = get_commander_chatops_binding_service()
    code = service.issue_binding_code(user, ttl_minutes=10)
    get_auth_service().record_audit_event(
        action="commander_chatops_binding_code_issued",
        resource_type="notification_platform_binding_code",
        resource_id=code.get("code"),
        details={"expires_at": code.get("expires_at")},
        user_id=getattr(user, "user_id", None),
    )
    return {
        "status": "success",
        "binding": service.get_binding_for_user(user),
        "pending_code": code,
    }


@router.post("/chatops/bindings/me/revoke")
async def revoke_commander_chatops_binding(user=Depends(require_authenticated_user)):
    """撤销当前登录用户的通知平台绑定与未使用绑定码。"""
    service = get_commander_chatops_binding_service()
    revoked = service.revoke_binding_for_user(user)
    get_auth_service().record_audit_event(
        action="commander_chatops_binding_revoked",
        resource_type="notification_platform_binding",
        resource_id=(revoked.get("binding") or {}).get("notification_platform_open_id"),
        details={"revoked_at": revoked.get("revoked_at")},
        user_id=getattr(user, "user_id", None),
    )
    return {
        "status": "success",
        "revoked": bool(revoked.get("binding")),
        "binding": revoked.get("binding"),
        "pending_code": None,
        "revoked_at": revoked.get("revoked_at"),
    }


@router.get("/tracing")
async def tracing_summary(trace_id: Optional[str] = None):
    """获取 LLM 调用链路追踪摘要"""
    from core.tracing import get_tracer

    tracer = get_tracer()
    return tracer.get_trace_summary(trace_id)


class SwarmRequest(BaseModel):
    """蜂群模式请求"""
    user_input: str = Field(..., description="自然语言测试需求")
    target_url: str = Field("", description="目标 URL")
    mode: Optional[str] = Field(None, description="发现模式: requirement/change/exploration/coverage/fault")
    diff_text: str = Field("", description="Git diff 文本（变更驱动）")


@router.post("/swarm")
async def commander_swarm(req: SwarmRequest):
    """
    🐝 蜂群模式 — 战略层分析 + 智能并行执行

    与 /run 的区别：先由 TestArchitect 做战略分析（5种发现模式），
    再智能分解为多条并行测试线。
    """
    import datetime as dt

    from agents.commander import get_commander

    commander = get_commander()

    # 预创建 mission 记录
    import uuid
    mission_id = uuid.uuid4().hex[:8]

    async def _run_swarm():
        try:
            await commander.run_swarm(
                user_input=req.user_input,
                target_url=req.target_url,
                mode=req.mode,
                diff_text=req.diff_text,
            )
        except Exception as e:
            logger.error(f"Swarm mission failed: {e}")

    asyncio.create_task(_run_swarm())

    return {
        "message": "🐝 蜂群模式已启动",
        "mode": req.mode or "auto",
        "user_input": req.user_input,
    }


@router.get("/health")
async def agent_health():
    """🏥 获取所有 Agent 的健康状态"""
    from core.agent_bus import get_agent_bus

    bus = get_agent_bus()
    return {
        "agents": bus.get_health(),
        "statistics": bus.get_statistics(),
    }


@router.get("/profiles")
async def list_profiles():
    """📋 获取所有 Agent Profile"""
    from core.agent_profile import get_profile_manager

    pm = get_profile_manager()
    return {
        "profiles": pm.to_summary(),
        "total": len(pm.list_all()),
    }


@router.get("/skills")
async def list_skills():
    """🧰 获取所有技能包"""
    from core.skill_loader import get_skill_loader

    loader = get_skill_loader()
    return {
        "skills": loader.to_summary(),
        "total": len(loader.list_all()),
    }


@router.get("/skills/{skill_id}")
async def get_skill_detail(skill_id: str):
    """📖 获取技能包详情（含策略全文）"""
    from core.skill_loader import get_skill_loader

    loader = get_skill_loader()
    skill = loader.get(skill_id)
    if not skill:
        return {"error": f"Skill '{skill_id}' not found"}
    return {
        "skill_id": skill.skill_id,
        "name": skill.name,
        "description": skill.description,
        "test_type": skill.test_type,
        "target_squad": skill.target_squad,
        "tags": skill.tags,
        "preconditions": skill.preconditions,
        "strategy_text": skill.strategy_text,
        "examples_count": len(skill.examples),
        "prompt_preview": skill.to_prompt()[:500],
    }


class WebhookMessage(BaseModel):
    """企微/钉钉 Webhook 回调消息"""
    msg_type: str = Field("text", description="消息类型")
    content: str = Field("", description="消息内容")
    from_user: str = Field("", description="发送人")
    chat_id: str = Field("", description="群聊 ID")


def _truncate_chatops_text(value: str, limit: int = 240) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _serialize_chatops_event(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "channel": row.get("channel", "generic"),
        "source": row.get("source", "manual"),
        "event_type": row.get("event_type", "message"),
        "message": row.get("message", ""),
        "from_user": row.get("from_user", ""),
        "chat_id": row.get("chat_id", ""),
        "response": row.get("response", ""),
        "status": row.get("status", "ok"),
        "delivery_configured": int(row.get("delivery_configured") or 0),
        "delivery_delivered": int(row.get("delivery_delivered") or 0),
        "delivery_failed": int(row.get("delivery_failed") or 0),
        "run_id": row.get("run_id", ""),
        "command_id": row.get("command_id", ""),
        "requester_id": row.get("requester_id", ""),
        "binding_status": row.get("binding_status", ""),
        "created_at": row.get("created_at", ""),
    }


def _record_chatops_event(
    *,
    channel: str,
    source: str,
    event_type: str,
    message: str,
    from_user: str,
    chat_id: str,
    response: str,
    status: str,
    delivery: Optional[dict] = None,
    run_id: str = "",
    command_id: str = "",
    requester_id: str = "",
    binding_status: str = "",
):
    delivery = delivery or {}
    execute(
        """
        INSERT INTO commander_chatops_events (
            channel, source, event_type, message, from_user, chat_id, response,
            status, delivery_configured, delivery_delivered, delivery_failed,
            run_id, command_id, requester_id, binding_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            channel,
            source,
            event_type,
            _truncate_chatops_text(message),
            _truncate_chatops_text(from_user, 120),
            _truncate_chatops_text(chat_id, 120),
            _truncate_chatops_text(response),
            status,
            int(delivery.get("configured") or 0),
            int(delivery.get("delivered") or 0),
            int(delivery.get("failed") or 0),
            _truncate_chatops_text(run_id, 120),
            _truncate_chatops_text(command_id, 120),
            _truncate_chatops_text(requester_id, 120),
            _truncate_chatops_text(binding_status, 60),
        ),
    )


def _upsert_chat_binding(
    *,
    channel: str,
    source: str,
    chat_id: str,
    from_user: str,
    message: str,
    reply_mode: str = "",
    delivery_ok: bool = False,
    run_id: str = "",
    command_id: str = "",
    requester_id: str = "",
    binding_status: str = "",
):
    normalized_chat_id = str(chat_id or "").strip()
    if not normalized_chat_id:
        return
    execute(
        """
        INSERT INTO commander_chatops_chat_bindings (
            chat_id, channel, source, last_from_user, last_message,
            last_seen_at, last_reply_mode, last_delivery_ok,
            last_run_id, last_command_id, last_requester_id, binding_status
        ) VALUES (?, ?, ?, ?, ?, datetime('now'), ?, ?, ?, ?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            channel=excluded.channel,
            source=excluded.source,
            last_from_user=excluded.last_from_user,
            last_message=excluded.last_message,
            last_seen_at=datetime('now'),
            last_reply_mode=excluded.last_reply_mode,
            last_delivery_ok=excluded.last_delivery_ok,
            last_run_id=excluded.last_run_id,
            last_command_id=excluded.last_command_id,
            last_requester_id=excluded.last_requester_id,
            binding_status=excluded.binding_status
        """,
        (
            normalized_chat_id,
            str(channel or "notification_platform"),
            str(source or "event_subscription"),
            _truncate_chatops_text(from_user, 120),
            _truncate_chatops_text(message),
            _truncate_chatops_text(reply_mode, 60),
            1 if delivery_ok else 0,
            _truncate_chatops_text(run_id, 120),
            _truncate_chatops_text(command_id, 120),
            _truncate_chatops_text(requester_id, 120),
            _truncate_chatops_text(binding_status, 60),
            ),
        )


def _record_app_bot_check(result: dict, source: str = "manual") -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO commander_chatops_app_bot_checks (
                success, message, status_code, source, app_id_masked
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                1 if bool(result.get("ok")) else 0,
                str(result.get("message") or ("应用机器人凭据校验通过" if result.get("ok") else "")),
                result.get("status_code"),
                str(source or "manual"),
                str(result.get("app_id_masked") or ""),
            ),
        )


def _purge_app_bot_state(purge_history: bool = True) -> dict:
    """清理当前项目误绑定应用机器人后残留的校验/联调痕迹。"""
    with get_connection() as conn:
        checks_removed = conn.execute("DELETE FROM commander_chatops_app_bot_checks").rowcount or 0
        bindings_removed = 0
        events_removed = 0
        if purge_history:
            bindings_removed = conn.execute("DELETE FROM commander_chatops_chat_bindings").rowcount or 0
            events_removed = conn.execute(
                """
                DELETE FROM commander_chatops_events
                WHERE source IN ('external_self_check', 'simulate', 'simulation')
                   OR chat_id LIKE 'oc_%'
                   OR chat_id = 'notification_debug_chat'
                """
            ).rowcount or 0
    return {
        "checks_removed": int(checks_removed),
        "bindings_removed": int(bindings_removed),
        "events_removed": int(events_removed),
    }


def _get_chatops_overview(*, allow_live_probe: bool = False) -> dict:
    return get_commander_chatops_service().get_overview(allow_live_probe=allow_live_probe)


def _extract_notification_platform_text_content(payload: dict) -> str:
    event = payload.get("event") or {}
    message = event.get("message") or {}
    content = message.get("content") or ""
    if not content:
        return ""
    try:
        parsed = json.loads(content)
    except Exception:
        return str(content).strip()
    return str(parsed.get("text") or "").strip()


def _extract_notification_platform_sender_identity(payload: dict) -> dict:
    event = payload.get("event") or {}
    sender = event.get("sender") or {}
    sender_id = sender.get("sender_id") or {}
    open_id = str(sender_id.get("open_id") or "").strip()
    user_id = str(sender_id.get("user_id") or "").strip()
    union_id = str(sender_id.get("union_id") or "").strip()
    return {
        "open_id": open_id,
        "user_id": user_id,
        "union_id": union_id,
        "sender_type": str(sender.get("sender_type") or "").strip(),
    }


def _detect_notification_platform_event_source(payload: dict, default_source: str = "event_subscription") -> str:
    """识别当前通知平台事件是否来自平台公网自测，而不是真实群聊回流。"""
    header = payload.get("header") or {}
    event = payload.get("event") or {}
    message = event.get("message") or {}
    sender = event.get("sender") or {}
    sender_id = sender.get("sender_id") or {}

    if payload.get("type") == "url_verification":
        challenge = str(payload.get("challenge") or "").strip().lower()
        if challenge.startswith("external-self-check-"):
            return "external_self_check"
        return default_source

    markers = [
        str(header.get("app_id") or "").strip().lower(),
        str(header.get("tenant_key") or "").strip().lower(),
        str(header.get("token") or "").strip().lower(),
        str(message.get("chat_id") or "").strip().lower(),
        str(sender_id.get("open_id") or "").strip().lower(),
        str(sender_id.get("user_id") or "").strip().lower(),
    ]
    if any(
        marker in {"external-self-check", "oc_external_self_check", "ou_external_self_check"}
        for marker in markers
        if marker
    ):
        return "external_self_check"
    return default_source


_CHATOPS_HELP_PATTERN = re.compile(
    r"^(你好|您好|hi|hello|hey|在吗|在么|help|帮助|命令|菜单|说明)[!！。?？\s]*$",
    re.IGNORECASE,
)
_CHATOPS_STATUS_PATTERN = re.compile(r"^(状态|health|status)[!！。?？\s]*$", re.IGNORECASE)
_CHATOPS_EMPTY_TEST_PATTERN = re.compile(r"^(测试|test|帮我测|帮我测试)[!！。?？\s]*$", re.IGNORECASE)
_CHATOPS_BIND_PATTERN = re.compile(r"^(绑定|bind)\s+([A-Za-z0-9\-]+)\s*$", re.IGNORECASE)
_CHATOPS_REPORT_PATTERN = re.compile(r"^(报告|report)\s+([^\s]+)\s*$", re.IGNORECASE)
_CHATOPS_FINDINGS_PATTERN = re.compile(r"^(发现|findings)\s+([^\s]+)\s*$", re.IGNORECASE)
_CHATOPS_RISK_PATTERN = re.compile(r"^(风险|risk)\s+([^\s]+)\s*$", re.IGNORECASE)
_CHATOPS_STOP_PATTERN = re.compile(r"^(停止|取消|stop|cancel)\s+([^\s]+)\s*$", re.IGNORECASE)
_CHATOPS_APPROVE_PATTERN = re.compile(r"^(批准|approve)\s+([^\s]+)(?:\s+(.+))?$", re.IGNORECASE)
_CHATOPS_REJECT_PATTERN = re.compile(r"^(驳回|reject)\s+([^\s]+)(?:\s+(.+))?$", re.IGNORECASE)


def _build_chatops_help_response() -> str:
    return (
        "👋 我是测试平台军团机器人。\n"
        "可直接发送：\n"
        "• 状态\n"
        "• 报告 <任务ID>\n"
        "• 测试 <URL/需求>\n"
        "• 发现 <探索会话ID>\n"
        "• 风险 <评估ID>\n"
        "• 停止 <任务ID>\n"
        "• 批准 <run_id> [备注] / 驳回 <run_id> [备注]\n"
        "• 绑定 <绑定码>"
    )


def _build_public_chatops_user():
    return SimpleNamespace(
        user_id="chatops_public",
        username="chatops_public",
        role=UserRole.VIEWER,
        project_ids=["*"],
    )


def _normalize_chatops_command_source(source: str) -> str:
    normalized = str(source or "").strip().lower()
    if normalized in {"simulation", "external_self_check", "subscription_self_check"}:
        return "simulation"
    if normalized in {"event_subscription", "notification_platform", "app_bot", "webhook_receive"}:
        return "notification_platform"
    if normalized in {"api", "web"}:
        return "web"
    return normalized or "notification_platform"


def _build_chatops_source_context(
    *,
    source: str,
    raw_message: str,
    from_user: str,
    chat_id: str,
    binding_status: str,
) -> dict:
    return {
        "channel": "notification_platform" if source in {"notification_platform", "simulation"} else "generic",
        "source": source,
        "raw_message": _truncate_chatops_text(raw_message, 400),
        "from_user": _truncate_chatops_text(from_user, 120),
        "chat_id": _truncate_chatops_text(chat_id, 120),
        "binding_status": binding_status,
    }


def _format_platform_status_response(payload: dict) -> str:
    summary = payload.get("summary") or {}
    chatops = payload.get("chatops") or {}
    registered = int(summary.get("registered_agents") or 0)
    healthy = int(summary.get("healthy_agents") or 0)
    active = int(summary.get("active_agents") or 0)
    sync_text = (
        "已联通"
        if chatops.get("ready")
        else "平台侧已就绪，待通知平台联调"
        if chatops.get("platform_ready")
        else str(chatops.get("summary") or "未就绪")
    )
    heartbeat_note = "（空闲时为 0 属正常）" if registered and healthy == 0 else ""
    return (
        "📡 军团状态\n"
        f"• 已注册 Agent: {registered}\n"
        f"• 健康心跳: {healthy}/{registered}{heartbeat_note}\n"
        f"• 活跃注册: {active}/{registered}\n"
        f"• 通知平台双向: {sync_text}\n"
        "• 指令: 状态 / 报告 <任务ID> / 测试 <URL/需求> / 绑定 <绑定码>"
    )


def _format_gateway_result_message(command_id: str, payload: dict) -> str:
    result = payload.get("result") or {}
    run = payload.get("run") or {}

    if command_id == "platform.status":
        return _format_platform_status_response(result)

    if command_id == "commander.mission.report":
        summary = (result or {}).get("summary") or {}
        mission_id = str(result.get("mission_id") or "")
        return (
            f"📋 任务 #{mission_id}\n"
            f"• 测试线: {summary.get('total_tests', 0)}\n"
            f"• 通过: {summary.get('completed', 0)}\n"
            f"• 失败: {summary.get('failed', 0)}\n"
            f"• 成功率: {summary.get('success_rate', 0)}%"
        )

    if command_id == "commander.mission.start":
        mission = result.get("mission") or {}
        return (
            f"🐝 已启动蜂群测试任务\n"
            f"• mission_id: {mission.get('mission_id', '-')}\n"
            f"• command_run: {run.get('run_id', '-')}\n"
            f"• 目标: {mission.get('target_url') or '未指定 URL'}\n"
            f"• 需求: {mission.get('user_input') or '-'}"
        )

    if command_id == "commander.mission.cancel":
        mission = result.get("mission") or {}
        return (
            f"🛑 任务已停止\n"
            f"• mission_id: {result.get('mission_id', '-')}\n"
            f"• 当前状态: {mission.get('status') or 'cancelled'}"
        )

    if command_id == "exploration.findings.list":
        findings = list(result.get("findings") or [])
        session_id = str(result.get("session_id") or "")
        if not findings:
            return f"🔎 会话 {session_id} 当前没有发现。"
        top_lines = []
        for item in findings[:3]:
            review_flag = " · 待人工复核" if item.get("requires_human_review") else ""
            top_lines.append(
                f"• [{item.get('severity', 'low')}] {item.get('title') or item.get('finding_type') or '未命名发现'}{review_flag}"
            )
        return (
            f"🔎 会话 {session_id} 共 {len(findings)} 条发现\n"
            + "\n".join(top_lines)
        )

    if command_id == "release.risk.get":
        assessment = result.get("assessment") or {}
        blockers = list(assessment.get("blockers") or [])
        blocker_text = "无" if not blockers else "；".join(
            str(item.get("message") or item.get("title") or item.get("type") or "未知阻断项")
            for item in blockers[:3]
        )
        return (
            f"🧭 发布风险评估 {assessment.get('assessment_id', '-')}\n"
            f"• 业务风险: {assessment.get('business_risk', '-')}\n"
            f"• 体验风险: {assessment.get('ux_risk', '-')}\n"
            f"• 发布风险: {assessment.get('release_risk', '-')}\n"
            f"• 自动发布资格: {'可自动' if assessment.get('auto_release_eligible') else '需人工'}\n"
            f"• Blockers: {blocker_text}"
        )

    return f"✅ 命令 {command_id} 已执行，run_id={run.get('run_id', '-')}"


def _parse_chatops_command(content: str) -> dict:
    text = str(content or "").strip()
    if not text:
        return {"kind": "help"}
    if _CHATOPS_HELP_PATTERN.match(text):
        return {"kind": "help"}

    match = _CHATOPS_BIND_PATTERN.match(text)
    if match:
        return {"kind": "bind", "code": match.group(2)}

    if _CHATOPS_STATUS_PATTERN.match(text):
        return {
            "kind": "command",
            "command_id": "platform.status",
            "arguments": {},
            "public_allowed": True,
        }

    match = _CHATOPS_REPORT_PATTERN.match(text)
    if match:
        return {
            "kind": "command",
            "command_id": "commander.mission.report",
            "arguments": {"mission_id": match.group(2)},
            "public_allowed": False,
        }

    match = _CHATOPS_FINDINGS_PATTERN.match(text)
    if match:
        return {
            "kind": "command",
            "command_id": "exploration.findings.list",
            "arguments": {"session_id": match.group(2)},
            "public_allowed": False,
        }

    match = _CHATOPS_RISK_PATTERN.match(text)
    if match:
        return {
            "kind": "command",
            "command_id": "release.risk.get",
            "arguments": {"assessment_id": match.group(2)},
            "public_allowed": False,
        }

    match = _CHATOPS_STOP_PATTERN.match(text)
    if match:
        return {
            "kind": "command",
            "command_id": "commander.mission.cancel",
            "arguments": {"mission_id": match.group(2)},
            "public_allowed": False,
        }

    match = _CHATOPS_APPROVE_PATTERN.match(text)
    if match:
        return {
            "kind": "approve",
            "run_id": match.group(2),
            "comment": str(match.group(3) or "").strip(),
            "public_allowed": False,
        }

    match = _CHATOPS_REJECT_PATTERN.match(text)
    if match:
        return {
            "kind": "reject",
            "run_id": match.group(2),
            "comment": str(match.group(3) or "").strip(),
            "public_allowed": False,
        }

    if _CHATOPS_EMPTY_TEST_PATTERN.match(text):
        return {
            "kind": "error",
            "response": "请补充要测试的 URL 或测试需求，例如：测试 https://example.com 登录流程",
        }

    urls = re.findall(r'https?://\S+', text)
    target_url = urls[0] if urls else ""
    normalized_input = re.sub(r'^(测试|test)\s+', '', text, flags=re.IGNORECASE)
    user_input = re.sub(r'https?://\S+', '', normalized_input).strip() or normalized_input.strip()
    return {
        "kind": "command",
        "command_id": "commander.mission.start",
        "arguments": {
            "user_input": user_input,
            "target_url": target_url,
            "parallel": True,
        },
        "public_allowed": False,
    }


async def _handle_commander_chat_message(
    content: str,
    from_user: str = "",
    chat_id: str = "",
    source: str = "event_subscription",
) -> dict:
    text = str(content or "").strip()
    logger.info(f"[Webhook] 收到消息: {text} (from: {from_user}, source: {source})")

    parsed = _parse_chatops_command(text)
    if parsed["kind"] == "help":
        return {"response": _build_chatops_help_response(), "binding_status": "help"}
    if parsed["kind"] == "error":
        return {"response": parsed["response"], "binding_status": "invalid"}

    binding_service = get_commander_chatops_binding_service()
    normalized_source = _normalize_chatops_command_source(source)

    if parsed["kind"] == "bind":
        try:
            binding = binding_service.bind_open_id(
                code=str(parsed["code"] or ""),
                notification_platform_open_id=from_user,
                chat_id=chat_id,
                source=normalized_source,
            )
        except ChatOpsBindingValidationError as exc:
            return {
                "response": f"❌ {exc}",
                "binding_status": "unbound",
            }
        return {
            "response": (
                f"🔗 绑定成功\n"
                f"• 平台账号: {binding.get('username', '-')}\n"
                f"• 通知平台身份: {binding.get('notification_platform_open_id', '-')}"
            ),
            "binding_status": "bound",
            "requester_id": binding.get("user_id", ""),
            "binding": binding,
        }

    bound_user = binding_service.resolve_bound_user(from_user)
    binding_status = "bound" if bound_user else "unbound"
    if not bound_user and not parsed.get("public_allowed"):
        return {
            "response": "🔐 当前通知平台身份尚未绑定平台账号，请先在 Legion 控制中心生成绑定码，并发送：绑定 <绑定码>",
            "binding_status": "unbound",
        }

    gateway = get_commander_command_gateway()
    acting_user = bound_user or _build_public_chatops_user()
    source_context = _build_chatops_source_context(
        source=normalized_source,
        raw_message=text,
        from_user=from_user,
        chat_id=chat_id,
        binding_status=binding_status,
    )

    try:
        if parsed["kind"] == "approve":
            payload = await gateway.approve_command_run(
                parsed["run_id"],
                user=acting_user,
                comment=str(parsed.get("comment") or "通知平台批准执行"),
                confirm=True,
                source=normalized_source,
            )
            response = (
                f"✅ 已批准命令 {parsed['run_id']}\n"
                f"• 当前状态: {payload.get('run', {}).get('status', '-')}\n"
                f"• 审批状态: {payload.get('approval', {}).get('status', '-')}"
            )
            return {
                "response": response,
                "run": payload.get("run"),
                "approval": payload.get("approval"),
                "binding_status": binding_status,
                "requester_id": getattr(acting_user, "user_id", ""),
                "command_id": str((payload.get("run") or {}).get("command_id") or ""),
            }

        if parsed["kind"] == "reject":
            payload = gateway.reject_command_run(
                parsed["run_id"],
                user=acting_user,
                reason=str(parsed.get("comment") or "通知平台驳回"),
                source=normalized_source,
            )
            response = (
                f"🛑 已驳回命令 {parsed['run_id']}\n"
                f"• 当前状态: {payload.get('run', {}).get('status', '-')}\n"
                f"• 审批状态: {payload.get('approval', {}).get('status', '-')}"
            )
            return {
                "response": response,
                "run": payload.get("run"),
                "approval": payload.get("approval"),
                "binding_status": binding_status,
                "requester_id": getattr(acting_user, "user_id", ""),
                "command_id": str((payload.get("run") or {}).get("command_id") or ""),
            }

        payload = await gateway.execute_command(
            parsed["command_id"],
            parsed.get("arguments") or {},
            user=acting_user,
            confirm=True,
            source=normalized_source,
            source_context=source_context,
        )
        response = _format_gateway_result_message(parsed["command_id"], payload)
        return {
            "response": response,
            "run": payload.get("run"),
            "approval": payload.get("approval"),
            "result": payload.get("result"),
            "binding_status": binding_status,
            "requester_id": getattr(acting_user, "user_id", ""),
            "command_id": parsed["command_id"],
        }
    except CommandPermissionError as exc:
        return {
            "response": f"⛔ {exc}",
            "binding_status": binding_status,
            "requester_id": getattr(acting_user, "user_id", ""),
            "command_id": parsed.get("command_id", ""),
        }
    except (CommandValidationError, CommandApprovalError, CommandGatewayError) as exc:
        return {
            "response": f"⚠️ {exc}",
            "binding_status": binding_status,
            "requester_id": getattr(acting_user, "user_id", ""),
            "command_id": parsed.get("command_id", ""),
        }


async def _deliver_commander_response_to_notification_platform(message: str) -> dict:
    from core.db_helper import query_all
    from routers.notification import _format_message

    rows = query_all(
        """
        SELECT *
        FROM notification_webhooks
        WHERE enabled=1 AND type='notification_platform'
        ORDER BY last_test_success DESC, created_at DESC
        """
    )
    if not rows:
        return {
            "configured": 0,
            "delivered": 0,
            "failed": 0,
            "sender": "webhook",
            "mode": "webhook_only",
            "message": "未配置启用中的通知平台 Webhook，无法回发群消息。",
        }

    payload = _format_message(
        "notification_platform",
        "军团中心",
        "completed",
        message,
    )
    delivered = 0
    failures: list[dict] = []
    async with httpx.AsyncClient(timeout=10) as client:
        for row in rows[:1]:
            try:
                resp = await client.post(row["url"], json=payload)
                if resp.status_code < 300:
                    delivered += 1
                else:
                    failures.append({
                        "id": row["id"],
                        "name": row["name"],
                        "status_code": resp.status_code,
                    })
            except Exception as exc:
                failures.append({
                    "id": row["id"],
                    "name": row["name"],
                    "error": str(exc),
                })
    return {
        "configured": len(rows),
        "delivered": delivered,
        "failed": len(failures),
        "failures": failures,
        "sender": "webhook",
        "mode": "webhook_only",
        "message": "通知平台 Webhook 已回发消息。" if delivered > 0 else "通知平台 Webhook 回发失败。",
    }


async def _get_notification_platform_tenant_access_token() -> dict:
    app_id = str(Config.NOTIFICATION_PLATFORM_APP_ID or os.getenv("NOTIFICATION_PLATFORM_APP_ID", "")).strip()
    app_secret = str(Config.NOTIFICATION_PLATFORM_APP_SECRET or os.getenv("NOTIFICATION_PLATFORM_APP_SECRET", "")).strip()
    app_id_masked = f"{app_id[:3]}...{app_id[-3:]}" if len(app_id) > 6 else ("*" * len(app_id) if app_id else "")
    if not app_id or not app_secret:
        return {
            "ok": False,
            "message": "未配置通知平台应用机器人 App ID / Secret。",
            "app_bot_configured": False,
            "app_id_masked": app_id_masked,
        }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=8.0)) as client:
            response = await client.post(
                "https://open.notification_platform.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret},
            )
        body = response.json() if response.content else {}
    except Exception as exc:
        return {
            "ok": False,
            "message": f"获取通知平台 tenant_access_token 失败：{exc}",
            "app_bot_configured": True,
            "app_id_masked": app_id_masked,
        }

    code = body.get("code", -1)
    normalized_code = -1 if code is None else int(code)
    if response.status_code >= 300 or normalized_code != 0:
        return {
            "ok": False,
            "message": str(body.get("msg") or body.get("message") or f"HTTP {response.status_code}"),
            "app_bot_configured": True,
            "status_code": response.status_code,
            "app_id_masked": app_id_masked,
        }

    token = str(body.get("tenant_access_token") or "").strip()
    if not token:
        return {
            "ok": False,
            "message": "通知平台未返回 tenant_access_token。",
            "app_bot_configured": True,
            "status_code": response.status_code,
            "app_id_masked": app_id_masked,
        }
    return {
        "ok": True,
        "token": token,
        "app_bot_configured": True,
        "message": "应用机器人凭据校验通过，已成功获取 tenant_access_token。",
        "status_code": response.status_code,
        "app_id_masked": app_id_masked,
    }


async def _deliver_commander_response_via_notification_platform_app_bot(message: str, chat_id: str) -> dict:
    normalized_chat_id = str(chat_id or "").strip()
    if not normalized_chat_id:
        return {
            "configured": 0,
            "delivered": 0,
            "failed": 1,
            "sender": "app_bot",
            "mode": "app_bot",
            "message": "缺少 chat_id，无法通过通知平台应用机器人回发。",
            "failures": [{"error": "missing_chat_id"}],
        }

    token_result = await _get_notification_platform_tenant_access_token()
    if not bool(token_result.get("ok")):
        return {
            "configured": 1 if token_result.get("app_bot_configured") else 0,
            "delivered": 0,
            "failed": 1,
            "sender": "app_bot",
            "mode": "app_bot",
            "message": str(token_result.get("message") or "获取通知平台应用机器人凭据失败"),
            "failures": [{"error": str(token_result.get("message") or "token_error")}],
        }

    payload = {
        "receive_id": normalized_chat_id,
        "msg_type": "text",
        "content": json.dumps({"text": str(message or "")}, ensure_ascii=False),
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=8.0)) as client:
            response = await client.post(
                "https://open.notification_platform.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
                headers={
                    "Authorization": f"Bearer {token_result['token']}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                json=payload,
            )
        body = response.json() if response.content else {}
    except Exception as exc:
        return {
            "configured": 1,
            "delivered": 0,
            "failed": 1,
            "sender": "app_bot",
            "mode": "app_bot",
            "message": f"通知平台应用机器人回发失败：{exc}",
            "failures": [{"error": str(exc)}],
        }

    code = body.get("code", -1)
    normalized_code = -1 if code is None else int(code)
    if response.status_code >= 300 or normalized_code != 0:
        return {
            "configured": 1,
            "delivered": 0,
            "failed": 1,
            "sender": "app_bot",
            "mode": "app_bot",
            "message": str(body.get("msg") or body.get("message") or f"HTTP {response.status_code}"),
            "failures": [{
                "status_code": response.status_code,
                "error": str(body.get("msg") or body.get("message") or "send_failed"),
            }],
        }

    return {
        "configured": 1,
        "delivered": 1,
        "failed": 0,
        "sender": "app_bot",
        "mode": "app_bot",
        "message": "通知平台应用机器人已回发消息。",
        "failures": [],
        "message_id": (body.get("data") or {}).get("message_id", ""),
    }


async def _deliver_commander_response(message: str, chat_id: str = "") -> dict:
    if str(chat_id or "").strip():
        app_bot_result = await _deliver_commander_response_via_notification_platform_app_bot(message, chat_id)
        if int(app_bot_result.get("delivered") or 0) > 0:
            return {
                **app_bot_result,
                "primary": "app_bot",
                "fallback_used": False,
            }
        webhook_result = await _deliver_commander_response_to_notification_platform(message)
        return {
            **webhook_result,
            "configured": int(app_bot_result.get("configured") or 0) + int(webhook_result.get("configured") or 0),
            "primary": "app_bot",
            "sender": str(webhook_result.get("sender") or "webhook"),
            "mode": "app_bot_fallback_webhook",
            "fallback_used": True,
            "app_bot_delivery": app_bot_result,
        }
    webhook_result = await _deliver_commander_response_to_notification_platform(message)
    return {
        **webhook_result,
        "primary": "webhook",
        "fallback_used": False,
    }


@router.post("/webhook/receive")
async def webhook_receive(msg: WebhookMessage):
    """
    📨 企微/钉钉双向交互 — 指令接收端点

    配置企微/钉钉机器人的「接收消息 URL」指向此端点。
    收到 @机器人 消息后自动触发 Commander 执行。

    支持指令格式：
    - "测试 https://xxx.com"  → 启动蜂群测试
    - "状态"                  → 返回军团健康状态
    - "报告 {mission_id}"     → 返回指定任务报告
    """
    result = await _handle_commander_chat_message(
        msg.content,
        from_user=msg.from_user,
        chat_id=msg.chat_id,
        source="webhook_receive",
    )
    _record_chatops_event(
        channel="generic",
        source="webhook_receive",
        event_type="message",
        message=msg.content,
        from_user=msg.from_user,
        chat_id=msg.chat_id,
        response=result.get("response", ""),
        status="ok",
        delivery={"configured": 0, "delivered": 0, "failed": 0},
        run_id=str((result.get("run") or {}).get("run_id") or ""),
        command_id=str(result.get("command_id") or ""),
        requester_id=str(result.get("requester_id") or ""),
        binding_status=str(result.get("binding_status") or ""),
    )
    return result


async def _process_notification_platform_event(payload: dict, source: str = "event_subscription"):
    """统一处理通知平台事件订阅 payload，支持真实回调和平台侧自检复用。"""
    if payload.get("type") == "url_verification":
        expected_token = (Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN or os.getenv("NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "")).strip()
        actual_token = str(payload.get("token") or "").strip()
        if expected_token and actual_token != expected_token:
            _record_chatops_event(
                channel="notification_platform",
                source=source,
                event_type="url_verification",
                message="url_verification",
                from_user="",
                chat_id="",
                response="verification token mismatch",
                status="forbidden",
                delivery={"configured": 0, "delivered": 0, "failed": 0},
            )
            return {"code": 403, "msg": "verification token mismatch"}
        _record_chatops_event(
            channel="notification_platform",
            source=source,
            event_type="url_verification",
            message="url_verification",
            from_user="",
            chat_id="",
            response="challenge accepted",
            status="verified",
            delivery={"configured": 0, "delivered": 0, "failed": 0},
        )
        return {"challenge": payload.get("challenge", "")}

    header = payload.get("header") or {}
    if header.get("event_type") != "im.message.receive_v1":
        _record_chatops_event(
            channel="notification_platform",
            source=source,
            event_type=header.get("event_type") or "unsupported_event",
            message="unsupported_event",
            from_user="",
            chat_id="",
            response=header.get("event_type") or "unsupported_event",
            status="ignored",
            delivery={"configured": 0, "delivered": 0, "failed": 0},
        )
        return {
            "status": "ignored",
            "reason": header.get("event_type") or "unsupported_event",
        }

    event = payload.get("event") or {}
    message = event.get("message") or {}
    if message.get("message_type") != "text":
        _record_chatops_event(
            channel="notification_platform",
            source=source,
            event_type="message",
            message=f"[{message.get('message_type')}]",
            from_user="",
            chat_id=str(message.get("chat_id") or ""),
            response="unsupported_message_type",
            status="ignored",
            delivery={"configured": 0, "delivered": 0, "failed": 0},
        )
        return {
            "status": "ignored",
            "reason": "unsupported_message_type",
            "message_type": message.get("message_type"),
        }

    text = _extract_notification_platform_text_content(payload)
    if not str(text or "").strip():
        _record_chatops_event(
            channel="notification_platform",
            source=source,
            event_type="message",
            message="[empty]",
            from_user="",
            chat_id=str(message.get("chat_id") or ""),
            response="empty_message",
            status="ignored",
            delivery={"configured": 0, "delivered": 0, "failed": 0},
        )
        return {
            "status": "ignored",
            "reason": "empty_message",
        }
    sender_identity = _extract_notification_platform_sender_identity(payload)
    from_user = str(
        sender_identity.get("open_id")
        or sender_identity.get("user_id")
        or sender_identity.get("union_id")
        or sender_identity.get("sender_type")
        or ""
    )
    chat_id = str(message.get("chat_id") or "")

    result = await _handle_commander_chat_message(
        text,
        from_user=from_user,
        chat_id=chat_id,
        source=source,
    )
    delivery = await _deliver_commander_response(result.get("response", ""), chat_id=chat_id)
    get_commander_chatops_binding_service().touch_binding(from_user, chat_id=chat_id)
    _upsert_chat_binding(
        channel="notification_platform",
        source=source,
        chat_id=chat_id,
        from_user=from_user,
        message=text,
        reply_mode=str(delivery.get("mode") or ""),
        delivery_ok=int(delivery.get("delivered") or 0) > 0,
        run_id=str((result.get("run") or {}).get("run_id") or ""),
        command_id=str(result.get("command_id") or ""),
        requester_id=str(result.get("requester_id") or ""),
        binding_status=str(result.get("binding_status") or ""),
    )
    _record_chatops_event(
        channel="notification_platform",
        source=source,
        event_type="message",
        message=text,
        from_user=from_user,
        chat_id=chat_id,
        response=result.get("response", ""),
        status="ok",
        delivery=delivery,
        run_id=str((result.get("run") or {}).get("run_id") or ""),
        command_id=str(result.get("command_id") or ""),
        requester_id=str(result.get("requester_id") or ""),
        binding_status=str(result.get("binding_status") or ""),
    )
    return {
        "status": "ok",
        "message": text,
        "result": result,
        "delivery": delivery,
    }


@router.post("/notification_platform/events")
async def notification_platform_event_receive(payload: dict = Body(...)):
    """
    🪽 通知平台事件订阅入口

    用于接收通知平台应用机器人的消息事件。
    注意：这不是自定义 Webhook 机器人本身的能力，仍需在通知平台开发者后台
    配置事件订阅 URL 指向此端点。
    """
    return await _process_notification_platform_event(
        payload,
        source=_detect_notification_platform_event_source(payload, default_source="event_subscription"),
    )


@router.get("/chatops/overview")
async def commander_chatops_overview():
    """返回通知平台 ChatOps 当前接入状态与最近消息摘要。"""
    return {
        "status": "success",
        "overview": _get_chatops_overview(allow_live_probe=True),
    }


@router.post("/chatops/probe-refresh")
async def commander_chatops_probe_refresh():
    """立即强制重试一次公网回调回探，并返回最新概览。"""
    service = get_commander_chatops_service()
    result = service.refresh_callback_probe()
    return {
        "status": "success",
        "probe": result.get("probe", {}),
        "overview": result.get("overview", {}),
    }


@router.post("/chatops/local-tunnel/restart")
async def commander_chatops_local_tunnel_restart():
    """重启本机 OpenSSH 反向隧道，用于恢复公网回调链路。"""
    service = get_commander_chatops_service()
    result = service.restart_local_tunnel()
    return {
        "status": "success" if bool(result.get("ok")) else "error",
        "ok": bool(result.get("ok")),
        "message": str(result.get("message") or ""),
        "stdout": str(result.get("stdout") or ""),
        "stderr": str(result.get("stderr") or ""),
        "tunnel": result.get("tunnel", {}),
        "overview": result.get("overview", {}),
    }


@router.post("/chatops/config/token")
async def commander_chatops_config_token(req: CommanderChatOpsTokenConfigRequest):
    """配置或重新生成通知平台事件订阅 verification token。"""
    provided = str(req.verification_token or "").strip()
    if req.regenerate or not provided:
        provided = secrets.token_urlsafe(24)
    config_result = Config.set_notification_platform_event_verification_token(provided)
    overview = _get_chatops_overview()
    return {
        "status": "success",
        "token": provided,
        "token_masked": overview.get("verification_token_masked", ""),
        "verification_token_updated_at": config_result.get("verification_token_updated_at", ""),
        "overview": overview,
    }


@router.post("/chatops/config/callback-url")
async def commander_chatops_config_callback_url(req: CommanderChatOpsCallbackConfigRequest):
    """配置通知平台事件订阅使用的公网回调基地址。"""
    raw = str(req.public_api_base_url or "").strip()
    normalized = raw.rstrip("/")
    if normalized:
        parsed = urlsplit(normalized)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return {
                "status": "error",
                "message": "PUBLIC_API_BASE_URL 必须是完整的 http(s) 地址",
                "overview": _get_chatops_overview(),
            }
    updated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    Config.update_runtime_env({
        "PUBLIC_API_BASE_URL": normalized,
        "PUBLIC_API_BASE_URL_UPDATED_AT": updated_at,
    })
    overview = _get_chatops_overview()
    return {
        "status": "success",
        "public_api_base_url": normalized,
        "public_api_base_url_updated_at": updated_at,
        "callback_url": overview.get("callback_url", ""),
        "callback_url_public": bool(overview.get("callback_url_public")),
        "overview": overview,
    }


@router.post("/chatops/config/app-bot")
async def commander_chatops_config_app_bot(req: CommanderChatOpsAppBotConfigRequest):
    """配置通知平台应用机器人凭据，用于判断真实群聊双向链路是否已具备接入条件。"""
    app_id = str(req.app_id or "").strip()
    app_secret = str(req.app_secret or "").strip()
    config_result = Config.set_notification_platform_app_bot_credentials(app_id, app_secret)
    validation = await _get_notification_platform_tenant_access_token()
    _record_app_bot_check(validation, source="config_save")
    overview = _get_chatops_overview()
    return {
        "status": "success",
        "app_bot_configured": config_result.get("app_bot_configured", False),
        "app_bot_updated_at": config_result.get("app_bot_updated_at", ""),
        "app_id_masked": overview.get("app_bot_id_masked", ""),
        "validation": {
            "ok": bool(validation.get("ok")),
            "message": str(validation.get("message") or ""),
            "status_code": validation.get("status_code"),
            "app_id_masked": str(validation.get("app_id_masked") or ""),
        },
        "overview": overview,
    }


@router.post("/chatops/config/app-bot/unbind")
async def commander_chatops_unbind_app_bot(req: CommanderChatOpsAppBotUnbindRequest):
    """解绑当前项目串用的通知平台应用机器人，并可选清理校验/联调痕迹。"""
    config_result = Config.set_notification_platform_app_bot_credentials("", "")
    purge_result = _purge_app_bot_state(bool(req.purge_history))
    overview = _get_chatops_overview()
    return {
        "status": "success",
        "message": "当前项目已解绑通知平台应用机器人，现仅保留 Webhook 通知通道。",
        "app_bot_configured": config_result.get("app_bot_configured", False),
        "app_bot_updated_at": config_result.get("app_bot_updated_at", ""),
        "purged": purge_result,
        "overview": overview,
    }


@router.post("/chatops/app-bot-self-check")
async def commander_chatops_app_bot_self_check():
    """立即验证当前通知平台应用机器人凭据是否能成功获取 tenant_access_token。"""
    validation = await _get_notification_platform_tenant_access_token()
    _record_app_bot_check(validation, source="manual_self_check")
    return {
        "status": "success" if bool(validation.get("ok")) else "error",
        "validation": {
            "ok": bool(validation.get("ok")),
            "message": str(validation.get("message") or ""),
            "status_code": validation.get("status_code"),
            "app_id_masked": str(validation.get("app_id_masked") or ""),
        },
        "overview": _get_chatops_overview(),
    }


@router.post("/chatops/subscription-self-check")
async def commander_chatops_subscription_self_check(req: CommanderChatOpsSubscriptionSelfCheckRequest):
    """在平台内模拟一次通知平台 challenge 校验，确认事件订阅入口已可用。"""
    token = (Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN or os.getenv("NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "")).strip()
    if not token:
        return {
            "status": "error",
            "message": "尚未配置 NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN",
            "overview": _get_chatops_overview(),
        }
    payload = {
        "type": "url_verification",
        "challenge": req.challenge or "codex-self-check",
        "token": token,
    }
    result = await _process_notification_platform_event(payload, source="subscription_self_check")
    return {
        "status": "success",
        "result": result,
        "overview": _get_chatops_overview(),
    }


@router.post("/chatops/external-self-check")
async def commander_chatops_external_self_check():
    """通过当前公网回调地址执行一次 challenge + 文本消息双验证。"""
    overview = _get_chatops_overview()
    callback_url = str(overview.get("callback_url") or "").strip()
    token = (Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN or os.getenv("NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "")).strip()

    if not callback_url or not bool(overview.get("callback_url_public")):
        return {
            "status": "error",
            "message": "当前还没有可用的公网回调地址，请先保存一个公网基地址。",
            "overview": overview,
        }

    if not token:
        return {
            "status": "error",
            "message": "尚未配置 NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN，无法执行外部 challenge 校验。",
            "overview": overview,
        }

    challenge = f"external-self-check-{secrets.token_hex(4)}"
    event_id = f"evt_external_self_check_{secrets.token_hex(6)}"
    now_ms = str(int(datetime.utcnow().timestamp() * 1000))

    async def _post_payload(label: str, payload: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=True) as client:
                response = await client.post(callback_url, json=payload)
            body_text = response.text or ""
            try:
                body = response.json()
            except Exception:
                body = body_text

            result = {
                "label": label,
                "ok": bool(response.is_success),
                "status_code": response.status_code,
                "body_excerpt": _truncate_chatops_text(
                    json.dumps(body, ensure_ascii=False) if isinstance(body, dict) else str(body),
                    1200,
                ),
            }
            if label == "challenge":
                result["challenge_matched"] = bool(isinstance(body, dict) and str(body.get("challenge") or "") == challenge)
            if label == "message":
                if isinstance(body, dict):
                    response_text = ""
                    command_result = body.get("result") or {}
                    if isinstance(command_result, dict):
                        response_text = str(command_result.get("response") or "")
                    result["command_response"] = _truncate_chatops_text(response_text, 600)
                    result["delivery"] = body.get("delivery") or {}
            return result
        except Exception as exc:
            return {
                "label": label,
                "ok": False,
                "status_code": 0,
                "error": str(exc),
            }

    challenge_payload = {
        "type": "url_verification",
        "challenge": challenge,
        "token": token,
    }
    message_payload = {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
            "event_id": event_id,
            "create_time": now_ms,
            "token": "external-self-check",
            "app_id": "external-self-check",
            "tenant_key": "external-self-check",
        },
        "event": {
            "sender": {
                "sender_id": {
                    "union_id": "external-self-check",
                    "user_id": "external-self-check",
                    "open_id": "ou_external_self_check",
                },
                "sender_type": "user",
                "tenant_key": "external-self-check",
            },
            "message": {
                "message_id": f"om_{event_id}",
                "root_id": None,
                "parent_id": None,
                "create_time": now_ms,
                "update_time": now_ms,
                "chat_id": "oc_external_self_check",
                "thread_id": None,
                "chat_type": "group",
                "message_type": "text",
                "content": json.dumps({"text": "status"}, ensure_ascii=False),
                "mentions": [],
            },
        },
    }

    challenge_check = await _post_payload("challenge", challenge_payload)
    message_check = await _post_payload("message", message_payload)
    refreshed_overview = _get_chatops_overview()
    success = bool(challenge_check.get("ok")) and bool(challenge_check.get("challenge_matched")) and bool(message_check.get("ok"))

    return {
        "status": "success" if success else "warning",
        "callback_url": callback_url,
        "challenge": challenge,
        "challenge_check": challenge_check,
        "message_check": message_check,
        "overview": refreshed_overview,
    }


@router.post("/chatops/simulate")
async def commander_chatops_simulate(req: CommanderChatOpsSimulateRequest):
    """模拟一条通知平台文本指令，便于平台侧自检双向链路。"""
    result = await _handle_commander_chat_message(
        req.message,
        from_user=req.from_user,
        chat_id=req.chat_id,
        source="simulation",
    )
    delivery = {"configured": 0, "delivered": 0, "failed": 0, "message": "未触发回推"}
    if req.deliver:
        delivery = await _deliver_commander_response(result.get("response", ""), chat_id=req.chat_id)

    status = "ok"
    if req.deliver and int(delivery.get("delivered") or 0) <= 0:
        status = "warning"

    _record_chatops_event(
        channel="notification_platform",
        source="simulation",
        event_type="message",
        message=req.message,
        from_user=req.from_user,
        chat_id=req.chat_id,
        response=result.get("response", ""),
        status=status,
        delivery=delivery,
        run_id=str((result.get("run") or {}).get("run_id") or ""),
        command_id=str(result.get("command_id") or ""),
        requester_id=str(result.get("requester_id") or ""),
        binding_status=str(result.get("binding_status") or ""),
    )
    return {
        "status": "success",
        "result": result,
        "delivery": delivery,
        "overview": _get_chatops_overview(),
    }


@router.get("/scheduler/crons")
async def list_cron_jobs():
    """⏰ 获取定时巡检任务列表"""
    from core.test_scheduler import get_scheduler

    scheduler = get_scheduler()
    return {
        "cron_jobs": scheduler.get_cron_jobs(),
        "statistics": scheduler.get_statistics(),
    }

