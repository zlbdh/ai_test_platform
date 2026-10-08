# -*- coding: utf-8 -*-
"""
Exploratory Testing Session Service

Persist exploratory testing sessions, structured findings, and evidence packages.
The current version uses controlled heuristics based on the test charter and target URL,
providing a stable data model for future browser exploration and VLM analysis.
"""
from __future__ import annotations

from datetime import datetime
import json
from typing import Any, Dict, List, Optional
import uuid

from core.db_helper import get_connection


class ExplorationServiceError(Exception):
    """Exploratory testing service error."""


class ExplorationPermissionError(ExplorationServiceError):
    """Exploratory testing permission error."""


class ExplorationSessionNotFoundError(ExplorationServiceError):
    """Exploratory testing session not found."""


class ExplorationFindingNotFoundError(ExplorationServiceError):
    """Exploratory finding not found."""


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _json_dump(payload: Any) -> str:
    return json.dumps(payload if payload is not None else {}, ensure_ascii=False, default=str)


def _json_load(payload: Optional[str], default: Any) -> Any:
    raw = str(payload or "").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


class ExplorationService:
    """Persistence service for exploratory testing sessions and findings."""

    def __init__(self):
        self._ensure_schema()

    def _ensure_schema(self):
        with get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS exploration_sessions (
                    session_id TEXT PRIMARY KEY,
                    group_id TEXT DEFAULT '',
                    project_key TEXT DEFAULT '',
                    target_url TEXT DEFAULT '',
                    charter TEXT DEFAULT '',
                    requester_id TEXT DEFAULT '',
                    status TEXT DEFAULT 'created',
                    summary_json TEXT DEFAULT '{}',
                    risk_score REAL DEFAULT 0,
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS experience_findings (
                    finding_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    project_key TEXT DEFAULT '',
                    severity TEXT DEFAULT 'low',
                    finding_type TEXT DEFAULT 'regression',
                    title TEXT DEFAULT '',
                    summary TEXT DEFAULT '',
                    confidence REAL DEFAULT 0,
                    evidence_json TEXT DEFAULT '{}',
                    requires_human_review INTEGER DEFAULT 0,
                    review_status TEXT DEFAULT 'pending',
                    review_comment TEXT DEFAULT '',
                    reviewed_by TEXT DEFAULT '',
                    reviewed_at TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_exploration_sessions_created ON exploration_sessions(created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_experience_findings_session ON experience_findings(session_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_experience_findings_review ON experience_findings(review_status, requires_human_review, created_at DESC)"
            )
            existing_columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(experience_findings)").fetchall()
            }
            migrations = {
                "review_status": "ALTER TABLE experience_findings ADD COLUMN review_status TEXT DEFAULT 'pending'",
                "review_comment": "ALTER TABLE experience_findings ADD COLUMN review_comment TEXT DEFAULT ''",
                "reviewed_by": "ALTER TABLE experience_findings ADD COLUMN reviewed_by TEXT DEFAULT ''",
                "reviewed_at": "ALTER TABLE experience_findings ADD COLUMN reviewed_at TEXT DEFAULT ''",
            }
            for column_name, sql in migrations.items():
                if column_name not in existing_columns:
                    conn.execute(sql)

    def create_session(
        self,
        *,
        user,
        group_id: str,
        project_key: str,
        target_url: str,
        charter: str,
    ) -> Dict[str, Any]:
        self._ensure_project_scope(user, project_key)
        session_id = f"explore_{uuid.uuid4().hex[:12]}"
        findings = self._generate_findings(target_url=target_url, charter=charter)
        risk_score = self._calculate_risk_score(findings)
        summary = self._build_summary(target_url=target_url, charter=charter, findings=findings, risk_score=risk_score)
        now = _now_iso()

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO exploration_sessions (
                    session_id, group_id, project_key, target_url, charter, requester_id,
                    status, summary_json, risk_score, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    group_id,
                    project_key,
                    target_url,
                    charter,
                    getattr(user, "user_id", ""),
                    "completed",
                    _json_dump(summary),
                    float(risk_score),
                    now,
                    now,
                ),
            )
            for finding in findings:
                conn.execute(
                    """
                    INSERT INTO experience_findings (
                        finding_id, session_id, project_key, severity, finding_type, title,
                        summary, confidence, evidence_json, requires_human_review,
                        review_status, review_comment, reviewed_by, reviewed_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        finding["finding_id"],
                        session_id,
                        project_key,
                        finding["severity"],
                        finding["finding_type"],
                        finding["title"],
                        finding["summary"],
                        float(finding["confidence"]),
                        _json_dump(finding["evidence"]),
                        1 if finding["requires_human_review"] else 0,
                        "pending",
                        "",
                        "",
                        "",
                        now,
                    ),
                )

        return self.get_session(user=user, session_id=session_id)

    def get_session(self, *, user, session_id: str) -> Dict[str, Any]:
        row = self._load_session(session_id)
        self._ensure_project_scope(user, str(row.get("project_key") or ""))
        payload = self._serialize_session(row)
        payload["findings"] = self.list_findings(user=user, session_id=session_id)["findings"]
        return payload

    def list_sessions(
        self,
        *,
        user,
        project_key: str = "",
        status: str = "",
        limit: int = 20,
    ) -> Dict[str, Any]:
        self._ensure_project_scope(user, project_key)
        sql = [
            "SELECT * FROM exploration_sessions",
            "WHERE 1=1",
        ]
        params: List[Any] = []
        if project_key:
            sql.append("AND project_key = ?")
            params.append(project_key)
        if status:
            sql.append("AND status = ?")
            params.append(status)
        sql.append("ORDER BY created_at DESC")
        sql.append("LIMIT ?")
        params.append(max(1, min(int(limit), 200)))

        with get_connection() as conn:
            rows = conn.execute(" ".join(sql), tuple(params)).fetchall()

        sessions: List[Dict[str, Any]] = []
        for item in rows:
            row = dict(item)
            try:
                self._ensure_project_scope(user, str(row.get("project_key") or ""))
            except ExplorationPermissionError:
                continue
            sessions.append(self._serialize_session(row))
        return {"sessions": sessions, "count": len(sessions)}

    def stop_session(self, *, user, session_id: str) -> Dict[str, Any]:
        row = self._load_session(session_id)
        self._ensure_project_scope(user, str(row.get("project_key") or ""))
        status = str(row.get("status") or "")
        if status not in {"completed", "stopped", "cancelled"}:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE exploration_sessions SET status = ?, updated_at = ? WHERE session_id = ?",
                    ("stopped", _now_iso(), session_id),
                )
        return self.get_session(user=user, session_id=session_id)

    def list_findings(
        self,
        *,
        user,
        session_id: str,
        severity: str = "",
        review_only: bool = False,
        review_status: str = "",
    ) -> Dict[str, Any]:
        row = self._load_session(session_id)
        self._ensure_project_scope(user, str(row.get("project_key") or ""))
        sql = [
            "SELECT * FROM experience_findings WHERE session_id = ?",
        ]
        params: List[Any] = [session_id]
        if severity:
            sql.append("AND severity = ?")
            params.append(severity)
        if review_only:
            sql.append("AND requires_human_review = 1")
        if review_status:
            sql.append("AND review_status = ?")
            params.append(review_status)
        sql.append("ORDER BY created_at DESC")

        with get_connection() as conn:
            rows = conn.execute(" ".join(sql), tuple(params)).fetchall()

        findings = [self._serialize_finding(dict(item)) for item in rows]
        return {"session_id": session_id, "findings": findings, "count": len(findings)}

    def get_finding(self, *, user, finding_id: str) -> Dict[str, Any]:
        row = self._load_finding(finding_id)
        self._ensure_project_scope(user, str(row.get("project_key") or ""))
        return self._serialize_finding(row)

    def review_finding(
        self,
        *,
        user,
        finding_id: str,
        decision: str,
        comment: str = "",
    ) -> Dict[str, Any]:
        row = self._load_finding(finding_id)
        self._ensure_project_scope(user, str(row.get("project_key") or ""))
        next_status = str(decision or "").strip().lower()
        if next_status not in {"confirmed", "dismissed"}:
            raise ExplorationServiceError("Review decision must be confirmed or dismissed")

        reviewed_by = str(getattr(user, "username", "") or getattr(user, "user_id", "") or "")
        reviewed_at = _now_iso()
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE experience_findings
                SET review_status = ?, review_comment = ?, reviewed_by = ?, reviewed_at = ?
                WHERE finding_id = ?
                """,
                (
                    next_status,
                    str(comment or ""),
                    reviewed_by,
                    reviewed_at,
                    finding_id,
                ),
            )
        return self.get_finding(user=user, finding_id=finding_id)

    def list_review_queue(
        self,
        *,
        user,
        project_key: str = "",
        severity: str = "",
        review_status: str = "",
        limit: int = 20,
    ) -> Dict[str, Any]:
        self._ensure_project_scope(user, project_key)
        next_review_status = str(review_status or "").strip() or "pending"
        sql = [
            "SELECT * FROM experience_findings",
            "WHERE requires_human_review = 1",
        ]
        params: List[Any] = []
        if project_key:
            sql.append("AND project_key = ?")
            params.append(project_key)
        if severity:
            sql.append("AND severity = ?")
            params.append(severity)
        if next_review_status:
            sql.append("AND review_status = ?")
            params.append(next_review_status)
        sql.append("ORDER BY created_at DESC")

        with get_connection() as conn:
            rows = conn.execute(" ".join(sql), tuple(params)).fetchall()

        accessible_rows: List[Dict[str, Any]] = []
        for item in rows:
            row = dict(item)
            try:
                self._ensure_project_scope(user, str(row.get("project_key") or ""))
            except ExplorationPermissionError:
                continue
            accessible_rows.append(row)
        findings = [
            self._serialize_finding(item)
            for item in accessible_rows[: max(1, min(int(limit), 200))]
        ]
        return {
            "review_status": next_review_status,
            "findings": findings,
            "count": len(accessible_rows),
        }

    def list_findings_for_sessions(self, session_ids: List[str]) -> List[Dict[str, Any]]:
        valid_ids = [str(item).strip() for item in session_ids if str(item).strip()]
        if not valid_ids:
            return []
        placeholders = ", ".join("?" for _ in valid_ids)
        with get_connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM experience_findings WHERE session_id IN ({placeholders}) ORDER BY created_at DESC",
                tuple(valid_ids),
            ).fetchall()
        return [self._serialize_finding(dict(item)) for item in rows]

    def _load_session(self, session_id: str) -> Dict[str, Any]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM exploration_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            raise ExplorationSessionNotFoundError(f"Exploratory session not found: {session_id}")
        return dict(row)

    def _load_finding(self, finding_id: str) -> Dict[str, Any]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM experience_findings WHERE finding_id = ?",
                (finding_id,),
            ).fetchone()
        if not row:
            raise ExplorationFindingNotFoundError(f"Exploratory finding not found: {finding_id}")
        return dict(row)

    def _serialize_session(self, row: Dict[str, Any]) -> Dict[str, Any]:
        summary = _json_load(row.get("summary_json"), {})
        return {
            "session_id": str(row.get("session_id") or ""),
            "group_id": str(row.get("group_id") or ""),
            "project_key": str(row.get("project_key") or ""),
            "target_url": str(row.get("target_url") or ""),
            "charter": str(row.get("charter") or ""),
            "requester_id": str(row.get("requester_id") or ""),
            "status": str(row.get("status") or ""),
            "summary": summary,
            "risk_score": float(row.get("risk_score") or 0),
            "finding_count": int(summary.get("finding_count") or 0),
            "human_review_count": int(summary.get("requires_human_review_count") or 0),
            "created_at": str(row.get("created_at") or ""),
            "updated_at": str(row.get("updated_at") or ""),
        }

    def _serialize_finding(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "finding_id": str(row.get("finding_id") or ""),
            "session_id": str(row.get("session_id") or ""),
            "project_key": str(row.get("project_key") or ""),
            "severity": str(row.get("severity") or ""),
            "finding_type": str(row.get("finding_type") or ""),
            "title": str(row.get("title") or ""),
            "summary": str(row.get("summary") or ""),
            "confidence": float(row.get("confidence") or 0),
            "evidence": _json_load(row.get("evidence_json"), {}),
            "requires_human_review": bool(row.get("requires_human_review")),
            "review_status": str(row.get("review_status") or "pending"),
            "review_comment": str(row.get("review_comment") or ""),
            "reviewed_by": str(row.get("reviewed_by") or ""),
            "reviewed_at": str(row.get("reviewed_at") or ""),
            "created_at": str(row.get("created_at") or ""),
        }

    def _ensure_project_scope(self, user, project_key: str):
        if not project_key:
            return
        if not user:
            raise ExplorationPermissionError("Authentication is required")
        role_value = getattr(getattr(user, "role", None), "value", getattr(user, "role", ""))
        if role_value == "admin":
            return
        scope = {str(item).strip() for item in (getattr(user, "project_ids", None) or []) if str(item).strip()}
        if scope and "*" not in scope and project_key not in scope:
            raise ExplorationPermissionError(f"The current account does not have access to project {project_key}")

    def _generate_findings(self, *, target_url: str, charter: str) -> List[Dict[str, Any]]:
        text = f"{target_url}\n{charter}".lower()
        findings: List[Dict[str, Any]] = []
        if any(keyword in text for keyword in ("login", "登录", "auth", "认证")):
            findings.append(
                self._build_finding(
                    severity="medium",
                    finding_type="business",
                    title="The primary sign-in flow requires close review",
                    summary="The exploratory charter covers sign-in or authentication. Manually review authentication redirects, failure messages, and retry flows.",
                    confidence=0.74,
                    requires_human_review=True,
                    impact_scope="Primary authentication flow",
                )
            )
        if any(keyword in text for keyword in ("payment", "支付", "checkout", "下单")):
            findings.append(
                self._build_finding(
                    severity="high",
                    finding_type="business",
                    title="The transaction flow has high business risk",
                    summary="The charter covers payment or checkout. Any anomaly directly affects conversion and requires manual sign-off before release.",
                    confidence=0.82,
                    requires_human_review=True,
                    impact_scope="Transaction conversion flow",
                )
            )
        if any(keyword in text for keyword in ("search", "搜索", "discover", "browse", "列表")):
            findings.append(
                self._build_finding(
                    severity="medium",
                    finding_type="ux",
                    title="The discovery path needs additional experience assessment",
                    summary="The exploratory charter covers search or browsing. Add checks for empty states, filters, and the first mobile screen.",
                    confidence=0.68,
                    requires_human_review=False,
                    impact_scope="Discovery and browsing experience",
                )
            )
        if not findings:
            findings.append(
                self._build_finding(
                    severity="low",
                    finding_type="regression",
                    title="Add default regression focus areas",
                    summary="The charter did not match a specific high-risk domain. General regression focus areas were generated; manually sample key paths.",
                    confidence=0.61,
                    requires_human_review=False,
                    impact_scope="General regression coverage",
                )
            )
        return findings

    def _build_finding(
        self,
        *,
        severity: str,
        finding_type: str,
        title: str,
        summary: str,
        confidence: float,
        requires_human_review: bool,
        impact_scope: str,
    ) -> Dict[str, Any]:
        evidence = {
            "screenshot": "",
            "dom_excerpt": "<synthetic-exploration-context />",
            "network_excerpt": "pending_live_capture",
            "reproduction_steps": [
                "Read the exploratory test charter and identify the primary target flow",
                "Generate prioritized exploration paths from the charter",
                "Add manual review recommendations for high-risk steps",
            ],
            "impact_scope": impact_scope,
            "ai_confidence": confidence,
        }
        return {
            "finding_id": f"finding_{uuid.uuid4().hex[:12]}",
            "severity": severity,
            "finding_type": finding_type,
            "title": title,
            "summary": summary,
            "confidence": confidence,
            "evidence": evidence,
            "requires_human_review": requires_human_review,
        }

    def _calculate_risk_score(self, findings: List[Dict[str, Any]]) -> float:
        weights = {"low": 0.25, "medium": 0.55, "high": 0.82, "critical": 0.95}
        score = 0.0
        for finding in findings:
            score = max(score, weights.get(str(finding.get("severity") or "low"), 0.25))
            if finding.get("requires_human_review"):
                score = max(score, min(0.99, score + 0.08))
        return round(score, 2)

    def _build_summary(
        self,
        *,
        target_url: str,
        charter: str,
        findings: List[Dict[str, Any]],
        risk_score: float,
    ) -> Dict[str, Any]:
        severity_counts: Dict[str, int] = {}
        for finding in findings:
            severity = str(finding.get("severity") or "low")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        return {
            "target_url": target_url,
            "charter": charter,
            "finding_count": len(findings),
            "severity_breakdown": severity_counts,
            "requires_human_review_count": sum(1 for item in findings if item.get("requires_human_review")),
            "risk_score": risk_score,
            "conclusion": "The exploratory testing session generated structured findings. Use the manual review queue for the final release decision.",
        }


_service_instance: Optional[ExplorationService] = None


def get_exploration_service() -> ExplorationService:
    global _service_instance
    if _service_instance is None:
        _service_instance = ExplorationService()
    return _service_instance
