# -*- coding: utf-8 -*-
"""
Platform Readiness Service

从局部（模块/功能）和全局（架构/目标/总设计）两个视角，
统一评估平台当前的生产推进状态。
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
                "name": "维护模块",
                "score": maintenance_score,
                "status": self._status_from_score(maintenance_score),
                "summary": f"当前状态 {maintenance_status}，最近原因 {maintenance.get('reason') or '未执行'}",
            },
            {
                "key": "notification_module",
                "name": "告警模块",
                "score": notification_score,
                "status": self._status_from_score(notification_score),
                "summary": str(notification.get("summary") or "尚未接出生产告警通道"),
            },
            {
                "key": "chatops_module",
                "name": "通知平台指令链路",
                "score": chatops_score,
                "status": self._status_from_score(chatops_score),
                "summary": (
                    f"{str(chatops.get('summary') or '通知平台双向指令链路尚未评估')} "
                    f"(平台侧 {'已就绪' if chatops_platform_ready else '待完善'} / "
                    f"公网回调 {'已打通' if chatops_external_callback_ready else '待验证'} / "
                    f"App 凭据 {'已验证' if chatops_app_bot_ready else '已保存待校验' if chatops_app_bot_configured else '未保存'} / "
                    f"群聊直连 {'已联通' if chatops_external_connected else '待验证'} / "
                    f"历史回流 {'已观察' if chatops_external_history_observed else '未观察'}"
                    f"{'（当前已退化）' if chatops_external_connection_stale else ''})"
                ),
            },
            {
                "key": "data_governance_module",
                "name": "数据治理",
                "score": governance_score,
                "status": self._status_from_score(governance_score),
                "summary": (
                    f"影子库 {shadow_count} 个，活动可疑维护历史 {suspect_count} 条，"
                    f"已归档 {archived_count} 条，归档导出 {'已完成' if archive_export_fresh else '待更新'}，"
                    f"超期清理 {'待执行' if archive_cleanup_needed else '正常'}"
                ),
            },
            {
                "key": "execution_center_module",
                "name": "执行闭环",
                "score": execution_score,
                "status": self._status_from_score(execution_score),
                "summary": f"执行批次 {execution_groups} 个，测试记录 {test_runs} 条，报告历史 {report_entries} 条",
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
                "name": "架构稳定性",
                "score": architecture_score,
                "status": self._status_from_score(architecture_score),
                "summary": "核心分层、执行中心、报告和维护主链已成型",
            },
            {
                "key": "delivery_governance",
                "name": "交付治理",
                "score": delivery_score,
                "status": self._status_from_score(delivery_score),
                "summary": "平台已具备批次归档、可疑历史归档与离线导出能力，剩余治理工作集中在长期保留策略收口",
            },
            {
                "key": "operations_readiness",
                "name": "运维就绪度",
                "score": operations_score,
                "status": self._status_from_score(operations_score),
                "summary": "当前聚焦维护、告警接出、数据治理三项核心运维能力",
            },
            {
                "key": "goal_alignment",
                "name": "目标达成度",
                "score": goal_score,
                "status": self._status_from_score(goal_score),
                "summary": "离生产级的主要差距已收敛到告警接出和环境治理，而不是主功能缺失",
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
            recommendations.append("接出至少 1 个生产告警 Webhook，让维护失败和风险预警真正进入通知链路。")
        elif not bool(chatops.get("ready")):
            if not bool(chatops.get("callback_url_public", True)):
                recommendations.append("先把 PUBLIC_API_BASE_URL 配成通知平台可访问的公网地址，再去通知平台开发者后台完成事件订阅。")
            elif bool((chatops.get("callback_probe") or {}).get("attempted")) and not bool((chatops.get("callback_probe") or {}).get("success")):
                recommendations.append(
                    "先修复公网回调地址的外部可达性，再去通知平台开发者后台完成事件订阅；"
                    + (
                        "平台历史上已经验证过真实群消息回流，但当前公网入口已退化。"
                        if bool(chatops.get("external_connection_stale"))
                        else "当前隧道或公网入口仍未稳定可用。"
                    )
                )
            elif not bool(chatops.get("verification_token_configured")):
                recommendations.append("先在平台内生成 verification token，并执行一次 challenge 自检，再去通知平台开发者后台配置事件订阅。")
            elif not bool(chatops.get("platform_ready")):
                recommendations.append("先在平台内完成一次 challenge 自检，再去通知平台开发者后台发送测试消息，补齐双向群聊指令链路。")
            elif bool(chatops.get("platform_ready")):
                recommendations.append("把平台里已生成的 verification token 和回调地址复制到通知平台开发者后台，并发送一条测试消息完成外部回流验证。")
            else:
                recommendations.append("先在平台内完成一次通知平台双向链路自检，再去群里发送一条测试消息，补齐最后的真实联调。")
        if int(db_observability.get("shadow_count") or 0) > 0:
            recommendations.append("清理影子业务库 D:\\workspace\\ai_test_platform\\data\\business.db，避免错误目录启动旧实例。")
        if int(data_quality.get("archived_history_count") or 0) > 0 and not bool(data_quality.get("archive_export_fresh", False)):
            recommendations.append("为已归档的维护历史建立离线导出或保留策略，进一步收敛运行数据库的长期噪声。")
        if bool(data_quality.get("archive_cleanup_needed", False)):
            recommendations.append("执行一次归档保留清理，消化已超出保留周期的归档记录和历史导出文件。")
        if maintenance.get("status") == "failed":
            recommendations.append("优先修复最近一次维护失败原因，避免平台维护主链出现新的不可恢复断点。")
        if not recommendations:
            recommendations.append("当前 readiness 已较稳定，下一步适合把告警、发布和环境治理串成标准运维流程。")
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
            "主能力已收口到准生产阶段，但告警接出与环境治理仍是主要约束。"
            if stage == "pre-production"
            else "平台已具备真实可用的 Beta 能力，核心差距集中在运维治理。"
            if stage == "beta"
            else "平台整体已接近生产级运行基线。"
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
