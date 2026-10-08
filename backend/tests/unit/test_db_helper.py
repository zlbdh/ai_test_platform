"""
Tests for core.db_helper module
"""
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core import db_helper


class TestDbHelper:
    """Tests for db_helper context managers and convenience methods."""

    def setup_method(self):
        """Use a temporary database for each test."""
        self._original_db_path = db_helper.DB_PATH
        self._original_backend_dir = db_helper._BACKEND_DIR
        self._original_legacy_candidates = list(db_helper.LEGACY_DB_CANDIDATES)
        # Create the table using get_connection because each :memory: connection is isolated.
        # Use a temporary file instead.
        import tempfile
        self._tmpfile = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self._tmpfile.close()
        db_helper.DB_PATH = self._tmpfile.name
        # Create a test table.
        with db_helper.get_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS test_items (id INTEGER PRIMARY KEY, name TEXT, value TEXT)")

    def teardown_method(self):
        db_helper.DB_PATH = self._original_db_path
        db_helper._BACKEND_DIR = self._original_backend_dir
        db_helper.LEGACY_DB_CANDIDATES = self._original_legacy_candidates
        try:
            os.unlink(self._tmpfile.name)
        except Exception:
            pass

    def test_get_connection_context_manager(self):
        """The context manager should commit and close automatically."""
        with db_helper.get_connection() as conn:
            conn.execute("INSERT INTO test_items (name, value) VALUES (?, ?)", ("key1", "val1"))
        
        # Verify persistence using a new connection.
        row = db_helper.query_one("SELECT * FROM test_items WHERE name=?", ("key1",))
        assert row is not None
        assert row["value"] == "val1"

    def test_get_connection_rollback_on_error(self):
        """Roll back when an exception occurs."""
        try:
            with db_helper.get_connection() as conn:
                conn.execute("INSERT INTO test_items (name, value) VALUES (?, ?)", ("bad", "data"))
                raise ValueError("Simulated error")
        except ValueError:
            pass
        
        row = db_helper.query_one("SELECT * FROM test_items WHERE name=?", ("bad",))
        assert row is None

    def test_query_one_found(self):
        with db_helper.get_connection() as conn:
            conn.execute("INSERT INTO test_items (name, value) VALUES (?, ?)", ("a", "1"))
        
        result = db_helper.query_one("SELECT * FROM test_items WHERE name=?", ("a",))
        assert result is not None
        assert result["name"] == "a"

    def test_query_one_not_found(self):
        result = db_helper.query_one("SELECT * FROM test_items WHERE name=?", ("nonexistent",))
        assert result is None

    def test_query_all(self):
        with db_helper.get_connection() as conn:
            conn.execute("INSERT INTO test_items (name, value) VALUES (?, ?)", ("x", "1"))
            conn.execute("INSERT INTO test_items (name, value) VALUES (?, ?)", ("y", "2"))
        
        results = db_helper.query_all("SELECT * FROM test_items ORDER BY name")
        assert len(results) == 2
        assert results[0]["name"] == "x"
        assert results[1]["name"] == "y"

    def test_execute(self):
        with db_helper.get_connection() as conn:
            conn.execute("INSERT INTO test_items (name, value) VALUES (?, ?)", ("del", "me"))
        
        affected = db_helper.execute("DELETE FROM test_items WHERE name=?", ("del",))
        assert affected == 1

    def test_execute_safe_ignores_operational_error(self):
        """execute_safe should ignore missing-table errors."""
        affected = db_helper.execute_safe("DELETE FROM nonexistent_table WHERE id=1")
        assert affected == 0

    def test_concurrent_writes(self):
        """Concurrent writes from multiple threads should not lose data."""
        errors = []

        def writer(tid):
            try:
                for i in range(20):
                    db_helper.execute(
                        "INSERT INTO test_items (name, value) VALUES (?, ?)",
                        (f"t{tid}_i{i}", f"val_{i}")
                    )
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=writer, args=(tid,)) for tid in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Concurrent write errors: {errors}"
        results = db_helper.query_all("SELECT COUNT(*) as cnt FROM test_items")
        assert results[0]["cnt"] == 100  # 5 threads * 20 inserts

    def test_get_db_path_is_absolute_and_independent_of_cwd(self, tmp_path, monkeypatch):
        backend_dir = tmp_path / "backend"
        monkeypatch.setattr(db_helper, "_BACKEND_DIR", backend_dir)
        db_helper.DB_PATH = os.path.join("data", "business.db")

        first_cwd = tmp_path / "cwd1"
        second_cwd = tmp_path / "cwd2"
        first_cwd.mkdir()
        second_cwd.mkdir()

        monkeypatch.chdir(first_cwd)
        first_path = db_helper.get_db_path()

        monkeypatch.chdir(second_cwd)
        second_path = db_helper.get_db_path()

        expected = str((backend_dir / "data" / "business.db").resolve())
        assert first_path == expected
        assert second_path == expected

    def test_get_db_path_supports_business_db_path_env(self, tmp_path, monkeypatch):
        backend_dir = tmp_path / "backend"
        backend_dir.mkdir()
        monkeypatch.setattr(db_helper, "_BACKEND_DIR", backend_dir)
        db_helper.DB_PATH = "ignored-by-test.db"

        env_db = str((tmp_path / "custom" / "business.db").resolve())
        monkeypatch.setenv("BUSINESS_DB_PATH", env_db)

        db_helper.DB_PATH = os.getenv("BUSINESS_DB_PATH", db_helper.DEFAULT_DB_PATH)
        assert db_helper.get_db_path() == env_db

    def test_get_db_observability_reports_shadow_db(self, tmp_path):
        current_db = tmp_path / "backend" / "data" / "business.db"
        current_db.parent.mkdir(parents=True)
        current_db.write_text("main", encoding="utf-8")
        shadow_db = tmp_path / "workspace" / "data" / "business.db"
        shadow_db.parent.mkdir(parents=True)
        shadow_db.write_text("shadow", encoding="utf-8")

        db_helper.DB_PATH = str(current_db)
        db_helper.LEGACY_DB_CANDIDATES = [str(shadow_db)]

        observability = db_helper.get_db_observability()
        assert observability["path"] == str(current_db.resolve())
        assert observability["shadow_paths"] == [str(shadow_db.resolve())]
        assert observability["shadow_count"] == 1
        assert observability["risk_level"] == "warning"
        assert observability["current_db"]["size_bytes"] > 0
        assert observability["shadow_dbs"][0]["size_bytes"] > 0

    def test_quarantine_shadow_databases_moves_shadow_files_to_archive(self, tmp_path):
        current_db = tmp_path / "backend" / "data" / "business.db"
        current_db.parent.mkdir(parents=True)
        current_db.write_text("main", encoding="utf-8")
        shadow_db = tmp_path / "workspace" / "data" / "business.db"
        shadow_db.parent.mkdir(parents=True)
        shadow_db.write_text("shadow", encoding="utf-8")
        archive_dir = tmp_path / "archive"

        db_helper.DB_PATH = str(current_db)
        db_helper.LEGACY_DB_CANDIDATES = [str(shadow_db)]
        db_helper.SHADOW_DB_ARCHIVE_DIR = str(archive_dir)

        result = db_helper.quarantine_shadow_databases("test_quarantine")

        assert result["moved_count"] == 1
        assert result["skipped_count"] == 0
        assert not shadow_db.exists()
        archived_path = result["moved"][0]["archived_path"]
        assert os.path.exists(archived_path)
        assert result["observability"]["shadow_count"] == 0
        assert result["observability"]["risk_level"] == "normal"
