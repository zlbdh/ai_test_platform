# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.commander import router as commander_router
from services.auth_service import Permission
from services.commander_command_gateway_service import CommandConfirmationRequiredError


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(commander_router)
    return TestClient(app)


def _allow_permissions(auth: MagicMock, *permissions: Permission):
    allowed = set(permissions)
    auth.check_permission.side_effect = lambda _user, permission: permission in allowed


def test_commander_commands_require_token():
    client = _make_client()

    with patch("core.auth_dependencies.get_auth_service") as mock_get_auth:
        response = client.get("/api/commander/commands")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication token required"
    mock_get_auth.assert_not_called()


def test_commander_commands_list_returns_gateway_payload_for_view_user():
    client = _make_client()
    auth = MagicMock()
    viewer_user = SimpleNamespace(user_id="viewer1", username="viewer")
    auth.validate_token.return_value = viewer_user
    _allow_permissions(auth, Permission.VIEW_RESULTS, Permission.DEPLOY_VIEW)
    gateway = MagicMock()
    gateway.list_commands.return_value = [
        {"command_id": "platform.status", "allowed": True},
        {"command_id": "deploy.job.cancel", "allowed": False},
    ]

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.commander.get_commander_command_gateway", return_value=gateway):
        response = client.get(
            "/api/commander/commands",
            headers={"Authorization": "Bearer viewer-token"},
        )

    assert response.status_code == 200
    assert response.json()["commands"] == [
        {"command_id": "platform.status", "allowed": True},
        {"command_id": "deploy.job.cancel", "allowed": False},
    ]
    gateway.list_commands.assert_called_once_with(user=viewer_user)


def test_commander_command_execute_returns_gateway_result():
    client = _make_client()
    auth = MagicMock()
    admin_user = SimpleNamespace(user_id="admin1", username="admin")
    auth.validate_token.return_value = admin_user
    auth.check_permission.return_value = True
    gateway = MagicMock()
    gateway.execute_command = AsyncMock(
        return_value={
            "command_id": "deploy.job.cancel",
            "risk_level": "high",
            "read_only": False,
            "run": {"run_id": "cmdrun_demo", "status": "approval_pending"},
            "approval": {"approval_id": "cmdapproval_demo", "status": "pending"},
            "result": None,
        }
    )

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.commander.get_commander_command_gateway", return_value=gateway):
        response = client.post(
            "/api/commander/commands/execute",
            headers={"Authorization": "Bearer admin-token"},
            json={
                "command_id": "deploy.job.cancel",
                "arguments": {"job_id": "job_demo"},
                "confirm": True,
            },
        )

    assert response.status_code == 200
    assert response.json()["result"]["run"]["status"] == "approval_pending"
    gateway.execute_command.assert_awaited_once_with(
        "deploy.job.cancel",
        {"job_id": "job_demo"},
        user=admin_user,
        confirm=True,
        source="web",
    )


def test_commander_command_execute_supports_release_deploy_request():
    client = _make_client()
    auth = MagicMock()
    deploy_user = SimpleNamespace(user_id="dev1", username="dev")
    auth.validate_token.return_value = deploy_user
    auth.check_permission.return_value = True
    gateway = MagicMock()
    gateway.execute_command = AsyncMock(
        return_value={
            "command_id": "release.deploy.request",
            "risk_level": "high",
            "read_only": False,
            "run": {"run_id": "cmdrun_release", "status": "succeeded"},
            "approval": None,
            "result": {
                "assessment_id": "assessment-1",
                "approval_id": "approval-1",
                "job_id": "job-1",
                "release_decision": "auto_executed",
            },
        }
    )

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.commander.get_commander_command_gateway", return_value=gateway):
        response = client.post(
            "/api/commander/commands/execute",
            headers={"Authorization": "Bearer deploy-token"},
            json={
                "command_id": "release.deploy.request",
                "arguments": {
                    "assessment_id": "assessment-1",
                    "target_type": "repo",
                    "repo_id": "repo-1",
                    "branch": "main",
                    "comment": "自动发布",
                },
                "confirm": True,
            },
        )

    assert response.status_code == 200
    assert response.json()["result"]["result"]["release_decision"] == "auto_executed"
    gateway.execute_command.assert_awaited_once_with(
        "release.deploy.request",
        {
            "assessment_id": "assessment-1",
            "target_type": "repo",
            "repo_id": "repo-1",
            "branch": "main",
            "comment": "自动发布",
        },
        user=deploy_user,
        confirm=True,
        source="web",
    )


def test_commander_command_execute_maps_confirmation_error():
    client = _make_client()
    auth = MagicMock()
    admin_user = SimpleNamespace(user_id="admin1", username="admin")
    auth.validate_token.return_value = admin_user
    auth.check_permission.return_value = True
    gateway = MagicMock()
    gateway.execute_command = AsyncMock(
        side_effect=CommandConfirmationRequiredError("命令 deploy.job.cancel 为高风险动作，需显式确认 confirm=true")
    )

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.commander.get_commander_command_gateway", return_value=gateway):
        response = client.post(
            "/api/commander/commands/execute",
            headers={"Authorization": "Bearer admin-token"},
            json={
                "command_id": "deploy.job.cancel",
                "arguments": {"job_id": "job_demo"},
                "confirm": False,
            },
        )

    assert response.status_code == 409
    assert "confirm=true" in response.json()["detail"]


def test_commander_command_runs_list_returns_gateway_payload():
    client = _make_client()
    auth = MagicMock()
    viewer_user = SimpleNamespace(user_id="viewer1", username="viewer")
    auth.validate_token.return_value = viewer_user
    auth.check_permission.return_value = True
    gateway = MagicMock()
    gateway.list_command_runs.return_value = {
        "runs": [{"run_id": "cmdrun_demo", "status": "approval_pending"}],
        "count": 1,
    }

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.commander.get_commander_command_gateway", return_value=gateway):
        response = client.get(
            "/api/commander/commands/runs?approval_status=pending&project_key=demo&source=notification_platform&limit=5",
            headers={"Authorization": "Bearer viewer-token"},
        )

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["runs"][0]["run_id"] == "cmdrun_demo"
    gateway.list_command_runs.assert_called_once_with(
        user=viewer_user,
        status="",
        approval_status="pending",
        command_id="",
        project_key="demo",
        source="notification_platform",
        limit=5,
    )


def test_commander_command_run_approve_returns_gateway_payload():
    client = _make_client()
    auth = MagicMock()
    admin_user = SimpleNamespace(user_id="admin1", username="admin")
    auth.validate_token.return_value = admin_user
    auth.check_permission.return_value = True
    gateway = MagicMock()
    gateway.approve_command_run = AsyncMock(
        return_value={
            "run": {"run_id": "cmdrun_demo", "status": "succeeded"},
            "approval": {"approval_id": "cmdapproval_demo", "status": "approved"},
            "result": {"job": {"id": "job_demo", "status": "cancelled"}},
        }
    )

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.commander.get_commander_command_gateway", return_value=gateway):
        response = client.post(
            "/api/commander/commands/runs/cmdrun_demo/approve",
            headers={"Authorization": "Bearer admin-token"},
            json={"comment": "批准", "confirm": True},
        )

    assert response.status_code == 200
    assert response.json()["run"]["status"] == "succeeded"
    assert response.json()["approval"]["status"] == "approved"
    gateway.approve_command_run.assert_awaited_once_with(
        "cmdrun_demo",
        user=admin_user,
        comment="批准",
        confirm=True,
        source="web",
    )


def test_commander_command_run_reject_returns_gateway_payload():
    client = _make_client()
    auth = MagicMock()
    admin_user = SimpleNamespace(user_id="admin1", username="admin")
    auth.validate_token.return_value = admin_user
    auth.check_permission.return_value = True
    gateway = MagicMock()
    gateway.reject_command_run.return_value = {
        "run": {"run_id": "cmdrun_demo", "status": "rejected"},
        "approval": {"approval_id": "cmdapproval_demo", "status": "rejected"},
    }

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.commander.get_commander_command_gateway", return_value=gateway):
        response = client.post(
            "/api/commander/commands/runs/cmdrun_demo/reject",
            headers={"Authorization": "Bearer admin-token"},
            json={"comment": "驳回"},
        )

    assert response.status_code == 200
    assert response.json()["run"]["status"] == "rejected"
    assert response.json()["approval"]["status"] == "rejected"
    gateway.reject_command_run.assert_called_once_with(
        "cmdrun_demo",
        user=admin_user,
        reason="驳回",
        source="web",
    )
