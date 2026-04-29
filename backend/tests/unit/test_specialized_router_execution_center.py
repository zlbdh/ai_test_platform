# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from routers.grpc import GrpcCallRequest, grpc_call
from routers.websocket_test import WSSendRequest, ws_quick_test
from routers.mobile import MobileTestRequest, mobile_test
from routers.chaos import ChaosRunRequest, chaos_run


@pytest.mark.asyncio
async def test_grpc_call_records_execution_center_entry():
    recorder = MagicMock()
    grpc_service = MagicMock()
    grpc_service.call = AsyncMock(return_value=SimpleNamespace(
        success=True,
        data={"ok": True},
        error=None,
        status_code=0,
        response_time_ms=128,
    ))

    with patch("services.grpc_testing.create_grpc_service", return_value=grpc_service), \
         patch("routers.grpc.get_execution_center_service", return_value=recorder):
        result = await grpc_call(
            GrpcCallRequest(
                host="127.0.0.1",
                port=50051,
                service="demo.UserService",
                method="GetUser",
                data={"id": 1},
                session_id="sess_demo",
                execution_group_id="batch_demo",
                group_title="API 专项批次",
            )
        )

    assert result["status"] == "success"
    recorder.record_specialized_result.assert_called_once()
    kwargs = recorder.record_specialized_result.call_args.kwargs
    assert kwargs["mode"] == "grpc"
    assert kwargs["execution_group_id"] == "batch_demo"
    assert kwargs["session_id"] == "sess_demo"


@pytest.mark.asyncio
async def test_ws_quick_test_records_execution_center_entry():
    recorder = MagicMock()
    ws_service = MagicMock()
    ws_service.run_scenario = AsyncMock(return_value=SimpleNamespace(
        connected=True,
        messages=[SimpleNamespace(direction="receive", content={"ok": True}, timestamp=123456.0, message_type="text")],
        total_time_ms=88,
        error=None,
    ))

    with patch("services.websocket_testing.create_ws_test_service", return_value=ws_service), \
         patch("routers.websocket_test.get_execution_center_service", return_value=recorder):
        result = await ws_quick_test(
            WSSendRequest(
                url="ws://127.0.0.1:9001/ws",
                message={"hello": "world"},
                session_id="sess_demo",
                execution_group_id="batch_demo",
                group_title="API 专项批次",
            )
        )

    assert result["status"] == "success"
    recorder.record_specialized_result.assert_called_once()
    kwargs = recorder.record_specialized_result.call_args.kwargs
    assert kwargs["mode"] == "websocket"
    assert kwargs["execution_group_id"] == "batch_demo"


@pytest.mark.asyncio
async def test_mobile_test_records_execution_center_entry():
    recorder = MagicMock()
    mobile_service = MagicMock()
    mobile_service.test_devices = AsyncMock(return_value=SimpleNamespace(
        to_dict=lambda: {
            "url": "http://127.0.0.1:8010/",
            "devices_tested": 1,
            "total_issues": 0,
            "score": 100,
            "summary": "设备 1 台 · 问题 0 个",
            "results": [
                {
                    "device": "iPhone 14",
                    "issues": [],
                    "metrics": {},
                }
            ],
        }
    ))

    with patch("services.mobile_emulation.create_mobile_service", return_value=mobile_service), \
         patch("routers.mobile.get_execution_center_service", return_value=recorder):
        result = await mobile_test(
            MobileTestRequest(
                url="http://127.0.0.1:8010/",
                devices=["iphone_14"],
                session_id="sess_demo",
                execution_group_id="batch_demo",
                group_title="韧性测试批次",
            )
        )

    assert result["total_issues"] == 0
    recorder.record_specialized_result.assert_called_once()
    kwargs = recorder.record_specialized_result.call_args.kwargs
    assert kwargs["mode"] == "mobile"
    assert kwargs["execution_group_id"] == "batch_demo"


@pytest.mark.asyncio
async def test_chaos_run_records_execution_center_entry():
    recorder = MagicMock()
    chaos_service = MagicMock()
    chaos_service.run_scenarios = AsyncMock(return_value=SimpleNamespace(
        to_dict=lambda: {
            "url": "http://127.0.0.1:8010/",
            "scenarios_run": 2,
            "passed": 2,
            "failed": 0,
            "errors": 0,
            "summary": "执行 2 个场景: 通过 2, 失败 0, 错误 0",
            "results": [
                {"scenario": "慢速网络 (3G)", "status": "passed", "details": "通过", "duration_ms": 320},
                {"scenario": "断网恢复", "status": "passed", "details": "通过", "duration_ms": 210},
            ],
            "total_duration_ms": 530,
        }
    ))

    with patch("services.chaos_engineering.create_chaos_service", return_value=chaos_service), \
         patch("routers.chaos.get_execution_center_service", return_value=recorder):
        result = await chaos_run(
            ChaosRunRequest(
                url="http://127.0.0.1:8010/",
                scenarios=["slow_network", "offline_recovery"],
                session_id="sess_demo",
                execution_group_id="batch_demo",
                group_title="韧性测试批次",
            )
        )

    assert result["passed"] == 2
    recorder.record_specialized_result.assert_called_once()
    kwargs = recorder.record_specialized_result.call_args.kwargs
    assert kwargs["mode"] == "chaos"
    assert kwargs["duration_ms"] == 530
