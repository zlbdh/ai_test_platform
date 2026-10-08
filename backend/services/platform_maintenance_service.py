# -*- coding: utf-8 -*-
"""
Platform Maintenance Service

Central responsibilities:
1. Synchronize external history into the execution center
2. Repair legacy execution-center data artifacts
3. Repair report history titles and reporting conventions
"""
from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from core.allure_reporter import get_reporter
from core.db_helper import get_connection, get_db_observability
from core.notify_helper import send_completion_notification
from services.execution_center_service import get_execution_center_service

logger = logging.getLogger(__name__)
ROUTINE_REASONS = {"history_list", "history_detail", "report_history"}
SUSPECT_PATH_MARKERS = (
    "\\demo\\business.db",
    "\\legacy\\business.db",
    "/demo/business.db",
    "/legacy/business.db",
)
ARCHIVE_EXPORT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "platform_maintenance_exports")
)
DEFAULT_ARCHIVE_RETENTION_DAYS = int(os.getenv("PLATFORM_ARCHIVE_RETENTION_DAYS", "30"))


class PlatformMaintenanceService:
    def __init__(self, min_interval_seconds: Optional[int] = None):
        self._lock = threading.Lock()
        self._min_interval_seconds = int(
            min_interval_seconds
            if min_interval_seconds is not None
            else os.getenv("PLATFORM_MAINTENANCE_INTERVAL_SECONDS", "15")
        )
        self._last_run_monotonic = 0.0
        self._last_result: Dict[str, Any] = {
            "status": "never",
            "reason": "",
            "timestamp": "",
            "duration_ms": 0,
            "skipped": False,
            "alert_sent": False,
            "risk_alert_sent": False,
            "warning_detected": False,
            "sync": {"performance": 0, "security": 0},
            "repair": {"group_updates": 0, "record_updates": 0, "legacy_groups": 0},
            "report_history": {"history_entries": 0, "updated_entries": 0},
            "risk": {"level": "normal", "shadow_count": 0, "summary": ""},
            "notification": {
                "webhook_count": 0,
                "tested_enabled": 0,
                "healthy_enabled": 0,
                "untested_enabled": 0,
                "ready": False,
                "summary": "No active production alert Webhook is configured",
            },
            "data_quality": {
                "suspect_history_count": 0,
                "raw_history_count": 0,
                "archived_history_count": 0,
                "visible_history_count": 0,
                "archive_export_count": 0,
                "last_archive_export_at": "",
                "last_archive_export_reason": "",
                "last_archive_export_path": "",
                "last_archive_export_format": "",
                "archive_export_fresh": True,
                "archive_retention_days": DEFAULT_ARCHIVE_RETENTION_DAYS,
                "archive_cleanup_needed": False,
                "archive_cleanup_candidate_count": 0,
                "archive_run_cleanup_candidates": 0,
                "archive_export_cleanup_candidates": 0,
                "last_archive_cleanup_at": "",
                "last_archive_cleanup_reason": "",
                "last_archive_cleanup_dry_run": True,
                "last_archive_cleanup_deleted_runs": 0,
                "last_archive_cleanup_deleted_exports": 0,
                "clean": True,
                "summary": "Maintenance history is healthy",
            },
        }
        self._last_activity: Dict[str, Any] = {
            "status": "never",
            "reason": "",
            "timestamp": "",
            "duration_ms": 0,
            "skipped": False,
            "alert_sent": False,
            "risk_alert_sent": False,
            "warning_detected": False,
            "sync": {"performance": 0, "security": 0},
            "repair": {"group_updates": 0, "record_updates": 0, "legacy_groups": 0},
            "report_history": {"history_entries": 0, "updated_entries": 0},
            "risk": {"level": "normal", "shadow_count": 0, "summary": ""},
            "notification": {
                "webhook_count": 0,
                "tested_enabled": 0,
                "healthy_enabled": 0,
                "untested_enabled": 0,
                "ready": False,
                "summary": "No active production alert Webhook is configured",
            },
            "data_quality": {
                "suspect_history_count": 0,
                "raw_history_count": 0,
                "archived_history_count": 0,
                "visible_history_count": 0,
                "archive_export_count": 0,
                "last_archive_export_at": "",
                "last_archive_export_reason": "",
                "last_archive_export_path": "",
                "last_archive_export_format": "",
                "archive_export_fresh": True,
                "archive_retention_days": DEFAULT_ARCHIVE_RETENTION_DAYS,
                "archive_cleanup_needed": False,
                "archive_cleanup_candidate_count": 0,
                "archive_run_cleanup_candidates": 0,
                "archive_export_cleanup_candidates": 0,
                "last_archive_cleanup_at": "",
                "last_archive_cleanup_reason": "",
                "last_archive_cleanup_dry_run": True,
                "last_archive_cleanup_deleted_runs": 0,
                "last_archive_cleanup_deleted_exports": 0,
                "clean": True,
                "summary": "Maintenance history is healthy",
            },
        }

    def _is_routine_reason(self, reason: Optional[str]) -> bool:
        return str(reason or "").strip().lower() in ROUTINE_REASONS

    def _get_columns(self, conn, table_name: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row[1]) for row in rows}

    def _ensure_schema(self, conn) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS platform_maintenance_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                duration_ms INTEGER DEFAULT 0,
                sync_json TEXT DEFAULT '{}',
                repair_json TEXT DEFAULT '{}',
                report_history_json TEXT DEFAULT '{}',
                risk_json TEXT DEFAULT '{}',
                skipped INTEGER DEFAULT 0,
                alert_sent INTEGER DEFAULT 0,
                risk_alert_sent INTEGER DEFAULT 0,
                warning_detected INTEGER DEFAULT 0,
                error_message TEXT DEFAULT ''
            )
            """
        )
        existing = self._get_columns(conn, "platform_maintenance_runs")
        if "alert_sent" not in existing:
            conn.execute("ALTER TABLE platform_maintenance_runs ADD COLUMN alert_sent INTEGER DEFAULT 0")
        if "risk_alert_sent" not in existing:
            conn.execute("ALTER TABLE platform_maintenance_runs ADD COLUMN risk_alert_sent INTEGER DEFAULT 0")
        if "warning_detected" not in existing:
            conn.execute("ALTER TABLE platform_maintenance_runs ADD COLUMN warning_detected INTEGER DEFAULT 0")
        if "risk_json" not in existing:
            conn.execute("ALTER TABLE platform_maintenance_runs ADD COLUMN risk_json TEXT DEFAULT '{}'")
        if "archived" not in existing:
            conn.execute("ALTER TABLE platform_maintenance_runs ADD COLUMN archived INTEGER DEFAULT 0")
        if "archived_at" not in existing:
            conn.execute("ALTER TABLE platform_maintenance_runs ADD COLUMN archived_at TEXT DEFAULT ''")
        if "archive_reason" not in existing:
            conn.execute("ALTER TABLE platform_maintenance_runs ADD COLUMN archive_reason TEXT DEFAULT ''")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_platform_maintenance_runs_created_at "
            "ON platform_maintenance_runs(created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_platform_maintenance_runs_archived "
            "ON platform_maintenance_runs(archived, created_at DESC)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS platform_maintenance_archive_exports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                archive_count INTEGER DEFAULT 0,
                format TEXT DEFAULT 'json',
                file_path TEXT NOT NULL,
                bytes_written INTEGER DEFAULT 0,
                metadata_json TEXT DEFAULT '{}'
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_platform_maintenance_archive_exports_created_at "
            "ON platform_maintenance_archive_exports(created_at DESC)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS platform_maintenance_archive_cleanup_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                retention_days INTEGER DEFAULT 30,
                dry_run INTEGER DEFAULT 1,
                candidate_runs INTEGER DEFAULT 0,
                candidate_exports INTEGER DEFAULT 0,
                deleted_runs INTEGER DEFAULT 0,
                deleted_exports INTEGER DEFAULT 0,
                metadata_json TEXT DEFAULT '{}'
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_platform_maintenance_archive_cleanup_runs_created_at "
            "ON platform_maintenance_archive_cleanup_runs(created_at DESC)"
        )

    def _table_exists(self, conn, table_name: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (table_name,),
        ).fetchone()
        return row is not None

    def _parse_json_object(self, raw: Any) -> Dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _normalize_path_text(self, value: Any) -> str:
        return str(value or "").replace("/", "\\").lower()

    def _is_suspect_path(self, value: Any) -> bool:
        normalized = self._normalize_path_text(value)
        return any(marker in normalized for marker in SUSPECT_PATH_MARKERS)

    def _is_suspect_history_risk(self, risk: Dict[str, Any]) -> bool:
        current_db_path = risk.get("current_db_path") or risk.get("path") or ""
        if self._is_suspect_path(current_db_path):
            return True
        for path in risk.get("shadow_paths") or []:
            if self._is_suspect_path(path):
                return True
        return False

    def _build_risk_snapshot(self) -> Dict[str, Any]:
        observability = get_db_observability()
        shadow_paths = [str(path) for path in (observability.get("shadow_paths") or [])]
        shadow_count = int(observability.get("shadow_count") or len(shadow_paths))
        level = str(observability.get("risk_level") or ("warning" if shadow_count else "normal"))
        current_db = observability.get("current_db") or {}
        summary = (
            f"Detected {shadow_count} shadow business databases"
            if shadow_count
            else "No shadow business databases found"
        )
        return {
            "level": level,
            "shadow_count": shadow_count,
            "summary": summary,
            "current_db_path": str(observability.get("path") or ""),
            "current_db_size_bytes": int(current_db.get("size_bytes") or 0),
            "current_db_updated_at": str(current_db.get("updated_at") or ""),
            "shadow_paths": shadow_paths,
        }

    def _build_notification_snapshot(self) -> Dict[str, Any]:
        webhook_count = 0
        healthy_enabled = 0
        tested_enabled = 0
        try:
            with get_connection() as conn:
                if self._table_exists(conn, "notification_webhooks"):
                    columns = self._get_columns(conn, "notification_webhooks")
                    if {"last_test_at", "last_test_success"} <= columns:
                        row = conn.execute(
                            """
                            SELECT
                                SUM(CASE WHEN enabled=1 THEN 1 ELSE 0 END) AS enabled_count,
                                SUM(CASE WHEN enabled=1 AND last_test_at != '' THEN 1 ELSE 0 END) AS tested_enabled_count,
                                SUM(CASE WHEN enabled=1 AND last_test_success=1 THEN 1 ELSE 0 END) AS healthy_enabled_count
                            FROM notification_webhooks
                            """
                        ).fetchone()
                        webhook_count = int((row["enabled_count"] if row else 0) or 0)
                        tested_enabled = int((row["tested_enabled_count"] if row else 0) or 0)
                        healthy_enabled = int((row["healthy_enabled_count"] if row else 0) or 0)
                    else:
                        row = conn.execute(
                            "SELECT COUNT(*) AS count FROM notification_webhooks WHERE enabled=1"
                        ).fetchone()
                        webhook_count = int((row["count"] if row else 0) or 0)
                        tested_enabled = 0
                        healthy_enabled = 0
        except Exception:
            logger.exception("[Maintenance] Failed to count notification Webhooks")
        untested_enabled = max(webhook_count - tested_enabled, 0)
        ready = healthy_enabled > 0
        if webhook_count == 0:
            summary = "No active production alert Webhook is configured"
        elif tested_enabled == 0:
            summary = f"Configured {webhook_count} Webhooks, but no alert channel has been verified"
        elif healthy_enabled == 0:
            summary = f"Configured {webhook_count} Webhooks, but all recent tests failed"
        else:
            summary = f"Configured {webhook_count} Webhooks; {healthy_enabled} passed their latest tests"
        return {
            "webhook_count": webhook_count,
            "tested_enabled": tested_enabled,
            "healthy_enabled": healthy_enabled,
            "untested_enabled": untested_enabled,
            "ready": ready,
            "summary": summary,
        }

    def _get_archive_export_state(self, conn, archived_count: int) -> Dict[str, Any]:
        export_count = 0
        last_export_at = ""
        last_export_reason = ""
        last_export_path = ""
        last_export_format = ""
        archive_export_fresh = archived_count == 0

        if self._table_exists(conn, "platform_maintenance_archive_exports"):
            row = conn.execute(
                """
                SELECT id, reason, created_at, format, file_path
                FROM platform_maintenance_archive_exports
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            count_row = conn.execute(
                "SELECT COUNT(*) AS count FROM platform_maintenance_archive_exports"
            ).fetchone()
            export_count = int((count_row["count"] if count_row else 0) or 0)
            if row:
                last_export_at = str(row["created_at"] or "")
                last_export_reason = str(row["reason"] or "")
                last_export_path = str(row["file_path"] or "")
                last_export_format = str(row["format"] or "json")

        if archived_count > 0 and last_export_at:
            latest_archived_row = conn.execute(
                """
                SELECT COALESCE(NULLIF(archived_at, ''), created_at) AS archived_marker
                FROM platform_maintenance_runs
                WHERE archived = 1
                ORDER BY archived_marker DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            latest_archived_at = str((latest_archived_row["archived_marker"] if latest_archived_row else "") or "")
            archive_export_fresh = bool(latest_archived_at) and last_export_at >= latest_archived_at

        return {
            "archive_export_count": export_count,
            "last_archive_export_at": last_export_at,
            "last_archive_export_reason": last_export_reason,
            "last_archive_export_path": last_export_path,
            "last_archive_export_format": last_export_format,
            "archive_export_fresh": archive_export_fresh,
        }

    def _get_archive_cleanup_state(
        self,
        conn,
        *,
        archived_count: int,
        export_state: Dict[str, Any],
        retention_days: int = DEFAULT_ARCHIVE_RETENTION_DAYS,
    ) -> Dict[str, Any]:
        normalized_retention_days = max(
            int(DEFAULT_ARCHIVE_RETENTION_DAYS if retention_days is None else retention_days),
            0,
        )
        archive_run_cleanup_candidates = 0
        archive_export_cleanup_candidates = 0
        last_cleanup_at = ""
        last_cleanup_reason = ""
        last_cleanup_dry_run = True
        last_cleanup_deleted_runs = 0
        last_cleanup_deleted_exports = 0

        latest_export_at = str(export_state.get("last_archive_export_at") or "")
        if archived_count > 0 and latest_export_at:
            cutoff = (datetime.now() - timedelta(days=normalized_retention_days)).isoformat()
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM platform_maintenance_runs
                WHERE archived = 1
                  AND COALESCE(NULLIF(archived_at, ''), created_at) <= ?
                  AND COALESCE(NULLIF(archived_at, ''), created_at) <= ?
                """,
                (cutoff, latest_export_at),
            ).fetchone()
            archive_run_cleanup_candidates = int((row["count"] if row else 0) or 0)

            export_rows = conn.execute(
                """
                SELECT id, created_at
                FROM platform_maintenance_archive_exports
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
            latest_export_id = int(export_rows[0]["id"]) if export_rows else 0
            for row in export_rows:
                if int(row["id"]) == latest_export_id:
                    continue
                if str(row["created_at"] or "") <= cutoff:
                    archive_export_cleanup_candidates += 1

        if self._table_exists(conn, "platform_maintenance_archive_cleanup_runs"):
            row = conn.execute(
                """
                SELECT reason, created_at, dry_run, deleted_runs, deleted_exports
                FROM platform_maintenance_archive_cleanup_runs
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            if row:
                last_cleanup_at = str(row["created_at"] or "")
                last_cleanup_reason = str(row["reason"] or "")
                last_cleanup_dry_run = bool(row["dry_run"])
                last_cleanup_deleted_runs = int(row["deleted_runs"] or 0)
                last_cleanup_deleted_exports = int(row["deleted_exports"] or 0)

        return {
            "archive_retention_days": normalized_retention_days,
            "archive_cleanup_needed": (archive_run_cleanup_candidates + archive_export_cleanup_candidates) > 0,
            "archive_cleanup_candidate_count": archive_run_cleanup_candidates + archive_export_cleanup_candidates,
            "archive_run_cleanup_candidates": archive_run_cleanup_candidates,
            "archive_export_cleanup_candidates": archive_export_cleanup_candidates,
            "last_archive_cleanup_at": last_cleanup_at,
            "last_archive_cleanup_reason": last_cleanup_reason,
            "last_archive_cleanup_dry_run": last_cleanup_dry_run,
            "last_archive_cleanup_deleted_runs": last_cleanup_deleted_runs,
            "last_archive_cleanup_deleted_exports": last_cleanup_deleted_exports,
        }

    def _build_data_quality_snapshot(self, pending_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raw_count = 0
        archived_count = 0
        suspect_count = 0
        export_state = {
            "archive_export_count": 0,
            "last_archive_export_at": "",
            "last_archive_export_reason": "",
            "last_archive_export_path": "",
            "last_archive_export_format": "",
            "archive_export_fresh": True,
        }
        cleanup_state = {
            "archive_retention_days": DEFAULT_ARCHIVE_RETENTION_DAYS,
            "archive_cleanup_needed": False,
            "archive_cleanup_candidate_count": 0,
            "archive_run_cleanup_candidates": 0,
            "archive_export_cleanup_candidates": 0,
            "last_archive_cleanup_at": "",
            "last_archive_cleanup_reason": "",
            "last_archive_cleanup_dry_run": True,
            "last_archive_cleanup_deleted_runs": 0,
            "last_archive_cleanup_deleted_exports": 0,
        }
        try:
            with get_connection() as conn:
                self._ensure_schema(conn)
                rows = conn.execute("SELECT risk_json, archived FROM platform_maintenance_runs").fetchall()
                raw_count = len(rows)
                for row in rows:
                    if bool(row["archived"]):
                        archived_count += 1
                        continue
                    risk = self._parse_json_object(row["risk_json"])
                    if self._is_suspect_history_risk(risk):
                        suspect_count += 1
                export_state = self._get_archive_export_state(conn, archived_count=archived_count)
                cleanup_state = self._get_archive_cleanup_state(
                    conn,
                    archived_count=archived_count,
                    export_state=export_state,
                )
        except Exception:
            logger.exception("[Maintenance] Failed to assess maintenance history cleanliness")

        if pending_result and not pending_result.get("skipped"):
            if self._is_suspect_history_risk(pending_result.get("risk") or {}):
                suspect_count += 1
            raw_count += 1

        active_count = max(raw_count - archived_count, 0)
        visible_count = max(active_count - suspect_count, 0)
        clean = suspect_count == 0
        if not clean:
            summary = f"Detected {suspect_count} suspicious maintenance records hidden from the default main view"
        elif bool(cleanup_state.get("archive_cleanup_needed")):
            summary = (
                f"Archived {archived_count} maintenance records; export is current; "
                f"{cleanup_state.get('archive_cleanup_candidate_count') or 0} items are overdue for cleanup"
            )
        elif archived_count and not bool(export_state.get("archive_export_fresh")):
            summary = f"Archived {archived_count} maintenance records, but the archive export is not current"
        elif archived_count:
            summary = f"Archived {archived_count} maintenance records; export is current"
        else:
            summary = "Maintenance history is healthy"
        return {
            "suspect_history_count": suspect_count,
            "raw_history_count": raw_count,
            "archived_history_count": archived_count,
            "visible_history_count": visible_count,
            **export_state,
            **cleanup_state,
            "clean": clean,
            "summary": summary,
        }

    def _persist_run(self, result: Dict[str, Any]) -> None:
        with get_connection() as conn:
            self._ensure_schema(conn)
            conn.execute(
                """
                INSERT INTO platform_maintenance_runs
                (status, reason, created_at, duration_ms, sync_json, repair_json, report_history_json, risk_json, skipped, alert_sent, risk_alert_sent, warning_detected, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(result.get("status") or "unknown"),
                    str(result.get("reason") or "runtime"),
                    str(result.get("timestamp") or datetime.now().isoformat()),
                    int(result.get("duration_ms") or 0),
                    json.dumps(result.get("sync") or {}, ensure_ascii=False),
                    json.dumps(result.get("repair") or {}, ensure_ascii=False),
                    json.dumps(result.get("report_history") or {}, ensure_ascii=False),
                    json.dumps(result.get("risk") or {}, ensure_ascii=False),
                    1 if result.get("skipped") else 0,
                    1 if result.get("alert_sent") else 0,
                    1 if result.get("risk_alert_sent") else 0,
                    1 if result.get("warning_detected") else 0,
                    str(result.get("error") or ""),
                ),
            )

    def _row_to_history_item(self, row) -> Dict[str, Any]:
        risk = self._parse_json_object(row["risk_json"])
        suspect = self._is_suspect_history_risk(risk)
        return {
            "id": int(row["id"]),
            "status": str(row["status"] or "unknown"),
            "reason": str(row["reason"] or "runtime"),
            "timestamp": str(row["created_at"] or ""),
            "duration_ms": int(row["duration_ms"] or 0),
            "sync": self._parse_json_object(row["sync_json"]),
            "repair": self._parse_json_object(row["repair_json"]),
            "report_history": self._parse_json_object(row["report_history_json"]),
            "risk": risk,
            "skipped": bool(row["skipped"]),
            "alert_sent": bool(row["alert_sent"]),
            "risk_alert_sent": bool(row["risk_alert_sent"]),
            "warning_detected": bool(row["warning_detected"]),
            "error": str(row["error_message"] or ""),
            "suspect": suspect,
            "archived": bool(row["archived"]),
            "archived_at": str(row["archived_at"] or ""),
            "archive_reason": str(row["archive_reason"] or ""),
        }

    def list_runs(
        self,
        limit: int = 20,
        include_suspect: bool = False,
        include_archived: bool = False,
    ) -> Dict[str, Any]:
        with get_connection() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(
                """
                SELECT id, status, reason, created_at, duration_ms, sync_json, repair_json,
                       report_history_json, risk_json, skipped, alert_sent, risk_alert_sent, warning_detected,
                       error_message, archived, archived_at, archive_reason
                FROM platform_maintenance_runs
                ORDER BY created_at DESC, id DESC
                """,
            ).fetchall()
        archived_count = 0
        active_rows = []
        for row in rows:
            if bool(row["archived"]):
                archived_count += 1
                if not include_archived:
                    continue
            active_rows.append(row)

        items = []
        suspect_count = 0
        for row in active_rows:
            item = self._row_to_history_item(row)
            suspect = bool(item["suspect"])
            if suspect:
                suspect_count += 1
                if not include_suspect:
                    continue
            items.append(item)
        visible_items = items[:limit]
        return {
            "items": visible_items,
            "total": len(items),
            "raw_total": len(active_rows),
            "suspect_count": suspect_count,
            "filtered": not include_suspect,
            "include_suspect": include_suspect,
            "archived_count": archived_count,
            "include_archived": include_archived,
        }

    def archive_suspect_runs(self, *, reason: str = "ops_archive", limit: int = 0) -> Dict[str, Any]:
        archived_ids = []
        with get_connection() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(
                """
                SELECT id, risk_json, archived
                FROM platform_maintenance_runs
                WHERE archived = 0
                ORDER BY created_at ASC, id ASC
                """
            ).fetchall()
            for row in rows:
                risk = self._parse_json_object(row["risk_json"])
                if self._is_suspect_history_risk(risk):
                    archived_ids.append(int(row["id"]))
                    if limit > 0 and len(archived_ids) >= limit:
                        break
            archived_at = datetime.now().isoformat()
            if archived_ids:
                placeholders = ",".join("?" for _ in archived_ids)
                conn.execute(
                    f"""
                    UPDATE platform_maintenance_runs
                    SET archived = 1, archived_at = ?, archive_reason = ?
                    WHERE id IN ({placeholders})
                    """,
                    (archived_at, reason, *archived_ids),
                )

        with self._lock:
            refreshed_quality = self._build_data_quality_snapshot()
            if self._last_result.get("status") != "never":
                self._last_result["data_quality"] = copy.deepcopy(refreshed_quality)
            if self._last_activity.get("status") != "never":
                self._last_activity["data_quality"] = copy.deepcopy(refreshed_quality)

        return {
            "archived_count": len(archived_ids),
            "archived_ids": archived_ids,
            "reason": reason,
            "archived_at": archived_at if archived_ids else "",
            "remaining": int(refreshed_quality.get("suspect_history_count") or 0),
            "data_quality": refreshed_quality,
        }

    def export_archived_runs(self, *, reason: str = "ops_export_archive", export_format: str = "json") -> Dict[str, Any]:
        normalized_format = str(export_format or "json").strip().lower()
        if normalized_format not in {"json", "jsonl"}:
            raise ValueError("unsupported export format")

        os.makedirs(ARCHIVE_EXPORT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        extension = "jsonl" if normalized_format == "jsonl" else "json"
        export_path = os.path.join(
            ARCHIVE_EXPORT_DIR,
            f"platform_maintenance_archive_{reason}_{timestamp}.{extension}",
        )

        with get_connection() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(
                """
                SELECT id, status, reason, created_at, duration_ms, sync_json, repair_json,
                       report_history_json, risk_json, skipped, alert_sent, risk_alert_sent, warning_detected,
                       error_message, archived, archived_at, archive_reason
                FROM platform_maintenance_runs
                WHERE archived = 1
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
            items = [self._row_to_history_item(row) for row in rows]
            payload = {
                "exported_at": datetime.now().isoformat(),
                "reason": reason,
                "format": normalized_format,
                "count": len(items),
                "items": items,
            }
            if normalized_format == "jsonl":
                with open(export_path, "w", encoding="utf-8") as handle:
                    for item in items:
                        handle.write(json.dumps(item, ensure_ascii=False) + "\n")
            else:
                with open(export_path, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, ensure_ascii=False, indent=2)

            bytes_written = os.path.getsize(export_path) if os.path.exists(export_path) else 0
            conn.execute(
                """
                INSERT INTO platform_maintenance_archive_exports
                (reason, created_at, archive_count, format, file_path, bytes_written, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reason,
                    payload["exported_at"],
                    len(items),
                    normalized_format,
                    export_path,
                    bytes_written,
                    json.dumps(
                        {
                            "count": len(items),
                            "format": normalized_format,
                            "bytes_written": bytes_written,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )

        with self._lock:
            refreshed_quality = self._build_data_quality_snapshot()
            if self._last_result.get("status") != "never":
                self._last_result["data_quality"] = copy.deepcopy(refreshed_quality)
            if self._last_activity.get("status") != "never":
                self._last_activity["data_quality"] = copy.deepcopy(refreshed_quality)

        return {
            "reason": reason,
            "format": normalized_format,
            "exported_at": payload["exported_at"],
            "file_path": export_path,
            "count": len(items),
            "bytes_written": bytes_written,
            "data_quality": refreshed_quality,
        }

    def cleanup_archive_retention(
        self,
        *,
        reason: str = "ops_cleanup_archive",
        retention_days: int = DEFAULT_ARCHIVE_RETENTION_DAYS,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        normalized_retention_days = max(
            int(DEFAULT_ARCHIVE_RETENTION_DAYS if retention_days is None else retention_days),
            0,
        )
        cutoff = (datetime.now() - timedelta(days=normalized_retention_days)).isoformat()
        deleted_runs = 0
        deleted_exports = 0
        deleted_export_files = []

        with get_connection() as conn:
            self._ensure_schema(conn)
            export_state = self._get_archive_export_state(
                conn,
                archived_count=int(
                    (conn.execute("SELECT COUNT(*) AS count FROM platform_maintenance_runs WHERE archived = 1").fetchone() or {"count": 0})["count"]
                    or 0
                ),
            )
            latest_export_at = str(export_state.get("last_archive_export_at") or "")

            archived_candidate_rows = []
            if latest_export_at:
                archived_candidate_rows = conn.execute(
                    """
                    SELECT id
                    FROM platform_maintenance_runs
                    WHERE archived = 1
                      AND COALESCE(NULLIF(archived_at, ''), created_at) <= ?
                      AND COALESCE(NULLIF(archived_at, ''), created_at) <= ?
                    ORDER BY COALESCE(NULLIF(archived_at, ''), created_at) ASC, id ASC
                    """,
                    (cutoff, latest_export_at),
                ).fetchall()

            export_rows = conn.execute(
                """
                SELECT id, file_path, created_at
                FROM platform_maintenance_archive_exports
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
            latest_export_id = int(export_rows[0]["id"]) if export_rows else 0
            export_candidate_rows = [
                row for row in export_rows
                if int(row["id"]) != latest_export_id and str(row["created_at"] or "") <= cutoff
            ]

            archived_candidate_ids = [int(row["id"]) for row in archived_candidate_rows]
            export_candidate_ids = [int(row["id"]) for row in export_candidate_rows]

            if not dry_run:
                if archived_candidate_ids:
                    placeholders = ",".join("?" for _ in archived_candidate_ids)
                    deleted_runs = conn.execute(
                        f"DELETE FROM platform_maintenance_runs WHERE id IN ({placeholders})",
                        archived_candidate_ids,
                    ).rowcount
                if export_candidate_ids:
                    placeholders = ",".join("?" for _ in export_candidate_ids)
                    deleted_exports = conn.execute(
                        f"DELETE FROM platform_maintenance_archive_exports WHERE id IN ({placeholders})",
                        export_candidate_ids,
                    ).rowcount
                    for row in export_candidate_rows:
                        file_path = str(row["file_path"] or "")
                        if file_path and os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                                deleted_export_files.append(file_path)
                            except OSError:
                                logger.exception("[Maintenance] Failed to delete archive export file: %s", file_path)

            created_at = datetime.now().isoformat()
            conn.execute(
                """
                INSERT INTO platform_maintenance_archive_cleanup_runs
                (reason, created_at, retention_days, dry_run, candidate_runs, candidate_exports, deleted_runs, deleted_exports, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reason,
                    created_at,
                    normalized_retention_days,
                    1 if dry_run else 0,
                    len(archived_candidate_ids),
                    len(export_candidate_ids),
                    deleted_runs,
                    deleted_exports,
                    json.dumps(
                        {
                            "cutoff": cutoff,
                            "deleted_export_files": deleted_export_files,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )

        with self._lock:
            refreshed_quality = self._build_data_quality_snapshot()
            if self._last_result.get("status") != "never":
                self._last_result["data_quality"] = copy.deepcopy(refreshed_quality)
            if self._last_activity.get("status") != "never":
                self._last_activity["data_quality"] = copy.deepcopy(refreshed_quality)

        return {
            "reason": reason,
            "retention_days": normalized_retention_days,
            "dry_run": dry_run,
            "cutoff": cutoff,
            "candidate_runs": len(archived_candidate_ids),
            "candidate_exports": len(export_candidate_ids),
            "deleted_runs": deleted_runs,
            "deleted_exports": deleted_exports,
            "deleted_export_files": deleted_export_files,
            "data_quality": refreshed_quality,
        }

    def _merge_live_snapshots(self, base_status: Dict[str, Any]) -> Dict[str, Any]:
        status = copy.deepcopy(base_status)
        status["risk"] = self._build_risk_snapshot()
        status["warning_detected"] = status["risk"].get("level") == "warning"
        status["notification"] = self._build_notification_snapshot()
        status["data_quality"] = self._build_data_quality_snapshot()
        return status

    def _notify_failure(self, result: Dict[str, Any]) -> bool:
        duration_ms = int(result.get("duration_ms") or 0)
        duration_text = f"{duration_ms}ms" if duration_ms < 1000 else f"{duration_ms / 1000:.1f}s"
        notify_result = self._run_notification_sync(
            title="Unified platform maintenance failed",
            status="failed",
            summary=(
                f"Trigger: {result.get('reason') or 'runtime'}\n"
                f"Error: {result.get('error') or 'Unknown error'}"
            ),
            details={
                "duration": duration_text,
                "total_steps": 3,
                "passed": 0,
                "failed": 1,
            },
        )
        return bool((notify_result or {}).get("delivered"))

    def _run_notification_sync(self, **kwargs) -> Dict[str, Any]:
        def _run():
            return asyncio.run(send_completion_notification(**kwargs))

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return _run() or {}

        holder: Dict[str, Any] = {}

        def _worker() -> None:
            try:
                holder["result"] = _run()
            except Exception as exc:  # pragma: no cover - controlled forwarding
                holder["error"] = exc

        worker = threading.Thread(target=_worker, daemon=True)
        worker.start()
        worker.join(timeout=15)
        if worker.is_alive():
            logger.warning("[Maintenance] Notification delivery timed out; treating it as undelivered")
            return {}
        if "error" in holder:
            raise holder["error"]
        return holder.get("result") or {}

    def _should_send_risk_alert(self, previous_status: Dict[str, Any], result: Dict[str, Any]) -> bool:
        if result.get("status") != "success":
            return False
        if result.get("skipped") or not result.get("warning_detected"):
            return False
        if self._is_routine_reason(result.get("reason")):
            return False

        current_risk = result.get("risk") or {}
        previous_risk = previous_status.get("risk") or {}
        if str(previous_risk.get("level") or "") != "warning":
            return True

        current_paths = sorted(str(path) for path in (current_risk.get("shadow_paths") or []))
        previous_paths = sorted(str(path) for path in (previous_risk.get("shadow_paths") or []))
        if current_paths != previous_paths:
            return True

        return (
            int(current_risk.get("shadow_count") or 0) != int(previous_risk.get("shadow_count") or 0)
            or str(current_risk.get("summary") or "") != str(previous_risk.get("summary") or "")
        )

    def _notify_risk_warning(self, result: Dict[str, Any]) -> bool:
        risk = result.get("risk") or {}
        duration_ms = int(result.get("duration_ms") or 0)
        duration_text = f"{duration_ms}ms" if duration_ms < 1000 else f"{duration_ms / 1000:.1f}s"
        summary = (
            f"Trigger: {result.get('reason') or 'runtime'}\n"
            f"{risk.get('summary') or 'Business database risk detected'}\n"
            f"Current business database: {risk.get('current_db_path') or 'Unknown'}"
        )
        if risk.get("shadow_paths"):
            summary += "\nShadow databases:\n" + "\n".join(f"- {path}" for path in risk["shadow_paths"])

        notify_result = self._run_notification_sync(
            title="Platform business database risk alert",
            status="warning",
            summary=summary,
            details={
                "duration": duration_text,
                "total_steps": 3,
                "passed": 3,
                "failed": 0,
            },
        )
        return bool((notify_result or {}).get("delivered"))

    def run(self, *, force: bool = False, reason: str = "runtime") -> Dict[str, Any]:
        now_monotonic = time.monotonic()
        requested_at = datetime.now().isoformat()

        with self._lock:
            previous_status = copy.deepcopy(self._last_result)
            if (
                not force
                and self._last_run_monotonic > 0
                and (now_monotonic - self._last_run_monotonic) < self._min_interval_seconds
            ):
                cached = copy.deepcopy(self._last_result)
                cached["skipped"] = True
                cached["skip_reason"] = "throttled"
                cached["requested_at"] = requested_at
                cached["reason"] = reason
                return cached

            started = time.perf_counter()
            result: Dict[str, Any] = {
                "status": "success",
                "reason": reason,
                "timestamp": requested_at,
                "duration_ms": 0,
                "skipped": False,
                "alert_sent": False,
                "risk_alert_sent": False,
                "warning_detected": False,
                "sync": {"performance": 0, "security": 0},
                "repair": {"group_updates": 0, "record_updates": 0, "legacy_groups": 0},
                "report_history": {"history_entries": 0, "updated_entries": 0},
                "risk": self._build_risk_snapshot(),
                "notification": {
                    "webhook_count": 0,
                    "tested_enabled": 0,
                    "healthy_enabled": 0,
                    "untested_enabled": 0,
                    "ready": False,
                    "summary": "No active production alert Webhook is configured",
                },
                "data_quality": {
                    "suspect_history_count": 0,
                    "raw_history_count": 0,
                    "archived_history_count": 0,
                    "visible_history_count": 0,
                    "archive_export_count": 0,
                    "last_archive_export_at": "",
                    "last_archive_export_reason": "",
                    "last_archive_export_path": "",
                    "last_archive_export_format": "",
                    "archive_export_fresh": True,
                    "archive_retention_days": DEFAULT_ARCHIVE_RETENTION_DAYS,
                    "archive_cleanup_needed": False,
                    "archive_cleanup_candidate_count": 0,
                    "archive_run_cleanup_candidates": 0,
                    "archive_export_cleanup_candidates": 0,
                    "last_archive_cleanup_at": "",
                    "last_archive_cleanup_reason": "",
                    "last_archive_cleanup_dry_run": True,
                    "last_archive_cleanup_deleted_runs": 0,
                    "last_archive_cleanup_deleted_exports": 0,
                    "clean": True,
                    "summary": "Maintenance history is healthy",
                },
            }
            result["warning_detected"] = result["risk"].get("level") == "warning"
            try:
                execution_center = get_execution_center_service()
                result["sync"] = execution_center.sync_external_histories()
                result["repair"] = execution_center.repair_text_artifacts()
                result["report_history"] = get_reporter().repair_history()
            except Exception as exc:
                logger.exception("[Maintenance] Unified maintenance failed (%s)", reason)
                result["status"] = "failed"
                result["error"] = str(exc)
            finally:
                result["duration_ms"] = int((time.perf_counter() - started) * 1000)
                result["notification"] = self._build_notification_snapshot()
                result["data_quality"] = self._build_data_quality_snapshot(result)
                if result.get("status") == "failed":
                    try:
                        result["alert_sent"] = self._notify_failure(result)
                    except Exception:
                        logger.exception("[Maintenance] Failed to send failure alert")
                elif self._should_send_risk_alert(previous_status, result):
                    try:
                        result["risk_alert_sent"] = self._notify_risk_warning(result)
                    except Exception:
                        logger.exception("[Maintenance] Failed to send risk alert")
                self._last_run_monotonic = now_monotonic
                self._last_activity = copy.deepcopy(result)
                if self._last_result.get("status") == "never" or not self._is_routine_reason(result.get("reason")):
                    self._last_result = copy.deepcopy(result)
                if not result.get("skipped"):
                    try:
                        self._persist_run(result)
                    except Exception:
                        logger.exception("[Maintenance] Failed to persist maintenance results")
            return copy.deepcopy(result)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            base = copy.deepcopy(self._last_result)
        return self._merge_live_snapshots(base)

    def get_latest_activity(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._last_activity)


_service: Optional[PlatformMaintenanceService] = None


def get_platform_maintenance_service() -> PlatformMaintenanceService:
    global _service
    if _service is None:
        _service = PlatformMaintenanceService()
    return _service
