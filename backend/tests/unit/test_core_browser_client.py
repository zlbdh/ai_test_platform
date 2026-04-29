import inspect
from unittest.mock import AsyncMock, patch

import pytest


class _FakeAccessibility:
    def snapshot(self):
        return {"role": "button", "name": "Submit", "children": []}


class _FakePage:
    def __init__(self):
        self.url = "about:blank"
        self.accessibility = _FakeAccessibility()
        self.clicked = None

    def goto(self, url, wait_until=None):
        self.url = url
        return None

    def title(self):
        return "Example Title"

    def click(self, selector):
        self.clicked = selector
        return None


def _make_browser(fake_page):
    browser = AsyncMock()
    browser.get_page = AsyncMock(return_value=fake_page)

    async def run_browser(callback, session_id="default_session", timeout=10.0):
        result = callback(fake_page)
        if inspect.isawaitable(result):
            return await result
        return result

    browser.run_browser = AsyncMock(side_effect=run_browser)
    return browser


@pytest.mark.asyncio
async def test_open_uses_browser_bridge_and_returns_page_info():
    from skills.core_browser_client import execute_browser_command

    fake_page = _FakePage()
    browser = _make_browser(fake_page)

    with patch("skills.core_browser_client.SharedBrowser", return_value=browser):
        result = await execute_browser_command("open", ["https://example.com"], session_id="default")

    assert result["success"] is True
    assert result["result"]["url"] == "https://example.com"
    assert result["result"]["title"] == "Example Title"
    for call in browser.run_browser.await_args_list:
        assert call.kwargs["session_id"] == "default_session"


@pytest.mark.asyncio
async def test_click_normalizes_default_session_and_executes_via_bridge():
    from skills.core_browser_client import execute_browser_command

    fake_page = _FakePage()
    browser = _make_browser(fake_page)

    with patch("skills.core_browser_client.SharedBrowser", return_value=browser):
        result = await execute_browser_command("click", ["#submit"])

    assert result == {"success": True, "result": "clicked"}
    assert fake_page.clicked == "#submit"
    browser.run_browser.assert_awaited_once()
    assert browser.run_browser.await_args.kwargs["session_id"] == "default_session"


@pytest.mark.asyncio
async def test_launch_returns_error_when_browser_session_missing():
    from skills.core_browser_client import execute_browser_command

    browser = AsyncMock()
    browser.get_page = AsyncMock(return_value=None)
    browser.run_browser = AsyncMock()

    with patch("skills.core_browser_client.SharedBrowser", return_value=browser):
        result = await execute_browser_command("launch", [], session_id="default")

    assert result["success"] is False
    assert "No active browser session" in result["error"]
    browser.get_page.assert_awaited_once_with(session_id="default_session")
