# -*- coding: utf-8 -*-
"""
WebSocket 测试路由 — 串联 services/websocket_testing.py
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from services.execution_center_service import get_execution_center_service

router = APIRouter(prefix="/api/ws-test", tags=["websocket"])


# === Request Models ===

class WSConnectRequest(BaseModel):
    url: str
    headers: Optional[Dict[str, str]] = None
    subprotocols: Optional[List[str]] = None
    timeout: float = 10.0


class WSSendRequest(BaseModel):
    url: str
    headers: Optional[Dict[str, str]] = None
    message: Any
    is_json: bool = True
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


class WSReceiveRequest(BaseModel):
    url: str
    headers: Optional[Dict[str, str]] = None
    count: int = 1
    timeout: float = 10.0


class WSScenarioStep(BaseModel):
    action: str  # "send" | "receive" | "wait"
    data: Optional[Any] = None
    timeout: Optional[float] = None
    count: Optional[int] = None


class WSAssertionItem(BaseModel):
    message_index: int
    path: Optional[str] = None
    operator: str  # "equals", "contains", "exists", etc.
    expected: Any


class WSScenarioRequest(BaseModel):
    url: str
    headers: Optional[Dict[str, str]] = None
    scenario: List[Dict[str, Any]]
    assertions: Optional[List[Dict[str, Any]]] = None
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


# === Endpoints ===

@router.post("/scenario")
async def ws_run_scenario(req: WSScenarioRequest):
    """运行 WebSocket 测试场景（连接→发送/接收→断言→断开）"""
    from services.websocket_testing import create_ws_test_service, WSAssertion
    try:
        service = create_ws_test_service(req.url, req.headers)

        # 转换断言
        assertions = None
        if req.assertions:
            assertions = [
                WSAssertion(
                    message_index=a.get("message_index", 0),
                    path=a.get("path"),
                    operator=a.get("operator", "equals"),
                    expected=a.get("expected")
                )
                for a in req.assertions
            ]

        result = await service.run_scenario(req.scenario, assertions)
        get_execution_center_service().record_specialized_result(
            mode="websocket",
            title=f"WebSocket 场景 · {req.url}",
            target_url=req.url,
            success=result.connected and not result.error and result.assertions_failed == 0,
            summary=f"消息 {len(result.messages)} 条 · 断言成功 {result.assertions_passed} / 失败 {result.assertions_failed}",
            detail_items=[
                {
                    "target": f"消息 {index + 1}",
                    "passed": True,
                    "message": f"{item.direction}: {str(item.content)[:120]}",
                }
                for index, item in enumerate(result.messages[:6])
            ],
            duration_ms=int(result.total_time_ms or 0),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="websocket_scenario",
        )
        return {
            "status": "success",
            "connected": result.connected,
            "messages": [
                {
                    "direction": m.direction,
                    "content": m.content,
                    "timestamp": m.timestamp,
                    "message_type": m.message_type
                }
                for m in result.messages
            ],
            "assertions_passed": result.assertions_passed,
            "assertions_failed": result.assertions_failed,
            "total_time_ms": result.total_time_ms,
            "error": result.error
        }
    except Exception as e:
        get_execution_center_service().record_specialized_result(
            mode="websocket",
            title=f"WebSocket 场景 · {req.url}",
            target_url=req.url,
            success=False,
            summary=str(e),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="websocket_scenario",
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick-test")
async def ws_quick_test(req: WSSendRequest):
    """快速测试：连接→发送一条消息→接收响应→断开"""
    from services.websocket_testing import create_ws_test_service
    try:
        service = create_ws_test_service(req.url, req.headers)
        
        # 简单场景：connect → send → receive → disconnect
        scenario = [
            {"action": "send", "data": req.message, "is_json": req.is_json},
            {"action": "receive", "timeout": 5.0}
        ]
        result = await service.run_scenario(scenario)
        get_execution_center_service().record_specialized_result(
            mode="websocket",
            title=f"WebSocket 快速测试 · {req.url}",
            target_url=req.url,
            success=result.connected and not result.error,
            summary=f"消息 {len(result.messages)} 条 · 总耗时 {result.total_time_ms}ms",
            detail_items=[
                {
                    "target": f"消息 {index + 1}",
                    "passed": True,
                    "message": f"{item.direction}: {str(item.content)[:120]}",
                }
                for index, item in enumerate(result.messages[:6])
            ],
            duration_ms=int(result.total_time_ms or 0),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="websocket_quick",
        )
        return {
            "status": "success",
            "connected": result.connected,
            "messages": [
                {
                    "direction": m.direction,
                    "content": m.content,
                    "timestamp": m.timestamp,
                    "message_type": m.message_type
                }
                for m in result.messages
            ],
            "total_time_ms": result.total_time_ms,
            "error": result.error
        }
    except Exception as e:
        get_execution_center_service().record_specialized_result(
            mode="websocket",
            title=f"WebSocket 快速测试 · {req.url}",
            target_url=req.url,
            success=False,
            summary=str(e),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="websocket_quick",
        )
        raise HTTPException(status_code=500, detail=str(e))
