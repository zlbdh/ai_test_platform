# -*- coding: utf-8 -*-
import sqlite3
from unittest.mock import patch

import pytest

from agents.commander import Commander
from services.execution_center_service import ExecutionCenterService


@pytest.mark.asyncio
async def test_commander_run_archives_group_and_bug_summary(tmp_path):
    db_path = tmp_path / "business.db"
    real_connect = sqlite3.connect

    def _connect(*args, **kwargs):
        conn = real_connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def _fake_parse(self, mission):
        return {"intent": "login"}

    async def _fake_strategy(self, mission):
        return {
            "test_types": ["api_rest", "visual_regression"],
            "priority": "high",
            "parallel": False,
            "timeout_seconds": 30,
            "retry_count": 1,
            "ai_confidence": 0.91,
            "reasoning": "需要同时覆盖接口与视觉线",
            "recommended_agents": ["api", "visual"],
        }

    async def _fake_api(self, task):
        return {
            "test_type": "api_rest",
            "status": "error",
            "error": "登录接口返回 500",
            "result": {
                "errors": ["登录接口返回 500"],
                "summary": "登录接口 500",
            },
        }

    async def _fake_visual(self, task):
        return {
            "test_type": "visual_regression",
            "status": "completed",
            "result": {
                "baselines_count": 2,
                "baselines": ["home.png", "login.png"],
                "note": "视觉基线检查完成",
            },
        }

    async def _fake_notify(self, mission):
        return None

    with patch("core.db_helper.sqlite3.connect", side_effect=_connect), \
            patch.object(Commander, "_load_missions", lambda self: None), \
            patch.object(Commander, "_register_profiles", lambda self: None), \
            patch.object(Commander, "_parse_requirement", _fake_parse), \
            patch.object(Commander, "_select_strategy", _fake_strategy), \
            patch.object(Commander, "_run_api_test", _fake_api), \
            patch.object(Commander, "_run_visual_test", _fake_visual), \
            patch.object(Commander, "_notify", _fake_notify):
        commander = Commander()
        result = await commander.run(
            user_input="测试登录模块",
            target_url="http://example.com/login",
            parallel=False,
            mission_id="mission_demo",
        )

        assert result["execution_group_id"] == "mission_demo"
        assert result["execution_center_path"] == "/history?group=mission_demo"
        assert len(result["bug_summary"]) == 1
        assert result["bug_summary"][0]["summary"] == "登录接口返回 500"

        grouped = ExecutionCenterService().list_grouped_runs(limit=10)
        group = next(item for item in grouped["items"] if item["group_id"] == "mission_demo")
        assert group["title"].startswith("Legion test · 测试登录模块")
        assert group["status"] == "failed"

        record_map = {record["task_id"]: record for record in group["records"]}
        assert "mission_demo" in record_map
        assert record_map["mission_demo"]["mode"] == "commander"
        assert record_map["mission_demo"]["status"] == "failed"
        assert "commander_mission_demo_api_rest_1" in record_map
        assert record_map["commander_mission_demo_api_rest_1"]["mode"] == "api_rest"
        assert "commander_mission_demo_visual_regression_2" in record_map
        assert record_map["commander_mission_demo_visual_regression_2"]["status"] == "success"
