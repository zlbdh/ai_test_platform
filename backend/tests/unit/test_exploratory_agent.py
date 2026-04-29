"""
ExploratoryTestAgent 单元测试
覆盖: _compute_state_hash, _calculate_coverage, generate_report, ActionType/PageState/AnomalyFound 数据结构
"""
import pytest
from unittest.mock import AsyncMock
from agents.exploratory_agent import (
    ExploratoryTestAgent, ActionType, PageState,
    ExplorationAction, AnomalyFound, create_exploratory_agent
)


class TestActionType:
    def test_enum_values(self):
        assert ActionType.CLICK.value == "click"
        assert ActionType.INPUT.value == "input"
        assert ActionType.SELECT.value == "select"
        assert ActionType.NAVIGATE.value == "navigate"
        assert ActionType.SCROLL.value == "scroll"
        assert ActionType.HOVER.value == "hover"


class TestPageState:
    def test_creation(self):
        state = PageState(
            url="https://example.com",
            title="Test",
            html_hash="abc123",
            elements_count=10,
            forms_count=2,
            links_count=5,
        )
        assert state.url == "https://example.com"
        assert state.elements_count == 10


class TestExplorationAction:
    def test_with_value(self):
        action = ExplorationAction(
            action_type=ActionType.INPUT,
            target="#search",
            value="hello",
        )
        assert action.value == "hello"

    def test_without_value(self):
        action = ExplorationAction(
            action_type=ActionType.CLICK,
            target="button",
        )
        assert action.value is None


class TestComputeStateHash:
    def test_same_content_same_hash(self):
        agent = ExploratoryTestAgent()
        h1 = agent._compute_state_hash("<html>Hello</html>", "http://a.com")
        h2 = agent._compute_state_hash("<html>Hello</html>", "http://a.com")
        assert h1 == h2

    def test_different_url_different_hash(self):
        agent = ExploratoryTestAgent()
        h1 = agent._compute_state_hash("<html>Hello</html>", "http://a.com")
        h2 = agent._compute_state_hash("<html>Hello</html>", "http://b.com")
        assert h1 != h2

    def test_normalizes_numbers(self):
        """数字被 normalize 掉，所以相同结构但不同数字 → 相同 hash"""
        agent = ExploratoryTestAgent()
        h1 = agent._compute_state_hash("<p>item 123</p>", "http://a.com")
        h2 = agent._compute_state_hash("<p>item 456</p>", "http://a.com")
        assert h1 == h2

    def test_normalizes_hex(self):
        """Hex token 被 normalize"""
        agent = ExploratoryTestAgent()
        h1 = agent._compute_state_hash("<p>token=abcdef0123456789</p>", "http://a.com")
        h2 = agent._compute_state_hash("<p>token=1234567890abcdef</p>", "http://a.com")
        assert h1 == h2


class TestCalculateCoverage:
    def test_no_history(self):
        agent = ExploratoryTestAgent()
        assert agent._calculate_coverage() == 0.0

    def test_all_unique_states(self):
        agent = ExploratoryTestAgent()
        agent.action_history = [ExplorationAction(ActionType.CLICK, "a")]
        agent.visited_states = {"s1", "s2", "s3"} # possible = 9
        agent.state_graph = {
            "s1": {"a1": "s2", "a2": "s3", "a3": "s1"},
            "s2": {"a1": "s3", "a2": "s1", "a3": "s2"},
            "s3": {"a1": "s1", "a2": "s2", "a3": "s3"}
        } # 9 edges -> coverage 1.0
        assert agent._calculate_coverage() == 1.0

    def test_low_coverage(self):
        agent = ExploratoryTestAgent()
        agent.action_history = [ExplorationAction(ActionType.CLICK, "a")]
        # 模拟有10个状态 (可能30条边)，但目前只探索了3条边
        agent.visited_states = {f"s{i}" for i in range(10)}
        agent.state_graph = {
            "s1": {"a1": "s2", "a2": "s3", "a3": "s4"}
        }
        assert agent._calculate_coverage() == 0.1

    def test_capped_at_one(self):
        agent = ExploratoryTestAgent()
        agent.action_history = [ExplorationAction(ActionType.CLICK, "a")]
        # 模拟状态极少，边数超出预估上限的情况
        agent.visited_states = {"s1"} # len = 1, possible = 3
        agent.state_graph = {
            "s1": {"a1": "s1", "a2": "s1", "a3": "s1", "a4": "s1"}
        } # len = 4 (> 3)
        assert agent._calculate_coverage() == 1.0


class TestGenerateReport:
    def test_empty_report(self):
        agent = ExploratoryTestAgent()
        report = agent.generate_report()
        assert report["summary"]["total_states_visited"] == 0
        assert report["summary"]["total_actions_performed"] == 0
        assert report["summary"]["unique_urls"] == 0
        assert report["summary"]["anomalies_found"] == 0
        assert report["visited_urls"] == []
        assert report["action_history"] == []
        assert report["anomalies"] == []

    def test_report_with_data(self):
        agent = ExploratoryTestAgent()
        agent.visited_states = {"h1", "h2"}
        agent.visited_urls = {"http://a.com", "http://b.com"}
        agent.action_history = [
            ExplorationAction(ActionType.CLICK, "button"),
            ExplorationAction(ActionType.INPUT, "#field", "value"),
        ]
        agent.anomalies = [
            AnomalyFound("server_error", "500 error", "http://a.com", "500", "high"),
        ]

        report = agent.generate_report()
        assert report["summary"]["total_states_visited"] == 2
        assert report["summary"]["total_actions_performed"] == 2
        assert report["summary"]["unique_urls"] == 2
        assert report["summary"]["anomalies_found"] == 1
        assert len(report["action_history"]) == 2
        assert report["anomalies"][0]["type"] == "server_error"

    def test_action_history_limit(self):
        """最近 20 个 action"""
        agent = ExploratoryTestAgent()
        agent.action_history = [
            ExplorationAction(ActionType.CLICK, f"el{i}") for i in range(30)
        ]
        report = agent.generate_report()
        assert len(report["action_history"]) == 20


class TestCreateExploratoryAgent:
    def test_factory_function(self):
        agent = create_exploratory_agent()
        assert isinstance(agent, ExploratoryTestAgent)
        assert agent.browser is None
        assert agent.llm is None

    def test_with_browser(self):
        mock_browser = object()
        agent = create_exploratory_agent(browser=mock_browser)
        assert agent.browser is mock_browser


class TestBrowserCompatibility:
    @pytest.mark.asyncio
    async def test_get_current_state_supports_current_url_bridge(self):
        browser = type("FakeBrowser", (), {})()
        browser.current_url = AsyncMock(return_value="https://example.com/dashboard")
        browser.title = AsyncMock(return_value="Dashboard")

        agent = ExploratoryTestAgent(browser=browser)
        state = await agent._get_current_state()

        assert state.url == "https://example.com/dashboard"
        assert state.title == "Dashboard"

    @pytest.mark.asyncio
    async def test_discover_actions_with_bridged_elements(self):
        class FakeElement:
            def __init__(self, attrs=None, text=""):
                self.attrs = attrs or {}
                self.text = text

            async def get_attribute(self, name):
                return self.attrs.get(name)

            async def inner_text(self):
                return self.text

        class FakeBrowser:
            async def query_selector_all(self, selector):
                if selector == "a[href]":
                    return [FakeElement(attrs={"href": "/reports"})]
                if selector == "button, input[type=\"submit\"]":
                    return [FakeElement(text="提交表单")]
                if selector == "input[type=\"text\"], input[type=\"search\"]":
                    return [FakeElement(attrs={"name": "keyword"})]
                return []

        agent = ExploratoryTestAgent(browser=FakeBrowser())
        actions = await agent._discover_actions()

        assert any(action.target == "a[href='/reports']" for action in actions)
        assert any(action.target == "button:has-text('提交表单')" for action in actions)
        assert any(action.target == "input[name='keyword']" for action in actions)

    @pytest.mark.asyncio
    async def test_execute_action_uses_query_selector_proxy(self):
        class FakeElement:
            def __init__(self):
                self.click = AsyncMock()
                self.fill = AsyncMock()

        class FakeBrowser:
            def __init__(self):
                self.element = FakeElement()

            async def query_selector(self, selector):
                return self.element

        agent = ExploratoryTestAgent(browser=FakeBrowser())

        await agent._execute_action(ExplorationAction(ActionType.CLICK, "button.primary"))
        await agent._execute_action(ExplorationAction(ActionType.INPUT, "input[name='q']", "hello"))

        agent.browser.element.click.assert_awaited_once()
        agent.browser.element.fill.assert_awaited_once_with("hello")
