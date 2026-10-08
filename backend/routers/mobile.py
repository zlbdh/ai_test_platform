# -*- coding: utf-8 -*-
"""
Mobile emulation routes
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from services.execution_center_service import get_execution_center_service

router = APIRouter(prefix="/api/mobile", tags=["mobile"])


class MobileTestRequest(BaseModel):
    url: str
    devices: Optional[List[str]] = None
    screenshot: bool = False
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


@router.post("/test")
async def mobile_test(req: MobileTestRequest):
    """Run mobile emulation tests"""
    from services.mobile_emulation import create_mobile_service
    try:
        service = create_mobile_service()
        report = await service.test_devices(req.url, req.devices, req.screenshot)
        report_dict = report.to_dict()
        detail_items = []
        for result in report_dict.get("results", []):
            issues = result.get("issues", []) or []
            if not issues:
                detail_items.append(
                    {
                        "target": result.get("device") or "device",
                        "passed": True,
                        "message": "No mobile issues found",
                    }
                )
                continue
            for issue in issues:
                detail_items.append(
                    {
                        "target": result.get("device") or issue.get("device") or "device",
                        "passed": False,
                        "message": issue.get("description") or issue.get("rule_id") or "Mobile issues found",
                    }
                )
        get_execution_center_service().record_specialized_result(
            mode="mobile",
            title=f"Mobile testing · {req.url}",
            target_url=req.url,
            success=int(report_dict.get("total_issues", 0) or 0) == 0 and float(report_dict.get("score", -1) or -1) >= 0,
            summary=report_dict.get("summary") or f"Devices: {report_dict.get('devices_tested', 0)} · Issues: {report_dict.get('total_issues', 0)}",
            detail_items=detail_items,
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="mobile",
        )
        return report_dict
    except Exception as e:
        get_execution_center_service().record_specialized_result(
            mode="mobile",
            title=f"Mobile testing · {req.url}",
            target_url=req.url,
            success=False,
            summary=str(e),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="mobile",
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/devices")
async def mobile_list_devices():
    """List predefined devices"""
    from services.mobile_emulation import create_mobile_service
    service = create_mobile_service()
    return {"devices": service.list_devices()}
