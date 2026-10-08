# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.release import router as release_router


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(release_router)
    return TestClient(app)


def test_create_release_risk_assessment_route_returns_service_payload():
    client = _make_client()
    auth = MagicMock()
    user = SimpleNamespace(user_id="user1", username="demo")
    auth.validate_token.return_value = user
    svc = MagicMock()
    svc.create_assessment.return_value = {
        "assessment_id": "release_demo",
        "release_risk": "high",
        "auto_release_eligible": False,
        "evidence": {
            "review_summary": {
                "pending": 1,
                "confirmed": 0,
                "dismissed": 0,
                "active": 1,
                "effective": 1,
            },
        },
        "policy_hit": {
            "review_blocked": True,
            "review_policy_mode": "conservative",
        },
    }

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.release.get_release_risk_service", return_value=svc):
        response = client.post(
            "/api/release/risk-assessments",
            headers={"Authorization": "Bearer demo-token"},
            json={
                "project_key": "demo",
                "environment": "production",
                "exploration_session_ids": ["explore_demo"],
                "required_tests_passed": True,
                "change_summary": "Payment flow update",
            },
        )

    assert response.status_code == 200
    assert response.json()["assessment"]["assessment_id"] == "release_demo"
    assert response.json()["assessment"]["evidence"]["review_summary"]["pending"] == 1
    assert response.json()["assessment"]["policy_hit"]["review_blocked"] is True
    svc.create_assessment.assert_called_once()


def test_list_release_risk_assessments_route_passes_filters():
    client = _make_client()
    auth = MagicMock()
    user = SimpleNamespace(user_id="user1", username="demo")
    auth.validate_token.return_value = user
    svc = MagicMock()
    svc.list_assessments.return_value = {
        "assessments": [{"assessment_id": "release_demo", "project_key": "demo"}],
        "count": 1,
    }

    with patch("core.auth_dependencies.get_auth_service", return_value=auth), \
         patch("routers.release.get_release_risk_service", return_value=svc):
        response = client.get(
            "/api/release/risk-assessments?project_key=demo&environment=staging&auto_release_eligible=true&limit=5",
            headers={"Authorization": "Bearer demo-token"},
        )

    assert response.status_code == 200
    assert response.json()["count"] == 1
    svc.list_assessments.assert_called_once_with(
        user=user,
        project_key="demo",
        environment="staging",
        auto_release_eligible=True,
        limit=5,
    )
