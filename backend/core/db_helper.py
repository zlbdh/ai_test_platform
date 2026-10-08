"""
SQLite connection helpers
Provide context managers and query helpers to remove repeated connection/close patterns from main.py
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv

    _CORE_DIR = Path(__file__).resolve().parent
    _BACKEND_DIR = _CORE_DIR.parent
    _WORKSPACE_ROOT = _BACKEND_DIR.parent
    _ENV_PATH = _WORKSPACE_ROOT / ".env"
    load_dotenv(_ENV_PATH, override=False) if _ENV_PATH.exists() else load_dotenv(override=False)
except ImportError:
    _CORE_DIR = Path(__file__).resolve().parent
    _BACKEND_DIR = _CORE_DIR.parent
    _WORKSPACE_ROOT = _BACKEND_DIR.parent


DEFAULT_DB_PATH = str((_BACKEND_DIR / "data" / "business.db").resolve())
DB_PATH = os.getenv("BUSINESS_DB_PATH", DEFAULT_DB_PATH)
LEGACY_DB_CANDIDATES = [
    str((_WORKSPACE_ROOT / "data" / "business.db").resolve()),
]
SHADOW_DB_ARCHIVE_DIR = str((_WORKSPACE_ROOT / "data" / "shadow_db_archive").resolve())


def resolve_db_path(raw_path: Optional[str] = None) -> str:
    """Resolve the database to a stable absolute path independent of the working directory."""
    candidate = raw_path or DB_PATH or DEFAULT_DB_PATH
    if candidate == ":memory:":
        return candidate

    path = Path(candidate)
    if not path.is_absolute():
        path = _BACKEND_DIR / candidate
    return str(path.resolve())


def get_db_path() -> str:
    """Return the active business database path."""
    return resolve_db_path()


def _file_metadata(path: str) -> Dict[str, Any]:
    candidate = Path(path)
    exists = candidate.exists()
    return {
        "path": str(candidate),
        "exists": exists,
        "size_bytes": int(candidate.stat().st_size) if exists else 0,
        "updated_at": datetime.fromtimestamp(candidate.stat().st_mtime).isoformat() if exists else "",
    }


def get_db_observability() -> Dict[str, Any]:
    """Return the database path and potential shadow-database details for runtime diagnostics."""
    current_path = get_db_path()
    shadow_paths = []
    shadow_dbs = []
    if current_path != ":memory:":
        current = Path(current_path).resolve()
        for candidate in LEGACY_DB_CANDIDATES:
            resolved_candidate = Path(candidate).resolve()
            if resolved_candidate != current and resolved_candidate.exists():
                resolved = str(resolved_candidate)
                shadow_paths.append(resolved)
                shadow_dbs.append(_file_metadata(resolved))

    current_db = {
        "path": current_path,
        "exists": current_path == ":memory:" or Path(current_path).exists(),
        "size_bytes": 0,
        "updated_at": "",
    }
    if current_path != ":memory:":
        current_db = _file_metadata(current_path)

    return {
        "path": current_path,
        "is_memory": current_path == ":memory:",
        "current_db": current_db,
        "shadow_paths": shadow_paths,
        "shadow_dbs": shadow_dbs,
        "shadow_count": len(shadow_paths),
        "risk_level": "warning" if shadow_paths else "normal",
    }


def quarantine_shadow_databases(reason: str = "ops_quarantine") -> Dict[str, Any]:
    """Isolate a shadow business database without deleting it: move it to an archive directory with a timestamp."""
    observability = get_db_observability()
    current_path = observability.get("path") or ""
    archive_dir = Path(SHADOW_DB_ARCHIVE_DIR)
    archive_dir.mkdir(parents=True, exist_ok=True)

    moved: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for item in observability.get("shadow_dbs") or []:
        source_path = str(item.get("path") or "")
        if not source_path:
            continue
        source = Path(source_path)
        if str(source.resolve()) == str(Path(current_path).resolve()):
            skipped.append({"path": source_path, "reason": "is_current_db"})
            continue
        if not source.exists():
            skipped.append({"path": source_path, "reason": "missing"})
            continue

        suffix = "".join(source.suffixes) or ".db"
        stem = source.name[:-len(suffix)] if suffix and source.name.endswith(suffix) else source.stem
        destination = archive_dir / f"{stem}.shadow_{reason}_{timestamp}{suffix}"
        counter = 1
        while destination.exists():
            destination = archive_dir / f"{stem}.shadow_{reason}_{timestamp}_{counter}{suffix}"
            counter += 1
        try:
            shutil.move(str(source), str(destination))
            moved.append(
                {
                    "source_path": str(source.resolve()),
                    "archived_path": str(destination.resolve()),
                    "size_bytes": int(item.get("size_bytes") or 0),
                }
            )
        except Exception as exc:
            skipped.append({"path": source_path, "reason": f"move_failed:{exc}"})

    refreshed = get_db_observability()
    return {
        "reason": reason,
        "archive_dir": str(archive_dir),
        "moved_count": len(moved),
        "moved": moved,
        "skipped_count": len(skipped),
        "skipped": skipped,
        "observability": refreshed,
    }


def init_db():
    """Initialize the database and required tables"""
    db_path = get_db_path()
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS test_records
                     (id TEXT PRIMARY KEY, timestamp TEXT, goal TEXT, status TEXT, logs_json TEXT)''')


@contextmanager
def get_connection():
    """SQLite connection context manager that commits and closes automatically"""
    db_path = get_db_path()
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query_one(sql: str, params: tuple = ()) -> Optional[dict]:
    """Run a query and return one row as a dictionary, or None if there is no result"""
    with get_connection() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def query_all(sql: str, params: tuple = ()) -> List[dict]:
    """Run a query and return all rows as a list of dictionaries"""
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def execute(sql: str, params: tuple = ()) -> int:
    """Execute a write and return the affected row count"""
    with get_connection() as conn:
        cursor = conn.execute(sql, params)
        return cursor.rowcount


def execute_safe(sql: str, params: tuple = ()) -> int:
    """Execute a write, ignore operational errors such as missing tables, and return the affected row count"""
    try:
        return execute(sql, params)
    except sqlite3.OperationalError:
        return 0
