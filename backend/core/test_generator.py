# -*- coding: utf-8 -*-
"""
Test Generator — enhanced test generation

Extend the existing RequirementParser with:
1. Multistage Chain-of-Thought prompts
2. Automatic negative scenarios
3. Boundary identification
4. Performance/security scenario templates
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class GeneratedTestCase:
    """Generated test case"""
    id: str = ""
    title: str = ""
    category: str = "functional"   # functional, boundary, negative, performance, security
    priority: str = "medium"       # high, medium, low
    preconditions: List[str] = field(default_factory=list)
    steps: List[Dict] = field(default_factory=list)
    expected_results: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "priority": self.priority,
            "preconditions": self.preconditions,
            "steps": self.steps,
            "expected_results": self.expected_results,
            "tags": self.tags,
        }


class TestGenerator:
    """
    Enhanced test generator

    Use multistage Chain-of-Thought (CoT) prompts:
    Stage 1: Extract test conditions from requirements
    Stage 2: Generate positive/negative/boundary scenarios for each condition
    Stage 3: Generate specific steps
    Stage 4: LLM-as-Judge quality review
    """

    STAGE1_PROMPT = """You are a senior QA test design expert.

## Task
Extract every testable condition from these requirements.

## Requirement Description
{requirement}

## Requirements
List all testable conditions as JSON, without Markdown fences:
{{
    "conditions": [
        {{
            "id": "C1",
            "description": "<Condition description>",
            "type": "<functional/validation/permission/data>",
            "inputs": ["<Relevant input fields>"],
            "constraints": ["<Constraints>"]
        }}
    ]
}}"""

    STAGE2_PROMPT = """Generate multidimensional test scenarios from these test conditions.

## Test Conditions
{condition}

## Requirements
Generate these types of scenario for this condition:
1. Happy path
2. Boundary conditions
3. Negative scenarios
4. Error recovery

Output JSON without Markdown fences:
{{
    "scenarios": [
        {{
            "title": "<Scenario title>",
            "category": "<functional/boundary/negative/error_recovery>",
            "priority": "<high/medium/low>",
            "description": "<Scenario description>",
            "test_data": "<Specific test data>"
        }}
    ]
}}"""

    STAGE3_PROMPT = """Convert this test scenario into steps executable by automation.

## Scenario
Title: {title}
Description: {description}
Category: {category}
Test data: {test_data}

## Requirements
Output JSON without Markdown fences:
{{
    "preconditions": ["<Precondition 1>"],
    "steps": [
        {{
            "step": 1,
            "action": "<Action description, such as entering 'xxx' in an input>",
            "expected": "<Expected result>"
        }}
    ],
    "expected_results": ["<Final expected result>"],
    "tags": ["<Tag>"]
}}"""

    REVIEW_PROMPT = """You are a QA test review expert. Assess the quality of these test cases.

## Requirements
{requirement}

## Generated Test Cases
{test_cases}

## Review Dimensions
1. Coverage completeness: Are important scenarios missing?
2. Executable steps: Are steps specific enough for automation?
3. Clear expectations: Are expected results explicit and verifiable?
4. Boundary coverage: Are boundaries and exceptions covered?

Output JSON without Markdown fences:
{{
    "overall_score": <1-10>,
    "coverage_score": <1-10>,
    "executability_score": <1-10>,
    "missing_scenarios": ["<Missing scenarios>"],
    "improvements": ["<Improvement recommendations>"]
}}"""

    def __init__(self):
        self._llm = None

    def _get_llm(self):
        if self._llm is None:
            from core.llm_manager import get_llm_for_role
            self._llm = get_llm_for_role("planner", temperature=0.3)
        return self._llm

    async def generate(
        self,
        requirement: str,
        categories: List[str] = None,
        with_review: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate test cases in multiple stages.

        Args:
            requirement: Requirement description
            categories: Category filter (functional/boundary/negative, etc.)
            with_review: Whether to enable LLM-as-Judge review

        Returns:
            Complete test generation result
        """
        import asyncio

        logger.info(f"🧪 Generating test cases: {requirement[:100]}...")

        # Stage 1: Extract test conditions
        conditions = await self._stage1_extract_conditions(requirement)
        if not conditions:
            return {"success": False, "error": "No testable conditions were extracted", "test_cases": []}

        # Stage 2: Generate multidimensional scenarios
        all_scenarios = []
        for cond in conditions:
            scenarios = await self._stage2_generate_scenarios(cond)
            all_scenarios.extend(scenarios)

        # Stage 3: Convert to executable steps
        test_cases = []
        for i, scenario in enumerate(all_scenarios):
            if categories and scenario.get("category") not in categories:
                continue
            tc = await self._stage3_generate_steps(scenario, i + 1)
            if tc:
                test_cases.append(tc)

        # Stage 4: Quality review
        review = None
        if with_review and test_cases:
            review = await self._stage4_review(requirement, test_cases)

        logger.info(f"✅ Generated {len(test_cases)} test cases")

        return {
            "success": True,
            "test_cases": [tc.to_dict() for tc in test_cases],
            "conditions_found": len(conditions),
            "scenarios_generated": len(all_scenarios),
            "review": review,
        }

    async def _stage1_extract_conditions(self, requirement: str) -> List[Dict]:
        """Stage 1: Extract test conditions"""
        try:
            import asyncio
            llm = self._get_llm()
            prompt = self.STAGE1_PROMPT.format(requirement=requirement)
            result = await asyncio.to_thread(llm.invoke, prompt)
            content = result.content if hasattr(result, "content") else str(result)
            data = self._parse_json(content)
            return data.get("conditions", [])
        except Exception as e:
            logger.error(f"Stage 1 failed: {e}")
            return []

    async def _stage2_generate_scenarios(self, condition: Dict) -> List[Dict]:
        """Stage 2: Generate multidimensional scenarios"""
        try:
            import asyncio
            llm = self._get_llm()
            prompt = self.STAGE2_PROMPT.format(condition=json.dumps(condition, ensure_ascii=False))
            result = await asyncio.to_thread(llm.invoke, prompt)
            content = result.content if hasattr(result, "content") else str(result)
            data = self._parse_json(content)
            return data.get("scenarios", [])
        except Exception as e:
            logger.error(f"Stage 2 failed: {e}")
            return []

    async def _stage3_generate_steps(self, scenario: Dict, index: int) -> Optional[GeneratedTestCase]:
        """Stage 3: Generate executable steps"""
        try:
            import asyncio
            llm = self._get_llm()
            prompt = self.STAGE3_PROMPT.format(
                title=scenario.get("title", ""),
                description=scenario.get("description", ""),
                category=scenario.get("category", "functional"),
                test_data=scenario.get("test_data", ""),
            )
            result = await asyncio.to_thread(llm.invoke, prompt)
            content = result.content if hasattr(result, "content") else str(result)
            data = self._parse_json(content)

            return GeneratedTestCase(
                id=f"TC_{index:03d}",
                title=scenario.get("title", f"Test case {index}"),
                category=scenario.get("category", "functional"),
                priority=scenario.get("priority", "medium"),
                preconditions=data.get("preconditions", []),
                steps=data.get("steps", []),
                expected_results=data.get("expected_results", []),
                tags=data.get("tags", []),
            )
        except Exception as e:
            logger.error(f"Stage 3 failed: {e}")
            return None

    async def _stage4_review(self, requirement: str, test_cases: List[GeneratedTestCase]) -> Optional[Dict]:
        """Stage 4: LLM-as-Judge review"""
        try:
            import asyncio
            llm = self._get_llm()
            tc_text = json.dumps([tc.to_dict() for tc in test_cases[:10]], ensure_ascii=False, indent=2)[:3000]
            prompt = self.REVIEW_PROMPT.format(requirement=requirement, test_cases=tc_text)
            result = await asyncio.to_thread(llm.invoke, prompt)
            content = result.content if hasattr(result, "content") else str(result)
            return self._parse_json(content)
        except Exception as e:
            logger.error(f"Stage 4 review failed: {e}")
            return None

    @staticmethod
    def _parse_json(text: str) -> Dict:
        """Parse JSON from LLM output"""
        t = text.strip()
        if t.startswith("```"):
            t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        if t.endswith("```"):
            t = t[:-3]
        return json.loads(t.strip())
