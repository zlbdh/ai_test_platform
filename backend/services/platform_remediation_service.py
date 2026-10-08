# -*- coding: utf-8 -*-
"""
Platform Remediation Service

Turn static readiness assessments into actionable items
so the control center identifies both problems and the next steps to address them.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from core.db_helper import get_db_observability
from services.commander_chatops_service import get_commander_chatops_service
from services.platform_maintenance_service import get_platform_maintenance_service
from services.platform_readiness_service import get_platform_readiness_service


class PlatformRemediationService:
    def _task(
        self,
        *,
        key: str,
        title: str,
        scope: str,
        priority: str,
        blocking: bool,
        route: str,
        summary: str,
        impact: str,
        next_step: str,
        evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "key": key,
            "title": title,
            "scope": scope,
            "priority": priority,
            "blocking": blocking,
            "status": "open",
            "route": route,
            "summary": summary,
            "impact": impact,
            "next_step": next_step,
            "evidence": evidence,
        }

    def evaluate(self) -> Dict[str, Any]:
        maintenance = get_platform_maintenance_service().get_status()
        chatops = get_commander_chatops_service().get_overview(allow_live_probe=False)
        readiness = get_platform_readiness_service().evaluate()
        db_observability = get_db_observability()

        notification = maintenance.get("notification") or {}
        data_quality = maintenance.get("data_quality") or {}
        risk = maintenance.get("risk") or {}

        tasks: List[Dict[str, Any]] = []

        if not bool(notification.get("ready")):
            tasks.append(
                self._task(
                    key="notification_webhook",
                    title="Connect a production alert Webhook",
                    scope="local",
                    priority="P0",
                    blocking=True,
                    route="/notifications",
                    summary="No healthy production-ready alert channel is available, so maintenance failures and risk alerts cannot reliably reach notifications.",
                    impact="This weakens production operations and leaves incident detection dependent on manual monitoring.",
                    next_step="In notification settings, add or enable at least one production-reachable Webhook and run a test or drill. Confirm that the latest test returns HTTP 200.",
                    evidence={
                        "webhook_count": int(notification.get("webhook_count") or 0),
                        "tested_enabled": int(notification.get("tested_enabled") or 0),
                        "healthy_enabled": int(notification.get("healthy_enabled") or 0),
                        "untested_enabled": int(notification.get("untested_enabled") or 0),
                        "ready": bool(notification.get("ready")),
                        "summary": str(notification.get("summary") or ""),
                    },
                )
            )

        if bool(notification.get("ready")) and not bool(chatops.get("ready")):
            platform_ready = bool(chatops.get("platform_ready"))
            verification_token_configured = bool(chatops.get("verification_token_configured"))
            callback_url_public = bool(chatops.get("callback_url_public", True))
            external_connection_stale = bool(chatops.get("external_connection_stale"))
            external_self_check_recent_success = bool(chatops.get("external_self_check_recent_success"))
            external_callback_ready = bool(chatops.get("external_callback_ready"))
            app_bot_configured = bool(chatops.get("app_bot_configured"))
            app_bot_ready = bool(chatops.get("app_bot_ready"))
            callback_probe = chatops.get("callback_probe") or {}
            callback_probe_success = bool(callback_probe.get("success"))
            tasks.append(
                self._task(
                    key="notification_platform_chatops_subscription",
                    title="Complete notification event subscription",
                    scope="local",
                    priority="P1",
                    blocking=False,
                    route="/notifications",
                    summary="The notification reply channel is healthy, but the bidirectional group command channel is not fully ready.",
                    impact="The platform can send notifications to groups, but commands sent in a group cannot yet reliably return to the platform and trigger execution.",
                    next_step=(
                        "Run \"Verify app bot\" in notification settings and confirm that the App ID / Secret can obtain tenant_access_token before continuing event subscription integration."
                        if app_bot_configured and not app_bot_ready
                        else (
                            "The platform public endpoint self-test passed. Enable event subscription in the notification provider's developer console, "
                            "configure the current callback URL and verification token, add the app bot to the target group, "
                            "then send \"status\" in the group to complete the first real integration test."
                        )
                        if platform_ready and external_callback_ready and external_self_check_recent_success
                        else
                        "Set PUBLIC_API_BASE_URL to a provider-reachable public URL or establish a public tunnel, then configure event subscription in the notification provider's developer console."
                        if not callback_url_public
                        else (
                            "Real notification group-message delivery was previously verified, but the public endpoint has degraded. Restore callback reachability before configuring event subscription in the provider's developer console."
                            if external_connection_stale
                            else "Restore public callback reachability, then configure event subscription in the notification provider's developer console."
                        )
                        if bool(callback_probe.get("attempted")) and not callback_probe_success
                        else "Generate a verification token and run the platform challenge self-check, then complete event subscription in the notification provider's developer console."
                        if not verification_token_configured
                        else "Complete the platform challenge self-check, then send a test text message from the notification provider's developer console."
                        if not platform_ready
                        else "In the notification provider's developer console, set the event subscription URL to /api/commander/notification_platform/events, "
                        "configure the platform-generated verification token, then send a test text message."
                        if platform_ready
                        else "Complete the platform challenge self-check, then send a test text message from the notification provider's developer console."
                    ),
                    evidence={
                        "webhook_ready": bool(chatops.get("webhook_ready")),
                        "verification_token_configured": bool(chatops.get("verification_token_configured")),
                        "platform_ready": platform_ready,
                        "callback_url": str(chatops.get("callback_url") or ""),
                        "callback_url_public": callback_url_public,
                        "callback_probe_attempted": bool(callback_probe.get("attempted")),
                        "callback_probe_success": callback_probe_success,
                        "callback_probe_issue": str(callback_probe.get("issue") or ""),
                        "callback_probe_summary": str(callback_probe.get("summary") or ""),
                        "external_connection_stale": external_connection_stale,
                        "external_callback_ready": external_callback_ready,
                        "external_self_check_recent_success": external_self_check_recent_success,
                        "external_connected_history_observed": bool(chatops.get("external_connected_history_observed")),
                        "latest_external_success_at": str(chatops.get("latest_external_success_at") or ""),
                        "app_bot_configured": app_bot_configured,
                        "app_bot_ready": app_bot_ready,
                        "app_bot_check": chatops.get("app_bot_check") or {},
                        "app_bot_id_masked": str(chatops.get("app_bot_id_masked") or ""),
                        "external_connected": bool(chatops.get("external_connected")),
                        "subscription_endpoint_verified": bool(chatops.get("subscription_endpoint_verified")),
                        "verification_token_updated_at": str(chatops.get("verification_token_updated_at") or ""),
                        "healthy_notification_platform_webhook_count": int(chatops.get("healthy_notification_platform_webhook_count") or 0),
                        "summary": str(chatops.get("summary") or ""),
                    },
                )
            )

        if int(db_observability.get("shadow_count") or 0) > 0:
            tasks.append(
                self._task(
                    key="shadow_business_db",
                    title="Resolve shadow business databases",
                    scope="local",
                    priority="P0",
                    blocking=True,
                    route="",
                    summary="Shadow business database files remain in the workspace. Starting an old instance in the wrong directory can still write to a nonauthoritative database.",
                    impact="This undermines database consistency, maintenance assessment, and troubleshooting and must be resolved before production readiness.",
                    next_step="Confirm the authoritative business database, then remove or isolate shadow database paths and avoid starting old instances from the wrong directory.",
                    evidence={
                        "current_db_path": str(db_observability.get("path") or ""),
                        "shadow_count": int(db_observability.get("shadow_count") or 0),
                        "shadow_paths": [str(item) for item in (db_observability.get("shadow_paths") or [])],
                    },
                )
            )

        if int(data_quality.get("archived_history_count") or 0) > 0 and not bool(data_quality.get("archive_export_fresh", False)):
            tasks.append(
                self._task(
                    key="archived_history_governance",
                    title="Manage archived maintenance history",
                    scope="global",
                    priority="P1",
                    blocking=False,
                    route="",
                    summary="Suspicious maintenance history has been archived, but long-term retention and offline export policies are not standardized yet.",
                    impact="This does not block short-term use, but it increases operational database noise and future governance costs.",
                    next_step="Define an archive retention policy and add offline exports or periodic cleanup where needed.",
                    evidence={
                        "archived_history_count": int(data_quality.get("archived_history_count") or 0),
                        "archive_export_count": int(data_quality.get("archive_export_count") or 0),
                        "last_archive_export_at": str(data_quality.get("last_archive_export_at") or ""),
                        "archive_export_fresh": bool(data_quality.get("archive_export_fresh", False)),
                        "summary": str(data_quality.get("summary") or ""),
                    },
                )
            )

        if bool(data_quality.get("archive_cleanup_needed", False)):
            tasks.append(
                self._task(
                    key="archive_retention_cleanup",
                    title="Run archive retention cleanup",
                    scope="global",
                    priority="P1",
                    blocking=False,
                    route="/",
                    summary="Archived maintenance records or historical exports exceed the retention period; the archive lifecycle needs cleanup.",
                    impact="This does not affect core features immediately, but it increases long-term noise in the operational database and export directory.",
                    next_step="Run a dry-run check first, then remove expired archive records and old exports according to the retention policy.",
                    evidence={
                        "archive_cleanup_candidate_count": int(data_quality.get("archive_cleanup_candidate_count") or 0),
                        "archive_run_cleanup_candidates": int(data_quality.get("archive_run_cleanup_candidates") or 0),
                        "archive_export_cleanup_candidates": int(data_quality.get("archive_export_cleanup_candidates") or 0),
                        "archive_retention_days": int(data_quality.get("archive_retention_days") or 0),
                        "summary": str(data_quality.get("summary") or ""),
                    },
                )
            )

        if str(readiness.get("stage") or "") != "production-ready":
            tasks.append(
                self._task(
                    key="production_readiness_gap",
                    title="Reach the production operating baseline",
                    scope="global",
                    priority="P1",
                    blocking=False,
                    route="/",
                    summary="Core platform capabilities are in preproduction, but the platform is not yet production-ready.",
                    impact="The platform currently suits Beta or preproduction use; further governance work is needed for stable long-term operation.",
                    next_step="Complete alert channel integration and environment governance first, then standardize the release baseline and operational audits.",
                    evidence={
                        "stage": str(readiness.get("stage") or ""),
                        "score": int(readiness.get("score") or 0),
                        "summary": str(readiness.get("summary") or ""),
                    },
                )
            )

        tasks.sort(key=lambda item: (0 if item["priority"] == "P0" else 1, 0 if item["scope"] == "local" else 1))

        return {
            "computed_at": datetime.now().isoformat(),
            "status": "attention" if tasks else "stable",
            "summary": "Production-readiness action items remain." if tasks else "No new production-readiness blockers were found.",
            "counts": {
                "total": len(tasks),
                "blocking": sum(1 for item in tasks if item["blocking"]),
                "local": sum(1 for item in tasks if item["scope"] == "local"),
                "global": sum(1 for item in tasks if item["scope"] == "global"),
                "p0": sum(1 for item in tasks if item["priority"] == "P0"),
                "p1": sum(1 for item in tasks if item["priority"] == "P1"),
            },
            "items": tasks,
            "risk": {
                "shadow_count": int(risk.get("shadow_count") or db_observability.get("shadow_count") or 0),
                "notification_ready": bool(notification.get("ready")),
                "readiness_stage": str(readiness.get("stage") or ""),
            },
        }


_service: Optional[PlatformRemediationService] = None


def get_platform_remediation_service() -> PlatformRemediationService:
    global _service
    if _service is None:
        _service = PlatformRemediationService()
    return _service
