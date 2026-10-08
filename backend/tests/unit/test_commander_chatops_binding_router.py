# -*- coding: utf-8 -*-
from contextlib import contextmanager
import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.commander import router as commander_router
from services.commander_chatops_binding_service import CommanderChatOpsBindingService


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(commander_router)
    return TestClient(app)


def _make_user(user_id: str, username: str):
    return SimpleNamespace(
        user_id=user_id,
        username=username,
        email=f"{username}@example.com",
        role="developer",
        project_ids=["demo"],
    )


def _patch_temp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "chatops_router.db"

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


def test_chatops_binding_routes_issue_and_revoke(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    client = _make_client()
    user = _make_user("user_1", "alice")
    auth = MagicMock()
    auth.validate_token.return_value = user
    auth.record_audit_event = MagicMock()
    auth.users = {user.user_id: user}
    binding_service = CommanderChatOpsBindingService()

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.commander.get_auth_service", return_value=auth), \
         patch("routers.commander.get_commander_chatops_binding_service", return_value=binding_service):
        issue_response = client.post(
            "/api/commander/chatops/bindings/me/issue",
            headers={"Authorization": "Bearer demo-token"},
        )
        me_response = client.get(
            "/api/commander/chatops/bindings/me",
            headers={"Authorization": "Bearer demo-token"},
        )
        revoke_response = client.post(
            "/api/commander/chatops/bindings/me/revoke",
            headers={"Authorization": "Bearer demo-token"},
        )

    assert issue_response.status_code == 200
    issue_payload = issue_response.json()
    assert issue_payload["pending_code"]["code"].startswith("BIND-")
    assert me_response.status_code == 200
    assert me_response.json()["pending_code"]["code"] == issue_payload["pending_code"]["code"]
    assert revoke_response.status_code == 200
    assert revoke_response.json()["revoked"] is False
    assert auth.record_audit_event.call_count == 2


def test_chatops_simulate_public_status_routes_to_gateway(monkeypatch):
    client = _make_client()
    gateway = MagicMock()
    gateway.execute_command = AsyncMock(return_value={
        "command_id": "platform.status",
        "run": {"run_id": "run-status", "command_id": "platform.status", "status": "succeeded"},
        "approval": None,
        "result": {
            "summary": {"registered_agents": 6, "healthy_agents": 6, "active_agents": 6},
            "chatops": {"ready": True, "platform_ready": True, "summary": "ready"},
        },
    })
    binding_service = MagicMock()
    binding_service.resolve_bound_user.return_value = None
    binding_service.touch_binding.return_value = None

    with patch("routers.commander.get_commander_command_gateway", return_value=gateway), \
         patch("routers.commander.get_commander_chatops_binding_service", return_value=binding_service), \
         patch("routers.commander._get_chatops_overview", return_value={"recent_events": []}), \
         patch("routers.commander.execute", return_value=None):
        response = client.post(
            "/api/commander/chatops/simulate",
            json={
                "message": "状态",
                "from_user": "ou_unbound",
                "chat_id": "oc_demo",
                "deliver": False,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["run"]["run_id"] == "run-status"
    assert "Legion status" in body["result"]["response"]
    gateway.execute_command.assert_awaited_once()
    _, kwargs = gateway.execute_command.await_args
    assert kwargs["source"] == "simulation"
    assert kwargs["source_context"]["binding_status"] == "unbound"
    assert kwargs["source_context"]["raw_message"] == "状态"


def test_chatops_simulate_unbound_write_command_requires_binding(monkeypatch):
    client = _make_client()
    gateway = MagicMock()
    gateway.execute_command = AsyncMock()
    binding_service = MagicMock()
    binding_service.resolve_bound_user.return_value = None

    with patch("routers.commander.get_commander_command_gateway", return_value=gateway), \
         patch("routers.commander.get_commander_chatops_binding_service", return_value=binding_service), \
         patch("routers.commander._get_chatops_overview", return_value={"recent_events": []}), \
         patch("routers.commander.execute", return_value=None):
        response = client.post(
            "/api/commander/chatops/simulate",
            json={
                "message": "测试 https://demo.example.com 登录流程",
                "from_user": "ou_unbound",
                "chat_id": "oc_demo",
                "deliver": False,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert "not linked to a platform account" in body["result"]["response"]
    gateway.execute_command.assert_not_called()


def test_notification_platform_event_receive_bound_report_routes_to_gateway(monkeypatch):
    client = _make_client()
    bound_user = _make_user("user_1", "alice")
    gateway = MagicMock()
    gateway.execute_command = AsyncMock(return_value={
        "command_id": "commander.mission.report",
        "run": {"run_id": "run-report", "command_id": "commander.mission.report", "status": "succeeded"},
        "approval": None,
        "result": {
            "mission_id": "mission-1",
            "summary": {"total_tests": 3, "completed": 3, "failed": 0, "success_rate": 100},
        },
    })
    binding_service = MagicMock()
    binding_service.resolve_bound_user.return_value = bound_user
    binding_service.touch_binding.return_value = None

    payload = {
        "schema": "2.0",
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "sender": {
                "sender_id": {"open_id": "ou_bound"},
                "sender_type": "user",
            },
            "message": {
                "chat_id": "oc_demo",
                "message_type": "text",
                "content": json.dumps({"text": "报告 mission-1"}, ensure_ascii=False),
            },
        },
    }

    with patch("routers.commander.get_commander_command_gateway", return_value=gateway), \
         patch("routers.commander.get_commander_chatops_binding_service", return_value=binding_service), \
         patch("routers.commander._deliver_commander_response", AsyncMock(return_value={"configured": 0, "delivered": 0, "failed": 0, "mode": "webhook_only"})), \
         patch("routers.commander.execute", return_value=None):
        response = client.post("/api/commander/notification_platform/events", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    gateway.execute_command.assert_awaited_once()
    _, kwargs = gateway.execute_command.await_args
    assert kwargs["source"] == "notification_platform"
    assert kwargs["source_context"]["from_user"] == "ou_bound"
    assert kwargs["source_context"]["chat_id"] == "oc_demo"
