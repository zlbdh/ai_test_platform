# -*- coding: utf-8 -*-
"""
认证系统路由 - 用户认证、项目管理、审计日志
"""
from fastapi import APIRouter, HTTPException, Depends
from core.models import LoginRequest, RegisterRequest, CreateProjectRequest
from core.auth_dependencies import extract_request_token, require_authenticated_user
from services.auth_service import get_auth_service, UserRole, Permission, ROLE_PERMISSIONS, User

router = APIRouter(tags=["Authentication"])


@router.post("/api/auth/login")
async def auth_login(req: LoginRequest):
    """用户登录"""
    auth = get_auth_service()
    session = auth.authenticate(req.username, req.password)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {
        "status": "success",
        "token": session.token,
        "expires_at": session.expires_at
    }


@router.post("/api/auth/register")
async def auth_register(req: RegisterRequest):
    """用户注册"""
    auth = get_auth_service()
    for u in auth.users.values():
        if u.username == req.username:
            raise HTTPException(status_code=400, detail="Username already exists")
    user = auth.create_user(req.username, req.email, req.password)
    return {"status": "success", "user_id": user.user_id}


@router.post("/api/auth/logout")
async def auth_logout(token: str = Depends(extract_request_token)):
    """用户登出"""
    if not token:
        raise HTTPException(status_code=401, detail="Authentication token required")
    auth = get_auth_service()
    auth.logout(token)
    return {"status": "success"}


@router.get("/api/auth/me")
async def auth_me(user: User = Depends(require_authenticated_user)):
    """获取当前用户信息"""
    return {
        "status": "success",
        "user": {
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "project_ids": user.project_ids,
            "permissions": [permission.value for permission in ROLE_PERMISSIONS.get(user.role, [])],
        }
    }


@router.post("/api/projects")
async def create_project(req: CreateProjectRequest, token: str):
    """创建项目"""
    auth = get_auth_service()
    user = auth.validate_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    project = auth.create_project(req.name, req.description, user.user_id)
    return {"status": "success", "project_id": project.project_id}


@router.get("/api/projects")
async def list_projects(token: str):
    """获取项目列表"""
    auth = get_auth_service()
    user = auth.validate_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    projects = []
    for proj in auth.projects.values():
        if auth.check_project_access(user, proj.project_id):
            projects.append({
                "project_id": proj.project_id,
                "name": proj.name,
                "description": proj.description
            })
    return {"status": "success", "projects": projects}


@router.get("/api/audit/logs")
async def get_audit_logs(token: str, limit: int = 100):
    """获取审计日志 (仅管理员)"""
    auth = get_auth_service()
    user = auth.validate_token(token)
    if not user or not auth.check_permission(user, Permission.ADMIN):
        raise HTTPException(status_code=403, detail="Admin access required")

    logs = auth.get_audit_logs(limit=limit)
    return {
        "status": "success",
        "logs": [
            {
                "log_id": l.log_id,
                "user_id": l.user_id,
                "action": l.action,
                "resource_type": l.resource_type,
                "timestamp": l.timestamp
            }
            for l in logs
        ]
    }
