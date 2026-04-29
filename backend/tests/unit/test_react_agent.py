from unittest.mock import AsyncMock, MagicMock, patch


def _make_agent():
    from agents.react import ReActAgent

    with patch("agents.react.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_get_llm.return_value = mock_llm
        return ReActAgent()


class TestReActAgentBridge:
    def test_execute_tool_uses_bridged_page_for_browser_actions(self):
        agent = _make_agent()
        fake_page = object()
        state = {"context": {}}

        with patch("agents.react.get_bridged_page", new=AsyncMock(return_value=fake_page)) as mock_get_page, \
             patch("agents.react.tool_click", new=AsyncMock(return_value="clicked")) as mock_tool_click:
            result = agent._execute_tool("tool_click", {"target": "#submit"}, state)

        assert result == "clicked"
        mock_get_page.assert_awaited_once()
        mock_tool_click.assert_awaited_once_with(fake_page, "#submit")
