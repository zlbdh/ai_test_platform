# -*- coding: utf-8 -*-
"""
AutoAcceptanceEngine — 风险自动验收引擎
基于贝叶斯置信度评估，自动决定测试变更是否可安全合并。

核心思路:
    risk_score = P(故障 | 变更) = f(变更影响范围, 测试覆盖, 历史稳定性)
    若 risk_score < 阈值 => 自动验收
    否则 => 人工审核
"""
import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# ── 数据结构 ──────────────────────────────────────────────

class RiskLevel(str, Enum):
    LOW = "low"           # 自动验收
    MEDIUM = "medium"     # 需人工确认
    HIGH = "high"         # 强制人工审核
    CRITICAL = "critical" # 禁止自动验收


@dataclass
class ChangeImpact:
    """变更影响分析结果"""
    files_changed: List[str] = field(default_factory=list)
    lines_added: int = 0
    lines_deleted: int = 0
    modules_affected: List[str] = field(default_factory=list)
    has_schema_change: bool = False
    has_config_change: bool = False
    has_api_change: bool = False
    impact_score: float = 0.0  # 0-1


@dataclass
class TestConfidence:
    """测试置信度评分"""
    coverage_pct: float = 0.0            # 覆盖率百分比
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    historical_stability: float = 1.0    # 历史稳定性 0-1
    flaky_test_count: int = 0
    confidence_score: float = 0.0        # 综合置信度 0-1


@dataclass
class AcceptanceDecision:
    """验收决策结果"""
    risk_level: RiskLevel
    risk_score: float          # 0-1 (越高越危险)
    confidence_score: float    # 0-1 (越高越可信)
    auto_accept: bool
    reasons: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


# ── 核心引擎 ──────────────────────────────────────────────

class AutoAcceptanceEngine:
    """
    风险自动验收引擎

    流程:
        1. analyze_change_impact() → ChangeImpact
        2. evaluate_test_confidence() → TestConfidence
        3. make_decision(impact, confidence) → AcceptanceDecision
    """

    # 可配置参数
    RISK_THRESHOLD = 0.3       # risk_score < 此值 → 自动验收
    CONFIDENCE_MIN = 0.7       # confidence_score 需 >= 此值才能自动验收
    
    # 权重
    W_IMPACT = 0.4
    W_COVERAGE = 0.3
    W_STABILITY = 0.3

    def __init__(self):
        self._decision_history: List[AcceptanceDecision] = []

    # ── 1. 变更影响分析 ──────────────────────────────────

    def analyze_change_impact(self, diff_text: str = "", files: List[str] = None) -> ChangeImpact:
        """
        分析代码变更的影响范围

        Args:
            diff_text: Git diff 文本（可选，用于精细分析）
            files: 变更文件列表
        """
        files = files or []
        impact = ChangeImpact(files_changed=files)

        if diff_text:
            for line in diff_text.split("\n"):
                if line.startswith("+") and not line.startswith("+++"):
                    impact.lines_added += 1
                elif line.startswith("-") and not line.startswith("---"):
                    impact.lines_deleted += 1

        # 模块分析
        modules = set()
        high_risk_patterns = {
            "schema": ["migration", "schema", "models.py", "alembic"],
            "config": [".env", "config.py", "settings"],
            "api":    ["routers/", "main.py", "endpoints"],
        }
        
        for f in files:
            f_lower = f.lower()
            # 提取模块名
            parts = f.replace("\\", "/").split("/")
            if len(parts) > 1:
                modules.add(parts[0])
            
            # 高风险检测
            for risk_type, patterns in high_risk_patterns.items():
                if any(p in f_lower for p in patterns):
                    if risk_type == "schema":
                        impact.has_schema_change = True
                    elif risk_type == "config":
                        impact.has_config_change = True
                    elif risk_type == "api":
                        impact.has_api_change = True

        impact.modules_affected = list(modules)

        # 计算影响分数 (0-1)
        change_size = impact.lines_added + impact.lines_deleted
        size_score = min(change_size / 500, 1.0)  # 500行以上满分
        module_score = min(len(modules) / 5, 1.0)  # 5模块以上满分
        risk_bonus = sum([
            0.2 if impact.has_schema_change else 0,
            0.1 if impact.has_config_change else 0,
            0.15 if impact.has_api_change else 0,
        ])

        impact.impact_score = min(size_score * 0.4 + module_score * 0.3 + risk_bonus, 1.0)
        
        logger.info(
            f"Change Impact: {len(files)} files, +{impact.lines_added}/-{impact.lines_deleted}, "
            f"modules={impact.modules_affected}, score={impact.impact_score:.2f}"
        )
        return impact

    # ── 2. 测试置信度评估 ──────────────────────────────

    def evaluate_test_confidence(
        self,
        tests_passed: int = 0,
        tests_failed: int = 0,
        tests_skipped: int = 0,
        coverage_pct: float = 0.0,
        flaky_count: int = 0,
        historical_pass_rate: float = 1.0,
    ) -> TestConfidence:
        """
        评估测试结果的置信度

        Args:
            tests_passed: 通过的测试数
            tests_failed: 失败的测试数
            tests_skipped: 跳过的测试数
            coverage_pct: 代码覆盖率百分比
            flaky_count: 不稳定测试数量
            historical_pass_rate: 历史通过率 (0-1)
        """
        total = tests_passed + tests_failed + tests_skipped
        pass_rate = tests_passed / max(total, 1)
        
        # 置信度 = 通过率 * 覆盖率权重 * 稳定性 - flaky 惩罚
        coverage_factor = min(coverage_pct / 100, 1.0)
        flaky_penalty = min(flaky_count * 0.05, 0.3)  # 每个 flaky 扣 5%，最多扣 30%

        confidence = (
            pass_rate * 0.5
            + coverage_factor * 0.25
            + historical_pass_rate * 0.25
            - flaky_penalty
        )
        confidence = max(0.0, min(confidence, 1.0))

        result = TestConfidence(
            coverage_pct=coverage_pct,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            tests_skipped=tests_skipped,
            historical_stability=historical_pass_rate,
            flaky_test_count=flaky_count,
            confidence_score=confidence,
        )

        logger.info(
            f"Test Confidence: {tests_passed}/{total} passed, "
            f"coverage={coverage_pct:.0f}%, confidence={confidence:.2f}"
        )
        return result

    # ── 3. 决策 ──────────────────────────────────────────

    def make_decision(
        self,
        impact: ChangeImpact,
        confidence: TestConfidence,
    ) -> AcceptanceDecision:
        """
        基于变更影响和测试置信度做出验收决策

        risk_score = impact_score * W_IMPACT 
                   + (1 - confidence_score) * W_CONFIDENCE
        """
        reasons = []

        # 计算风险分数
        risk_score = (
            impact.impact_score * self.W_IMPACT
            + (1 - confidence.confidence_score) * (self.W_COVERAGE + self.W_STABILITY)
        )
        risk_score = min(max(risk_score, 0.0), 1.0)

        # 硬性否决条件
        if confidence.tests_failed > 0:
            risk_score = max(risk_score, 0.8)
            reasons.append(f"{confidence.tests_failed} 个测试失败 — 强制人工审核")

        if impact.has_schema_change:
            risk_score = max(risk_score, 0.6)
            reasons.append("包含数据库 schema 变更 — 提升风险等级")

        # 确定风险等级
        if risk_score < 0.2:
            risk_level = RiskLevel.LOW
        elif risk_score < 0.4:
            risk_level = RiskLevel.MEDIUM
        elif risk_score < 0.7:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.CRITICAL

        # 自动验收判断
        auto_accept = (
            risk_score < self.RISK_THRESHOLD
            and confidence.confidence_score >= self.CONFIDENCE_MIN
            and confidence.tests_failed == 0
        )

        if auto_accept:
            reasons.append(f"风险评分 {risk_score:.2f} < 阈值 {self.RISK_THRESHOLD} ✅")
            reasons.append(f"置信度 {confidence.confidence_score:.2f} >= 最低要求 {self.CONFIDENCE_MIN} ✅")
        else:
            if risk_score >= self.RISK_THRESHOLD:
                reasons.append(f"风险评分 {risk_score:.2f} >= 阈值 {self.RISK_THRESHOLD}")
            if confidence.confidence_score < self.CONFIDENCE_MIN:
                reasons.append(f"置信度 {confidence.confidence_score:.2f} < 最低要求 {self.CONFIDENCE_MIN}")

        decision = AcceptanceDecision(
            risk_level=risk_level,
            risk_score=risk_score,
            confidence_score=confidence.confidence_score,
            auto_accept=auto_accept,
            reasons=reasons,
        )

        self._decision_history.append(decision)
        
        logger.info(
            f"Acceptance Decision: risk={risk_score:.2f} ({risk_level.value}), "
            f"auto_accept={auto_accept}, reasons={reasons}"
        )
        return decision

    # ── 便捷方法 ──────────────────────────────────────────

    def evaluate(
        self,
        diff_text: str = "",
        files: List[str] = None,
        tests_passed: int = 0,
        tests_failed: int = 0,
        coverage_pct: float = 0.0,
    ) -> AcceptanceDecision:
        """
        一站式评估：分析变更 → 评估测试 → 做出决策
        """
        impact = self.analyze_change_impact(diff_text=diff_text, files=files)
        confidence = self.evaluate_test_confidence(
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            coverage_pct=coverage_pct,
        )
        return self.make_decision(impact, confidence)

    def get_history(self) -> List[AcceptanceDecision]:
        """获取决策历史"""
        return self._decision_history.copy()


# ── 单例 ──
_engine: Optional[AutoAcceptanceEngine] = None


def get_acceptance_engine() -> AutoAcceptanceEngine:
    """获取 AutoAcceptanceEngine 单例"""
    global _engine
    if _engine is None:
        _engine = AutoAcceptanceEngine()
    return _engine
