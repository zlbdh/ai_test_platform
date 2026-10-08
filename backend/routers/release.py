# -*- coding: utf-8 -*-
"""
Release risk assessment API routes
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.auth_dependencies import require_authenticated_user
from services.release_risk_service import (
    ReleaseRiskAssessmentNotFoundError,
    ReleaseRiskPermissionError,
    ReleaseRiskServiceError,
    get_release_risk_service,
)


router = APIRouter(prefix="/api/release", tags=["Release risk"])


class ReleaseRiskAssessmentCreateRequest(BaseModel):
    project_key: str = Field("", description="Project identifier")
    environment: str = Field("test", description="Target environment")
    exploration_session_ids: List[str] = Field(default_factory=list, description="Exploration session ID list")
    required_tests_passed: bool = Field(True, description="Whether required tests passed")
    change_summary: str = Field("", description="Change summary")


@router.post("/risk-assessments")
async def create_release_risk_assessment(
    req: ReleaseRiskAssessmentCreateRequest,
    user=Depends(require_authenticated_user),
):
    svc = get_release_risk_service()
    try:
        payload = svc.create_assessment(
            user=user,
            project_key=req.project_key,
            environment=req.environment,
            exploration_session_ids=req.exploration_session_ids,
            required_tests_passed=req.required_tests_passed,
            change_summary=req.change_summary,
        )
    except ReleaseRiskPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ReleaseRiskServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "success", "assessment": payload}


@router.get("/risk-assessments")
async def list_release_risk_assessments(
    project_key: str = Query("", description="Project filter"),
    environment: str = Query("", description="Environment filter"),
    auto_release_eligible: bool | None = Query(None, description="Automatic release eligibility filter"),
    limit: int = Query(20, ge=1, le=200),
    user=Depends(require_authenticated_user),
):
    svc = get_release_risk_service()
    try:
        payload = svc.list_assessments(
            user=user,
            project_key=project_key,
            environment=environment,
            auto_release_eligible=auto_release_eligible,
            limit=limit,
        )
    except ReleaseRiskPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ReleaseRiskServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "success", **payload}


@router.get("/risk-assessments/{assessment_id}")
async def get_release_risk_assessment(
    assessment_id: str,
    user=Depends(require_authenticated_user),
):
    svc = get_release_risk_service()
    try:
        payload = svc.get_assessment(user=user, assessment_id=assessment_id)
    except ReleaseRiskAssessmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReleaseRiskPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"status": "success", "assessment": payload}
