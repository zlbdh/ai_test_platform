# -*- coding: utf-8 -*-
"""
探索性测试会话服务

提供探索性测试会话、结构化发现与证据包的持久化能力。
当前版本先基于测试章程和目标 URL 做受控启发式归纳，
为后续接入真实浏览器探索和 VLM 分析预留稳定数据模型。
"""
from __future__ import annotations

from datetime import datetime
import json
from typing import Any, Dict, List, Optional
import uuid

from core.db_helper import get_connection


class ExplorationServiceError(Exception):
    """探索性测试服务异常。"""


class ExplorationPermissionError(ExplorationServiceError):
    """探索性测试访问权限异常。"""


class ExplorationSessionNotFoundError(ExplorationServiceError):
    """未找到探索性测试会话。"""


class ExplorationFindingNotFoundError(ExplorationServiceError):
    """未找到探索发现。"""


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
    """探索性测试会话与发现持久化服务。"""

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
            raise ExplorationServiceError("复核结论仅支持 confirmed 或 dismissed")

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
            raise ExplorationSessionNotFoundError(f"未找到探索会话 {session_id}")
        return dict(row)

    def _load_finding(self, finding_id: str) -> Dict[str, Any]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM experience_findings WHERE finding_id = ?",
                (finding_id,),
            ).fetchone()
        if not row:
            raise ExplorationFindingNotFoundError(f"未找到探索发现 {finding_id}")
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
            raise ExplorationPermissionError("需要登录态")
        role_value = getattr(getattr(user, "role", None), "value", getattr(user, "role", ""))
        if role_value == "admin":
            return
        scope = {str(item).strip() for item in (getattr(user, "project_ids", None) or []) if str(item).strip()}
        if scope and "*" not in scope and project_key not in scope:
            raise ExplorationPermissionError(f"当前账号无权访问项目 {project_key}")

    def _generate_findings(self, *, target_url: str, charter: str) -> List[Dict[str, Any]]:
        text = f"{target_url}\n{charter}".lower()
        findings: List[Dict[str, Any]] = []
        if any(keyword in text for keyword in ("login", "登录", "auth", "认证")):
            findings.append(
                self._build_finding(
                    severity="medium",
                    finding_type="business",
                    title="登录主链路需重点复核",
                    summary="探索性章程涉及登录/认证流程，建议对鉴权跳转、失败提示和重试链路做人工复核。",
                    confidence=0.74,
                    requires_human_review=True,
                    impact_scope="认证主链路",
                )
            )
        if any(keyword in text for keyword in ("payment", "支付", "checkout", "下单")):
            findings.append(
                self._build_finding(
                    severity="high",
                    finding_type="business",
                    title="交易链路存在高业务风险",
                    summary="章程覆盖支付/下单场景，任何异常都会直接影响成交，需要发布前人工签核。",
                    confidence=0.82,
                    requires_human_review=True,
                    impact_scope="交易转化链路",
                )
            )
        if any(keyword in text for keyword in ("search", "搜索", "discover", "browse", "列表")):
            findings.append(
                self._build_finding(
                    severity="medium",
                    finding_type="ux",
                    title="信息发现路径需补体验评估",
                    summary="探索性章程覆盖搜索/浏览场景，建议补充空态、筛选器和移动端首屏体验检查。",
                    confidence=0.68,
                    requires_human_review=False,
                    impact_scope="发现与浏览体验",
                )
            )
        if not findings:
            findings.append(
                self._build_finding(
                    severity="low",
                    finding_type="regression",
                    title="需补默认回归关注项",
                    summary="当前章程未命中特定高风险域，已生成通用回归关注项并建议抽样人工复核关键路径。",
                    confidence=0.61,
                    requires_human_review=False,
                    impact_scope="通用回归覆盖面",
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
                "阅读探索性测试章程并锁定目标主链路",
                "基于章程生成优先探索路径",
                "对高风险节点补人工复核建议",
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
            "conclusion": "探索性测试会话已生成结构化发现，建议结合人工复核队列做最终发布判断。",
        }


_service_instance: Optional[ExplorationService] = None


def get_exploration_service() -> ExplorationService:
    global _service_instance
    if _service_instance is None:
        _service_instance = ExplorationService()
    return _service_instance
