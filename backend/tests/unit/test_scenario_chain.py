# -*- coding: utf-8 -*-
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.scenario_chain import ScenarioChainEngine


class FakeOrchestrator:
    def __init__(self, task_id: str, is_running: bool = False):
        self.task_id = task_id
        self.is_running = is_running
        self.stop_called = False

    def start_task(self, **kwargs):
        return self.task_id

    def stop_task(self):
        self.stop_called = True
        self.is_running = False


def test_upsert_scenario_by_name_updates_existing(tmp_path, monkeypatch):
    monkeypatch.setattr("core.scenario_chain.SCENARIOS_DIR", tmp_path)
    engine = ScenarioChainEngine()
    created = engine.create_scenario(
        "示例项目登录回归",
        description="旧描述",
        steps=[{"name": "旧步骤", "instruction": "old"}],
        tags=["old"],
    )

    updated = engine.upsert_scenario_by_name(
        "示例项目登录回归",
        description="新描述",
        steps=[{"name": "新步骤", "instruction": "new"}],
        tags=["wave0", "登录"],
    )

    assert updated["id"] == created["id"]
    assert updated["description"] == "新描述"
    assert updated["steps"][0]["name"] == "新步骤"
    assert updated["tags"] == ["wave0", "登录"]


@pytest.mark.asyncio
async def test_execute_scenario_persists_step_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr("core.scenario_chain.SCENARIOS_DIR", tmp_path)
    engine = ScenarioChainEngine()
    scenario = engine.create_scenario(
        "登录场景",
        steps=[
            {
                "id": "step_login",
                "name": "登录",
                "url": "https://example.com/login",
                "instruction": "输入账号并登录",
                "timeout": 1,
            }
        ],
    )

    fake_orch = FakeOrchestrator("task_login")

    with patch.object(engine, "_get_orchestrator", return_value=fake_orch), \
         patch.object(engine, "_query_task_status", return_value="completed"), \
         patch("core.scenario_chain.asyncio.sleep", new=AsyncMock()):
        result = await engine.execute_scenario(scenario["id"])

    saved = engine.get_scenario(scenario["id"])

    assert result["status"] == "completed"
    assert result["passed"] == 1
    assert saved["steps"][0]["status"] == "passed"
    assert saved["steps"][0]["result"]["task_id"] == "task_login"
    assert saved["steps"][0]["result"]["status"] == "success"
    assert saved["steps"][0]["result"]["shared_state"]["step_login"]["status"] == "success"


@pytest.mark.asyncio
async def test_execute_scenario_resets_old_runtime_and_skips_failed_dependency(tmp_path, monkeypatch):
    monkeypatch.setattr("core.scenario_chain.SCENARIOS_DIR", tmp_path)
    engine = ScenarioChainEngine()
    scenario = engine.create_scenario(
        "支付场景",
        steps=[
            {
                "id": "step_login",
                "name": "登录",
                "url": "https://example.com/login",
                "instruction": "登录失败",
                "timeout": 1,
                "on_failure": "continue",
                "status": "passed",
                "result": {"task_id": "stale"},
                "duration_ms": 999,
            },
            {
                "id": "step_pay",
                "name": "支付",
                "url": "https://example.com/pay",
                "instruction": "提交支付",
                "timeout": 1,
                "depends_on": "step_login",
                "status": "passed",
                "result": {"task_id": "old"},
            },
        ],
    )

    fake_orch = FakeOrchestrator("task_fail")
    get_orch = MagicMock(return_value=fake_orch)

    with patch.object(engine, "_get_orchestrator", get_orch), \
         patch.object(engine, "_query_task_status", return_value="failed"), \
         patch("core.scenario_chain.asyncio.sleep", new=AsyncMock()):
        result = await engine.execute_scenario(scenario["id"])

    saved = engine.get_scenario(scenario["id"])

    assert result["status"] == "failed"
    assert result["failed"] == 1
    assert result["skipped"] == 1
    assert get_orch.call_count == 1
    assert saved["steps"][0]["status"] == "failed"
    assert saved["steps"][0]["duration_ms"] >= 0
    assert saved["steps"][0]["result"]["status"] == "failed"
    assert saved["steps"][1]["status"] == "skipped"
    assert saved["steps"][1]["result"]["reason"] == "Prerequisite step step_login failed"
