"""
SelfHealingEngine 单元测试
覆盖: FailureType 枚举, HealingAction/HealingResult 数据类,
      classify_failure (7 种类型), get_statistics, get_healing_engine 单例
"""
import pytest
from core.self_healing import (
    FailureType, HealingAction, HealingResult,
    SelfHealingEngine, get_healing_engine
)


# ---------------------------------------------------------------------------
# 数据结构测试
# ---------------------------------------------------------------------------
class TestFailureType:
    def test_enum_values(self):
        assert FailureType.ELEMENT_NOT_FOUND.value == "element_not_found"
        assert FailureType.TIMEOUT.value == "timeout"
        assert FailureType.ASSERTION.value == "assertion"
        assert FailureType.NETWORK.value == "network"
        assert FailureType.AUTHENTICATION.value == "authentication"
        assert FailureType.DATA_MISMATCH.value == "data_mismatch"
        assert FailureType.UNKNOWN.value == "unknown"


class TestHealingAction:
    def test_creation(self):
        action = HealingAction(
            action_type="retry",
            description="重试操作",
            parameters={"delay": 1.0},
            success_probability=0.8,
        )
        assert action.action_type == "retry"
        assert action.success_probability == 0.8


class TestHealingResult:
    def test_success(self):
        result = HealingResult(
            success=True,
            action_taken=None,
            retry_count=1,
            total_time_ms=200,
            original_error="timeout",
        )
        assert result.success is True
        assert result.healed_error is None

    def test_failure(self):
        result = HealingResult(
            success=False,
            action_taken=None,
            retry_count=3,
            total_time_ms=5000,
            original_error="element not found",
            healed_error="still not found",
        )
        assert result.success is False
        assert result.healed_error == "still not found"


# ---------------------------------------------------------------------------
# classify_failure 测试 (7 种类型)
# ---------------------------------------------------------------------------
class TestClassifyFailure:
    @pytest.fixture
    def engine(self):
        return SelfHealingEngine()

    def test_element_not_found(self, engine):
        assert engine.classify_failure(Exception("Element not found"), {}) == FailureType.ELEMENT_NOT_FOUND

    def test_element_not_found_chinese(self, engine):
        assert engine.classify_failure(Exception("找不到按钮"), {}) == FailureType.ELEMENT_NOT_FOUND

    def test_timeout(self, engine):
        assert engine.classify_failure(Exception("Request timed out"), {}) == FailureType.TIMEOUT

    def test_timeout_chinese(self, engine):
        assert engine.classify_failure(Exception("操作超时"), {}) == FailureType.TIMEOUT

    def test_assertion(self, engine):
        assert engine.classify_failure(Exception("AssertionError: expected 200"), {}) == FailureType.ASSERTION

    def test_network(self, engine):
        assert engine.classify_failure(Exception("Connection refused"), {}) == FailureType.NETWORK

    def test_authentication(self, engine):
        assert engine.classify_failure(Exception("401 Unauthorized"), {}) == FailureType.AUTHENTICATION

    def test_authentication_forbidden(self, engine):
        assert engine.classify_failure(Exception("403 Forbidden"), {}) == FailureType.AUTHENTICATION

    def test_data_mismatch(self, engine):
        assert engine.classify_failure(Exception("Data mismatch detected"), {}) == FailureType.DATA_MISMATCH

    def test_data_mismatch_chinese(self, engine):
        assert engine.classify_failure(Exception("数据不匹配"), {}) == FailureType.DATA_MISMATCH

    def test_unknown(self, engine):
        assert engine.classify_failure(Exception("Something random happened"), {}) == FailureType.UNKNOWN


# ---------------------------------------------------------------------------
# get_statistics 测试
# ---------------------------------------------------------------------------
class TestGetStatistics:
    def test_empty(self):
        engine = SelfHealingEngine()
        stats = engine.get_statistics()
        assert stats["total_healings"] == 0
        assert stats["successful_healings"] == 0
        assert stats["success_rate"] == 0
        assert stats["learned_patterns"] >= 0

    def test_with_history(self):
        engine = SelfHealingEngine()
        engine.healing_history = [
            {"success": True},
            {"success": True},
            {"success": False},
        ]
        stats = engine.get_statistics()
        assert stats["total_healings"] == 3
        assert stats["successful_healings"] == 2
        assert abs(stats["success_rate"] - 2 / 3) < 0.01


# ---------------------------------------------------------------------------
# 初始化 + 单例测试
# ---------------------------------------------------------------------------
class TestInit:
    def test_defaults(self):
        engine = SelfHealingEngine()
        assert engine.max_retries == 3
        assert engine.base_delay == 1.0

    def test_custom_params(self):
        engine = SelfHealingEngine(max_retries=5, base_delay=2.0)
        assert engine.max_retries == 5
        assert engine.base_delay == 2.0

    def test_singleton(self):
        e1 = get_healing_engine()
        e2 = get_healing_engine()
        assert e1 is e2
