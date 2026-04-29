"""
DataAgent 单元测试
覆盖: __init__, execute_test, cleanup_test_data
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _patch_deps():
    with patch("agents.data_agent.get_llm") as mock_llm, \
         patch("agents.data_agent.DATA_TOOLS") as mock_tools, \
         patch("agents.data_agent.query_db_natural_language_tool") as mock_nl, \
         patch("agents.data_agent.Config"):
        mock_llm.return_value = MagicMock()
        # Mock 各工具
        mock_tool = MagicMock()
        mock_tool.invoke = MagicMock(return_value={"result": "ok"})
        mock_tools.__getitem__ = MagicMock(return_value=mock_tool)
        mock_nl.invoke = MagicMock(return_value={"sql": "SELECT 1", "result": []})
        yield mock_tools


def _make_data_agent():
    from agents.data_agent import DataAgent
    return DataAgent()


class TestInit:
    def test_has_llm(self):
        agent = _make_data_agent()
        assert agent.llm is not None

    def test_has_tools(self):
        agent = _make_data_agent()
        assert hasattr(agent, 'tools')


class TestExecuteTest:
    def test_basic(self):
        agent = _make_data_agent()
        result = agent.execute_test("验证订单数据")
        assert result["agent"] == "data_agent"
        assert result["scenario"] == "验证订单数据"
        assert "status" in result

    def test_with_rules(self, _patch_deps):
        agent = _make_data_agent()
        rules = [
            {"type": "row_count", "table": "orders", "expected": 10},
            {"type": "null_check", "column": "user_id"},
        ]
        result = agent.execute_test("验证订单完整性", verification_rules=rules)
        assert result["agent"] == "data_agent"


class TestCleanup:
    def test_cleanup_basic(self, _patch_deps):
        agent = _make_data_agent()
        rules = [{"table": "test_orders", "condition": "created_at < '2024-01-01'"}]
        result = agent.cleanup_test_data(rules)
        assert isinstance(result, dict)

    def test_cleanup_empty_rules(self):
        agent = _make_data_agent()
        result = agent.cleanup_test_data([])
        assert isinstance(result, dict)
