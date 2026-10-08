# -*- coding: utf-8 -*-
"""
Execution Center Service

Persist platform test results consistently as:
1. execution_groups: parent records for test executions
2. test_runs: child records for individual tests
"""
from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from core.db_helper import get_connection
from core.text_display import BROKEN_TEXT_STATE, NORMAL_TEXT_STATE, looks_broken_text, resolve_display_text

logger = logging.getLogger(__name__)


class ExecutionCenterService:
    """Unified execution-center persistence and grouping service."""

    _MODE_LABELS: Dict[str, str] = {
        "api_workbench": "API Workbench",
        "database": "Database Query",
        "performance": "Performance Test",
        "security": "Security Scan",
        "accessibility": "Accessibility Test",
        "i18n": "Internationalization Test",
        "compliance": "Compliance Audit",
        "graphql": "GraphQL Test",
        "websocket": "WebSocket Test",
        "grpc": "gRPC Test",
        "chaos": "Chaos Test",
        "mobile": "Mobile Test",
    }

    @staticmethod
    def _looks_broken_text(value: Optional[str]) -> bool:
        return looks_broken_text(value)

    def _normalize_text_metadata(
        self,
        *,
        requirement: Optional[str],
        target_url: str,
        fallback: str,
        requirement_display: Optional[str] = None,
        requirement_raw: Optional[str] = None,
        task_text_state: Optional[str] = None,
    ) -> Dict[str, Any]:
        raw = str(requirement_raw if requirement_raw is not None else requirement or "").strip()
        display, detected_state = resolve_display_text(
            requirement_display if requirement_display is not None else requirement,
            target_url,
            fallback or "Untitled Test",
        )
        normalized_state = str(task_text_state or detected_state or NORMAL_TEXT_STATE).strip() or NORMAL_TEXT_STATE
        if normalized_state != BROKEN_TEXT_STATE and self._looks_broken_text(raw):
            normalized_state = BROKEN_TEXT_STATE
        return {
            "requirement": display,
            "requirement_display": display,
            "requirement_raw": raw,
            "requirement_raw_present": 1 if bool(raw) else 0,
            "task_text_state": normalized_state,
        }

    @staticmethod
    def _compact_target(target_url: str) -> str:
        raw = str(target_url or "").strip()
        if not raw:
            return ""
        try:
            parsed = urlparse(raw)
            if parsed.scheme and parsed.netloc:
                path = parsed.path if parsed.path and parsed.path != "/" else ""
                return f"{parsed.netloc}{path}"
        except Exception:
            pass
        return raw

    def _build_group_title(self, mode: str, target_url: str, fallback: str = "") -> str:
        label = self._compact_target(target_url) or str(fallback or "").strip() or "Specialized Test Batch"
        return f"Specialized Test · {label}"

    def _build_requirement_title(self, mode: str, target_url: str, fallback: str = "") -> str:
        label = str(target_url or "").strip() or str(fallback or "").strip()
        prefix = self._MODE_LABELS.get(str(mode or "").strip(), "")
        if prefix and label:
            return f"{prefix} · {label}"
        return label or prefix or "Untitled Test Record"

    def _prefer_text(
        self,
        current: Optional[str],
        *candidates: Optional[str],
    ) -> str:
        if not self._looks_broken_text(current):
            return str(current or "").strip()
        for candidate in candidates:
            if not self._looks_broken_text(candidate):
                return str(candidate or "").strip()
        return str(current or candidates[0] or "").strip()

    def _get_columns(self, conn, table_name: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row[1]) for row in rows}

    def _ensure_columns(self, conn, table_name: str, columns: Dict[str, str]) -> None:
        existing = self._get_columns(conn, table_name)
        for column_name, column_def in columns.items():
            if column_name in existing:
                continue
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")

    def _ensure_schema(self, conn) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS test_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                requirement TEXT,
                status TEXT DEFAULT 'unknown',
                log_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                duration_ms INTEGER DEFAULT 0,
                target_url TEXT DEFAULT '',
                mode TEXT DEFAULT 'smart',
                logs_json TEXT,
                execution_group_id TEXT DEFAULT '',
                record_kind TEXT DEFAULT 'child',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._ensure_columns(
            conn,
            "test_runs",
            {
                "duration_ms": "INTEGER DEFAULT 0",
                "target_url": "TEXT DEFAULT ''",
                "mode": "TEXT DEFAULT 'smart'",
                "logs_json": "TEXT",
                "execution_group_id": "TEXT DEFAULT ''",
                "record_kind": "TEXT DEFAULT 'child'",
                "requirement_display": "TEXT DEFAULT ''",
                "requirement_raw": "TEXT DEFAULT ''",
                "requirement_raw_present": "INTEGER DEFAULT 0",
                "task_text_state": "TEXT DEFAULT 'normal'",
            },
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_groups (
                group_id TEXT PRIMARY KEY,
                title TEXT,
                requirement TEXT,
                status TEXT DEFAULT 'unknown',
                target_url TEXT DEFAULT '',
                mode TEXT DEFAULT 'smart',
                source TEXT DEFAULT 'manual',
                root_task_id TEXT DEFAULT '',
                session_id TEXT DEFAULT '',
                requirement_display TEXT DEFAULT '',
                requirement_raw_present INTEGER DEFAULT 0,
                task_text_state TEXT DEFAULT 'normal',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._ensure_columns(
            conn,
            "execution_groups",
            {
                "requirement_display": "TEXT DEFAULT ''",
                "requirement_raw_present": "INTEGER DEFAULT 0",
                "task_text_state": "TEXT DEFAULT 'normal'",
            },
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_center_ignored (
                task_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_test_runs_group ON test_runs(execution_group_id, created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_test_runs_task_id ON test_runs(task_id)"
        )

    def _normalize_legacy_rows(self, conn) -> Dict[str, int]:
        legacy_groups = 0
        rows = conn.execute(
            """
            SELECT task_id, requirement, status, COALESCE(target_url, '') AS target_url,
                   COALESCE(mode, 'smart') AS mode, created_at
            FROM test_runs
            WHERE COALESCE(execution_group_id, '') = ''
            """
        ).fetchall()
        for row in rows:
            group_id = str(row["task_id"])
            requirement = str(row["requirement"] or row["task_id"] or "Untitled Test")
            created_at = str(row["created_at"] or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            legacy_groups += 1
            self._ensure_group(
                conn,
                group_id=group_id,
                title=requirement,
                requirement=requirement,
                target_url=str(row["target_url"] or ""),
                mode=str(row["mode"] or "smart"),
                source="legacy",
                root_task_id=group_id,
                session_id="",
                created_at=created_at,
                status=str(row["status"] or "unknown"),
            )
            conn.execute(
                """
                UPDATE test_runs
                SET execution_group_id = ?,
                    record_kind = CASE
                        WHEN COALESCE(NULLIF(record_kind, ''), '') IN ('', 'child') THEN 'root'
                        ELSE record_kind
                    END
                WHERE task_id = ?
                """,
                (group_id, group_id),
            )
        repaired = self._repair_placeholder_rows(conn)
        repaired["legacy_groups"] = legacy_groups
        return repaired

    def _repair_placeholder_rows(self, conn) -> Dict[str, int]:
        group_updates = 0
        record_updates = 0
        groups = conn.execute(
            """
            SELECT group_id, title, requirement, COALESCE(target_url, '') AS target_url,
                   COALESCE(mode, 'smart') AS mode,
                   COALESCE(requirement_display, '') AS requirement_display,
                   COALESCE(requirement_raw_present, 0) AS requirement_raw_present,
                   COALESCE(task_text_state, 'normal') AS task_text_state
            FROM execution_groups
            """
        ).fetchall()
        for row in groups:
            fallback_title = self._build_group_title(
                str(row["mode"] or "smart"),
                str(row["target_url"] or ""),
                str(row["requirement"] or row["group_id"] or ""),
            )
            next_title = self._prefer_text(row["title"], fallback_title)
            next_requirement = self._prefer_text(row["requirement"], fallback_title)
            next_requirement_display = self._prefer_text(
                row["requirement_display"],
                next_requirement,
                next_title,
                fallback_title,
            )
            next_text_state = BROKEN_TEXT_STATE if (
                self._looks_broken_text(row["title"]) or self._looks_broken_text(row["requirement"])
            ) else str(row["task_text_state"] or NORMAL_TEXT_STATE)
            if (
                next_title != str(row["title"] or "")
                or next_requirement != str(row["requirement"] or "")
                or next_requirement_display != str(row["requirement_display"] or "")
                or next_text_state != str(row["task_text_state"] or NORMAL_TEXT_STATE)
            ):
                conn.execute(
                    """
                    UPDATE execution_groups
                    SET title = ?, requirement = ?, requirement_display = ?, task_text_state = ?
                    WHERE group_id = ?
                    """,
                    (next_title, next_requirement, next_requirement_display, next_text_state, row["group_id"]),
                )
                group_updates += 1

        runs = conn.execute(
            """
            SELECT task_id, requirement, COALESCE(target_url, '') AS target_url,
                   COALESCE(mode, 'smart') AS mode,
                   COALESCE(requirement_display, '') AS requirement_display,
                   COALESCE(requirement_raw_present, 0) AS requirement_raw_present,
                   COALESCE(task_text_state, 'normal') AS task_text_state
            FROM test_runs
            """
        ).fetchall()
        for row in runs:
            fallback_requirement = self._build_requirement_title(
                str(row["mode"] or "smart"),
                str(row["target_url"] or ""),
                str(row["task_id"] or ""),
            )
            next_requirement = self._prefer_text(row["requirement"], fallback_requirement)
            next_requirement_display = self._prefer_text(
                row["requirement_display"],
                next_requirement,
                fallback_requirement,
            )
            next_text_state = BROKEN_TEXT_STATE if self._looks_broken_text(row["requirement"]) else str(
                row["task_text_state"] or NORMAL_TEXT_STATE
            )
            if (
                next_requirement != str(row["requirement"] or "")
                or next_requirement_display != str(row["requirement_display"] or "")
                or next_text_state != str(row["task_text_state"] or NORMAL_TEXT_STATE)
            ):
                conn.execute(
                    """
                    UPDATE test_runs
                    SET requirement = ?, requirement_display = ?, task_text_state = ?
                    WHERE task_id = ?
                    """,
                    (next_requirement, next_requirement_display, next_text_state, row["task_id"]),
                )
                record_updates += 1
        return {"group_updates": group_updates, "record_updates": record_updates}

    def repair_text_artifacts(self) -> Dict[str, int]:
        with get_connection() as conn:
            self._ensure_schema(conn)
            return self._normalize_legacy_rows(conn)

    def _is_ignored(self, conn, task_id: str) -> bool:
        row = conn.execute(
            "SELECT task_id FROM execution_center_ignored WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        return bool(row)

    def _mark_ignored_conn(self, conn, task_ids: Iterable[str]) -> None:
        unique_ids = [task_id for task_id in dict.fromkeys(task_ids) if task_id]
        if not unique_ids:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.executemany(
            """
            INSERT OR REPLACE INTO execution_center_ignored (task_id, created_at)
            VALUES (?, ?)
            """,
            [(task_id, now) for task_id in unique_ids],
        )

    def mark_ignored(self, task_ids: Iterable[str]) -> None:
        with get_connection() as conn:
            self._ensure_schema(conn)
            self._normalize_legacy_rows(conn)
            self._mark_ignored_conn(conn, task_ids)

    def _build_system_log(self, content: str) -> Dict[str, Any]:
        return {"type": "system", "content": content}

    def _build_observation_log(self, content: str) -> Dict[str, Any]:
        return {"type": "observation", "content": content}

    def _build_error_log(self, content: str) -> Dict[str, Any]:
        return {"type": "error", "content": content}

    def _build_assertion_log(
        self,
        target: str,
        passed: bool,
        content: str,
        step: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "type": "assertion",
            "status": "pass" if passed else "fail",
            "action": "assert",
            "step": step or target,
            "target": target,
            "content": content,
        }

    def _ensure_group(
        self,
        conn,
        *,
        group_id: str,
        title: str,
        requirement: str,
        target_url: str,
        mode: str,
        source: str,
        root_task_id: str = "",
        session_id: str = "",
        requirement_display: str = "",
        requirement_raw_present: int = 0,
        task_text_state: str = NORMAL_TEXT_STATE,
        created_at: Optional[str] = None,
        status: str = "unknown",
    ) -> str:
        now = created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = conn.execute(
            """
            SELECT group_id, title, requirement, root_task_id, session_id, source, mode,
                   COALESCE(requirement_display, '') AS requirement_display,
                   COALESCE(requirement_raw_present, 0) AS requirement_raw_present,
                   COALESCE(task_text_state, 'normal') AS task_text_state
            FROM execution_groups
            WHERE group_id = ?
            """,
            (group_id,),
        ).fetchone()
        if row:
            current_source = str(row["source"] or source or "manual")
            next_source = "commander" if current_source == "commander" or source == "commander" else (source or current_source or "manual")
            next_mode = "commander" if next_source == "commander" else (mode or str(row["mode"] or "smart") or "smart")
            next_title = self._prefer_text(
                row["title"],
                title,
                self._build_group_title(mode, target_url, requirement or group_id),
                requirement,
                group_id,
            )
            next_requirement = self._prefer_text(
                row["requirement"],
                requirement,
                self._build_group_title(mode, target_url, title or group_id),
                title,
                group_id,
            )
            next_requirement_display = self._prefer_text(
                row["requirement_display"],
                requirement_display,
                next_requirement,
                next_title,
            )
            next_text_state = BROKEN_TEXT_STATE if (
                str(row["task_text_state"] or "") == BROKEN_TEXT_STATE
                or str(task_text_state or "") == BROKEN_TEXT_STATE
            ) else NORMAL_TEXT_STATE
            next_requirement_raw_present = 1 if (
                int(row["requirement_raw_present"] or 0) > 0
                or int(requirement_raw_present or 0) > 0
            ) else 0
            next_root_task_id = str(row["root_task_id"] or root_task_id or group_id)
            next_session_id = str(row["session_id"] or session_id or "")
            conn.execute(
                """
                UPDATE execution_groups
                SET title = ?, requirement = ?, status = ?, target_url = ?, mode = ?,
                    source = ?, root_task_id = ?, session_id = ?, requirement_display = ?,
                    requirement_raw_present = ?, task_text_state = ?, updated_at = ?
                WHERE group_id = ?
                """,
                (
                    next_title,
                    next_requirement,
                    status or "unknown",
                    target_url or "",
                    next_mode,
                    next_source,
                    next_root_task_id,
                    next_session_id,
                    next_requirement_display,
                    next_requirement_raw_present,
                    next_text_state,
                    now,
                    group_id,
                ),
            )
            return group_id

        conn.execute(
            """
            INSERT INTO execution_groups
            (group_id, title, requirement, status, target_url, mode, source, root_task_id, session_id,
             requirement_display, requirement_raw_present, task_text_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                group_id,
                title or requirement or group_id,
                requirement or title or group_id,
                status or "unknown",
                target_url or "",
                mode or "smart",
                source or "manual",
                root_task_id or group_id,
                session_id or "",
                requirement_display or requirement or title or group_id,
                int(requirement_raw_present or 0),
                task_text_state or NORMAL_TEXT_STATE,
                now,
                now,
            ),
        )
        return group_id

    def ensure_group(
        self,
        *,
        group_id: Optional[str] = None,
        title: str = "",
        requirement: str = "",
        target_url: str = "",
        mode: str = "smart",
        source: str = "manual",
        root_task_id: str = "",
        session_id: str = "",
        requirement_display: str = "",
        requirement_raw_present: int = 0,
        task_text_state: str = NORMAL_TEXT_STATE,
        created_at: Optional[str] = None,
        status: str = "unknown",
    ) -> str:
        resolved_group_id = group_id or root_task_id or f"group_{uuid.uuid4().hex[:8]}"
        with get_connection() as conn:
            self._ensure_schema(conn)
            self._normalize_legacy_rows(conn)
            self._ensure_group(
                conn,
                group_id=resolved_group_id,
                title=title or requirement or resolved_group_id,
                requirement=requirement or title or resolved_group_id,
                target_url=target_url,
                mode=mode,
                source=source,
                root_task_id=root_task_id or resolved_group_id,
                session_id=session_id,
                requirement_display=requirement_display or requirement or title or resolved_group_id,
                requirement_raw_present=int(requirement_raw_present or 0),
                task_text_state=task_text_state or NORMAL_TEXT_STATE,
                created_at=created_at,
                status=status,
            )
        return resolved_group_id

    def bind_session_group(
        self,
        session_id: str,
        group_id: str,
        title: str = "",
        target_url: str = "",
    ) -> None:
        from core.session_manager import session_manager

        session = session_manager.get_session(session_id)
        session.set_context("execution_group_id", group_id)
        session.set_context("execution_group_title", title or "")
        session.set_context("execution_group_target_url", target_url or "")

    def get_session_group(self, session_id: Optional[str]) -> Optional[Dict[str, str]]:
        if not session_id:
            return None
        from core.session_manager import session_manager

        session = session_manager.get_session(session_id)
        group_id = session.get_context("execution_group_id")
        if not group_id:
            return None
        return {
            "group_id": str(group_id),
            "title": str(session.get_context("execution_group_title") or ""),
            "target_url": str(session.get_context("execution_group_target_url") or ""),
        }

    def _resolve_group_id(
        self,
        *,
        execution_group_id: Optional[str],
        session_id: Optional[str],
        fallback_task_id: str,
    ) -> str:
        if execution_group_id:
            return execution_group_id
        session_group = self.get_session_group(session_id)
        if session_group and session_group.get("group_id"):
            return str(session_group["group_id"])
        return fallback_task_id

    def _aggregate_status(self, statuses: List[str]) -> str:
        normalized = [str(status or "unknown") for status in statuses]
        if any(status == "failed" for status in normalized):
            return "failed"
        if any(status == "recovered" for status in normalized):
            return "recovered"
        if any(status == "healed" for status in normalized):
            return "healed"
        if normalized and all(status == "success" for status in normalized):
            return "success"
        if any(status == "running" for status in normalized):
            return "running"
        return normalized[0] if normalized else "unknown"

    def _refresh_group_summary(self, conn, group_id: str) -> None:
        rows = conn.execute(
            """
            SELECT task_id, requirement, status, error_count, duration_ms,
                   COALESCE(target_url, '') AS target_url,
                   COALESCE(mode, 'smart') AS mode,
                   COALESCE(record_kind, 'child') AS record_kind,
                   COALESCE(requirement_display, '') AS requirement_display,
                   COALESCE(requirement_raw_present, 0) AS requirement_raw_present,
                   COALESCE(task_text_state, 'normal') AS task_text_state,
                   created_at
            FROM test_runs
            WHERE execution_group_id = ?
            ORDER BY CASE WHEN COALESCE(record_kind, 'child') = 'root' THEN 0 ELSE 1 END, created_at ASC
            """,
            (group_id,),
        ).fetchall()
        if not rows:
            return

        status = self._aggregate_status([str(row["status"] or "unknown") for row in rows])
        created_values = [str(row["created_at"]) for row in rows if row["created_at"]]
        created_at = min(created_values) if created_values else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        updated_at = max(created_values) if created_values else created_at
        root_row = next((row for row in rows if str(row["record_kind"] or "") == "root"), rows[0])
        target_url = str(root_row["target_url"] or "") or next(
            (str(row["target_url"] or "") for row in rows if row["target_url"]),
            "",
        )
        mode = str(root_row["mode"] or "smart")
        title = str(root_row["requirement"] or root_row["task_id"] or group_id)
        requirement_display = str(root_row["requirement_display"] or title)
        requirement_raw_present = int(root_row["requirement_raw_present"] or 0)
        task_text_state = str(root_row["task_text_state"] or NORMAL_TEXT_STATE)
        root_task_id = str(root_row["task_id"] or group_id)

        existing = conn.execute(
            """
            SELECT title, requirement, session_id, source, mode, root_task_id,
                   COALESCE(requirement_display, '') AS requirement_display,
                   COALESCE(requirement_raw_present, 0) AS requirement_raw_present,
                   COALESCE(task_text_state, 'normal') AS task_text_state
            FROM execution_groups
            WHERE group_id = ?
            """,
            (group_id,),
        ).fetchone()
        session_id = str(existing["session_id"] or "") if existing else ""
        source = str(existing["source"] or "manual") if existing else "manual"
        if source == "commander":
            mode = "commander"
            root_task_id = str(existing["root_task_id"] or group_id)
            if existing and existing["title"]:
                title = str(existing["title"] or title)

        self._ensure_group(
            conn,
            group_id=group_id,
            title=str(existing["title"] or title) if existing else title,
            requirement=str(existing["requirement"] or title) if existing else title,
            target_url=target_url,
            mode=mode,
            source=source,
            root_task_id=root_task_id,
            session_id=session_id,
            requirement_display=str(existing["requirement_display"] or requirement_display) if existing else requirement_display,
            requirement_raw_present=max(int(existing["requirement_raw_present"] or 0), requirement_raw_present) if existing else requirement_raw_present,
            task_text_state=str(existing["task_text_state"] or task_text_state) if existing else task_text_state,
            created_at=created_at,
            status=status,
        )
        conn.execute(
            """
            UPDATE execution_groups
            SET status = ?, target_url = ?, mode = ?, root_task_id = ?,
                created_at = ?, updated_at = ?, requirement = COALESCE(NULLIF(requirement, ''), ?),
                title = COALESCE(NULLIF(title, ''), ?),
                requirement_display = COALESCE(NULLIF(requirement_display, ''), ?),
                requirement_raw_present = MAX(COALESCE(requirement_raw_present, 0), ?),
                task_text_state = CASE
                    WHEN COALESCE(task_text_state, 'normal') = 'broken_fallback' OR ? = 'broken_fallback'
                    THEN 'broken_fallback'
                    ELSE COALESCE(task_text_state, 'normal')
                END
            WHERE group_id = ?
            """,
            (
                status,
                target_url,
                mode,
                root_task_id,
                created_at,
                updated_at,
                title,
                title,
                requirement_display,
                requirement_raw_present,
                task_text_state,
                group_id,
            ),
        )

    def upsert_run(
        self,
        *,
        task_id: str,
        requirement: str,
        status: str,
        target_url: str = "",
        mode: str = "special",
        logs: Optional[List[Dict[str, Any]]] = None,
        duration_ms: int = 0,
        created_at: Optional[str] = None,
        execution_group_id: Optional[str] = None,
        session_id: Optional[str] = None,
        group_title: Optional[str] = None,
        record_kind: Optional[str] = None,
        requirement_display: Optional[str] = None,
        requirement_raw: Optional[str] = None,
        task_text_state: Optional[str] = None,
    ) -> str:
        payload_logs = logs or []
        error_count = sum(1 for log in payload_logs if log.get("type") == "error")
        local_now = created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        text_meta = self._normalize_text_metadata(
            requirement=requirement,
            target_url=target_url,
            fallback=task_id,
            requirement_display=requirement_display,
            requirement_raw=requirement_raw,
            task_text_state=task_text_state,
        )

        with get_connection() as conn:
            self._ensure_schema(conn)
            self._normalize_legacy_rows(conn)
            if self._is_ignored(conn, task_id):
                logger.info("[ExecutionCenter] Skip ignored task %s", task_id)
                return task_id

            resolved_group_id = self._resolve_group_id(
                execution_group_id=execution_group_id,
                session_id=session_id,
                fallback_task_id=task_id,
            )
            resolved_record_kind = record_kind or ("root" if resolved_group_id == task_id else "child")
            session_group = self.get_session_group(session_id)
            resolved_group_title = (
                group_title
                or (session_group.get("title") if session_group else "")
                or requirement
                or task_id
            )

            self._ensure_group(
                conn,
                group_id=resolved_group_id,
                title=resolved_group_title,
                requirement=resolved_group_title,
                target_url=target_url,
                mode=mode,
                source="execution-center",
                root_task_id=resolved_group_id if resolved_record_kind == "root" else "",
                session_id=session_id or "",
                requirement_display=text_meta["requirement_display"],
                requirement_raw_present=text_meta["requirement_raw_present"],
                task_text_state=text_meta["task_text_state"],
                created_at=local_now,
                status=status,
            )

            row = conn.execute(
                "SELECT id FROM test_runs WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            params = (
                text_meta["requirement"],
                status,
                len(payload_logs),
                error_count,
                duration_ms,
                target_url,
                mode,
                json.dumps(payload_logs, ensure_ascii=False),
                resolved_group_id,
                resolved_record_kind,
                text_meta["requirement_display"],
                text_meta["requirement_raw"],
                text_meta["requirement_raw_present"],
                text_meta["task_text_state"],
                local_now,
            )
            if row:
                conn.execute(
                    """
                    UPDATE test_runs
                    SET requirement = ?, status = ?, log_count = ?, error_count = ?,
                        duration_ms = ?, target_url = ?, mode = ?, logs_json = ?,
                        execution_group_id = ?, record_kind = ?, requirement_display = ?,
                        requirement_raw = ?, requirement_raw_present = ?, task_text_state = ?, created_at = ?
                    WHERE task_id = ?
                    """,
                    params + (task_id,),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO test_runs
                    (task_id, requirement, status, log_count, error_count, duration_ms, target_url, mode, logs_json,
                     execution_group_id, record_kind, requirement_display, requirement_raw, requirement_raw_present,
                     task_text_state, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (task_id,) + params,
                )

            self._refresh_group_summary(conn, resolved_group_id)

        return task_id

    def _serialize_record_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "task_id": row["task_id"],
            "requirement": row["requirement"] or "Untitled Test Record",
            "requirement_display": row["requirement_display"] or row["requirement"] or "Untitled Test Record",
            "status": row["status"] or "unknown",
            "log_count": int(row["log_count"] or 0),
            "error_count": int(row["error_count"] or 0),
            "duration_ms": int(row["duration_ms"] or 0),
            "target_url": row["target_url"] or "",
            "mode": row["mode"] or "smart",
            "created_at": row["created_at"] or "",
            "execution_group_id": row["execution_group_id"] or row["task_id"],
            "record_kind": row["record_kind"] or "child",
            "requirement_raw_present": int(row["requirement_raw_present"] or 0),
            "task_text_state": row["task_text_state"] or NORMAL_TEXT_STATE,
        }

    def list_grouped_runs(self, limit: int = 50) -> Dict[str, Any]:
        with get_connection() as conn:
            self._ensure_schema(conn)
            self._normalize_legacy_rows(conn)
            groups = conn.execute(
                """
                SELECT group_id, title, requirement, status, target_url, mode, source,
                       root_task_id, session_id, created_at, updated_at,
                       COALESCE(requirement_display, '') AS requirement_display,
                       COALESCE(requirement_raw_present, 0) AS requirement_raw_present,
                       COALESCE(task_text_state, 'normal') AS task_text_state
                FROM execution_groups
                ORDER BY COALESCE(updated_at, created_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            if not groups:
                return {"items": [], "total": 0}

            group_ids = [str(group["group_id"]) for group in groups]
            placeholders = ",".join("?" for _ in group_ids)
            records = conn.execute(
                f"""
                SELECT task_id, requirement, status, log_count, error_count,
                       COALESCE(duration_ms, 0) AS duration_ms,
                       COALESCE(target_url, '') AS target_url,
                       COALESCE(mode, 'smart') AS mode,
                       COALESCE(created_at, '') AS created_at,
                       COALESCE(execution_group_id, task_id) AS execution_group_id,
                       COALESCE(record_kind, 'child') AS record_kind,
                       COALESCE(requirement_display, '') AS requirement_display,
                       COALESCE(requirement_raw_present, 0) AS requirement_raw_present,
                       COALESCE(task_text_state, 'normal') AS task_text_state
                FROM test_runs
                WHERE execution_group_id IN ({placeholders})
                ORDER BY CASE WHEN COALESCE(record_kind, 'child') = 'root' THEN 0 ELSE 1 END, created_at DESC
                """,
                group_ids,
            ).fetchall()

            result_map: Dict[str, Dict[str, Any]] = {}
            for group in groups:
                result_map[str(group["group_id"])] = {
                    "group_id": group["group_id"],
                    "title": group["title"] or group["requirement"] or group["group_id"],
                    "requirement": group["requirement"] or group["title"] or group["group_id"],
                    "requirement_display": group["requirement_display"] or group["requirement"] or group["title"] or group["group_id"],
                    "status": group["status"] or "unknown",
                    "target_url": group["target_url"] or "",
                    "mode": group["mode"] or "smart",
                    "source": group["source"] or "manual",
                    "root_task_id": group["root_task_id"] or "",
                    "session_id": group["session_id"] or "",
                    "requirement_raw_present": int(group["requirement_raw_present"] or 0),
                    "task_text_state": group["task_text_state"] or NORMAL_TEXT_STATE,
                    "created_at": group["created_at"] or "",
                    "updated_at": group["updated_at"] or group["created_at"] or "",
                    "record_count": 0,
                    "log_count": 0,
                    "error_count": 0,
                    "duration_ms": 0,
                    "records": [],
                }

            for row in records:
                serialized = self._serialize_record_row(row)
                group_id = serialized["execution_group_id"]
                group = result_map.get(group_id)
                if not group:
                    continue
                group["records"].append(serialized)
                group["record_count"] += 1
                group["log_count"] += serialized["log_count"]
                group["error_count"] += serialized["error_count"]
                group["duration_ms"] += serialized["duration_ms"]

            return {"items": list(result_map.values()), "total": len(result_map)}

    def get_group_detail(self, group_id: str) -> Optional[Dict[str, Any]]:
        data = self.list_grouped_runs(limit=500)
        for item in data["items"]:
            if item["group_id"] == group_id:
                return item
        return None

    def delete_group(self, group_id: str) -> int:
        with get_connection() as conn:
            self._ensure_schema(conn)
            self._normalize_legacy_rows(conn)
            rows = conn.execute(
                "SELECT task_id FROM test_runs WHERE execution_group_id = ?",
                (group_id,),
            ).fetchall()
            if not rows:
                return 0
            task_ids = [str(row["task_id"]) for row in rows]
            self._mark_ignored_conn(conn, task_ids)
            deleted = conn.execute(
                "DELETE FROM test_runs WHERE execution_group_id = ?",
                (group_id,),
            ).rowcount
            conn.execute("DELETE FROM execution_groups WHERE group_id = ?", (group_id,))
            return int(deleted or 0)

    def record_database_result(
        self,
        *,
        action: str,
        connection_name: str,
        db_type: str,
        database: str,
        success: bool,
        message: str,
        detail_items: Optional[List[Dict[str, Any]]] = None,
        duration_ms: int = 0,
        execution_group_id: Optional[str] = None,
        session_id: Optional[str] = None,
        group_title: Optional[str] = None,
    ) -> str:
        detail_items = detail_items or []
        task_id = f"database_{action}_{uuid.uuid4().hex[:8]}"
        title = f"Database {action} · {connection_name} · {db_type}"
        logs: List[Dict[str, Any]] = [
            self._build_system_log(f"Database test completed: {connection_name} ({db_type})"),
            self._build_assertion_log(
                target=f"Database {action}",
                passed=success,
                content=message,
            ),
        ]
        for item in detail_items:
            target = str(item.get("target") or item.get("rule") or action)
            passed = bool(item.get("passed", False))
            content = str(item.get("content") or item.get("message") or item.get("actual") or "")
            logs.append(self._build_assertion_log(target=target, passed=passed, content=content))
        return self.upsert_run(
            task_id=task_id,
            requirement=title,
            status="success" if success else "failed",
            target_url=database,
            mode="database",
            logs=logs,
            duration_ms=duration_ms,
            execution_group_id=execution_group_id,
            session_id=session_id,
            group_title=group_title,
        )

    def record_accessibility_result(
        self,
        report: Dict[str, Any],
        quick: bool = False,
        execution_group_id: Optional[str] = None,
        session_id: Optional[str] = None,
        group_title: Optional[str] = None,
    ) -> str:
        issues = report.get("issues", []) or []
        total = int(report.get("total") if quick else report.get("total_issues", 0) or 0)
        success = report.get("status", "success") != "error" and total == 0 and report.get("score", 0) != -1
        label = "Quick Check" if quick else "Accessibility Audit"
        task_id = f"accessibility_{'quick' if quick else 'audit'}_{uuid.uuid4().hex[:8]}"
        logs: List[Dict[str, Any]] = [
            self._build_system_log(f"{label} completed: {report.get('url', '')}"),
            self._build_assertion_log(
                target=label,
                passed=success,
                content=report.get("summary") or f"Found {total} issues",
            ),
        ]
        for issue in issues:
            logs.append(
                self._build_assertion_log(
                    target=str(issue.get("rule_id") or "a11y-issue"),
                    passed=False,
                    content=str(issue.get("description") or issue),
                )
            )
        if report.get("status") == "error":
            logs.append(self._build_error_log(str(report.get("error") or "Accessibility test failed")))
        return self.upsert_run(
            task_id=task_id,
            requirement=f"{label} · {report.get('url', '')}",
            status="success" if success else "failed",
            target_url=report.get("url", ""),
            mode="accessibility",
            logs=logs,
            execution_group_id=execution_group_id,
            session_id=session_id,
            group_title=group_title,
        )

    def record_i18n_result(
        self,
        report: Dict[str, Any],
        quick: bool = False,
        execution_group_id: Optional[str] = None,
        session_id: Optional[str] = None,
        group_title: Optional[str] = None,
    ) -> str:
        issues = report.get("issues", []) or []
        total = int(report.get("total") if quick else report.get("total_issues", 0) or 0)
        success = report.get("status", "success") != "error" and total == 0 and report.get("score", 0) != -1
        label = "i18n Quick Check" if quick else "i18n Specialized Test"
        locale_info = report.get("locale") or ",".join(report.get("locales_tested", []) or [])
        task_id = f"i18n_{'quick' if quick else 'audit'}_{uuid.uuid4().hex[:8]}"
        logs: List[Dict[str, Any]] = [
            self._build_system_log(f"{label} completed: {report.get('url', '')}"),
            self._build_assertion_log(
                target=label,
                passed=success,
                content=report.get("summary") or f"Locale={locale_info}; found {total} issues",
            ),
        ]
        for issue in issues:
            logs.append(
                self._build_assertion_log(
                    target=str(issue.get("rule_id") or "i18n-issue"),
                    passed=False,
                    content=str(issue.get("description") or issue),
                )
            )
        if report.get("status") == "error":
            logs.append(self._build_error_log(str(report.get("error") or "i18n test failed")))
        return self.upsert_run(
            task_id=task_id,
            requirement=f"{label} · {report.get('url', '')}",
            status="success" if success else "failed",
            target_url=report.get("url", ""),
            mode="i18n",
            logs=logs,
            execution_group_id=execution_group_id,
            session_id=session_id,
            group_title=group_title,
        )

    def record_compliance_result(
        self,
        report: Dict[str, Any],
        execution_group_id: Optional[str] = None,
        session_id: Optional[str] = None,
        group_title: Optional[str] = None,
    ) -> str:
        issues = report.get("issues", []) or []
        total = int(report.get("total_issues", 0) or 0)
        success = total == 0 and report.get("score", 0) != -1
        task_id = f"compliance_{uuid.uuid4().hex[:8]}"
        logs: List[Dict[str, Any]] = [
            self._build_system_log(f"Compliance audit completed: {report.get('url', '')}"),
            self._build_assertion_log(
                target="Compliance Audit",
                passed=success,
                content=report.get("summary") or f"Found {total} issues",
            ),
        ]
        for issue in issues:
            logs.append(
                self._build_assertion_log(
                    target=str(issue.get("rule_id") or issue.get("standard") or "compliance-issue"),
                    passed=False,
                    content=str(issue.get("description") or issue),
                )
            )
        return self.upsert_run(
            task_id=task_id,
            requirement=f"Compliance Audit · {report.get('url', '')}",
            status="success" if success else "failed",
            target_url=report.get("url", ""),
            mode="compliance",
            logs=logs,
            execution_group_id=execution_group_id,
            session_id=session_id,
            group_title=group_title,
        )

    def record_specialized_result(
        self,
        *,
        mode: str,
        title: str,
        target_url: str,
        success: bool,
        summary: str,
        detail_items: Optional[List[Dict[str, Any]]] = None,
        duration_ms: int = 0,
        execution_group_id: Optional[str] = None,
        session_id: Optional[str] = None,
        group_title: Optional[str] = None,
        task_prefix: Optional[str] = None,
    ) -> str:
        detail_items = detail_items or []
        task_id = f"{task_prefix or mode}_{uuid.uuid4().hex[:8]}"
        logs: List[Dict[str, Any]] = [
            self._build_system_log(f"{title} completed: {target_url or '-'}"),
            self._build_assertion_log(
                target=title,
                passed=success,
                content=summary,
            ),
        ]
        for item in detail_items:
            target = str(item.get("target") or item.get("name") or item.get("path") or title)
            passed = bool(item.get("passed", False))
            content = str(
                item.get("content")
                or item.get("message")
                or item.get("actual")
                or item.get("description")
                or summary
            )
            logs.append(self._build_assertion_log(target=target, passed=passed, content=content))
        if not success and summary:
            logs.append(self._build_error_log(summary))
        return self.upsert_run(
            task_id=task_id,
            requirement=title,
            status="success" if success else "failed",
            target_url=target_url,
            mode=mode,
            logs=logs,
            duration_ms=duration_ms,
            execution_group_id=execution_group_id,
            session_id=session_id,
            group_title=group_title,
        )

    def record_security_result(self, result: Any) -> str:
        config = result.config
        alerts = result.alerts or []
        stats = result.stats or {}
        success = result.status.value == "completed" and len(alerts) == 0 and not result.errors
        task_id = f"security_{result.scan_id}"
        logs: List[Dict[str, Any]] = [
            self._build_system_log(f"Security scan completed: {config.target_url}"),
            self._build_assertion_log(
                target="Security Scan",
                passed=success,
                content=f"Warnings: {len(alerts)}; high risk: {stats.get('high', 0)}",
            ),
        ]
        for alert in alerts:
            logs.append(
                self._build_assertion_log(
                    target=alert.name,
                    passed=False,
                    content=f"[{alert.risk}] {alert.description}",
                )
            )
        for error in result.errors:
            logs.append(self._build_error_log(error))
        duration_ms = int(result.duration * 1000) if result.duration else 0
        return self.upsert_run(
            task_id=task_id,
            requirement=f"Security Scan · {config.target_url}",
            status="success" if success else "failed",
            target_url=config.target_url,
            mode="security",
            logs=logs,
            duration_ms=duration_ms,
            created_at=result.started_at.isoformat(sep=" ") if result.started_at else None,
            execution_group_id=getattr(config, "execution_group_id", None),
            session_id=getattr(config, "session_id", None),
            group_title=getattr(config, "group_title", None),
        )

    def record_performance_result(self, result: Any) -> str:
        config = result.config
        stats = result.stats or {}
        business_success_rate = float(stats.get("business_success_rate", stats.get("success_rate", 0)) or 0)
        failures = int(stats.get("failures", 0) or 0)
        http_5xx = int(stats.get("http_5xx", 0) or 0)
        success = result.status.value == "completed" and failures == 0 and http_5xx == 0 and not result.errors
        task_id = f"performance_{result.test_id}"
        logs: List[Dict[str, Any]] = [
            self._build_system_log(f"Performance test completed: {config.target_url}"),
            self._build_assertion_log(
                target="Business Success Rate",
                passed=business_success_rate >= 99.9,
                content=f"Business success rate: {business_success_rate:.2f}% / total requests: {stats.get('total_requests', 0)}",
            ),
            self._build_assertion_log(
                target="Server Errors",
                passed=http_5xx == 0,
                content=f"HTTP 5xx count: {http_5xx}",
            ),
            self._build_observation_log(
                f"Average response: {stats.get('avg_response_time', 0)}ms, RPS {stats.get('requests_per_second', 0)}"
            ),
        ]
        for error in result.errors:
            logs.append(self._build_error_log(error))
        duration_ms = int(result.duration * 1000) if result.duration else 0
        return self.upsert_run(
            task_id=task_id,
            requirement=f"Performance Test · {config.target_url}",
            status="success" if success else "failed",
            target_url=config.target_url,
            mode="performance",
            logs=logs,
            duration_ms=duration_ms,
            created_at=result.started_at.isoformat(sep=" ") if result.started_at else None,
            execution_group_id=getattr(config, "execution_group_id", None),
            session_id=getattr(config, "session_id", None),
            group_title=getattr(config, "group_title", None),
        )

    def sync_external_histories(self) -> Dict[str, int]:
        imported = {"performance": 0, "security": 0}
        try:
            from services.performance_runner import get_performance_runner, LoadTestConfig, LoadTestResult, LoadTestStatus

            runner = get_performance_runner()
            for item in runner.get_history(limit=200):
                task_id = f"performance_{item.get('test_id', '')}"
                if not item.get("test_id"):
                    continue
                with get_connection() as conn:
                    self._ensure_schema(conn)
                    self._normalize_legacy_rows(conn)
                    existing = conn.execute("SELECT task_id FROM test_runs WHERE task_id = ?", (task_id,)).fetchone()
                    ignored = self._is_ignored(conn, task_id)
                if existing or ignored:
                    continue
                result = LoadTestResult(
                    test_id=item["test_id"],
                    status=LoadTestStatus(item.get("status", "completed")),
                    config=LoadTestConfig(**item.get("config", {})),
                    stats=item.get("stats", {}) or {},
                    errors=item.get("errors", []) or [],
                    started_at=datetime.fromisoformat(item["started_at"]) if item.get("started_at") else None,
                    finished_at=datetime.fromisoformat(item["finished_at"]) if item.get("finished_at") else None,
                )
                self.record_performance_result(result)
                imported["performance"] += 1
        except Exception as exc:
            logger.warning("[ExecutionCenter] Failed to sync performance history: %s", exc)

        try:
            from services.security_scanner import get_security_scanner, ScanConfig, ScanResult, ScanStatus, SecurityAlert

            scanner = get_security_scanner()
            for item in scanner.get_history(limit=200):
                task_id = f"security_{item.get('scan_id', '')}"
                if not item.get("scan_id"):
                    continue
                with get_connection() as conn:
                    self._ensure_schema(conn)
                    self._normalize_legacy_rows(conn)
                    existing = conn.execute("SELECT task_id FROM test_runs WHERE task_id = ?", (task_id,)).fetchone()
                    ignored = self._is_ignored(conn, task_id)
                if existing or ignored:
                    continue
                result = ScanResult(
                    scan_id=item["scan_id"],
                    status=ScanStatus(item.get("status", "completed")),
                    config=ScanConfig(**item.get("config", {})),
                    stats=item.get("stats", {}) or {},
                    errors=item.get("errors", []) or [],
                    started_at=datetime.fromisoformat(item["started_at"]) if item.get("started_at") else None,
                    finished_at=datetime.fromisoformat(item["finished_at"]) if item.get("finished_at") else None,
                    alerts=[SecurityAlert(**alert) for alert in item.get("alerts", []) or []],
                )
                self.record_security_result(result)
                imported["security"] += 1
        except Exception as exc:
            logger.warning("[ExecutionCenter] Failed to sync security history: %s", exc)

        return imported


_service: Optional[ExecutionCenterService] = None


def get_execution_center_service() -> ExecutionCenterService:
    global _service
    if _service is None:
        _service = ExecutionCenterService()
    return _service
