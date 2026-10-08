# -*- coding: utf-8 -*-
import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.platform_maintenance_service import PlatformMaintenanceService


@pytest.fixture(autouse=True)
def isolate_platform_maintenance_db(tmp_path, monkeypatch):
    db_path = tmp_path / "business.db"
    real_connect = sqlite3.connect

    def _connect(*args, **kwargs):
        timeout = kwargs.get("timeout", 30)
        conn = real_connect(db_path, timeout=timeout)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr("core.db_helper.sqlite3.connect", _connect)
    return db_path


def test_platform_maintenance_run_aggregates_execution_and_report_steps():
    execution_center = MagicMock()
    execution_center.sync_external_histories.return_value = {"performance": 2, "security": 1}
    execution_center.repair_text_artifacts.return_value = {"group_updates": 1, "record_updates": 3, "legacy_groups": 0}

    reporter = MagicMock()
    reporter.repair_history.return_value = {"history_entries": 8, "updated_entries": 2}

    service = PlatformMaintenanceService(min_interval_seconds=60)

    with patch("services.platform_maintenance_service.get_execution_center_service", return_value=execution_center), \
         patch("services.platform_maintenance_service.get_reporter", return_value=reporter), \
         patch("services.platform_maintenance_service.send_completion_notification", side_effect=[{"delivered": 1}]), \
         patch("services.platform_maintenance_service.get_db_observability", return_value={
             "path": r"D:\demo\business.db",
             "current_db": {"size_bytes": 1024, "updated_at": "2026-03-16T10:00:00"},
             "shadow_paths": [r"D:\legacy\business.db"],
             "shadow_count": 1,
             "risk_level": "warning",
         }):
        result = service.run(force=True, reason="startup")

    assert result["status"] == "success"
    assert result["reason"] == "startup"
    assert result["skipped"] is False
    assert result["sync"] == {"performance": 2, "security": 1}
    assert result["repair"]["group_updates"] == 1
    assert result["report_history"]["updated_entries"] == 2
    assert result["warning_detected"] is True
    assert result["risk_alert_sent"] is True
    assert result["risk"]["shadow_count"] == 1
    assert service.get_status()["status"] == "success"


def test_platform_maintenance_run_throttles_repeated_calls():
    execution_center = MagicMock()
    execution_center.sync_external_histories.return_value = {"performance": 0, "security": 0}
    execution_center.repair_text_artifacts.return_value = {"group_updates": 0, "record_updates": 0, "legacy_groups": 0}

    reporter = MagicMock()
    reporter.repair_history.return_value = {"history_entries": 0, "updated_entries": 0}

    service = PlatformMaintenanceService(min_interval_seconds=999)

    with patch("services.platform_maintenance_service.get_execution_center_service", return_value=execution_center), \
         patch("services.platform_maintenance_service.get_reporter", return_value=reporter), \
         patch("services.platform_maintenance_service.get_db_observability", return_value={
             "path": r"D:\demo\business.db",
             "current_db": {"size_bytes": 2048, "updated_at": "2026-03-16T10:05:00"},
             "shadow_paths": [],
             "shadow_count": 0,
             "risk_level": "normal",
         }):
        first = service.run(reason="history_list")
        second = service.run(reason="report_history")

    assert first["status"] == "success"
    assert second["skipped"] is True
    assert second["skip_reason"] == "throttled"
    execution_center.sync_external_histories.assert_called_once()
    reporter.repair_history.assert_called_once()


def test_platform_maintenance_keeps_operational_status_when_routine_reason_runs():
    execution_center = MagicMock()
    execution_center.sync_external_histories.return_value = {"performance": 0, "security": 0}
    execution_center.repair_text_artifacts.return_value = {"group_updates": 0, "record_updates": 0, "legacy_groups": 0}

    reporter = MagicMock()
    reporter.repair_history.return_value = {"history_entries": 0, "updated_entries": 0}

    service = PlatformMaintenanceService(min_interval_seconds=0)

    with patch("services.platform_maintenance_service.get_execution_center_service", return_value=execution_center), \
         patch("services.platform_maintenance_service.get_reporter", return_value=reporter), \
         patch("services.platform_maintenance_service.get_db_observability", return_value={
             "path": r"D:\demo\business.db",
             "current_db": {"size_bytes": 2048, "updated_at": "2026-03-16T10:05:00"},
             "shadow_paths": [],
             "shadow_count": 0,
             "risk_level": "normal",
         }):
        service.run(force=True, reason="startup")
        service.run(force=True, reason="history_list")

    assert service.get_status()["reason"] == "startup"
    assert service.get_latest_activity()["reason"] == "history_list"


def test_platform_maintenance_persists_non_skipped_runs(tmp_path):
    db_path = tmp_path / "business.db"
    real_connect = sqlite3.connect

    def _connect(*args, **kwargs):
        conn = real_connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    execution_center = MagicMock()
    execution_center.sync_external_histories.return_value = {"performance": 1, "security": 0}
    execution_center.repair_text_artifacts.return_value = {"group_updates": 2, "record_updates": 1, "legacy_groups": 0}

    reporter = MagicMock()
    reporter.repair_history.return_value = {"history_entries": 3, "updated_entries": 1}

    service = PlatformMaintenanceService(min_interval_seconds=60)

    with patch("services.platform_maintenance_service.get_execution_center_service", return_value=execution_center), \
         patch("services.platform_maintenance_service.get_reporter", return_value=reporter), \
         patch("core.db_helper.sqlite3.connect", side_effect=_connect), \
         patch("services.platform_maintenance_service.send_completion_notification", side_effect=[{"delivered": 1}]), \
         patch("services.platform_maintenance_service.get_db_observability", return_value={
             "path": str(db_path),
             "current_db": {"size_bytes": 2048, "updated_at": "2026-03-16T10:05:00"},
             "shadow_paths": [],
             "shadow_count": 0,
             "risk_level": "normal",
         }):
        result = service.run(force=True, reason="startup")
        history = service.list_runs(limit=10)

    assert result["status"] == "success"
    assert history["total"] == 1
    assert history["items"][0]["reason"] == "startup"
    assert history["items"][0]["sync"]["performance"] == 1
    assert history["items"][0]["repair"]["group_updates"] == 2
    assert history["items"][0]["risk"]["shadow_count"] == 0
    assert history["items"][0]["warning_detected"] is False
    assert history["items"][0]["risk_alert_sent"] is False


def test_platform_maintenance_tracks_notification_and_filters_suspect_history(tmp_path):
    db_path = tmp_path / "business.db"
    real_connect = sqlite3.connect

    def _connect(*args, **kwargs):
        conn = real_connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    execution_center = MagicMock()
    execution_center.sync_external_histories.return_value = {"performance": 0, "security": 0}
    execution_center.repair_text_artifacts.return_value = {"group_updates": 0, "record_updates": 0, "legacy_groups": 0}

    reporter = MagicMock()
    reporter.repair_history.return_value = {"history_entries": 2, "updated_entries": 0}

    service = PlatformMaintenanceService(min_interval_seconds=0)

    with patch("core.db_helper.sqlite3.connect", side_effect=_connect):
        with _connect() as conn:
            service._ensure_schema(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_webhooks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    type TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    last_test_at TEXT DEFAULT '',
                    last_test_success INTEGER DEFAULT 0,
                    last_test_status INTEGER DEFAULT 0,
                    last_test_message TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                INSERT INTO notification_webhooks
                (name, url, type, enabled, last_test_at, last_test_success, last_test_status, last_test_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("ops", "http://127.0.0.1/webhook", "generic", 1, "2026-03-16T11:05:00", 1, 200, "Sent successfully"),
            )
            conn.execute(
                """
                INSERT INTO platform_maintenance_runs
                (status, reason, created_at, duration_ms, sync_json, repair_json, report_history_json, risk_json, skipped, alert_sent, risk_alert_sent, warning_detected, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "success",
                    "legacy_fixture",
                    "2026-03-16T09:00:00",
                    10,
                    "{}",
                    "{}",
                    "{}",
                    '{"level":"warning","shadow_count":1,"summary":"legacy","current_db_path":"D:\\\\demo\\\\business.db","shadow_paths":["D:\\\\legacy\\\\business.db"]}',
                    0,
                    0,
                    0,
                    1,
                    "",
                ),
            )
            conn.commit()

        with patch("services.platform_maintenance_service.get_execution_center_service", return_value=execution_center), \
             patch("services.platform_maintenance_service.get_reporter", return_value=reporter), \
             patch("services.platform_maintenance_service.get_db_observability", return_value={
                 "path": str(db_path),
                 "current_db": {"size_bytes": 4096, "updated_at": "2026-03-16T11:00:00"},
                 "shadow_paths": [],
                 "shadow_count": 0,
                 "risk_level": "normal",
             }):
            result = service.run(force=True, reason="startup")
            filtered = service.list_runs(limit=10)
            unfiltered = service.list_runs(limit=10, include_suspect=True)

    assert result["notification"]["ready"] is True
    assert result["notification"]["webhook_count"] == 1
    assert result["notification"]["tested_enabled"] == 1
    assert result["notification"]["healthy_enabled"] == 1
    assert result["notification"]["untested_enabled"] == 0
    assert result["data_quality"]["suspect_history_count"] == 1
    assert result["data_quality"]["clean"] is False
    assert filtered["filtered"] is True
    assert filtered["suspect_count"] == 1
    assert filtered["raw_total"] == 2
    assert filtered["total"] == 1
    assert filtered["archived_count"] == 0
    assert len(filtered["items"]) == 1
    assert filtered["items"][0]["suspect"] is False
    assert unfiltered["include_suspect"] is True
    assert unfiltered["total"] == 2
    assert any(item["suspect"] for item in unfiltered["items"])


def test_platform_maintenance_notification_requires_healthy_test_to_be_ready(tmp_path):
    db_path = tmp_path / "business.db"
    real_connect = sqlite3.connect

    def _connect(*args, **kwargs):
        conn = real_connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    execution_center = MagicMock()
    execution_center.sync_external_histories.return_value = {"performance": 0, "security": 0}
    execution_center.repair_text_artifacts.return_value = {"group_updates": 0, "record_updates": 0, "legacy_groups": 0}

    reporter = MagicMock()
    reporter.repair_history.return_value = {"history_entries": 0, "updated_entries": 0}

    service = PlatformMaintenanceService(min_interval_seconds=0)

    with patch("core.db_helper.sqlite3.connect", side_effect=_connect):
        with _connect() as conn:
            service._ensure_schema(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_webhooks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    type TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    last_test_at TEXT DEFAULT '',
                    last_test_success INTEGER DEFAULT 0,
                    last_test_status INTEGER DEFAULT 0,
                    last_test_message TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                INSERT INTO notification_webhooks
                (name, url, type, enabled, last_test_at, last_test_success, last_test_status, last_test_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("ops", "http://127.0.0.1/webhook", "generic", 1, "", 0, 0, ""),
            )
            conn.commit()

        with patch("services.platform_maintenance_service.get_execution_center_service", return_value=execution_center), \
             patch("services.platform_maintenance_service.get_reporter", return_value=reporter), \
             patch("services.platform_maintenance_service.get_db_observability", return_value={
                 "path": str(db_path),
                 "current_db": {"size_bytes": 4096, "updated_at": "2026-03-16T11:00:00"},
                 "shadow_paths": [],
                 "shadow_count": 0,
                 "risk_level": "normal",
             }):
            result = service.run(force=True, reason="startup")

    assert result["notification"]["webhook_count"] == 1
    assert result["notification"]["tested_enabled"] == 0
    assert result["notification"]["healthy_enabled"] == 0
    assert result["notification"]["untested_enabled"] == 1
    assert result["notification"]["ready"] is False
    assert "no alert channel has been verified" in result["notification"]["summary"]


def test_platform_maintenance_get_status_refreshes_live_notification_snapshot(tmp_path):
    db_path = tmp_path / "business.db"
    real_connect = sqlite3.connect

    def _connect(*args, **kwargs):
        conn = real_connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    execution_center = MagicMock()
    execution_center.sync_external_histories.return_value = {"performance": 0, "security": 0}
    execution_center.repair_text_artifacts.return_value = {"group_updates": 0, "record_updates": 0, "legacy_groups": 0}

    reporter = MagicMock()
    reporter.repair_history.return_value = {"history_entries": 0, "updated_entries": 0}

    service = PlatformMaintenanceService(min_interval_seconds=0)

    with patch("core.db_helper.sqlite3.connect", side_effect=_connect):
        with patch("services.platform_maintenance_service.get_execution_center_service", return_value=execution_center), \
             patch("services.platform_maintenance_service.get_reporter", return_value=reporter), \
             patch("services.platform_maintenance_service.get_db_observability", return_value={
                 "path": str(db_path),
                 "current_db": {"size_bytes": 4096, "updated_at": "2026-03-16T11:00:00"},
                 "shadow_paths": [],
                 "shadow_count": 0,
                 "risk_level": "normal",
             }):
            first = service.run(force=True, reason="startup")

        with _connect() as conn:
            service._ensure_schema(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_webhooks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    type TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    last_test_at TEXT DEFAULT '',
                    last_test_success INTEGER DEFAULT 0,
                    last_test_status INTEGER DEFAULT 0,
                    last_test_message TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                INSERT INTO notification_webhooks
                (name, url, type, enabled, last_test_at, last_test_success, last_test_status, last_test_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("ops", "http://127.0.0.1/webhook", "generic", 1, "2026-03-16T11:05:00", 1, 200, "Sent successfully"),
            )
            conn.commit()

        current = service.get_status()

    assert first["notification"]["ready"] is False
    assert current["notification"]["webhook_count"] == 1
    assert current["notification"]["tested_enabled"] == 1
    assert current["notification"]["healthy_enabled"] == 1
    assert current["notification"]["ready"] is True


def test_platform_maintenance_archive_suspect_runs_marks_rows_without_deleting(tmp_path):
    db_path = tmp_path / "business.db"
    real_connect = sqlite3.connect

    def _connect(*args, **kwargs):
        conn = real_connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    service = PlatformMaintenanceService(min_interval_seconds=0)

    with patch("core.db_helper.sqlite3.connect", side_effect=_connect):
        with _connect() as conn:
            service._ensure_schema(conn)
            conn.execute(
                """
                INSERT INTO platform_maintenance_runs
                (status, reason, created_at, duration_ms, sync_json, repair_json, report_history_json, risk_json, skipped, alert_sent, risk_alert_sent, warning_detected, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "success",
                    "legacy_fixture",
                    "2026-03-16T09:00:00",
                    10,
                    "{}",
                    "{}",
                    "{}",
                    '{"level":"warning","shadow_count":1,"summary":"legacy","current_db_path":"D:\\\\demo\\\\business.db","shadow_paths":["D:\\\\legacy\\\\business.db"]}',
                    0,
                    0,
                    0,
                    1,
                    "",
                ),
            )
            conn.execute(
                """
                INSERT INTO platform_maintenance_runs
                (status, reason, created_at, duration_ms, sync_json, repair_json, report_history_json, risk_json, skipped, alert_sent, risk_alert_sent, warning_detected, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "success",
                    "startup",
                    "2026-03-16T10:00:00",
                    11,
                    "{}",
                    "{}",
                    "{}",
                    '{"level":"normal","shadow_count":0,"summary":"ok","current_db_path":"D:\\\\workspace\\\\ai_test_platform\\\\backend\\\\data\\\\business.db","shadow_paths":[]}',
                    0,
                    0,
                    0,
                    0,
                    "",
                ),
            )
            conn.commit()

        result = service.archive_suspect_runs(reason="ops_archive")
        filtered = service.list_runs(limit=10)
        full = service.list_runs(limit=10, include_suspect=True, include_archived=True)

        with _connect() as conn:
            archived_rows = conn.execute(
                "SELECT archived, archive_reason FROM platform_maintenance_runs WHERE reason='legacy_fixture'"
            ).fetchall()

    assert result["archived_count"] == 1
    assert result["remaining"] == 0
    assert result["data_quality"]["clean"] is True
    assert result["data_quality"]["archived_history_count"] == 1
    assert filtered["archived_count"] == 1
    assert filtered["raw_total"] == 1
    assert filtered["total"] == 1
    assert filtered["items"][0]["reason"] == "startup"
    assert full["archived_count"] == 1
    assert full["total"] == 2
    assert any(item["archived"] for item in full["items"])
    assert archived_rows[0]["archived"] == 1
    assert archived_rows[0]["archive_reason"] == "ops_archive"


def test_platform_maintenance_export_archived_runs_writes_file_and_marks_snapshot_fresh(tmp_path):
    db_path = tmp_path / "business.db"
    archive_dir = tmp_path / "exports"
    real_connect = sqlite3.connect

    def _connect(*args, **kwargs):
        conn = real_connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    service = PlatformMaintenanceService(min_interval_seconds=0)

    with patch("core.db_helper.sqlite3.connect", side_effect=_connect), \
         patch("services.platform_maintenance_service.ARCHIVE_EXPORT_DIR", str(archive_dir)):
        with _connect() as conn:
            service._ensure_schema(conn)
            conn.execute(
                """
                INSERT INTO platform_maintenance_runs
                (status, reason, created_at, duration_ms, sync_json, repair_json, report_history_json, risk_json, skipped, alert_sent, risk_alert_sent, warning_detected, error_message, archived, archived_at, archive_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "success",
                    "legacy_fixture",
                    "2026-03-16T09:00:00",
                    10,
                    "{}",
                    "{}",
                    "{}",
                    '{"level":"normal","shadow_count":0,"summary":"ok","current_db_path":"D:\\\\workspace\\\\ai_test_platform\\\\backend\\\\data\\\\business.db","shadow_paths":[]}',
                    0,
                    0,
                    0,
                    0,
                    "",
                    1,
                    "2026-03-16T11:00:00",
                    "ops_archive",
                ),
            )
            conn.commit()

        result = service.export_archived_runs(reason="ops_export_archive", export_format="json")

    exported_file = tmp_path / "exports" / Path(result["file_path"]).name
    assert result["count"] == 1
    assert result["format"] == "json"
    assert result["data_quality"]["archive_export_count"] == 1
    assert result["data_quality"]["archive_export_fresh"] is True
    assert exported_file.exists()
    exported_payload = json.loads(exported_file.read_text(encoding="utf-8"))
    assert exported_payload["count"] == 1
    assert exported_payload["items"][0]["archive_reason"] == "ops_archive"


def test_platform_maintenance_cleanup_archive_retention_deletes_expired_records_and_old_exports(tmp_path):
    db_path = tmp_path / "business.db"
    archive_dir = tmp_path / "exports"
    archive_dir.mkdir()
    old_export_file = archive_dir / "old.json"
    latest_export_file = archive_dir / "latest.json"
    old_export_file.write_text("old", encoding="utf-8")
    latest_export_file.write_text("latest", encoding="utf-8")
    real_connect = sqlite3.connect

    def _connect(*args, **kwargs):
        conn = real_connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    service = PlatformMaintenanceService(min_interval_seconds=0)

    with patch("core.db_helper.sqlite3.connect", side_effect=_connect):
        with _connect() as conn:
            service._ensure_schema(conn)
            conn.execute(
                """
                INSERT INTO platform_maintenance_runs
                (status, reason, created_at, duration_ms, sync_json, repair_json, report_history_json, risk_json, skipped, alert_sent, risk_alert_sent, warning_detected, error_message, archived, archived_at, archive_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "success",
                    "legacy_fixture",
                    "2000-03-01T09:00:00",
                    10,
                    "{}",
                    "{}",
                    "{}",
                    '{"level":"normal","shadow_count":0,"summary":"ok","current_db_path":"D:\\\\workspace\\\\ai_test_platform\\\\backend\\\\data\\\\business.db","shadow_paths":[]}',
                    0,
                    0,
                    0,
                    0,
                    "",
                    1,
                    "2000-03-01T10:00:00",
                    "ops_archive",
                ),
            )
            conn.execute(
                """
                INSERT INTO platform_maintenance_archive_exports
                (reason, created_at, archive_count, format, file_path, bytes_written, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("older_export", "2000-03-02T10:00:00", 1, "json", str(old_export_file), 3, "{}"),
            )
            conn.execute(
                """
                INSERT INTO platform_maintenance_archive_exports
                (reason, created_at, archive_count, format, file_path, bytes_written, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("latest_export", "2000-03-16T10:00:00", 1, "json", str(latest_export_file), 6, "{}"),
            )
            conn.commit()

        result = service.cleanup_archive_retention(reason="ops_cleanup_archive", retention_days=0, dry_run=False)

        with _connect() as conn:
            remaining_archived = conn.execute("SELECT COUNT(*) AS count FROM platform_maintenance_runs WHERE archived = 1").fetchone()["count"]
            remaining_exports = conn.execute("SELECT COUNT(*) AS count FROM platform_maintenance_archive_exports").fetchone()["count"]

    assert result["candidate_runs"] == 1
    assert result["candidate_exports"] == 1
    assert result["retention_days"] == 0
    assert result["deleted_runs"] == 1
    assert result["deleted_exports"] == 1
    assert str(old_export_file) in result["deleted_export_files"]
    assert not old_export_file.exists()
    assert latest_export_file.exists()
    assert remaining_archived == 0
    assert remaining_exports == 1
    assert result["data_quality"]["last_archive_cleanup_reason"] == "ops_cleanup_archive"


def test_platform_maintenance_failure_sends_notification_and_marks_alert():
    execution_center = MagicMock()
    execution_center.sync_external_histories.side_effect = RuntimeError("sync crashed")

    reporter = MagicMock()
    reporter.repair_history.return_value = {"history_entries": 0, "updated_entries": 0}

    notified = {"called": False}

    async def fake_notify(**kwargs):
        notified["called"] = True
        return {"delivered": 1}

    service = PlatformMaintenanceService(min_interval_seconds=60)

    with patch("services.platform_maintenance_service.get_execution_center_service", return_value=execution_center), \
         patch("services.platform_maintenance_service.get_reporter", return_value=reporter), \
         patch("services.platform_maintenance_service.send_completion_notification", side_effect=fake_notify), \
         patch("services.platform_maintenance_service.get_db_observability", return_value={
             "path": r"D:\demo\business.db",
             "current_db": {"size_bytes": 2048, "updated_at": "2026-03-16T10:05:00"},
             "shadow_paths": [],
             "shadow_count": 0,
             "risk_level": "normal",
         }):
        result = service.run(force=True, reason="startup")

    assert result["status"] == "failed"
    assert result["alert_sent"] is True
    assert result["risk_alert_sent"] is False
    assert notified["called"] is True


def test_platform_maintenance_warning_alert_is_deduplicated_when_shadow_state_unchanged():
    execution_center = MagicMock()
    execution_center.sync_external_histories.return_value = {"performance": 0, "security": 0}
    execution_center.repair_text_artifacts.return_value = {"group_updates": 0, "record_updates": 0, "legacy_groups": 0}

    reporter = MagicMock()
    reporter.repair_history.return_value = {"history_entries": 0, "updated_entries": 0}

    service = PlatformMaintenanceService(min_interval_seconds=0)

    with patch("services.platform_maintenance_service.get_execution_center_service", return_value=execution_center), \
         patch("services.platform_maintenance_service.get_reporter", return_value=reporter), \
         patch("services.platform_maintenance_service.send_completion_notification", side_effect=[{"delivered": 1}]) as notify_mock, \
         patch("services.platform_maintenance_service.get_db_observability", return_value={
             "path": r"D:\demo\business.db",
             "current_db": {"size_bytes": 2048, "updated_at": "2026-03-16T10:05:00"},
             "shadow_paths": [r"D:\legacy\business.db"],
             "shadow_count": 1,
             "risk_level": "warning",
         }):
        first = service.run(force=True, reason="startup")
        second = service.run(force=True, reason="dashboard_manual")

    assert first["risk_alert_sent"] is True
    assert second["risk_alert_sent"] is False
    assert notify_mock.call_count == 1


def test_platform_maintenance_running_loop_does_not_mark_risk_alert_sent_without_delivery():
    execution_center = MagicMock()
    execution_center.sync_external_histories.return_value = {"performance": 0, "security": 0}
    execution_center.repair_text_artifacts.return_value = {"group_updates": 0, "record_updates": 0, "legacy_groups": 0}

    reporter = MagicMock()
    reporter.repair_history.return_value = {"history_entries": 0, "updated_entries": 0}

    async def fake_notify(**kwargs):
        return {"configured": 0, "attempted": 0, "delivered": 0, "failed": 0}

    service = PlatformMaintenanceService(min_interval_seconds=0)

    with patch("services.platform_maintenance_service.get_execution_center_service", return_value=execution_center), \
         patch("services.platform_maintenance_service.get_reporter", return_value=reporter), \
         patch("services.platform_maintenance_service.send_completion_notification", side_effect=fake_notify), \
         patch("services.platform_maintenance_service.asyncio.get_running_loop", return_value=object()), \
         patch("services.platform_maintenance_service.get_db_observability", return_value={
             "path": r"D:\demo\business.db",
             "current_db": {"size_bytes": 2048, "updated_at": "2026-03-16T10:05:00"},
             "shadow_paths": [r"D:\legacy\business.db"],
             "shadow_count": 1,
             "risk_level": "warning",
         }):
        result = service.run(force=True, reason="startup")

    assert result["risk_alert_sent"] is False
