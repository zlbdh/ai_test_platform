# -*- coding: utf-8 -*-
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.session_bootstrap import apply_auth_bootstrap
from core.session_manager import SessionManager, session_manager

router = APIRouter(prefix="/api/session", tags=["session"])


class AuthBootstrapRequest(BaseModel):
    session_id: str = SessionManager.DEFAULT_SESSION_ID
    base_url: str
    username: str = ""
    password: str = ""
    access_token: str = ""
    login_path: str = "/auth/login1"
    token_cookie_name: str = "Admin-Token"
    bootstrap_landing_path: str = "/qyLogin"
    target_path: Optional[str] = None
    station_id: Optional[str] = None
    city: Optional[str] = None
    switch_station_path: str = "/system/user/switchCityStation"
    local_storage: Dict[str, Any] = Field(default_factory=dict)
    apply_now: bool = False


@router.post("/bootstrap-auth")
async def bootstrap_auth(req: AuthBootstrapRequest):
    session = session_manager.get_session(req.session_id or SessionManager.DEFAULT_SESSION_ID)
    payload = req.model_dump()
    payload["session_id"] = req.session_id or SessionManager.DEFAULT_SESSION_ID

    session.set_context("auth_bootstrap", payload)
    session.set_context("auth_bootstrap_applied", False)
    session.set_context("auth_bootstrap_result", {})

    result = None
    if req.apply_now:
        if session.get_page() is None:
            raise HTTPException(status_code=400, detail="当前会话没有活跃浏览器页面，无法立即应用预认证")
        try:
            result = await session.run_browser(lambda page: apply_auth_bootstrap(page, payload), timeout=45.0)
            session.set_context("auth_bootstrap_applied", True)
            session.set_context("auth_bootstrap_result", result)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"预认证应用失败: {exc}") from exc

    return {
        "status": "success",
        "message": "会话预认证配置已保存",
        "data": {
            "session_id": payload["session_id"],
            "stored": True,
            "applied": bool(result),
            "result": result or {},
        },
    }
