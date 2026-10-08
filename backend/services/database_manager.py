"""
Database Manager Service - Database Connection & Data Validation

Provides:
- Multiple database connection management (SQLite, MySQL, PostgreSQL)
- Data injection into tables
- Data cleanup
- Data validation/assertion
"""

import logging
import os
import json
import re
import time
import uuid
import sqlite3
from urllib.parse import urlparse, unquote
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

# Data directory
DATA_DIR = Path(__file__).parent.parent / "data" / "database_manager"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CONNECTIONS_FILE = DATA_DIR / "connections.json"


@dataclass
class DatabaseConnection:
    """Database connection configuration"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "New Connection"
    db_type: str = "sqlite"  # sqlite, mysql, postgresql
    host: str = "localhost"
    port: int = 3306
    database: str = ""
    username: str = ""
    password: str = ""  # Note: In production, use secure storage
    read_only: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ValidationRule:
    """Data validation rule"""
    table: str
    column: str
    operator: str  # equals, not_equals, greater_than, less_than, contains, exists, count_equals
    expected: Any
    where_clause: str = ""


class DatabaseManagerService:
    """Database connection and data management service"""

    # SQL identifier validation: allow letters, digits, and underscores; the first character cannot be a digit
    _IDENTIFIER_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

    @staticmethod
    def _validate_identifier(name: str) -> bool:
        """Validate the safety of SQL table and column identifiers"""
        return bool(DatabaseManagerService._IDENTIFIER_RE.match(name))

    def __init__(self):
        self.connections: Dict[str, DatabaseConnection] = {}
        self._deleted_connection_ids: Set[str] = set()
        self._load_connections()

    def _load_connections(self):
        """Load connections from disk"""
        if CONNECTIONS_FILE.exists():
            try:
                with open(CONNECTIONS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for conn_data in data:
                        conn_data.setdefault("read_only", conn_data.get("db_type") != "sqlite")
                        conn = DatabaseConnection(**conn_data)
                        self.connections[conn.id] = conn
            except Exception as e:
                logger.error(f"Error loading database connections: {e}")

    def _save_connections(self):
        """Save connections to disk"""
        persisted: Dict[str, Dict[str, Any]] = {}
        if CONNECTIONS_FILE.exists():
            try:
                with open(CONNECTIONS_FILE, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                if isinstance(existing_data, list):
                    for conn_data in existing_data:
                        conn_id = str(conn_data.get("id") or "")
                        if not conn_id or conn_id in self._deleted_connection_ids:
                            continue
                        persisted[conn_id] = conn_data
            except Exception as e:
                logger.warning(f"Error reading existing database connections for merge: {e}")

        for conn in self.connections.values():
            persisted[conn.id] = asdict(conn)

        data = list(persisted.values())
        with open(CONNECTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _normalize_db_type(raw_type: str) -> str:
        value = (raw_type or "sqlite").lower()
        if value.startswith("mysql"):
            return "mysql"
        if value.startswith("postgresql") or value.startswith("postgres"):
            return "postgresql"
        if value.startswith("sqlite"):
            return "sqlite"
        return value

    def _parse_connection_string(self, connection_string: str) -> Dict[str, Any]:
        parsed = urlparse(connection_string)
        db_type = self._normalize_db_type(parsed.scheme.split("+")[0] if parsed.scheme else "")
        if db_type == "sqlite":
            database = unquote(parsed.path.lstrip("/")) or ":memory:"
            return {
                "db_type": "sqlite",
                "database": database,
                "host": "",
                "port": 0,
                "username": "",
                "password": "",
            }
        return {
            "db_type": db_type,
            "host": parsed.hostname or "localhost",
            "port": parsed.port or (3306 if db_type == "mysql" else 5432),
            "database": unquote(parsed.path.lstrip("/")),
            "username": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
        }

    def _build_connection_string(self, conn: DatabaseConnection, mask_password: bool = True) -> str:
        db_type = self._normalize_db_type(conn.db_type)
        if db_type == "sqlite":
            return f"sqlite:///{conn.database}"
        password = conn.password or ""
        if mask_password and password:
            password = "***"
        auth = conn.username or ""
        if password:
            auth = f"{auth}:{password}"
        if auth:
            auth = f"{auth}@"
        return f"{db_type}://{auth}{conn.host}:{conn.port}/{conn.database}"

    def _serialize_connection(self, conn: DatabaseConnection) -> Dict[str, Any]:
        result = asdict(conn)
        result["password"] = "***" if conn.password else ""
        result["connection_string"] = self._build_connection_string(conn, mask_password=True)
        return result

    @staticmethod
    def _default_read_only(data: Dict[str, Any]) -> bool:
        if "read_only" in data:
            return bool(data["read_only"])
        db_type = DatabaseManagerService._normalize_db_type(data.get("db_type", "sqlite"))
        if data.get("connection_string"):
            db_type = DatabaseManagerService._normalize_db_type(
                urlparse(str(data["connection_string"])).scheme.split("+")[0]
            )
        return db_type != "sqlite"

    # ==================== Connection Management ====================

    def list_connections(self) -> List[Dict]:
        """List all database connections"""
        return [self._serialize_connection(conn) for conn in self.connections.values()]

    def get_connection(self, conn_id: str) -> Optional[Dict]:
        """Get a specific connection"""
        conn = self.connections.get(conn_id)
        if conn:
            return self._serialize_connection(conn)
        return None

    def create_connection(self, data: Dict) -> Dict:
        """Create a new database connection"""
        normalized = dict(data)
        connection_string = normalized.get("connection_string")
        if connection_string:
            normalized.update(self._parse_connection_string(str(connection_string)))
        normalized["db_type"] = self._normalize_db_type(normalized.get("db_type", "sqlite"))
        conn = DatabaseConnection(
            name=normalized.get('name', 'New Connection'),
            db_type=normalized.get('db_type', 'sqlite'),
            host=normalized.get('host', 'localhost'),
            port=normalized.get('port', 3306),
            database=normalized.get('database', ''),
            username=normalized.get('username', ''),
            password=normalized.get('password', ''),
            read_only=self._default_read_only(normalized),
        )
        self._deleted_connection_ids.discard(conn.id)
        self.connections[conn.id] = conn
        self._save_connections()
        return self.get_connection(conn.id)

    def update_connection(self, conn_id: str, data: Dict) -> Optional[Dict]:
        """Update a database connection"""
        conn = self.connections.get(conn_id)
        if not conn:
            return None

        normalized = dict(data)
        connection_string = normalized.get("connection_string")
        if connection_string:
            normalized.update(self._parse_connection_string(str(connection_string)))
        if 'db_type' in normalized:
            normalized['db_type'] = self._normalize_db_type(normalized['db_type'])

        if 'name' in normalized:
            conn.name = normalized['name']
        if 'db_type' in normalized:
            conn.db_type = normalized['db_type']
        if 'host' in normalized:
            conn.host = normalized['host']
        if 'port' in normalized:
            conn.port = normalized['port']
        if 'database' in normalized:
            conn.database = normalized['database']
        if 'username' in normalized:
            conn.username = normalized['username']
        if 'password' in normalized and normalized['password'] != '***':
            conn.password = normalized['password']
        if 'read_only' in normalized:
            conn.read_only = bool(normalized['read_only'])

        self._deleted_connection_ids.discard(conn_id)
        self._save_connections()
        return self.get_connection(conn_id)

    def delete_connection(self, conn_id: str) -> bool:
        """Delete a database connection"""
        if conn_id in self.connections:
            del self.connections[conn_id]
            self._deleted_connection_ids.add(conn_id)
            self._save_connections()
            return True
        return False

    # ==================== Connection Testing ====================

    def _get_sqlite_connection(self, conn: DatabaseConnection):
        """Get SQLite connection"""
        db_path = conn.database
        if db_path == ":memory:":
            return sqlite3.connect(":memory:")
        if not os.path.isabs(db_path):
            db_path = str(DATA_DIR / db_path)
        return sqlite3.connect(db_path)

    def _get_mysql_connection(self, conn: DatabaseConnection):
        """Get MySQL connection via PyMySQL."""
        import pymysql
        last_error: Optional[Exception] = None
        for attempt in range(2):
            try:
                return pymysql.connect(
                    host=conn.host,
                    port=int(conn.port or 3306),
                    user=conn.username,
                    password=conn.password,
                    database=conn.database,
                    charset="utf8mb4",
                    autocommit=True,
                    connect_timeout=5,
                    read_timeout=10,
                    write_timeout=10,
                    cursorclass=pymysql.cursors.DictCursor,
                )
            except Exception as exc:
                last_error = exc
                error_text = str(exc).lower()
                retryable = any(
                    token in error_text for token in (
                        "timed out",
                        "timeout",
                        "can't connect to mysql server",
                        "lost connection",
                        "connection reset",
                    )
                )
                if attempt == 1 or not retryable:
                    raise
                logger.warning(
                    "Transient MySQL connection error for %s:%s/%s, retrying once: %s",
                    conn.host,
                    conn.port,
                    conn.database,
                    exc,
                )
                time.sleep(0.3)
        if last_error:
            raise last_error
        raise RuntimeError("Unexpected MySQL connection error")

    def test_connection(self, conn_id: str) -> Dict:
        """Test a database connection"""
        conn = self.connections.get(conn_id)
        if not conn:
            return {"success": False, "error": "Connection not found"}

        try:
            if conn.db_type == 'sqlite':
                db_conn = self._get_sqlite_connection(conn)
                cursor = db_conn.cursor()
                cursor.execute("SELECT 1")
                db_conn.close()
                return {"success": True, "message": "SQLite connection successful"}

            elif conn.db_type == 'mysql':
                db_conn = self._get_mysql_connection(conn)
                with db_conn.cursor() as cursor:
                    cursor.execute("SELECT 1 AS ok")
                    cursor.fetchone()
                db_conn.close()
                return {"success": True, "message": "MySQL connection successful"}

            elif conn.db_type == 'postgresql':
                # PostgreSQL would require psycopg2
                # For now, return a mock success
                return {"success": True, "message": "PostgreSQL connection test (mock)"}

            else:
                return {"success": False, "error": f"Unknown database type: {conn.db_type}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_tables(self, conn_id: str) -> List[str]:
        """Get list of tables in the database"""
        conn = self.connections.get(conn_id)
        if not conn:
            return []

        try:
            if conn.db_type == 'sqlite':
                db_conn = self._get_sqlite_connection(conn)
                cursor = db_conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                tables = [row[0] for row in cursor.fetchall()]
                db_conn.close()
                return tables
            elif conn.db_type == 'mysql':
                db_conn = self._get_mysql_connection(conn)
                with db_conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT table_name AS name
                        FROM information_schema.tables
                        WHERE table_schema = DATABASE()
                        ORDER BY table_name
                        """
                    )
                    tables = [row["name"] for row in cursor.fetchall()]
                db_conn.close()
                return tables
            else:
                return []
        except Exception as e:
            logger.error(f"Error getting tables: {e}")
            return []

    def get_table_columns(self, conn_id: str, table_name: str) -> List[Dict]:
        """Get columns of a table"""
        conn = self.connections.get(conn_id)
        if not conn:
            return []

        try:
            if conn.db_type == 'sqlite':
                if not self._validate_identifier(table_name):
                    return []
                db_conn = self._get_sqlite_connection(conn)
                cursor = db_conn.cursor()
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = [{"name": row[1], "type": row[2], "nullable": not row[3]} for row in cursor.fetchall()]
                db_conn.close()
                return columns
            elif conn.db_type == 'mysql':
                if not self._validate_identifier(table_name):
                    return []
                db_conn = self._get_mysql_connection(conn)
                with db_conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            COLUMN_NAME AS name,
                            COLUMN_TYPE AS type,
                            CASE WHEN IS_NULLABLE = 'YES' THEN TRUE ELSE FALSE END AS nullable
                        FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
                        ORDER BY ORDINAL_POSITION
                        """,
                        (table_name,),
                    )
                    columns = list(cursor.fetchall())
                    if not columns:
                        # Some remote accounts can list tables but cannot read information_schema.columns.
                        # Fall back to SHOW FULL COLUMNS so the schema view remains available.
                        cursor.execute(f"SHOW FULL COLUMNS FROM `{table_name}`")
                        fallback_rows = cursor.fetchall()
                        columns = [
                            {
                                "name": row.get("Field"),
                                "type": row.get("Type"),
                                "nullable": row.get("Null") == "YES",
                            }
                            for row in fallback_rows
                        ]
                db_conn.close()
                return columns
            else:
                return []
        except Exception as e:
            logger.error(f"Error getting columns: {e}")
            return []

    # ==================== Data Operations ====================

    def inject_data(self, conn_id: str, table_name: str, data: List[Dict]) -> Dict:
        """Inject data into a table"""
        conn = self.connections.get(conn_id)
        if not conn:
            return {"success": False, "error": "Connection not found", "inserted": 0}
        if conn.read_only:
            return {"success": False, "error": "Connection is read-only", "inserted": 0}

        if not data:
            return {"success": True, "message": "No data to inject", "inserted": 0}

        # Validate table name safety
        if not self._validate_identifier(table_name):
            return {"success": False, "error": "Invalid table name", "inserted": 0}

        try:
            if conn.db_type == 'sqlite':
                db_conn = self._get_sqlite_connection(conn)
                cursor = db_conn.cursor()

                # Get columns from first row + validate column names
                columns = list(data[0].keys())
                for col in columns:
                    if not self._validate_identifier(col):
                        db_conn.close()
                        return {"success": False, "error": f"Invalid column name: {col}", "inserted": 0}

                placeholders = ', '.join(['?' for _ in columns])
                column_names = ', '.join(columns)

                sql = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"

                inserted = 0
                for row in data:
                    values = [row.get(col) for col in columns]
                    cursor.execute(sql, values)
                    inserted += 1

                db_conn.commit()
                db_conn.close()

                return {"success": True, "message": f"Inserted {inserted} rows", "inserted": inserted}
            elif conn.db_type == 'mysql':
                db_conn = self._get_mysql_connection(conn)
                columns = list(data[0].keys())
                for col in columns:
                    if not self._validate_identifier(col):
                        db_conn.close()
                        return {"success": False, "error": f"Invalid column name: {col}", "inserted": 0}
                placeholders = ', '.join(['%s' for _ in columns])
                column_names = ', '.join(f"`{col}`" for col in columns)
                sql = f"INSERT INTO `{table_name}` ({column_names}) VALUES ({placeholders})"

                inserted = 0
                with db_conn.cursor() as cursor:
                    for row in data:
                        values = [row.get(col) for col in columns]
                        cursor.execute(sql, values)
                        inserted += 1
                db_conn.close()
                return {"success": True, "message": f"Inserted {inserted} rows", "inserted": inserted}

            else:
                return {"success": False, "error": "Database type not supported for injection", "inserted": 0}

        except Exception as e:
            return {"success": False, "error": str(e), "inserted": 0}

    def clean_table(self, conn_id: str, table_name: str, where_clause: str = "") -> Dict:
        """Clean (delete) data from a table"""
        conn = self.connections.get(conn_id)
        if not conn:
            return {"success": False, "error": "Connection not found", "deleted": 0}
        if conn.read_only:
            return {"success": False, "error": "Connection is read-only", "deleted": 0}

        # Validate table name safety
        if not self._validate_identifier(table_name):
            return {"success": False, "error": "Invalid table name", "deleted": 0}

        # Validate where_clause by rejecting dangerous keywords
        if where_clause:
            _upper = where_clause.upper()
            FORBIDDEN = ['DROP', 'INSERT', 'UPDATE', 'DELETE', 'ALTER', 'CREATE', 'EXEC', '--', ';']
            for kw in FORBIDDEN:
                if kw in _upper:
                    return {"success": False, "error": f"Forbidden keyword in where clause: {kw}", "deleted": 0}

        try:
            if conn.db_type == 'sqlite':
                db_conn = self._get_sqlite_connection(conn)
                cursor = db_conn.cursor()

                if where_clause:
                    sql = f"DELETE FROM {table_name} WHERE {where_clause}"
                else:
                    sql = f"DELETE FROM {table_name}"

                cursor.execute(sql)
                deleted = cursor.rowcount
                db_conn.commit()
                db_conn.close()

                return {"success": True, "message": f"Deleted {deleted} rows", "deleted": deleted}
            elif conn.db_type == 'mysql':
                db_conn = self._get_mysql_connection(conn)
                with db_conn.cursor() as cursor:
                    if where_clause:
                        sql = f"DELETE FROM `{table_name}` WHERE {where_clause}"
                    else:
                        sql = f"DELETE FROM `{table_name}`"
                    cursor.execute(sql)
                    deleted = cursor.rowcount
                db_conn.close()
                return {"success": True, "message": f"Deleted {deleted} rows", "deleted": deleted}

            else:
                return {"success": False, "error": "Database type not supported for cleanup", "deleted": 0}

        except Exception as e:
            return {"success": False, "error": str(e), "deleted": 0}

    def query_data(self, conn_id: str, sql: str, limit: int = 100) -> Dict:
        """Execute a SELECT query"""
        conn = self.connections.get(conn_id)
        if not conn:
            return {"success": False, "error": "Connection not found", "rows": []}

        # Security: Only allow SELECT queries
        sql_stripped = sql.strip()
        if not sql_stripped.upper().startswith('SELECT'):
            return {"success": False, "error": "Only SELECT queries are allowed", "rows": []}

        # Security: reject semicolons to prevent multiple statements, and reject destructive keywords
        _upper = sql_stripped.upper()
        FORBIDDEN = ['DROP', 'INSERT', 'UPDATE', 'DELETE', 'ALTER', 'CREATE', 'EXEC', 'ATTACH', 'DETACH']
        if ';' in sql_stripped:
            return {"success": False, "error": "Semicolons are not allowed in queries", "rows": []}
        for kw in FORBIDDEN:
            # Match standalone keywords only
            if re.search(rf'\b{kw}\b', _upper):
                return {"success": False, "error": f"Forbidden keyword: {kw}", "rows": []}

        started_at = time.perf_counter()
        try:
            if conn.db_type == 'sqlite':
                db_conn = self._get_sqlite_connection(conn)
                db_conn.row_factory = sqlite3.Row
                cursor = db_conn.cursor()

                # Add LIMIT if not present
                if 'LIMIT' not in _upper:
                    sql_stripped = f"{sql_stripped} LIMIT {limit}"

                cursor.execute(sql_stripped)
                rows = [dict(row) for row in cursor.fetchall()]
                db_conn.close()
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                return {
                    "success": True,
                    "rows": rows,
                    "count": len(rows),
                    "elapsed_ms": elapsed_ms,
                    "message": f"Query completed: returned {len(rows)} rows in {elapsed_ms} ms",
                }
            elif conn.db_type == 'mysql':
                db_conn = self._get_mysql_connection(conn)
                with db_conn.cursor() as cursor:
                    if 'LIMIT' not in _upper:
                        sql_stripped = f"{sql_stripped} LIMIT {limit}"
                    cursor.execute(sql_stripped)
                    rows = list(cursor.fetchall())
                db_conn.close()
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                return {
                    "success": True,
                    "rows": rows,
                    "count": len(rows),
                    "elapsed_ms": elapsed_ms,
                    "message": f"Query completed: returned {len(rows)} rows in {elapsed_ms} ms",
                }

            else:
                return {"success": False, "error": "Database type not supported for queries", "rows": []}

        except Exception as e:
            return {"success": False, "error": str(e), "rows": []}

    def generate_schema_text(self, conn_id: str) -> Dict[str, Any]:
        """Generate a textual schema overview for a managed connection."""
        conn = self.connections.get(conn_id)
        if not conn:
            return {"success": False, "error": "Connection not found", "schema": ""}

        tables = self.get_tables(conn_id)
        if not tables:
            return {"success": True, "schema": "-- No tables found", "table_count": 0}

        lines = [f"-- {conn.name} ({conn.db_type}) schema overview", f"-- database: {conn.database}", ""]
        for table_name in tables:
            columns = self.get_table_columns(conn_id, table_name)
            lines.append(f"TABLE {table_name}")
            for column in columns:
                nullable = "NULL" if column.get("nullable") else "NOT NULL"
                lines.append(f"  - {column.get('name')} {column.get('type')} {nullable}")
            lines.append("")
        return {
            "success": True,
            "schema": "\n".join(lines).strip(),
            "table_count": len(tables),
        }

    # ==================== Data Validation ====================

    def validate_data(self, conn_id: str, rules: List[Dict]) -> Dict:
        """Validate data against rules"""
        conn = self.connections.get(conn_id)
        if not conn:
            return {"success": False, "error": "Connection not found", "results": []}

        results = []
        all_passed = True

        try:
            if conn.db_type == 'sqlite':
                db_conn = self._get_sqlite_connection(conn)
                cursor = db_conn.cursor()
                identifier_wrap = lambda name: name
            elif conn.db_type == 'mysql':
                db_conn = self._get_mysql_connection(conn)
                cursor = db_conn.cursor()
                identifier_wrap = lambda name: f"`{name}`"
            else:
                return {"success": False, "error": "Database type not supported for validation", "results": results}

            for rule in rules:
                table = rule.get('table', '')
                column = rule.get('column', '_count')
                operator = rule.get('operator', 'exists')
                expected = rule.get('expected')
                where = rule.get('where_clause', '')

                # Validate table and column name safety
                if not self._validate_identifier(table):
                    results.append({"rule": rule, "actual": None, "passed": False, "message": "Invalid table name"})
                    all_passed = False
                    continue
                if column != '_count' and not self._validate_identifier(column):
                    results.append({"rule": rule, "actual": None, "passed": False, "message": f"Invalid column name: {column}"})
                    all_passed = False
                    continue

                try:
                    wrapped_table = identifier_wrap(table)
                    wrapped_column = identifier_wrap(column) if column != '_count' else column
                    if operator == 'count_equals':
                        sql = f"SELECT COUNT(*) FROM {wrapped_table}"
                        if where:
                            sql += f" WHERE {where}"
                        cursor.execute(sql)
                        row = cursor.fetchone()
                        actual = row[0] if isinstance(row, tuple) else list(row.values())[0]
                        passed = actual == expected
                    elif operator == 'exists':
                        sql = f"SELECT COUNT(*) FROM {wrapped_table}"
                        if where:
                            sql += f" WHERE {where}"
                        cursor.execute(sql)
                        row = cursor.fetchone()
                        actual = row[0] if isinstance(row, tuple) else list(row.values())[0]
                        passed = actual > 0
                    else:
                        sql = f"SELECT {wrapped_column} FROM {wrapped_table}"
                        if where:
                            sql += f" WHERE {where}"
                        sql += " LIMIT 1"
                        cursor.execute(sql)
                        row = cursor.fetchone()
                        if isinstance(row, dict):
                            actual = next(iter(row.values()), None)
                        else:
                            actual = row[0] if row else None

                        if operator == 'equals':
                            passed = actual == expected
                        elif operator == 'not_equals':
                            passed = actual != expected
                        elif operator == 'greater_than':
                            passed = actual is not None and actual > expected
                        elif operator == 'less_than':
                            passed = actual is not None and actual < expected
                        elif operator == 'contains':
                            passed = actual is not None and str(expected) in str(actual)
                        else:
                            passed = False
                            actual = f"Unknown operator: {operator}"

                    results.append({
                        "rule": rule,
                        "actual": actual,
                        "passed": passed,
                        "message": "Passed" if passed else f"Expected {expected}, got {actual}"
                    })
                    if not passed:
                        all_passed = False
                except Exception as e:
                    results.append({
                        "rule": rule,
                        "actual": None,
                        "passed": False,
                        "message": f"Error: {str(e)}"
                    })
                    all_passed = False

            db_conn.close()

            return {
                "success": all_passed,
                "results": results,
                "total": len(rules),
                "passed": sum(1 for r in results if r['passed']),
                "failed": sum(1 for r in results if not r['passed'])
            }

        except Exception as e:
            return {"success": False, "error": str(e), "results": results}


# Singleton instance
_service_instance: Optional[DatabaseManagerService] = None


def get_database_manager() -> DatabaseManagerService:
    """Get or create the singleton service instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = DatabaseManagerService()
    return _service_instance
