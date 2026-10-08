# -*- coding: utf-8 -*-
"""
Core routes: task start/stop/SSE stream/status/control
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from core.session_manager import session_manager, SessionManager
from core.models import PauseRequest

router = APIRouter(tags=["core"])


def setup_core_routes(orchestrator, SharedBrowserState, TestRequest):
    """Register core routes with an orchestrator dependency"""

    def resolve_runtime(session_id: str = ""):
        sid = session_id or SessionManager.DEFAULT_SESSION_ID
        orch = orchestrator(sid) if callable(orchestrator) else orchestrator
        session = getattr(orch, "session", None) or session_manager.get_session(sid)
        return sid, orch, session

    @router.post("/api/start")
    async def start_task(request: TestRequest):
        """Start a test task"""
        _, orch, _ = resolve_runtime(request.session_id or "")
        if orch.is_running:
            raise HTTPException(status_code=409, detail="Task already running")
        planner_mode = request.planner_mode or "smart"
        task_id = orch.start_task(
            request.requirement,
            mode=planner_mode,
            target_url=request.target_url or "",
            browser_mode=request.browser_mode or "chromium",
            execution_group_id=request.execution_group_id or "",
            execution_mode=request.execution_mode or "default",
            interaction_policy=request.interaction_policy or "default",
        )
        return {
            "status": "started",
            "task_id": task_id,
            "planner_mode": planner_mode,
            "execution_mode": getattr(orch, "_execution_mode", "default"),
            "interaction_policy": getattr(orch, "_interaction_policy", "default"),
        }

    @router.post("/api/stop")
    async def stop_task(session_id: str = SessionManager.DEFAULT_SESSION_ID):
        """Force a task to stop"""
        _, orch, _ = resolve_runtime(session_id)
        orch.stop_task()
        return {"status": "stopped"}

    @router.get("/api/stream")
    async def stream_logs(request: Request):
        """SSE Log Stream — Supports Last-Event-ID reconnection"""
        session_id = request.query_params.get("session_id", SessionManager.DEFAULT_SESSION_ID)
        start_seq = 0
        if request:
            last_id = request.headers.get("last-event-id", "0")
            try:
                start_seq = int(last_id)
            except (ValueError, TypeError):
                start_seq = 0
        _, orch, _ = resolve_runtime(session_id)
        return StreamingResponse(
            orch.stream_logs(start_seq=start_seq),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )

    @router.get("/api/status")
    async def api_status(session_id: str = SessionManager.DEFAULT_SESSION_ID):
        """Get system status"""
        _, orch, session = resolve_runtime(session_id)
        status, task = session.get_status()
        signal = session.get_signal()
        reason = session.get_pause_reason()
        has_page = session.get_page() is not None
        screenshot = session.get_intervention_screenshot()

        return {
            "status": status,
            "task": task,
            "task_display": getattr(orch, "_task_requirement_display", "") or task,
            "task_text_state": getattr(orch, "_task_text_state", "normal"),
            "execution_mode": getattr(orch, "_execution_mode", "default"),
            "interaction_policy": getattr(orch, "_interaction_policy", "default"),
            "step_budget": getattr(orch, "_step_budget", None),
            "signal": signal,
            "pause_reason": reason,
            "active_task_id": orch.active_task_id,
            "is_running": orch.is_running,
            "has_browser": has_page,
            "intervention_screenshot": screenshot
        }

    @router.post("/api/control/pause")
    async def api_control_pause(session_id: str = SessionManager.DEFAULT_SESSION_ID):
        _, _, session = resolve_runtime(session_id)
        session.set_signal("PAUSED", reason="User Request")
        return {"status": "ok", "signal": "PAUSED"}

    @router.post("/api/control/resume")
    async def api_control_resume(session_id: str = SessionManager.DEFAULT_SESSION_ID):
        _, _, session = resolve_runtime(session_id)
        session.set_signal("RUNNING")
        return {"status": "ok", "signal": "RUNNING"}

    @router.post("/api/control/suspend")
    async def api_control_suspend(request: PauseRequest):
        """Downgrade Intervention to Pause (Hide Modal, Keep Waiting)"""
        _, _, session = resolve_runtime(request.session_id or "")
        session.set_signal("PAUSED", reason=request.reason)
        return {"status": "suspended", "signal": "PAUSED", "reason": request.reason}

    @router.post("/api/control/stop")
    async def api_control_stop(session_id: str = SessionManager.DEFAULT_SESSION_ID):
        _, orch, session = resolve_runtime(session_id)
        session.set_signal("STOPPED")
        orch.stop_task()
        return {"status": "ok", "signal": "STOPPED"}

    return router
