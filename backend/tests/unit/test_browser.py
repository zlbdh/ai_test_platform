"""
core/browser.py unit tests.
Covers _new_page_state, _process_dom_indexer, _fill_evaluate_results,
format_page_state_for_log, and the SharedBrowser singleton.
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


def _run(coro):
    return asyncio.run(coro)


class TestNewPageState:
    def test_returns_dict(self):
        from core.browser import _new_page_state
        state = _new_page_state()
        assert isinstance(state, dict)

    def test_default_keys(self):
        from core.browser import _new_page_state
        state = _new_page_state()
        expected_keys = {"url", "title", "interactive_elements", "element_count",
                         "visible_text", "scroll_info", "alerts", "new_elements"}
        assert set(state.keys()) == expected_keys

    def test_default_values(self):
        from core.browser import _new_page_state
        state = _new_page_state()
        assert state["url"] == ""
        assert state["title"] == ""
        assert state["interactive_elements"] == ""
        assert state["element_count"] == 0
        assert state["visible_text"] == ""
        assert state["scroll_info"] == {}
        assert state["alerts"] == []
        assert state["new_elements"] == []

    def test_returns_new_instance(self):
        from core.browser import _new_page_state
        s1 = _new_page_state()
        s2 = _new_page_state()
        assert s1 is not s2


class TestProcessDomIndexer:
    def test_fills_state(self):
        from core.browser import _process_dom_indexer
        state = {"interactive_elements": "", "element_count": 0, "new_elements": []}
        mock_indexer = MagicMock()
        mock_indexer.format_for_llm.return_value = "[1] <button> Login"
        mock_indexer._index_map = {"btn1": {}, "btn2": {}}
        mock_indexer.get_new_elements.return_value = []
        _process_dom_indexer(state, mock_indexer)
        assert state["interactive_elements"] == "[1] <button> Login"
        assert state["element_count"] == 2

    def test_with_new_elements(self):
        from core.browser import _process_dom_indexer
        state = {"interactive_elements": "", "element_count": 0, "new_elements": []}
        mock_indexer = MagicMock()
        mock_indexer.format_for_llm.return_value = ""
        mock_indexer._index_map = {}
        mock_indexer.get_new_elements.return_value = [
            {"idx": 1, "tag": "button", "text": "Submit"},
            {"idx": 2, "tag": "a", "text": "Link"},
        ]
        _process_dom_indexer(state, mock_indexer)
        assert len(state["new_elements"]) == 2
        assert "<button>" in state["new_elements"][0]

    def test_handles_exception(self):
        from core.browser import _process_dom_indexer
        state = {"interactive_elements": "", "element_count": 0, "new_elements": []}
        mock_indexer = MagicMock()
        mock_indexer.format_for_llm.side_effect = Exception("scan error")
        _process_dom_indexer(state, mock_indexer)
        assert state["element_count"] == 0


class TestFillEvaluateResults:
    def test_fills_all(self):
        from core.browser import _fill_evaluate_results
        state = {"visible_text": "", "scroll_info": {}, "alerts": []}
        _fill_evaluate_results(state, "Hello World", {"can_scroll_down": True}, ["alert1"])
        assert state["visible_text"] == "Hello World"
        assert state["scroll_info"]["can_scroll_down"] is True
        assert state["alerts"] == ["alert1"]

    def test_truncates_text(self):
        from core.browser import _fill_evaluate_results
        state = {"visible_text": "", "scroll_info": {}, "alerts": []}
        long_text = "a" * 3000
        _fill_evaluate_results(state, long_text, {}, [])
        assert len(state["visible_text"]) == 800

    def test_handles_none(self):
        from core.browser import _fill_evaluate_results
        state = {"visible_text": "", "scroll_info": {}, "alerts": []}
        _fill_evaluate_results(state, None, None, None)
        assert state["visible_text"] == ""
        assert state["scroll_info"] == {}
        assert state["alerts"] == []


class TestFormatPageStateForLog:
    def test_basic(self):
        from core.browser import format_page_state_for_log
        state = {
            "url": "http://example.com",
            "title": "Example",
            "element_count": 5,
            "scroll_info": {},
            "alerts": [],
            "new_elements": [],
        }
        output = format_page_state_for_log(state)
        assert "example.com" in output
        assert "Example" in output
        assert "5" in output

    def test_with_scroll(self):
        from core.browser import format_page_state_for_log
        state = {
            "url": "http://a.com", "title": "A",
            "element_count": 0,
            "scroll_info": {"scroll_percent": 50, "can_scroll_down": True, "pixels_below": 300},
            "alerts": [], "new_elements": [],
        }
        output = format_page_state_for_log(state)
        assert "50%" in output
        assert "300px" in output

    def test_with_alerts(self):
        from core.browser import format_page_state_for_log
        state = {
            "url": "", "title": "", "element_count": 0,
            "scroll_info": {},
            "alerts": ["弹窗: 确认删除？"],
            "new_elements": [],
        }
        output = format_page_state_for_log(state)
        assert "弹窗" in output

    def test_with_new_elements(self):
        from core.browser import format_page_state_for_log
        state = {
            "url": "", "title": "", "element_count": 0,
            "scroll_info": {},
            "alerts": [],
            "new_elements": ["*[1]<button>Submit"],
        }
        output = format_page_state_for_log(state)
        assert "Submit" in output

    def test_empty_state(self):
        from core.browser import format_page_state_for_log
        state = {
            "url": "", "title": "", "element_count": 0,
            "scroll_info": {}, "alerts": [], "new_elements": [],
        }
        output = format_page_state_for_log(state)
        assert "URL" in output


class TestSharedBrowser:
    def test_singleton(self):
        from core.browser import SharedBrowser
        b1 = SharedBrowser()
        b2 = SharedBrowser()
        assert b1 is b2

    @patch("core.session_manager.session_manager")
    def test_get_page(self, mock_sm):
        from core.browser import SharedBrowser
        mock_session = MagicMock()
        mock_session.get_page.return_value = "mock_page"
        mock_sm.get_session.return_value = mock_session
        b = SharedBrowser()
        result = _run(b.get_page())
        assert result == "mock_page"

    @patch("core.session_manager.session_manager")
    def test_get_page_none(self, mock_sm):
        from core.browser import SharedBrowser
        mock_session = MagicMock()
        mock_session.get_page.return_value = None
        mock_sm.get_session.return_value = mock_session
        b = SharedBrowser()
        result = _run(b.get_page())
        assert result is None

    @patch("core.session_manager.session_manager")
    def test_run_browser(self, mock_sm):
        from core.browser import SharedBrowser
        mock_session = MagicMock()
        mock_session.run_browser = AsyncMock(return_value="ok")
        mock_sm.get_session.return_value = mock_session
        b = SharedBrowser()
        result = _run(
            b.run_browser(lambda page: page, session_id="default", timeout=12.0)
        )
        assert result == "ok"
        mock_sm.get_session.assert_called_with("default_session")
        mock_session.run_browser.assert_called_once()


class TestBridgedBrowserPage:
    @patch("core.browser.SharedBrowser")
    def test_get_bridged_page_returns_none_without_page(self, mock_browser_cls):
        from core.browser import get_bridged_page
        mock_browser = MagicMock()
        mock_browser.get_page = AsyncMock(return_value=None)
        mock_browser_cls.return_value = mock_browser
        result = _run(get_bridged_page())
        assert result is None

    def test_locator_fill_uses_run_browser_bridge(self):
        from core.browser import BridgedBrowserPage
        mock_browser = MagicMock()
        mock_browser._resolve_session_id.return_value = "default_session"
        mock_browser.run_browser = AsyncMock(return_value=None)

        page = BridgedBrowserPage(session_id="default", browser=mock_browser)
        _run(page.locator("#name").first.fill("alice"))

        mock_browser.run_browser.assert_awaited_once()
        assert mock_browser.run_browser.await_args.kwargs["session_id"] == "default_session"

    def test_goto_uses_run_browser_bridge(self):
        from core.browser import BridgedBrowserPage
        mock_browser = MagicMock()
        mock_browser._resolve_session_id.return_value = "default_session"
        mock_browser.run_browser = AsyncMock(return_value=None)

        page = BridgedBrowserPage(session_id="default", browser=mock_browser)
        _run(page.goto("https://example.com", wait_until="networkidle"))

        mock_browser.run_browser.assert_awaited_once()
        assert mock_browser.run_browser.await_args.kwargs["session_id"] == "default_session"

    def test_query_selector_all_returns_bridged_elements(self):
        from core.browser import BridgedBrowserPage

        class FakeLocatorItem:
            def __init__(self, element, recorder):
                self.element = element
                self.recorder = recorder

            def get_attribute(self, name):
                return self.element.get("attrs", {}).get(name)

            def inner_text(self):
                return self.element.get("text", "")

            def click(self, timeout=5000):
                self.recorder["clicked"] = timeout

            def fill(self, value, timeout=5000):
                self.recorder["filled"] = (value, timeout)

        class FakeLocator:
            def __init__(self, elements, recorder):
                self.elements = elements
                self.recorder = recorder

            def count(self):
                return len(self.elements)

            def nth(self, index):
                return FakeLocatorItem(self.elements[index], self.recorder.setdefault(index, {}))

        class FakePage:
            def __init__(self):
                self._elements = {
                    "a[href]": [
                        {"text": "Home", "attrs": {"href": "/home"}},
                        {"text": "Docs", "attrs": {"href": "/docs"}},
                    ]
                }
                self.recorder = {}

            def locator(self, selector):
                return FakeLocator(self._elements.get(selector, []), self.recorder.setdefault(selector, {}))

        fake_page = FakePage()

        async def run_browser(callback, session_id="default_session", timeout=10.0):
            return callback(fake_page)

        mock_browser = MagicMock()
        mock_browser._resolve_session_id.return_value = "default_session"
        mock_browser.run_browser = AsyncMock(side_effect=run_browser)

        page = BridgedBrowserPage(session_id="default", browser=mock_browser)
        elements = _run(page.query_selector_all("a[href]"))

        assert len(elements) == 2
        href = _run(elements[1].get_attribute("href"))
        text = _run(elements[0].inner_text())

        assert href == "/docs"
        assert text == "Home"

    def test_query_selector_returns_none_when_missing(self):
        from core.browser import BridgedBrowserPage

        class FakeLocator:
            def count(self):
                return 0

        class FakePage:
            def locator(self, selector):
                return FakeLocator()

        async def run_browser(callback, session_id="default_session", timeout=10.0):
            return callback(FakePage())

        mock_browser = MagicMock()
        mock_browser._resolve_session_id.return_value = "default_session"
        mock_browser.run_browser = AsyncMock(side_effect=run_browser)

        page = BridgedBrowserPage(session_id="default", browser=mock_browser)
        element = _run(page.query_selector("#missing"))

        assert element is None

