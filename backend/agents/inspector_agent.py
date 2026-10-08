# -*- coding: utf-8 -*-
"""
Inspector Agent — visual quality reviewer
Review screenshots after each step to check whether the business outcome is correct.
Complements Healer (DOM locator repair) and Judge (semantic text assertions):
Inspector focuses on actions that succeed technically but produce an incorrect business outcome.

Phase 3 enhancements:
- store_finding(): Write rejected results to the ChromaDB bugs collection
- RAG retrieval: fetch prior findings for the same page/action from the bugs collection before review
- Confidence threshold: automatically pass results when confidence < threshold
"""
import json
import logging
import time
from typing import Optional, List

from core.models import InspectionResult
from core.prompts import INSPECTOR_VISION_PROMPT
from core.llm_manager import get_vision_llm
from core.config import Config

logger = logging.getLogger(__name__)

# Actions exempt from review because they do not produce business outcomes
SKIP_ACTIONS = frozenset({"goto", "wait", "scroll", "screenshot", "set_var", "done"})


class InspectorAgent:
    """Visual quality reviewer: inspect screenshots after each step to assess business correctness"""

    def __init__(self, vlm=None, vector_store=None, confidence_threshold: float = None):
        """
        Args:
            vlm: Optional VLM instance; inject a fake in tests.
                 If None, load lazily through get_vision_llm() at runtime.
            vector_store: Optional VectorStore instance; inject a mock in tests.
            confidence_threshold: Confidence threshold; automatically pass results below this value.
                                  Defaults to Config.INSPECTOR_CONFIDENCE_THRESHOLD.
        """
        self._vlm = vlm
        self._vector_store = vector_store
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else Config.INSPECTOR_CONFIDENCE_THRESHOLD
        )

    @property
    def vlm(self):
        if self._vlm is None:
            self._vlm = get_vision_llm()
        return self._vlm

    @property
    def vector_store(self):
        if self._vector_store is None:
            try:
                from core.vector_store import get_vector_store
                self._vector_store = get_vector_store()
            except Exception as e:
                logger.warning(f"[Inspector] VectorStore unavailable: {e}")
        return self._vector_store

    @staticmethod
    def should_inspect(action: str) -> bool:
        """Determine whether the action requires Inspector review"""
        return action not in SKIP_ACTIONS

    def inspect(
        self,
        screenshot_b64: str,
        step_desc: str,
        expected_outcome: str,
        page_state: dict,
    ) -> InspectionResult:
        """
        Review a screenshot and return a pass/reject decision.

        Args:
            screenshot_b64: Page screenshot after execution (base64 JPEG)
            step_desc: Description of the action just executed (such as "click(Submit button)")
            expected_outcome: Expected business outcome (such as "A success message should appear")
            page_state: Current page-state dictionary (url, title, visible_text, etc.)

        Returns:
            InspectionResult(passed, confidence, reason, anomalies)
        """
        vision_llm = self.vlm
        if vision_llm is None:
            logger.warning("[Inspector] Vision LLM not available, auto-passing.")
            return InspectionResult(
                passed=True,
                confidence=0.0,
                reason="Vision LLM unavailable, skipped inspection",
            )

        url = page_state.get("url", "unknown")
        visible_text = page_state.get("visible_text", "")
        if isinstance(visible_text, list):
            visible_text = " | ".join(visible_text)
        # Truncate to avoid token overflow
        visible_text = visible_text[:2000]

        # Phase 3: Retrieve prior review findings through RAG
        history_context = self._recall_history(url, step_desc)

        prompt_text = INSPECTOR_VISION_PROMPT.format(
            step_desc=step_desc,
            expected_outcome=expected_outcome or "The action should complete normally without errors",
            url=url,
            visible_text=visible_text,
        )

        # Append prior findings to the prompt when available
        if history_context:
            prompt_text += f"\n\nPrior review findings for the same page/action:\n{history_context}"

        # Build multimodal message with screenshot
        from langchain_core.messages import HumanMessage

        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt_text},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{screenshot_b64}",
                    },
                },
            ]
        )

        try:
            from core.llm_manager import invoke_with_fallback
            response = invoke_with_fallback(vision_llm, [message])
            result_text = response.content if hasattr(response, "content") else str(response)
            result = self._parse_result(result_text)

            # Phase 3: Confidence-threshold calibration: automatically pass low-confidence results
            if not result.passed and result.confidence < self.confidence_threshold:
                logger.info(
                    f"[Inspector] Confidence {result.confidence:.0%} < threshold "
                    f"{self.confidence_threshold:.0%}, auto-passing despite rejection"
                )
                result = InspectionResult(
                    passed=True,
                    confidence=result.confidence,
                    reason=f"Auto-passed: confidence {result.confidence:.0%} below threshold {self.confidence_threshold:.0%}. Original: {result.reason}",
                    anomalies=result.anomalies,
                )

            # Phase 3: Write rejected results to ChromaDB
            if not result.passed:
                self.store_finding(
                    url=url,
                    step_desc=step_desc,
                    result=result,
                )

            return result
        except Exception as e:
            logger.error(f"[Inspector] VLM invocation failed: {e}")
            return InspectionResult(
                passed=True,
                confidence=0.0,
                reason=f"VLM error, auto-passing: {e}",
            )

    def store_finding(
        self,
        url: str,
        step_desc: str,
        result: InspectionResult,
    ) -> Optional[str]:
        """
        Write rejected review results to the ChromaDB bugs collection (Phase 3: memory feedback loop).

        Args:
            url: Page URL
            step_desc: Action description
            result: Review result

        Returns:
            Stored document ID, or None on failure
        """
        vs = self.vector_store
        if vs is None:
            logger.warning("[Inspector] VectorStore unavailable, skipping store_finding")
            return None

        content = (
            f"Inspector rejected | URL: {url} | Action: {step_desc} | "
            f"Reason: {result.reason} | Anomalies: {', '.join(result.anomalies)} | "
            f"Confidence: {result.confidence:.0%}"
        )
        metadata = {
            "source": "inspector",
            "url": url,
            "step_desc": step_desc,
            "confidence": result.confidence,
            "anomaly_count": len(result.anomalies),
            "timestamp": time.time(),
        }

        try:
            doc_id = vs.store_document("bugs", content, metadata)
            logger.info(f"[Inspector] Finding stored to ChromaDB: {doc_id}")
            return doc_id
        except Exception as e:
            logger.warning(f"[Inspector] Failed to store finding: {e}")
            return None

    def _recall_history(self, url: str, step_desc: str) -> str:
        """
        Retrieve prior review findings for the same page/action from the ChromaDB bugs collection using RAG (Phase 3: memory feedback loop).

        Args:
            url: Current page URL
            step_desc: Current action description

        Returns:
            Prior findings as text; empty when no records exist or the feature is disabled
        """
        if not Config.INSPECTOR_ENABLE_RAG:
            return ""

        vs = self.vector_store
        if vs is None:
            return ""

        query = f"Inspector {step_desc} {url}"
        try:
            results = vs.search("bugs", query, n_results=3)
            if not results:
                return ""

            # Keep only records from the inspector
            inspector_results = [
                r for r in results
                if r.get("metadata", {}).get("source") == "inspector"
            ]
            if not inspector_results:
                return ""

            lines = []
            for r in inspector_results[:3]:
                content = r.get("content", "")[:300]
                lines.append(f"- {content}")

            return "\n".join(lines)
        except Exception as e:
            logger.debug(f"[Inspector] RAG recall failed (non-critical): {e}")
            return ""

    @staticmethod
    def _parse_result(raw: str) -> InspectionResult:
        """Parse the VLM's JSON response into an InspectionResult"""
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last fence lines
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
            return InspectionResult(
                passed=bool(data.get("passed", True)),
                confidence=float(data.get("confidence", 0.5)),
                reason=str(data.get("reason", "")),
                anomalies=list(data.get("anomalies", [])),
            )
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning(f"[Inspector] JSON parse failed, auto-passing: {e}")
            return InspectionResult(
                passed=True,
                confidence=0.0,
                reason=f"JSON parse error, auto-passing: {raw[:200]}",
            )
