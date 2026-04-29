# -*- coding: utf-8 -*-
"""
Evaluation Module - Agent 质量评估体系

提供量化评估每个 Agent 的决策质量和可靠性的框架：
- metrics: 14种评估指标
- benchmark_suite: 标准化基准测试套件
- judge: LLM-as-Judge 评估器
- reporter: 评估报告生成器
"""

from .metrics import (
    BaseMetric,
    PlanCompletenessMetric,
    ExecutionFidelityMetric,
    HealingSuccessRateMetric,
    HallucinationDetector,
    TokenEfficiencyMetric,
    ConsistencyScoreMetric,
    StepAccuracyMetric,
    GoalAchievementMetric,
    MetricResult,
    evaluate_all,
)
from .judge import LLMJudge
from .benchmark_suite import BenchmarkSuite, BenchmarkScenario
from .reporter import EvaluationReporter

__all__ = [
    "BaseMetric",
    "PlanCompletenessMetric",
    "ExecutionFidelityMetric",
    "HealingSuccessRateMetric",
    "HallucinationDetector",
    "TokenEfficiencyMetric",
    "ConsistencyScoreMetric",
    "StepAccuracyMetric",
    "GoalAchievementMetric",
    "MetricResult",
    "evaluate_all",
    "LLMJudge",
    "BenchmarkSuite",
    "BenchmarkScenario",
    "EvaluationReporter",
]
