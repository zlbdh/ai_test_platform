# -*- coding: utf-8 -*-
"""
Exploratory testing API routes
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


router = APIRouter(prefix="/api/exploration", tags=["Exploratory testing"])


class ExplorationSessionCreateRequest(BaseModel):
    group_id: str = Field("", description="Optional execution group ID")
    project_key: str = Field("", description="Project identifier")
    target_url: str = Field(..., description="Target URL")
    charter: str = Field(..., description="Exploratory testing charter")


class ExplorationFindingReviewRequest(BaseModel):
    decision: str = Field(..., description="Review decision: confirmed / dismissed")
    comment: str = Field("", description="Review comment")


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
    project_key: str = Query("", description="Project filter"),
    status: str = Query("", description="Session status filter"),
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
    severity: str = Query("", description="Severity filter"),
    review_only: bool = Query(False, description="Return only findings requiring human review"),
    review_status: str = Query("", description="Review status filter"),
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
    project_key: str = Query("", description="Project filter"),
    severity: str = Query("", description="Severity filter"),
    review_status: str = Query("", description="Review status filter; defaults to pending"),
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
