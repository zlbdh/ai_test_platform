# -*- coding: utf-8 -*-
"""
Chaos engineering routes
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from services.execution_center_service import get_execution_center_service

router = APIRouter(prefix="/api/chaos", tags=["chaos"])


class ChaosRunRequest(BaseModel):
    url: str
    scenarios: Optional[List[str]] = None
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


@router.post("/run")
async def chaos_run(req: ChaosRunRequest):
    """Run chaos testing scenarios"""
    from services.chaos_engineering import create_chaos_service
    try:
        service = create_chaos_service()
        report = await service.run_scenarios(req.url, req.scenarios)
        report_dict = report.to_dict()
        get_execution_center_service().record_specialized_result(
            mode="chaos",
            title=f"Chaos testing · {req.url}",
            target_url=req.url,
            success=int(report_dict.get("failed", 0) or 0) == 0 and int(report_dict.get("errors", 0) or 0) == 0,
            summary=report_dict.get("summary") or f"{report_dict.get('scenarios_run', 0)} scenarios",
            detail_items=[
                {
                    "target": item.get("scenario") or "chaos-scenario",
                    "passed": item.get("status") == "passed",
                    "message": item.get("details") or f"Duration: {int(item.get('duration_ms', 0) or 0)}ms",
                }
                for item in (report_dict.get("results", []) or [])
            ],
            duration_ms=int(report_dict.get("total_duration_ms", 0) or 0),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="chaos",
        )
        return report_dict
    except Exception as e:
        get_execution_center_service().record_specialized_result(
            mode="chaos",
            title=f"Chaos testing · {req.url}",
            target_url=req.url,
            success=False,
            summary=str(e),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="chaos",
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scenarios")
async def chaos_list_scenarios():
    """List available chaos scenarios"""
    from services.chaos_engineering import create_chaos_service
    service = create_chaos_service()
    return {"scenarios": service.list_scenarios()}
