# -*- coding: utf-8 -*-
"""
AutoAcceptanceEngine — automated risk acceptance engine
Use Bayesian confidence assessment to decide whether test changes can be merged safely.

Core approach:
    risk_score = P(failure given change) = f(change impact, test coverage, historical stability)
    If risk_score < threshold => automatic acceptance
    Otherwise => human review
"""
import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# ── Data structures ──────────────────────────────────────────────

class RiskLevel(str, Enum):
    LOW = "low"           # Automatic acceptance
    MEDIUM = "medium"     # Human confirmation required
    HIGH = "high"         # Mandatory human review
    CRITICAL = "critical" # Automatic acceptance prohibited


@dataclass
class ChangeImpact:
    """Change impact analysis results"""
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
    """Test confidence score"""
    coverage_pct: float = 0.0            # Coverage percentage
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    historical_stability: float = 1.0    # Historical stability, 0-1
    flaky_test_count: int = 0
    confidence_score: float = 0.0        # Overall confidence, 0-1


@dataclass
class AcceptanceDecision:
    """Acceptance decision"""
    risk_level: RiskLevel
    risk_score: float          # 0-1 (higher means greater risk)
    confidence_score: float    # 0-1 (higher means greater confidence)
    auto_accept: bool
    reasons: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


# ── Core engine ──────────────────────────────────────────────

class AutoAcceptanceEngine:
    """
    Automated risk acceptance engine

    Workflow:
        1. analyze_change_impact() → ChangeImpact
        2. evaluate_test_confidence() → TestConfidence
        3. make_decision(impact, confidence) → AcceptanceDecision
    """

    # Configurable parameters
    RISK_THRESHOLD = 0.3       # risk_score below this value permits automatic acceptance
    CONFIDENCE_MIN = 0.7       # confidence_score must be at least this value for automatic acceptance
    
    # Weights
    W_IMPACT = 0.4
    W_COVERAGE = 0.3
    W_STABILITY = 0.3

    def __init__(self):
        self._decision_history: List[AcceptanceDecision] = []

    # ── 1. Change impact analysis ──────────────────────────────────

    def analyze_change_impact(self, diff_text: str = "", files: List[str] = None) -> ChangeImpact:
        """
        Analyze the impact of code changes

        Args:
            diff_text: Git diff text (optional, for detailed analysis)
            files: Changed file list
        """
        files = files or []
        impact = ChangeImpact(files_changed=files)

        if diff_text:
            for line in diff_text.split("\n"):
                if line.startswith("+") and not line.startswith("+++"):
                    impact.lines_added += 1
                elif line.startswith("-") and not line.startswith("---"):
                    impact.lines_deleted += 1

        # Module analysis
        modules = set()
        high_risk_patterns = {
            "schema": ["migration", "schema", "models.py", "alembic"],
            "config": [".env", "config.py", "settings"],
            "api":    ["routers/", "main.py", "endpoints"],
        }
        
        for f in files:
            f_lower = f.lower()
            # Extract module names
            parts = f.replace("\\", "/").split("/")
            if len(parts) > 1:
                modules.add(parts[0])
            
            # High-risk detection
            for risk_type, patterns in high_risk_patterns.items():
                if any(p in f_lower for p in patterns):
                    if risk_type == "schema":
                        impact.has_schema_change = True
                    elif risk_type == "config":
                        impact.has_config_change = True
                    elif risk_type == "api":
                        impact.has_api_change = True

        impact.modules_affected = list(modules)

        # Calculate impact score (0-1)
        change_size = impact.lines_added + impact.lines_deleted
        size_score = min(change_size / 500, 1.0)  # Maximum score at 500 or more lines
        module_score = min(len(modules) / 5, 1.0)  # Maximum score at 5 or more modules
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

    # ── 2. Test confidence assessment ──────────────────────────────

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
        Assess confidence in the test results

        Args:
            tests_passed: Number of passed tests
            tests_failed: Number of failed tests
            tests_skipped: Number of skipped tests
            coverage_pct: Code coverage percentage
            flaky_count: Number of flaky tests
            historical_pass_rate: Historical pass rate (0-1)
        """
        total = tests_passed + tests_failed + tests_skipped
        pass_rate = tests_passed / max(total, 1)
        
        # Confidence = pass rate * coverage weight * stability - flaky penalty
        coverage_factor = min(coverage_pct / 100, 1.0)
        flaky_penalty = min(flaky_count * 0.05, 0.3)  # Deduct 5% for each flaky test, up to 30%

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

    # ── 3. Decision ──────────────────────────────────────────

    def make_decision(
        self,
        impact: ChangeImpact,
        confidence: TestConfidence,
    ) -> AcceptanceDecision:
        """
        Decide acceptance based on change impact and test confidence

        risk_score = impact_score * W_IMPACT 
                   + (1 - confidence_score) * W_CONFIDENCE
        """
        reasons = []

        # Calculate the risk score
        risk_score = (
            impact.impact_score * self.W_IMPACT
            + (1 - confidence.confidence_score) * (self.W_COVERAGE + self.W_STABILITY)
        )
        risk_score = min(max(risk_score, 0.0), 1.0)

        # Hard veto conditions
        if confidence.tests_failed > 0:
            risk_score = max(risk_score, 0.8)
            reasons.append(f"{confidence.tests_failed} failed tests — mandatory human review")

        if impact.has_schema_change:
            risk_score = max(risk_score, 0.6)
            reasons.append("Database schema changes detected — increase the risk level")

        # Determine risk level
        if risk_score < 0.2:
            risk_level = RiskLevel.LOW
        elif risk_score < 0.4:
            risk_level = RiskLevel.MEDIUM
        elif risk_score < 0.7:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.CRITICAL

        # Determine automatic acceptance
        auto_accept = (
            risk_score < self.RISK_THRESHOLD
            and confidence.confidence_score >= self.CONFIDENCE_MIN
            and confidence.tests_failed == 0
        )

        if auto_accept:
            reasons.append(f"Risk score {risk_score:.2f} < threshold {self.RISK_THRESHOLD} ✅")
            reasons.append(f"Confidence {confidence.confidence_score:.2f} >= minimum {self.CONFIDENCE_MIN} ✅")
        else:
            if risk_score >= self.RISK_THRESHOLD:
                reasons.append(f"Risk score {risk_score:.2f} >= threshold {self.RISK_THRESHOLD}")
            if confidence.confidence_score < self.CONFIDENCE_MIN:
                reasons.append(f"Confidence {confidence.confidence_score:.2f} < minimum {self.CONFIDENCE_MIN}")

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

    # ── Convenience methods ──────────────────────────────────────────

    def evaluate(
        self,
        diff_text: str = "",
        files: List[str] = None,
        tests_passed: int = 0,
        tests_failed: int = 0,
        coverage_pct: float = 0.0,
    ) -> AcceptanceDecision:
        """
        End-to-end assessment: analyze changes → assess tests → make a decision
        """
        impact = self.analyze_change_impact(diff_text=diff_text, files=files)
        confidence = self.evaluate_test_confidence(
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            coverage_pct=coverage_pct,
        )
        return self.make_decision(impact, confidence)

    def get_history(self) -> List[AcceptanceDecision]:
        """Get decision history"""
        return self._decision_history.copy()


# ── Singleton ──
_engine: Optional[AutoAcceptanceEngine] = None


def get_acceptance_engine() -> AutoAcceptanceEngine:
    """Get the AutoAcceptanceEngine singleton"""
    global _engine
    if _engine is None:
        _engine = AutoAcceptanceEngine()
    return _engine
