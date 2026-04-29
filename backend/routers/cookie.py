# -*- coding: utf-8 -*-
"""
Cookie 管理路由 — REST API 端点
支持: 导出/导入 Cookie、管理预置 Auth Profile
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["cookie"])


class CookieExportRequest(BaseModel):
    name: str
    domain: Optional[str] = None


class CookieImportRequest(BaseModel):
    name: str


class PresetSaveRequest(BaseModel):
    preset_name: str
    cookie_name: str


def setup_cookie_routes(SharedBrowserState):
    """注册 Cookie 管理路由，注入 SharedBrowserState 依赖"""
    from core.session_manager import session_manager

    def _get_session(session_id: str):
        return session_manager.get_session(session_id)

    @router.get("/api/cookies/list")
    async def list_cookies():
        """列出所有已保存的 Cookie 文件"""
        from core.cookie_manager import cookie_manager
        return {"cookies": cookie_manager.list_saved()}

    @router.post("/api/cookies/export")
    async def export_cookies(req: CookieExportRequest, session_id: str = "default_session"):
        """从当前浏览器页面导出 Cookie"""
        session = _get_session(session_id)
        if not session.get_page():
            raise HTTPException(status_code=400, detail="No active browser page")
        from core.cookie_manager import cookie_manager
        cookies = await session.run_browser(lambda page: page.context.cookies())
        result = cookie_manager.save_cookie_payload(cookies, req.name, req.domain)
        return {"status": "success", **result}

    @router.post("/api/cookies/import")
    async def import_cookies(req: CookieImportRequest, session_id: str = "default_session"):
        """导入 Cookie 到当前浏览器上下文"""
        session = _get_session(session_id)
        if not session.get_page():
            raise HTTPException(status_code=400, detail="No active browser page")
        from core.cookie_manager import cookie_manager
        try:
            cookies = cookie_manager.load_cookie_payload(req.name)
            await session.run_browser(lambda page: page.context.add_cookies(cookies))
            result = {"count": len(cookies), "name": req.name}
            return {"status": "success", **result}
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @router.delete("/api/cookies/{name}")
    async def delete_cookie(name: str):
        """删除已保存的 Cookie 文件"""
        from core.cookie_manager import cookie_manager
        if cookie_manager.delete_saved(name):
            return {"status": "deleted", "name": name}
        raise HTTPException(status_code=404, detail=f"Cookie file not found: {name}")

    # --- Preset 端点 ---

    @router.get("/api/cookies/presets")
    async def list_presets():
        """列出预置 Auth Profile"""
        from core.cookie_manager import cookie_manager
        return {"presets": cookie_manager.list_presets()}

    @router.post("/api/cookies/presets")
    async def save_preset(req: PresetSaveRequest):
        """保存预置 Auth Profile"""
        from core.cookie_manager import cookie_manager
        try:
            cookie_manager.save_preset(req.preset_name, req.cookie_name)
            return {"status": "saved", "preset": req.preset_name}
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @router.delete("/api/cookies/presets/{preset_name}")
    async def delete_preset(preset_name: str):
        """删除预置 Auth Profile"""
        from core.cookie_manager import cookie_manager
        if cookie_manager.delete_preset(preset_name):
            return {"status": "deleted", "preset": preset_name}
        raise HTTPException(status_code=404, detail=f"Preset not found: {preset_name}")

    @router.post("/api/cookies/presets/{preset_name}/inject")
    async def inject_preset(preset_name: str, session_id: str = "default_session"):
        """注入预置 Cookie 到当前浏览器（跳过登录流程）"""
        session = _get_session(session_id)
        if not session.get_page():
            raise HTTPException(status_code=400, detail="No active browser page")
        from core.cookie_manager import cookie_manager
        try:
            if not cookie_manager.list_presets():
                raise ValueError("No presets configured")
            presets = {item["name"]: item["cookie_file"] for item in cookie_manager.list_presets()}
            if preset_name not in presets:
                raise ValueError(f"Preset not found: {preset_name}")
            cookies = cookie_manager.load_cookie_payload(presets[preset_name])
            await session.run_browser(lambda page: page.context.add_cookies(cookies))
            result = {"count": len(cookies), "name": presets[preset_name], "preset": preset_name}
            return {"status": "injected", **result}
        except (ValueError, FileNotFoundError) as e:
            raise HTTPException(status_code=404, detail=str(e))

    return router
