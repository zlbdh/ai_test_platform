# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.exploration import router as exploration_router


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(exploration_router)
    return TestClient(app)


def test_create_exploration_session_route_returns_service_payload():
    client = _make_client()
    auth = MagicMock()
    user = SimpleNamespace(user_id="user1", username="demo")
    auth.validate_token.return_value = user
    svc = MagicMock()
    svc.create_session.return_value = {
        "session_id": "explore_demo",
        "status": "completed",
        "summary": {"finding_count": 1},
    }

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.exploration.get_exploration_service", return_value=svc):
        response = client.post(
            "/api/exploration/sessions",
            headers={"Authorization": "Bearer demo-token"},
            json={
                "group_id": "grp1",
                "project_key": "demo",
                "target_url": "https://demo.example.com",
                "charter": "Check the login flow",
            },
        )

    assert response.status_code == 200
    assert response.json()["session"]["session_id"] == "explore_demo"
    svc.create_session.assert_called_once()


def test_list_exploration_sessions_route_passes_filters():
    client = _make_client()
    auth = MagicMock()
    user = SimpleNamespace(user_id="user1", username="demo")
    auth.validate_token.return_value = user
    svc = MagicMock()
    svc.list_sessions.return_value = {
        "sessions": [{"session_id": "explore_demo", "project_key": "demo"}],
        "count": 1,
    }

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.exploration.get_exploration_service", return_value=svc):
        response = client.get(
            "/api/exploration/sessions?project_key=demo&status=completed&limit=5",
            headers={"Authorization": "Bearer demo-token"},
        )

    assert response.status_code == 200
    assert response.json()["count"] == 1
    svc.list_sessions.assert_called_once_with(
        user=user,
        project_key="demo",
        status="completed",
        limit=5,
    )


def test_list_exploration_findings_route_passes_review_filters():
    client = _make_client()
    auth = MagicMock()
    user = SimpleNamespace(user_id="user1", username="demo")
    auth.validate_token.return_value = user
    svc = MagicMock()
    svc.list_findings.return_value = {
        "session_id": "explore_demo",
        "findings": [{"finding_id": "finding_demo", "review_status": "pending"}],
        "count": 1,
    }

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.exploration.get_exploration_service", return_value=svc):
        response = client.get(
            "/api/exploration/sessions/explore_demo/findings?severity=high&review_only=true&review_status=pending",
            headers={"Authorization": "Bearer demo-token"},
        )

    assert response.status_code == 200
    assert response.json()["count"] == 1
    svc.list_findings.assert_called_once_with(
        user=user,
        session_id="explore_demo",
        severity="high",
        review_only=True,
        review_status="pending",
    )


def test_get_exploration_finding_route_returns_finding():
    client = _make_client()
    auth = MagicMock()
    user = SimpleNamespace(user_id="user1", username="demo")
    auth.validate_token.return_value = user
    svc = MagicMock()
    svc.get_finding.return_value = {
        "finding_id": "finding_demo",
        "review_status": "pending",
    }

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.exploration.get_exploration_service", return_value=svc):
        response = client.get(
            "/api/exploration/findings/finding_demo",
            headers={"Authorization": "Bearer demo-token"},
        )

    assert response.status_code == 200
    assert response.json()["finding"]["finding_id"] == "finding_demo"
    svc.get_finding.assert_called_once_with(user=user, finding_id="finding_demo")


def test_list_exploration_review_queue_route_passes_filters():
    client = _make_client()
    auth = MagicMock()
    user = SimpleNamespace(user_id="user1", username="demo")
    auth.validate_token.return_value = user
    svc = MagicMock()
    svc.list_review_queue.return_value = {
        "review_status": "pending",
        "findings": [{"finding_id": "finding_demo"}],
        "count": 1,
    }

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.exploration.get_exploration_service", return_value=svc):
        response = client.get(
            "/api/exploration/review-queue?project_key=demo&severity=high&review_status=pending&limit=8",
            headers={"Authorization": "Bearer demo-token"},
        )

    assert response.status_code == 200
    assert response.json()["review_status"] == "pending"
    svc.list_review_queue.assert_called_once_with(
        user=user,
        project_key="demo",
        severity="high",
        review_status="pending",
        limit=8,
    )


def test_review_finding_route_returns_updated_finding():
    client = _make_client()
    auth = MagicMock()
    user = SimpleNamespace(user_id="user1", username="demo")
    auth.validate_token.return_value = user
    svc = MagicMock()
    svc.review_finding.return_value = {
        "finding_id": "finding_demo",
        "review_status": "confirmed",
        "review_comment": "Manual review",
    }

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.exploration.get_exploration_service", return_value=svc):
        response = client.post(
            "/api/exploration/findings/finding_demo/review",
            headers={"Authorization": "Bearer demo-token"},
            json={"decision": "confirmed", "comment": "Manual review"},
        )

    assert response.status_code == 200
    assert response.json()["finding"]["review_status"] == "confirmed"
    svc.review_finding.assert_called_once_with(
        user=user,
        finding_id="finding_demo",
        decision="confirmed",
        comment="Manual review",
    )
