# -*- coding: utf-8 -*-
"""
Semantic Router — Semantic testing API

Endpoints:
- POST /api/semantic/action  Execute a semantic action
- POST /api/semantic/assert  Semantic assertion
- POST /api/semantic/query   Semantic query
- POST /api/semantic/analyze Semantic page analysis
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional
from contextlib import suppress
import asyncio
import inspect
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/semantic", tags=["semantic"])


async def _resolve_page_attr(page, attr_name: str, *args, default=None, **kwargs):
    """Support reading properties and methods on async and sync Playwright Page objects."""
    try:
        value = getattr(page, attr_name)
        if callable(value):
            value = value(*args, **kwargs)
        if inspect.isawaitable(value):
            value = await value
        return default if value is None else value
    except Exception:
        return default


async def _capture_semantic_frames(session_id: str, session, page):
    try:
        while session_id in _semantic_browsers and session.get_page() is page:
            try:
                raw = await _resolve_page_attr(
                    page,
                    "screenshot",
                    type="jpeg",
                    quality=50,
                    timeout=3000,
                    default=None,
                )
                if raw:
                    session.set_frame(raw)
            except Exception:
                pass
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        raise


@router.get("/sessions")
async def list_active_sessions():
    """List all sessions with an active browser page"""
    from core.session_manager import session_manager
    all_ids = session_manager.list_sessions()
    active = []
    for sid in all_ids:
        session = session_manager.get_session(sid)
        page = session.get_page()
        if page:
            try:
                url = await _resolve_page_attr(page, "url", default="unknown")
                title = await _resolve_page_attr(page, "title", default="unknown")
            except Exception:
                url = "unknown"
                title = "unknown"
            active.append({"session_id": sid, "url": url, "title": title})
    return {"sessions": active}


class StartBrowserRequest(BaseModel):
    url: str = ""
    session_id: str = "semantic_session"

# Store the semantic testing Playwright instance for cleanup
_semantic_browsers: Dict[str, Dict[str, Any]] = {}


@router.post("/start-browser")
async def start_semantic_browser(req: StartBrowserRequest):
    """Launch a separate browser for semantic testing"""
    from core.session_manager import session_manager
    from playwright.async_api import async_playwright

    session = session_manager.get_session(req.session_id)
    page = session.get_page()
    if page:
        url = await _resolve_page_attr(page, "url", default="about:blank")
        return {"status": "already_running", "session_id": req.session_id, "url": url}

    if req.session_id in _semantic_browsers:
        await stop_semantic_browser(req.session_id)

    pw = None
    browser = None
    context = None

    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        stealth_js = """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
        window.chrome = { runtime: {} };
        """
        await context.add_init_script(stealth_js)
        page = await context.new_page()

        target_url = req.url or "about:blank"
        if req.url:
            target_url = req.url if req.url.startswith("http") else f"https://{req.url}"
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)

        session.set_page(page)
        capture_task = asyncio.create_task(_capture_semantic_frames(req.session_id, session, page))
        _semantic_browsers[req.session_id] = {
            "pw": pw,
            "browser": browser,
            "context": context,
            "page": page,
            "capture_task": capture_task,
        }
        logger.info(f"[Semantic] Browser started for session {req.session_id}")
        return {"status": "started", "session_id": req.session_id, "url": target_url}
    except Exception as e:
        session.clear()
        if context is not None:
            with suppress(Exception):
                await context.close()
        if browser is not None:
            with suppress(Exception):
                await browser.close()
        if pw is not None:
            with suppress(Exception):
                await pw.stop()
        raise HTTPException(status_code=500, detail=f"Browser launch failed: {e}")


@router.post("/stop-browser")
async def stop_semantic_browser(session_id: str = "semantic_session"):
    """Stop the semantic testing browser"""
    from core.session_manager import session_manager

    if session_id in _semantic_browsers:
        info = _semantic_browsers.pop(session_id)
        capture_task = info.get("capture_task")
        if capture_task:
            capture_task.cancel()
            with suppress(asyncio.CancelledError):
                await capture_task
        for resource_name in ("context", "browser"):
            resource = info.get(resource_name)
            if resource:
                with suppress(Exception):
                    await resource.close()
        pw = info.get("pw")
        if pw:
            with suppress(Exception):
                await pw.stop()

    session = session_manager.get_session(session_id)
    session.clear()
    session.set_frame(None)
    logger.info(f"[Semantic] Browser stopped for session {session_id}")
    return {"status": "stopped", "session_id": session_id}


class SemanticActionRequest(BaseModel):
    instruction: str
    session_id: str = "default_session"

class SemanticAssertRequest(BaseModel):
    assertion: str
    session_id: str = "default_session"

class SemanticQueryRequest(BaseModel):
    query: str
    session_id: str = "default_session"


@router.post("/action")
async def semantic_action(req: SemanticActionRequest):
    """Execute a semantic action, such as 'Click the login button' or 'Enter AI testing in the search box'"""
    from core.session_manager import session_manager

    session = session_manager.get_session(req.session_id)
    page = session.get_page()
    if not page:
        raise HTTPException(status_code=400, detail="No active browser session")

    from core.semantic_actions import ai_action
    result = await ai_action(page, req.instruction)
    return {"status": "success", **result}


@router.post("/assert")
async def semantic_assert(req: SemanticAssertRequest):
    """Evaluate a semantic assertion, such as 'The page shows a successful login' or 'There are at least five search results'"""
    from core.session_manager import session_manager

    session = session_manager.get_session(req.session_id)
    page = session.get_page()
    if not page:
        raise HTTPException(status_code=400, detail="No active browser session")

    from core.semantic_actions import ai_assert
    result = await ai_assert(page, req.assertion)
    return {"status": "success", **result}


@router.post("/query")
async def semantic_query(req: SemanticQueryRequest):
    """Query page data semantically, such as 'Get the list of search result titles'"""
    from core.session_manager import session_manager

    session = session_manager.get_session(req.session_id)
    page = session.get_page()
    if not page:
        raise HTTPException(status_code=400, detail="No active browser session")

    from core.semantic_actions import ai_query
    result = await ai_query(page, req.query)
    return {"status": "success", **result}


@router.post("/analyze")
async def semantic_analyze(session_id: str = "default_session"):
    """Analyze the current page's semantic context"""
    import base64
    from core.session_manager import session_manager
    from core.semantic_engine import get_visual_analyzer

    session = session_manager.get_session(session_id)
    page = session.get_page()
    if not page:
        raise HTTPException(status_code=400, detail="No active browser session")

    try:
        # Take a screenshot
        screenshot = await _resolve_page_attr(page, "screenshot", type="jpeg", quality=60, default=None)
        if not screenshot:
            raise RuntimeError("Cannot capture a page screenshot")
        b64 = base64.b64encode(screenshot).decode("utf-8")

        analyzer = get_visual_analyzer()
        analysis = await analyzer.analyze(b64)
        title = await _resolve_page_attr(page, "title", default="")
        url = await _resolve_page_attr(page, "url", default="")

        return {
            "status": "success",
            "url": url,
            "title": title,
            "analysis": analysis,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
