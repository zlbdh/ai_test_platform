# -*- coding: utf-8 -*-
"""
LLM-as-Judge — Use an LLM to evaluate another LLM's output quality

Supports multidimensional scores (0-10) and structured evaluation results.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import json
import logging
import time

logger = logging.getLogger(__name__)


@dataclass
class JudgeResult:
    """LLM-as-Judge evaluation result"""
    scores: Dict[str, float] = field(default_factory=dict)   # Dimension → score from 0 to 10
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
    Use an LLM to evaluate agent output quality.

    Evaluation dimensions:
    - completeness: whether the output covers the goal's requirements
    - accuracy: whether actions are precise and correct
    - efficiency: whether the steps are concise without unnecessary actions
    - robustness: whether edge cases are handled
    - clarity: whether output descriptions are clear
    """

    JUDGE_PROMPT = """You are an experienced QA reviewer. Evaluate the following AI testing agent's execution performance. Write your assessment in American English.

## Test goal
{goal}

## Planned steps
{planned_steps}

## Actual execution
{executed_steps}

## Execution result
{result}

## Evaluation dimensions (0-10 each)

Evaluate the following five dimensions and return JSON:

1. **completeness**: whether all aspects of the test goal were covered
2. **accuracy**: whether each action was precise and its result correct
3. **efficiency**: whether steps were concise and token consumption reasonable
4. **robustness**: whether exceptions and edge cases were handled properly
5. **clarity**: whether logs and feedback were clear and useful

Return exactly the following JSON format without Markdown fences:
{{
    "completeness": <0-10>,
    "accuracy": <0-10>,
    "efficiency": <0-10>,
    "robustness": <0-10>,
    "clarity": <0-10>,
    "reasoning": "<overall assessment in 2-3 sentences>",
    "suggestions": ["<improvement suggestion 1>", "<improvement suggestion 2>"]
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
        """Run an LLM-as-Judge evaluation"""
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
            logger.error(f"LLM-as-Judge evaluation failed: {e}")
            return JudgeResult(
                reasoning=f"Evaluation failed: {str(e)}",
            )

    async def _invoke_llm(self, llm, prompt: str) -> str:
        """Call the LLM"""
        try:
            # Try an asynchronous call
            result = await llm.ainvoke(prompt)
            return result.content if hasattr(result, "content") else str(result)
        except Exception:
            # Fall back to a synchronous call
            import asyncio
            result = await asyncio.to_thread(llm.invoke, prompt)
            return result.content if hasattr(result, "content") else str(result)

    def _parse_response(self, response: str) -> JudgeResult:
        """Parse the LLM response into a structured result"""
        try:
            # Remove any Markdown fences
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
            logger.warning(f"Failed to parse the LLM Judge response: {e}, raw: {response[:200]}")
            return JudgeResult(
                overall_score=5.0,
                reasoning=f"Response parsing failed; raw text: {response[:200]}",
            )

    def judge_sync(
        self,
        goal: str,
        planned_steps: list,
        executed_steps: list,
        result: dict,
    ) -> JudgeResult:
        """Synchronous LLM-as-Judge implementation"""
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
            logger.error(f"Synchronous LLM-as-Judge call failed: {e}")
            return JudgeResult(reasoning=f"Synchronous call failed: {str(e)}")
