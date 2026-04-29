# -*- coding: utf-8 -*-
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.auth import router as auth_router
from services.auth_service import Permission, UserRole


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router)
    return TestClient(app)


def test_auth_me_accepts_bearer_token_and_returns_permissions():
    client = _make_client()
    auth = MagicMock()
    auth.validate_token.return_value = SimpleNamespace(
        user_id="user_1",
        username="alice",
        email="alice@test.com",
        role=UserRole.DEVELOPER,
        project_ids=["proj1"],
    )

    with patch("core.auth_dependencies.get_auth_service", return_value=auth):
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer demo-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["username"] == "alice"
    assert payload["user"]["permissions"] == [
        Permission.CREATE_TEST.value,
        Permission.RUN_TEST.value,
        Permission.VIEW_RESULTS.value,
        Permission.API_ACCESS.value,
        Permission.DEPLOY_VIEW.value,
        Permission.DEPLOY_REQUEST.value,
    ]
    auth.validate_token.assert_called_once_with("demo-token")


def test_auth_logout_accepts_token_from_body():
    client = _make_client()
    auth = MagicMock()

    with patch("routers.auth.get_auth_service", return_value=auth):
        response = client.post("/api/auth/logout", json={"token": "body-token"})

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    auth.logout.assert_called_once_with("body-token")


def test_auth_me_supports_dev_bypass_without_token():
    client = _make_client()
    auth = MagicMock()
    auth.get_dev_bypass_user.return_value = SimpleNamespace(
        user_id="user_admin",
        username="admin",
        email="admin@test.com",
        role=UserRole.ADMIN,
        project_ids=[],
    )

    with patch.dict(os.environ, {"DEV_AUTH_BYPASS": "true"}, clear=False), \
         patch("core.auth_dependencies.get_auth_service", return_value=auth):
        response = client.get("/api/auth/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["username"] == "admin"
    assert Permission.ADMIN.value in payload["user"]["permissions"]
    auth.get_dev_bypass_user.assert_called_once_with()
