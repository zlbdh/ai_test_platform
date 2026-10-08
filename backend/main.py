from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Optional
from contextlib import asynccontextmanager
import uvicorn
import logging
import time
import os
import sys
import threading

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config import Config
from core.app_meta import API_TITLE, APP_VERSION
from core.models import TestRequest, DataFactoryRequest
from core.shared import SharedBrowserState
from core.session_manager import session_manager
from services.commander_chatops_service import get_commander_chatops_service
from services.platform_maintenance_service import get_platform_maintenance_service
from services.platform_readiness_service import get_platform_readiness_service

# Configure shared logging with trace_id and structured formatting
from core.logging_config import setup_logging, new_trace_id
setup_logging()
logger = logging.getLogger(__name__)

# ── Database initialization ──
from core.db_helper import init_db, execute_safe
init_db()


# ── Orchestrator management (thread-safe) ────────────────────────────────────────────
_orch_lock = threading.Lock()
orchestrators = {}


def get_orchestrator(session_id: str = "default_session"):
    from agents.orchestrator import Orchestrator
    with _orch_lock:
        if session_id not in orchestrators:
            orchestrators[session_id] = Orchestrator(session_id)
        return orchestrators[session_id]


# ── API key authentication dependency ────────────────────────────────────────────────────────
SYSTEM_API_KEY = os.getenv("SYSTEM_API_KEY", "")


async def require_system_key(request: Request):
    """System administration endpoint authentication — requires the X-API-Key header or SYSTEM_API_KEY environment variable"""
    if not SYSTEM_API_KEY:
        return  # Skip when no key is configured (development mode)
    key = request.headers.get("X-API-Key", "")
    if key != SYSTEM_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API Key")


# ── Lifespan (replaces deprecated on_event) ─────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    logger.info("🔥 Backend Service Started")
    # Initialize AgentBus with centralized registration from YAML profiles
    try:
        from agents.commander import Commander
        _cmd = Commander()
        logger.info("[AgentBus] Commander and profiles registered")
    except Exception as e:
        logger.warning(f"[AgentBus] Initialization failed (nonblocking): {e}")

    try:
        maintenance = get_platform_maintenance_service().run(force=True, reason="startup")
        logger.info("[Maintenance] Startup maintenance completed: %s", maintenance)
    except Exception as e:
        logger.warning(f"[Maintenance] Startup maintenance failed (nonblocking): {e}")

    yield  # ── Running ──

    # ── Shutdown ──
    logger.info("🛑 Shutting down all Orchestrators...")
    with _orch_lock:
        for sid, orch in orchestrators.items():
            try:
                orch.stop_task()
            except Exception as e:
                logger.warning(f"Failed to stop orchestrator {sid}: {e}")


app = FastAPI(title=API_TITLE, version=APP_VERSION, lifespan=lifespan)


# ── Frontend domains allowed by CORS ───────────────────────────────────────────────────────
ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:8010,http://localhost:3000,http://127.0.0.1:8010,http://localhost:5173,http://127.0.0.1:5173"
).split(",")


# ── Global exception handling + Trace-ID ──────────────────────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from core.models import APIError


@app.exception_handler(APIError)
async def api_error_handler(request, exc: APIError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": exc.message, "error_code": exc.error_code},
    )


class GlobalExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        trace_id = new_trace_id()
        t0 = time.time()
        try:
            response = await call_next(request)
            elapsed = (time.time() - t0) * 1000
            logger.info(f"{request.method} {request.url.path} → {response.status_code} ({elapsed:.0f}ms)")
            response.headers["X-Trace-Id"] = trace_id
            return response
        except HTTPException:
            raise
        except Exception as e:
            elapsed = (time.time() - t0) * 1000
            logger.error(f"{request.method} {request.url.path} → 500 ({elapsed:.0f}ms) {type(e).__name__}: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": f"Internal server error: {type(e).__name__}", "error_code": "INTERNAL_ERROR"},
                headers={"X-Trace-Id": trace_id},
            )


app.add_middleware(GlobalExceptionMiddleware)

# ── CORS — add after GlobalExceptionMiddleware to keep CORS outermost ───
# Starlette executes middleware in reverse registration order (LIFO); CORS must be outermost to add headers to every response
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Register route modules ─────────────────────────────────────────────────────────────
from routers import (
    graphql_router, ws_test_router, grpc_router, database_router,
    testing_router, knowledge_router,
    cicd_router, ai_enhancement_router, auth_router,
    requirement_router, platform_router, setup_platform_routes,
    advanced_testing_router, oauth_router,
    core_router, setup_core_routes,
    plan_router, history_router, data_router, report_router,
    commander_router, deploy_router, exploration_router, release_router,
)
from routers.accessibility import router as accessibility_router
from routers.i18n import router as i18n_router
from routers.compliance import router as compliance_router
from routers.chaos import router as chaos_router
from routers.mobile import router as mobile_router
from routers.workbench import router as workbench_router
from routers.evaluation import router as evaluation_router
from routers.semantic import router as semantic_router
from routers.quality_gate import router as quality_gate_router
from routers.notification import router as notification_router
from routers.scheduler import router as scheduler_router
from routers.analytics import router as analytics_router
from routers.testdata import router as testdata_router
from routers.scenario import router as scenario_router
from routers.visual import router as visual_router
from routers.session_bootstrap import router as session_bootstrap_router

setup_core_routes(get_orchestrator, SharedBrowserState, TestRequest)

from routers.cookie import setup_cookie_routes
cookie_router = setup_cookie_routes(SharedBrowserState)

for r in [
    graphql_router, ws_test_router, grpc_router, database_router,
    accessibility_router, i18n_router, compliance_router, chaos_router,
    mobile_router, testing_router, workbench_router, knowledge_router,
    cicd_router, ai_enhancement_router, auth_router,
    requirement_router, platform_router, advanced_testing_router, oauth_router,
    core_router, plan_router, history_router, data_router, report_router,
    cookie_router, commander_router, evaluation_router, semantic_router, quality_gate_router,
    notification_router, scheduler_router, analytics_router, testdata_router, scenario_router, visual_router,
    session_bootstrap_router, deploy_router, exploration_router, release_router,
]:
    app.include_router(r)

setup_platform_routes(app)


# ── Mount static report files ─────────────────────────────────────────────────────────
from fastapi.staticfiles import StaticFiles

try:
    report_dir = os.path.join(Config.PROJECT_ROOT, "data", "allure-report")
    os.makedirs(report_dir, exist_ok=True)
    app.mount("/reports", StaticFiles(directory=report_dir, html=True), name="reports")
except Exception as e:
    logger.warning(f"Could not mount reports directory: {e}")


# ── Health Check ─────────────────────────────────────────────────────────────
@app.get("/api/health")
async def api_health():
    """System health check"""
    from core.db_helper import get_connection, get_db_observability
    cfg = Config()
    db_ok = False
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")
            db_ok = True
    except Exception:
        pass

    llm_configured = bool(
        cfg.OPENAI_API_KEY or cfg.GEMINI_API_KEY or
        cfg.DEEPSEEK_API_KEY or cfg.CHATGLM_API_KEY or
        cfg.ANTHROPIC_API_KEY
    )

    with _orch_lock:
        any_running = any(o.is_running for o in orchestrators.values())

    maintenance_status = get_platform_maintenance_service().get_status()
    readiness = get_platform_readiness_service().evaluate()
    db_observability = get_db_observability()
    notification_snapshot = maintenance_status.get("notification") or {}
    data_quality_snapshot = maintenance_status.get("data_quality") or {}
    chatops_snapshot = get_commander_chatops_service().get_overview(allow_live_probe=False)

    status_code = 200 if (db_ok and llm_configured) else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if status_code == 200 else "degraded",
            "version": app.version,
            "checks": {
                "database": "ok" if db_ok else "unreachable",
                "database_path": db_observability["path"],
                "database_shadow_paths": db_observability["shadow_paths"],
                "database_shadow_count": db_observability["shadow_count"],
                "database_consistency": db_observability["risk_level"],
                "notification_webhook_count": int(notification_snapshot.get("webhook_count") or 0),
                "notification_tested_webhook_count": int(notification_snapshot.get("tested_enabled") or 0),
                "notification_healthy_webhook_count": int(notification_snapshot.get("healthy_enabled") or 0),
                "notification_untested_webhook_count": int(notification_snapshot.get("untested_enabled") or 0),
                "notification_ready": bool(notification_snapshot.get("ready")),
                "commander_chatops_ready": bool(chatops_snapshot.get("ready")),
                "commander_chatops_platform_ready": bool(chatops_snapshot.get("platform_ready")),
                "commander_chatops_external_connected": bool(chatops_snapshot.get("external_connected")),
                "commander_chatops_external_connected_current": bool(chatops_snapshot.get("external_connected_current", chatops_snapshot.get("external_connected"))),
                "commander_chatops_external_connected_history_observed": bool(chatops_snapshot.get("external_connected_history_observed")),
                "commander_chatops_external_connection_stale": bool(chatops_snapshot.get("external_connection_stale")),
                "commander_chatops_external_callback_ready": bool(chatops_snapshot.get("external_callback_ready")),
                "commander_chatops_external_self_check_recent_success": bool(chatops_snapshot.get("external_self_check_recent_success")),
                "commander_chatops_direct_chat_ready": bool(chatops_snapshot.get("direct_chat_ready")),
                "commander_chatops_app_bot_configured": bool(chatops_snapshot.get("app_bot_configured")),
                "commander_chatops_app_bot_ready": bool(chatops_snapshot.get("app_bot_ready")),
                "commander_chatops_app_bot_check": chatops_snapshot.get("app_bot_check") or {},
                "commander_chatops_unified_robot_target": bool(chatops_snapshot.get("unified_robot_target")),
                "commander_chatops_unified_robot_platform_ready": bool(chatops_snapshot.get("unified_robot_platform_ready")),
                "commander_chatops_unified_robot_ready": bool(chatops_snapshot.get("unified_robot_ready")),
                "commander_chatops_delivery_strategy": str(chatops_snapshot.get("delivery_strategy") or ""),
                "commander_chatops_delivery_strategy_summary": str(chatops_snapshot.get("delivery_strategy_summary") or ""),
                "commander_chatops_verification_token_configured": bool(chatops_snapshot.get("verification_token_configured")),
                "commander_chatops_callback_provider": chatops_snapshot.get("callback_provider") or {},
                "commander_chatops_callback_recommendation": str(chatops_snapshot.get("callback_recommendation") or ""),
                "commander_chatops_callback_probe_attempted": bool((chatops_snapshot.get("callback_probe") or {}).get("attempted")),
                "commander_chatops_callback_probe_success": bool((chatops_snapshot.get("callback_probe") or {}).get("success")),
                "commander_chatops_callback_probe_issue": str((chatops_snapshot.get("callback_probe") or {}).get("issue") or ""),
                "commander_chatops_callback_probe_summary": str((chatops_snapshot.get("callback_probe") or {}).get("summary") or ""),
                "commander_chatops_latest_external_success_at": str(chatops_snapshot.get("latest_external_success_at") or ""),
                "commander_chatops_latest_external_self_check_at": str(chatops_snapshot.get("latest_external_self_check_at") or ""),
                "maintenance_suspect_history_count": int(data_quality_snapshot.get("suspect_history_count") or 0),
                "maintenance_archived_history_count": int(data_quality_snapshot.get("archived_history_count") or 0),
                "maintenance_history_clean": bool(data_quality_snapshot.get("clean", True)),
                "readiness_stage": readiness.get("stage"),
                "readiness_score": readiness.get("score"),
                "llm_configured": llm_configured,
                "llm_provider": cfg.LLM_PROVIDER,
                "task_running": any_running,
                "maintenance": maintenance_status,
            },
        },
    )


@app.get("/")
def read_root():
    return {"status": "ok", "message": "AI Test Platform Backend is running"}


# ── Data Factory API ─────────────────────────────────────────────────────────
from core.data_factory import get_data_factory


@app.get("/api/data-factory/types")
async def get_data_types():
    return {"status": "success", "types": get_data_factory().get_available_types()}


@app.post("/api/data-factory/generate")
async def api_generate_factory_data(req: DataFactoryRequest):
    factory = get_data_factory()
    data = factory.generate(req.template) if req.count == 1 else factory.generate_batch(req.template, req.count)
    return {"status": "success", "data": data}


# ── WebSocket Sandbox ────────────────────────────────────────────────────────
import asyncio
import base64
import json
from fastapi import WebSocket, WebSocketDisconnect
import queue as thread_queue


@app.websocket("/ws/sandbox")
async def websocket_sandbox(websocket: WebSocket, session_id: str = "default_session"):
    await websocket.accept()
    logger.info(f"WS Sandbox Connected (session: {session_id})")

    session = session_manager.get_session(session_id)

    max_retries = 120
    retry = 0
    while not session.get_page():
        if retry > max_retries:
            await websocket.send_json({"type": "status", "message": "Wait timed out. Start a test task first"})
            await websocket.close(code=1000, reason="No active browser session")
            return
        if retry % 10 == 0:
            await websocket.send_json({"type": "status", "message": f"Waiting for a browser session... ({retry // 2}s)"})
        await asyncio.sleep(0.5)
        retry += 1

    await websocket.send_json({"type": "status", "message": "Browser session connected"})

    frame_queue = thread_queue.Queue(maxsize=2)
    stop_event = threading.Event()

    def screenshot_worker():
        last_frame = None
        while not stop_event.is_set():
            try:
                frame_bytes = session.get_frame()
                if frame_bytes and frame_bytes is not last_frame:
                    last_frame = frame_bytes
                    frame_b64 = base64.b64encode(frame_bytes).decode("utf-8")
                    try:
                        frame_queue.put_nowait(frame_b64)
                    except thread_queue.Full:
                        try:
                            frame_queue.get_nowait()
                        except thread_queue.Empty:
                            pass
                        frame_queue.put_nowait(frame_b64)
            except Exception:
                pass
            stop_event.wait(0.15)

    screenshot_thread = threading.Thread(target=screenshot_worker, daemon=True)
    screenshot_thread.start()

    try:
        async def send_frames():
            while True:
                try:
                    frame_data = await asyncio.to_thread(frame_queue.get, timeout=1.0)
                    await websocket.send_json({"type": "frame", "data": frame_data})
                except thread_queue.Empty:
                    if not session.get_page():
                        await websocket.send_json({"type": "status", "message": "Browser session ended"})
                        break
                except Exception:
                    break

        async def receive_commands():
            while True:
                try:
                    data = await websocket.receive_text()
                    cmd = json.loads(data)
                    if not session.get_page():
                        continue
                    if cmd["type"] == "click":
                        await session.run_browser(lambda page: page.mouse.click(cmd["x"], cmd["y"]))
                    elif cmd["type"] == "type":
                        await session.run_browser(lambda page: page.keyboard.type(cmd["text"]))
                    elif cmd["type"] == "scroll":
                        await session.run_browser(lambda page: page.mouse.wheel(0, cmd.get("deltaY", 0)))
                except (WebSocketDisconnect, Exception):
                    break

        done, pending = await asyncio.wait(
            [asyncio.create_task(send_frames()), asyncio.create_task(receive_commands())],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        logger.info("WS Sandbox Disconnected")
    except Exception as e:
        logger.error(f"WS Error: {e}")
    finally:
        stop_event.set()
        screenshot_thread.join(timeout=2)


# ── System Management（Requires API key） ────────────────────────────────────────
@app.post("/api/system/db/reset", dependencies=[Depends(require_system_key)])
async def system_db_reset():
    """Clear history and report data (requires the X-API-Key header)"""
    import glob
    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    if os.path.exists(report_dir):
        for f in glob.glob(os.path.join(report_dir, "*")):
            os.remove(f)
    history_file = os.path.join(os.path.dirname(__file__), "data", "history.json")
    if os.path.exists(history_file):
        with open(history_file, "w", encoding="utf-8") as f:
            f.write("[]")
    execute_safe("DELETE FROM test_runs")
    execute_safe("DELETE FROM test_records")
    return {"status": "success", "message": "Database reset"}


@app.post("/api/system/db/backup", dependencies=[Depends(require_system_key)])
async def system_db_backup():
    """Back up the data directory (requires the X-API-Key header)"""
    import shutil
    from datetime import datetime
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    if not os.path.exists(data_dir):
        raise HTTPException(status_code=404, detail="Data directory does not exist")
    backup_name = f"data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_path = os.path.join(os.path.dirname(__file__), backup_name)
    shutil.copytree(data_dir, backup_path)
    return {"status": "success", "message": f"Backup completed: {backup_name}"}


# ── Main Entry ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8020, reload=True)

