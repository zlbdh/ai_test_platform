"""
Judge Agent (判断代理) — 语义测试结果判断
统一通过 planner_service.semantic_verify 实现。
保留此文件作为向后兼容接口 (react.py / executor.py 引用)。
"""
import logging

logger = logging.getLogger(__name__)


def semantic_judge(expected_intent: str, page_content: str) -> bool:
    """
    判断页面内容是否语义满足预期意图。
    
    统一底层实现：调用 planner_service.semantic_verify，
    避免与 semantic_verify 功能重复。
    
    Returns: True = PASS, False = FAIL
    """
    try:
        from services.planner_service import planner_service
        result = planner_service.semantic_verify(
            assertion=expected_intent,
            page_context={"url": "", "visible_text": page_content[:2000]}
        )
        
        passed = result.get('passed', False)
        reason = result.get('reason', '无')
        logger.info(f"[Judge] Ruling: Intent='{expected_intent}' → Verdict={'PASS' if passed else 'FAIL'} ({reason})")
        return passed
    except Exception as e:
        logger.warning(f"[Judge] Error: {e}")
        return False
