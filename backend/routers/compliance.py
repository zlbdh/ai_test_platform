# -*- coding: utf-8 -*-
"""
合规测试路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from services.execution_center_service import get_execution_center_service

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


class ComplianceAuditRequest(BaseModel):
    url: str
    standards: Optional[List[str]] = None  # ["GDPR", "SOC2", "PCI-DSS"]
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


@router.post("/audit")
async def compliance_audit(req: ComplianceAuditRequest):
    """执行合规审计"""
    from services.compliance_testing import create_compliance_service
    try:
        service = create_compliance_service()
        report = await service.audit(req.url, req.standards)
        payload = report.to_dict()
        get_execution_center_service().record_compliance_result(
            payload,
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
        )
        return payload
    except Exception as e:
        get_execution_center_service().record_compliance_result(
            {"url": req.url, "summary": str(e), "score": -1, "total_issues": 0, "issues": []},
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
        )
        raise HTTPException(status_code=500, detail=str(e))
