# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.semantic_actions import ai_action, ai_assert, ai_query, _parse_instruction
from core.semantic_engine import SemanticElement, SemanticLocator
from routers.semantic import _resolve_page_attr


class SyncPageStub:
    def __init__(self):
        self.url = "https://example.com/login"

    def evaluate(self, script):
        if "document.body.innerText" in script:
            return "Signed in successfully. Welcome back"
        return [
            {
                "index": 0,
                "tag": "button",
                "text": "Sign in",
                "placeholder": "",
                "ariaLabel": "",
                "role": "button",
                "type": "submit",
                "id": "login-btn",
                "name": "",
                "className": "primary",
                "href": "",
                "x": 120,
                "y": 60,
                "width": 80,
                "height": 32,
            }
        ]

    def title(self):
        return "Sign-in page"


class AsyncMouseStub:
    def __init__(self):
        self.clicks = []

    async def click(self, x, y):
        self.clicks.append((x, y))


class AsyncKeyboardStub:
    def __init__(self):
        self.typed = []

    async def type(self, value):
        self.typed.append(value)


class AsyncPageStub:
    def __init__(self):
        self.url = "https://example.com/dashboard"
        self.mouse = AsyncMouseStub()
        self.keyboard = AsyncKeyboardStub()

    async def evaluate(self, script):
        return "Result A\nResult B\nResult C"

    async def title(self):
        return "Dashboard"

    def locator(self, selector):
        raise AssertionError(f"unexpected selector lookup: {selector}")


@pytest.mark.asyncio
async def test_parse_instruction_extracts_fill_value():
    action_type, target, value = _parse_instruction('在搜索框中输入"AI测试"')

    assert action_type == "fill"
    assert "在搜索框中输入" in target
    assert value == "AI测试"


@pytest.mark.asyncio
async def test_semantic_locator_extract_elements_supports_sync_page():
    locator = SemanticLocator()

    elements = await locator._extract_elements(SyncPageStub())

    assert len(elements) == 1
    assert elements[0].text == "Sign in"
    assert elements[0].selector == "#login-btn"


@pytest.mark.asyncio
async def test_ai_assert_supports_sync_page():
    fake_llm = SimpleNamespace(
        invoke=lambda prompt: SimpleNamespace(
            content='{"passed": true, "reasoning": "Text matched", "evidence": "Welcome back"}'
        )
    )
    with patch("core.llm_manager.get_llm_for_role", return_value=fake_llm) as get_llm:
        result = await ai_assert(SyncPageStub(), "The page displays a welcome message")

    get_llm.assert_called_once_with("executor", temperature=0.0)
    assert result["success"] is True
    assert result["passed"] is True
    assert result["evidence"] == "Welcome back"


@pytest.mark.asyncio
async def test_ai_query_supports_async_page():
    fake_llm = SimpleNamespace(
        invoke=lambda prompt: SimpleNamespace(
            content='{"data": ["Result A", "Result B"], "source": "Page text", "confidence": 0.92}'
        )
    )
    with patch("core.llm_manager.get_llm_for_role", return_value=fake_llm) as get_llm:
        result = await ai_query(AsyncPageStub(), "Get the first two results")

    get_llm.assert_called_once_with("executor", temperature=0.0)
    assert result["success"] is True
    assert result["data"] == ["Result A", "Result B"]
    assert result["confidence"] == 0.92


@pytest.mark.asyncio
async def test_ai_action_supports_async_page_coordinate_click():
    page = AsyncPageStub()
    element = SemanticElement(
        element_id="el_1",
        text="Submit",
        role="button",
        selector="",
        bounding_box={"x": 88, "y": 42, "width": 90, "height": 32},
    )

    class FakeLocator:
        async def locate(self, page, instruction, use_vision=True):
            return element

    with patch("core.semantic_engine.get_semantic_locator", return_value=FakeLocator()):
        result = await ai_action(page, "Click the submit button")

    assert result["success"] is True
    assert result["method"] == "coordinate_click"
    assert page.mouse.clicks == [(88, 42)]


@pytest.mark.asyncio
async def test_resolve_page_attr_supports_async_method_and_property():
    page = AsyncPageStub()

    title = await _resolve_page_attr(page, "title", default="unknown")
    url = await _resolve_page_attr(page, "url", default="unknown")

    assert title == "Dashboard"
    assert url == "https://example.com/dashboard"
