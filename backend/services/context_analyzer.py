import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ContextAnalyzer:
    """
    上下文分析器 (Smart Router): 
    根据用户输入的完整度（URL、需求描述、RAG文档），决定最佳的规划策略。
    """

    @staticmethod
    def analyze(requirement: str, target_url: str, rag_context: str) -> Dict[str, Any]:
        """
        分析输入，返回 {strategy, reasoning}
        Strategies:
        - EXPLORER: 仅有 URL，无详细需求 -> 探索性测试 (Crawl-First 必选)
        - VERIFICATION: URL + 详细需求/文档 -> 验证测试 (Crawl + RAG)
        - TDD: 仅需求，无 URL -> 设计模式 (只生成用例大纲)
        - WHITE_BOX: (暂未实现) 代码 + 需求
        """
        
        requirement_text = (requirement or "").strip()
        target_url_text = (target_url or "").strip()
        rag_context_text = (rag_context or "").strip()

        has_url = bool(target_url_text)
        has_context = len(rag_context_text) > 50  # 假设微量上下文不算
        req_length = len(requirement_text)
        
        strategy = "UNKNOWN"
        reasoning = []
        
        # 1. 判定 TDD 模式 (无 URL)
        if not has_url:
            strategy = "TDD"
            reasoning.append("No Target URL provided. Switching to TDD/Design Mode.")
            return {"strategy": strategy, "reasoning": "; ".join(reasoning)}
            
        # 2. 判定 Explorer 模式 (有 URL，但需求很模糊)
        # 简单启发式：需求字数少，且没检索到有效文档
        is_vague_req = req_length == 0 or (
            req_length < 20 and ("测试" in requirement_text or "test" in requirement_text.lower())
        )
        
        if has_url and (not has_context) and is_vague_req:
            strategy = "EXPLORER"
            reasoning.append("Target URL provided but requirement is vague and no RAG context found.")
            reasoning.append("Switching to Explorer Mode (Crawl -> SiteMap -> Explore).")
            return {"strategy": strategy, "reasoning": "; ".join(reasoning)}
            
        # 3. 判定 Verification 模式 (默认强模式)
        if has_url:
            strategy = "VERIFICATION"
            reasoning.append("Target URL and sufficient context/requirement provided.")
            reasoning.append("Switching to Verification Mode (Crawl + RAG -> Verify).")
            return {"strategy": strategy, "reasoning": "; ".join(reasoning)}
            
        return {"strategy": "VERIFICATION", "reasoning": "Fallback to default Verification mode."}
