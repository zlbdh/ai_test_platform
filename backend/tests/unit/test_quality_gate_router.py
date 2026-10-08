# -*- coding: utf-8 -*-
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.quality_gate import router as quality_gate_router


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(quality_gate_router)
    return TestClient(app)


def test_gate_history_route_passes_run_id_and_status_filters():
    client = _make_client()
    fake_gate = MagicMock()
    fake_gate.get_history.return_value = [
        {"run_id": "task001", "status": "warning", "verdict": {"summary": "Context gate"}, "timestamp": 1712040000},
    ]

    with patch("cicd.quality_gate.get_quality_gate", return_value=fake_gate):
        response = client.get("/api/quality-gate/history?limit=10&run_id=task001&status=warning")

    assert response.status_code == 200
    assert response.json()["data"]["count"] == 1
    fake_gate.get_history.assert_called_once_with(limit=10, run_id="task001", status="warning")
