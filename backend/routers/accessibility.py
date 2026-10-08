# -*- coding: utf-8 -*-
"""
Accessibility testing routes
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.execution_center_service import get_execution_center_service

router = APIRouter(prefix="/api/accessibility", tags=["accessibility"])


class A11yAuditRequest(BaseModel):
    url: str
    level: str = "AA"  # A, AA, AAA
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


class A11yQuickCheckRequest(BaseModel):
    url: str
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


@router.post("/audit")
async def a11y_audit(req: A11yAuditRequest):
    """Run a WCAG accessibility audit (requires Playwright)"""
    from services.accessibility_testing import create_accessibility_service
    try:
        service = create_accessibility_service()
        report = await service.audit(req.url, req.level)
        payload = report.to_dict()
        get_execution_center_service().record_accessibility_result(
            payload,
            quick=False,
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
        )
        return payload
    except Exception as e:
        get_execution_center_service().record_accessibility_result(
            {"url": req.url, "status": "error", "error": str(e), "score": -1, "total_issues": 0, "issues": []},
            quick=False,
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick-check")
async def a11y_quick_check(req: A11yQuickCheckRequest):
    """Run a quick accessibility check (static HTTP analysis; no Playwright required)"""
    from services.accessibility_testing import create_accessibility_service
    try:
        service = create_accessibility_service()
        payload = await service.quick_check(req.url)
        get_execution_center_service().record_accessibility_result(
            payload,
            quick=True,
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
        )
        return payload
    except Exception as e:
        get_execution_center_service().record_accessibility_result(
            {"url": req.url, "status": "error", "error": str(e), "score": -1, "total": 0, "issues": []},
            quick=True,
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
        )
        raise HTTPException(status_code=500, detail=str(e))
