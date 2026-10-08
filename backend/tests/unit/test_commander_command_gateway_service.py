# -*- coding: utf-8 -*-
from contextlib import contextmanager
import sqlite3
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from services.auth_service import Permission
from services.commander_command_gateway_service import (
    CommandConfirmationRequiredError,
    CommanderCommandGatewayService,
)


def _make_user(role: str = "tester", project_ids=None):
    return SimpleNamespace(
        user_id="user_demo",
        username="demo",
        role=SimpleNamespace(value=role),
        project_ids=list(project_ids or []),
    )


def _allow_permissions(auth: MagicMock, *permissions: Permission):
    allowed = set(permissions)
    auth.check_permission.side_effect = lambda _user, permission: permission in allowed


def _patch_temp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "command_gateway.db"

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
        "services.commander_command_gateway_service.get_connection",
        _get_connection,
    )
    monkeypatch.setattr("services.exploration_service.get_connection", _get_connection)
    monkeypatch.setattr("services.release_risk_service.get_connection", _get_connection)
    monkeypatch.setattr("services.exploration_service._service_instance", None)
    monkeypatch.setattr("services.release_risk_service._service_instance", None)


def test_list_commands_marks_permission_and_approval_metadata(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    auth = MagicMock()
    _allow_permissions(auth, Permission.VIEW_RESULTS, Permission.DEPLOY_VIEW)
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_auth_service",
        lambda: auth,
    )

    service = CommanderCommandGatewayService()
    commands = service.list_commands(user=_make_user(role="tester", project_ids=["demo"]))
    by_id = {item["command_id"]: item for item in commands}

    assert by_id["platform.status"]["allowed"] is True
    assert by_id["deploy.jobs.list"]["allowed"] is True
    assert by_id["deploy.job.cancel"]["allowed"] is False
    assert by_id["deploy.job.cancel"]["requires_confirmation"] is True
    assert by_id["deploy.job.cancel"]["approval_required"] is True
    assert by_id["deploy.job.cancel"]["approval_policy"] == "required"


@pytest.mark.asyncio
async def test_execute_deploy_jobs_list_filters_scope_and_persists_run(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    auth = MagicMock()
    _allow_permissions(auth, Permission.DEPLOY_VIEW)
    deploy_service = MagicMock()
    deploy_service.list_jobs.return_value = [
        {"id": "job_demo", "status": "queued", "project_key": "demo"},
        {"id": "job_other", "status": "running", "project_key": "proj2"},
    ]
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_auth_service",
        lambda: auth,
    )
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_deploy_service",
        lambda: deploy_service,
    )

    service = CommanderCommandGatewayService()
    user = _make_user(role="tester", project_ids=["demo"])
    result = await service.execute_command(
        "deploy.jobs.list",
        {"limit": 20},
        user=user,
    )

    assert result["result"]["jobs"] == [{"id": "job_demo", "status": "queued", "project_key": "demo"}]
    assert result["run"]["status"] == "succeeded"
    runs = service.list_command_runs(user=user)
    assert runs["count"] == 1
    assert runs["runs"][0]["command_id"] == "deploy.jobs.list"
    deploy_service.list_jobs.assert_called_once_with(limit=20, status="")


@pytest.mark.asyncio
async def test_execute_exploration_session_create_returns_structured_session(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    auth = MagicMock()
    _allow_permissions(auth, Permission.RUN_TEST, Permission.VIEW_RESULTS)
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_auth_service",
        lambda: auth,
    )

    service = CommanderCommandGatewayService()
    result = await service.execute_command(
        "exploration.session.create",
        {
            "project_key": "demo",
            "target_url": "https://demo.example.com/login",
            "charter": "围绕登录与认证链路做探索",
        },
        user=_make_user(role="tester", project_ids=["demo"]),
        source="api",
    )

    assert result["run"]["status"] == "succeeded"
    assert result["result"]["session"]["project_key"] == "demo"
    assert result["result"]["session"]["summary"]["finding_count"] >= 1


@pytest.mark.asyncio
async def test_execute_release_risk_assess_uses_exploration_findings(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    auth = MagicMock()
    _allow_permissions(auth, Permission.RUN_TEST, Permission.VIEW_RESULTS, Permission.DEPLOY_VIEW)
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_auth_service",
        lambda: auth,
    )

    service = CommanderCommandGatewayService()
    user = _make_user(role="developer", project_ids=["demo"])
    exploration = await service.execute_command(
        "exploration.session.create",
        {
            "project_key": "demo",
            "target_url": "https://demo.example.com/home",
            "charter": "做一轮通用回归探索",
        },
        user=user,
        source="api",
    )
    session_id = exploration["result"]["session"]["session_id"]

    assessment = await service.execute_command(
        "release.risk.assess",
        {
            "project_key": "demo",
            "environment": "staging",
            "exploration_session_ids": [session_id],
            "required_tests_passed": True,
            "change_summary": "Minor home page styling update",
        },
        user=user,
        source="api",
    )

    assert assessment["run"]["status"] == "succeeded"
    assert assessment["result"]["assessment"]["release_risk"] == "low"
    assert assessment["result"]["assessment"]["auto_release_eligible"] is True
    assert assessment["result"]["assessment"]["policy_hit"]["review_blocked"] is False
    assert assessment["result"]["assessment"]["evidence"]["review_summary"]["effective"] >= 1


@pytest.mark.asyncio
async def test_execute_release_risk_assess_reflects_review_blockers(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    auth = MagicMock()
    _allow_permissions(auth, Permission.RUN_TEST, Permission.VIEW_RESULTS, Permission.DEPLOY_VIEW)
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_auth_service",
        lambda: auth,
    )

    service = CommanderCommandGatewayService()
    user = _make_user(role="developer", project_ids=["demo"])
    exploration = await service.execute_command(
        "exploration.session.create",
        {
            "project_key": "demo",
            "target_url": "https://demo.example.com/login",
            "charter": "围绕登录与认证链路做探索",
        },
        user=user,
        source="web",
    )
    finding_id = exploration["result"]["session"]["findings"][0]["finding_id"]

    await service.execute_command(
        "exploration.finding.review",
        {
            "finding_id": finding_id,
            "decision": "confirmed",
            "comment": "Blocked after manual review",
        },
        user=user,
        source="web",
    )

    assessment = await service.execute_command(
        "release.risk.assess",
        {
            "project_key": "demo",
            "environment": "staging",
            "exploration_session_ids": [exploration["result"]["session"]["session_id"]],
            "required_tests_passed": True,
            "change_summary": "Login flow update",
        },
        user=user,
        source="web",
    )

    blocker_types = {item["type"] for item in assessment["result"]["assessment"]["blockers"]}
    assert assessment["run"]["status"] == "succeeded"
    assert "confirmed_issue_requires_manual_release" in blocker_types
    assert assessment["result"]["assessment"]["policy_hit"]["review_blocked"] is True
    assert assessment["result"]["assessment"]["evidence"]["confirmed_findings"] == [finding_id]


@pytest.mark.asyncio
async def test_execute_release_deploy_request_auto_executes_nonprod_low_risk(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    auth = MagicMock()
    _allow_permissions(auth, Permission.RUN_TEST, Permission.VIEW_RESULTS, Permission.DEPLOY_VIEW, Permission.DEPLOY_REQUEST)
    deploy_service = MagicMock()
    deploy_service.create_deploy_approval.return_value = {
        "id": "approval_auto",
        "project_key": "demo",
        "repo_id": "repo1",
        "branch": "main",
        "status": "pending",
        "message": "Awaiting approval",
        "request_comment": "Release under the low-risk policy",
    }
    deploy_service.review_approval.return_value = {
        "id": "approval_auto",
        "project_key": "demo",
        "repo_id": "repo1",
        "branch": "main",
        "status": "approved",
        "message": "Approval granted; deployment job created",
        "job_id": "job_auto",
        "job": {"id": "job_auto", "project_key": "demo", "status": "queued"},
    }
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_auth_service",
        lambda: auth,
    )
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_deploy_service",
        lambda: deploy_service,
    )

    service = CommanderCommandGatewayService()
    user = _make_user(role="developer", project_ids=["demo"])
    exploration = await service.execute_command(
        "exploration.session.create",
        {
            "project_key": "demo",
            "target_url": "https://demo.example.com/home",
            "charter": "做一轮通用回归探索",
        },
        user=user,
        source="web",
    )
    assessment = await service.execute_command(
        "release.risk.assess",
        {
            "project_key": "demo",
            "environment": "staging",
            "exploration_session_ids": [exploration["result"]["session"]["session_id"]],
            "required_tests_passed": True,
            "change_summary": "Minor home page styling update",
        },
        user=user,
        source="web",
    )

    result = await service.execute_command(
        "release.deploy.request",
        {
            "assessment_id": assessment["result"]["assessment"]["assessment_id"],
            "target_type": "repo",
            "repo_id": "repo1",
            "branch": "main",
            "comment": "Release under the low-risk policy",
        },
        user=user,
        confirm=True,
        source="web",
    )

    assert result["run"]["status"] == "succeeded"
    assert result["result"]["release_decision"] == "auto_executed"
    assert result["result"]["approval_id"] == "approval_auto"
    assert result["result"]["job_id"] == "job_auto"
    assert result["result"]["deploy_target"] == {
        "target_type": "repo",
        "project_key": "demo",
        "repo_id": "repo1",
        "branch": "main",
    }
    deploy_service.create_deploy_approval.assert_called_once_with(
        action="full_deploy",
        project_key="demo",
        repo_id="repo1",
        branch="main",
        request_comment="Release under the low-risk policy",
        requested_by="user_demo",
        requested_by_name="demo",
    )
    deploy_service.review_approval.assert_called_once()
    action_names = [call.kwargs["action"] for call in auth.record_audit_event.call_args_list]
    assert "deploy_approval_request_create" in action_names
    assert "deploy_approval_approve" in action_names


@pytest.mark.asyncio
async def test_execute_release_deploy_request_creates_pending_approval_when_review_blocked(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    auth = MagicMock()
    _allow_permissions(auth, Permission.RUN_TEST, Permission.VIEW_RESULTS, Permission.DEPLOY_VIEW, Permission.DEPLOY_REQUEST)
    deploy_service = MagicMock()
    deploy_service.create_deploy_approval.return_value = {
        "id": "approval_pending",
        "project_key": "demo",
        "repo_id": "",
        "branch": "",
        "status": "pending",
        "message": "Awaiting approval",
        "request_comment": "Awaiting manual approval",
    }
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_auth_service",
        lambda: auth,
    )
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_deploy_service",
        lambda: deploy_service,
    )

    service = CommanderCommandGatewayService()
    user = _make_user(role="developer", project_ids=["demo"])
    exploration = await service.execute_command(
        "exploration.session.create",
        {
            "project_key": "demo",
            "target_url": "https://demo.example.com/login",
            "charter": "围绕登录与认证链路做探索",
        },
        user=user,
        source="web",
    )
    finding_id = exploration["result"]["session"]["findings"][0]["finding_id"]
    await service.execute_command(
        "exploration.finding.review",
        {
            "finding_id": finding_id,
            "decision": "confirmed",
            "comment": "Blocked after manual review",
        },
        user=user,
        source="web",
    )
    assessment = await service.execute_command(
        "release.risk.assess",
        {
            "project_key": "demo",
            "environment": "staging",
            "exploration_session_ids": [exploration["result"]["session"]["session_id"]],
            "required_tests_passed": True,
            "change_summary": "Login flow update",
        },
        user=user,
        source="web",
    )

    result = await service.execute_command(
        "release.deploy.request",
        {
            "assessment_id": assessment["result"]["assessment"]["assessment_id"],
            "target_type": "project",
            "comment": "Awaiting manual approval",
        },
        user=user,
        confirm=True,
        source="web",
    )

    assert result["run"]["status"] == "succeeded"
    assert result["result"]["release_decision"] == "approval_created"
    assert result["result"]["approval_id"] == "approval_pending"
    assert result["result"]["job_id"] == ""
    assert result["result"]["job"] is None
    deploy_service.create_deploy_approval.assert_called_once_with(
        action="full_deploy_all",
        project_key="demo",
        repo_id="",
        branch="",
        request_comment="Awaiting manual approval",
        requested_by="user_demo",
        requested_by_name="demo",
    )
    deploy_service.review_approval.assert_not_called()
    action_names = [call.kwargs["action"] for call in auth.record_audit_event.call_args_list]
    assert "deploy_approval_request_create" in action_names
    assert "deploy_approval_approve" not in action_names


@pytest.mark.asyncio
async def test_execute_release_deploy_request_keeps_production_pending_even_if_auto_release_eligible(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    auth = MagicMock()
    _allow_permissions(auth, Permission.DEPLOY_REQUEST, Permission.DEPLOY_VIEW)
    deploy_service = MagicMock()
    deploy_service.create_deploy_approval.return_value = {
        "id": "approval_prod",
        "project_key": "demo",
        "repo_id": "repo1",
        "branch": "release",
        "status": "pending",
        "message": "Awaiting approval",
    }
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_auth_service",
        lambda: auth,
    )
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_deploy_service",
        lambda: deploy_service,
    )

    service = CommanderCommandGatewayService()
    user = _make_user(role="developer", project_ids=["demo"])
    with patch(
        "services.release_risk_service.get_release_risk_service"
    ) as mock_release:
        mock_release.return_value.get_assessment.return_value = {
            "assessment_id": "release_prod",
            "project_key": "demo",
            "environment": "production",
            "auto_release_eligible": True,
            "blockers": [],
            "policy_hit": {"review_blocked": False},
            "input": {"environment": "production"},
        }

        result = await service.execute_command(
            "release.deploy.request",
            {
                "assessment_id": "release_prod",
                "target_type": "repo",
                "repo_id": "repo1",
                "branch": "release",
            },
            user=user,
            confirm=True,
            source="web",
        )

    assert result["run"]["status"] == "succeeded"
    assert result["result"]["release_decision"] == "approval_created"
    assert result["result"]["job_id"] == ""
    deploy_service.review_approval.assert_not_called()


@pytest.mark.asyncio
async def test_execute_exploration_review_queue_list_returns_pending_findings(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    auth = MagicMock()
    _allow_permissions(auth, Permission.RUN_TEST, Permission.VIEW_RESULTS)
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_auth_service",
        lambda: auth,
    )

    service = CommanderCommandGatewayService()
    user = _make_user(role="tester", project_ids=["demo"])
    exploration = await service.execute_command(
        "exploration.session.create",
        {
            "project_key": "demo",
            "target_url": "https://demo.example.com/login",
            "charter": "围绕登录与认证链路做探索",
        },
        user=user,
        source="web",
    )
    assert exploration["result"]["session"]["summary"]["requires_human_review_count"] >= 1

    queue = await service.execute_command(
        "exploration.review.queue.list",
        {
            "project_key": "demo",
            "review_status": "pending",
        },
        user=user,
        source="web",
    )

    assert queue["run"]["status"] == "succeeded"
    assert queue["result"]["review_status"] == "pending"
    assert queue["result"]["count"] >= 1
    assert all(item["requires_human_review"] for item in queue["result"]["findings"])


@pytest.mark.asyncio
async def test_execute_exploration_finding_review_returns_updated_finding(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    auth = MagicMock()
    _allow_permissions(auth, Permission.RUN_TEST, Permission.VIEW_RESULTS)
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_auth_service",
        lambda: auth,
    )

    service = CommanderCommandGatewayService()
    user = _make_user(role="tester", project_ids=["demo"])
    exploration = await service.execute_command(
        "exploration.session.create",
        {
            "project_key": "demo",
            "target_url": "https://demo.example.com/login",
            "charter": "围绕登录与认证链路做探索",
        },
        user=user,
        source="web",
    )
    finding_id = exploration["result"]["session"]["findings"][0]["finding_id"]

    reviewed = await service.execute_command(
        "exploration.finding.review",
        {
            "finding_id": finding_id,
            "decision": "confirmed",
            "comment": "Manual review",
        },
        user=user,
        source="web",
    )

    assert reviewed["run"]["status"] == "succeeded"
    assert reviewed["result"]["finding"]["finding_id"] == finding_id
    assert reviewed["result"]["finding"]["review_status"] == "confirmed"
    assert reviewed["result"]["finding"]["review_comment"] == "Manual review"


@pytest.mark.asyncio
async def test_list_command_runs_supports_project_filter(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    auth = MagicMock()
    _allow_permissions(auth, Permission.RUN_TEST, Permission.VIEW_RESULTS)
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_auth_service",
        lambda: auth,
    )

    service = CommanderCommandGatewayService()
    user = _make_user(role="tester", project_ids=["demo"])
    await service.execute_command(
        "exploration.session.create",
        {
            "project_key": "demo",
            "target_url": "https://demo.example.com/login",
            "charter": "围绕登录与认证链路做探索",
        },
        user=user,
        source="api",
    )
    await service.execute_command(
        "exploration.session.create",
        {
            "project_key": "proj2",
            "target_url": "https://proj2.example.com/home",
            "charter": "做一轮通用回归探索",
        },
        user=_make_user(role="tester", project_ids=["proj2"]),
        source="api",
    )

    payload = service.list_command_runs(
        user=user,
        project_key="demo",
        limit=10,
    )

    assert payload["count"] == 1
    assert payload["runs"][0]["project_key"] == "demo"


@pytest.mark.asyncio
async def test_execute_cancel_requires_explicit_confirmation(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    auth = MagicMock()
    _allow_permissions(auth, Permission.ADMIN)
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_auth_service",
        lambda: auth,
    )

    service = CommanderCommandGatewayService()

    with pytest.raises(CommandConfirmationRequiredError):
        await service.execute_command(
            "deploy.job.cancel",
            {"job_id": "job_demo"},
            user=_make_user(role="admin", project_ids=["demo"]),
            confirm=False,
        )


@pytest.mark.asyncio
async def test_execute_cancel_creates_pending_approval(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    auth = MagicMock()
    _allow_permissions(auth, Permission.ADMIN)
    deploy_service = MagicMock()
    deploy_service.get_job_detail.return_value = {
        "id": "job_demo",
        "project_key": "demo",
        "record_id": "rec_demo",
    }
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_auth_service",
        lambda: auth,
    )
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_deploy_service",
        lambda: deploy_service,
    )

    service = CommanderCommandGatewayService()
    result = await service.execute_command(
        "deploy.job.cancel",
        {"job_id": "job_demo"},
        user=_make_user(role="admin", project_ids=["demo"]),
        confirm=True,
        source="api",
    )

    assert result["result"] is None
    assert result["run"]["status"] == "approval_pending"
    assert result["run"]["approval_status"] == "pending"
    assert result["approval"]["status"] == "pending"
    deploy_service.cancel_job.assert_not_called()
    assert auth.record_audit_event.call_count == 2


@pytest.mark.asyncio
async def test_approve_command_run_executes_cancel_and_records_audit(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    auth = MagicMock()
    _allow_permissions(auth, Permission.ADMIN, Permission.DEPLOY_APPROVE)
    deploy_service = MagicMock()
    deploy_service.get_job_detail.return_value = {
        "id": "job_demo",
        "project_key": "demo",
        "record_id": "rec_demo",
    }
    deploy_service.cancel_job.return_value = {
        "id": "job_demo",
        "status": "cancelled",
        "record_id": "rec_demo",
    }
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_auth_service",
        lambda: auth,
    )
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_deploy_service",
        lambda: deploy_service,
    )

    service = CommanderCommandGatewayService()
    requester = _make_user(role="admin", project_ids=["demo"])
    created = await service.execute_command(
        "deploy.job.cancel",
        {"job_id": "job_demo"},
        user=requester,
        confirm=True,
        source="api",
    )

    approved = await service.approve_command_run(
        created["run"]["run_id"],
        user=requester,
        comment="Approve job cancellation",
        source="api",
    )

    assert approved["run"]["status"] == "succeeded"
    assert approved["run"]["approval_status"] == "approved"
    assert approved["approval"]["status"] == "approved"
    assert approved["result"]["job"]["status"] == "cancelled"
    deploy_service.cancel_job.assert_called_once_with("job_demo")
    audit_actions = [call.kwargs["action"] for call in auth.record_audit_event.call_args_list]
    assert audit_actions == [
        "commander_command_requested",
        "commander_command_approval_requested",
        "commander_command_approval_approved",
        "commander_command_executed",
    ]


@pytest.mark.asyncio
async def test_reject_command_run_marks_rejected_without_execution(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    auth = MagicMock()
    _allow_permissions(auth, Permission.ADMIN, Permission.DEPLOY_APPROVE)
    deploy_service = MagicMock()
    deploy_service.get_job_detail.return_value = {
        "id": "job_demo",
        "project_key": "demo",
        "record_id": "rec_demo",
    }
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_auth_service",
        lambda: auth,
    )
    monkeypatch.setattr(
        "services.commander_command_gateway_service.get_deploy_service",
        lambda: deploy_service,
    )

    service = CommanderCommandGatewayService()
    requester = _make_user(role="admin", project_ids=["demo"])
    created = await service.execute_command(
        "deploy.job.cancel",
        {"job_id": "job_demo"},
        user=requester,
        confirm=True,
        source="api",
    )

    rejected = service.reject_command_run(
        created["run"]["run_id"],
        user=requester,
        reason="Cancellation is not allowed in the current window",
        source="api",
    )

    assert rejected["run"]["status"] == "rejected"
    assert rejected["run"]["approval_status"] == "rejected"
    assert rejected["approval"]["status"] == "rejected"
    deploy_service.cancel_job.assert_not_called()
