# -*- coding: utf-8 -*-
from importlib import reload

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.models import TestRequest
import routers.core as core_router_module


class _FakeSession:
    def get_status(self):
        return "RUNNING", "??????? Wave0 ???????"

    def get_signal(self):
        return "RUNNING"

    def get_pause_reason(self):
        return None

    def get_page(self):
        return object()

    def get_intervention_screenshot(self):
        return None


class _FakeOrchestrator:
    def __init__(self, is_running: bool = True):
        self.session = _FakeSession()
        self.active_task_id = "task_status_demo"
        self.is_running = is_running
        self._task_requirement_display = "https://example.com/login"
        self._task_text_state = "broken_fallback"
        self._execution_mode = "probe"
        self._interaction_policy = "read_only"
        self._step_budget = 8
        self.start_calls = []

    def start_task(self, *args, **kwargs):
        self.start_calls.append({"args": args, "kwargs": kwargs})
        return "task_probe_start"


def _make_client(is_running: bool = True) -> tuple[TestClient, _FakeOrchestrator]:
    module = reload(core_router_module)
    app = FastAPI()
    orch = _FakeOrchestrator(is_running=is_running)
    router = module.setup_core_routes(lambda _sid="": orch, object, TestRequest)
    app.include_router(router)
    return TestClient(app), orch


def test_api_status_returns_task_display_and_text_state():
    client, _ = _make_client()

    response = client.get("/api/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "RUNNING"
    assert payload["task"] == "??????? Wave0 ???????"
    assert payload["task_display"] == "https://example.com/login"
    assert payload["task_text_state"] == "broken_fallback"
    assert payload["execution_mode"] == "probe"
    assert payload["interaction_policy"] == "read_only"
    assert payload["step_budget"] == 8
    assert payload["active_task_id"] == "task_status_demo"
    assert payload["is_running"] is True
    assert payload["has_browser"] is True


def test_api_start_passes_probe_execution_fields():
    client, orch = _make_client(is_running=False)

    response = client.post(
        "/api/start",
        json={
            "requirement": "打开登录页，不要登录，不要输入",
            "target_url": "https://example.com/login",
            "planner_mode": "smart",
            "execution_mode": "probe",
            "interaction_policy": "read_only",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "started"
    assert payload["task_id"] == "task_probe_start"
    assert payload["execution_mode"] == "probe"
    assert payload["interaction_policy"] == "read_only"
    assert orch.start_calls[0]["kwargs"]["execution_mode"] == "probe"
    assert orch.start_calls[0]["kwargs"]["interaction_policy"] == "read_only"
