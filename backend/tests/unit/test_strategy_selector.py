"""
AITestStrategySelector 单元测试
覆盖: TestType/Priority 枚举, analyze_target, analyze_requirement, learn_from_result, 单例
"""
import pytest
from core.strategy_selector import (
    TestType, Priority, TestStrategy,
    AITestStrategySelector, get_strategy_selector
)


class TestEnums:
    def test_test_types(self):
        assert TestType.UI_E2E.value == "ui_e2e"
        assert TestType.API_REST.value == "api_rest"
        assert TestType.PERFORMANCE.value == "performance"
        assert TestType.SECURITY.value == "security"

    def test_priorities(self):
        assert Priority.CRITICAL.value == 1
        assert Priority.LOW.value == 4


class TestAnalyzeTarget:
    @pytest.fixture
    def selector(self):
        return AITestStrategySelector()

    def test_web_url(self, selector):
        result = selector.analyze_target("https://example.com/page")
        assert result["is_url"] is True
        assert result["domain"] == "example.com"
        assert result["protocol"] == "https"
        assert result["is_api_endpoint"] is False

    def test_api_endpoint(self, selector):
        result = selector.analyze_target("https://api.example.com/api/v1/users")
        assert result["is_url"] is True
        assert result["is_api_endpoint"] is True

    def test_graphql_endpoint(self, selector):
        result = selector.analyze_target("https://example.com/graphql")
        assert result["is_api_endpoint"] is True

    def test_database_url(self, selector):
        result = selector.analyze_target("mysql://localhost:3306/testdb")
        assert result["is_database"] is True

    def test_postgres_url(self, selector):
        result = selector.analyze_target("postgres://user:pass@host/db")
        assert result["is_database"] is True

    def test_plain_text(self, selector):
        result = selector.analyze_target("just some text")
        assert result["is_url"] is False
        assert result["is_database"] is False


class TestAnalyzeRequirement:
    @pytest.fixture
    def selector(self):
        return AITestStrategySelector()

    def test_ui_keywords(self, selector):
        scores = selector.analyze_requirement("测试登录页面的按钮和表单")
        assert scores[TestType.UI_E2E] > 0

    def test_api_keywords(self, selector):
        scores = selector.analyze_requirement("测试 REST API 接口")
        assert scores[TestType.API_REST] > 0

    def test_performance_keywords(self, selector):
        scores = selector.analyze_requirement("性能压测并发1000用户")
        assert scores[TestType.PERFORMANCE] > 0

    def test_security_keywords(self, selector):
        scores = selector.analyze_requirement("安全扫描SQL注入XSS")
        assert scores[TestType.SECURITY] > 0

    def test_normalization(self, selector):
        scores = selector.analyze_requirement("测试登录页面")
        max_score = max(scores.values())
        assert max_score <= 1.0  # 归一化后最大值为 1.0

    def test_empty_requirement(self, selector):
        scores = selector.analyze_requirement("")
        assert all(v == 0.0 for v in scores.values())


class TestLearnFromResult:
    def test_records_history(self):
        selector = AITestStrategySelector()
        strategy = TestStrategy(
            test_types=[TestType.UI_E2E],
            priority=Priority.HIGH,
        )
        selector.learn_from_result("测试登录", strategy, success=True, feedback="good")
        assert len(selector.history) == 1
        assert selector.history[0]["success"] is True

    def test_multiple_records(self):
        selector = AITestStrategySelector()
        strategy = TestStrategy(test_types=[TestType.API_REST], priority=Priority.MEDIUM)
        selector.learn_from_result("测试A", strategy, True)
        selector.learn_from_result("测试B", strategy, False)
        assert len(selector.history) == 2


class TestSingleton:
    def test_get_strategy_selector(self):
        s1 = get_strategy_selector()
        s2 = get_strategy_selector()
        assert s1 is s2
