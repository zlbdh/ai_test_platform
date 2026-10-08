# -*- coding: utf-8 -*-
"""
GraphQL testing routes — integrates services/graphql_testing.py
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from services.execution_center_service import get_execution_center_service

router = APIRouter(prefix="/api/graphql", tags=["graphql"])


# === Request Models ===

class GraphQLExecuteRequest(BaseModel):
    endpoint: str
    query: str
    variables: Optional[Dict[str, Any]] = None
    operation_name: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    timeout: float = 30.0
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


class GraphQLIntrospectRequest(BaseModel):
    endpoint: str
    headers: Optional[Dict[str, str]] = None
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


class GraphQLTestSuiteRequest(BaseModel):
    endpoint: str
    headers: Optional[Dict[str, str]] = None
    tests: List[Dict[str, Any]]
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


class GraphQLGenerateQueryRequest(BaseModel):
    endpoint: str
    headers: Optional[Dict[str, str]] = None
    type_name: str
    depth: int = 2
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


# === Endpoints ===

@router.post("/execute")
async def graphql_execute(req: GraphQLExecuteRequest):
    """Execute a GraphQL query"""
    from services.graphql_testing import create_graphql_service, GraphQLRequest
    try:
        service = create_graphql_service(req.endpoint, req.headers)
        gql_req = GraphQLRequest(
            query=req.query,
            variables=req.variables,
            operation_name=req.operation_name
        )
        response = await service.execute(gql_req, timeout=req.timeout)
        success = response.status_code < 400 and not response.errors
        detail_items = [
            {
                "target": error.get("path") or "graphql-error",
                "passed": False,
                "message": error.get("message") or str(error),
            }
            for error in (response.errors or [])
        ]
        get_execution_center_service().record_specialized_result(
            mode="graphql",
            title=f"GraphQL execution · {req.endpoint}",
            target_url=req.endpoint,
            success=success,
            summary=f"HTTP {response.status_code} · {response.response_time_ms}ms · Errors: {len(response.errors or [])}",
            detail_items=detail_items,
            duration_ms=int(response.response_time_ms or 0),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
        )
        return {
            "status": "success",
            "data": response.data,
            "errors": response.errors,
            "extensions": response.extensions,
            "status_code": response.status_code,
            "response_time_ms": response.response_time_ms
        }
    except Exception as e:
        get_execution_center_service().record_specialized_result(
            mode="graphql",
            title=f"GraphQL execution · {req.endpoint}",
            target_url=req.endpoint,
            success=False,
            summary=str(e),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/introspect")
async def graphql_introspect(req: GraphQLIntrospectRequest):
    """Get the GraphQL schema through introspection"""
    from services.graphql_testing import create_graphql_service
    try:
        service = create_graphql_service(req.endpoint, req.headers)
        schema = await service.introspect()
        get_execution_center_service().record_specialized_result(
            mode="graphql",
            title=f"GraphQL introspection · {req.endpoint}",
            target_url=req.endpoint,
            success=bool(schema),
            summary=f"Retrieved {len(schema.get('types', []) or []) if isinstance(schema, dict) else 0} type definitions",
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="graphql_introspect",
        )
        return {"status": "success", "schema": schema}
    except Exception as e:
        get_execution_center_service().record_specialized_result(
            mode="graphql",
            title=f"GraphQL introspection · {req.endpoint}",
            target_url=req.endpoint,
            success=False,
            summary=str(e),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="graphql_introspect",
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-suite")
async def graphql_test_suite(req: GraphQLTestSuiteRequest):
    """Run a GraphQL test suite"""
    from services.graphql_testing import create_graphql_service
    try:
        service = create_graphql_service(req.endpoint, req.headers)
        results = await service.run_test_suite(req.tests)
        passed = sum(1 for r in results if r.get("passed"))
        failed = len(results) - passed
        detail_items = [
            {
                "target": item.get("name") or item.get("query") or "graphql-test",
                "passed": item.get("passed", False),
                "message": item.get("error") or f"Assertions passed {item.get('assertions_passed', 0)} / failed {item.get('assertions_failed', 0)}",
            }
            for item in results
        ]
        get_execution_center_service().record_specialized_result(
            mode="graphql",
            title=f"GraphQL test suite · {req.endpoint}",
            target_url=req.endpoint,
            success=failed == 0,
            summary=f"Executed {len(results)} tests: {passed} passed, {failed} failed",
            detail_items=detail_items,
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="graphql_suite",
        )
        return {
            "status": "success",
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "results": results
        }
    except Exception as e:
        get_execution_center_service().record_specialized_result(
            mode="graphql",
            title=f"GraphQL test suite · {req.endpoint}",
            target_url=req.endpoint,
            success=False,
            summary=str(e),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
            task_prefix="graphql_suite",
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-query")
async def graphql_generate_query(req: GraphQLGenerateQueryRequest):
    """Generate queries automatically from the schema"""
    from services.graphql_testing import create_graphql_service
    try:
        service = create_graphql_service(req.endpoint, req.headers)
        query = await service.generate_query_from_schema(req.type_name, depth=req.depth)
        return {"status": "success", "query": query}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
