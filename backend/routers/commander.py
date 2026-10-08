# -*- coding: utf-8 -*-
"""
Commander API routes

REST API for Commander:
- POST /api/commander/run       Start comprehensive testing with one instruction
- GET  /api/commander/status    Get mission status
- POST /api/commander/cancel    Cancel a mission
- GET  /api/commander/missions  Mission history list
- GET  /api/commander/stream    SSE progress stream
- POST /api/commander/architect Test architect analysis
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

router = APIRouter(prefix="/api/commander", tags=["Commander"])


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


# ── Request models ─────────────────────────────────────────────────────────────────


from pydantic import BaseModel, Field


class CommanderRunRequest(BaseModel):
    """Commander run request"""
    user_input: str = Field(..., description="Natural-language test requirements")
    target_url: str = Field("", description="Target URL (optional)")
    parallel: bool = Field(True, description="Whether to execute test tracks in parallel")


class PrototypeWorkerSwitches(BaseModel):
    visual: bool = Field(True, description="Whether to enable Visual Worker")
    flow: bool = Field(True, description="Whether to enable Flow Worker")
    ab: bool = Field(True, description="Whether to enable A/B Worker")
    a11y: bool = Field(True, description="Whether to enable A11y Worker")
    perf: bool = Field(True, description="Whether to enable Perf Worker")


class PrototypeProviders(BaseModel):
    visual: Optional[str] = Field(None, description="Visual Worker Provider")
    flow: Optional[str] = Field(None, description="Flow Worker Provider")
    ab: Optional[str] = Field(None, description="A/B Worker Provider")
    a11y: Optional[str] = Field(None, description="A11y Worker Provider")
    perf: Optional[str] = Field(None, description="Perf Worker Provider")


class PrototypeRunRequest(BaseModel):
    source_type: str = Field(..., description="Source type: url | file | directory")
    source: str = Field(..., description="Prototype URL / file path / directory path")
    compare_source: str = Field("", description="Optional A/B comparison source")
    playbook_id: str = Field("", description="Optional playbook ID")
    worker_switches: PrototypeWorkerSwitches = Field(default_factory=PrototypeWorkerSwitches)
    providers: PrototypeProviders = Field(default_factory=PrototypeProviders)
    wcag_level: str = Field("AA", description="A11y target level")


class UnifiedTaskRequest(BaseModel):
    """Unified task entry request"""
    task_kind: Literal["general", "prototype", "exploration"] = Field(..., description="Task type")
    user_goal: str = Field(..., description="User goal/task intent")
    source_context: Dict[str, Any] = Field(default_factory=dict, description="Input context")
    strategy: Dict[str, Any] = Field(default_factory=dict, description="Execution strategy")


class UnifiedTaskActionResponse(BaseModel):
    task_id: str
    cancelled: bool = Field(False, description="Whether it has stopped")
    status: str = Field(..., description="Current task status")
    message: str = Field(..., description="Action feedback")


class ArchitectRequest(BaseModel):
    """TestArchitect analysis request"""
    input_text: str = Field("", description="Requirement description/PRD")
    target_url: str = Field("", description="Target URL")
    mode: Optional[str] = Field(None, description="Discovery mode: requirement/change/exploration/coverage/fault")
    diff_text: str = Field("", description="Git diff text (change-driven)")


class CancelRequest(BaseModel):
    """Cancellation request"""
    mission_id: str = Field(..., description="Mission ID")


class CommanderCommandExecuteRequest(BaseModel):
    """Unified command gateway execution request"""
    command_id: str = Field(..., description="Command ID")
    arguments: dict = Field(default_factory=dict, description="Command arguments")
    confirm: bool = Field(False, description="Explicit confirmation for high-risk commands")


class CommanderCommandApprovalDecisionRequest(BaseModel):
    """Unified command approval decision request"""
    comment: str = Field("", description="Approval comment/rejection reason")
    confirm: bool = Field(True, description="Explicit confirmation when approving execution")


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
                yield f"data: {json.dumps({'level': 'end', 'message': 'Mission ended'}, ensure_ascii=False)}\n\n"
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


# ── API endpoints ─────────────────────────────────────────────────────────────────


@router.post("/run")
async def commander_run(req: CommanderRunRequest):
    """
    🚀 Start comprehensive testing with one instruction (nonblocking)

    Return mission_id immediately and execute the mission in the background.
    The frontend tracks progress in real time through GET /stream/{mission_id}.
    """
    from agents.commander import get_commander

    commander = get_commander()
    
    # Create the mission record first to obtain mission_id
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
    
    # Execute the mission in the background
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
                    "message": f"❌ Mission error: {e}",
                    "data": {},
                })
            elif mission_obj is not None:
                from agents.commander import MissionStatus

                mission_obj.status = MissionStatus.FAILED
                mission_obj.log(f"❌ Mission error: {e}", level="error")
    
    asyncio.create_task(_run_in_background())
    
    return mission


@router.post("/prototype/run")
async def commander_prototype_run(req: PrototypeRunRequest):
    """Start the seven-agent prototype testing orchestration flow."""
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
                        "message": f"❌ Prototype task error: {exc}",
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
    """Unified task entry point."""
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
    task_kind: str = Query("", description="Optional task type filter"),
    status: str = Query("", description="Optional status filter"),
    lineage_root_id: str = Query("", description="Optional rerun lineage root task filter"),
):
    """List unified tasks."""
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
    """Get unified task details."""
    from agents.commander import get_commander

    commander = get_commander()
    service = get_unified_task_service()
    task = service.get_task(commander=commander, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Unified task not found")
    return task


@router.get("/tasks/{task_id}/result")
async def commander_get_unified_task_result(task_id: str):
    """Get unified task results."""
    from agents.commander import get_commander

    commander = get_commander()
    service = get_unified_task_service()
    task = service.get_task_result(commander=commander, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Unified task not found")
    return task


@router.post("/tasks/{task_id}/cancel", response_model=UnifiedTaskActionResponse)
async def commander_cancel_unified_task(task_id: str):
    """Stop a unified task."""
    from agents.commander import get_commander

    commander = get_commander()
    service = get_unified_task_service()
    try:
        return service.cancel_task(commander=commander, task_id=task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unified task not found") from exc


@router.post("/tasks/{task_id}/rerun")
async def commander_rerun_unified_task(task_id: str):
    """Rerun a unified task with the original task context."""
    from agents.commander import get_commander

    commander = get_commander()
    service = get_unified_task_service()
    try:
        return service.rerun_task(commander=commander, task_id=task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unified task not found") from exc


@router.get("/tasks/{task_id}/stream")
async def commander_stream_unified_task(task_id: str):
    """Stream unified task logs over SSE."""
    from agents.commander import get_commander

    commander = get_commander()
    service = get_unified_task_service()
    task = service.get_task(commander=commander, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Unified task not found")
    return _build_streaming_response(commander, task_id)


@router.get("/status/{mission_id}")
async def commander_status(mission_id: str):
    """Get mission status"""
    from agents.commander import get_commander

    commander = get_commander()
    mission = commander.get_mission(mission_id)
    if mission is None:
        return {"error": "Mission not found", "mission_id": mission_id}
    return mission


@router.get("/prototype/status/{mission_id}")
async def commander_prototype_status(mission_id: str):
    """Get prototype testing task status."""
    from agents.commander import get_commander

    commander = get_commander()
    mission = commander.get_mission(mission_id)
    if mission is None or mission.get("mission_kind") != "prototype_agents":
        return {"error": "Prototype mission not found", "mission_id": mission_id}
    return mission


@router.post("/cancel")
async def commander_cancel(req: CancelRequest):
    """Cancel a mission"""
    from agents.commander import get_commander

    commander = get_commander()
    success = commander.cancel_mission(req.mission_id)
    return {
        "mission_id": req.mission_id,
        "cancelled": success,
    }


@router.get("/missions")
async def commander_missions(limit: int = Query(20, ge=1, le=100)):
    """Get recent missions"""
    from agents.commander import get_commander

    commander = get_commander()
    return commander.list_missions(limit=limit)


@router.get("/prototype/missions")
async def commander_prototype_missions(limit: int = Query(20, ge=1, le=100)):
    """Get recent prototype testing tasks."""
    from agents.commander import get_commander

    commander = get_commander()
    return get_prototype_agents_service().list_missions(commander, limit=limit)


@router.delete("/missions/{mission_id}")
async def delete_mission(mission_id: str):
    """Delete one mission record"""
    from agents.commander import get_commander

    commander = get_commander()
    if mission_id in commander._missions:
        del commander._missions[mission_id]
        return {"deleted": True, "mission_id": mission_id}
    return {"deleted": False, "error": "Mission not found"}


@router.delete("/missions")
async def clear_all_missions():
    """Clear all mission records"""
    from agents.commander import get_commander

    commander = get_commander()
    count = len(commander._missions)
    commander._missions.clear()
    return {"cleared": True, "count": count}


@router.get("/stream/{mission_id}")
async def commander_stream(mission_id: str):
    """
    Stream mission progress logs over SSE

    The frontend receives real-time logs after connecting to this endpoint.
    """
    from agents.commander import get_commander

    commander = get_commander()

    return _build_streaming_response(commander, mission_id)


@router.get("/prototype/stream/{mission_id}")
async def commander_prototype_stream(mission_id: str):
    """Stream prototype testing task logs over SSE."""
    from agents.commander import get_commander

    commander = get_commander()
    mission = commander.get_mission(mission_id)
    if mission is None or mission.get("mission_kind") != "prototype_agents":
        raise HTTPException(status_code=404, detail="Prototype mission not found")
    return _build_streaming_response(commander, mission_id)


@router.post("/architect")
async def architect_analyze(req: ArchitectRequest):
    """
    🧠 Test architect analysis

    Input requirements/URL/diff → automatically discover testing needs
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
    """List all agents registered on AgentBus"""
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
    """List command definitions available in the unified command gateway."""
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
    """Execute a controlled command through the unified command gateway."""
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
    status: str = Query("", description="Run status filter"),
    approval_status: str = Query("", description="Approval status filter"),
    command_id: str = Query("", description="Command ID filter"),
    project_key: str = Query("", description="Project filter"),
    source: str = Query("", description="Source filter"),
    limit: int = Query(20, ge=1, le=200),
    user=Depends(require_authenticated_user),
):
    """List unified command run records."""
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
    """Get details of one unified command run."""
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
    """Approve and execute a pending command."""
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
    """Reject a pending command."""
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
    """Get the signed-in user's notification platform binding status and latest binding code."""
    service = get_commander_chatops_binding_service()
    return {
        "status": "success",
        "binding": service.get_binding_for_user(user),
        "pending_code": service.get_latest_issued_code_for_user(user),
    }


@router.post("/chatops/bindings/me/issue")
async def issue_commander_chatops_binding_code(user=Depends(require_authenticated_user)):
    """Issue a one-time notification platform binding code for the signed-in user."""
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
    """Revoke the signed-in user's notification platform binding and unused binding code."""
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
    """Get an LLM call trace summary"""
    from core.tracing import get_tracer

    tracer = get_tracer()
    return tracer.get_trace_summary(trace_id)


class SwarmRequest(BaseModel):
    """Swarm mode request"""
    user_input: str = Field(..., description="Natural-language test requirements")
    target_url: str = Field("", description="Target URL")
    mode: Optional[str] = Field(None, description="Discovery mode: requirement/change/exploration/coverage/fault")
    diff_text: str = Field("", description="Git diff text (change-driven)")


@router.post("/swarm")
async def commander_swarm(req: SwarmRequest):
    """
    🐝 Swarm mode — strategic analysis and intelligent parallel execution

    Unlike /run, TestArchitect first performs strategic analysis with five discovery modes,
    then decomposes the task into parallel test tracks.
    """
    import datetime as dt

    from agents.commander import get_commander

    commander = get_commander()

    # Create the mission record in advance
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
        "message": "🐝 Swarm mode started",
        "mode": req.mode or "auto",
        "user_input": req.user_input,
    }


@router.get("/health")
async def agent_health():
    """🏥 Get the health of all agents"""
    from core.agent_bus import get_agent_bus

    bus = get_agent_bus()
    return {
        "agents": bus.get_health(),
        "statistics": bus.get_statistics(),
    }


@router.get("/profiles")
async def list_profiles():
    """📋 Get all agent profiles"""
    from core.agent_profile import get_profile_manager

    pm = get_profile_manager()
    return {
        "profiles": pm.to_summary(),
        "total": len(pm.list_all()),
    }


@router.get("/skills")
async def list_skills():
    """🧰 Get all skill packages"""
    from core.skill_loader import get_skill_loader

    loader = get_skill_loader()
    return {
        "skills": loader.to_summary(),
        "total": len(loader.list_all()),
    }


@router.get("/skills/{skill_id}")
async def get_skill_detail(skill_id: str):
    """📖 Get skill package details, including the full strategy"""
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
    """WeCom/DingTalk webhook callback message"""
    msg_type: str = Field("text", description="Message type")
    content: str = Field("", description="Message content")
    from_user: str = Field("", description="Sender")
    chat_id: str = Field("", description="Group chat ID")


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
                str(result.get("message") or ("App bot credentials validated" if result.get("ok") else "")),
                result.get("status_code"),
                str(source or "manual"),
                str(result.get("app_id_masked") or ""),
            ),
        )


def _purge_app_bot_state(purge_history: bool = True) -> dict:
    """Clean up validation and integration traces left by an incorrectly bound app bot in the current project."""
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
    """Identify whether the notification event came from the platform's public endpoint self-test rather than a real group chat response."""
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
        "👋 I'm the testing platform's legion bot.\n"
        "Send a command:\n"
        "• status\n"
        "• report <mission-id>\n"
        "• test <URL/requirements>\n"
        "• findings <exploration-session-id>\n"
        "• risk <assessment-id>\n"
        "• stop <mission-id>\n"
        "• approve <run_id> [comment] / reject <run_id> [comment]\n"
        "• bind <binding-code>"
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
        "Connected"
        if chatops.get("ready")
        else "Platform ready; notification platform integration pending"
        if chatops.get("platform_ready")
        else str(chatops.get("summary") or "Not ready")
    )
    heartbeat_note = " (zero is normal when idle)" if registered and healthy == 0 else ""
    return (
        "📡 Legion status\n"
        f"• Registered agents: {registered}\n"
        f"• Healthy heartbeats: {healthy}/{registered}{heartbeat_note}\n"
        f"• Active registrations: {active}/{registered}\n"
        f"• Notification platform two-way connection: {sync_text}\n"
        "• Commands: status / report <mission-id> / test <URL/requirements> / bind <binding-code>"
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
            f"📋 Mission #{mission_id}\n"
            f"• Test tracks: {summary.get('total_tests', 0)}\n"
            f"• Passed: {summary.get('completed', 0)}\n"
            f"• Failed: {summary.get('failed', 0)}\n"
            f"• Success rate: {summary.get('success_rate', 0)}%"
        )

    if command_id == "commander.mission.start":
        mission = result.get("mission") or {}
        return (
            f"🐝 Swarm testing mission started\n"
            f"• mission_id: {mission.get('mission_id', '-')}\n"
            f"• command_run: {run.get('run_id', '-')}\n"
            f"• Target: {mission.get('target_url') or 'No URL specified'}\n"
            f"• Requirements: {mission.get('user_input') or '-'}"
        )

    if command_id == "commander.mission.cancel":
        mission = result.get("mission") or {}
        return (
            f"🛑 Mission stopped\n"
            f"• mission_id: {result.get('mission_id', '-')}\n"
            f"• Current status: {mission.get('status') or 'cancelled'}"
        )

    if command_id == "exploration.findings.list":
        findings = list(result.get("findings") or [])
        session_id = str(result.get("session_id") or "")
        if not findings:
            return f"🔎 No findings for session {session_id} yet."
        top_lines = []
        for item in findings[:3]:
            review_flag = " · Human review pending" if item.get("requires_human_review") else ""
            top_lines.append(
                f"• [{item.get('severity', 'low')}] {item.get('title') or item.get('finding_type') or 'Untitled finding'}{review_flag}"
            )
        return (
            f"🔎 Session {session_id}: {len(findings)} findings\n"
            + "\n".join(top_lines)
        )

    if command_id == "release.risk.get":
        assessment = result.get("assessment") or {}
        blockers = list(assessment.get("blockers") or [])
        blocker_text = "None" if not blockers else "; ".join(
            str(item.get("message") or item.get("title") or item.get("type") or "Unknown blocker")
            for item in blockers[:3]
        )
        return (
            f"🧭 Release risk assessment {assessment.get('assessment_id', '-')}\n"
            f"• Business risk: {assessment.get('business_risk', '-')}\n"
            f"• UX risk: {assessment.get('ux_risk', '-')}\n"
            f"• Release risk: {assessment.get('release_risk', '-')}\n"
            f"• Automatic release eligibility: {'Eligible' if assessment.get('auto_release_eligible') else 'Human review required'}\n"
            f"• Blockers: {blocker_text}"
        )

    return f"✅ Command {command_id} executed, run_id={run.get('run_id', '-')}"


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
            "response": "Provide a test URL or requirements, for example: test https://example.com login flow",
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
    logger.info(f"[Webhook] Message received: {text} (from: {from_user}, source: {source})")

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
                f"🔗 Binding successful\n"
                f"• Platform account: {binding.get('username', '-')}\n"
                f"• Notification platform identity: {binding.get('notification_platform_open_id', '-')}"
            ),
            "binding_status": "bound",
            "requester_id": binding.get("user_id", ""),
            "binding": binding,
        }

    bound_user = binding_service.resolve_bound_user(from_user)
    binding_status = "bound" if bound_user else "unbound"
    if not bound_user and not parsed.get("public_allowed"):
        return {
            "response": "🔐 The notification platform identity is not linked to a platform account. Generate a binding code in the Legion control center, then send: bind <binding-code>",
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
                comment=str(parsed.get("comment") or "Execution approved through the notification platform"),
                confirm=True,
                source=normalized_source,
            )
            response = (
                f"✅ Command approved: {parsed['run_id']}\n"
                f"• Current status: {payload.get('run', {}).get('status', '-')}\n"
                f"• Approval status: {payload.get('approval', {}).get('status', '-')}"
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
                reason=str(parsed.get("comment") or "Rejected through the notification platform"),
                source=normalized_source,
            )
            response = (
                f"🛑 Command rejected: {parsed['run_id']}\n"
                f"• Current status: {payload.get('run', {}).get('status', '-')}\n"
                f"• Approval status: {payload.get('approval', {}).get('status', '-')}"
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
            "message": "No enabled notification platform webhook is configured; cannot reply to the group.",
        }

    payload = _format_message(
        "notification_platform",
        "Legion center",
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
        "message": "Notification platform webhook reply sent." if delivered > 0 else "Notification platform webhook reply failed.",
    }


async def _get_notification_platform_tenant_access_token() -> dict:
    app_id = str(Config.NOTIFICATION_PLATFORM_APP_ID or os.getenv("NOTIFICATION_PLATFORM_APP_ID", "")).strip()
    app_secret = str(Config.NOTIFICATION_PLATFORM_APP_SECRET or os.getenv("NOTIFICATION_PLATFORM_APP_SECRET", "")).strip()
    app_id_masked = f"{app_id[:3]}...{app_id[-3:]}" if len(app_id) > 6 else ("*" * len(app_id) if app_id else "")
    if not app_id or not app_secret:
        return {
            "ok": False,
            "message": "Notification platform app bot App ID / Secret is not configured.",
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
            "message": f"Failed to obtain the notification platform tenant_access_token: {exc}",
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
            "message": "The notification platform did not return tenant_access_token.",
            "app_bot_configured": True,
            "status_code": response.status_code,
            "app_id_masked": app_id_masked,
        }
    return {
        "ok": True,
        "token": token,
        "app_bot_configured": True,
        "message": "App bot credentials validated; tenant_access_token obtained successfully.",
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
            "message": "Missing chat_id; cannot reply through the notification platform app bot.",
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
            "message": str(token_result.get("message") or "Failed to obtain notification platform app bot credentials"),
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
            "message": f"Notification platform app bot reply failed: {exc}",
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
        "message": "Notification platform app bot reply sent.",
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
    📨 WeCom/DingTalk two-way interaction — command receiver endpoint

    Set the WeCom/DingTalk bot's message receiving URL to this endpoint.
    Messages mentioning the bot automatically trigger Commander execution.

    Supported command formats:
    - "test https://xxx.com" → Start swarm testing
    - "status" → Return legion health
    - "report {mission_id}" → Return the specified mission report
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
    """Handle notification platform event subscription payloads consistently for real callbacks and platform self-checks."""
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
    🪽 Notification platform event subscription endpoint

    Receives message events from the notification platform app bot.
    Note: this is not a custom webhook bot capability. In the notification platform developer console,
    configure the event subscription URL to point to this endpoint.
    """
    return await _process_notification_platform_event(
        payload,
        source=_detect_notification_platform_event_source(payload, default_source="event_subscription"),
    )


@router.get("/chatops/overview")
async def commander_chatops_overview():
    """Return the current notification platform ChatOps connection status and recent message summaries."""
    return {
        "status": "success",
        "overview": _get_chatops_overview(allow_live_probe=True),
    }


@router.post("/chatops/probe-refresh")
async def commander_chatops_probe_refresh():
    """Immediately retry the public callback probe and return the latest overview."""
    service = get_commander_chatops_service()
    result = service.refresh_callback_probe()
    return {
        "status": "success",
        "probe": result.get("probe", {}),
        "overview": result.get("overview", {}),
    }


@router.post("/chatops/local-tunnel/restart")
async def commander_chatops_local_tunnel_restart():
    """Restart the local OpenSSH reverse tunnel to restore public callbacks."""
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
    """Configure or regenerate the notification platform event subscription verification token."""
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
    """Configure the public callback base URL for notification platform event subscriptions."""
    raw = str(req.public_api_base_url or "").strip()
    normalized = raw.rstrip("/")
    if normalized:
        parsed = urlsplit(normalized)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return {
                "status": "error",
                "message": "PUBLIC_API_BASE_URL must be a complete http(s) URL",
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
    """Configure notification platform app bot credentials to assess readiness for real two-way group chat integration."""
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
    """Unbind the notification platform app bot incorrectly shared with the current project, optionally cleaning validation and integration traces."""
    config_result = Config.set_notification_platform_app_bot_credentials("", "")
    purge_result = _purge_app_bot_state(bool(req.purge_history))
    overview = _get_chatops_overview()
    return {
        "status": "success",
        "message": "The notification platform app bot is unbound from this project; only the webhook notification channel remains.",
        "app_bot_configured": config_result.get("app_bot_configured", False),
        "app_bot_updated_at": config_result.get("app_bot_updated_at", ""),
        "purged": purge_result,
        "overview": overview,
    }


@router.post("/chatops/app-bot-self-check")
async def commander_chatops_app_bot_self_check():
    """Immediately verify whether the current notification platform app bot credentials can obtain tenant_access_token."""
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
    """Simulate a notification platform challenge check internally to confirm the event subscription endpoint is available."""
    token = (Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN or os.getenv("NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "")).strip()
    if not token:
        return {
            "status": "error",
            "message": "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN is not configured",
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
    """Verify both the challenge and a text message through the current public callback URL."""
    overview = _get_chatops_overview()
    callback_url = str(overview.get("callback_url") or "").strip()
    token = (Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN or os.getenv("NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "")).strip()

    if not callback_url or not bool(overview.get("callback_url_public")):
        return {
            "status": "error",
            "message": "No public callback URL is available. Save a public base URL first.",
            "overview": overview,
        }

    if not token:
        return {
            "status": "error",
            "message": "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN is not configured; cannot run an external challenge check.",
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
    """Simulate a notification platform text command to self-check the two-way connection."""
    result = await _handle_commander_chat_message(
        req.message,
        from_user=req.from_user,
        chat_id=req.chat_id,
        source="simulation",
    )
    delivery = {"configured": 0, "delivered": 0, "failed": 0, "message": "No reply triggered"}
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
    """⏰ Get scheduled inspection tasks"""
    from core.test_scheduler import get_scheduler

    scheduler = get_scheduler()
    return {
        "cron_jobs": scheduler.get_cron_jobs(),
        "statistics": scheduler.get_statistics(),
    }

