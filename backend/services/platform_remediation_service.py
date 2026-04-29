# -*- coding: utf-8 -*-
"""
Platform Remediation Service

将 readiness 的静态评估进一步收敛成“可执行行动项”，
让控制中心不仅能看见问题，还能明确知道下一步该做什么。
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
                    title="接出生产告警 Webhook",
                    scope="local",
                    priority="P0",
                    blocking=True,
                    route="/notifications",
                    summary="当前没有 production-ready 的健康告警通道，维护失败和风险预警还无法稳定进入通知链路。",
                    impact="会直接削弱平台的生产运维闭环，问题发生时只能依赖人工盯盘。",
                    next_step="进入通知配置页，新增或启用至少 1 个生产可达 Webhook，并执行测试或演练，确认最近测试返回 200。",
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
                    title="补齐通知平台事件订阅",
                    scope="local",
                    priority="P1",
                    blocking=False,
                    route="/notifications",
                    summary="通知平台回推通道已经健康，但双向群聊指令链路还未完全就绪。",
                    impact="当前可以把平台通知推到通知平台群，但群里直接发指令还不能稳定回流到平台触发执行。",
                    next_step=(
                        "先在通知配置页执行一次“验证应用机器人”，确认当前 App ID / Secret 能成功获取 tenant_access_token，再继续联调事件订阅。"
                        if app_bot_configured and not app_bot_ready
                        else (
                            "当前平台公网自测已经通过；下一步请在通知平台开放平台启用事件订阅，"
                            "将当前回调地址和 verification token 配进去，把应用机器人加入目标群，"
                            "然后在群里发送一条“状态”完成首次真实联调。"
                        )
                        if platform_ready and external_callback_ready and external_self_check_recent_success
                        else
                        "先把 PUBLIC_API_BASE_URL 配成通知平台可访问的公网地址或挂一条公网隧道，再去通知平台开发者后台配置事件订阅。"
                        if not callback_url_public
                        else (
                            "平台历史上已验证过一次真实通知平台群消息回流，但当前公网入口已退化；请先修复当前公网回调地址的外部可达性，再去通知平台开发者后台配置事件订阅。"
                            if external_connection_stale
                            else "先修复当前公网回调地址的外部可达性，再去通知平台开发者后台配置事件订阅。"
                        )
                        if bool(callback_probe.get("attempted")) and not callback_probe_success
                        else "先在平台内生成 verification token 并执行 challenge 自检，再去通知平台开发者后台完成事件订阅配置。"
                        if not verification_token_configured
                        else "先在平台内完成 challenge 自检，再去通知平台开发者后台发送一条测试文本消息。"
                        if not platform_ready
                        else "在通知平台开发者后台把事件订阅 URL 指向 /api/commander/notification_platform/events，"
                        "并把平台里生成的 verification token 配进去，然后发送一条测试文本消息。"
                        if platform_ready
                        else "先在平台内完成 challenge 自检，再去通知平台开发者后台发送一条测试文本消息。"
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
                    title="治理影子业务库",
                    scope="local",
                    priority="P0",
                    blocking=True,
                    route="",
                    summary="当前工作区仍存在影子业务库文件，错误目录启动旧实例时仍可能写入非权威数据。",
                    impact="会干扰业务库一致性、维护判断和运维排障，属于生产级收口前必须处理的问题。",
                    next_step="确认当前权威业务库后，清理或隔离影子库路径，并避免从错误目录启动旧实例。",
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
                    title="收敛已归档维护历史",
                    scope="global",
                    priority="P1",
                    blocking=False,
                    route="",
                    summary="平台已经把可疑维护历史归档，但归档后的长期保留和离线导出策略仍未形成固定规范。",
                    impact="短期不阻塞使用，但会持续增加运行库噪声和后续治理成本。",
                    next_step="补一份归档数据保留策略，必要时增加离线导出或定期清理机制。",
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
                    title="执行归档保留清理",
                    scope="global",
                    priority="P1",
                    blocking=False,
                    route="/",
                    summary="当前存在已超出保留周期的归档维护记录或历史导出文件，归档生命周期还需要一次清理动作。",
                    impact="短期不会影响主功能，但会增加运行数据库和导出目录的长期噪声。",
                    next_step="先做一次 dry-run 检查，再按保留策略清理过期归档记录和旧导出文件。",
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
                    title="推进到生产级运行基线",
                    scope="global",
                    priority="P1",
                    blocking=False,
                    route="/",
                    summary="平台主能力已经进入准生产阶段，但仍未达到 production-ready。",
                    impact="意味着当前更适合 Beta/准生产场景，距离稳定长期托底还差最后一段治理收口。",
                    next_step="优先完成告警接出和环境治理，再继续推进发布基线与运维审计规范化。",
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
            "summary": "当前存在需要继续推进的生产化行动项。" if tasks else "当前未发现新的生产化阻塞行动项。",
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
