"""
Master Agent - primary planner
Handles task decomposition, agent coordination, and result aggregation
"""
from typing import Dict, Any, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from core.config import Config
from core.llm_manager import get_llm_for_role
from core.state import QAState
from skills.knowledge_tools import get_similar_test_plans, get_prd_context, get_api_documentation
from langchain_core.output_parsers import JsonOutputParser


from core.prompts import PLAN_TEST_SYSTEM, PLAN_TEST_USER_TEMPLATE, AGENT_EXTRACTION_PROMPT
import logging

logger = logging.getLogger(__name__)

class MasterAgent:
    """Primary planning agent"""

    def __init__(self):
        """Initialize Master Agent"""
        self.llm = get_llm_for_role("executor")

        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", PLAN_TEST_SYSTEM),
            ("human", PLAN_TEST_USER_TEMPLATE)
        ])

    def plan_test(self, scenario: str, prd_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Plan test tasks (enhanced: integrates the vector database)

        Args:
            scenario: Test scenario description
            prd_context: Optional PRD context

        Returns:
            Test plan
        """
        # Retrieve similar test plans from the vector database
        similar_plans = []
        try:
            similar_plans = get_similar_test_plans.invoke({
                "scenario": scenario,
                "n_results": 3
            })
        except Exception as e:
            logger.warning(f"  [Master Agent] Vector database retrieval failed: {str(e)}")

        # Get PRD context
        prd_info = []
        if prd_context:
            try:
                prd_info = get_prd_context.invoke({
                    "query": scenario,
                    "n_results": 2
                })
            except Exception as e:
                pass

        # Build an enhanced prompt with references to previous plans
        enhanced_prompt = f"Test scenario: {scenario}\n\n"

        if similar_plans:
            enhanced_prompt += "Reference similar historical test plans:\n"
            for plan in similar_plans[:2]:
                plan_content = plan.get("content", "")[:200]
                enhanced_prompt += f"- {plan_content}\n"
            enhanced_prompt += "\n"

        if prd_info:
            enhanced_prompt += "PRD context:\n"
            for info in prd_info[:1]:
                info_content = info.get("content", "")[:200]
                enhanced_prompt += f"- {info_content}\n"
            enhanced_prompt += "\n"

        enhanced_prompt += "Decompose the task and plan the execution steps."

        chain = self.prompt_template | self.llm | StrOutputParser()
        plan_text = chain.invoke({"scenario": enhanced_prompt})

        # Parse the plan
        plan = {
            "scenario": scenario,
            "plan_text": plan_text,
            "required_agents": self._extract_agents(plan_text),
            "steps": self._extract_steps(plan_text),
            "similar_plans_referenced": len(similar_plans),
            "prd_context_used": len(prd_info) > 0
        }

        return plan

    def _extract_agents(self, plan_text: str) -> List[str]:
        """Extract required agents from the plan (LLM reasoning with keyword fallback)"""
        # Prefer LLM reasoning
        try:
            prompt = ChatPromptTemplate.from_template(AGENT_EXTRACTION_PROMPT)
            chain = prompt | get_llm_for_role("executor") | JsonOutputParser()
            result = chain.invoke({"plan_text": plan_text})
            agents = result.get("agents", [])
            valid_agents = {"ui_agent", "api_agent", "data_agent", "ops_agent"}
            llm_agents = [a for a in agents if a in valid_agents]
            if llm_agents:
                logger.info(f"[MasterAgent] LLM-extracted agents: {llm_agents} | {result.get('reasoning', '')}")
                return llm_agents
        except Exception as e:
            logger.warning(f"[MasterAgent] LLM agent extraction failed; falling back to keywords: {e}")

        # Fallback: Keyword matching
        agents = []
        plan_lower = plan_text.lower()

        if "ui" in plan_lower or "前端" in plan_lower or "界面" in plan_lower:
            agents.append("ui_agent")
        if "api" in plan_lower or "接口" in plan_lower or "后端" in plan_lower:
            agents.append("api_agent")
        if "data" in plan_lower or "数据" in plan_lower or "数据库" in plan_lower:
            agents.append("data_agent")
        if "ops" in plan_lower or "日志" in plan_lower or "运维" in plan_lower:
            agents.append("ops_agent")

        # Require at least UI and API by default
        if not agents:
            agents = ["ui_agent", "api_agent"]

        return agents

    def _extract_steps(self, plan_text: str) -> List[str]:
        """Extract steps from the plan text"""
        # Simplified approach: extract steps by keyword
        steps = []
        lines = plan_text.split('\n')

        for i, line in enumerate(lines):
            if any(keyword in line for keyword in ['1.', '2.', '3.', '步骤', 'step']):
                steps.append(line.strip())

        # Create default steps if none are found
        if not steps:
            steps = [
                "1. UI Agent runs frontend tests",
                "2. API Agent runs API tests",
                "3. Data Agent verifies data consistency",
                "4. Aggregate results and generate a report"
            ]

        return steps

    def generate_report(self, state: QAState) -> Dict[str, Any]:
        """
        Generate the final test report

        Args:
            state: QA state

        Returns:
            Test report
        """
        report = {
            "test_scenario": state.get("test_scenario", ""),
            "task_description": state.get("task_description", ""),
            "summary": {
                "total_steps": len(state.get("completed_steps", [])),
                "failed_steps": len(state.get("failed_steps", [])),
                "success_rate": self._calculate_success_rate(state),
                "inspection_total": len(state.get("inspection_results", [])),
                "inspection_passed": sum(1 for r in state.get("inspection_results", []) if r.get("passed")),
                "inspection_rejected": sum(1 for r in state.get("inspection_results", []) if not r.get("passed")),
            },
            "ui_results": state.get("ui_results", []),
            "api_results": state.get("api_results", []),
            "data_results": state.get("data_results", []),
            "ops_results": state.get("ops_results", []),
            "inspection_results": state.get("inspection_results", []),
            "errors": state.get("errors", []),
            "warnings": state.get("warnings", []),
            "recommendations": self._generate_recommendations(state)
        }

        return report

    def _calculate_success_rate(self, state: QAState) -> float:
        """Calculate the success rate"""
        completed = len(state.get("completed_steps", []))
        failed = len(state.get("failed_steps", []))
        total = completed + failed

        if total == 0:
            return 0.0

        return (completed / total) * 100

    def _generate_recommendations(self, state: QAState) -> List[str]:
        """Generate recommendations"""
        recommendations = []

        errors = state.get("errors", [])
        if errors:
            recommendations.append(f"Found {len(errors)} errors; prioritize fixing them")

        failed_steps = state.get("failed_steps", [])
        if failed_steps:
            recommendations.append(f"The following steps failed: {', '.join(failed_steps)}")

        # Recommendations for Inspector rejections
        rejected = [r for r in state.get("inspection_results", []) if not r.get("passed")]
        if rejected:
            recommendations.append(f"Inspector rejected {len(rejected)} items during visual review; check the related screenshots and anomaly descriptions")
            for r in rejected[:3]:
                recommendations.append(f"  - {r.get('step', '?')}: {r.get('reason', 'Unknown reason')}")

        if not errors and not failed_steps and not rejected:
            recommendations.append("All tests passed; ready for release")

        return recommendations
