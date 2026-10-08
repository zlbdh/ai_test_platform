"""
Judge Agent — semantic evaluation of test results
Uses planner_service.semantic_verify consistently.
Retained as a backward-compatible interface referenced by react.py / executor.py.
"""
import logging

logger = logging.getLogger(__name__)


def semantic_judge(expected_intent: str, page_content: str) -> bool:
    """
    Determine whether the page content semantically satisfies the expected intent.

    Use the shared implementation by calling planner_service.semantic_verify,
    avoiding duplicate semantic verification logic.

    Returns: True = PASS, False = FAIL
    """
    try:
        from services.planner_service import planner_service
        result = planner_service.semantic_verify(
            assertion=expected_intent,
            page_context={"url": "", "visible_text": page_content[:2000]}
        )

        passed = result.get('passed', False)
        reason = result.get('reason', 'None')
        logger.info(f"[Judge] Ruling: Intent='{expected_intent}' → Verdict={'PASS' if passed else 'FAIL'} ({reason})")
        return passed
    except Exception as e:
        logger.warning(f"[Judge] Error: {e}")
        return False
