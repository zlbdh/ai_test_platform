# -*- coding: utf-8 -*-
"""
Quality Gate — Quality gate engine

Provide structured quality decisions in CI/CD pipelines:
- Coverage threshold checks
- Agent evaluation score gates
- Custom rule engine
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import json
import time
import os
import sqlite3
import logging

logger = logging.getLogger(__name__)


class GateStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    PENDING = "pending"


@dataclass
class GateRule:
    """Quality gate rule"""
    name: str
    description: str = ""
    metric: str = ""           # Corresponding metric name
    operator: str = ">="      # >=, <=, ==, !=
    threshold: float = 0.0
    severity: str = "blocking"  # blocking, warning, info
    enabled: bool = True

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "metric": self.metric,
            "operator": self.operator,
            "threshold": self.threshold,
            "severity": self.severity,
            "enabled": self.enabled,
        }


@dataclass
class GateCheckResult:
    """Result of checking one rule"""
    rule_name: str
    status: GateStatus = GateStatus.PENDING
    actual_value: float = 0.0
    threshold: float = 0.0
    message: str = ""

    def to_dict(self) -> Dict:
        return {
            "rule_name": self.rule_name,
            "status": self.status.value,
            "actual_value": round(self.actual_value, 4),
            "threshold": self.threshold,
            "message": self.message,
        }


@dataclass
class GateVerdict:
    """Overall quality gate decision"""
    status: GateStatus = GateStatus.PENDING
    checks: List[GateCheckResult] = field(default_factory=list)
    summary: str = ""
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "status": self.status.value,
            "checks": [c.to_dict() for c in self.checks],
            "summary": self.summary,
            "passed": self.status == GateStatus.PASSED,
            "timestamp": self.timestamp,
            "total_checks": len(self.checks),
            "passed_checks": sum(1 for c in self.checks if c.status == GateStatus.PASSED),
            "failed_checks": sum(1 for c in self.checks if c.status == GateStatus.FAILED),
        }


# ── Default rules ──────────────────────────────────────────────────────────────────

DEFAULT_RULES: List[GateRule] = [
    GateRule(
        name="goal_achievement_gate",
        description="Test goal achievement must be >= 80%",
        metric="goal_achievement",
        operator=">=",
        threshold=0.8,
        severity="blocking",
    ),
    GateRule(
        name="step_accuracy_gate",
        description="First-attempt step success rate >= 70%",
        metric="step_accuracy",
        operator=">=",
        threshold=0.7,
        severity="blocking",
    ),
    GateRule(
        name="hallucination_gate",
        description="Hallucination score (higher is better) >= 0.8",
        metric="hallucination_score",
        operator=">=",
        threshold=0.8,
        severity="blocking",
    ),
    GateRule(
        name="healing_rate_warning",
        description="Healing success rate >= 0.6 (warning)",
        metric="healing_success_rate",
        operator=">=",
        threshold=0.6,
        severity="warning",
    ),
    GateRule(
        name="token_efficiency_info",
        description="Token efficiency >= 0.5 (informational)",
        metric="token_efficiency",
        operator=">=",
        threshold=0.5,
        severity="info",
    ),
]


class QualityGateEngine:
    """Quality gate engine"""

    def __init__(self):
        self._rules = list(DEFAULT_RULES)
        self._db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "quality_gate.db",
        )
        self._init_db()
        self._load_custom_rules()

    def _init_db(self):
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gate_rules (
                    name TEXT PRIMARY KEY,
                    data TEXT,
                    created_at REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gate_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    status TEXT,
                    verdict TEXT,
                    timestamp REAL
                )
            """)

    def _load_custom_rules(self):
        """Load custom rules from the database"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute("SELECT data FROM gate_rules").fetchall()
                for row in rows:
                    data = json.loads(row[0])
                    rule = GateRule(**data)
                    # Replace the default rule with the same name
                    self._rules = [r for r in self._rules if r.name != rule.name]
                    self._rules.append(rule)
        except Exception:
            pass

    def check(self, metric_scores: Dict[str, float], run_id: str = "") -> GateVerdict:
        """Run quality gate checks"""
        start = time.time()
        checks = []
        has_blocking_fail = False
        has_warning = False

        for rule in self._rules:
            if not rule.enabled:
                continue

            actual = metric_scores.get(rule.metric, -1)
            if actual < 0:
                checks.append(GateCheckResult(
                    rule_name=rule.name,
                    status=GateStatus.PENDING,
                    message=f"Data for metric {rule.metric} is unavailable",
                ))
                continue

            passed = self._evaluate_rule(actual, rule.operator, rule.threshold)

            if passed:
                status = GateStatus.PASSED
                msg = f"{rule.metric} = {actual:.3f} {rule.operator} {rule.threshold} ✅"
            else:
                if rule.severity == "blocking":
                    status = GateStatus.FAILED
                    has_blocking_fail = True
                    msg = f"{rule.metric} = {actual:.3f} does not meet {rule.operator} {rule.threshold} ❌"
                elif rule.severity == "warning":
                    status = GateStatus.WARNING
                    has_warning = True
                    msg = f"{rule.metric} = {actual:.3f} is below the expected {rule.threshold} ⚠️"
                else:
                    status = GateStatus.WARNING
                    msg = f"{rule.metric} = {actual:.3f} (informational) ℹ️"

            checks.append(GateCheckResult(
                rule_name=rule.name,
                status=status,
                actual_value=actual,
                threshold=rule.threshold,
                message=msg,
            ))

        # Overall decision
        if has_blocking_fail:
            overall = GateStatus.FAILED
            summary = "❌ Quality gate failed: blocking rules did not pass"
        elif has_warning:
            overall = GateStatus.WARNING
            summary = "⚠️ Quality gate passed with warnings"
        else:
            overall = GateStatus.PASSED
            summary = "✅ All quality gates passed"

        verdict = GateVerdict(
            status=overall,
            checks=checks,
            summary=summary,
            duration_ms=(time.time() - start) * 1000,
        )

        # Persist
        self._save_history(run_id, verdict)

        return verdict

    def add_rule(self, rule: GateRule):
        """Add or update a custom rule"""
        self._rules = [r for r in self._rules if r.name != rule.name]
        self._rules.append(rule)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO gate_rules (name, data, created_at) VALUES (?, ?, ?)",
                (rule.name, json.dumps(rule.to_dict()), time.time()),
            )

    def list_rules(self) -> List[Dict]:
        return [r.to_dict() for r in self._rules if r.enabled]

    def get_history(self, limit: int = 20, run_id: str = "", status: str = "") -> List[Dict]:
        try:
            with sqlite3.connect(self._db_path) as conn:
                sql = "SELECT run_id, status, verdict, timestamp FROM gate_history"
                where_clauses = []
                params: List[Any] = []
                if run_id:
                    where_clauses.append("run_id = ?")
                    params.append(run_id)
                if status:
                    where_clauses.append("status = ?")
                    params.append(status)
                if where_clauses:
                    sql += " WHERE " + " AND ".join(where_clauses)
                sql += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                rows = conn.execute(sql, tuple(params)).fetchall()
                return [{"run_id": r[0], "status": r[1], "verdict": json.loads(r[2]), "timestamp": r[3]} for r in rows]
        except Exception:
            return []

    def _save_history(self, run_id: str, verdict: GateVerdict):
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "INSERT INTO gate_history (run_id, status, verdict, timestamp) VALUES (?, ?, ?, ?)",
                    (run_id, verdict.status.value, json.dumps(verdict.to_dict()), time.time()),
                )
        except Exception as e:
            logger.warning(f"Failed to save quality gate history: {e}")

    @staticmethod
    def _evaluate_rule(actual: float, operator: str, threshold: float) -> bool:
        if operator == ">=":
            return actual >= threshold
        elif operator == "<=":
            return actual <= threshold
        elif operator == "==":
            return abs(actual - threshold) < 0.001
        elif operator == "!=":
            return abs(actual - threshold) >= 0.001
        elif operator == ">":
            return actual > threshold
        elif operator == "<":
            return actual < threshold
        return False


# ── Singleton ──────────────────────────────────────────────────────────────────────

_gate: Optional[QualityGateEngine] = None


def get_quality_gate() -> QualityGateEngine:
    global _gate
    if _gate is None:
        _gate = QualityGateEngine()
    return _gate
