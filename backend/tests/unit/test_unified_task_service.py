# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.unified_task_service import UnifiedTaskService


class _DummyCommander:
    def __init__(self) -> None:
        self._missions = {}
        self.saved = 0

    def get_mission(self, mission_id: str):
        return self._missions.get(mission_id)

    def _save_missions(self):
        self.saved += 1


def _close_background_task():
    created = {}

    def _fake_create_task(coro):
        created["scheduled"] = True
        coro.close()
        return SimpleNamespace(done=lambda: True)

    return created, _fake_create_task


def test_list_tasks_filters_unified_only_and_sorts_desc():
    service = UnifiedTaskService()
    commander = _DummyCommander()
    commander._missions = {
        "old": {
            "mission_id": "old",
            "task_kind": "general",
            "unified_task": True,
            "created_at": "2026-04-02T10:00:00",
            "status": "completed",
            "user_input": "较早任务",
            "logs": [],
            "report": {},
        },
        "skip": {
            "mission_id": "skip",
            "task_kind": "general",
            "unified_task": False,
            "created_at": "2026-04-02T11:00:00",
            "status": "completed",
            "user_input": "普通任务",
            "logs": [],
            "report": {},
        },
        "new": {
            "mission_id": "new",
            "task_kind": "prototype",
            "unified_task": True,
            "created_at": "2026-04-02T12:00:00",
            "status": "completed",
            "user_input": "较新任务",
            "logs": [],
            "report": {},
        },
    }

    result = service.list_tasks(commander=commander, limit=10)

    assert [item["task_id"] for item in result] == ["new", "old"]
    assert all(item["task_id"] != "skip" for item in result)


def test_list_tasks_supports_kind_and_status_filters():
    service = UnifiedTaskService()
    commander = _DummyCommander()
    commander._missions = {
        "general_1": {
            "mission_id": "general_1",
            "task_kind": "general",
            "unified_task": True,
            "created_at": "2026-04-02T10:00:00",
            "status": "completed",
            "user_input": "通用任务",
            "logs": [],
            "report": {},
        },
        "prototype_1": {
            "mission_id": "prototype_1",
            "task_kind": "prototype",
            "unified_task": True,
            "created_at": "2026-04-02T12:00:00",
            "status": "pending",
            "user_input": "原型任务",
            "logs": [],
            "report": {},
        },
    }

    result = service.list_tasks(commander=commander, limit=10, task_kind="prototype", status="pending")

    assert [item["task_id"] for item in result] == ["prototype_1"]


def test_list_tasks_supports_lineage_filter():
    service = UnifiedTaskService()
    commander = _DummyCommander()
    commander._missions = {
        "task_root": {
            "mission_id": "task_root",
            "task_kind": "prototype",
            "unified_task": True,
            "created_at": "2026-04-02T10:00:00",
            "status": "completed",
            "user_input": "首轮任务",
            "logs": [],
            "report": {},
            "lineage_root_id": "chain_1",
        },
        "task_rerun": {
            "mission_id": "task_rerun",
            "task_kind": "prototype",
            "unified_task": True,
            "created_at": "2026-04-02T11:00:00",
            "status": "completed",
            "user_input": "复跑任务",
            "logs": [],
            "report": {},
            "lineage_root_id": "chain_1",
            "rerun_from_task_id": "task_root",
        },
        "task_other": {
            "mission_id": "task_other",
            "task_kind": "prototype",
            "unified_task": True,
            "created_at": "2026-04-02T12:00:00",
            "status": "completed",
            "user_input": "其他链路任务",
            "logs": [],
            "report": {},
            "lineage_root_id": "chain_2",
        },
    }

    result = service.list_tasks(commander=commander, limit=10, lineage_root_id="chain_1")

    assert [item["task_id"] for item in result] == ["task_rerun", "task_root"]


@pytest.mark.asyncio
async def test_create_general_task_builds_unified_pending_mission():
    service = UnifiedTaskService()
    commander = _DummyCommander()
    created, fake_create_task = _close_background_task()

    with patch("services.unified_task_service.asyncio.create_task", side_effect=fake_create_task):
        task = service.create_task(
            commander=commander,
            task_kind="general",
            user_goal="检查登录主链路",
            source_context={"target_url": "https://demo.example.com/login"},
            strategy={"parallel": False},
        )

    assert created["scheduled"] is True
    assert task["task_kind"] == "general"
    assert task["mission_kind"] == "commander"
    assert task["status"] == "pending"
    assert task["expert_path"] == "/orchestrator"
    assert task["quality_gate_path"].startswith("/quality-gate?task_id=")
    assert task["execution_center_path"].startswith("/history?group=")
    assert "task_id=" in task["execution_center_path"]
    assert "lineage_root_id=" in task["execution_center_path"]
    assert task["source_context"]["target_url"] == "https://demo.example.com/login"
    assert task["agent_states"]["commander"] == "idle"
    assert commander.saved >= 1


@pytest.mark.asyncio
async def test_create_prototype_task_keeps_context_and_expert_path():
    service = UnifiedTaskService()
    commander = _DummyCommander()
    created, fake_create_task = _close_background_task()

    class _DummyPrototypeService:
        def create_mission(self, payload, mission_id):
            return {
                "mission_id": mission_id,
                "mission_kind": "prototype_agents",
                "status": "pending",
                "created_at": "2026-04-02T12:00:00",
                "logs": [],
                "strategy": {"worker_switches": payload["worker_switches"]},
                "agent_states": {"orchestrator": "idle"},
                "report": {},
            }

    with patch("services.unified_task_service.get_prototype_agents_service", return_value=_DummyPrototypeService()), \
         patch("services.unified_task_service.asyncio.create_task", side_effect=fake_create_task):
        task = service.create_task(
            commander=commander,
            task_kind="prototype",
            user_goal="对目录执行原型测试",
            source_context={
                "source_type": "directory",
                "source": "D:\\prototype",
                "playbook_id": "sample-platform-prototype",
            },
            strategy={"wcag_level": "AA"},
        )

    assert created["scheduled"] is True
    assert task["task_kind"] == "prototype"
    assert task["mission_kind"] == "prototype_agents"
    assert task["expert_path"] == "/prototype-agents"
    assert task["source_context"]["source"] == "D:\\prototype"
    assert task["gate_summary"]["status"] == "passed"
    assert task["lineage_root_id"] == task["task_id"]
    assert task["rerun_from_task_id"] == ""
    assert task["verification_state"]["status"] == "verified_passed"
    assert f"task_id={task['task_id']}" in task["execution_center_path"]


def test_get_task_result_builds_general_fallback_findings_and_failed_gate():
    service = UnifiedTaskService()
    commander = _DummyCommander()
    commander._missions["general_1"] = {
        "mission_id": "general_1",
        "mission_kind": "commander",
        "task_kind": "general",
        "unified_task": True,
        "user_input": "通用任务",
        "status": "completed",
        "created_at": "2026-04-02T12:00:00",
        "logs": [{"timestamp": "2026-04-02T12:00:01", "level": "error", "message": "失败"}],
        "report": {
            "summary": {
                "total_tests": 3,
                "failed": 1,
                "completed": 2,
            }
        },
        "bug_summary": [
            {
                "test_type": "api_rest",
                "title": "登录接口异常",
                "summary": "接口返回 500",
            }
        ],
        "execution_group_id": "general_1",
    }

    result = service.get_task_result(commander=commander, task_id="general_1")

    assert result is not None
    assert result["gate_summary"]["status"] == "failed"
    assert result["findings"][0]["title"] == "登录接口异常"
    assert result["quality_gate_path"] == "/quality-gate?task_id=general_1&run_id=general_1&task_kind=general&status=completed&focus=history"
    assert result["recommendations"]
    assert result["evidence_summary"]["finding_count"] == 1
    assert result["verification_state"]["status"] == "issues_found"
    assert result["execution_center_path"] == "/history?group=general_1&record=general_1&task_id=general_1&lineage_root_id=general_1"


def test_get_task_marks_exploration_as_warning_when_static_unprovable():
    service = UnifiedTaskService()
    commander = _DummyCommander()
    commander._missions["explore_1"] = {
        "mission_id": "explore_1",
        "mission_kind": "exploration_frontdoor",
        "task_kind": "exploration",
        "unified_task": True,
        "user_input": "探索订单链路",
        "status": "completed",
        "created_at": "2026-04-02T12:00:00",
        "logs": [],
        "report": {
            "summary": {"task_kind": "exploration"},
            "findings": [],
            "quality_gate_metrics": {
                "error_count": 0,
                "static_unprovable_count": 1,
            },
        },
    }

    result = service.get_task(commander=commander, task_id="explore_1")

    assert result is not None
    assert result["gate_summary"]["status"] == "warning"
    assert "无法证明" in result["gate_summary"]["summary"]
    assert result["expert_path"] == "/exploratory"
    assert result["verification_state"]["status"] == "context_unprovable"


def test_cancel_task_marks_general_task_cancelled():
    service = UnifiedTaskService()
    commander = _DummyCommander()
    commander._missions["general_1"] = {
        "mission_id": "general_1",
        "mission_kind": "commander",
        "task_kind": "general",
        "unified_task": True,
        "status": "executing",
        "agent_states": {"commander": "running"},
        "logs": [],
    }

    def _cancel(_mission_id: str) -> bool:
        return True

    commander.cancel_mission = _cancel

    result = service.cancel_task(commander=commander, task_id="general_1")

    assert result["cancelled"] is True
    assert result["status"] == "cancelled"
    assert commander._missions["general_1"]["agent_states"]["commander"] == "cancelled"


def test_rerun_task_clones_original_context():
    service = UnifiedTaskService()
    commander = _DummyCommander()
    commander._missions["prototype_1"] = {
        "mission_id": "prototype_1",
        "mission_kind": "prototype_agents",
        "task_kind": "prototype",
        "unified_task": True,
        "user_input": "原型复跑",
        "source_context": {"source_type": "directory", "source": "D:\\demo"},
        "strategy": {"wcag_level": "AA"},
        "status": "completed",
        "logs": [],
        "lineage_root_id": "prototype_root",
    }

    with patch.object(service, "create_task", return_value={"task_id": "prototype_2", "task_kind": "prototype"}) as create_task:
        result = service.rerun_task(commander=commander, task_id="prototype_1")

    assert result["task_id"] == "prototype_2"
    create_task.assert_called_once_with(
        commander=commander,
        task_kind="prototype",
        user_goal="原型复跑",
        source_context={"source_type": "directory", "source": "D:\\demo"},
        strategy={"wcag_level": "AA"},
        lineage_root_id="prototype_root",
        rerun_from_task_id="prototype_1",
    )
