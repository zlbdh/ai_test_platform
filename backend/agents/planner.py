import logging
from typing import List, Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from core.prompts import PLANNER_NODE_PROMPT
from core.llm_manager import get_llm_for_role
from services.knowledge import kb
from agents.state import EngineState, TestStep
from core.config import Config as settings
from core.parsers import DocumentParser

logger = logging.getLogger(__name__)

class PlannerNode:
    """
    Planning Agent (Planner)
    Responsibilities:
    1. Understand the user's natural-language requirements
    2. Retrieve PRD/API documents when RAG is enabled
    3. Generate structured test steps (TestPlan)
    """

    def plan(self, state: EngineState) -> EngineState:
        requirement = state["task"]
        logger.info(f"[Planner] Planning for: {requirement}")

        # 1. RAG Retrieve (Optional)
        context = ""
        if getattr(settings, 'ENABLE_RAG', True) and kb.get_status()['enabled']:
            # Search relevant docs
            docs = kb.query_knowledge(requirement, k=3)
            if docs:
                context = "\n---\n".join(docs)
                logger.info(f"[Planner] RAG Context Loaded ({len(docs)} chunks)")

        # 2. LLM Generate
        steps = self._generate_plan_llm(requirement, context)

        if not steps:
            state["error"] = "Failed to generate plan"
            return state

        state["plan"] = steps
        state["current_step_index"] = 0

        return state

    def _generate_plan_llm(self, requirement: str, context: str) -> List[TestStep]:

        prompt = ChatPromptTemplate.from_template(PLANNER_NODE_PROMPT)

        chain = prompt | get_llm_for_role("planner") | JsonOutputParser()

        try:
            res = chain.invoke({"requirement": requirement, "context": context})
            # Validate format (Simple check)
            valid_steps = []
            for item in res:
                valid_steps.append({
                    "action": item.get("action", "wait"),
                    "target": item.get("target", ""),
                    "value": item.get("value", ""),
                    "selector": item.get("selector", "")
                })
            return valid_steps
        except Exception as e:
            logger.error(f"[Planner] Planning Error: {e}")
            return []
