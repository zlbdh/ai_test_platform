# -*- coding: utf-8 -*-
"""
Platform Readiness Service

Assess progress toward production from both local (modules/features)
and global (architecture/goals/overall design) perspectives.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from core.db_helper import get_connection, get_db_observability
from services.commander_chatops_service import get_commander_chatops_service
from services.platform_maintenance_service import get_platform_maintenance_service


class PlatformReadinessService:
    def _table_exists(self, conn, table_name: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (table_name,),
        ).fetchone()
        return row is not None

    def _safe_count(self, table_name: str) -> int:
        try:
            with get_connection() as conn:
                if not self._table_exists(conn, table_name):
                    return 0
                row = conn.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
                return int((row["count"] if row else 0) or 0)
        except Exception:
            return 0

    def _status_from_score(self, score: int) -> str:
        if score >= 85:
            return "good"
        if score >= 60:
            return "warning"
        return "critical"

    def _build_local_sections(
        self,
        maintenance: Dict[str, Any],
        chatops: Dict[str, Any],
        db_observability: Dict[str, Any],
        execution_groups: int,
        test_runs: int,
    ) -> List[Dict[str, Any]]:
        notification = maintenance.get("notification") or {}
        data_quality = maintenance.get("data_quality") or {}
        report_history = maintenance.get("report_history") or {}

        maintenance_status = str(maintenance.get("status") or "never")
        maintenance_skipped = bool(maintenance.get("skipped"))
        maintenance_score = 100 if maintenance_status == "success" and not maintenance_skipped else 75 if maintenance_status == "success" else 35 if maintenance_status == "failed" else 50

        notification_count = int(notification.get("webhook_count") or 0)
        notification_tested = int(notification.get("tested_enabled") or 0)
        notification_healthy = int(notification.get("healthy_enabled") or 0)
        notification_ready = bool(notification.get("ready"))
        if notification_ready:
            notification_score = 100
        elif notification_count > 0 and notification_tested > 0:
            notification_score = 55
        elif notification_count > 0:
            notification_score = 45
        else:
            notification_score = 30

        chatops_ready = bool(chatops.get("ready"))
        chatops_platform_ready = bool(chatops.get("platform_ready"))
        chatops_external_connected = bool(chatops.get("external_connected"))
        chatops_external_history_observed = bool(
            chatops.get("external_connected_history_observed")
            or chatops.get("latest_external_successful_event")
        )
        chatops_external_connection_stale = bool(chatops.get("external_connection_stale"))
        chatops_external_callback_ready = bool(chatops.get("external_callback_ready"))
        chatops_direct_chat_ready = bool(chatops.get("direct_chat_ready", chatops_ready))
        chatops_app_bot_configured = bool(chatops.get("app_bot_configured"))
        chatops_app_bot_ready = bool(chatops.get("app_bot_ready"))
        chatops_webhook_ready = bool(chatops.get("webhook_ready"))
        chatops_token_ready = bool(chatops.get("verification_token_configured"))
        chatops_probe = chatops.get("callback_probe") or {}
        chatops_probe_success = bool(chatops_probe.get("success"))
        if chatops_direct_chat_ready:
            chatops_score = 100
        elif chatops_platform_ready and chatops_external_callback_ready:
            chatops_score = 96
        elif chatops_platform_ready and chatops_external_connection_stale:
            chatops_score = 68
        elif chatops_platform_ready and chatops_probe_success:
            chatops_score = 94
        elif chatops_platform_ready:
            chatops_score = 82
        elif chatops_webhook_ready and chatops_token_ready:
            chatops_score = 80
        elif chatops_webhook_ready:
            chatops_score = 70
        elif int(chatops.get("enabled_notification_platform_webhook_count") or 0) > 0:
            chatops_score = 55
        else:
            chatops_score = 40

        suspect_count = int(data_quality.get("suspect_history_count") or 0)
        archived_count = int(data_quality.get("archived_history_count") or 0)
        archive_export_fresh = bool(data_quality.get("archive_export_fresh", archived_count == 0))
        archive_cleanup_needed = bool(data_quality.get("archive_cleanup_needed", False))
        shadow_count = int(db_observability.get("shadow_count") or 0)
        governance_score = 100
        if shadow_count > 0:
            governance_score -= 25
        if suspect_count > 0:
            governance_score -= 35
        elif archived_count > 0 and not archive_export_fresh:
            governance_score -= 5
        if archive_cleanup_needed:
            governance_score -= 5
        governance_score = max(governance_score, 20)

        report_entries = int(report_history.get("history_entries") or 0)
        execution_score = 100 if execution_groups > 0 and test_runs > 0 and report_entries > 0 else 75 if execution_groups > 0 and test_runs > 0 else 45

        return [
            {
                "key": "maintenance_module",
                "name": "Maintenance Module",
                "score": maintenance_score,
                "status": self._status_from_score(maintenance_score),
                "summary": f"Current status: {maintenance_status}; latest reason: {maintenance.get('reason') or 'Not run'}",
            },
            {
                "key": "notification_module",
                "name": "Alerting Module",
                "score": notification_score,
                "status": self._status_from_score(notification_score),
                "summary": str(notification.get("summary") or "No production alert channel connected"),
            },
            {
                "key": "chatops_module",
                "name": "Notification Command Channel",
                "score": chatops_score,
                "status": self._status_from_score(chatops_score),
                "summary": (
                    f"{str(chatops.get('summary') or 'The bidirectional notification command channel has not been assessed')} "
                    f"(Platform: {'ready' if chatops_platform_ready else 'incomplete'} / "
                    f"Public callback: {'connected' if chatops_external_callback_ready else 'unverified'} / "
                    f"App credentials: {'verified' if chatops_app_bot_ready else 'saved, awaiting validation' if chatops_app_bot_configured else 'not saved'} / "
                    f"Direct group chat: {'connected' if chatops_external_connected else 'unverified'} / "
                    f"Historical inbound messages: {'observed' if chatops_external_history_observed else 'not observed'}"
                    f"{' (currently degraded)' if chatops_external_connection_stale else ''})"
                ),
            },
            {
                "key": "data_governance_module",
                "name": "Data Governance",
                "score": governance_score,
                "status": self._status_from_score(governance_score),
                "summary": (
                    f"Shadow databases: {shadow_count}; active suspicious maintenance records: {suspect_count}; "
                    f"Archived {archived_count}; archive export: {'complete' if archive_export_fresh else 'update needed'}, "
                    f"Overdue cleanup: {'pending' if archive_cleanup_needed else 'healthy'}"
                ),
            },
            {
                "key": "execution_center_module",
                "name": "Execution Workflow",
                "score": execution_score,
                "status": self._status_from_score(execution_score),
                "summary": f"Execution batches: {execution_groups}; test records: {test_runs}; report history: {report_entries}",
            },
        ]

    def _build_global_sections(
        self,
        local_sections: List[Dict[str, Any]],
        chatops: Dict[str, Any],
        db_observability: Dict[str, Any],
        maintenance: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        notification = maintenance.get("notification") or {}
        data_quality = maintenance.get("data_quality") or {}

        architecture_score = 88
        if int(db_observability.get("shadow_count") or 0) > 0:
            architecture_score -= 8

        delivery_score = 92
        if int(data_quality.get("archived_history_count") or 0) > 0 and not bool(data_quality.get("archive_export_fresh", False)):
            delivery_score -= 4
        if int(data_quality.get("suspect_history_count") or 0) > 0:
            delivery_score -= 18

        operations_score = round(
            (
                next(section["score"] for section in local_sections if section["key"] == "maintenance_module")
                + next(section["score"] for section in local_sections if section["key"] == "notification_module")
                + next(section["score"] for section in local_sections if section["key"] == "chatops_module")
                + next(section["score"] for section in local_sections if section["key"] == "data_governance_module")
            ) / 4
        )

        goal_score = 95
        if not bool(notification.get("ready")):
            goal_score -= 20
        elif not bool(chatops.get("ready")):
            goal_score -= 2 if bool(chatops.get("platform_ready")) else 5
        if int(db_observability.get("shadow_count") or 0) > 0:
            goal_score -= 10
        if int(data_quality.get("suspect_history_count") or 0) > 0:
            goal_score -= 10

        return [
            {
                "key": "architecture",
                "name": "Architecture Stability",
                "score": architecture_score,
                "status": self._status_from_score(architecture_score),
                "summary": "Core layers, execution center, reporting, and the primary maintenance workflow are established",
            },
            {
                "key": "delivery_governance",
                "name": "Delivery Governance",
                "score": delivery_score,
                "status": self._status_from_score(delivery_score),
                "summary": "The platform supports batch archival, suspicious-history archival, and offline exports; remaining governance work centers on long-term retention policies",
            },
            {
                "key": "operations_readiness",
                "name": "Operational Readiness",
                "score": operations_score,
                "status": self._status_from_score(operations_score),
                "summary": "Current focus: maintenance, alert channel integration, and data governance",
            },
            {
                "key": "goal_alignment",
                "name": "Goal Attainment",
                "score": goal_score,
                "status": self._status_from_score(goal_score),
                "summary": "The main production gaps are now alert channel integration and environment governance, rather than missing core features",
            },
        ]

    def _build_recommendations(
        self,
        chatops: Dict[str, Any],
        db_observability: Dict[str, Any],
        maintenance: Dict[str, Any],
    ) -> List[str]:
        notification = maintenance.get("notification") or {}
        data_quality = maintenance.get("data_quality") or {}
        recommendations: List[str] = []
        if not bool(notification.get("ready")):
            recommendations.append("Connect at least one production alert Webhook so maintenance failures and risk alerts reach the notification channel.")
        elif not bool(chatops.get("ready")):
            if not bool(chatops.get("callback_url_public", True)):
                recommendations.append("Set PUBLIC_API_BASE_URL to a public URL reachable by the notification provider, then complete event subscription in its developer console.")
            elif bool((chatops.get("callback_probe") or {}).get("attempted")) and not bool((chatops.get("callback_probe") or {}).get("success")):
                recommendations.append(
                    "Restore public callback reachability before completing event subscription in the notification provider's developer console; "
                    + (
                        "real group-message delivery was previously verified, but the current public endpoint has degraded."
                        if bool(chatops.get("external_connection_stale"))
                        else "the tunnel or public endpoint is not yet stable."
                    )
                )
            elif not bool(chatops.get("verification_token_configured")):
                recommendations.append("Generate a verification token and run the challenge self-check in the platform, then configure event subscription in the notification provider's developer console.")
            elif not bool(chatops.get("platform_ready")):
                recommendations.append("Complete the platform challenge self-check, then send a test message from the notification provider's developer console to complete the bidirectional group command channel.")
            elif bool(chatops.get("platform_ready")):
                recommendations.append("Copy the platform-generated verification token and callback URL into the notification provider's developer console, then send a test message to verify inbound delivery.")
            else:
                recommendations.append("Run a bidirectional notification channel self-check in the platform, then send a test message in the group to complete real integration testing.")
        if int(db_observability.get("shadow_count") or 0) > 0:
            recommendations.append("Clean up the shadow business database at D:\\workspace\\ai_test_platform\\data\\business.db to prevent an old instance from starting in the wrong directory.")
        if int(data_quality.get("archived_history_count") or 0) > 0 and not bool(data_quality.get("archive_export_fresh", False)):
            recommendations.append("Define offline export or retention policies for archived maintenance history to reduce long-term noise in the operational database.")
        if bool(data_quality.get("archive_cleanup_needed", False)):
            recommendations.append("Run archive retention cleanup to remove records and historical export files beyond the retention period.")
        if maintenance.get("status") == "failed":
            recommendations.append("Resolve the latest maintenance failure first to avoid new unrecoverable breaks in the primary maintenance workflow.")
        if not recommendations:
            recommendations.append("Readiness is relatively stable. Next, connect alerting, releases, and environment governance into a standard operational workflow.")
        return recommendations

    def evaluate(self) -> Dict[str, Any]:
        maintenance = get_platform_maintenance_service().get_status()
        chatops = get_commander_chatops_service().get_overview(allow_live_probe=False)
        db_observability = get_db_observability()
        execution_groups = self._safe_count("execution_groups")
        test_runs = self._safe_count("test_runs")

        local_sections = self._build_local_sections(
            maintenance=maintenance,
            chatops=chatops,
            db_observability=db_observability,
            execution_groups=execution_groups,
            test_runs=test_runs,
        )
        global_sections = self._build_global_sections(
            local_sections=local_sections,
            chatops=chatops,
            db_observability=db_observability,
            maintenance=maintenance,
        )

        local_score = round(sum(section["score"] for section in local_sections) / max(len(local_sections), 1))
        global_score = round(sum(section["score"] for section in global_sections) / max(len(global_sections), 1))
        overall_score = round((local_score * 0.55) + (global_score * 0.45))

        stage = "production-ready" if overall_score >= 90 else "pre-production" if overall_score >= 75 else "beta"
        if not bool((maintenance.get("notification") or {}).get("ready")) and stage == "production-ready":
            stage = "pre-production"
        if int(db_observability.get("shadow_count") or 0) > 0 and stage == "production-ready":
            stage = "pre-production"

        summary = (
            "Core capabilities have reached a preproduction stage, with alerting and environment governance still the main constraints."
            if stage == "pre-production"
            else "The platform has usable Beta capabilities; the main remaining gaps are operational governance."
            if stage == "beta"
            else "The platform is close to the production operating baseline."
        )

        return {
            "stage": stage,
            "score": overall_score,
            "local_score": local_score,
            "global_score": global_score,
            "summary": summary,
            "computed_at": datetime.now().isoformat(),
            "local": local_sections,
            "global": global_sections,
            "recommendations": self._build_recommendations(
                chatops=chatops,
                db_observability=db_observability,
                maintenance=maintenance,
            ),
        }


_service: Optional[PlatformReadinessService] = None


def get_platform_readiness_service() -> PlatformReadinessService:
    global _service
    if _service is None:
        _service = PlatformReadinessService()
    return _service
