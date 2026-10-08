"""
APIAgent unit tests
Coverage: __init__, execute_test, chain_api_calls
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _patch_deps():
    with patch("agents.api_agent.get_llm_for_role") as mock_llm, \
         patch("agents.api_agent.API_TOOLS") as mock_tools, \
         patch("agents.api_agent.Config"):
        mock_llm.return_value = MagicMock()
        # Mock each tool's invoke method.
        mock_call = MagicMock()
        mock_call.invoke = MagicMock(return_value={"status_code": 200, "body": {}})
        mock_tools.__getitem__ = MagicMock(return_value=mock_call)
        yield mock_tools


def _make_api_agent():
    from agents.api_agent import APIAgent
    return APIAgent()


class TestInit:
    def test_has_llm(self):
        agent = _make_api_agent()
        assert agent.llm is not None

    def test_has_tools(self):
        agent = _make_api_agent()
        assert agent.tools is not None


class TestExecuteTest:
    def test_basic_no_swagger(self):
        agent = _make_api_agent()
        result = agent.execute_test("Test user login")
        assert result["agent"] == "api_agent"
        assert result["scenario"] == "Test user login"
        # No Swagger URL or target URL should produce a warning.
        assert result["status"] == "warning"

    def test_with_url_in_scenario(self, _patch_deps):
        agent = _make_api_agent()
        result = agent.execute_test("Test the http://api.example.com/users endpoint")
        assert result["agent"] == "api_agent"
        # A URL extracted from the scenario should produce endpoints_tested.
        assert isinstance(result["endpoints_tested"], list)

    @patch("workflows.api_fuzzing_subgraph.get_fuzzing_subgraph")
    def test_swagger_url(self, mock_get_subgraph, _patch_deps):
        swagger_mock = MagicMock()
        swagger_mock.invoke = MagicMock(return_value={
            "endpoints": [
                {"path": "/api/products", "method": "GET"},
                {"path": "/api/cart/add", "method": "POST"},
            ]
        })
        _patch_deps.__getitem__ = MagicMock(return_value=swagger_mock)

        # Mock subgraph to prevent real network/LLM calls hanging the test
        mock_subgraph = MagicMock()
        mock_subgraph.run.return_value = [{"vulnerability": "none", "severity": "low"}]
        mock_get_subgraph.return_value = mock_subgraph

        agent = _make_api_agent()
        result = agent.execute_test("Test the e-commerce API", swagger_url="http://api.com/swagger.json")
        assert result["agent"] == "api_agent"
        assert len(result["endpoints_tested"]) == 2
        
        # Verify subgraph was called for the cart endpoint
        mock_subgraph.run.assert_called_once()


class TestChainApiCalls:
    def test_login_flow(self, _patch_deps):
        login_mock = MagicMock()
        login_mock.invoke = MagicMock(return_value={
            "status_code": 200,
            "body": {"token": "abc123", "user_id": "u1"}
        })
        _patch_deps.__getitem__ = MagicMock(return_value=login_mock)

        agent = _make_api_agent()
        result = agent.chain_api_calls([
            {"action": "login", "credentials": {"username": "admin", "password": "123"}},
            {"action": "add_to_cart", "data": {"product_id": 1}},
        ])
        assert result["status"] == "success"
        assert "token" in result["context"]

    def test_generic_action(self, _patch_deps):
        api_mock = MagicMock()
        api_mock.invoke = MagicMock(return_value={"status_code": 200, "body": {}})
        _patch_deps.__getitem__ = MagicMock(return_value=api_mock)

        agent = _make_api_agent()
        result = agent.chain_api_calls([
            {"action": "custom", "method": "GET", "endpoint": "/api/health"},
        ])
        assert result["status"] == "success"
        assert len(result["chain_results"]) == 1

    def test_empty_sequence(self):
        agent = _make_api_agent()
        result = agent.chain_api_calls([])
        assert result["status"] == "success"
        assert result["chain_results"] == []
