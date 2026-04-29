# -*- coding: utf-8 -*-
"""
探索性测试 API 路由
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.auth_dependencies import require_authenticated_user
from services.exploration_service import (
    ExplorationFindingNotFoundError,
    ExplorationPermissionError,
    ExplorationServiceError,
    ExplorationSessionNotFoundError,
    get_exploration_service,
)


router = APIRouter(prefix="/api/exploration", tags=["探索性测试"])


class ExplorationSessionCreateRequest(BaseModel):
    group_id: str = Field("", description="可选执行分组 ID")
    project_key: str = Field("", description="项目标识")
    target_url: str = Field(..., description="目标 URL")
    charter: str = Field(..., description="探索性测试章程")


class ExplorationFindingReviewRequest(BaseModel):
    decision: str = Field(..., description="复核结论：confirmed / dismissed")
    comment: str = Field("", description="复核备注")


@router.post("/sessions")
async def create_exploration_session(
    req: ExplorationSessionCreateRequest,
    user=Depends(require_authenticated_user),
):
    svc = get_exploration_service()
    try:
        payload = svc.create_session(
            user=user,
            group_id=req.group_id,
            project_key=req.project_key,
            target_url=req.target_url,
            charter=req.charter,
        )
    except ExplorationPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ExplorationServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "success", "session": payload}


@router.get("/sessions")
async def list_exploration_sessions(
    project_key: str = Query("", description="项目筛选"),
    status: str = Query("", description="会话状态筛选"),
    limit: int = Query(20, ge=1, le=200),
    user=Depends(require_authenticated_user),
):
    svc = get_exploration_service()
    try:
        payload = svc.list_sessions(
            user=user,
            project_key=project_key,
            status=status,
            limit=limit,
        )
    except ExplorationPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ExplorationServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "success", **payload}


@router.get("/sessions/{session_id}")
async def get_exploration_session(
    session_id: str,
    user=Depends(require_authenticated_user),
):
    svc = get_exploration_service()
    try:
        payload = svc.get_session(user=user, session_id=session_id)
    except ExplorationSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExplorationPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"status": "success", "session": payload}


@router.post("/sessions/{session_id}/stop")
async def stop_exploration_session(
    session_id: str,
    user=Depends(require_authenticated_user),
):
    svc = get_exploration_service()
    try:
        payload = svc.stop_session(user=user, session_id=session_id)
    except ExplorationSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExplorationPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"status": "success", "session": payload}


@router.get("/sessions/{session_id}/findings")
async def list_exploration_findings(
    session_id: str,
    severity: str = Query("", description="严重级别筛选"),
    review_only: bool = Query(False, description="仅返回需人工复核的发现"),
    review_status: str = Query("", description="复核状态筛选"),
    user=Depends(require_authenticated_user),
):
    svc = get_exploration_service()
    try:
        payload = svc.list_findings(
            user=user,
            session_id=session_id,
            severity=severity,
            review_only=review_only,
            review_status=review_status,
        )
    except ExplorationSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExplorationPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"status": "success", **payload}


@router.get("/review-queue")
async def list_exploration_review_queue(
    project_key: str = Query("", description="项目筛选"),
    severity: str = Query("", description="严重级别筛选"),
    review_status: str = Query("", description="复核状态筛选，默认 pending"),
    limit: int = Query(20, ge=1, le=200),
    user=Depends(require_authenticated_user),
):
    svc = get_exploration_service()
    try:
        payload = svc.list_review_queue(
            user=user,
            project_key=project_key,
            severity=severity,
            review_status=review_status,
            limit=limit,
        )
    except ExplorationPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ExplorationServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "success", **payload}


@router.get("/findings/{finding_id}")
async def get_exploration_finding(
    finding_id: str,
    user=Depends(require_authenticated_user),
):
    svc = get_exploration_service()
    try:
        payload = svc.get_finding(user=user, finding_id=finding_id)
    except ExplorationFindingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExplorationPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"status": "success", "finding": payload}


@router.post("/findings/{finding_id}/review")
async def review_exploration_finding(
    finding_id: str,
    req: ExplorationFindingReviewRequest,
    user=Depends(require_authenticated_user),
):
    svc = get_exploration_service()
    try:
        payload = svc.review_finding(
            user=user,
            finding_id=finding_id,
            decision=req.decision,
            comment=req.comment,
        )
    except ExplorationFindingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExplorationPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ExplorationServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "success", "finding": payload}
