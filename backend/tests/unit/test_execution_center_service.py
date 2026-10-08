# -*- coding: utf-8 -*-
import sqlite3
from unittest.mock import patch

from services.execution_center_service import ExecutionCenterService


def test_upsert_and_ignore(tmp_path):
    db_path = tmp_path / "business.db"
    real_connect = sqlite3.connect

    def _connect(*args, **kwargs):
        conn = real_connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    svc = ExecutionCenterService()

    with patch("core.db_helper.sqlite3.connect", side_effect=_connect):
        svc.upsert_run(
            task_id="performance_demo",
            requirement="性能测试 · http://example.com",
            status="failed",
            target_url="http://example.com",
            mode="performance",
            logs=[{"type": "assertion", "status": "fail", "content": "HTTP 401"}],
            duration_ms=1200,
            execution_group_id="batch_demo",
            group_title="服务商品中心全链路测试",
            record_kind="child",
        )
        svc.upsert_run(
            task_id="performance_demo",
            requirement="性能测试 · http://example.com",
            status="success",
            target_url="http://example.com",
            mode="performance",
            logs=[{"type": "assertion", "status": "pass", "content": "HTTP 200"}],
            duration_ms=800,
            execution_group_id="batch_demo",
            group_title="服务商品中心全链路测试",
            record_kind="child",
        )

        conn = _connect()
        row = conn.execute("SELECT task_id, status, duration_ms, execution_group_id, record_kind FROM test_runs WHERE task_id='performance_demo'").fetchone()
        assert row["status"] == "success"
        assert row["duration_ms"] == 800
        assert row["execution_group_id"] == "batch_demo"
        assert row["record_kind"] == "child"

        grouped = svc.list_grouped_runs(limit=10)
        assert grouped["total"] == 1
        assert grouped["items"][0]["group_id"] == "batch_demo"
        assert grouped["items"][0]["record_count"] == 1
        assert grouped["items"][0]["records"][0]["task_id"] == "performance_demo"

        svc.mark_ignored(["security_demo"])
        svc.upsert_run(
            task_id="security_demo",
            requirement="安全扫描 · http://example.com",
            status="failed",
            target_url="http://example.com",
            mode="security",
            logs=[{"type": "assertion", "status": "fail", "content": "High risk"}],
        )
        ignored = conn.execute("SELECT COUNT(*) AS c FROM test_runs WHERE task_id='security_demo'").fetchone()
        assert ignored["c"] == 0
        conn.close()


def test_record_database_result_keeps_duration_and_repairs_placeholder_titles(tmp_path):
    db_path = tmp_path / "business.db"
    real_connect = sqlite3.connect

    def _connect(*args, **kwargs):
        conn = real_connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    svc = ExecutionCenterService()

    with patch("core.db_helper.sqlite3.connect", side_effect=_connect):
        conn = _connect()
        svc._ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO execution_groups (group_id, title, requirement, status, target_url, mode, source, root_task_id, session_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "batch_bad",
                "???? ? ry_cloud",
                "???? ? ry_cloud",
                "success",
                "ry_cloud",
                "database",
                "execution-center",
                "batch_bad",
                "sess_bad",
                "2026-03-14 10:00:00",
                "2026-03-14 10:00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO test_runs (task_id, requirement, status, log_count, error_count, duration_ms, target_url, mode, logs_json, execution_group_id, record_kind, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "api_workbench_bad",
                "API 工作台 · ??????",
                "success",
                1,
                0,
                0,
                "http://127.0.0.1:8020/api/health",
                "api_workbench",
                "[]",
                "batch_bad",
                "child",
                "2026-03-14 10:00:00",
            ),
        )
        conn.commit()
        conn.close()

        svc.record_database_result(
            action="查询",
            connection_name="ry_cloud_readonly_live",
            db_type="mysql",
            database="ry_cloud",
            success=True,
            message="查询完成，返回 1 行，用时 321 ms",
            duration_ms=321,
            execution_group_id="batch_bad",
            session_id="sess_bad",
            group_title="Specialized Test · ry_cloud",
        )

        grouped = svc.list_grouped_runs(limit=10)
        batch = next(item for item in grouped["items"] if item["group_id"] == "batch_bad")
        assert batch["title"] == "Specialized Test · ry_cloud"
        assert batch["duration_ms"] == 321
        repaired_child = next(item for item in batch["records"] if item["task_id"] == "api_workbench_bad")
        assert repaired_child["requirement"] == "API Workbench · http://127.0.0.1:8020/api/health"


def test_repair_text_artifacts_reports_repaired_counts(tmp_path):
    db_path = tmp_path / "business.db"
    real_connect = sqlite3.connect

    def _connect(*args, **kwargs):
        conn = real_connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    svc = ExecutionCenterService()

    with patch("core.db_helper.sqlite3.connect", side_effect=_connect):
        conn = _connect()
        svc._ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO execution_groups (group_id, title, requirement, status, target_url, mode, source, root_task_id, session_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "batch_fix",
                "???? ? ry_cloud",
                "???? ? ry_cloud",
                "success",
                "ry_cloud",
                "database",
                "execution-center",
                "batch_fix",
                "",
                "2026-03-14 10:00:00",
                "2026-03-14 10:00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO test_runs (task_id, requirement, status, log_count, error_count, duration_ms, target_url, mode, logs_json, execution_group_id, record_kind, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "api_fix",
                "API 工作台 · ??????",
                "success",
                1,
                0,
                0,
                "http://127.0.0.1:8020/api/health",
                "api_workbench",
                "[]",
                "batch_fix",
                "child",
                "2026-03-14 10:00:00",
            ),
        )
        conn.commit()
        conn.close()

        stats = svc.repair_text_artifacts()
        assert stats["group_updates"] >= 1
        assert stats["record_updates"] >= 1

        conn = _connect()
        group_row = conn.execute(
            "SELECT title, requirement FROM execution_groups WHERE group_id = 'batch_fix'"
        ).fetchone()
        run_row = conn.execute(
            "SELECT requirement FROM test_runs WHERE task_id = 'api_fix'"
        ).fetchone()
        conn.close()

        assert group_row["title"] == "Specialized Test · ry_cloud"
        assert group_row["requirement"] == "Specialized Test · ry_cloud"
        assert run_row["requirement"] == "API Workbench · http://127.0.0.1:8020/api/health"


def test_commander_group_keeps_commander_mode_when_smart_root_exists(tmp_path):
    db_path = tmp_path / "business.db"
    real_connect = sqlite3.connect

    def _connect(*args, **kwargs):
        conn = real_connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    svc = ExecutionCenterService()

    with patch("core.db_helper.sqlite3.connect", side_effect=_connect):
        svc.ensure_group(
            group_id="mission_demo",
            title="军团测试 · 登录回归",
            requirement="登录回归",
            target_url="http://example.com/login",
            mode="commander",
            source="commander",
            root_task_id="mission_demo",
            session_id="commander_mission_demo",
            status="running",
        )
        svc.upsert_run(
            task_id="task_ui_demo",
            requirement="登录回归",
            status="success",
            target_url="http://example.com/login",
            mode="smart",
            logs=[{"type": "observation", "content": "UI 通过"}],
            duration_ms=1200,
            execution_group_id="mission_demo",
            session_id="commander_mission_demo",
            group_title="军团测试 · 登录回归",
            record_kind="root",
        )
        svc.upsert_run(
            task_id="mission_demo",
            requirement="军团任务 · 登录回归",
            status="failed",
            target_url="http://example.com/login",
            mode="commander",
            logs=[{"type": "error", "content": "API 登录失败"}],
            duration_ms=1800,
            execution_group_id="mission_demo",
            session_id="commander_mission_demo",
            group_title="军团测试 · 登录回归",
            record_kind="child",
        )

        grouped = svc.list_grouped_runs(limit=10)
        group = next(item for item in grouped["items"] if item["group_id"] == "mission_demo")
        assert group["mode"] == "commander"


def test_upsert_run_keeps_display_requirement_and_text_state_metadata(tmp_path):
    db_path = tmp_path / "business.db"
    real_connect = sqlite3.connect

    def _connect(*args, **kwargs):
        conn = real_connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    svc = ExecutionCenterService()

    with patch("core.db_helper.sqlite3.connect", side_effect=_connect):
        svc.upsert_run(
            task_id="task_encoding_guard",
            requirement="https://example.com/login",
            requirement_display="https://example.com/login",
            requirement_raw="??????? Wave0 ???????",
            task_text_state="broken_fallback",
            status="success",
            target_url="https://example.com/login",
            mode="smart",
            logs=[{"type": "system", "event": "text_encoding_fallback", "content": "需求文本疑似编码损坏，已回退为可读标题。"}],
            execution_group_id="batch_encoding_guard",
            group_title="https://example.com/login",
            record_kind="root",
        )

        grouped = svc.list_grouped_runs(limit=10)
        group = next(item for item in grouped["items"] if item["group_id"] == "batch_encoding_guard")
        record = next(item for item in group["records"] if item["task_id"] == "task_encoding_guard")

        assert group["requirement_display"] == "https://example.com/login"
        assert group["task_text_state"] == "broken_fallback"
        assert group["requirement_raw_present"] == 1
        assert record["requirement"] == "https://example.com/login"
        assert record["requirement_display"] == "https://example.com/login"
        assert record["task_text_state"] == "broken_fallback"
        assert record["requirement_raw_present"] == 1
