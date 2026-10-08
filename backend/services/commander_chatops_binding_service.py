# -*- coding: utf-8 -*-
"""
Commander ChatOps Binding Service

Manage controlled bindings between notification platform identities and platform users.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import secrets
from typing import Any, Dict, Optional

from core.db_helper import get_connection
from services.auth_service import User, get_auth_service


class ChatOpsBindingError(Exception):
    """Base exception for notification platform binding flows."""


class ChatOpsBindingValidationError(ChatOpsBindingError):
    """Invalid binding parameters or state."""


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class CommanderChatOpsBindingService:
    """Manage notification platform user bindings and single-use binding codes."""

    def __init__(self) -> None:
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_platform_user_bindings (
                    notification_platform_open_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    username TEXT DEFAULT '',
                    chat_id TEXT DEFAULT '',
                    source TEXT DEFAULT 'notification_platform',
                    status TEXT DEFAULT 'active',
                    bound_at TEXT DEFAULT '',
                    last_seen_at TEXT DEFAULT '',
                    revoked_at TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_platform_binding_codes (
                    code TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    username TEXT DEFAULT '',
                    status TEXT DEFAULT 'issued',
                    created_at TEXT DEFAULT '',
                    expires_at TEXT DEFAULT '',
                    used_at TEXT DEFAULT '',
                    revoked_at TEXT DEFAULT '',
                    issued_by TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_notification_platform_user_bindings_user_id ON notification_platform_user_bindings(user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_notification_platform_binding_codes_user_id ON notification_platform_binding_codes(user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_notification_platform_binding_codes_expires_at ON notification_platform_binding_codes(expires_at)"
            )

    def issue_binding_code(self, user: User, *, ttl_minutes: int = 10) -> Dict[str, Any]:
        ttl = max(int(ttl_minutes or 0), 1)
        code = f"BIND-{secrets.token_hex(3).upper()}"
        now = _now_iso()
        expires_at = (datetime.now() + timedelta(minutes=ttl)).isoformat(timespec="seconds")

        with get_connection() as conn:
            conn.execute(
                """
                UPDATE notification_platform_binding_codes
                SET status = 'revoked', revoked_at = ?
                WHERE user_id = ? AND status = 'issued'
                """,
                (now, user.user_id),
            )
            conn.execute(
                """
                INSERT INTO notification_platform_binding_codes (
                    code, user_id, username, status, created_at, expires_at, used_at, revoked_at, issued_by
                ) VALUES (?, ?, ?, 'issued', ?, ?, '', '', ?)
                """,
                (
                    code,
                    user.user_id,
                    user.username,
                    now,
                    expires_at,
                    user.user_id,
                ),
            )
        return self.get_binding_code(code) or {}

    def get_binding_code(self, code: str) -> Optional[Dict[str, Any]]:
        normalized = str(code or "").strip().upper()
        if not normalized:
            return None
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM notification_platform_binding_codes WHERE code = ?",
                (normalized,),
            ).fetchone()
        if not row:
            return None
        return self._serialize_code_row(dict(row))

    def get_binding_for_user(self, user: User) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM notification_platform_user_bindings
                WHERE user_id = ? AND status = 'active'
                ORDER BY datetime(bound_at) DESC
                LIMIT 1
                """,
                (user.user_id,),
            ).fetchone()
        if not row:
            return None
        return self._serialize_binding_row(dict(row))

    def get_binding_for_open_id(self, notification_platform_open_id: str) -> Optional[Dict[str, Any]]:
        normalized = str(notification_platform_open_id or "").strip()
        if not normalized:
            return None
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM notification_platform_user_bindings
                WHERE notification_platform_open_id = ? AND status = 'active'
                LIMIT 1
                """,
                (normalized,),
            ).fetchone()
        if not row:
            return None
        return self._serialize_binding_row(dict(row))

    def get_latest_issued_code_for_user(self, user: User) -> Optional[Dict[str, Any]]:
        now = _now_iso()
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE notification_platform_binding_codes
                SET status = 'expired'
                WHERE status = 'issued' AND expires_at < ?
                """,
                (now,),
            )
            row = conn.execute(
                """
                SELECT *
                FROM notification_platform_binding_codes
                WHERE user_id = ? AND status = 'issued'
                ORDER BY datetime(created_at) DESC
                LIMIT 1
                """,
                (user.user_id,),
            ).fetchone()
        if not row:
            return None
        return self._serialize_code_row(dict(row))

    def bind_open_id(
        self,
        *,
        code: str,
        notification_platform_open_id: str,
        chat_id: str = "",
        source: str = "notification_platform",
    ) -> Dict[str, Any]:
        normalized_code = str(code or "").strip().upper()
        normalized_open_id = str(notification_platform_open_id or "").strip()
        normalized_chat_id = str(chat_id or "").strip()
        if not normalized_code:
            raise ChatOpsBindingValidationError("Binding code is required")
        if not normalized_open_id:
            raise ChatOpsBindingValidationError("Notification platform open_id is required")

        now = _now_iso()
        auth = get_auth_service()
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE notification_platform_binding_codes
                SET status = 'expired'
                WHERE status = 'issued' AND expires_at < ?
                """,
                (now,),
            )
            code_row = conn.execute(
                "SELECT * FROM notification_platform_binding_codes WHERE code = ?",
                (normalized_code,),
            ).fetchone()
            if not code_row:
                raise ChatOpsBindingValidationError("Binding code does not exist")
            code_payload = dict(code_row)
            if str(code_payload.get("status") or "") != "issued":
                raise ChatOpsBindingValidationError("Binding code is no longer valid; generate a new code in Legion")
            if str(code_payload.get("expires_at") or "") < now:
                conn.execute(
                    "UPDATE notification_platform_binding_codes SET status = 'expired' WHERE code = ?",
                    (normalized_code,),
                )
                raise ChatOpsBindingValidationError("Binding code has expired; generate a new code")

            user_id = str(code_payload.get("user_id") or "")
            user = auth.users.get(user_id)
            if not user:
                raise ChatOpsBindingValidationError("The platform user for this binding code does not exist")

            existing_open_id = conn.execute(
                """
                SELECT *
                FROM notification_platform_user_bindings
                WHERE notification_platform_open_id = ? AND status = 'active'
                LIMIT 1
                """,
                (normalized_open_id,),
            ).fetchone()
            if existing_open_id and str(existing_open_id["user_id"] or "") != user.user_id:
                raise ChatOpsBindingValidationError("This notification platform identity is already bound to another platform account")

            conn.execute(
                """
                UPDATE notification_platform_user_bindings
                SET status = 'revoked', revoked_at = ?
                WHERE user_id = ? AND status = 'active'
                """,
                (now, user.user_id),
            )
            conn.execute(
                """
                INSERT INTO notification_platform_user_bindings (
                    notification_platform_open_id, user_id, username, chat_id, source, status, bound_at, last_seen_at, revoked_at
                ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, '')
                ON CONFLICT(notification_platform_open_id) DO UPDATE SET
                    user_id = excluded.user_id,
                    username = excluded.username,
                    chat_id = excluded.chat_id,
                    source = excluded.source,
                    status = 'active',
                    bound_at = excluded.bound_at,
                    last_seen_at = excluded.last_seen_at,
                    revoked_at = ''
                """,
                (
                    normalized_open_id,
                    user.user_id,
                    user.username,
                    normalized_chat_id,
                    str(source or "notification_platform"),
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE notification_platform_binding_codes
                SET status = 'used', used_at = ?
                WHERE code = ?
                """,
                (now, normalized_code),
            )

        binding = self.get_binding_for_open_id(normalized_open_id)
        if not binding:
            raise ChatOpsBindingValidationError("Failed to save the notification platform binding")
        return binding

    def revoke_binding_for_user(self, user: User) -> Dict[str, Any]:
        now = _now_iso()
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM notification_platform_user_bindings
                WHERE user_id = ? AND status = 'active'
                ORDER BY datetime(bound_at) DESC
                LIMIT 1
                """,
                (user.user_id,),
            ).fetchone()
            if row:
                conn.execute(
                    """
                    UPDATE notification_platform_user_bindings
                    SET status = 'revoked', revoked_at = ?
                    WHERE user_id = ? AND status = 'active'
                    """,
                    (now, user.user_id),
                )
            conn.execute(
                """
                UPDATE notification_platform_binding_codes
                SET status = 'revoked', revoked_at = ?
                WHERE user_id = ? AND status = 'issued'
                """,
                (now, user.user_id),
            )
        return {
            "binding": self._serialize_binding_row(dict(row)) if row else None,
            "revoked_at": now,
        }

    def resolve_bound_user(self, notification_platform_open_id: str) -> Optional[User]:
        binding = self.get_binding_for_open_id(notification_platform_open_id)
        if not binding:
            return None
        return get_auth_service().users.get(binding["user_id"])

    def touch_binding(self, notification_platform_open_id: str, *, chat_id: str = "") -> None:
        normalized = str(notification_platform_open_id or "").strip()
        if not normalized:
            return
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE notification_platform_user_bindings
                SET last_seen_at = ?, chat_id = CASE WHEN ? = '' THEN chat_id ELSE ? END
                WHERE notification_platform_open_id = ? AND status = 'active'
                """,
                (_now_iso(), str(chat_id or "").strip(), str(chat_id or "").strip(), normalized),
            )

    @staticmethod
    def _serialize_binding_row(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "notification_platform_open_id": str(row.get("notification_platform_open_id") or ""),
            "user_id": str(row.get("user_id") or ""),
            "username": str(row.get("username") or ""),
            "chat_id": str(row.get("chat_id") or ""),
            "source": str(row.get("source") or ""),
            "status": str(row.get("status") or ""),
            "bound_at": str(row.get("bound_at") or ""),
            "last_seen_at": str(row.get("last_seen_at") or ""),
            "revoked_at": str(row.get("revoked_at") or ""),
        }

    @staticmethod
    def _serialize_code_row(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "code": str(row.get("code") or ""),
            "user_id": str(row.get("user_id") or ""),
            "username": str(row.get("username") or ""),
            "status": str(row.get("status") or ""),
            "created_at": str(row.get("created_at") or ""),
            "expires_at": str(row.get("expires_at") or ""),
            "used_at": str(row.get("used_at") or ""),
            "revoked_at": str(row.get("revoked_at") or ""),
            "issued_by": str(row.get("issued_by") or ""),
        }


_service: Optional[CommanderChatOpsBindingService] = None


def get_commander_chatops_binding_service() -> CommanderChatOpsBindingService:
    global _service
    if _service is None:
        _service = CommanderChatOpsBindingService()
    return _service
