# -*- coding: utf-8 -*-
"""
平台信息路由 - 平台信息、健康检查、指标、API 文档、环境验证
"""
import datetime
from fastapi import APIRouter, HTTPException
from core.app_meta import APP_VERSION
from core.db_helper import get_db_observability, quarantine_shadow_databases
from core.env_validator import get_validator
from core.api_doc_generator import ApiDocGenerator
from core.models import (
    MaintenanceArchiveExportRequest,
    MaintenanceArchiveCleanupRequest,
    MaintenanceArchiveRequest,
    MaintenanceRunRequest,
    ShadowDbQuarantineRequest,
)
from services.platform_maintenance_service import get_platform_maintenance_service
from services.commander_chatops_service import get_commander_chatops_service
from services.platform_remediation_service import get_platform_remediation_service
from services.platform_readiness_service import get_platform_readiness_service

router = APIRouter(tags=["Platform"])

# 需要在 main.py 中调用 setup_platform_routes(app) 来注入 app 引用
_app_ref = None


def setup_platform_routes(app):
    """注入 FastAPI app 引用，用于文档生成和端点列表"""
    global _app_ref
    _app_ref = app


def _platform_version() -> str:
    app = _app_ref
    return str(getattr(app, "version", "") or APP_VERSION)


@router.get("/api/platform/info")
async def get_platform_info():
    """获取平台信息"""
    service = get_platform_maintenance_service()
    maintenance = service.get_status()
    db_observability = get_db_observability()
    notification = maintenance.get("notification") or {}
    data_quality = maintenance.get("data_quality") or {}
    chatops = get_commander_chatops_service().get_overview(allow_live_probe=False)
    readiness = get_platform_readiness_service().evaluate()
    return {
        "name": "AI Test Platform",
        "version": _platform_version(),
        "features": [
            "UI E2E Testing",
            "API Testing (REST/GraphQL)",
            "Performance Testing",
            "Security Scanning",
            "Database Testing",
            "WebSocket Testing",
            "CI/CD Integration",
            "AI Strategy Selection",
            "Self-Healing",
            "Knowledge Base",
            "User Authentication",
            "Project Isolation",
            "Audit Logging",
            "Platform Maintenance"
        ],
        "ai_capabilities": {
            "strategy_selection": True,
            "self_healing": True,
            "knowledge_learning": True,
            "root_cause_analysis": True,
            "requirement_parsing": True
        },
        "operations": {
            "auto_maintenance": True,
            "maintenance_status": maintenance.get("status", "never"),
            "last_maintenance_reason": maintenance.get("reason", ""),
            "business_db_path": db_observability["path"],
            "business_db_exists": db_observability["current_db"]["exists"],
            "business_db_size_bytes": db_observability["current_db"]["size_bytes"],
            "business_db_updated_at": db_observability["current_db"]["updated_at"],
            "shadow_business_dbs": db_observability["shadow_paths"],
            "shadow_business_db_count": db_observability["shadow_count"],
            "business_db_risk_level": db_observability["risk_level"],
            "notification_webhook_count": int(notification.get("webhook_count") or 0),
            "notification_tested_webhook_count": int(notification.get("tested_enabled") or 0),
            "notification_healthy_webhook_count": int(notification.get("healthy_enabled") or 0),
            "notification_untested_webhook_count": int(notification.get("untested_enabled") or 0),
            "notification_ready": bool(notification.get("ready")),
            "notification_summary": str(notification.get("summary") or ""),
            "commander_chatops_ready": bool(chatops.get("ready")),
            "commander_chatops_platform_ready": bool(chatops.get("platform_ready")),
            "commander_chatops_webhook_ready": bool(chatops.get("webhook_ready")),
            "commander_chatops_external_connected": bool(chatops.get("external_connected")),
            "commander_chatops_external_connected_current": bool(chatops.get("external_connected_current", chatops.get("external_connected"))),
            "commander_chatops_external_connected_history_observed": bool(chatops.get("external_connected_history_observed")),
            "commander_chatops_external_connection_stale": bool(chatops.get("external_connection_stale")),
            "commander_chatops_external_callback_ready": bool(chatops.get("external_callback_ready")),
            "commander_chatops_external_self_check_recent_success": bool(chatops.get("external_self_check_recent_success")),
            "commander_chatops_direct_chat_ready": bool(chatops.get("direct_chat_ready")),
            "commander_chatops_app_bot_configured": bool(chatops.get("app_bot_configured")),
            "commander_chatops_app_bot_ready": bool(chatops.get("app_bot_ready")),
            "commander_chatops_app_bot_id_masked": str(chatops.get("app_bot_id_masked") or ""),
            "commander_chatops_app_bot_updated_at": str(chatops.get("app_bot_updated_at") or ""),
            "commander_chatops_app_bot_check": chatops.get("app_bot_check") or {},
            "commander_chatops_unified_robot_target": bool(chatops.get("unified_robot_target")),
            "commander_chatops_unified_robot_platform_ready": bool(chatops.get("unified_robot_platform_ready")),
            "commander_chatops_unified_robot_ready": bool(chatops.get("unified_robot_ready")),
            "commander_chatops_delivery_strategy": str(chatops.get("delivery_strategy") or ""),
            "commander_chatops_delivery_strategy_summary": str(chatops.get("delivery_strategy_summary") or ""),
            "commander_chatops_subscription_endpoint_verified": bool(chatops.get("subscription_endpoint_verified")),
            "commander_chatops_verification_token_configured": bool(chatops.get("verification_token_configured")),
            "commander_chatops_verification_token_masked": str(chatops.get("verification_token_masked") or ""),
            "commander_chatops_verification_token_updated_at": str(chatops.get("verification_token_updated_at") or ""),
            "commander_chatops_callback_url": str(chatops.get("callback_url") or ""),
            "commander_chatops_callback_url_public": bool(chatops.get("callback_url_public", False)),
            "commander_chatops_callback_provider": chatops.get("callback_provider") or {},
            "commander_chatops_callback_recommendation": str(chatops.get("callback_recommendation") or ""),
            "commander_chatops_callback_probe_attempted": bool((chatops.get("callback_probe") or {}).get("attempted")),
            "commander_chatops_callback_probe_success": bool((chatops.get("callback_probe") or {}).get("success")),
            "commander_chatops_callback_probe_issue": str((chatops.get("callback_probe") or {}).get("issue") or ""),
            "commander_chatops_callback_probe_summary": str((chatops.get("callback_probe") or {}).get("summary") or ""),
            "commander_chatops_callback_probe_status_code": (chatops.get("callback_probe") or {}).get("status_code"),
            "commander_chatops_callback_probe_content_type": str((chatops.get("callback_probe") or {}).get("content_type") or ""),
            "commander_chatops_callback_probe_probed_at": str((chatops.get("callback_probe") or {}).get("probed_at") or ""),
            "commander_chatops_summary": str(chatops.get("summary") or ""),
            "commander_chatops_recent_event_at": str((chatops.get("latest_event") or {}).get("created_at") or ""),
            "commander_chatops_recent_success_at": str((chatops.get("latest_successful_event") or {}).get("created_at") or ""),
            "commander_chatops_latest_external_success_at": str(chatops.get("latest_external_success_at") or ""),
            "commander_chatops_latest_external_self_check_at": str(chatops.get("latest_external_self_check_at") or ""),
            "commander_chatops_recent_delivery_count": int((chatops.get("latest_event") or {}).get("delivery_delivered") or 0),
            "maintenance_suspect_history_count": int(data_quality.get("suspect_history_count") or 0),
            "maintenance_archived_history_count": int(data_quality.get("archived_history_count") or 0),
            "maintenance_archive_export_count": int(data_quality.get("archive_export_count") or 0),
            "maintenance_last_archive_export_at": str(data_quality.get("last_archive_export_at") or ""),
            "maintenance_last_archive_export_reason": str(data_quality.get("last_archive_export_reason") or ""),
            "maintenance_last_archive_export_path": str(data_quality.get("last_archive_export_path") or ""),
            "maintenance_last_archive_export_format": str(data_quality.get("last_archive_export_format") or ""),
            "maintenance_archive_export_fresh": bool(data_quality.get("archive_export_fresh", True)),
            "maintenance_archive_retention_days": int(data_quality.get("archive_retention_days") or 0),
            "maintenance_archive_cleanup_needed": bool(data_quality.get("archive_cleanup_needed", False)),
            "maintenance_archive_cleanup_candidate_count": int(data_quality.get("archive_cleanup_candidate_count") or 0),
            "maintenance_archive_run_cleanup_candidates": int(data_quality.get("archive_run_cleanup_candidates") or 0),
            "maintenance_archive_export_cleanup_candidates": int(data_quality.get("archive_export_cleanup_candidates") or 0),
            "maintenance_last_archive_cleanup_at": str(data_quality.get("last_archive_cleanup_at") or ""),
            "maintenance_last_archive_cleanup_reason": str(data_quality.get("last_archive_cleanup_reason") or ""),
            "maintenance_last_archive_cleanup_dry_run": bool(data_quality.get("last_archive_cleanup_dry_run", True)),
            "maintenance_last_archive_cleanup_deleted_runs": int(data_quality.get("last_archive_cleanup_deleted_runs") or 0),
            "maintenance_last_archive_cleanup_deleted_exports": int(data_quality.get("last_archive_cleanup_deleted_exports") or 0),
            "maintenance_history_clean": bool(data_quality.get("clean", True)),
            "maintenance_history_summary": str(data_quality.get("summary") or ""),
            "readiness_stage": readiness.get("stage"),
            "readiness_score": readiness.get("score"),
            "readiness_summary": readiness.get("summary"),
        },
    }


@router.get("/api/platform/capabilities")
async def get_platform_capabilities():
    """获取平台能力清单"""
    return {
        "version": _platform_version(),
        "test_types": [
            "ui_e2e", "rest_api", "graphql", "websocket", "grpc",
            "performance", "security", "database", "contract", "exploratory"
        ],
        "ai_features": [
            "intelligent_strategy_selection", "self_healing",
            "knowledge_learning", "requirement_parsing",
            "test_case_generation", "root_cause_analysis"
        ],
        "enterprise_features": [
            "user_authentication", "project_isolation",
            "audit_logging", "role_based_access"
        ],
        "integrations": [
            "cicd_webhook", "allure_reporting",
            "junit_export", "api_documentation"
        ],
        "ai_automation_rate": "95%",
        "commercial_readiness": "beta",
        "readiness_snapshot": get_platform_readiness_service().evaluate(),
        "production_readiness": {
            "execution_center_grouping": True,
            "batch_reporting": True,
            "auto_maintenance": True,
            "maintenance_audit": True,
            "notification_platform_chatops_platform_ready": bool(get_commander_chatops_service().get_overview(allow_live_probe=False).get("platform_ready")),
            "notification_platform_chatops_bridge": bool(get_commander_chatops_service().get_overview(allow_live_probe=False).get("ready")),
        },
    }


@router.get("/api/platform/maintenance")
async def get_platform_maintenance(
    limit: int = 20,
    include_suspect: bool = False,
    include_archived: bool = False,
):
    """获取平台维护状态与最近执行记录"""
    service = get_platform_maintenance_service()
    return {
        "status": "success",
        "current": service.get_status(),
        "latest_activity": service.get_latest_activity(),
        "history": service.list_runs(
            limit=limit,
            include_suspect=include_suspect,
            include_archived=include_archived,
        ),
    }


@router.post("/api/platform/maintenance/run")
async def run_platform_maintenance(payload: MaintenanceRunRequest):
    """手动触发平台统一维护"""
    service = get_platform_maintenance_service()
    result = service.run(force=payload.force, reason=payload.reason or "manual")
    return {"status": "success", "result": result}


@router.post("/api/platform/maintenance/archive-suspect")
async def archive_suspect_platform_maintenance(payload: MaintenanceArchiveRequest):
    """归档可疑维护历史（非破坏性）"""
    service = get_platform_maintenance_service()
    result = service.archive_suspect_runs(
        reason=payload.reason or "ops_archive",
        limit=max(int(payload.limit or 0), 0),
    )
    return {"status": "success", "result": result}


@router.post("/api/platform/maintenance/export-archive")
async def export_archived_platform_maintenance(payload: MaintenanceArchiveExportRequest):
    """导出已归档的维护历史，便于离线留存与审计。"""
    service = get_platform_maintenance_service()
    try:
        result = service.export_archived_runs(
            reason=payload.reason or "ops_export_archive",
            export_format=payload.format or "json",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "success", "result": result}


@router.post("/api/platform/maintenance/cleanup-archive")
async def cleanup_archived_platform_maintenance(payload: MaintenanceArchiveCleanupRequest):
    """按保留策略 dry-run 或清理过期归档维护历史。"""
    service = get_platform_maintenance_service()
    result = service.cleanup_archive_retention(
        reason=payload.reason or "ops_cleanup_archive",
        retention_days=max(int(payload.retention_days or 0), 0),
        dry_run=bool(payload.dry_run),
    )
    return {"status": "success", "result": result}


@router.post("/api/platform/shadow-db/quarantine")
async def quarantine_platform_shadow_dbs(payload: ShadowDbQuarantineRequest):
    """隔离影子业务库到归档目录（非破坏性）。"""
    result = quarantine_shadow_databases(reason=payload.reason or "ops_quarantine")
    return {"status": "success", "result": result}


@router.get("/api/platform/readiness")
async def get_platform_readiness():
    """获取平台局部/全局就绪度评估"""
    return {
        "status": "success",
        "readiness": get_platform_readiness_service().evaluate(),
    }


@router.get("/api/platform/remediation")
async def get_platform_remediation():
    """获取平台生产推进行动项"""
    return {
        "status": "success",
        "remediation": get_platform_remediation_service().evaluate(),
    }


# NOTE: /api/health 保留在 main.py (含 DB 可达性检查)


@router.get("/api/metrics")
async def get_metrics():
    """获取平台指标"""
    import psutil

    app = _app_ref
    total_endpoints = len([r for r in app.routes if hasattr(r, 'path')]) if app else 0

    return {
        "status": "success",
        "metrics": {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "total_endpoints": total_endpoints
        }
    }


@router.get("/api/docs/generate")
async def generate_api_documentation(format: str = "json"):
    """生成 API 文档"""
    generator = ApiDocGenerator()
    if _app_ref:
        generator.extract_from_fastapi(_app_ref)

    if format == "markdown":
        content = generator.generate_markdown("AI Test Platform API")
        return {"status": "success", "format": "markdown", "content": content}
    else:
        openapi = generator.generate_openapi("AI Test Platform API", "2.1.0")
        return {"status": "success", "format": "openapi", "content": openapi}


@router.get("/api/docs/endpoints")
async def list_all_endpoints():
    """列出所有 API 端点"""
    app = _app_ref
    endpoints = []
    if app:
        for route in app.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                for method in route.methods:
                    if method not in ['HEAD', 'OPTIONS']:
                        doc = route.endpoint.__doc__ if hasattr(route, 'endpoint') and route.endpoint else ""
                        endpoints.append({
                            "path": route.path,
                            "method": method,
                            "summary": doc.split('\n')[0] if doc else ""
                        })

    return {
        "status": "success",
        "total": len(endpoints),
        "endpoints": sorted(endpoints, key=lambda x: x["path"])
    }


@router.get("/api/environment/validate")
async def validate_environment():
    """验证执行环境"""
    validator = get_validator()
    result = await validator.validate_all()
    return result
