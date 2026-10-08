"""
DatabaseManagerService unit tests.
Covers data classes, connection CRUD, connection tests, tables and columns, data
injection/cleanup/query/validation, security checks, and the singleton.
Uses SQLite :memory: for real database operations.
"""
import pytest
import json
from unittest.mock import patch, MagicMock

from services.database_manager import (
    DatabaseConnection, ValidationRule,
    DatabaseManagerService
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def svc(tmp_path):
    """Create an isolated DatabaseManagerService without reading disk files."""
    with patch("services.database_manager.CONNECTIONS_FILE", tmp_path / "connections.json"):
        s = DatabaseManagerService()
        yield s


def _add_sqlite_memory_conn(svc):
    """Add an in-memory SQLite connection and return its ID."""
    result = svc.create_connection({
        "name": "test_db",
        "db_type": "sqlite",
        "database": ":memory:"
    })
    return result["id"]


# ---------------------------------------------------------------------------
# Data classes.
# ---------------------------------------------------------------------------
class TestDatabaseConnection:
    def test_defaults(self):
        conn = DatabaseConnection()
        assert conn.db_type == "sqlite"
        assert conn.host == "localhost"
        assert conn.port == 3306
        assert len(conn.id) == 8


class TestValidationRule:
    def test_creation(self):
        rule = ValidationRule(table="users", column="name", operator="equals", expected="Alice")
        assert rule.table == "users"
        assert rule.where_clause == ""


# ---------------------------------------------------------------------------
# _validate_identifier security checks.
# ---------------------------------------------------------------------------
class TestValidateIdentifier:
    def test_valid(self):
        assert DatabaseManagerService._validate_identifier("users") is True
        assert DatabaseManagerService._validate_identifier("_private") is True
        assert DatabaseManagerService._validate_identifier("col_123") is True

    def test_invalid(self):
        assert DatabaseManagerService._validate_identifier("123abc") is False
        assert DatabaseManagerService._validate_identifier("drop table") is False
        assert DatabaseManagerService._validate_identifier("") is False
        assert DatabaseManagerService._validate_identifier("a;b") is False


# ---------------------------------------------------------------------------
# Connection CRUD.
# ---------------------------------------------------------------------------
class TestConnectionCRUD:
    def test_create_and_list(self, svc):
        svc.create_connection({"name": "db1", "db_type": "sqlite"})
        conns = svc.list_connections()
        assert len(conns) == 1
        assert conns[0]["name"] == "db1"

    def test_password_masked(self, svc):
        svc.create_connection({"name": "db", "password": "secret123"})
        conns = svc.list_connections()
        assert conns[0]["password"] == "***"

    def test_get_connection(self, svc):
        result = svc.create_connection({"name": "db"})
        conn = svc.get_connection(result["id"])
        assert conn is not None
        assert conn["name"] == "db"

    def test_get_connection_not_found(self, svc):
        assert svc.get_connection("nonexistent") is None

    def test_update_connection(self, svc):
        result = svc.create_connection({"name": "old"})
        updated = svc.update_connection(result["id"], {"name": "new"})
        assert updated["name"] == "new"

    def test_update_password_masked_skipped(self, svc):
        result = svc.create_connection({"name": "db", "password": "real"})
        cid = result["id"]
        svc.update_connection(cid, {"password": "***"})  # Do not overwrite the existing value.
        assert svc.connections[cid].password == "real"

    def test_update_nonexistent(self, svc):
        assert svc.update_connection("none", {"name": "x"}) is None

    def test_delete_connection(self, svc):
        result = svc.create_connection({"name": "db"})
        assert svc.delete_connection(result["id"]) is True
        assert len(svc.connections) == 0

    def test_delete_nonexistent(self, svc):
        assert svc.delete_connection("none") is False

    def test_create_connection_from_connection_string_defaults_to_read_only(self, svc):
        result = svc.create_connection({
            "name": "remote_db",
            "connection_string": "mysql+pymysql://user:pass@db.example.com:3336/ry_cloud",
        })
        conn = svc.connections[result["id"]]
        assert conn.db_type == "mysql"
        assert conn.host == "db.example.com"
        assert conn.port == 3336
        assert conn.database == "ry_cloud"
        assert conn.username == "user"
        assert conn.password == "pass"
        assert conn.read_only is True
        assert result["connection_string"] == "mysql://user:***@db.example.com:3336/ry_cloud"

    def test_save_connections_merges_existing_disk_entries(self, tmp_path):
        connections_file = tmp_path / "connections.json"
        with patch("services.database_manager.CONNECTIONS_FILE", connections_file):
            svc = DatabaseManagerService()
            connections_file.write_text(json.dumps([
                {
                    "id": "remote123",
                    "name": "remote_db",
                    "db_type": "mysql",
                    "host": "db.example.com",
                    "port": 3306,
                    "database": "ry_cloud",
                    "username": "tester",
                    "password": "secret",
                    "read_only": True,
                    "created_at": "2026-03-14T11:00:00",
                }
            ], ensure_ascii=False), encoding="utf-8")

            svc.create_connection({"name": "local_db", "db_type": "sqlite", "database": ":memory:"})
            saved = json.loads(connections_file.read_text(encoding="utf-8"))
        names = {item["name"] for item in saved}
        assert names == {"remote_db", "local_db"}

    def test_delete_connection_removes_persisted_entry_with_merge_enabled(self, tmp_path):
        connections_file = tmp_path / "connections.json"
        connections_file.write_text(json.dumps([
            {
                "id": "remote123",
                "name": "remote_db",
                "db_type": "mysql",
                "host": "db.example.com",
                "port": 3306,
                "database": "ry_cloud",
                "username": "tester",
                "password": "secret",
                "read_only": True,
                "created_at": "2026-03-14T11:00:00",
            }
        ], ensure_ascii=False), encoding="utf-8")
        with patch("services.database_manager.CONNECTIONS_FILE", connections_file):
            svc = DatabaseManagerService()
            assert svc.delete_connection("remote123") is True
            saved = json.loads(connections_file.read_text(encoding="utf-8"))
        assert saved == []


# ---------------------------------------------------------------------------
# test_connection tests.
# ---------------------------------------------------------------------------
class TestTestConnection:
    def test_sqlite_memory(self, svc):
        cid = _add_sqlite_memory_conn(svc)
        result = svc.test_connection(cid)
        assert result["success"] is True

    def test_mysql_real_connection(self, svc):
        r = svc.create_connection({"name": "m", "db_type": "mysql"})
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"ok": 1}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        with patch("pymysql.connect", return_value=mock_conn):
            result = svc.test_connection(r["id"])
        assert result["success"] is True

    def test_unknown_type(self, svc):
        r = svc.create_connection({"name": "x", "db_type": "oracle"})
        result = svc.test_connection(r["id"])
        assert result["success"] is False

    def test_not_found(self, svc):
        result = svc.test_connection("none")
        assert result["success"] is False


# ---------------------------------------------------------------------------
# SQLite data operations: inject, query, clean, and validate.
# Use a real in-memory database.
# ---------------------------------------------------------------------------
class TestSqliteOperations:
    def _make_file_conn(self, svc, tmp_path):
        """Create a file-backed connection to avoid separate :memory: databases per connection."""
        db_path = str(tmp_path / "test.db")
        result = svc.create_connection({
            "name": "file_db", "db_type": "sqlite", "database": db_path
        })
        return result["id"]

    def _setup_table(self, svc, conn_id):
        """Create a test table."""
        import sqlite3
        conn = svc.connections[conn_id]
        db = svc._get_sqlite_connection(conn)
        db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
        db.commit()
        db.close()

    def test_inject_data(self, svc, tmp_path):
        cid = self._make_file_conn(svc, tmp_path)
        self._setup_table(svc, cid)
        result = svc.inject_data(cid, "users", [
            {"id": 1, "name": "Alice", "age": 30},
            {"id": 2, "name": "Bob", "age": 25}
        ])
        assert result["success"] is True
        assert result["inserted"] == 2

    def test_inject_no_data(self, svc):
        cid = _add_sqlite_memory_conn(svc)
        result = svc.inject_data(cid, "users", [])
        assert result["success"] is True
        assert result["inserted"] == 0

    def test_inject_invalid_table_name(self, svc):
        cid = _add_sqlite_memory_conn(svc)
        result = svc.inject_data(cid, "drop table", [{"a": 1}])
        assert result["success"] is False

    def test_inject_invalid_column(self, svc):
        cid = _add_sqlite_memory_conn(svc)
        self._setup_table(svc, cid)
        result = svc.inject_data(cid, "users", [{"name;DROP": "evil"}])
        assert result["success"] is False

    def test_inject_not_found(self, svc):
        result = svc.inject_data("none", "t", [{"a": 1}])
        assert result["success"] is False

    def test_inject_blocked_when_connection_is_read_only(self, svc, tmp_path):
        cid = self._make_file_conn(svc, tmp_path)
        svc.connections[cid].read_only = True
        result = svc.inject_data(cid, "users", [{"id": 1}])
        assert result["success"] is False
        assert result["error"] == "Connection is read-only"


class TestQueryData:
    def test_only_select_allowed(self, svc):
        cid = _add_sqlite_memory_conn(svc)
        result = svc.query_data(cid, "DROP TABLE users")
        assert result["success"] is False

    def test_semicolons_forbidden(self, svc):
        cid = _add_sqlite_memory_conn(svc)
        result = svc.query_data(cid, "SELECT * FROM users; DROP TABLE users")
        assert result["success"] is False

    def test_forbidden_keywords(self, svc):
        cid = _add_sqlite_memory_conn(svc)
        result = svc.query_data(cid, "SELECT * FROM users UNION ALL DELETE FROM users")
        assert result["success"] is False

    def test_query_not_found(self, svc):
        result = svc.query_data("none", "SELECT 1")
        assert result["success"] is False

    def test_mysql_query_supported(self, svc):
        r = svc.create_connection({"name": "m", "db_type": "mysql"})
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [{"id": 1, "name": "Alice"}]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        with patch("pymysql.connect", return_value=mock_conn):
            result = svc.query_data(r["id"], "SELECT id, name FROM users", limit=10)
        assert result["success"] is True
        assert result["count"] == 1
        assert "elapsed_ms" in result
        assert "message" in result

    def test_mysql_connection_retries_once_on_transient_timeout(self, svc):
        r = svc.create_connection({"name": "m", "db_type": "mysql"})
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [{"id": 1}]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        with patch("pymysql.connect", side_effect=[RuntimeError("(2003, timed out)"), mock_conn]) as mock_connect:
            result = svc.query_data(r["id"], "SELECT id FROM users", limit=10)
        assert result["success"] is True
        assert mock_connect.call_count == 2


class TestGetTableColumns:
    def test_mysql_columns_fallback_to_show_full_columns(self, svc):
        result = svc.create_connection({"name": "m", "db_type": "mysql"})
        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = [
            [],
            [
                {"Field": "id", "Type": "bigint", "Null": "NO"},
                {"Field": "name", "Type": "varchar(64)", "Null": "YES"},
            ],
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        with patch("pymysql.connect", return_value=mock_conn):
            columns = svc.get_table_columns(result["id"], "demo_table")
        assert columns == [
            {"name": "id", "type": "bigint", "nullable": False},
            {"name": "name", "type": "varchar(64)", "nullable": True},
        ]


class TestCleanTable:
    def test_clean_invalid_table(self, svc):
        cid = _add_sqlite_memory_conn(svc)
        result = svc.clean_table(cid, "drop table")
        assert result["success"] is False

    def test_clean_forbidden_where(self, svc):
        cid = _add_sqlite_memory_conn(svc)
        result = svc.clean_table(cid, "users", "1=1; DROP TABLE users")
        assert result["success"] is False

    def test_clean_not_found(self, svc):
        result = svc.clean_table("none", "users")
        assert result["success"] is False


class TestGetTables:
    def test_not_found(self, svc):
        assert svc.get_tables("none") == []


class TestGetTableColumns:
    def test_not_found(self, svc):
        assert svc.get_table_columns("none", "users") == []


class TestSchemaOverview:
    def test_generate_schema_text(self, svc, tmp_path):
        db_path = str(tmp_path / "schema.db")
        result = svc.create_connection({
            "name": "schema_db",
            "db_type": "sqlite",
            "database": db_path,
            "read_only": False,
        })
        conn = svc.connections[result["id"]]
        db = svc._get_sqlite_connection(conn)
        db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        db.commit()
        db.close()

        schema = svc.generate_schema_text(result["id"])
        assert schema["success"] is True
        assert "TABLE users" in schema["schema"]
        assert "name TEXT NOT NULL" in schema["schema"]


class TestValidateData:
    def test_not_found(self, svc):
        result = svc.validate_data("none", [])
        assert result["success"] is False

    def test_invalid_table(self, svc):
        cid = _add_sqlite_memory_conn(svc)
        result = svc.validate_data(cid, [
            {"table": "drop table", "column": "x", "operator": "exists", "expected": True}
        ])
        assert result["results"][0]["passed"] is False


# ---------------------------------------------------------------------------
# Singleton.
# ---------------------------------------------------------------------------
class TestSingleton:
    def test_singleton(self):
        import services.database_manager as mod
        mod._service_instance = None
        with patch.object(DatabaseManagerService, "_load_connections"):
            s1 = mod.get_database_manager()
            s2 = mod.get_database_manager()
            assert s1 is s2
        mod._service_instance = None
