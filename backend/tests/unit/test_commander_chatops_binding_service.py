# -*- coding: utf-8 -*-
from contextlib import contextmanager
import sqlite3
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.commander_chatops_binding_service import (
    ChatOpsBindingValidationError,
    CommanderChatOpsBindingService,
)


def _make_user(user_id: str, username: str):
    return SimpleNamespace(user_id=user_id, username=username)


def _patch_temp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "chatops_binding.db"

    @contextmanager
    def _get_connection():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    monkeypatch.setattr(
        "services.commander_chatops_binding_service.get_connection",
        _get_connection,
    )


def test_issue_and_bind_open_id_marks_code_used(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    auth = MagicMock()
    auth.users = {"user_1": _make_user("user_1", "alice")}
    monkeypatch.setattr(
        "services.commander_chatops_binding_service.get_auth_service",
        lambda: auth,
    )

    service = CommanderChatOpsBindingService()
    code = service.issue_binding_code(_make_user("user_1", "alice"))

    binding = service.bind_open_id(
        code=code["code"],
        notification_platform_open_id="ou_demo",
        chat_id="oc_demo",
        source="notification_platform",
    )

    assert binding["user_id"] == "user_1"
    assert binding["username"] == "alice"
    assert binding["chat_id"] == "oc_demo"
    assert binding["source"] == "notification_platform"
    assert service.get_binding_code(code["code"])["status"] == "used"
    assert service.resolve_bound_user("ou_demo").user_id == "user_1"

    with pytest.raises(ChatOpsBindingValidationError):
        service.bind_open_id(
            code=code["code"],
            notification_platform_open_id="ou_demo",
            chat_id="oc_demo",
            source="notification_platform",
        )


def test_bind_open_id_rejects_expired_code(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    auth = MagicMock()
    auth.users = {"user_1": _make_user("user_1", "alice")}
    monkeypatch.setattr(
        "services.commander_chatops_binding_service.get_auth_service",
        lambda: auth,
    )

    service = CommanderChatOpsBindingService()
    code = service.issue_binding_code(_make_user("user_1", "alice"))

    # The service uses the patched get_connection above, so directly update the row.
    from services import commander_chatops_binding_service as binding_module

    with binding_module.get_connection() as conn:
        conn.execute(
            "UPDATE notification_platform_binding_codes SET expires_at = '2000-01-01T00:00:00' WHERE code = ?",
            (code["code"],),
        )

    with pytest.raises(ChatOpsBindingValidationError):
        service.bind_open_id(
            code=code["code"],
            notification_platform_open_id="ou_demo",
            chat_id="oc_demo",
            source="notification_platform",
        )

    assert service.get_latest_issued_code_for_user(_make_user("user_1", "alice")) is None


def test_revoke_binding_for_user_revokes_binding_and_pending_code(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    auth = MagicMock()
    user = _make_user("user_1", "alice")
    auth.users = {"user_1": user}
    monkeypatch.setattr(
        "services.commander_chatops_binding_service.get_auth_service",
        lambda: auth,
    )

    service = CommanderChatOpsBindingService()
    code = service.issue_binding_code(user)
    service.bind_open_id(
        code=code["code"],
        notification_platform_open_id="ou_demo",
        chat_id="oc_demo",
        source="notification_platform",
    )
    service.issue_binding_code(user)

    revoked = service.revoke_binding_for_user(user)

    assert revoked["binding"]["notification_platform_open_id"] == "ou_demo"
    assert service.get_binding_for_user(user) is None
    assert service.get_latest_issued_code_for_user(user) is None
