# -*- coding: utf-8 -*-
"""
Phase 3 unit tests: store_finding, RAG recall, and confidence thresholds.
"""
import pytest
import json
import time
from unittest.mock import MagicMock, patch, PropertyMock

from agents.inspector_agent import InspectorAgent, SKIP_ACTIONS
from core.models import InspectionResult


# ============================================================================
# Helpers
# ============================================================================

def _make_fake_vlm(response_text: str):
    """Build a fake VLM."""
    fake = MagicMock()
    fake_resp = MagicMock()
    fake_resp.content = response_text
    fake.invoke = MagicMock(return_value=fake_resp)
    return fake


def _make_fake_vector_store(search_results=None):
    """Build a fake VectorStore."""
    vs = MagicMock()
    vs.store_document = MagicMock(return_value="bugs_0")
    vs.search = MagicMock(return_value=search_results or [])
    return vs


SAMPLE_PAGE_STATE = {
    "url": "https://example.com/dashboard",
    "visible_text": "Welcome",
}
SAMPLE_SCREENSHOT = "iVBORw0KGgoAAAANSUhEUg=="


# ============================================================================
# P3-1: store_finding writes to ChromaDB
# ============================================================================

class TestStoreFinding:
    """store_finding method tests."""

    def test_store_finding_calls_vector_store(self):
        vs = _make_fake_vector_store()
        agent = InspectorAgent(vector_store=vs)
        result = InspectionResult(
            passed=False, confidence=0.8,
            reason="Red error", anomalies=["toast"]
        )
        doc_id = agent.store_finding(
            url="https://example.com",
            step_desc="click(Button)",
            result=result,
        )
        assert doc_id == "bugs_0"
        vs.store_document.assert_called_once()
        call_args = vs.store_document.call_args
        assert call_args[0][0] == "bugs"  # collection name
        assert "Inspector rejected" in call_args[0][1]  # content
        metadata = call_args[0][2]
        assert metadata["source"] == "inspector"
        assert metadata["url"] == "https://example.com"
        assert metadata["confidence"] == 0.8

    def test_store_finding_no_vector_store(self):
        agent = InspectorAgent(vector_store=None)
        # Force _vector_store to stay None
        agent._vector_store = None
        with patch("agents.inspector_agent.InspectorAgent.vector_store", new_callable=PropertyMock, return_value=None):
            result = InspectionResult(passed=False, confidence=0.8, reason="err", anomalies=[])
            doc_id = agent.store_finding("http://x.com", "click", result)
        assert doc_id is None

    def test_store_finding_exception_returns_none(self):
        vs = _make_fake_vector_store()
        vs.store_document.side_effect = RuntimeError("DB error")
        agent = InspectorAgent(vector_store=vs)
        result = InspectionResult(passed=False, confidence=0.8, reason="err", anomalies=[])
        doc_id = agent.store_finding("http://x.com", "click", result)
        assert doc_id is None

    def test_inspect_rejected_triggers_store(self):
        """A rejected inspect() result automatically calls store_finding."""
        vlm_resp = json.dumps({
            "passed": False, "confidence": 0.85,
            "reason": "Error visible", "anomalies": ["red banner"]
        })
        vs = _make_fake_vector_store()
        agent = InspectorAgent(
            vlm=_make_fake_vlm(vlm_resp),
            vector_store=vs,
            confidence_threshold=0.5,  # low threshold so rejection is not auto-passed
        )
        result = agent.inspect(
            screenshot_b64=SAMPLE_SCREENSHOT,
            step_desc="click(Submit)",
            expected_outcome="Submission successful",
            page_state=SAMPLE_PAGE_STATE,
        )
        assert result.passed is False
        vs.store_document.assert_called_once()

    def test_inspect_passed_does_not_store(self):
        """A passed inspect() result does not call store_finding."""
        vlm_resp = json.dumps({
            "passed": True, "confidence": 0.95,
            "reason": "OK", "anomalies": []
        })
        vs = _make_fake_vector_store()
        agent = InspectorAgent(vlm=_make_fake_vlm(vlm_resp), vector_store=vs)
        agent.inspect(
            screenshot_b64=SAMPLE_SCREENSHOT,
            step_desc="click(Button)",
            expected_outcome="",
            page_state=SAMPLE_PAGE_STATE,
        )
        vs.store_document.assert_not_called()


# ============================================================================
# P3-2: RAG recall of previous inspection records
# ============================================================================

class TestRAGRecall:
    """Test _recall_history and RAG prompt injection."""

    def test_recall_returns_history(self):
        vs = _make_fake_vector_store(search_results=[
            {"content": "Inspector rejected | URL: http://a.com | Action: click", "metadata": {"source": "inspector"}},
            {"content": "Inspector rejected | URL: http://b.com | Action: fill", "metadata": {"source": "inspector"}},
        ])
        agent = InspectorAgent(vector_store=vs)
        history = agent._recall_history("http://a.com", "click(Button)")
        assert "Inspector rejected" in history
        vs.search.assert_called_once_with("bugs", "Inspector click(Button) http://a.com", n_results=3)

    def test_recall_empty_when_no_results(self):
        vs = _make_fake_vector_store(search_results=[])
        agent = InspectorAgent(vector_store=vs)
        history = agent._recall_history("http://x.com", "click")
        assert history == ""

    def test_recall_filters_non_inspector_sources(self):
        vs = _make_fake_vector_store(search_results=[
            {"content": "some other bug", "metadata": {"source": "healer"}},
        ])
        agent = InspectorAgent(vector_store=vs)
        history = agent._recall_history("http://x.com", "click")
        assert history == ""

    def test_recall_disabled_when_config_off(self):
        vs = _make_fake_vector_store(search_results=[
            {"content": "data", "metadata": {"source": "inspector"}},
        ])
        agent = InspectorAgent(vector_store=vs)
        with patch("agents.inspector_agent.Config.INSPECTOR_ENABLE_RAG", False):
            history = agent._recall_history("http://x.com", "click")
        assert history == ""
        vs.search.assert_not_called()

    def test_recall_no_vector_store(self):
        agent = InspectorAgent(vector_store=None)
        agent._vector_store = None
        with patch("agents.inspector_agent.InspectorAgent.vector_store", new_callable=PropertyMock, return_value=None):
            history = agent._recall_history("http://x.com", "click")
        assert history == ""

    def test_recall_exception_returns_empty(self):
        vs = _make_fake_vector_store()
        vs.search.side_effect = RuntimeError("DB error")
        agent = InspectorAgent(vector_store=vs)
        history = agent._recall_history("http://x.com", "click")
        assert history == ""

    def test_history_injected_into_prompt(self):
        """RAG history is injected into the VLM prompt during inspect()."""
        vlm_resp = json.dumps({"passed": True, "confidence": 0.9, "reason": "ok", "anomalies": []})
        fake_vlm = _make_fake_vlm(vlm_resp)
        vs = _make_fake_vector_store(search_results=[
            {"content": "Inspector rejected | Historical record", "metadata": {"source": "inspector"}},
        ])
        agent = InspectorAgent(vlm=fake_vlm, vector_store=vs)
        agent.inspect(
            screenshot_b64=SAMPLE_SCREENSHOT,
            step_desc="click(Submit)",
            expected_outcome="",
            page_state=SAMPLE_PAGE_STATE,
        )
        # Check VLM was called with history in the prompt
        call_args = fake_vlm.invoke.call_args[0][0]
        prompt_text = call_args[0].content[0]["text"]
        assert "Prior review findings for the same page/action:" in prompt_text
        assert "Inspector rejected" in prompt_text


# ============================================================================
# P3-3: Confidence threshold calibration
# ============================================================================

class TestConfidenceThreshold:
    """Confidence threshold tests."""

    def test_low_confidence_rejection_auto_passes(self):
        """confidence < threshold: change rejection to pass."""
        vlm_resp = json.dumps({
            "passed": False, "confidence": 0.5,
            "reason": "maybe error", "anomalies": ["unsure"]
        })
        vs = _make_fake_vector_store()
        agent = InspectorAgent(
            vlm=_make_fake_vlm(vlm_resp),
            vector_store=vs,
            confidence_threshold=0.7,
        )
        result = agent.inspect(
            screenshot_b64=SAMPLE_SCREENSHOT,
            step_desc="click(Button)",
            expected_outcome="",
            page_state=SAMPLE_PAGE_STATE,
        )
        assert result.passed is True  # auto-passed
        assert result.confidence == 0.5
        assert "below threshold" in result.reason
        # Should NOT store since it was auto-passed
        vs.store_document.assert_not_called()

    def test_high_confidence_rejection_stays_rejected(self):
        """confidence >= threshold: retain rejection."""
        vlm_resp = json.dumps({
            "passed": False, "confidence": 0.85,
            "reason": "clear error", "anomalies": ["red banner"]
        })
        vs = _make_fake_vector_store()
        agent = InspectorAgent(
            vlm=_make_fake_vlm(vlm_resp),
            vector_store=vs,
            confidence_threshold=0.7,
        )
        result = agent.inspect(
            screenshot_b64=SAMPLE_SCREENSHOT,
            step_desc="click(Button)",
            expected_outcome="",
            page_state=SAMPLE_PAGE_STATE,
        )
        assert result.passed is False
        assert result.confidence == 0.85
        vs.store_document.assert_called_once()

    def test_exact_threshold_stays_rejected(self):
        """confidence == threshold: retain rejection because it is not strictly below the threshold."""
        vlm_resp = json.dumps({
            "passed": False, "confidence": 0.7,
            "reason": "borderline", "anomalies": []
        })
        vs = _make_fake_vector_store()
        agent = InspectorAgent(
            vlm=_make_fake_vlm(vlm_resp),
            vector_store=vs,
            confidence_threshold=0.7,
        )
        result = agent.inspect(
            screenshot_b64=SAMPLE_SCREENSHOT,
            step_desc="click(Button)",
            expected_outcome="",
            page_state=SAMPLE_PAGE_STATE,
        )
        assert result.passed is False
        assert result.confidence == 0.7

    def test_passed_result_ignores_threshold(self):
        """A passed result is unaffected by the threshold."""
        vlm_resp = json.dumps({
            "passed": True, "confidence": 0.3,
            "reason": "looks ok", "anomalies": []
        })
        agent = InspectorAgent(
            vlm=_make_fake_vlm(vlm_resp),
            confidence_threshold=0.7,
        )
        result = agent.inspect(
            screenshot_b64=SAMPLE_SCREENSHOT,
            step_desc="click(Button)",
            expected_outcome="",
            page_state=SAMPLE_PAGE_STATE,
        )
        assert result.passed is True
        assert result.confidence == 0.3

    def test_custom_threshold(self):
        """Custom threshold."""
        vlm_resp = json.dumps({
            "passed": False, "confidence": 0.85,
            "reason": "error", "anomalies": []
        })
        vs = _make_fake_vector_store()
        agent = InspectorAgent(
            vlm=_make_fake_vlm(vlm_resp),
            vector_store=vs,
            confidence_threshold=0.9,
        )
        result = agent.inspect(
            screenshot_b64=SAMPLE_SCREENSHOT,
            step_desc="click(Button)",
            expected_outcome="",
            page_state=SAMPLE_PAGE_STATE,
        )
        assert result.passed is True  # 0.85 < 0.9 → auto-pass
        assert "below threshold" in result.reason

    def test_zero_threshold_never_auto_passes(self):
        """threshold=0: retain every rejection."""
        vlm_resp = json.dumps({
            "passed": False, "confidence": 0.01,
            "reason": "maybe", "anomalies": []
        })
        vs = _make_fake_vector_store()
        agent = InspectorAgent(
            vlm=_make_fake_vlm(vlm_resp),
            vector_store=vs,
            confidence_threshold=0.0,
        )
        result = agent.inspect(
            screenshot_b64=SAMPLE_SCREENSHOT,
            step_desc="click(Button)",
            expected_outcome="",
            page_state=SAMPLE_PAGE_STATE,
        )
        assert result.passed is False
