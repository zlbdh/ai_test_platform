import datetime
import logging
import os
import shutil
import sqlite3
from typing import Any, Dict, List

from sqlalchemy import create_engine, inspect, text

from core.config import Config as settings
from core import db_helper

logger = logging.getLogger(__name__)

# Optional override for tests or controlled fallback scenarios.
MOCK_DB_PATH = ""


def _get_sqlite_path() -> str:
    """默认跟随平台正式业务库路径，必要时允许测试覆盖。"""
    candidate = MOCK_DB_PATH or db_helper.get_db_path()
    return db_helper.resolve_db_path(candidate)

FORBIDDEN_KEYWORDS = ["DROP", "TRUNCATE", "ALTER", "GRANT", "REVOKE"]


def get_db_connection():
    """
    Get a database connection based on configuration.
    Priority:
    1. DB_CONNECTION_STRING (if set) -> SQLAlchemy
    2. Fallback -> Local SQLite
    """
    conn_str = getattr(settings, "DB_CONNECTION_STRING", None)

    if conn_str and conn_str.strip():
        try:
            engine = create_engine(conn_str, pool_pre_ping=True)
            return engine.connect(), "sqlalchemy"
        except Exception as exc:
            logger.error("Failed to connect to external DB: %s", exc)

    sqlite_path = _get_sqlite_path()
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"


def execute_sql(sql: str, allow_unsafe: bool = False) -> Dict[str, Any]:
    """
    Execute a generic SQL query (SELECT, INSERT, UPDATE, DELETE).
    SafeMode: Blocks dangerous commands unless allow_unsafe=True.
    """
    normalized_sql = sql.strip().upper()
    if not allow_unsafe:
        for keyword in FORBIDDEN_KEYWORDS:
            if f" {keyword} " in f" {normalized_sql} " or normalized_sql.startswith(keyword):
                return {
                    "status": "error",
                    "message": f"🚫 Security Constraint: Execution of '{keyword}' is forbidden.",
                }

    try:
        conn, conn_type = get_db_connection()
        result: Dict[str, Any]

        if conn_type == "sqlalchemy":
            try:
                res = conn.execute(text(sql))
                if normalized_sql.startswith("SELECT"):
                    data = [dict(row._mapping) for row in res]
                    result = {"status": "success", "data": data, "count": len(data)}
                else:
                    conn.commit()
                    result = {"status": "success", "affected_rows": res.rowcount}
            finally:
                conn.close()
        else:
            try:
                cursor = conn.cursor()
                cursor.execute(sql)
                if normalized_sql.startswith("SELECT"):
                    rows = cursor.fetchall()
                    data = [dict(row) for row in rows]
                    result = {"status": "success", "data": data, "count": len(data)}
                else:
                    conn.commit()
                    result = {"status": "success", "affected_rows": cursor.rowcount}
            finally:
                conn.close()

        return result
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def list_db_tables() -> Dict[str, Any]:
    """Return the visible tables for the configured database."""
    try:
        conn, conn_type = get_db_connection()
        try:
            if conn_type == "sqlalchemy":
                table_names = inspect(conn).get_table_names()
                return {"status": "success", "tables": table_names}

            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall() if row and row[0]]
            return {"status": "success", "tables": tables}
        finally:
            conn.close()
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_db_schema() -> str:
    """Helper to let AI know table structure."""
    try:
        conn, conn_type = get_db_connection()
        try:
            if conn_type == "sqlalchemy":
                inspector = inspect(conn)
                table_names = inspector.get_table_names()
                if not table_names:
                    return "No tables found."

                schema_parts: List[str] = []
                for table_name in table_names:
                    columns = inspector.get_columns(table_name)
                    column_defs = []
                    for column in columns:
                        column_name = column.get("name", "unknown")
                        column_type = str(column.get("type", "UNKNOWN"))
                        nullable = "" if column.get("nullable", True) else " NOT NULL"
                        default = column.get("default")
                        default_clause = f" DEFAULT {default}" if default is not None else ""
                        column_defs.append(f"  {column_name} {column_type}{nullable}{default_clause}")
                    schema_parts.append(f"TABLE {table_name}:\n" + "\n".join(column_defs))
                return "\n\n".join(schema_parts)

            cursor = conn.cursor()
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            schema = "\n".join([table[0] for table in tables if table[0]])
            return schema if schema else "No tables found."
        finally:
            conn.close()
    except Exception as exc:
        logger.error("Could not retrieve schema: %s", exc)
        return f"Could not retrieve schema: {exc}"


# === New Tools for Safety Upgrade ===

def backup_db(table_name: str = None) -> Dict[str, Any]:
    """
    Backup database or specific table.
    """
    try:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "backups")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        conn_str = getattr(settings, "DB_CONNECTION_STRING", "")
        sqlite_path = _get_sqlite_path()

        if not conn_str or "sqlite" in conn_str or not conn_str.strip():
            if os.path.exists(sqlite_path):
                filename = os.path.basename(sqlite_path)
                backup_path = os.path.join(output_dir, f"{timestamp}_{filename}")
                shutil.copy2(sqlite_path, backup_path)
                return {"status": "success", "message": f"SQLite Backup created at {backup_path}"}
            return {"status": "error", "message": "DB file not found"}

        return {
            "status": "warning",
            "message": "Remote DB backup requires manual verified tools. Please run `scripts/backup_db.py`.",
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def snapshot_db(table: str, condition: str) -> Dict[str, Any]:
    """
    Take a snapshot of data for later comparison.
    Example: snapshot_db('users', 'id=1')
    """
    import re

    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table):
        return {"status": "error", "message": f"Invalid table name: {table}"}

    condition_upper = condition.strip().upper()
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in condition_upper:
            return {"status": "error", "message": f"Forbidden keyword in condition: {keyword}"}

    sql = f"SELECT * FROM {table} WHERE {condition}"
    return execute_sql(sql)


def diff_db(snapshot_data: List[Dict], table: str, condition: str) -> Dict[str, Any]:
    """
    Compare current DB state with snapshot (全行比较).
    """
    current_res = snapshot_db(table, condition)
    if current_res.get("status") == "error":
        return current_res

    current_data = current_res.get("data", [])

    if len(current_data) != len(snapshot_data):
        return {
            "status": "diff",
            "message": f"Row count changed: {len(snapshot_data)} -> {len(current_data)}",
            "before": snapshot_data,
            "after": current_data,
        }

    diffs = []
    for idx, (row_old, row_now) in enumerate(zip(snapshot_data, current_data)):
        row_diffs = []
        all_keys = set(list(row_old.keys()) + list(row_now.keys()))
        for key in all_keys:
            old_val = str(row_old.get(key, "<missing>"))
            new_val = str(row_now.get(key, "<missing>"))
            if old_val != new_val:
                row_diffs.append(f"{key}: {old_val} -> {new_val}")
        if row_diffs:
            diffs.append({"row": idx, "changes": row_diffs})

    if diffs:
        return {
            "status": "diff",
            "message": f"Content changed in {len(diffs)} row(s)",
            "details": diffs,
            "before": snapshot_data,
            "after": current_data,
        }

    return {"status": "same", "message": "No changes detected"}
