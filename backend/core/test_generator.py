# -*- coding: utf-8 -*-
"""
Test Generator — 增强型测试生成器

在现有 RequirementParser 基础上扩展：
1. 多阶段 Chain-of-Thought Prompt
2. 负面场景自动生成
3. 边界条件识别
4. 性能/安全场景模板
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class GeneratedTestCase:
    """生成的测试用例"""
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
    增强型测试生成器

    使用 Chain-of-Thought (CoT) 多阶段 Prompt：
    Stage 1: 从需求提取测试条件
    Stage 2: 为每个条件生成正面/负面/边界场景
    Stage 3: 生成具体步骤
    Stage 4: LLM-as-Judge 质量审查
    """

    STAGE1_PROMPT = """你是资深QA测试设计专家。

## 任务
从以下需求中提取所有可测试的条件。

## 需求描述
{requirement}

## 要求
请列出所有可测试的条件，输出JSON格式（不要markdown包裹）：
{{
    "conditions": [
        {{
            "id": "C1",
            "description": "<条件描述>",
            "type": "<functional/validation/permission/data>",
            "inputs": ["<涉及的输入字段>"],
            "constraints": ["<约束条件>"]
        }}
    ]
}}"""

    STAGE2_PROMPT = """基于以下测试条件，生成多维度测试场景。

## 测试条件
{condition}

## 要求
为此条件生成以下类型的测试场景：
1. 正常路径（Happy Path）
2. 边界条件（Boundary）
3. 负面场景（Negative）
4. 异常恢复（Error Recovery）

输出JSON格式（不要markdown包裹）：
{{
    "scenarios": [
        {{
            "title": "<场景标题>",
            "category": "<functional/boundary/negative/error_recovery>",
            "priority": "<high/medium/low>",
            "description": "<场景描述>",
            "test_data": "<具体测试数据>"
        }}
    ]
}}"""

    STAGE3_PROMPT = """将以下测试场景转化为自动化可执行的步骤。

## 场景
标题: {title}
描述: {description}
类别: {category}
测试数据: {test_data}

## 要求
输出JSON格式（不要markdown包裹）：
{{
    "preconditions": ["<前置条件1>"],
    "steps": [
        {{
            "step": 1,
            "action": "<操作描述，如：在输入框中输入'xxx'>",
            "expected": "<预期结果>"
        }}
    ],
    "expected_results": ["<最终预期结果>"],
    "tags": ["<标签>"]
}}"""

    REVIEW_PROMPT = """你是QA测试评审专家。请评审以下测试用例的质量。

## 需求
{requirement}

## 生成的测试用例
{test_cases}

## 评审维度
1. 覆盖完整性：是否遗漏了重要场景？
2. 步骤可执行性：步骤是否具体到可以自动化执行？
3. 预期明确性：预期结果是否明确可验证？
4. 边界考虑：是否覆盖了边界和异常情况？

输出JSON格式（不要markdown包裹）：
{{
    "overall_score": <1-10>,
    "coverage_score": <1-10>,
    "executability_score": <1-10>,
    "missing_scenarios": ["<遗漏的场景>"],
    "improvements": ["<改进建议>"]
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
        多阶段测试用例生成。

        Args:
            requirement: 需求描述
            categories: 生成类别过滤（functional/boundary/negative等）
            with_review: 是否启用 LLM-as-Judge 评审

        Returns:
            完整的测试生成结果
        """
        import asyncio

        logger.info(f"🧪 开始生成测试用例: {requirement[:100]}...")

        # Stage 1: 提取测试条件
        conditions = await self._stage1_extract_conditions(requirement)
        if not conditions:
            return {"success": False, "error": "未提取到可测试条件", "test_cases": []}

        # Stage 2: 生成多维场景
        all_scenarios = []
        for cond in conditions:
            scenarios = await self._stage2_generate_scenarios(cond)
            all_scenarios.extend(scenarios)

        # Stage 3: 转化为可执行步骤
        test_cases = []
        for i, scenario in enumerate(all_scenarios):
            if categories and scenario.get("category") not in categories:
                continue
            tc = await self._stage3_generate_steps(scenario, i + 1)
            if tc:
                test_cases.append(tc)

        # Stage 4: 质量审查
        review = None
        if with_review and test_cases:
            review = await self._stage4_review(requirement, test_cases)

        logger.info(f"✅ 生成完成: {len(test_cases)} 个测试用例")

        return {
            "success": True,
            "test_cases": [tc.to_dict() for tc in test_cases],
            "conditions_found": len(conditions),
            "scenarios_generated": len(all_scenarios),
            "review": review,
        }

    async def _stage1_extract_conditions(self, requirement: str) -> List[Dict]:
        """Stage 1: 提取测试条件"""
        try:
            import asyncio
            llm = self._get_llm()
            prompt = self.STAGE1_PROMPT.format(requirement=requirement)
            result = await asyncio.to_thread(llm.invoke, prompt)
            content = result.content if hasattr(result, "content") else str(result)
            data = self._parse_json(content)
            return data.get("conditions", [])
        except Exception as e:
            logger.error(f"Stage 1 失败: {e}")
            return []

    async def _stage2_generate_scenarios(self, condition: Dict) -> List[Dict]:
        """Stage 2: 生成多维场景"""
        try:
            import asyncio
            llm = self._get_llm()
            prompt = self.STAGE2_PROMPT.format(condition=json.dumps(condition, ensure_ascii=False))
            result = await asyncio.to_thread(llm.invoke, prompt)
            content = result.content if hasattr(result, "content") else str(result)
            data = self._parse_json(content)
            return data.get("scenarios", [])
        except Exception as e:
            logger.error(f"Stage 2 失败: {e}")
            return []

    async def _stage3_generate_steps(self, scenario: Dict, index: int) -> Optional[GeneratedTestCase]:
        """Stage 3: 生成可执行步骤"""
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
                title=scenario.get("title", f"测试用例 {index}"),
                category=scenario.get("category", "functional"),
                priority=scenario.get("priority", "medium"),
                preconditions=data.get("preconditions", []),
                steps=data.get("steps", []),
                expected_results=data.get("expected_results", []),
                tags=data.get("tags", []),
            )
        except Exception as e:
            logger.error(f"Stage 3 失败: {e}")
            return None

    async def _stage4_review(self, requirement: str, test_cases: List[GeneratedTestCase]) -> Optional[Dict]:
        """Stage 4: LLM-as-Judge 评审"""
        try:
            import asyncio
            llm = self._get_llm()
            tc_text = json.dumps([tc.to_dict() for tc in test_cases[:10]], ensure_ascii=False, indent=2)[:3000]
            prompt = self.REVIEW_PROMPT.format(requirement=requirement, test_cases=tc_text)
            result = await asyncio.to_thread(llm.invoke, prompt)
            content = result.content if hasattr(result, "content") else str(result)
            return self._parse_json(content)
        except Exception as e:
            logger.error(f"Stage 4 评审失败: {e}")
            return None

    @staticmethod
    def _parse_json(text: str) -> Dict:
        """解析 LLM 输出中的 JSON"""
        t = text.strip()
        if t.startswith("```"):
            t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        if t.endswith("```"):
            t = t[:-3]
        return json.loads(t.strip())
