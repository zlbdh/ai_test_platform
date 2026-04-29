# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.commander import router as commander_router


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(commander_router)
    return TestClient(app)


def test_create_unified_task_route_delegates_to_service():
    client = _make_client()
    fake_commander = SimpleNamespace()
    service = MagicMock()
    service.create_task.return_value = {
        "task_id": "task001",
        "task_kind": "general",
        "status": "pending",
    }

    with patch("agents.commander.get_commander", return_value=fake_commander), \
         patch("routers.commander.get_unified_task_service", return_value=service):
        response = client.post(
            "/api/commander/tasks",
            json={
                "task_kind": "general",
                "user_goal": "检查登录链路",
                "source_context": {"target_url": "https://demo.example.com"},
                "strategy": {"parallel": True},
            },
        )

    assert response.status_code == 200
    assert response.json()["task_id"] == "task001"
    service.create_task.assert_called_once_with(
        commander=fake_commander,
        task_kind="general",
        user_goal="检查登录链路",
        source_context={"target_url": "https://demo.example.com"},
        strategy={"parallel": True},
    )


def test_list_unified_tasks_route_returns_service_payload():
    client = _make_client()
    fake_commander = SimpleNamespace()
    service = MagicMock()
    service.list_tasks.return_value = [
        {"task_id": "task002", "task_kind": "prototype", "status": "completed"},
    ]

    with patch("agents.commander.get_commander", return_value=fake_commander), \
         patch("routers.commander.get_unified_task_service", return_value=service):
        response = client.get("/api/commander/tasks?limit=5")

    assert response.status_code == 200
    assert response.json()[0]["task_id"] == "task002"
    service.list_tasks.assert_called_once_with(
        commander=fake_commander,
        limit=5,
        task_kind="",
        status="",
        lineage_root_id="",
    )


def test_get_unified_task_route_returns_404_when_missing():
    client = _make_client()
    fake_commander = SimpleNamespace()
    service = MagicMock()
    service.get_task.return_value = None

    with patch("agents.commander.get_commander", return_value=fake_commander), \
         patch("routers.commander.get_unified_task_service", return_value=service):
        response = client.get("/api/commander/tasks/not-found")

    assert response.status_code == 404
    assert response.json()["detail"] == "Unified task not found"


def test_list_unified_tasks_route_passes_filters():
    client = _make_client()
    fake_commander = SimpleNamespace()
    service = MagicMock()
    service.list_tasks.return_value = []

    with patch("agents.commander.get_commander", return_value=fake_commander), \
         patch("routers.commander.get_unified_task_service", return_value=service):
        response = client.get("/api/commander/tasks?limit=8&task_kind=prototype&status=pending&lineage_root_id=chain_1")

    assert response.status_code == 200
    service.list_tasks.assert_called_once_with(
        commander=fake_commander,
        limit=8,
        task_kind="prototype",
        status="pending",
        lineage_root_id="chain_1",
    )


def test_cancel_unified_task_route_returns_action_payload():
    client = _make_client()
    fake_commander = SimpleNamespace()
    service = MagicMock()
    service.cancel_task.return_value = {
        "task_id": "task001",
        "cancelled": True,
        "status": "cancelled",
        "message": "任务已停止。",
    }

    with patch("agents.commander.get_commander", return_value=fake_commander), \
         patch("routers.commander.get_unified_task_service", return_value=service):
        response = client.post("/api/commander/tasks/task001/cancel")

    assert response.status_code == 200
    assert response.json()["cancelled"] is True
    service.cancel_task.assert_called_once_with(commander=fake_commander, task_id="task001")


def test_rerun_unified_task_route_returns_new_task():
    client = _make_client()
    fake_commander = SimpleNamespace()
    service = MagicMock()
    service.rerun_task.return_value = {
        "task_id": "task002",
        "task_kind": "general",
        "status": "pending",
    }

    with patch("agents.commander.get_commander", return_value=fake_commander), \
         patch("routers.commander.get_unified_task_service", return_value=service):
        response = client.post("/api/commander/tasks/task001/rerun")

    assert response.status_code == 200
    assert response.json()["task_id"] == "task002"
    service.rerun_task.assert_called_once_with(commander=fake_commander, task_id="task001")
