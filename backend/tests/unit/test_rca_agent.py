"""
RCAAgent 单元测试
覆盖: _categorize_errors, diagnose_error, generate_root_cause_report
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _patch_deps():
    """Mock RCA Agent 的外部依赖"""
    with patch("agents.rca_agent.get_llm") as mock_llm, \
         patch("agents.rca_agent.OPS_TOOLS") as mock_ops, \
         patch("agents.rca_agent.search_similar_bugs") as mock_search, \
         patch("agents.rca_agent.git_blame") as mock_blame, \
         patch("agents.rca_agent.correlate_logs_with_code") as mock_corr, \
         patch("agents.rca_agent.diagnose_error_with_history") as mock_diag:
        mock_llm.return_value = MagicMock()
        mock_ops.__getitem__ = MagicMock(return_value=MagicMock())
        mock_search.invoke = MagicMock(return_value=[])
        mock_blame.invoke = MagicMock(return_value={})
        mock_corr.invoke = MagicMock(return_value={})
        mock_diag.invoke = MagicMock(return_value={})
        yield


def _make_rca():
    from agents.rca_agent import RCAAgent
    return RCAAgent()


# ---------------------------------------------------------------------------
# 测试 _categorize_errors
# ---------------------------------------------------------------------------
class TestCategorizeErrors:
    def test_null_pointer(self):
        agent = _make_rca()
        errors = [{"log_line": "NullPointerException at line 42"}]
        cats = agent._categorize_errors(errors)
        assert cats["null_pointer"] == 1
        assert cats["timeout"] == 0

    def test_timeout(self):
        agent = _make_rca()
        errors = [{"log_line": "Request timeout after 30s"}]
        cats = agent._categorize_errors(errors)
        assert cats["timeout"] == 1

    def test_connection(self):
        agent = _make_rca()
        errors = [
            {"log_line": "Connection refused"},
            {"log_line": "ECONNREFUSED localhost:8080"},
        ]
        cats = agent._categorize_errors(errors)
        assert cats["connection"] == 2

    def test_permission(self):
        agent = _make_rca()
        errors = [
            {"log_line": "Permission denied: /var/log"},
            {"log_line": "Unauthorized access attempt"},
        ]
        cats = agent._categorize_errors(errors)
        assert cats["permission"] == 2

    def test_other(self):
        agent = _make_rca()
        errors = [{"log_line": "Unknown crash xyz"}]
        cats = agent._categorize_errors(errors)
        assert cats["other"] == 1

    def test_empty_errors(self):
        agent = _make_rca()
        cats = agent._categorize_errors([])
        assert all(v == 0 for v in cats.values())

    def test_mixed_errors(self):
        agent = _make_rca()
        errors = [
            {"log_line": "null reference"},
            {"log_line": "request timeout"},
            {"log_line": "connection reset"},
            {"log_line": "permission denied"},
            {"log_line": "segfault"},
        ]
        cats = agent._categorize_errors(errors)
        assert cats["null_pointer"] == 1
        assert cats["timeout"] == 1
        assert cats["connection"] == 1
        assert cats["permission"] == 1
        assert cats["other"] == 1


# ---------------------------------------------------------------------------
# 测试 diagnose_error（需要 mock LLM + Vector DB）
# ---------------------------------------------------------------------------
class TestDiagnoseError:
    def test_basic_diagnosis(self):
        agent = _make_rca()
        result = agent.diagnose_error("NullPointerException")
        assert isinstance(result, dict)
        assert result["agent"] == "rca_agent"

    def test_diagnosis_with_log_path(self):
        agent = _make_rca()
        result = agent.diagnose_error("timeout", log_path="/var/log/app.log")
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# 测试 generate_root_cause_report
# ---------------------------------------------------------------------------
class TestGenerateReport:
    def test_report_structure(self):
        agent = _make_rca()
        errors = [
            {"log_line": "NullPointerException", "timestamp": "12:00"},
            {"log_line": "Connection refused", "timestamp": "12:01"},
        ]
        report = agent.generate_root_cause_report(errors)
        assert isinstance(report, dict)
        assert report["agent"] == "rca_agent"
        assert report["total_errors"] == 2
        assert "diagnoses" in report
        assert "code_traces" in report
        assert "correlations" in report
        assert "recommendations" in report

    def test_empty_errors_report(self):
        agent = _make_rca()
        report = agent.generate_root_cause_report([])
        assert isinstance(report, dict)
