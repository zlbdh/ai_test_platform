# -*- coding: utf-8 -*-
"""
Agent 评估指标 — 量化评估每个 Agent 的决策质量和可靠性

指标分类：
- 规划质量: PlanCompletenessMetric
- 执行忠实度: ExecutionFidelityMetric
- 自愈成功率: HealingSuccessRateMetric
- 幻觉检测: HallucinationDetector
- Token 效率: TokenEfficiencyMetric
- 一致性: ConsistencyScoreMetric
- 步骤准确率: StepAccuracyMetric
- 目标完成率: GoalAchievementMetric
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


# ── 数据结构 ──────────────────────────────────────────────────────────────────

@dataclass
class MetricResult:
    """单个指标评估结果"""
    metric_name: str
    score: float           # 0.0 - 1.0 归一化分数
    raw_value: Any         # 原始值
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
    """评估上下文 — 包含评估所需的全部数据"""
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


# ── 基类 ──────────────────────────────────────────────────────────────────────

class BaseMetric(ABC):
    """评估指标基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """指标名称"""
        ...

    @property
    def description(self) -> str:
        return ""

    @abstractmethod
    def evaluate(self, ctx: EvaluationContext) -> MetricResult:
        """执行评估"""
        ...


# ── 具体指标实现 ──────────────────────────────────────────────────────────────

class PlanCompletenessMetric(BaseMetric):
    """
    规划完备性 — 评估 Agent 规划的步骤是否覆盖了目标的各方面。

    评估维度：
    - 步骤数是否合理（非空且不冗余）
    - 每步是否有明确的 action 和 target
    - 步骤间是否有逻辑顺序
    """

    @property
    def name(self) -> str:
        return "plan_completeness"

    @property
    def description(self) -> str:
        return "评估 Agent 规划步骤的完备性和逻辑性"

    def evaluate(self, ctx: EvaluationContext) -> MetricResult:
        steps = ctx.planned_steps
        if not steps:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                raw_value={"step_count": 0},
                details={"reason": "无规划步骤"},
            )

        # 检查每步是否有效
        valid_steps = 0
        issues = []
        for i, step in enumerate(steps):
            has_action = bool(step.get("action") or step.get("type") or step.get("instruction"))
            has_target = bool(step.get("target") or step.get("selector") or step.get("url"))
            if has_action:
                valid_steps += 1
            else:
                issues.append(f"步骤 {i+1} 缺少明确操作")

        validity_score = valid_steps / len(steps) if steps else 0

        # 步骤数量合理性（3-20步为正常范围）
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
    执行忠实度 — 计划 vs 实际执行的偏差。

    关注：
    - 实际执行的步骤是否与计划一致
    - 跳过或额外增加的步骤比例
    - 执行顺序偏差
    """

    @property
    def name(self) -> str:
        return "execution_fidelity"

    @property
    def description(self) -> str:
        return "计划步骤与实际执行之间的偏差率"

    def evaluate(self, ctx: EvaluationContext) -> MetricResult:
        planned = ctx.planned_steps
        executed = ctx.executed_steps

        if not planned:
            return MetricResult(
                metric_name=self.name,
                score=0.5,
                raw_value={"planned": 0, "executed": len(executed)},
                details={"reason": "无计划步骤，无法评估忠实度"},
            )

        if not executed:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                raw_value={"planned": len(planned), "executed": 0},
                details={"reason": "无执行步骤"},
            )

        # 计算匹配率
        planned_count = len(planned)
        executed_count = len(executed)

        # 匹配度：执行数/计划数的比例偏差
        ratio = min(executed_count, planned_count) / max(executed_count, planned_count)

        # 额外步骤惩罚（自愈/重试不惩罚）
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
    自愈成功率 — 各交互层级的触发频率和成功率。
    """

    @property
    def name(self) -> str:
        return "healing_success_rate"

    @property
    def description(self) -> str:
        return "自愈机制在各层级的触发频率和修复成功率"

    def evaluate(self, ctx: EvaluationContext) -> MetricResult:
        events = ctx.healing_events
        if not events:
            return MetricResult(
                metric_name=self.name,
                score=1.0,  # 无需自愈 = 完美
                raw_value={"total_events": 0},
                details={"reason": "无自愈事件"},
            )

        total = len(events)
        successes = sum(1 for e in events if e.get("success", False))
        success_rate = successes / total if total > 0 else 0

        # 按层级统计
        tier_stats = {}
        for e in events:
            tier = str(e.get("tier", "unknown"))
            if tier not in tier_stats:
                tier_stats[tier] = {"total": 0, "success": 0}
            tier_stats[tier]["total"] += 1
            if e.get("success", False):
                tier_stats[tier]["success"] += 1

        # 自愈频率：频繁自愈降低分数
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
    幻觉检测 — 检测 Agent 是否「编造」了实际不存在的操作结果。

    通过截图和 DOM 交叉验证：
    - Agent 声称点击了某按钮，但 DOM 中无此元素
    - Agent 声称页面显示了某文本，但截图中不存在
    """

    @property
    def name(self) -> str:
        return "hallucination_score"

    @property
    def description(self) -> str:
        return "Agent 幻觉行为检测分数（越高越好，即越少幻觉）"

    def evaluate(self, ctx: EvaluationContext) -> MetricResult:
        executed = ctx.executed_steps
        if not executed:
            return MetricResult(
                metric_name=self.name,
                score=1.0,
                raw_value={"checked_steps": 0},
                details={"reason": "无执行步骤"},
            )

        total_checks = 0
        hallucinations = 0
        hallucination_details = []

        for i, step in enumerate(executed):
            # 检查操作声明是否有实际结果佐证
            claimed_result = step.get("result", {})
            actual_success = step.get("success", None)

            if actual_success is not None:
                total_checks += 1
                # Agent 声称成功但实际失败
                if claimed_result.get("success") and not actual_success:
                    hallucinations += 1
                    hallucination_details.append({
                        "step": i + 1,
                        "type": "false_success_claim",
                        "claimed": claimed_result,
                    })

            # 检查 Agent 是否引用了不存在的选择器
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
            score = 0.8  # 无法验证时给予中等分数
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
    Token 效率 — 评估 Token 消耗、响应时间、重试次数是否合理。
    """

    @property
    def name(self) -> str:
        return "token_efficiency"

    @property
    def description(self) -> str:
        return "LLM Token 消耗和响应时间的效率评估"

    def evaluate(self, ctx: EvaluationContext) -> MetricResult:
        spans = ctx.trace_spans
        if not spans:
            return MetricResult(
                metric_name=self.name,
                score=0.5,
                raw_value={"total_spans": 0},
                details={"reason": "无 trace span 数据"},
            )

        total_tokens = sum(s.get("total_tokens", 0) for s in spans)
        total_duration = sum(s.get("duration_ms", 0) for s in spans)
        total_cost = sum(s.get("cost_usd", 0) for s in spans)
        avg_duration = total_duration / len(spans) if spans else 0

        # Token 效率评分
        # 基准：每步约 500 token、3000ms 响应为合理
        steps = len(ctx.executed_steps) or 1
        tokens_per_step = total_tokens / steps

        if tokens_per_step < 300:
            token_score = 1.0
        elif tokens_per_step < 800:
            token_score = 1.0 - (tokens_per_step - 300) / 1000
        else:
            token_score = max(0.2, 1.0 - (tokens_per_step - 300) / 2000)

        # 延迟评分
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
    一致性评分 — 相同任务多次执行的结果一致性。

    需要历史数据参与对比。
    """

    @property
    def name(self) -> str:
        return "consistency_score"

    @property
    def description(self) -> str:
        return "相同任务多次执行的结果一致性"

    def evaluate(self, ctx: EvaluationContext) -> MetricResult:
        # 从 SQLite 查询相同 goal 的历史执行
        history = self._get_history(ctx.goal)

        if len(history) < 2:
            return MetricResult(
                metric_name=self.name,
                score=0.8,
                raw_value={"history_count": len(history)},
                details={"reason": "历史数据不足，至少需要2次执行才能计算一致性"},
            )

        # 比较结果一致性
        results = [h.get("success", False) for h in history]
        success_rate = sum(results) / len(results)

        # 步骤数一致性
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
        """从评估数据库获取历史记录"""
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
    单步操作准确率 — 每一步操作在首次尝试中成功的概率。
    """

    @property
    def name(self) -> str:
        return "step_accuracy"

    @property
    def description(self) -> str:
        return "首次尝试成功的操作步骤占比"

    def evaluate(self, ctx: EvaluationContext) -> MetricResult:
        executed = ctx.executed_steps
        if not executed:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                raw_value={"total_steps": 0},
                details={"reason": "无执行步骤"},
            )

        first_attempt_success = 0
        total_actions = 0

        for step in executed:
            if step.get("is_healing") or step.get("is_retry"):
                continue  # 跳过自愈/重试步骤
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
    目标完成率 — 最终目标是否成功达成。
    """

    @property
    def name(self) -> str:
        return "goal_achievement"

    @property
    def description(self) -> str:
        return "最终测试目标是否成功达成"

    def evaluate(self, ctx: EvaluationContext) -> MetricResult:
        result = ctx.final_result
        if result is None:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                raw_value={"status": "no_result"},
                details={"reason": "无最终结果数据"},
            )

        # 从 final_result 判断
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


# ── 聚合评估 ──────────────────────────────────────────────────────────────────

# 所有可用指标
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
    运行所有（或指定的）评估指标。

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
            logger.warning(f"指标 {metric.name} 评估失败: {e}")
            results[metric.name] = MetricResult(
                metric_name=metric.name,
                score=0.0,
                raw_value={"error": str(e)},
                details={"evaluation_error": True},
            )

    return results


def compute_overall_score(results: Dict[str, MetricResult]) -> float:
    """计算加权综合分数"""
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
