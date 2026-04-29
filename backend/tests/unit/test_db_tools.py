import sqlite3
from pathlib import Path

from core import db_tools
from core import db_helper


class _FakeInspector:
    def get_table_names(self):
        return ["service_product", "service_category"]

    def get_columns(self, table_name):
        if table_name == "service_product":
            return [
                {"name": "id", "type": "INTEGER", "nullable": False},
                {"name": "name", "type": "VARCHAR(64)", "nullable": True},
            ]
        return [
            {"name": "id", "type": "INTEGER", "nullable": False},
            {"name": "category_name", "type": "VARCHAR(64)", "nullable": True},
        ]


class _FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_list_db_tables_with_sqlalchemy(monkeypatch):
    fake_conn = _FakeConnection()
    monkeypatch.setattr(db_tools, "get_db_connection", lambda: (fake_conn, "sqlalchemy"))
    monkeypatch.setattr(db_tools, "inspect", lambda conn: _FakeInspector())

    result = db_tools.list_db_tables()

    assert result == {"status": "success", "tables": ["service_product", "service_category"]}
    assert fake_conn.closed is True


def test_get_db_schema_with_sqlalchemy(monkeypatch):
    fake_conn = _FakeConnection()
    monkeypatch.setattr(db_tools, "get_db_connection", lambda: (fake_conn, "sqlalchemy"))
    monkeypatch.setattr(db_tools, "inspect", lambda conn: _FakeInspector())

    schema = db_tools.get_db_schema()

    assert "TABLE service_product" in schema
    assert "id INTEGER NOT NULL" in schema
    assert "name VARCHAR(64)" in schema
    assert "TABLE service_category" in schema
    assert fake_conn.closed is True


def test_list_db_tables_with_sqlite(tmp_path, monkeypatch):
    db_path = tmp_path / "local.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE sample_table (id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit()
    conn.close()

    monkeypatch.setattr(db_tools, "MOCK_DB_PATH", str(db_path))
    monkeypatch.setattr(db_tools.settings, "DB_CONNECTION_STRING", "")

    result = db_tools.list_db_tables()

    assert result["status"] == "success"
    assert "sample_table" in result["tables"]


def test_mock_db_path_uses_canonical_business_db():
    assert Path(db_tools._get_sqlite_path()).resolve() == Path(db_helper.get_db_path()).resolve()


def test_mock_db_path_follows_runtime_db_helper(monkeypatch, tmp_path):
    runtime_db = tmp_path / "runtime.db"
    monkeypatch.setattr(db_tools, "MOCK_DB_PATH", "")
    monkeypatch.setattr(db_helper, "get_db_path", lambda: str(runtime_db))

    assert Path(db_tools._get_sqlite_path()).resolve() == runtime_db.resolve()
