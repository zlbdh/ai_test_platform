from types import SimpleNamespace
from unittest.mock import patch

import pytest

from routers.scheduler import ScheduledTask, _execute_task


class TestScheduledTask:
    def test_config_uses_independent_default_dict(self):
        first = ScheduledTask(name="first")
        second = ScheduledTask(name="second")

        first.config["url"] = "https://example.com"

        assert second.config == {}


class TestExecuteTask:
    @pytest.mark.asyncio
    async def test_exploratory_task_calls_core_start_endpoint(self):
        calls = []

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, json):
                calls.append((url, json))
                return SimpleNamespace(status_code=202)

        task_data = {
            "task_type": "exploratory",
            "name": "nightly exploratory",
            "cron": "0 8 * * *",
            "notify_on_complete": False,
            "config": {
                "url": "https://example.com/app",
                "planner_mode": "quick",
            },
        }

        with patch("httpx.AsyncClient", FakeAsyncClient), patch("routers.scheduler.execute") as mock_execute:
            await _execute_task("sched_1234", task_data)

        assert calls == [
            (
                "http://localhost:8020/api/start",
                {
                    "requirement": "探索性测试 https://example.com/app",
                    "target_url": "https://example.com/app",
                    "planner_mode": "quick",
                    "session_id": "scheduled_sched_1234",
                },
            )
        ]
        assert mock_execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_exploratory_task_skips_call_without_url(self):
        calls = []

        class FakeAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, json):
                calls.append((url, json))
                return SimpleNamespace(status_code=202)

        task_data = {
            "task_type": "exploratory",
            "name": "nightly exploratory",
            "cron": "0 8 * * *",
            "notify_on_complete": False,
            "config": {},
        }

        with patch("httpx.AsyncClient", FakeAsyncClient), patch("routers.scheduler.execute") as mock_execute:
            await _execute_task("sched_1234", task_data)

        assert calls == []
        assert mock_execute.call_count >= 1
