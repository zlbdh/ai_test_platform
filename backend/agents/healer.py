"""
Self-Healing Agent (自愈代理)
当 Executor 执行失败时，分析错误原因并生成修正后的步骤。
支持全部 18 种动作类型。
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
    自愈机制 (Self-Healing)
    当 Executor 执行失败时，Healer 分析错误原因并生成修正后的步骤。
    
    Args:
        failed_step: 失败的步骤 (包含 action, target, value)
        error_msg: 错误消息
        page_content: 页面内容摘要
        interactive_elements: 当前页面可交互元素列表
        history: 最近的操作历史
    
    Returns:
        修正后的步骤 Dict，或 None（无法修复）
    """
    
    # 构建历史摘要
    history_text = ""
    if history:
        recent = history[-5:]
        lines = []
        for i, h in enumerate(recent, 1):
            status_icon = "✅" if h.get('status') == 'success' else "❌"
            lines.append(f"  {i}. {status_icon} {h.get('action', '?')}({h.get('target', '')}) → {h.get('message', '')[:40]}")
        history_text = "\n".join(lines)
    else:
        history_text = "  （无历史记录）"
    
    prompt = ChatPromptTemplate.from_template(HEALER_PROMPT)
    
    try:
        chain = prompt | get_llm_for_role("executor") | JsonOutputParser()
        corrected_step = chain.invoke({
            "action": failed_step.get('action', ''),
            "target": failed_step.get('target', ''),
            "value": failed_step.get('value', ''),
            "error": error_msg[:500],
            "elements": interactive_elements[:1500] if interactive_elements else "（无元素信息）",
            "page_content": page_content[:1000] if page_content else "（无页面内容）",
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
