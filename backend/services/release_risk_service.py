# -*- coding: utf-8 -*-
"""
发布风险评估服务

聚合探索性测试发现与发布输入信号，生成业务风险、体验风险、
发布风险和自动发布资格结论。
"""
from __future__ import annotations

from datetime import datetime
import json
from typing import Any, Dict, List, Optional
import uuid

from core.db_helper import get_connection
from services.exploration_service import get_exploration_service


class ReleaseRiskServiceError(Exception):
    """发布风险评估服务异常。"""


class ReleaseRiskAssessmentNotFoundError(ReleaseRiskServiceError):
    """未找到发布风险评估。"""


class ReleaseRiskPermissionError(ReleaseRiskServiceError):
    """发布风险评估权限异常。"""


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


class ReleaseRiskService:
    """发布风险评估持久化与策略判定服务。"""

    def __init__(self):
        self._ensure_schema()

    def _ensure_schema(self):
        with get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS release_risk_assessments (
                    assessment_id TEXT PRIMARY KEY,
                    project_key TEXT DEFAULT '',
                    environment TEXT DEFAULT '',
                    requester_id TEXT DEFAULT '',
                    input_json TEXT DEFAULT '{}',
                    business_risk TEXT DEFAULT 'medium',
                    ux_risk TEXT DEFAULT 'medium',
                    release_risk TEXT DEFAULT 'medium',
                    blockers_json TEXT DEFAULT '[]',
                    auto_release_eligible INTEGER DEFAULT 0,
                    evidence_json TEXT DEFAULT '{}',
                    policy_hit_json TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_release_risk_created ON release_risk_assessments(created_at DESC)"
            )

    def create_assessment(
        self,
        *,
        user,
        project_key: str,
        environment: str,
        exploration_session_ids: List[str],
        required_tests_passed: bool,
        change_summary: str = "",
    ) -> Dict[str, Any]:
        self._ensure_project_scope(user, project_key)
        findings = get_exploration_service().list_findings_for_sessions(exploration_session_ids)
        assessment_id = f"release_{uuid.uuid4().hex[:12]}"
        analysis = self._analyze(
            environment=environment,
            findings=findings,
            required_tests_passed=required_tests_passed,
        )
        created_at = _now_iso()
        input_payload = {
            "project_key": project_key,
            "environment": environment,
            "exploration_session_ids": exploration_session_ids,
            "required_tests_passed": required_tests_passed,
            "change_summary": change_summary,
        }
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO release_risk_assessments (
                    assessment_id, project_key, environment, requester_id, input_json,
                    business_risk, ux_risk, release_risk, blockers_json, auto_release_eligible,
                    evidence_json, policy_hit_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assessment_id,
                    project_key,
                    environment,
                    getattr(user, "user_id", ""),
                    _json_dump(input_payload),
                    analysis["business_risk"],
                    analysis["ux_risk"],
                    analysis["release_risk"],
                    _json_dump(analysis["blockers"]),
                    1 if analysis["auto_release_eligible"] else 0,
                    _json_dump(analysis["evidence"]),
                    _json_dump(analysis["policy_hit"]),
                    created_at,
                ),
            )
        return self.get_assessment(user=user, assessment_id=assessment_id)

    def get_assessment(self, *, user, assessment_id: str) -> Dict[str, Any]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM release_risk_assessments WHERE assessment_id = ?",
                (assessment_id,),
            ).fetchone()
        if not row:
            raise ReleaseRiskAssessmentNotFoundError(f"未找到发布风险评估 {assessment_id}")
        payload = self._serialize_assessment(dict(row))
        self._ensure_project_scope(user, payload["project_key"])
        return payload

    def list_assessments(
        self,
        *,
        user,
        project_key: str = "",
        environment: str = "",
        auto_release_eligible: Optional[bool] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        self._ensure_project_scope(user, project_key)
        sql = [
            "SELECT * FROM release_risk_assessments",
            "WHERE 1=1",
        ]
        params: List[Any] = []
        if project_key:
            sql.append("AND project_key = ?")
            params.append(project_key)
        if environment:
            sql.append("AND environment = ?")
            params.append(environment)
        if auto_release_eligible is not None:
            sql.append("AND auto_release_eligible = ?")
            params.append(1 if auto_release_eligible else 0)
        sql.append("ORDER BY created_at DESC")
        sql.append("LIMIT ?")
        params.append(max(1, min(int(limit), 200)))

        with get_connection() as conn:
            rows = conn.execute(" ".join(sql), tuple(params)).fetchall()

        assessments: List[Dict[str, Any]] = []
        for item in rows:
            payload = self._serialize_assessment(dict(item))
            try:
                self._ensure_project_scope(user, payload["project_key"])
            except ReleaseRiskPermissionError:
                continue
            assessments.append(payload)
        return {"assessments": assessments, "count": len(assessments)}

    def _serialize_assessment(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "assessment_id": str(row.get("assessment_id") or ""),
            "project_key": str(row.get("project_key") or ""),
            "environment": str(row.get("environment") or ""),
            "requester_id": str(row.get("requester_id") or ""),
            "input": _json_load(row.get("input_json"), {}),
            "business_risk": str(row.get("business_risk") or ""),
            "ux_risk": str(row.get("ux_risk") or ""),
            "release_risk": str(row.get("release_risk") or ""),
            "blockers": _json_load(row.get("blockers_json"), []),
            "auto_release_eligible": bool(row.get("auto_release_eligible")),
            "evidence": _json_load(row.get("evidence_json"), {}),
            "policy_hit": _json_load(row.get("policy_hit_json"), {}),
            "created_at": str(row.get("created_at") or ""),
        }

    def _ensure_project_scope(self, user, project_key: str):
        if not project_key:
            return
        if not user:
            raise ReleaseRiskPermissionError("需要登录态")
        role_value = getattr(getattr(user, "role", None), "value", getattr(user, "role", ""))
        if role_value == "admin":
            return
        scope = {str(item).strip() for item in (getattr(user, "project_ids", None) or []) if str(item).strip()}
        if scope and "*" not in scope and project_key not in scope:
            raise ReleaseRiskPermissionError(f"当前账号无权访问项目 {project_key}")

    def _analyze(
        self,
        *,
        environment: str,
        findings: List[Dict[str, Any]],
        required_tests_passed: bool,
    ) -> Dict[str, Any]:
        env_text = str(environment or "").strip().lower()
        highest_business = "low"
        highest_ux = "low"
        blockers: List[Dict[str, Any]] = []
        severity_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        effective_findings: List[Dict[str, Any]] = []
        active_review_findings: List[Dict[str, Any]] = []
        pending_review_findings: List[str] = []
        confirmed_review_findings: List[str] = []
        review_summary = {
            "pending": 0,
            "confirmed": 0,
            "dismissed": 0,
            "active": 0,
            "effective": 0,
        }

        for finding in findings:
            severity = str(finding.get("severity") or "low")
            finding_type = str(finding.get("finding_type") or "regression")
            review_status = str(finding.get("review_status") or "pending").strip().lower() or "pending"

            if review_status not in review_summary:
                review_summary[review_status] = 0
            review_summary[review_status] += 1

            if review_status == "dismissed":
                continue

            effective_findings.append(finding)
            if finding_type == "ux" and severity_order[severity] > severity_order[highest_ux]:
                highest_ux = severity
            if finding_type != "ux" and severity_order[severity] > severity_order[highest_business]:
                highest_business = severity
            if finding.get("requires_human_review"):
                active_review_findings.append(finding)
                if review_status == "pending":
                    pending_review_findings.append(str(finding.get("finding_id") or ""))
                    blockers.append(
                        {
                            "type": "human_review_pending",
                            "finding_id": finding.get("finding_id"),
                            "title": finding.get("title"),
                            "severity": severity,
                            "review_status": review_status,
                            "message": "存在待人工复核发现，禁止自动发布。",
                        }
                    )
                elif review_status == "confirmed":
                    confirmed_review_findings.append(str(finding.get("finding_id") or ""))
                    blockers.append(
                        {
                            "type": "confirmed_issue_requires_manual_release",
                            "finding_id": finding.get("finding_id"),
                            "title": finding.get("title"),
                            "severity": severity,
                            "review_status": review_status,
                            "message": "存在已确认问题，需人工放行。",
                        }
                    )

        review_summary["active"] = len(active_review_findings)
        review_summary["effective"] = len(effective_findings)

        if not required_tests_passed:
            blockers.append(
                {
                    "type": "required_tests_failed",
                    "message": "所需测试尚未全部通过，禁止自动发布。",
                }
            )

        if env_text in {"prod", "production", "online"}:
            blockers.append(
                {
                    "type": "production_requires_manual_approval",
                    "message": "生产环境发布必须保留人工批准。",
                }
            )

        release_risk = highest_business
        if severity_order[highest_ux] > severity_order[release_risk]:
            release_risk = highest_ux
        if blockers and severity_order[release_risk] < severity_order["high"]:
            release_risk = "high"

        auto_release_eligible = (
            env_text not in {"prod", "production", "online"}
            and not blockers
            and required_tests_passed
            and severity_order[release_risk] <= severity_order["low"]
        )

        return {
            "business_risk": highest_business,
            "ux_risk": highest_ux,
            "release_risk": release_risk,
            "blockers": blockers,
            "auto_release_eligible": auto_release_eligible,
            "evidence": {
                "finding_count": len(findings),
                "effective_finding_count": len(effective_findings),
                "high_risk_findings": [
                    item["finding_id"]
                    for item in effective_findings
                    if str(item.get("severity") or "low") in {"high", "critical"}
                ],
                "human_review_count": len(active_review_findings),
                "review_summary": review_summary,
                "pending_review_findings": pending_review_findings,
                "confirmed_findings": confirmed_review_findings,
            },
            "policy_hit": {
                "nonprod_only": env_text not in {"prod", "production", "online"},
                "required_tests_passed": required_tests_passed,
                "review_policy_mode": "conservative",
                "review_blocked": bool(pending_review_findings or confirmed_review_findings),
                "auto_release_eligible": auto_release_eligible,
            },
        }


_service_instance: Optional[ReleaseRiskService] = None


def get_release_risk_service() -> ReleaseRiskService:
    global _service_instance
    if _service_instance is None:
        _service_instance = ReleaseRiskService()
    return _service_instance
