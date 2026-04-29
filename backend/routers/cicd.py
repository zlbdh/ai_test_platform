# -*- coding: utf-8 -*-
"""
CI/CD 集成路由 - Jenkins/GitLab Webhook & Reports
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from core.models import CICDConfigUpdateRequest, CICDWebhookPayload
from services.cicd_integration import get_cicd_service
from core.api_response import ok, safe_handler

router = APIRouter(prefix="/api/ci", tags=["CI/CD"])


@router.get("/config")
async def get_cicd_config():
    """Get CI/CD configuration"""
    service = get_cicd_service()
    return ok({"config": service.get_config()})


@router.post("/config")
async def update_cicd_config(req: CICDConfigUpdateRequest):
    """Update CI/CD configuration"""
    service = get_cicd_service()
    config = service.update_config(req.dict(exclude_none=True))
    return ok({"config": config})


@router.get("/secret")
async def get_cicd_secret():
    """Get full webhook secret (one-time display)"""
    service = get_cicd_service()
    return ok({"secret": service.get_full_secret()})


@router.post("/webhook")
@safe_handler
async def cicd_webhook(payload: CICDWebhookPayload):
    """Receive webhook trigger from CI/CD systems"""
    service = get_cicd_service()

    if not service.config.enabled:
        raise ValueError("CI/CD integration is disabled")

    trigger = service.trigger_test(
        source=payload.source,
        ref=payload.ref,
        commit=payload.commit
    )
    result = service.run_mock_tests(trigger.id)

    return ok({"trigger_id": trigger.id, "result": result})


@router.get("/history")
async def get_cicd_history():
    """Get trigger history"""
    service = get_cicd_service()
    return ok({"history": service.get_trigger_history()})


@router.get("/trigger/{trigger_id}")
async def get_trigger_details(trigger_id: str):
    """Get details of a specific trigger"""
    service = get_cicd_service()
    trigger = service.get_trigger(trigger_id)
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return ok({"trigger": trigger})


@router.get("/report/{trigger_id}/junit.xml")
async def download_junit_report(trigger_id: str):
    """Download JUnit XML report"""
    service = get_cicd_service()
    path = service.get_report_path(trigger_id, 'junit')
    if not path:
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(path, media_type='application/xml', filename=f'{trigger_id}_junit.xml')


@router.get("/report/{trigger_id}/summary.html")
async def download_html_report(trigger_id: str):
    """Download HTML summary report"""
    service = get_cicd_service()
    path = service.get_report_path(trigger_id, 'html')
    if not path:
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(path, media_type='text/html', filename=f'{trigger_id}_summary.html')
