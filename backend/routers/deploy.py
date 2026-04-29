# -*- coding: utf-8 -*-
"""待测项目部署路由 — /api/deploy/*"""
import asyncio
import json
from dataclasses import asdict
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, List, Optional
from services.deploy_service import get_deploy_service
from core.api_response import ok, fail, safe_handler
from core.auth_dependencies import (
    require_admin_user,
    require_deploy_approve_user,
    require_deploy_request_user,
    require_deploy_view_user,
)
from services.auth_service import get_auth_service

router = APIRouter(prefix="/api/deploy", tags=["项目部署"])

ADMIN_ONLY = [Depends(require_admin_user)]
DEPLOY_VIEW_ONLY = [Depends(require_deploy_view_user)]
DEPLOY_REQUEST_ONLY = [Depends(require_deploy_request_user)]
DEPLOY_APPROVE_ONLY = [Depends(require_deploy_approve_user)]


def _audit_deploy_action(
    request: Request,
    action: str,
    resource_type: str,
    resource_id: Optional[str],
    details: Optional[dict] = None,
):
    user = getattr(request.state, "authenticated_user", None)
    if not user:
        return
    get_auth_service().record_audit_event(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        user_id=getattr(user, "user_id", None),
    )


def _role_value(user: Any) -> str:
    role = getattr(user, "role", None)
    if hasattr(role, "value"):
        return str(role.value)
    return str(role or "")


def _get_project_scope(user: Any) -> Optional[set[str]]:
    raw_scope = getattr(user, "project_ids", None)
    if not raw_scope:
        return None
    scope = {str(item).strip() for item in raw_scope if str(item).strip()}
    return scope or None


def _is_scope_allowed(user: Any, project_key: str) -> bool:
    if not user or not project_key:
        return True
    if _role_value(user) == "admin":
        return True
    scope = _get_project_scope(user)
    if not scope or "*" in scope:
        return True
    return project_key in scope


def _require_project_scope(request: Request, project_key: str):
    user = getattr(request.state, "authenticated_user", None)
    if not _is_scope_allowed(user, project_key):
        raise HTTPException(status_code=403, detail="Project scope access required")


def _get_item_project_key(item: Any, field: str = "project_key") -> str:
    if isinstance(item, dict):
        return str(item.get(field) or "")
    return str(getattr(item, field, "") or "")


def _filter_scoped_items(request: Request, items: List[Any], field: str = "project_key") -> List[Any]:
    user = getattr(request.state, "authenticated_user", None)
    scope = _get_project_scope(user)
    if not user or _role_value(user) == "admin" or not scope or "*" in scope:
        return items
    return [item for item in items if _get_item_project_key(item, field) in scope]


def _find_project_key_for_repo(svc, repo_id: str) -> str:
    for project in svc.projects.values():
        for repo in project.repos:
            if repo.id == repo_id:
                return project.key
    return ""


def _serialize_deploy_audit_log(log) -> dict:
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


# ── 请求模型 ──────────────────────────────────────────────────────────────────
class RepoInput(BaseModel):
    label: str = "默认"
    repo_url: str
    branch: str = "master"
    install_cmd: str = ""
    start_cmd: str = ""
    port: int = 0
    tech_stack: str = ""

class AddProjectRequest(BaseModel):
    name: str
    repos: List[RepoInput]
    git_token: str = ""

class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    repos: Optional[List[RepoInput]] = None
    git_token: Optional[str] = None

class DeployActionRequest(BaseModel):
    branch: str = ""

class GitTokenRequest(BaseModel):
    git_token: str


class ApprovalReviewRequest(BaseModel):
    comment: str = ""


# ── 项目 CRUD ─────────────────────────────────────────────────────────────────
@router.get("/projects", dependencies=DEPLOY_VIEW_ONLY)
async def get_projects(request: Request):
    svc = get_deploy_service()
    projects = _filter_scoped_items(request, svc.get_all_projects(), field="key")
    return ok({"projects": projects})

@router.post("/projects", dependencies=ADMIN_ONLY)
@safe_handler
async def add_project(req: AddProjectRequest, request: Request):
    svc = get_deploy_service()
    if not req.name or not req.repos:
        raise ValueError("项目名称和至少一个仓库不能为空")
    repos = [r.model_dump() for r in req.repos]
    if req.git_token and repos:
        repos[0]["git_token"] = req.git_token
    cfg = svc.add_project(name=req.name, repos=repos)
    _audit_deploy_action(
        request,
        "deploy_project_add",
        "deploy_project",
        cfg.key,
        {"project_key": cfg.key, "project_name": req.name},
    )
    return ok({"project": svc.get_project_detail(cfg.key)})

@router.put("/projects/{project_key}", dependencies=ADMIN_ONLY)
@safe_handler
async def update_project(project_key: str, req: UpdateProjectRequest, request: Request):
    _require_project_scope(request, project_key)
    svc = get_deploy_service()
    repos = [r.model_dump() for r in req.repos] if req.repos is not None else None
    cfg = svc.update_project(project_key, name=req.name, repos=repos)
    if req.git_token is not None:
        svc.set_project_token(project_key, req.git_token)
    _audit_deploy_action(
        request,
        "deploy_project_update",
        "deploy_project",
        project_key,
        {"project_key": project_key, "project_name": req.name or cfg.name},
    )
    return ok({"project": svc.get_project_detail(cfg.key)})

@router.delete("/projects/{project_key}", dependencies=ADMIN_ONLY)
@safe_handler
async def delete_project(project_key: str, request: Request):
    _require_project_scope(request, project_key)
    svc = get_deploy_service()
    svc.delete_project(project_key)
    _audit_deploy_action(
        request,
        "deploy_project_delete",
        "deploy_project",
        project_key,
        {"project_key": project_key},
    )
    return ok(message="项目已删除")


# ── Git Token (项目级) ─────────────────────────────────────────────────────────
@router.patch("/projects/{project_key}/token", dependencies=ADMIN_ONLY)
@safe_handler
async def set_project_token(project_key: str, req: GitTokenRequest, request: Request):
    if not req.git_token:
        raise ValueError("git_token 不能为空")
    _require_project_scope(request, project_key)
    svc = get_deploy_service()
    svc.set_project_token(project_key, req.git_token)
    _audit_deploy_action(
        request,
        "deploy_project_token_update",
        "deploy_project",
        project_key,
        {"project_key": project_key},
    )
    return ok(message="Git 令牌已保存")


# ── AI 智能分析 ───────────────────────────────────────────────────────────────
@router.post("/repo/{project_key}/{repo_id}/ai-analyze", dependencies=ADMIN_ONLY)
@safe_handler
async def ai_analyze_repo(project_key: str, repo_id: str, request: Request):
    _require_project_scope(request, project_key)
    svc = get_deploy_service()
    result = await svc.ai_analyze_repo(project_key, repo_id)
    return ok({"analysis": result})

class ApplyAIConfigRequest(BaseModel):
    tech_stack: str = ""
    install_cmd: str = ""
    start_cmd: str = ""
    port: int = 0
    deploy_context: dict = {}    # 用户补充的部署上下文

class AIRefineRequest(BaseModel):
    """AI 二次确认请求 — 用户补充的部署上下文"""
    server_address: str = ""
    db_connection: str = ""
    env_vars: str = ""       # KEY=VALUE 格式，每行一个
    user_notes: str = ""
    initial_config: dict = {}  # 当前 AI 分析结果

@router.post("/repo/{project_key}/{repo_id}/ai-refine", dependencies=ADMIN_ONLY)
@safe_handler
async def ai_refine_config(project_key: str, repo_id: str, req: AIRefineRequest, request: Request):
    """AI 二次确认 — 结合用户补充的部署上下文优化配置"""
    _require_project_scope(request, project_key)
    svc = get_deploy_service()
    svc._find_repo(project_key, repo_id)  # ValueError 由 @safe_handler 捕获

    from services.ai_deploy_analyzer import refine_deploy_config
    deploy_context = {
        "server_address": req.server_address,
        "db_connection": req.db_connection,
        "env_vars": req.env_vars,
        "user_notes": req.user_notes,
    }
    result = await refine_deploy_config(req.initial_config, deploy_context)
    return ok({"analysis": result})

@router.post("/repo/{project_key}/{repo_id}/apply-ai-config", dependencies=ADMIN_ONLY)
@safe_handler
async def apply_ai_config(project_key: str, repo_id: str, req: ApplyAIConfigRequest, request: Request):
    _require_project_scope(request, project_key)
    svc = get_deploy_service()
    repo_status = svc.apply_ai_config(project_key, repo_id, req.model_dump())
    _audit_deploy_action(
        request,
        "deploy_repo_apply_ai_config",
        "deploy_repo",
        repo_id,
        {"project_key": project_key, "repo_id": repo_id},
    )
    return ok({"repo": repo_status})


# ── 仓库级部署操作 (以 project_key + repo_id 为粒度) ──────────────────────────
@router.post("/repo/{project_key}/{repo_id}/clone", dependencies=ADMIN_ONLY)
@safe_handler
async def clone_repo(project_key: str, repo_id: str, request: Request, req: DeployActionRequest = None):
    _require_project_scope(request, project_key)
    svc = get_deploy_service()
    record = await svc.clone_repo(project_key, repo_id, req.branch if req else "")
    _audit_deploy_action(
        request,
        "deploy_repo_clone",
        "deploy_repo",
        repo_id,
        {"project_key": project_key, "repo_id": repo_id, "branch": req.branch if req else ""},
    )
    return ok({"record": asdict(record)})

@router.post("/repo/{project_key}/{repo_id}/install", dependencies=ADMIN_ONLY)
@safe_handler
async def install_repo(project_key: str, repo_id: str, request: Request):
    _require_project_scope(request, project_key)
    svc = get_deploy_service()
    record = await svc.install_repo(project_key, repo_id)
    _audit_deploy_action(
        request,
        "deploy_repo_install",
        "deploy_repo",
        repo_id,
        {"project_key": project_key, "repo_id": repo_id},
    )
    return ok({"record": asdict(record)})

@router.post("/repo/{project_key}/{repo_id}/start", dependencies=ADMIN_ONLY)
@safe_handler
async def start_repo(project_key: str, repo_id: str, request: Request):
    _require_project_scope(request, project_key)
    svc = get_deploy_service()
    record = await svc.start_repo(project_key, repo_id)
    _audit_deploy_action(
        request,
        "deploy_repo_start",
        "deploy_repo",
        repo_id,
        {"project_key": project_key, "repo_id": repo_id},
    )
    return ok({"record": asdict(record)})

@router.post("/repo/{project_key}/{repo_id}/stop", dependencies=ADMIN_ONLY)
@safe_handler
async def stop_repo(project_key: str, repo_id: str, request: Request):
    _require_project_scope(request, project_key)
    svc = get_deploy_service()
    record = await svc.stop_repo(project_key, repo_id)
    _audit_deploy_action(
        request,
        "deploy_repo_stop",
        "deploy_repo",
        repo_id,
        {"project_key": project_key, "repo_id": repo_id},
    )
    return ok({"record": asdict(record)})

@router.post("/repo/{project_key}/{repo_id}/full", dependencies=ADMIN_ONLY)
@safe_handler
async def full_deploy_repo(project_key: str, repo_id: str, request: Request, req: DeployActionRequest = None):
    """一键部署 — 后台执行，立即返回 record_id / job_id"""
    _require_project_scope(request, project_key)
    svc = get_deploy_service()
    branch = req.branch if req else ""
    job = svc.schedule_full_deploy(project_key, repo_id, branch)
    _audit_deploy_action(
        request,
        "deploy_repo_full",
        "deploy_repo",
        repo_id,
        {"project_key": project_key, "repo_id": repo_id, "branch": branch, "record_id": job.record_id, "job_id": job.id},
    )
    return ok({"record_id": job.record_id, "repo_id": repo_id, "job_id": job.id, "job_status": job.status})

@router.post("/repo/{project_key}/deploy-all", dependencies=ADMIN_ONLY)
@safe_handler
async def full_deploy_all(project_key: str, request: Request):
    """一键部署项目下所有仓库（后台执行）"""
    _require_project_scope(request, project_key)
    svc = get_deploy_service()
    job = svc.schedule_full_deploy_all(project_key)
    _audit_deploy_action(
        request,
        "deploy_project_full",
        "deploy_project",
        project_key,
        {"project_key": project_key, "record_id": job.record_id, "job_id": job.id},
    )
    return ok({
        "record_id": job.record_id,
        "project_key": project_key,
        "job_id": job.id,
        "job_status": job.status,
    })


@router.post("/repo/{project_key}/{repo_id}/full/request", dependencies=DEPLOY_REQUEST_ONLY)
@safe_handler
async def request_full_deploy_repo(project_key: str, repo_id: str, request: Request, req: DeployActionRequest = None):
    """创建仓库一键部署审批单"""
    _require_project_scope(request, project_key)
    svc = get_deploy_service()
    user = getattr(request.state, "authenticated_user", None)
    branch = req.branch if req else ""
    approval = svc.create_deploy_approval(
        action="full_deploy",
        project_key=project_key,
        repo_id=repo_id,
        branch=branch,
        requested_by=getattr(user, "user_id", "unknown"),
        requested_by_name=getattr(user, "username", "") or getattr(user, "user_id", "unknown"),
    )
    _audit_deploy_action(
        request,
        "deploy_approval_request_create",
        "deploy_approval",
        approval["id"],
        {"approval_id": approval["id"], "project_key": project_key, "repo_id": repo_id, "branch": branch},
    )
    return ok({"approval": approval})


@router.post("/repo/{project_key}/deploy-all/request", dependencies=DEPLOY_REQUEST_ONLY)
@safe_handler
async def request_full_deploy_all(project_key: str, request: Request):
    """创建项目级一键部署审批单"""
    _require_project_scope(request, project_key)
    svc = get_deploy_service()
    user = getattr(request.state, "authenticated_user", None)
    approval = svc.create_deploy_approval(
        action="full_deploy_all",
        project_key=project_key,
        requested_by=getattr(user, "user_id", "unknown"),
        requested_by_name=getattr(user, "username", "") or getattr(user, "user_id", "unknown"),
    )
    _audit_deploy_action(
        request,
        "deploy_approval_request_create",
        "deploy_approval",
        approval["id"],
        {"approval_id": approval["id"], "project_key": project_key, "repo_id": ""},
    )
    return ok({"approval": approval})


@router.get("/approvals", dependencies=DEPLOY_VIEW_ONLY)
async def list_approvals(request: Request, limit: int = 30, status: str = ""):
    """查询部署审批单"""
    svc = get_deploy_service()
    approvals = _filter_scoped_items(request, svc.list_approvals(limit=limit, status=status))
    return ok({"approvals": approvals})


@router.get("/approvals/{approval_id}", dependencies=DEPLOY_VIEW_ONLY)
async def get_approval_detail(approval_id: str, request: Request):
    """查询单条部署审批单"""
    svc = get_deploy_service()
    approval = svc.get_approval_detail(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="审批单不存在")
    _require_project_scope(request, approval.get("project_key", ""))
    return ok({"approval": approval})


@router.post("/approvals/{approval_id}/approve", dependencies=DEPLOY_APPROVE_ONLY)
@safe_handler
async def approve_approval(approval_id: str, request: Request, req: ApprovalReviewRequest):
    """审批通过并触发部署作业"""
    svc = get_deploy_service()
    user = getattr(request.state, "authenticated_user", None)
    current = svc.get_approval_detail(approval_id)
    if not current:
        raise HTTPException(status_code=404, detail="审批单不存在")
    _require_project_scope(request, current.get("project_key", ""))
    approval = svc.review_approval(
        approval_id,
        approved=True,
        reviewed_by=getattr(user, "user_id", "unknown"),
        reviewed_by_name=getattr(user, "username", "") or getattr(user, "user_id", "unknown"),
        comment=req.comment,
    )
    _audit_deploy_action(
        request,
        "deploy_approval_approve",
        "deploy_approval",
        approval_id,
        {
            "approval_id": approval_id,
            "project_key": current.get("project_key"),
            "job_id": approval.get("job_id"),
            "record_id": approval.get("record_id"),
        },
    )
    return ok({"approval": approval})


@router.post("/approvals/{approval_id}/reject", dependencies=DEPLOY_APPROVE_ONLY)
@safe_handler
async def reject_approval(approval_id: str, request: Request, req: ApprovalReviewRequest):
    """驳回部署审批单"""
    svc = get_deploy_service()
    user = getattr(request.state, "authenticated_user", None)
    current = svc.get_approval_detail(approval_id)
    if not current:
        raise HTTPException(status_code=404, detail="审批单不存在")
    _require_project_scope(request, current.get("project_key", ""))
    approval = svc.review_approval(
        approval_id,
        approved=False,
        reviewed_by=getattr(user, "user_id", "unknown"),
        reviewed_by_name=getattr(user, "username", "") or getattr(user, "user_id", "unknown"),
        comment=req.comment,
    )
    _audit_deploy_action(
        request,
        "deploy_approval_reject",
        "deploy_approval",
        approval_id,
        {
            "approval_id": approval_id,
            "project_key": current.get("project_key"),
            "comment": req.comment,
        },
    )
    return ok({"approval": approval})


@router.get("/audit", dependencies=DEPLOY_VIEW_ONLY)
async def list_deploy_audit_logs(
    request: Request,
    limit: int = 50,
    action: str = "",
    project_key: str = "",
    user_id: str = "",
):
    """查询部署相关审计日志，支持按项目范围自动收口。"""
    auth = get_auth_service()
    logs = auth.get_audit_logs(
        user_id=user_id or None,
        action=action or None,
        action_prefix="deploy_",
        limit=max(int(limit or 0), 0) or 50,
    )
    payloads = [_serialize_deploy_audit_log(log) for log in logs]
    if project_key:
        payloads = [item for item in payloads if item.get("project_key") == project_key]

    filtered: List[dict] = []
    user = getattr(request.state, "authenticated_user", None)
    for item in payloads:
        item_project_key = str(item.get("project_key") or "")
        if not item_project_key and _get_project_scope(user) and _role_value(user) != "admin":
            continue
        if _is_scope_allowed(user, item_project_key):
            filtered.append(item)
    return ok({"logs": filtered})


# ── SSE 实时事件流 ────────────────────────────────────────────────────────────
@router.get("/repo/{project_key}/{repo_id}/stream", dependencies=DEPLOY_VIEW_ONLY)
async def deploy_stream(project_key: str, repo_id: str, request: Request):
    """SSE 端点：实时推送部署进度事件"""
    _require_project_scope(request, project_key)
    svc = get_deploy_service()

    async def event_generator():
        async for event in svc.get_event_stream(repo_id):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── 单条记录详情 ──────────────────────────────────────────────────────────────
@router.get("/record/{record_id}", dependencies=DEPLOY_VIEW_ONLY)
async def get_record_detail(record_id: str, request: Request):
    """查询单条部署记录（含子步骤）"""
    svc = get_deploy_service()
    for r in reversed(svc.history):
        if r.id == record_id:
            _require_project_scope(request, r.project_key)
            return ok({"record": asdict(r)})
    raise HTTPException(status_code=404, detail="记录不存在")


@router.get("/jobs/{job_id}", dependencies=DEPLOY_VIEW_ONLY)
async def get_job_detail(job_id: str, request: Request):
    """查询后台部署作业状态"""
    svc = get_deploy_service()
    job = svc.get_job_detail(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="作业不存在")
    _require_project_scope(request, job.get("project_key", ""))
    return ok({"job": job})


@router.get("/jobs", dependencies=DEPLOY_VIEW_ONLY)
async def list_jobs(request: Request, limit: int = 30, status: str = ""):
    """查询后台部署作业列表"""
    svc = get_deploy_service()
    jobs = _filter_scoped_items(request, svc.list_jobs(limit=limit, status=status))
    return ok({"jobs": jobs})


@router.post("/jobs/{job_id}/cancel", dependencies=ADMIN_ONLY)
@safe_handler
async def cancel_job(job_id: str, request: Request):
    """取消后台部署作业"""
    svc = get_deploy_service()
    current = svc.get_job_detail(job_id)
    if not current:
        raise HTTPException(status_code=404, detail="作业不存在")
    _require_project_scope(request, current.get("project_key", ""))
    job = svc.cancel_job(job_id)
    _audit_deploy_action(
        request,
        "deploy_job_cancel",
        "deploy_job",
        job_id,
        {
            "job_id": job_id,
            "project_key": current.get("project_key"),
            "record_id": job.get("record_id"),
        },
    )
    return ok({"job": job})


# ── 日志/历史 ─────────────────────────────────────────────────────────────────
@router.get("/logs/{repo_id}", dependencies=DEPLOY_VIEW_ONLY)
async def get_logs(repo_id: str, request: Request, lines: int = 100):
    svc = get_deploy_service()
    project_key = _find_project_key_for_repo(svc, repo_id)
    if not project_key:
        raise HTTPException(status_code=404, detail="仓库不存在")
    _require_project_scope(request, project_key)
    return ok({"logs": svc.get_logs(repo_id, lines)})

@router.get("/history", dependencies=DEPLOY_VIEW_ONLY)
async def get_history(request: Request):
    svc = get_deploy_service()
    history = _filter_scoped_items(request, svc.get_deploy_history())
    return ok({"history": history})

@router.delete("/history/{record_id}", dependencies=ADMIN_ONLY)
async def delete_history_record(record_id: str, request: Request):
    """删除单条部署记录"""
    svc = get_deploy_service()
    record = next((item for item in reversed(svc.history) if item.id == record_id), None)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    _require_project_scope(request, record.project_key)
    svc.history = [r for r in svc.history if r.id != record_id]
    svc._save_history()
    _audit_deploy_action(
        request,
        "deploy_history_delete",
        "deploy_history",
        record_id,
        {"record_id": record_id, "project_key": record.project_key},
    )
    return ok(message="记录已删除")

@router.delete("/history", dependencies=ADMIN_ONLY)
async def clear_history(request: Request):
    """清空全部部署历史"""
    svc = get_deploy_service()
    svc.history.clear()
    svc._save_history()
    _audit_deploy_action(
        request,
        "deploy_history_clear",
        "deploy_history",
        "all",
        {"scope": "all"},
    )
    return ok(message="历史已清空")


# ── 部署记忆 ─────────────────────────────────────────────────────────────────
@router.get("/repo/{project_key}/{repo_id}/memory", dependencies=DEPLOY_VIEW_ONLY)
async def get_repo_memory(project_key: str, repo_id: str, request: Request):
    """获取仓库的部署记忆"""
    _require_project_scope(request, project_key)
    svc = get_deploy_service()
    mem = svc._load_memory(repo_id)
    return ok({"memory": mem, "has_memory": bool(mem)})


@router.delete("/repo/{project_key}/{repo_id}/memory", dependencies=ADMIN_ONLY)
async def clear_repo_memory(project_key: str, repo_id: str, request: Request):
    """清除仓库的部署记忆"""
    _require_project_scope(request, project_key)
    svc = get_deploy_service()
    svc.memory.pop(repo_id, None)
    mf = svc._memory_file(repo_id)
    if mf.exists():
        mf.unlink()
    _audit_deploy_action(
        request,
        "deploy_memory_clear",
        "deploy_memory",
        repo_id,
        {"project_key": project_key, "repo_id": repo_id},
    )
    return ok(message="记忆已清除")
