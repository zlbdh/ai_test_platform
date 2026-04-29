# -*- coding: utf-8 -*-
"""
API 工作台路由 — 使用 api_workbench_service 持久化后端
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from services.execution_center_service import get_execution_center_service

router = APIRouter(prefix="/api/workbench", tags=["workbench"])


# === Models ===
class CollectionCreate(BaseModel):
    name: str
    description: str = ""

class RequestCreate(BaseModel):
    name: str = "New Request"
    method: str = "GET"
    url: str = ""
    headers: Dict[str, str] = {}
    params: Dict[str, str] = {}
    body: str = ""
    body_type: str = "json"
    assertions: List[Dict[str, Any]] = []
    extract_variables: List[Dict[str, str]] = []

class RequestUpdate(BaseModel):
    name: Optional[str] = None
    method: Optional[str] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    body: Optional[str] = None
    params: Optional[Dict[str, str]] = None

class EnvironmentCreate(BaseModel):
    name: str
    variables: Dict[str, str] = {}

class ExecuteRequest(BaseModel):
    request: Dict[str, Any]
    extra_vars: Optional[Dict[str, str]] = None
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None

class RunCollectionRequest(BaseModel):
    collection_id: str
    stop_on_failure: bool = False
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


def _get_service():
    from services.api_workbench import get_api_workbench_service
    return get_api_workbench_service()


# === Collections ===

@router.get("/collections")
async def list_collections():
    """列出所有集合"""
    service = _get_service()
    return {"status": "success", "collections": service.list_collections()}


@router.post("/collections")
async def create_collection(req: CollectionCreate):
    """创建新集合"""
    service = _get_service()
    coll = service.create_collection(req.name, req.description)
    return {"status": "success", "collection": coll}


@router.get("/collections/{collection_id}")
async def get_collection(collection_id: str):
    """获取集合详情"""
    service = _get_service()
    coll = service.get_collection(collection_id)
    if not coll:
        raise HTTPException(404, "Collection not found")
    return {"status": "success", "collection": coll}


@router.put("/collections/{collection_id}")
async def update_collection(collection_id: str, req: CollectionCreate):
    """更新集合"""
    service = _get_service()
    coll = service.update_collection(collection_id, {"name": req.name, "description": req.description})
    if not coll:
        raise HTTPException(404, "Collection not found")
    return {"status": "success", "collection": coll}


@router.delete("/collections/{collection_id}")
async def delete_collection(collection_id: str):
    """删除集合"""
    service = _get_service()
    if service.delete_collection(collection_id):
        return {"status": "success", "message": "Collection deleted"}
    raise HTTPException(404, "Collection not found")


# === Requests within collections ===

@router.get("/collections/{collection_id}/requests")
async def list_requests(collection_id: str):
    """列出集合中的请求"""
    service = _get_service()
    coll = service.get_collection(collection_id)
    if not coll:
        raise HTTPException(404, "Collection not found")
    return {"requests": coll.get("requests", [])}


@router.post("/collections/{collection_id}/requests")
async def create_request(collection_id: str, req: RequestCreate):
    """在集合中创建请求"""
    service = _get_service()
    result = service.add_request(collection_id, req.dict())
    if not result:
        raise HTTPException(404, "Collection not found")
    return {"status": "success", "request": result}


@router.put("/collections/{collection_id}/requests/{request_id}")
async def update_request(collection_id: str, request_id: str, req: RequestUpdate):
    """更新请求"""
    service = _get_service()
    update_data = {k: v for k, v in req.dict().items() if v is not None}
    result = service.update_request(collection_id, request_id, update_data)
    if not result:
        raise HTTPException(404, "Request not found")
    return {"status": "success", "request": result}


@router.delete("/collections/{collection_id}/requests/{request_id}")
async def delete_request(collection_id: str, request_id: str):
    """删除请求"""
    service = _get_service()
    if service.delete_request(collection_id, request_id):
        return {"status": "success"}
    raise HTTPException(404, "Request not found")


# === Environments ===

@router.get("/environments")
async def list_environments():
    """列出所有环境"""
    service = _get_service()
    return {"status": "success", "environments": service.list_environments()}


@router.get("/environments/active")
async def get_active_environment():
    """获取当前活动环境"""
    service = _get_service()
    env = service.get_active_environment()
    return {"status": "success", "environment": env}


@router.post("/environments")
async def create_environment(req: EnvironmentCreate):
    """创建新环境"""
    service = _get_service()
    env = service.create_environment(req.name, req.variables)
    return {"status": "success", "environment": env}


@router.put("/environments/{env_id}")
async def update_environment(env_id: str, req: EnvironmentCreate):
    """更新环境"""
    service = _get_service()
    env = service.update_environment(env_id, {"name": req.name, "variables": req.variables})
    if not env:
        raise HTTPException(404, "Environment not found")
    return {"status": "success", "environment": env}


@router.post("/environments/{env_id}/activate")
async def activate_environment(env_id: str):
    """设置活动环境"""
    service = _get_service()
    if service.set_active_environment(env_id):
        return {"status": "success", "message": "Environment activated"}
    raise HTTPException(404, "Environment not found")


@router.delete("/environments/{env_id}")
async def delete_environment(env_id: str):
    """删除环境"""
    service = _get_service()
    if service.delete_environment(env_id):
        return {"status": "success", "message": "Environment deleted"}
    raise HTTPException(404, "Environment not found")


# === Execute ===

@router.post("/execute")
async def execute_request(req: ExecuteRequest):
    """执行 HTTP 请求"""
    try:
        service = _get_service()
        result = await service.execute_request(req.request, req.extra_vars or {})
        status_code = int(result.get("status_code") or 0)
        success = bool(result.get("success")) and 200 <= status_code < 400
        summary = (
            result.get("error")
            or f"HTTP {status_code} · {int(result.get('response_time_ms') or 0)}ms · 断言通过 {result.get('assertions_passed', 0)} / 失败 {result.get('assertions_failed', 0)}"
        )
        detail_items = [
            {
                "target": str(item.get("type") or item.get("path") or "assertion"),
                "passed": item.get("passed", False),
                "message": item.get("message") or f"期望 {item.get('expected')}，实际 {item.get('actual')}",
            }
            for item in result.get("assertion_details", []) or []
        ]
        request_name = str(req.request.get("name") or f"{req.request.get('method', 'GET')} {req.request.get('url', '')}")
        get_execution_center_service().record_specialized_result(
            mode="api_workbench",
            title=f"API 工作台 · {request_name}",
            target_url=str(req.request.get("url") or ""),
            success=success,
            summary=summary,
            detail_items=detail_items,
            duration_ms=int(result.get("response_time_ms") or 0),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="api_workbench",
        )
        return {"status": "success", "result": result}
    except Exception as e:
        import traceback
        traceback.print_exc()
        get_execution_center_service().record_specialized_result(
            mode="api_workbench",
            title=f"API 工作台 · {req.request.get('name') or req.request.get('method', 'GET')}",
            target_url=str(req.request.get("url") or ""),
            success=False,
            summary=str(e),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="api_workbench",
        )
        raise HTTPException(500, detail=f"执行请求失败: {str(e)}")


@router.post("/run-collection")
async def run_collection(req: RunCollectionRequest):
    """运行集合中的所有请求"""
    service = _get_service()
    result = await service.run_collection(req.collection_id, req.stop_on_failure)
    if "error" in result:
        get_execution_center_service().record_specialized_result(
            mode="api_workbench",
            title=f"API 集合执行 · {req.collection_id}",
            target_url=req.collection_id,
            success=False,
            summary=str(result["error"]),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="api_collection",
        )
        raise HTTPException(404, result["error"])
    success = int(result.get("failed", 0) or 0) == 0
    detail_items = [
        {
            "target": item.get("request_name") or item.get("request_id") or "request",
            "passed": item.get("success", False),
            "message": item.get("error") or f"HTTP {item.get('status_code', 0)} · {int(item.get('response_time_ms', 0) or 0)}ms",
        }
        for item in result.get("results", []) or []
    ]
    get_execution_center_service().record_specialized_result(
        mode="api_workbench",
        title=f"API 集合执行 · {result.get('collection_name') or req.collection_id}",
        target_url=str(result.get("collection_name") or req.collection_id),
        success=success,
        summary=f"共执行 {result.get('executed', 0)} 个请求，成功 {result.get('passed', 0)}，失败 {result.get('failed', 0)}",
        detail_items=detail_items,
        duration_ms=int(result.get("total_time_ms") or 0),
        execution_group_id=req.execution_group_id,
        session_id=req.session_id,
        group_title=req.group_title,
        task_prefix="api_collection",
    )
    return {"status": "success", "result": result}
