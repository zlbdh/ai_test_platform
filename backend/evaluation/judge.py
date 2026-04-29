# -*- coding: utf-8 -*-
"""
LLM-as-Judge — 用 LLM 评估另一个 LLM 的输出质量

支持多维度评分（0-10）、结构化评估输出。
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import json
import logging
import time

logger = logging.getLogger(__name__)


@dataclass
class JudgeResult:
    """LLM-as-Judge 评估结果"""
    scores: Dict[str, float] = field(default_factory=dict)   # 维度 → 0-10 分
    overall_score: float = 0.0
    reasoning: str = ""
    suggestions: list = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "scores": self.scores,
            "overall_score": round(self.overall_score, 2),
            "reasoning": self.reasoning,
            "suggestions": self.suggestions,
            "timestamp": self.timestamp,
        }


class LLMJudge:
    """
    使用 LLM 评估 Agent 输出质量。

    评估维度：
    - completeness（完整性）: 是否覆盖目标要求
    - accuracy（准确性）: 操作是否精确无误
    - efficiency（效率）: 步骤是否简洁，无多余操作
    - robustness（鲁棒性）: 是否处理了边界情况
    - clarity（清晰度）: 输出描述是否清晰
    """

    JUDGE_PROMPT = """你是一位资深QA评审专家。请评估以下AI测试Agent的执行表现。

## 测试目标
{goal}

## 计划步骤
{planned_steps}

## 实际执行
{executed_steps}

## 执行结果
{result}

## 评估维度（每项 0-10 分）

请从以下5个维度评估，并输出JSON格式：

1. **completeness**（完整性）: 是否覆盖了测试目标的所有方面
2. **accuracy**（准确性）: 每步操作是否精确，结果是否正确
3. **efficiency**（效率）: 步骤是否精简，Token消耗是否合理
4. **robustness**（鲁棒性）: 是否妥善处理了异常和边界情况
5. **clarity**（清晰度）: 日志和反馈描述是否清晰有用

请严格输出以下JSON格式（不要加markdown包裹）：
{{
    "completeness": <0-10>,
    "accuracy": <0-10>,
    "efficiency": <0-10>,
    "robustness": <0-10>,
    "clarity": <0-10>,
    "reasoning": "<总体评价，2-3句话>",
    "suggestions": ["<改进建议1>", "<改进建议2>"]
}}"""

    def __init__(self, llm_provider: str = "", model: str = ""):
        self.llm_provider = llm_provider
        self.model = model

    async def judge(
        self,
        goal: str,
        planned_steps: list,
        executed_steps: list,
        result: dict,
    ) -> JudgeResult:
        """执行 LLM-as-Judge 评估"""
        try:
            from core.llm_manager import get_llm_for_role

            llm = get_llm_for_role("executor", temperature=0.1)

            prompt = self.JUDGE_PROMPT.format(
                goal=goal,
                planned_steps=json.dumps(planned_steps, ensure_ascii=False, indent=2)[:2000],
                executed_steps=json.dumps(executed_steps, ensure_ascii=False, indent=2)[:2000],
                result=json.dumps(result, ensure_ascii=False, indent=2)[:1000],
            )

            response = await self._invoke_llm(llm, prompt)
            return self._parse_response(response)

        except Exception as e:
            logger.error(f"LLM-as-Judge 评估失败: {e}")
            return JudgeResult(
                reasoning=f"评估失败: {str(e)}",
            )

    async def _invoke_llm(self, llm, prompt: str) -> str:
        """调用 LLM"""
        try:
            # 尝试异步调用
            result = await llm.ainvoke(prompt)
            return result.content if hasattr(result, "content") else str(result)
        except Exception:
            # 回退到同步
            import asyncio
            result = await asyncio.to_thread(llm.invoke, prompt)
            return result.content if hasattr(result, "content") else str(result)

    def _parse_response(self, response: str) -> JudgeResult:
        """解析 LLM 响应为结构化结果"""
        try:
            # 清理可能的 markdown 包裹
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            data = json.loads(text)

            scores = {}
            for dim in ["completeness", "accuracy", "efficiency", "robustness", "clarity"]:
                scores[dim] = float(data.get(dim, 5))

            overall = sum(scores.values()) / len(scores) if scores else 0

            return JudgeResult(
                scores=scores,
                overall_score=overall,
                reasoning=data.get("reasoning", ""),
                suggestions=data.get("suggestions", []),
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"LLM Judge 响应解析失败: {e}, raw: {response[:200]}")
            return JudgeResult(
                overall_score=5.0,
                reasoning=f"响应解析失败，原始文本: {response[:200]}",
            )

    def judge_sync(
        self,
        goal: str,
        planned_steps: list,
        executed_steps: list,
        result: dict,
    ) -> JudgeResult:
        """同步版本的 LLM-as-Judge"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.judge(goal, planned_steps, executed_steps, result)
                    )
                    return future.result(timeout=60)
            else:
                return loop.run_until_complete(
                    self.judge(goal, planned_steps, executed_steps, result)
                )
        except Exception as e:
            logger.error(f"LLM-as-Judge 同步调用失败: {e}")
            return JudgeResult(reasoning=f"同步调用失败: {str(e)}")
