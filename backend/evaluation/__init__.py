# -*- coding: utf-8 -*-
"""
Evaluation Module - Agent quality assessment

A framework for measuring each agent's decision quality and reliability:
- metrics: 14 evaluation metrics
- benchmark_suite: Standardized benchmark suite
- judge: LLM-as-Judge evaluator
- reporter: Evaluation report generator
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
