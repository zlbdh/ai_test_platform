# -*- coding: utf-8 -*-
"""
i18n 测试路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from services.execution_center_service import get_execution_center_service

router = APIRouter(prefix="/api/i18n", tags=["i18n"])


class I18nTestRequest(BaseModel):
    url: str
    locales: List[str] = ["zh-CN", "en-US"]
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


class I18nQuickCheckRequest(BaseModel):
    url: str
    locale: str = "zh-CN"
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


@router.post("/test")
async def i18n_test(req: I18nTestRequest):
    """多语言测试（需要 Playwright）"""
    from services.i18n_testing import create_i18n_service
    try:
        service = create_i18n_service()
        report = await service.test_locale(req.url, req.locales)
        payload = report.to_dict()
        get_execution_center_service().record_i18n_result(
            payload,
            quick=False,
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
        )
        return payload
    except Exception as e:
        get_execution_center_service().record_i18n_result(
            {"url": req.url, "status": "error", "error": str(e), "score": -1, "total_issues": 0, "issues": []},
            quick=False,
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick-check")
async def i18n_quick_check(req: I18nQuickCheckRequest):
    """快速 i18n 检查（HTTP 静态分析）"""
    from services.i18n_testing import create_i18n_service
    try:
        service = create_i18n_service()
        payload = await service.quick_check(req.url, req.locale)
        get_execution_center_service().record_i18n_result(
            payload,
            quick=True,
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
        )
        return payload
    except Exception as e:
        get_execution_center_service().record_i18n_result(
            {"url": req.url, "status": "error", "error": str(e), "score": -1, "total": 0, "issues": [], "locale": req.locale},
            quick=True,
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
        )
        raise HTTPException(status_code=500, detail=str(e))
