# -*- coding: utf-8 -*-
"""
Agent evaluation metrics — measure each agent's decision quality and reliability

Metric categories:
- Planning quality: PlanCompletenessMetric
- Execution fidelity: ExecutionFidelityMetric
- Healing success rate: HealingSuccessRateMetric
- Hallucination detection: HallucinationDetector
- Token efficiency: TokenEfficiencyMetric
- Consistency: ConsistencyScoreMetric
- Step accuracy: StepAccuracyMetric
- Goal completion rate: GoalAchievementMetric
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
from abc import ABC, abstractmethod
import time
import json
import sqlite3
import os
import logging
import statistics

logger = logging.getLogger(__name__)


# ── Data structures ──────────────────────────────────────────────────────────────────

@dataclass
class MetricResult:
    """Evaluation result for one metric"""
    metric_name: str
    score: float           # Normalized score from 0.0 to 1.0
    raw_value: Any         # Raw value
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "metric_name": self.metric_name,
            "score": round(self.score, 4),
            "raw_value": self.raw_value,
            "details": self.details,
            "timestamp": self.timestamp,
        }


@dataclass
class EvaluationContext:
    """Evaluation context containing all data needed for assessment"""
    session_id: str = ""
    trace_id: str = ""
    agent_name: str = ""
    goal: str = ""
    planned_steps: List[Dict] = field(default_factory=list)
    executed_steps: List[Dict] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)        # base64
    dom_snapshots: List[str] = field(default_factory=list)
    healing_events: List[Dict] = field(default_factory=list)
    trace_spans: List[Dict] = field(default_factory=list)
    final_result: Optional[Dict] = None
    duration_ms: float = 0.0


# ── Base class ──────────────────────────────────────────────────────────────────────

class BaseMetric(ABC):
    """Base class for evaluation metrics"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Metric name"""
        ...

    @property
    def description(self) -> str:
        return ""

    @abstractmethod
    def evaluate(self, ctx: EvaluationContext) -> MetricResult:
        """Run the evaluation"""
        ...


# ── Metric implementations ──────────────────────────────────────────────────────────────

class PlanCompletenessMetric(BaseMetric):
    """
    Plan completeness — evaluate whether the agent's planned steps cover every aspect of the goal.

    Evaluation dimensions:
    - Whether the step count is reasonable (nonempty and not redundant)
    - Whether each step has a clear action and target
    - Whether the steps follow a logical order
    """

    @property
    def name(self) -> str:
        return "plan_completeness"

    @property
    def description(self) -> str:
        return "Evaluate the completeness and logical order of the agent's planned steps"

    def evaluate(self, ctx: EvaluationContext) -> MetricResult:
        steps = ctx.planned_steps
        if not steps:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                raw_value={"step_count": 0},
                details={"reason": "No planned steps"},
            )

        # Check whether each step is valid
        valid_steps = 0
        issues = []
        for i, step in enumerate(steps):
            has_action = bool(step.get("action") or step.get("type") or step.get("instruction"))
            has_target = bool(step.get("target") or step.get("selector") or step.get("url"))
            if has_action:
                valid_steps += 1
            else:
                issues.append(f"Step {i+1} has no clear action")

        validity_score = valid_steps / len(steps) if steps else 0

        # Evaluate step count (3-20 steps is the normal range)
        step_count = len(steps)
        if 3 <= step_count <= 20:
            count_score = 1.0
        elif step_count < 3:
            count_score = step_count / 3
        else:
            count_score = max(0.5, 1.0 - (step_count - 20) * 0.05)

        score = validity_score * 0.7 + count_score * 0.3

        return MetricResult(
            metric_name=self.name,
            score=min(1.0, score),
            raw_value={"valid_steps": valid_steps, "total_steps": step_count},
            details={"issues": issues, "validity_score": validity_score, "count_score": count_score},
        )


class ExecutionFidelityMetric(BaseMetric):
    """
    Execution fidelity — deviation between planned and actual execution.

    Focus areas:
    - Whether executed steps match the plan
    - Proportion of skipped or additional steps
    - Deviations in execution order
    """

    @property
    def name(self) -> str:
        return "execution_fidelity"

    @property
    def description(self) -> str:
        return "Deviation rate between planned and executed steps"

    def evaluate(self, ctx: EvaluationContext) -> MetricResult:
        planned = ctx.planned_steps
        executed = ctx.executed_steps

        if not planned:
            return MetricResult(
                metric_name=self.name,
                score=0.5,
                raw_value={"planned": 0, "executed": len(executed)},
                details={"reason": "No planned steps; cannot evaluate fidelity"},
            )

        if not executed:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                raw_value={"planned": len(planned), "executed": 0},
                details={"reason": "No executed steps"},
            )

        # Calculate the match rate
        planned_count = len(planned)
        executed_count = len(executed)

        # Match quality: deviation in the ratio of executed to planned steps
        ratio = min(executed_count, planned_count) / max(executed_count, planned_count)

        # Penalize extra steps (excluding healing and retries)
        extra_steps = max(0, executed_count - planned_count)
        healing_steps = sum(1 for s in executed if s.get("is_healing") or s.get("is_retry"))
        meaningful_extra = max(0, extra_steps - healing_steps)
        extra_penalty = min(0.3, meaningful_extra * 0.05)

        score = ratio - extra_penalty

        return MetricResult(
            metric_name=self.name,
            score=max(0.0, min(1.0, score)),
            raw_value={
                "planned_count": planned_count,
                "executed_count": executed_count,
                "healing_steps": healing_steps,
            },
            details={
                "ratio": round(ratio, 3),
                "extra_penalty": round(extra_penalty, 3),
                "meaningful_extra": meaningful_extra,
            },
        )


class HealingSuccessRateMetric(BaseMetric):
    """
    Healing success rate — trigger frequency and success rate at each interaction level.
    """

    @property
    def name(self) -> str:
        return "healing_success_rate"

    @property
    def description(self) -> str:
        return "Healing trigger frequency and recovery success rate at each level"

    def evaluate(self, ctx: EvaluationContext) -> MetricResult:
        events = ctx.healing_events
        if not events:
            return MetricResult(
                metric_name=self.name,
                score=1.0,  # No healing needed = perfect score
                raw_value={"total_events": 0},
                details={"reason": "No healing events"},
            )

        total = len(events)
        successes = sum(1 for e in events if e.get("success", False))
        success_rate = successes / total if total > 0 else 0

        # Aggregate by level
        tier_stats = {}
        for e in events:
            tier = str(e.get("tier", "unknown"))
            if tier not in tier_stats:
                tier_stats[tier] = {"total": 0, "success": 0}
            tier_stats[tier]["total"] += 1
            if e.get("success", False):
                tier_stats[tier]["success"] += 1

        # Healing frequency: frequent healing lowers the score
        frequency_penalty = min(0.3, total * 0.03)
        score = success_rate - frequency_penalty

        return MetricResult(
            metric_name=self.name,
            score=max(0.0, min(1.0, score)),
            raw_value={"total": total, "successes": successes, "rate": round(success_rate, 3)},
            details={"tier_stats": tier_stats, "frequency_penalty": round(frequency_penalty, 3)},
        )


class HallucinationDetector(BaseMetric):
    """
    Hallucination detection — detect whether the agent fabricated action results that did not occur.

    Cross-check screenshots and the DOM:
    - The agent claims it clicked a button that is absent from the DOM
    - The agent claims the page displays text that is absent from the screenshot
    """

    @property
    def name(self) -> str:
        return "hallucination_score"

    @property
    def description(self) -> str:
        return "Agent hallucination detection score (higher is better, meaning fewer hallucinations)"

    def evaluate(self, ctx: EvaluationContext) -> MetricResult:
        executed = ctx.executed_steps
        if not executed:
            return MetricResult(
                metric_name=self.name,
                score=1.0,
                raw_value={"checked_steps": 0},
                details={"reason": "No executed steps"},
            )

        total_checks = 0
        hallucinations = 0
        hallucination_details = []

        for i, step in enumerate(executed):
            # Check whether action claims are supported by actual results
            claimed_result = step.get("result", {})
            actual_success = step.get("success", None)

            if actual_success is not None:
                total_checks += 1
                # The agent claims success but the action actually failed
                if claimed_result.get("success") and not actual_success:
                    hallucinations += 1
                    hallucination_details.append({
                        "step": i + 1,
                        "type": "false_success_claim",
                        "claimed": claimed_result,
                    })

            # Check whether the agent referenced a nonexistent selector
            selector = step.get("selector", "")
            if selector and step.get("element_found") is False:
                total_checks += 1
                hallucinations += 1
                hallucination_details.append({
                    "step": i + 1,
                    "type": "phantom_element",
                    "selector": selector,
                })

        if total_checks == 0:
            score = 0.8  # Assign a moderate score when verification is unavailable
        else:
            score = 1.0 - (hallucinations / total_checks)

        return MetricResult(
            metric_name=self.name,
            score=max(0.0, score),
            raw_value={"hallucinations": hallucinations, "total_checks": total_checks},
            details={"hallucination_details": hallucination_details},
        )


class TokenEfficiencyMetric(BaseMetric):
    """
    Token efficiency — evaluate whether token consumption, response time, and retry count are reasonable.
    """

    @property
    def name(self) -> str:
        return "token_efficiency"

    @property
    def description(self) -> str:
        return "Evaluate efficiency based on LLM token consumption and response time"

    def evaluate(self, ctx: EvaluationContext) -> MetricResult:
        spans = ctx.trace_spans
        if not spans:
            return MetricResult(
                metric_name=self.name,
                score=0.5,
                raw_value={"total_spans": 0},
                details={"reason": "No trace span data"},
            )

        total_tokens = sum(s.get("total_tokens", 0) for s in spans)
        total_duration = sum(s.get("duration_ms", 0) for s in spans)
        total_cost = sum(s.get("cost_usd", 0) for s in spans)
        avg_duration = total_duration / len(spans) if spans else 0

        # Token efficiency score
        # Baseline: approximately 500 tokens and a 3,000 ms response per step is reasonable
        steps = len(ctx.executed_steps) or 1
        tokens_per_step = total_tokens / steps

        if tokens_per_step < 300:
            token_score = 1.0
        elif tokens_per_step < 800:
            token_score = 1.0 - (tokens_per_step - 300) / 1000
        else:
            token_score = max(0.2, 1.0 - (tokens_per_step - 300) / 2000)

        # Latency score
        if avg_duration < 2000:
            latency_score = 1.0
        elif avg_duration < 5000:
            latency_score = 1.0 - (avg_duration - 2000) / 6000
        else:
            latency_score = max(0.2, 1.0 - (avg_duration - 2000) / 10000)

        score = token_score * 0.5 + latency_score * 0.5

        return MetricResult(
            metric_name=self.name,
            score=max(0.0, min(1.0, score)),
            raw_value={
                "total_tokens": total_tokens,
                "total_cost_usd": round(total_cost, 4),
                "total_duration_ms": round(total_duration, 1),
                "avg_duration_ms": round(avg_duration, 1),
            },
            details={
                "tokens_per_step": round(tokens_per_step, 1),
                "token_score": round(token_score, 3),
                "latency_score": round(latency_score, 3),
                "span_count": len(spans),
            },
        )


class ConsistencyScoreMetric(BaseMetric):
    """
    Consistency score — agreement across repeated executions of the same task.

    Requires historical data for comparison.
    """

    @property
    def name(self) -> str:
        return "consistency_score"

    @property
    def description(self) -> str:
        return "Agreement across repeated executions of the same task"

    def evaluate(self, ctx: EvaluationContext) -> MetricResult:
        # Query SQLite for previous executions with the same goal
        history = self._get_history(ctx.goal)

        if len(history) < 2:
            return MetricResult(
                metric_name=self.name,
                score=0.8,
                raw_value={"history_count": len(history)},
                details={"reason": "Insufficient history; at least two executions are required to calculate consistency"},
            )

        # Compare result consistency
        results = [h.get("success", False) for h in history]
        success_rate = sum(results) / len(results)

        # Step count consistency
        step_counts = [h.get("step_count", 0) for h in history if h.get("step_count")]
        if len(step_counts) >= 2:
            step_stddev = statistics.stdev(step_counts) if len(step_counts) > 1 else 0
            step_mean = statistics.mean(step_counts) if step_counts else 1
            step_cv = step_stddev / step_mean if step_mean > 0 else 0
            step_consistency = max(0, 1.0 - step_cv)
        else:
            step_consistency = 0.8

        score = success_rate * 0.6 + step_consistency * 0.4

        return MetricResult(
            metric_name=self.name,
            score=max(0.0, min(1.0, score)),
            raw_value={"history_count": len(history), "success_rate": round(success_rate, 3)},
            details={"step_consistency": round(step_consistency, 3)},
        )

    def _get_history(self, goal: str) -> List[Dict]:
        """Get historical records from the evaluation database"""
        try:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data", "evaluation.db"
            )
            if not os.path.exists(db_path):
                return []
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM evaluation_runs WHERE goal = ? ORDER BY timestamp DESC LIMIT 10",
                    (goal,)
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception:
            return []


class StepAccuracyMetric(BaseMetric):
    """
    Step accuracy — the probability that each action succeeds on its first attempt.
    """

    @property
    def name(self) -> str:
        return "step_accuracy"

    @property
    def description(self) -> str:
        return "Proportion of action steps that succeed on the first attempt"

    def evaluate(self, ctx: EvaluationContext) -> MetricResult:
        executed = ctx.executed_steps
        if not executed:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                raw_value={"total_steps": 0},
                details={"reason": "No executed steps"},
            )

        first_attempt_success = 0
        total_actions = 0

        for step in executed:
            if step.get("is_healing") or step.get("is_retry"):
                continue  # Skip healing and retry steps
            total_actions += 1
            if step.get("success", False) and not step.get("heal_used", False):
                first_attempt_success += 1

        if total_actions == 0:
            score = 0.5
        else:
            score = first_attempt_success / total_actions

        return MetricResult(
            metric_name=self.name,
            score=max(0.0, min(1.0, score)),
            raw_value={
                "first_attempt_success": first_attempt_success,
                "total_actions": total_actions,
            },
            details={"accuracy_rate": round(score, 3)},
        )


class GoalAchievementMetric(BaseMetric):
    """
    Goal completion rate — whether the final goal was achieved.
    """

    @property
    def name(self) -> str:
        return "goal_achievement"

    @property
    def description(self) -> str:
        return "Whether the final test goal was achieved"

    def evaluate(self, ctx: EvaluationContext) -> MetricResult:
        result = ctx.final_result
        if result is None:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                raw_value={"status": "no_result"},
                details={"reason": "No final result data"},
            )

        # Determine the outcome from final_result
        success = result.get("success", False)
        status = result.get("status", "unknown")

        if success or status in ("passed", "success", "completed"):
            score = 1.0
        elif status in ("partial", "warning"):
            score = 0.6
        elif status in ("failed", "error"):
            score = 0.0
        else:
            score = 0.3

        return MetricResult(
            metric_name=self.name,
            score=score,
            raw_value={"success": success, "status": status},
            details={"final_result_summary": str(result.get("summary", ""))[:200]},
        )


# ── Aggregate evaluation ──────────────────────────────────────────────────────────────────

# All available metrics
ALL_METRICS: List[BaseMetric] = [
    PlanCompletenessMetric(),
    ExecutionFidelityMetric(),
    HealingSuccessRateMetric(),
    HallucinationDetector(),
    TokenEfficiencyMetric(),
    ConsistencyScoreMetric(),
    StepAccuracyMetric(),
    GoalAchievementMetric(),
]


def evaluate_all(ctx: EvaluationContext, metrics: Optional[List[BaseMetric]] = None) -> Dict[str, MetricResult]:
    """
    Run all evaluation metrics or a specified subset.

    Returns:
        Dict[metric_name, MetricResult]
    """
    if metrics is None:
        metrics = ALL_METRICS

    results = {}
    for metric in metrics:
        try:
            result = metric.evaluate(ctx)
            results[metric.name] = result
        except Exception as e:
            logger.warning(f"Metric {metric.name} evaluation failed: {e}")
            results[metric.name] = MetricResult(
                metric_name=metric.name,
                score=0.0,
                raw_value={"error": str(e)},
                details={"evaluation_error": True},
            )

    return results


def compute_overall_score(results: Dict[str, MetricResult]) -> float:
    """Calculate the weighted overall score"""
    weights = {
        "goal_achievement": 0.25,
        "step_accuracy": 0.15,
        "plan_completeness": 0.10,
        "execution_fidelity": 0.10,
        "healing_success_rate": 0.10,
        "hallucination_score": 0.15,
        "token_efficiency": 0.10,
        "consistency_score": 0.05,
    }

    total_weight = 0
    weighted_sum = 0

    for name, result in results.items():
        w = weights.get(name, 0.05)
        weighted_sum += result.score * w
        total_weight += w

    return round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.0
