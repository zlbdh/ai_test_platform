# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.deploy import router as deploy_router
from services.auth_service import AuditLog, Permission


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(deploy_router)
    return TestClient(app)


def _allow_permissions(auth: MagicMock, *permissions: Permission):
    allowed = set(permissions)
    auth.check_permission.side_effect = lambda _user, permission: permission in allowed


def test_deploy_routes_require_token():
    client = _make_client()

    with patch("core.auth_dependencies.get_auth_service") as mock_get_auth:
        response = client.get("/api/deploy/projects")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication token required"
    mock_get_auth.assert_not_called()


def test_admin_routes_require_admin_permission():
    client = _make_client()
    auth = MagicMock()
    auth.validate_token.return_value = MagicMock(user_id="tester")
    auth.check_permission.return_value = False

    with patch("core.auth_dependencies.get_auth_service", return_value=auth):
        response = client.post("/api/deploy/repo/proj1/repo1/full?token=tester-token", json={"branch": "release"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"
    auth.validate_token.assert_called_once_with("tester-token")


def test_get_projects_accepts_bearer_token_for_admin():
    client = _make_client()
    auth = MagicMock()
    admin_user = MagicMock(user_id="admin")
    auth.validate_token.return_value = admin_user
    auth.check_permission.return_value = True
    deploy_service = MagicMock()
    deploy_service.get_all_projects.return_value = [{"key": "demo", "name": "Demo"}]

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_deploy_service", return_value=deploy_service):
        response = client.get(
            "/api/deploy/projects",
            headers={"Authorization": "Bearer admin-token"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["data"]["projects"] == [{"key": "demo", "name": "Demo"}]
    auth.validate_token.assert_called_once_with("admin-token")
    auth.record_audit_event.assert_not_called()
    deploy_service.get_all_projects.assert_called_once()


def test_get_projects_accepts_deploy_view_permission():
    client = _make_client()
    auth = MagicMock()
    viewer_user = SimpleNamespace(user_id="viewer1", username="viewer")
    auth.validate_token.return_value = viewer_user
    _allow_permissions(auth, Permission.DEPLOY_VIEW)
    deploy_service = MagicMock()
    deploy_service.get_all_projects.return_value = [{"key": "demo", "name": "Demo"}]

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_deploy_service", return_value=deploy_service):
        response = client.get(
            "/api/deploy/projects",
            headers={"X-Auth-Token": "viewer-token"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["projects"] == [{"key": "demo", "name": "Demo"}]
    deploy_service.get_all_projects.assert_called_once()


def test_get_projects_filters_by_project_scope():
    client = _make_client()
    auth = MagicMock()
    scoped_user = SimpleNamespace(
        user_id="viewer1",
        username="viewer",
        role="tester",
        project_ids=["demo"],
    )
    auth.validate_token.return_value = scoped_user
    _allow_permissions(auth, Permission.DEPLOY_VIEW)
    deploy_service = MagicMock()
    deploy_service.get_all_projects.return_value = [
        {"key": "demo", "name": "Demo"},
        {"key": "proj2", "name": "Hidden"},
    ]

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_deploy_service", return_value=deploy_service):
        response = client.get(
            "/api/deploy/projects",
            headers={"Authorization": "Bearer viewer-token"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["projects"] == [{"key": "demo", "name": "Demo"}]
    deploy_service.get_all_projects.assert_called_once()


def test_add_project_accepts_token_from_json_body():
    client = _make_client()
    auth = MagicMock()
    admin_user = MagicMock(user_id="admin")
    auth.validate_token.return_value = admin_user
    auth.check_permission.return_value = True
    deploy_service = MagicMock()
    deploy_service.add_project.return_value = SimpleNamespace(key="proj_demo")
    deploy_service.get_project_detail.return_value = {"key": "proj_demo", "name": "Demo"}

    payload = {
        "name": "Demo",
        "repos": [
            {
                "label": "Frontend",
                "repo_url": "https://example.com/demo.git",
                "branch": "main",
                "install_cmd": "npm install",
                "start_cmd": "npm run dev",
                "port": 8010,
                "tech_stack": "react",
            }
        ],
        "token": "admin-token",
    }

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_deploy_service", return_value=deploy_service):
        response = client.post("/api/deploy/projects", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["data"]["project"] == {"key": "proj_demo", "name": "Demo"}
    auth.validate_token.assert_called_once_with("admin-token")
    auth.record_audit_event.assert_called_once_with(
        action="deploy_project_add",
        resource_type="deploy_project",
        resource_id="proj_demo",
        details={"project_key": "proj_demo", "project_name": "Demo"},
        user_id="admin",
    )
    deploy_service.add_project.assert_called_once()


def test_full_deploy_returns_job_id_for_admin():
    client = _make_client()
    auth = MagicMock()
    admin_user = MagicMock(user_id="admin")
    auth.validate_token.return_value = admin_user
    auth.check_permission.return_value = True
    deploy_service = MagicMock()
    deploy_service.schedule_full_deploy.return_value = SimpleNamespace(
        id="job_demo",
        record_id="rec_demo",
        status="queued",
    )

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_deploy_service", return_value=deploy_service):
        response = client.post(
            "/api/deploy/repo/proj1/repo1/full",
            headers={"Authorization": "Bearer admin-token"},
            json={"branch": "release"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["job_id"] == "job_demo"
    assert response.json()["data"]["record_id"] == "rec_demo"
    deploy_service.schedule_full_deploy.assert_called_once_with("proj1", "repo1", "release")


def test_full_project_deploy_returns_job_id_for_admin():
    client = _make_client()
    auth = MagicMock()
    admin_user = MagicMock(user_id="admin")
    auth.validate_token.return_value = admin_user
    auth.check_permission.return_value = True
    deploy_service = MagicMock()
    deploy_service.schedule_full_deploy_all.return_value = SimpleNamespace(
        id="job_project_demo",
        record_id="rec_project_demo",
        status="queued",
    )

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_deploy_service", return_value=deploy_service):
        response = client.post(
            "/api/deploy/repo/proj1/deploy-all",
            headers={"Authorization": "Bearer admin-token"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["job_id"] == "job_project_demo"
    assert response.json()["data"]["record_id"] == "rec_project_demo"
    deploy_service.schedule_full_deploy_all.assert_called_once_with("proj1")


def test_list_jobs_returns_service_payload_for_admin():
    client = _make_client()
    auth = MagicMock()
    admin_user = MagicMock(user_id="admin")
    auth.validate_token.return_value = admin_user
    auth.check_permission.return_value = True
    deploy_service = MagicMock()
    deploy_service.list_jobs.return_value = [{"id": "job_demo", "status": "queued"}]

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_deploy_service", return_value=deploy_service):
        response = client.get(
            "/api/deploy/jobs?limit=20&status=queued",
            headers={"Authorization": "Bearer admin-token"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["jobs"] == [{"id": "job_demo", "status": "queued"}]
    deploy_service.list_jobs.assert_called_once_with(limit=20, status="queued")


def test_list_jobs_accepts_deploy_view_permission():
    client = _make_client()
    auth = MagicMock()
    viewer_user = SimpleNamespace(user_id="viewer1", username="viewer")
    auth.validate_token.return_value = viewer_user
    _allow_permissions(auth, Permission.DEPLOY_VIEW)
    deploy_service = MagicMock()
    deploy_service.list_jobs.return_value = [{"id": "job_demo", "status": "queued"}]

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_deploy_service", return_value=deploy_service):
        response = client.get(
            "/api/deploy/jobs?limit=20&status=queued",
            headers={"Authorization": "Bearer viewer-token"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["jobs"] == [{"id": "job_demo", "status": "queued"}]
    deploy_service.list_jobs.assert_called_once_with(limit=20, status="queued")


def test_list_jobs_filters_by_project_scope():
    client = _make_client()
    auth = MagicMock()
    scoped_user = SimpleNamespace(
        user_id="viewer1",
        username="viewer",
        role="tester",
        project_ids=["proj1"],
    )
    auth.validate_token.return_value = scoped_user
    _allow_permissions(auth, Permission.DEPLOY_VIEW)
    deploy_service = MagicMock()
    deploy_service.list_jobs.return_value = [
        {"id": "job_demo", "status": "queued", "project_key": "proj1"},
        {"id": "job_other", "status": "running", "project_key": "proj2"},
    ]

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_deploy_service", return_value=deploy_service):
        response = client.get(
            "/api/deploy/jobs?limit=20",
            headers={"Authorization": "Bearer viewer-token"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["jobs"] == [{"id": "job_demo", "status": "queued", "project_key": "proj1"}]
    deploy_service.list_jobs.assert_called_once_with(limit=20, status="")


def test_cancel_job_returns_service_payload_for_admin():
    client = _make_client()
    auth = MagicMock()
    admin_user = MagicMock(user_id="admin")
    auth.validate_token.return_value = admin_user
    auth.check_permission.return_value = True
    deploy_service = MagicMock()
    deploy_service.get_job_detail.return_value = {
        "id": "job_demo",
        "project_key": "proj1",
        "record_id": "rec_demo",
    }
    deploy_service.cancel_job.return_value = {
        "id": "job_demo",
        "status": "cancelled",
        "record_id": "rec_demo",
    }

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_deploy_service", return_value=deploy_service):
        response = client.post(
            "/api/deploy/jobs/job_demo/cancel",
            headers={"Authorization": "Bearer admin-token"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["job"]["status"] == "cancelled"
    deploy_service.cancel_job.assert_called_once_with("job_demo")
    auth.record_audit_event.assert_called_once_with(
        action="deploy_job_cancel",
        resource_type="deploy_job",
        resource_id="job_demo",
        details={"job_id": "job_demo", "project_key": "proj1", "record_id": "rec_demo"},
        user_id="admin",
    )


def test_request_full_deploy_accepts_deploy_request_permission():
    client = _make_client()
    auth = MagicMock()
    developer_user = SimpleNamespace(user_id="dev1", username="alice")
    auth.validate_token.return_value = developer_user
    _allow_permissions(auth, Permission.DEPLOY_REQUEST)
    deploy_service = MagicMock()
    deploy_service.create_deploy_approval.return_value = {
        "id": "approval_demo",
        "status": "pending",
        "project_key": "proj1",
        "repo_id": "repo1",
    }

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_deploy_service", return_value=deploy_service):
        response = client.post(
            "/api/deploy/repo/proj1/repo1/full/request",
            headers={"Authorization": "Bearer dev-token"},
            json={"branch": "release"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["approval"]["id"] == "approval_demo"
    deploy_service.create_deploy_approval.assert_called_once_with(
        action="full_deploy",
        project_key="proj1",
        repo_id="repo1",
        branch="release",
        requested_by="dev1",
        requested_by_name="alice",
    )
    auth.record_audit_event.assert_called_once_with(
        action="deploy_approval_request_create",
        resource_type="deploy_approval",
        resource_id="approval_demo",
        details={
            "approval_id": "approval_demo",
            "project_key": "proj1",
            "repo_id": "repo1",
            "branch": "release",
        },
        user_id="dev1",
    )


def test_request_full_deploy_rejects_out_of_scope_project():
    client = _make_client()
    auth = MagicMock()
    developer_user = SimpleNamespace(
        user_id="dev1",
        username="alice",
        role="developer",
        project_ids=["proj1"],
    )
    auth.validate_token.return_value = developer_user
    _allow_permissions(auth, Permission.DEPLOY_REQUEST)
    deploy_service = MagicMock()

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_deploy_service", return_value=deploy_service):
        response = client.post(
            "/api/deploy/repo/proj2/repo1/full/request",
            headers={"Authorization": "Bearer dev-token"},
            json={"branch": "release"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Project scope access required"
    deploy_service.create_deploy_approval.assert_not_called()


def test_list_approvals_accepts_deploy_view_permission():
    client = _make_client()
    auth = MagicMock()
    tester_user = SimpleNamespace(user_id="tester1", username="bob")
    auth.validate_token.return_value = tester_user
    _allow_permissions(auth, Permission.DEPLOY_VIEW)
    deploy_service = MagicMock()
    deploy_service.list_approvals.return_value = [{"id": "approval_demo", "status": "pending"}]

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_deploy_service", return_value=deploy_service):
        response = client.get(
            "/api/deploy/approvals?limit=10&status=pending",
            headers={"X-Auth-Token": "tester-token"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["approvals"] == [{"id": "approval_demo", "status": "pending"}]
    deploy_service.list_approvals.assert_called_once_with(limit=10, status="pending")


def test_approve_approval_requires_deploy_approve_permission():
    client = _make_client()
    auth = MagicMock()
    developer_user = SimpleNamespace(user_id="dev1", username="alice")
    auth.validate_token.return_value = developer_user
    _allow_permissions(auth, Permission.DEPLOY_REQUEST, Permission.DEPLOY_VIEW)

    with patch("core.auth_dependencies.get_auth_service", return_value=auth):
        response = client.post(
            "/api/deploy/approvals/approval_demo/approve?token=dev-token",
            json={"comment": "Please execute"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Deploy approval access required"


def test_approve_approval_rejects_out_of_scope_project():
    client = _make_client()
    auth = MagicMock()
    approver_user = SimpleNamespace(
        user_id="ops1",
        username="ops",
        role="developer",
        project_ids=["proj1"],
    )
    auth.validate_token.return_value = approver_user
    _allow_permissions(auth, Permission.DEPLOY_APPROVE)
    deploy_service = MagicMock()
    deploy_service.get_approval_detail.return_value = {
        "id": "approval_demo",
        "status": "pending",
        "project_key": "proj2",
    }

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_deploy_service", return_value=deploy_service):
        response = client.post(
            "/api/deploy/approvals/approval_demo/approve",
            headers={"Authorization": "Bearer approver-token"},
            json={"comment": "Approve release"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Project scope access required"
    deploy_service.review_approval.assert_not_called()


def test_approve_approval_returns_service_payload_for_approver():
    client = _make_client()
    auth = MagicMock()
    approver_user = SimpleNamespace(user_id="ops1", username="ops")
    auth.validate_token.return_value = approver_user
    _allow_permissions(auth, Permission.DEPLOY_APPROVE)
    deploy_service = MagicMock()
    deploy_service.get_approval_detail.return_value = {
        "id": "approval_demo",
        "status": "pending",
        "project_key": "proj1",
    }
    deploy_service.review_approval.return_value = {
        "id": "approval_demo",
        "status": "approved",
        "job_id": "job_demo",
        "record_id": "rec_demo",
    }

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_deploy_service", return_value=deploy_service):
        response = client.post(
            "/api/deploy/approvals/approval_demo/approve",
            headers={"Authorization": "Bearer approver-token"},
            json={"comment": "Approve release"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["approval"]["status"] == "approved"
    deploy_service.review_approval.assert_called_once_with(
        "approval_demo",
        approved=True,
        reviewed_by="ops1",
        reviewed_by_name="ops",
        comment="Approve release",
    )
    auth.record_audit_event.assert_called_once_with(
        action="deploy_approval_approve",
        resource_type="deploy_approval",
        resource_id="approval_demo",
        details={"approval_id": "approval_demo", "project_key": "proj1", "job_id": "job_demo", "record_id": "rec_demo"},
        user_id="ops1",
    )


def test_list_deploy_audit_logs_filters_by_project_scope():
    client = _make_client()
    auth = MagicMock()
    auth.users = {
        "ops1": SimpleNamespace(username="ops"),
        "ops2": SimpleNamespace(username="qa"),
    }
    scoped_user = SimpleNamespace(
        user_id="viewer1",
        username="viewer",
        role="tester",
        project_ids=["proj1"],
    )
    auth.validate_token.return_value = scoped_user
    _allow_permissions(auth, Permission.DEPLOY_VIEW)
    auth.get_audit_logs.return_value = [
        AuditLog(
            log_id="audit_1",
            user_id="ops1",
            action="deploy_repo_full",
            resource_type="deploy_repo",
            resource_id="repo1",
            details={"project_key": "proj1", "repo_id": "repo1"},
            timestamp="2026-03-23T10:00:00",
        ),
        AuditLog(
            log_id="audit_2",
            user_id="ops2",
            action="deploy_repo_full",
            resource_type="deploy_repo",
            resource_id="repo2",
            details={"project_key": "proj2", "repo_id": "repo2"},
            timestamp="2026-03-23T10:05:00",
        ),
    ]

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.deploy.get_auth_service", return_value=auth):
        response = client.get(
            "/api/deploy/audit?limit=20",
            headers={"Authorization": "Bearer viewer-token"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["logs"] == [
        {
            "log_id": "audit_1",
            "user_id": "ops1",
            "username": "ops",
            "action": "deploy_repo_full",
            "resource_type": "deploy_repo",
            "resource_id": "repo1",
            "project_key": "proj1",
            "details": {"project_key": "proj1", "repo_id": "repo1"},
            "timestamp": "2026-03-23T10:00:00",
            "ip_address": None,
        }
    ]
    auth.get_audit_logs.assert_called_once_with(
        user_id=None,
        action=None,
        action_prefix="deploy_",
        limit=20,
    )
