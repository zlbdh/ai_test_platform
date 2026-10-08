# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

import asyncio
import pytest

from core.session_manager import SessionManager
from routers.semantic import (
    StartBrowserRequest,
    _semantic_browsers,
    list_active_sessions,
    semantic_analyze,
    start_semantic_browser,
    stop_semantic_browser,
)


class AsyncRouterPageStub:
    def __init__(self):
        self.url = "about:blank"

    async def goto(self, url, wait_until=None, timeout=None):
        self.url = url

    async def screenshot(self, **kwargs):
        return b"frame-bytes"

    async def title(self):
        return "Semantic test page"


class AsyncRouterContextStub:
    def __init__(self, page):
        self.page = page
        self.closed = False
        self.init_scripts = []

    async def add_init_script(self, script):
        self.init_scripts.append(script)

    async def new_page(self):
        return self.page

    async def close(self):
        self.closed = True


class AsyncRouterBrowserStub:
    def __init__(self, context):
        self.context = context
        self.closed = False

    async def new_context(self, **kwargs):
        return self.context

    async def close(self):
        self.closed = True


class AsyncRouterPlaywrightStub:
    def __init__(self, browser):
        self.chromium = SimpleNamespace(launch=self._launch)
        self.browser = browser
        self.stopped = False

    async def _launch(self, **kwargs):
        return self.browser

    async def stop(self):
        self.stopped = True


class AsyncPlaywrightStarterStub:
    def __init__(self, playwright):
        self.playwright = playwright

    async def start(self):
        return self.playwright


@pytest.fixture(autouse=True)
def _cleanup_semantic_sessions():
    SessionManager._sessions.clear()
    for info in list(_semantic_browsers.values()):
        task = info.get("capture_task")
        if task:
            task.cancel()
    _semantic_browsers.clear()
    yield
    for info in list(_semantic_browsers.values()):
        task = info.get("capture_task")
        if task:
            task.cancel()
    _semantic_browsers.clear()
    SessionManager._sessions.clear()


@pytest.mark.asyncio
async def test_start_and_stop_semantic_browser_with_async_playwright():
    page = AsyncRouterPageStub()
    context = AsyncRouterContextStub(page)
    browser = AsyncRouterBrowserStub(context)
    playwright = AsyncRouterPlaywrightStub(browser)
    starter = AsyncPlaywrightStarterStub(playwright)

    with patch("playwright.async_api.async_playwright", return_value=starter):
        result = await start_semantic_browser(
            StartBrowserRequest(url="example.com", session_id="semantic_router_test")
        )
        await asyncio.sleep(0.01)

        session = SessionManager.get_session("semantic_router_test")
        assert result["status"] == "started"
        assert result["url"] == "https://example.com"
        assert session.get_page() is page
        assert session.get_frame() == b"frame-bytes"
        assert "semantic_router_test" in _semantic_browsers

        stopped = await stop_semantic_browser("semantic_router_test")

    assert stopped["status"] == "stopped"
    assert browser.closed is True
    assert context.closed is True
    assert playwright.stopped is True
    assert SessionManager.get_session("semantic_router_test").get_page() is None


@pytest.mark.asyncio
async def test_list_active_sessions_reads_async_titles():
    session = SessionManager.get_session("semantic_list_test")
    page = AsyncRouterPageStub()
    page.url = "https://example.com/semantic"
    session.set_page(page)

    result = await list_active_sessions()

    assert result["sessions"] == [
        {
            "session_id": "semantic_list_test",
            "url": "https://example.com/semantic",
            "title": "Semantic test page",
        }
    ]


@pytest.mark.asyncio
async def test_semantic_analyze_returns_success_payload():
    session = SessionManager.get_session("semantic_analyze_test")
    page = AsyncRouterPageStub()
    session.set_page(page)

    with patch("core.semantic_engine.get_visual_analyzer") as mock_get_analyzer:
        analyzer = SimpleNamespace(analyze=AsyncMock(return_value={"elements": 3}))
        mock_get_analyzer.return_value = analyzer
        result = await semantic_analyze("semantic_analyze_test")

    assert result["status"] == "success"
    assert result["title"] == "Semantic test page"
    assert result["analysis"] == {"elements": 3}
