# -*- coding: utf-8 -*-
"""
gRPC 测试路由 — 串联 services/grpc_testing.py
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from services.execution_center_service import get_execution_center_service

router = APIRouter(prefix="/api/grpc", tags=["grpc"])


# === Request Models ===

class GrpcCallRequest(BaseModel):
    host: str
    port: int = 50051
    use_tls: bool = False
    service: str
    method: str
    data: Dict[str, Any] = {}
    metadata: Optional[Dict[str, str]] = None
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


class GrpcReflectRequest(BaseModel):
    host: str
    port: int = 50051
    use_tls: bool = False
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


class GrpcDescribeRequest(BaseModel):
    host: str
    port: int = 50051
    use_tls: bool = False
    service: str
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


class GrpcTestSuiteRequest(BaseModel):
    host: str
    port: int = 50051
    use_tls: bool = False
    tests: List[Dict[str, Any]]
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


# === Endpoints ===

@router.post("/call")
async def grpc_call(req: GrpcCallRequest):
    """执行 gRPC Unary 调用"""
    from services.grpc_testing import create_grpc_service, GrpcRequest
    try:
        service = create_grpc_service(req.host, req.port, req.use_tls)
        grpc_req = GrpcRequest(
            service=req.service,
            method=req.method,
            data=req.data,
            metadata=req.metadata
        )
        response = await service.call(grpc_req)
        get_execution_center_service().record_specialized_result(
            mode="grpc",
            title=f"gRPC 调用 · {req.service}/{req.method}",
            target_url=f"{req.host}:{req.port}",
            success=response.success,
            summary=response.error or f"状态码 {response.status_code} · {response.response_time_ms}ms",
            detail_items=[
                {
                    "target": f"{req.service}/{req.method}",
                    "passed": response.success,
                    "message": response.error or "调用成功",
                }
            ],
            duration_ms=int(response.response_time_ms or 0),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="grpc_call",
        )
        return {
            "status": "success" if response.success else "error",
            "data": response.data,
            "error": response.error,
            "status_code": response.status_code,
            "response_time_ms": response.response_time_ms
        }
    except Exception as e:
        get_execution_center_service().record_specialized_result(
            mode="grpc",
            title=f"gRPC 调用 · {req.service}/{req.method}",
            target_url=f"{req.host}:{req.port}",
            success=False,
            summary=str(e),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="grpc_call",
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/services")
async def grpc_list_services(req: GrpcReflectRequest):
    """列出 gRPC 可用服务（反射）"""
    from services.grpc_testing import create_grpc_service
    try:
        service = create_grpc_service(req.host, req.port, req.use_tls)
        services = await service.list_services()
        get_execution_center_service().record_specialized_result(
            mode="grpc",
            title=f"gRPC 反射 · {req.host}:{req.port}",
            target_url=f"{req.host}:{req.port}",
            success=len(services) > 0,
            summary=f"发现 {len(services)} 个服务",
            detail_items=[
                {"target": item, "passed": True, "message": "服务可见"}
                for item in services
            ],
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="grpc_reflect",
        )
        return {"status": "success", "services": services}
    except Exception as e:
        get_execution_center_service().record_specialized_result(
            mode="grpc",
            title=f"gRPC 反射 · {req.host}:{req.port}",
            target_url=f"{req.host}:{req.port}",
            success=False,
            summary=str(e),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="grpc_reflect",
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/describe")
async def grpc_describe_service(req: GrpcDescribeRequest):
    """描述 gRPC 服务方法"""
    from services.grpc_testing import create_grpc_service
    try:
        service = create_grpc_service(req.host, req.port, req.use_tls)
        description = await service.describe_service(req.service)
        get_execution_center_service().record_specialized_result(
            mode="grpc",
            title=f"gRPC 描述 · {req.service}",
            target_url=f"{req.host}:{req.port}",
            success=bool(description),
            summary="服务描述已获取" if description else "服务描述为空",
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="grpc_describe",
        )
        return {"status": "success", "description": description}
    except Exception as e:
        get_execution_center_service().record_specialized_result(
            mode="grpc",
            title=f"gRPC 描述 · {req.service}",
            target_url=f"{req.host}:{req.port}",
            success=False,
            summary=str(e),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="grpc_describe",
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-suite")
async def grpc_test_suite(req: GrpcTestSuiteRequest):
    """运行 gRPC 测试套件"""
    from services.grpc_testing import create_grpc_service
    try:
        service = create_grpc_service(req.host, req.port, req.use_tls)
        suite = await service.run_test_suite(req.tests)
        results = suite.get("results", [])
        passed = int(suite.get("passed", 0) or 0)
        failed = int(suite.get("failed", 0) or 0)
        get_execution_center_service().record_specialized_result(
            mode="grpc",
            title=f"gRPC 测试套件 · {req.host}:{req.port}",
            target_url=f"{req.host}:{req.port}",
            success=failed == 0 and len(results) > 0,
            summary=f"共执行 {len(results)} 个测试，成功 {passed}，失败 {failed}",
            detail_items=[
                {
                    "target": item.get("name") or "gRPC 测试",
                    "passed": item.get("passed", False),
                    "message": item.get("error") or f"耗时 {item.get('response_time_ms', 0)}ms",
                }
                for item in results
            ],
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="grpc_suite",
        )
        return {
            "status": "success",
            "total": int(suite.get("total", len(results)) or len(results)),
            "passed": passed,
            "failed": failed,
            "results": results
        }
    except Exception as e:
        get_execution_center_service().record_specialized_result(
            mode="grpc",
            title=f"gRPC 测试套件 · {req.host}:{req.port}",
            target_url=f"{req.host}:{req.port}",
            success=False,
            summary=str(e),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="grpc_suite",
        )
        raise HTTPException(status_code=500, detail=str(e))
