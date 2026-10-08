import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ContextAnalyzer:
    """
    Context analyzer (smart router).
    Choose the best planning strategy based on the completeness of the URL, requirements, and RAG documents.
    """

    @staticmethod
    def analyze(requirement: str, target_url: str, rag_context: str) -> Dict[str, Any]:
        """
        Analyze input and return {strategy, reasoning}.
        Strategies:
        - EXPLORER: URL with no detailed requirements; exploratory testing with mandatory crawl-first.
        - VERIFICATION: URL with detailed requirements or documents; verification using crawl and RAG.
        - TDD: Requirements without a URL; design mode generating case outlines only.
        - WHITE_BOX: Code with requirements (not yet implemented).
        """
        
        requirement_text = (requirement or "").strip()
        target_url_text = (target_url or "").strip()
        rag_context_text = (rag_context or "").strip()

        has_url = bool(target_url_text)
        has_context = len(rag_context_text) > 50  # Treat minimal context as insufficient
        req_length = len(requirement_text)
        
        strategy = "UNKNOWN"
        reasoning = []
        
        # 1. Determine TDD mode when no URL is supplied
        if not has_url:
            strategy = "TDD"
            reasoning.append("No Target URL provided. Switching to TDD/Design Mode.")
            return {"strategy": strategy, "reasoning": "; ".join(reasoning)}
            
        # 2. Determine Explorer mode when a URL is present but requirements are vague
        # Simple heuristic: short requirements and no useful retrieved documents
        is_vague_req = req_length == 0 or (
            req_length < 20 and ("测试" in requirement_text or "test" in requirement_text.lower())
        )
        
        if has_url and (not has_context) and is_vague_req:
            strategy = "EXPLORER"
            reasoning.append("Target URL provided but requirement is vague and no RAG context found.")
            reasoning.append("Switching to Explorer Mode (Crawl -> SiteMap -> Explore).")
            return {"strategy": strategy, "reasoning": "; ".join(reasoning)}
            
        # 3. Determine Verification mode as the default comprehensive mode
        if has_url:
            strategy = "VERIFICATION"
            reasoning.append("Target URL and sufficient context/requirement provided.")
            reasoning.append("Switching to Verification Mode (Crawl + RAG -> Verify).")
            return {"strategy": strategy, "reasoning": "; ".join(reasoning)}
            
        return {"strategy": "VERIFICATION", "reasoning": "Fallback to default Verification mode."}
