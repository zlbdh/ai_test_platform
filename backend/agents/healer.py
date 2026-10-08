"""
Self-Healing Agent
When Executor fails, analyze the cause and generate a corrected step.
Supports all 18 action types.
"""
import logging
from typing import Optional, Dict, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from core.llm_manager import get_llm_for_role
from core.config import Config
from core.prompts import HEALER_PROMPT

logger = logging.getLogger(__name__)


def self_heal(
    failed_step: Dict,
    error_msg: str,
    page_content: str,
    interactive_elements: str = "",
    history: List[Dict] = None
) -> Optional[Dict]:
    """
    Self-healing mechanism
    When Executor fails, Healer analyzes the cause and generates a corrected step.

    Args:
        failed_step: Failed step (including action, target, and value)
        error_msg: Error message
        page_content: Page content summary
        interactive_elements: List of interactive elements on the current page
        history: Recent action history

    Returns:
        Corrected step dictionary, or None if recovery is impossible
    """

    # Build a history summary
    history_text = ""
    if history:
        recent = history[-5:]
        lines = []
        for i, h in enumerate(recent, 1):
            status_icon = "✅" if h.get('status') == 'success' else "❌"
            lines.append(f"  {i}. {status_icon} {h.get('action', '?')}({h.get('target', '')}) → {h.get('message', '')[:40]}")
        history_text = "\n".join(lines)
    else:
        history_text = "  (No history)"

    prompt = ChatPromptTemplate.from_template(HEALER_PROMPT)

    try:
        chain = prompt | get_llm_for_role("executor") | JsonOutputParser()
        corrected_step = chain.invoke({
            "action": failed_step.get('action', ''),
            "target": failed_step.get('target', ''),
            "value": failed_step.get('value', ''),
            "error": error_msg[:500],
            "elements": interactive_elements[:1500] if interactive_elements else "(No element information)",
            "page_content": page_content[:1000] if page_content else "(No page content)",
            "history": history_text,
        })

        if corrected_step.get('action') == 'skip':
            logger.warning(f"[Healer] Cannot heal: {corrected_step.get('value', 'unknown reason')}")
            return None

        logger.info(f"[Healer] Healed: {failed_step.get('action')}({failed_step.get('target')}) → {corrected_step.get('action')}({corrected_step.get('target')})")
        return corrected_step
    except Exception as e:
        logger.error(f"[Healer] Self-heal LLM call failed: {e}")
        return None
