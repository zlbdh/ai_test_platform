"""
Authentication service: enterprise authentication.

Provides authentication and authorization:
- JWT token management
- User and project isolation
- API key authentication
- Audit logs
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import secrets
import json
import sqlite3
from pathlib import Path


class UserRole(Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    TESTER = "tester"
    VIEWER = "viewer"


class Permission(Enum):
    CREATE_TEST = "create_test"
    RUN_TEST = "run_test"
    VIEW_RESULTS = "view_results"
    MANAGE_USERS = "manage_users"
    MANAGE_PROJECTS = "manage_projects"
    API_ACCESS = "api_access"
    DEPLOY_VIEW = "deploy_view"
    DEPLOY_REQUEST = "deploy_request"
    DEPLOY_APPROVE = "deploy_approve"
    ADMIN = "admin"


# Role-to-permission mapping
ROLE_PERMISSIONS = {
    UserRole.ADMIN: [p for p in Permission],
    UserRole.DEVELOPER: [
        Permission.CREATE_TEST,
        Permission.RUN_TEST,
        Permission.VIEW_RESULTS,
        Permission.API_ACCESS,
        Permission.DEPLOY_VIEW,
        Permission.DEPLOY_REQUEST,
    ],
    UserRole.TESTER: [
        Permission.RUN_TEST,
        Permission.VIEW_RESULTS,
        Permission.DEPLOY_VIEW,
    ],
    UserRole.VIEWER: [Permission.VIEW_RESULTS]
}


@dataclass
class User:
    """User"""
    user_id: str
    username: str
    email: str
    password_hash: str
    role: UserRole
    project_ids: List[str]
    api_key: Optional[str]
    created_at: str
    last_login: Optional[str] = None
    is_active: bool = True


@dataclass
class Project:
    """Project"""
    project_id: str
    name: str
    description: str
    owner_id: str
    member_ids: List[str]
    created_at: str
    settings: Dict[str, Any] = None


@dataclass
class Session:
    """Session"""
    session_id: str
    user_id: str
    token: str
    created_at: str
    expires_at: str
    ip_address: Optional[str] = None


@dataclass
class AuditLog:
    """Audit log"""
    log_id: str
    user_id: str
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: Dict[str, Any]
    timestamp: str
    ip_address: Optional[str] = None


class AuthenticationService:
    """Authentication service"""
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path or "data/auth")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.audit_db_path = self.storage_path / "auth_audit.db"
        self._audit_cache_limit = 5000
        
        self.users: Dict[str, User] = {}
        self.projects: Dict[str, Project] = {}
        self.sessions: Dict[str, Session] = {}
        self.audit_logs: List[AuditLog] = []
        
        self._init_audit_storage()
        self._load()
        self._load_active_sessions()
        self._load_recent_audit_logs()
        self._ensure_admin()
    
    def _load(self):
        """Load data"""
        users_file = self.storage_path / "users.json"
        projects_file = self.storage_path / "projects.json"
        
        if users_file.exists():
            try:
                with open(users_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for u in data:
                        u["role"] = UserRole(u["role"])
                        self.users[u["user_id"]] = User(**u)
            except Exception:
                pass
        
        if projects_file.exists():
            try:
                with open(projects_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for p in data:
                        self.projects[p["project_id"]] = Project(**p)
            except Exception:
                pass
    
    def _save(self):
        """Save data"""
        users_file = self.storage_path / "users.json"
        projects_file = self.storage_path / "projects.json"
        
        with open(users_file, "w", encoding="utf-8") as f:
            data = []
            for u in self.users.values():
                d = asdict(u)
                d["role"] = u.role.value
                data.append(d)
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        with open(projects_file, "w", encoding="utf-8") as f:
            json.dump([asdict(p) for p in self.projects.values()], f, ensure_ascii=False, indent=2)

    def _connect_audit_db(self) -> sqlite3.Connection:
        """Connect to the audit log database."""
        conn = sqlite3.connect(self.audit_db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_audit_storage(self):
        """Initialize persistent authentication state."""
        try:
            with self._connect_audit_db() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        log_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        resource_type TEXT NOT NULL,
                        resource_id TEXT,
                        details_json TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        ip_address TEXT
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action)"
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sessions (
                        token TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        ip_address TEXT
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at)"
                )
        except sqlite3.Error:
            # Fall back to the in-memory cache so initialization does not interrupt the service.
            pass

    def _row_to_audit_log(self, row: sqlite3.Row) -> AuditLog:
        """Convert a SQLite record to an AuditLog."""
        details_raw = row["details_json"] or "{}"
        try:
            details = json.loads(details_raw)
        except json.JSONDecodeError:
            details = {}

        return AuditLog(
            log_id=row["log_id"],
            user_id=row["user_id"],
            action=row["action"],
            resource_type=row["resource_type"],
            resource_id=row["resource_id"],
            details=details,
            timestamp=row["timestamp"],
            ip_address=row["ip_address"],
        )

    def _load_recent_audit_logs(self):
        """Load recent persistent audit logs into the in-memory cache."""
        try:
            with self._connect_audit_db() as conn:
                rows = conn.execute(
                    """
                    SELECT log_id, user_id, action, resource_type, resource_id, details_json, timestamp, ip_address
                    FROM audit_logs
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (self._audit_cache_limit,),
                ).fetchall()
            self.audit_logs = [self._row_to_audit_log(row) for row in reversed(rows)]
        except sqlite3.Error:
            self.audit_logs = []

    def _load_active_sessions(self):
        """Load unexpired sessions so tokens remain valid after a service restart."""
        try:
            now = datetime.now().isoformat()
            with self._connect_audit_db() as conn:
                conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
                rows = conn.execute(
                    """
                    SELECT token, session_id, user_id, created_at, expires_at, ip_address
                    FROM sessions
                    ORDER BY created_at ASC
                    """
                ).fetchall()
            for row in rows:
                session = Session(
                    session_id=row["session_id"],
                    user_id=row["user_id"],
                    token=row["token"],
                    created_at=row["created_at"],
                    expires_at=row["expires_at"],
                    ip_address=row["ip_address"],
                )
                self.sessions[session.token] = session
        except sqlite3.Error:
            self.sessions = {}

    def _persist_audit_log(self, log: AuditLog):
        """Persist an audit log to SQLite."""
        try:
            with self._connect_audit_db() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO audit_logs (
                        log_id, user_id, action, resource_type, resource_id, details_json, timestamp, ip_address
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        log.log_id,
                        log.user_id,
                        log.action,
                        log.resource_type,
                        log.resource_id,
                        json.dumps(log.details or {}, ensure_ascii=False),
                        log.timestamp,
                        log.ip_address,
                    ),
                )
        except sqlite3.Error:
            # Keep the in-memory log if persistence fails, avoiding disruption of the main workflow.
            pass

    def _persist_session(self, session: Session):
        """Persist a session to SQLite."""
        try:
            with self._connect_audit_db() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO sessions (
                        token, session_id, user_id, created_at, expires_at, ip_address
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session.token,
                        session.session_id,
                        session.user_id,
                        session.created_at,
                        session.expires_at,
                        session.ip_address,
                    ),
                )
        except sqlite3.Error:
            pass

    def _delete_session(self, token: str):
        """Delete a persistent session."""
        try:
            with self._connect_audit_db() as conn:
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        except sqlite3.Error:
            pass
    
    def _ensure_admin(self):
        """Ensure a default administrator exists; read the password from the environment or generate one randomly"""
        if not any(u.role == UserRole.ADMIN for u in self.users.values()):
            import os, logging as _log
            admin_password = os.environ.get("ADMIN_DEFAULT_PASSWORD", "")
            if not admin_password:
                admin_password = secrets.token_urlsafe(16)
                _log.getLogger(__name__).warning(
                    f"[AuthService] Initial startup: an administrator account was created automatically. "
                    f"Username: admin | Password: {admin_password}"
                    f" | Change the password promptly or set ADMIN_DEFAULT_PASSWORD"
                )
            self.create_user(
                username="admin",
                email="admin@localhost",
                password=admin_password,
                role=UserRole.ADMIN
            )
    
    def _hash_password(self, password: str, salt: str = "") -> str:
        """Hash a password using PBKDF2 and a random salt"""
        if not salt:
            salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
        return f"{salt}${hashed.hex()}"
    
    def _generate_token(self) -> str:
        """Generate a token"""
        return secrets.token_urlsafe(32)
    
    def _generate_api_key(self) -> str:
        """Generate an API key"""
        return f"atp_{secrets.token_urlsafe(24)}"
    
    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: UserRole = UserRole.TESTER
    ) -> User:
        """Create a user"""
        user_id = f"user_{secrets.token_hex(8)}"
        
        user = User(
            user_id=user_id,
            username=username,
            email=email,
            password_hash=self._hash_password(password),
            role=role,
            project_ids=[],
            api_key=self._generate_api_key(),
            created_at=datetime.now().isoformat()
        )
        
        self.users[user_id] = user
        self._save()
        
        self._audit("create_user", "user", user_id, {"username": username})
        
        return user
    
    def authenticate(
        self,
        username: str,
        password: str,
        ip_address: Optional[str] = None
    ) -> Optional[Session]:
        """Authenticate a user"""
        user = None
        for u in self.users.values():
            if u.username == username:
                # Extract the salt from the stored hash and recompute
                if "$" in u.password_hash:
                    stored_salt = u.password_hash.split("$")[0]
                    if self._hash_password(password, stored_salt) == u.password_hash:
                        user = u
                        break
                else:
                    # Support legacy SHA256 hashes during migration
                    old_hash = hashlib.sha256(f"{password}ai_test_platform_salt".encode()).hexdigest()
                    if u.password_hash == old_hash:
                        # Automatically migrate to the new format
                        u.password_hash = self._hash_password(password)
                        self._save()
                        user = u
                        break
        
        if not user or not user.is_active:
            self._audit("login_failed", "session", None, {"username": username}, ip=ip_address)
            return None
        
        # Create a session
        session = Session(
            session_id=f"sess_{secrets.token_hex(16)}",
            user_id=user.user_id,
            token=self._generate_token(),
            created_at=datetime.now().isoformat(),
            expires_at=(datetime.now() + timedelta(hours=24)).isoformat(),
            ip_address=ip_address
        )
        
        self.sessions[session.token] = session
        self._persist_session(session)
        
        # Update the last login
        user.last_login = datetime.now().isoformat()
        self._save()
        
        self._audit("login", "session", session.session_id, {}, user_id=user.user_id, ip=ip_address)
        
        return session
    
    def authenticate_api_key(self, api_key: str) -> Optional[User]:
        """API key authentication"""
        for user in self.users.values():
            if user.api_key == api_key and user.is_active:
                return user
        return None
    
    def validate_token(self, token: str) -> Optional[User]:
        """Validate a token"""
        session = self.sessions.get(token)
        
        if not session:
            return None
        
        # Check expiration
        if datetime.fromisoformat(session.expires_at) < datetime.now():
            del self.sessions[token]
            self._delete_session(token)
            return None
        
        return self.users.get(session.user_id)

    def get_dev_bypass_user(self) -> Optional[User]:
        """Return a default local user, preferring an administrator, when development authentication bypass is enabled."""
        for user in self.users.values():
            if user.is_active and user.role == UserRole.ADMIN:
                return user

        for user in self.users.values():
            if user.is_active:
                return user

        return None
    
    def check_permission(self, user: User, permission: Permission) -> bool:
        """Check permissions"""
        user_permissions = ROLE_PERMISSIONS.get(user.role, [])
        return permission in user_permissions or Permission.ADMIN in user_permissions
    
    def create_project(
        self,
        name: str,
        description: str,
        owner_id: str
    ) -> Project:
        """Create a project"""
        project_id = f"proj_{secrets.token_hex(8)}"
        
        project = Project(
            project_id=project_id,
            name=name,
            description=description,
            owner_id=owner_id,
            member_ids=[owner_id],
            created_at=datetime.now().isoformat(),
            settings={}
        )
        
        self.projects[project_id] = project
        
        # Update the project list for the user
        if owner_id in self.users:
            self.users[owner_id].project_ids.append(project_id)
        
        self._save()
        self._audit("create_project", "project", project_id, {"name": name}, user_id=owner_id)
        
        return project
    
    def add_project_member(
        self,
        project_id: str,
        user_id: str,
        added_by: str
    ) -> bool:
        """Add a project member"""
        if project_id not in self.projects or user_id not in self.users:
            return False
        
        project = self.projects[project_id]
        if user_id not in project.member_ids:
            project.member_ids.append(user_id)
            self.users[user_id].project_ids.append(project_id)
            self._save()
            self._audit("add_member", "project", project_id, {"user_id": user_id}, user_id=added_by)
        
        return True
    
    def check_project_access(self, user: User, project_id: str) -> bool:
        """Check project access"""
        if user.role == UserRole.ADMIN:
            return True
        return project_id in user.project_ids
    
    def _audit(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[str],
        details: Dict[str, Any],
        user_id: Optional[str] = None,
        ip: Optional[str] = None
    ):
        """Record an audit log"""
        log = AuditLog(
            log_id=f"audit_{secrets.token_hex(8)}",
            user_id=user_id or "system",
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            timestamp=datetime.now().isoformat(),
            ip_address=ip
        )
        self.audit_logs.append(log)
        self._persist_audit_log(log)
        
        # Limit the number of logs
        if len(self.audit_logs) > self._audit_cache_limit * 2:
            self.audit_logs = self.audit_logs[-self._audit_cache_limit:]

    def record_audit_event(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[str],
        details: Dict[str, Any],
        user_id: Optional[str] = None,
        ip: Optional[str] = None,
    ):
        """Public audit recording entry point shared by routers and services."""
        self._audit(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            user_id=user_id,
            ip=ip,
        )
    
    def get_audit_logs(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        action_prefix: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """Get audit logs"""
        try:
            sql = [
                "SELECT log_id, user_id, action, resource_type, resource_id, details_json, timestamp, ip_address",
                "FROM audit_logs",
            ]
            filters = []
            params: List[Any] = []

            if user_id:
                filters.append("user_id = ?")
                params.append(user_id)
            if action:
                filters.append("action = ?")
                params.append(action)
            if resource_type:
                filters.append("resource_type = ?")
                params.append(resource_type)
            if action_prefix:
                filters.append("action LIKE ?")
                params.append(f"{action_prefix}%")

            if filters:
                sql.append("WHERE " + " AND ".join(filters))

            sql.append("ORDER BY timestamp DESC LIMIT ?")
            params.append(limit)

            with self._connect_audit_db() as conn:
                rows = conn.execute(" ".join(sql), params).fetchall()
            return [self._row_to_audit_log(row) for row in reversed(rows)]
        except sqlite3.Error:
            logs = self.audit_logs
            
            if user_id:
                logs = [l for l in logs if l.user_id == user_id]
            if action:
                logs = [l for l in logs if l.action == action]
            if resource_type:
                logs = [l for l in logs if l.resource_type == resource_type]
            if action_prefix:
                logs = [l for l in logs if l.action.startswith(action_prefix)]
            
            return logs[-limit:]
    
    def logout(self, token: str):
        """Sign out"""
        if token in self.sessions:
            session = self.sessions[token]
            self._audit("logout", "session", session.session_id, {}, user_id=session.user_id)
            del self.sessions[token]
            self._delete_session(token)


# Singleton
_auth_service: Optional[AuthenticationService] = None

def get_auth_service() -> AuthenticationService:
    """Get the authentication service singleton"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthenticationService()
    return _auth_service
