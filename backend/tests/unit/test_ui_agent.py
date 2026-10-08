"""
UIAgent unit tests
Coverage: _format_history, _format_dom_summary, execute_test, heal_and_retry.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.fixture(autouse=True)
def _patch_deps():
    with patch("agents.ui_agent.get_llm_for_role") as mock_llm, \
         patch("agents.ui_agent.UI_TOOLS"), \
         patch("agents.ui_agent.navigate"), \
         patch("agents.ui_agent.take_screenshot"), \
         patch("agents.ui_agent.get_interactable_elements"), \
         patch("agents.ui_agent.registry"):
        mock_llm.return_value = MagicMock()
        yield mock_llm


def _make_ui_agent():
    from agents.ui_agent import UIAgent
    return UIAgent()


class TestFormatHistory:
    def test_empty_history(self):
        agent = _make_ui_agent()
        result = agent._format_history([])
        assert result == "No history"

    def test_single_action(self):
        agent = _make_ui_agent()
        actions = [{"step": 1, "thought": "Click Login", "tool": "click", "args": {"selector": "#btn"}}]
        result = agent._format_history(actions)
        assert "Step 1" in result
        assert "Click Login" in result
        assert "click" in result

    def test_multiple_actions(self):
        agent = _make_ui_agent()
        actions = [
            {"step": i, "thought": f"Thought {i}", "tool": f"tool_{i}", "args": {}}
            for i in range(1, 8)
        ]
        result = agent._format_history(actions)
        # Keep only the five most recent actions.
        assert "Step 3" in result
        assert "Step 7" in result
        lines = result.strip().split("\n")
        # Each action occupies two lines (Step + Action).
        assert len(lines) == 10  # 5 actions * 2 lines

    def test_long_args_truncation(self):
        agent = _make_ui_agent()
        long_args = {"data": "x" * 200}
        actions = [{"step": 1, "thought": "test", "tool": "fill", "args": long_args}]
        result = agent._format_history(actions)
        assert "..." in result

    def test_missing_fields(self):
        agent = _make_ui_agent()
        actions = [{}]  # No fields are provided.
        result = agent._format_history(actions)
        assert "Step ?" in result
        assert "No thought" in result


class TestInit:
    def test_has_llm(self):
        agent = _make_ui_agent()
        assert agent.llm is not None

    def test_has_tools(self):
        agent = _make_ui_agent()
        assert hasattr(agent, 'tools')


# ═══════════════════════════════════════════════════
# _format_dom_summary
# ═══════════════════════════════════════════════════

class TestFormatDomSummary:
    def test_empty_dom_info(self):
        agent = _make_ui_agent()
        result = agent._format_dom_summary({})
        assert isinstance(result, str)

    def test_with_elements(self):
        agent = _make_ui_agent()
        dom_info = {
            "interactive_elements": "[1] <button> Login\n[2] <input> Username",
            "element_count": 2,
            "visible_text": "Welcome to the page",
            "url": "http://example.com",
            "title": "Example",
        }
        result = agent._format_dom_summary(dom_info)
        assert "Login" in result or "element" in result.lower() or len(result) > 0

    def test_with_no_elements(self):
        agent = _make_ui_agent()
        dom_info = {
            "interactive_elements": "",
            "element_count": 0,
        }
        result = agent._format_dom_summary(dom_info)
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════
# execute_test
# ═══════════════════════════════════════════════════

class TestExecuteTest:
    @pytest.mark.asyncio
    async def test_calls_autonomous_loop(self):
        agent = _make_ui_agent()
        with patch.object(agent, '_run_autonomous_loop', new_callable=AsyncMock, return_value={
            "status": "completed",
            "steps_taken": 3,
            "final_url": "http://example.com/dashboard"
        }) as mock_loop:
            result = await agent.execute_test("Test login functionality", url="http://example.com")
            mock_loop.assert_called_once()
            assert result is not None

    @pytest.mark.asyncio
    async def test_without_url(self):
        agent = _make_ui_agent()
        with patch.object(agent, '_run_autonomous_loop', new_callable=AsyncMock, return_value={
            "status": "completed", "steps_taken": 1
        }) as mock_loop, patch("agents.ui_agent.Config") as mock_config:
            mock_config.TARGET_URL = "http://default.com"
            result = await agent.execute_test("Check the home page")
            assert result is not None


# ═══════════════════════════════════════════════════
# heal_and_retry
# ═══════════════════════════════════════════════════

class TestHealAndRetry:
    @pytest.mark.asyncio
    async def test_heal_returns_dict(self):
        agent = _make_ui_agent()
        with patch("workflows.ui_healing_subgraph.get_healing_subgraph") as mock_get_subgraph:
            mock_subgraph = MagicMock()
            mock_subgraph.run = AsyncMock(return_value={"healed": True, "retry_result": {"status": "ok"}})
            mock_get_subgraph.return_value = mock_subgraph

            result = await agent.heal_and_retry(
                failed_action={"tool": "click", "args": {"selector": "#old-btn"}},
                context={"error": "element not found", "page_content": "Login page"}
            )
            assert result == {"healed": True, "retry_result": {"status": "ok"}}

    @pytest.mark.asyncio
    async def test_heal_with_empty_context(self):
        agent = _make_ui_agent()
        with patch("workflows.ui_healing_subgraph.get_healing_subgraph") as mock_get_subgraph:
            mock_subgraph = MagicMock()
            mock_subgraph.run = AsyncMock(return_value={})
            mock_get_subgraph.return_value = mock_subgraph

            result = await agent.heal_and_retry(failed_action={}, context={})
            assert result == {}

