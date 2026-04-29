# -*- coding: utf-8 -*-
"""
数据库测试路由 — 整合 core/db_tools.py + services/database_manager.py
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from core.models import DBConnectionRequest, DBInjectDataRequest, DBValidationRequest
from services.database_manager import get_database_manager
from services.execution_center_service import get_execution_center_service

router = APIRouter(prefix="/api/db", tags=["database"])


# === Request Models ===

class SQLExecuteRequest(BaseModel):
    sql: str
    allow_unsafe: bool = False
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


class SnapshotRequest(BaseModel):
    table: str
    condition: str
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


class DiffRequest(BaseModel):
    table: str
    condition: str
    snapshot_data: List[Dict[str, Any]]
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


class BackupRequest(BaseModel):
    table_name: Optional[str] = None
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


class ManagedQueryRequest(BaseModel):
    sql: str
    limit: int = 100
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


# === Endpoints ===

@router.post("/execute")
async def db_execute(req: SQLExecuteRequest):
    """执行 SQL 查询（安全模式）"""
    from core.db_tools import execute_sql
    try:
        result = execute_sql(req.sql, allow_unsafe=req.allow_unsafe)
        preview = req.sql.strip().replace("\n", " ")
        preview = preview[:120] + ("..." if len(preview) > 120 else "")
        success = str(result.get("status", "success")) != "error"
        if success and result.get("count") is not None:
            message = f"{preview} · 返回 {result.get('count', 0)} 行"
        elif success and result.get("affected_rows") is not None:
            message = f"{preview} · 影响 {result.get('affected_rows', 0)} 行"
        else:
            message = str(result.get("message") or result.get("error") or preview or "SQL 执行完成")
        get_execution_center_service().record_database_result(
            action="SQL 执行",
            connection_name="内置数据库",
            db_type="sqlite",
            database="platform",
            success=success,
            message=message,
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
        )
        return result
    except Exception as e:
        get_execution_center_service().record_database_result(
            action="SQL 执行",
            connection_name="内置数据库",
            db_type="sqlite",
            database="platform",
            success=False,
            message=str(e),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schema")
async def db_schema():
    """获取数据库 Schema"""
    from core.db_tools import get_db_schema
    try:
        schema = get_db_schema()
        return {"status": "success", "schema": schema}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/snapshot")
async def db_snapshot(req: SnapshotRequest):
    """创建数据快照"""
    from core.db_tools import snapshot_db
    try:
        result = snapshot_db(req.table, req.condition)
        get_execution_center_service().record_database_result(
            action="数据快照",
            connection_name="内置数据库",
            db_type="sqlite",
            database="platform",
            success=bool(result.get("status") == "success"),
            message=result.get("message") or f"{req.table} · 条件 {req.condition or '1=1'}",
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
        )
        return result
    except Exception as e:
        get_execution_center_service().record_database_result(
            action="数据快照",
            connection_name="内置数据库",
            db_type="sqlite",
            database="platform",
            success=False,
            message=str(e),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/diff")
async def db_diff(req: DiffRequest):
    """与快照比对差异"""
    from core.db_tools import diff_db
    try:
        result = diff_db(req.snapshot_data, req.table, req.condition)
        added = len(result.get("added", []) or [])
        removed = len(result.get("removed", []) or [])
        changed = len(result.get("changed", []) or [])
        get_execution_center_service().record_database_result(
            action="快照比对",
            connection_name="内置数据库",
            db_type="sqlite",
            database="platform",
            success=bool(result.get("status") == "success"),
            message=result.get("message") or f"{req.table} · 新增 {added} / 删除 {removed} / 变更 {changed}",
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
        )
        return result
    except Exception as e:
        get_execution_center_service().record_database_result(
            action="快照比对",
            connection_name="内置数据库",
            db_type="sqlite",
            database="platform",
            success=False,
            message=str(e),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backup")
async def db_backup(req: BackupRequest):
    """备份数据库"""
    from core.db_tools import backup_db
    try:
        result = backup_db(req.table_name)
        get_execution_center_service().record_database_result(
            action="数据库备份",
            connection_name="内置数据库",
            db_type="sqlite",
            database="platform",
            success=bool(result.get("status") == "success"),
            message=result.get("message") or f"备份 {req.table_name or '全部表'}",
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
        )
        return result
    except Exception as e:
        get_execution_center_service().record_database_result(
            action="数据库备份",
            connection_name="内置数据库",
            db_type="sqlite",
            database="platform",
            success=False,
            message=str(e),
            execution_group_id=req.execution_group_id,
            session_id=req.session_id,
            group_title=req.group_title,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables")
async def db_list_tables():
    """列出所有表"""
    from core.db_tools import list_db_tables
    try:
        result = list_db_tables()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Database Connection Manager ===

@router.get("/connections")
async def list_db_connections():
    """List all database connections"""
    return {"status": "success", "connections": get_database_manager().list_connections()}

@router.post("/connections")
async def create_db_connection(req: DBConnectionRequest):
    """Create a new database connection"""
    result = get_database_manager().create_connection(req.dict())
    return {"status": "success", "connection": result}

@router.get("/connections/{conn_id}")
async def get_db_connection(conn_id: str):
    """Get a database connection"""
    result = get_database_manager().get_connection(conn_id)
    if not result:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"status": "success", "connection": result}

@router.put("/connections/{conn_id}")
async def update_db_connection(conn_id: str, req: DBConnectionRequest):
    """Update a database connection"""
    result = get_database_manager().update_connection(conn_id, req.dict())
    if not result:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"status": "success", "connection": result}

@router.delete("/connections/{conn_id}")
async def delete_db_connection(conn_id: str):
    """Delete a database connection"""
    if get_database_manager().delete_connection(conn_id):
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Connection not found")

@router.post("/connections/{conn_id}/test")
async def test_db_connection(
    conn_id: str,
    execution_group_id: Optional[str] = None,
    session_id: str = "default_session",
    group_title: Optional[str] = None,
):
    """Test a database connection"""
    mgr = get_database_manager()
    result = mgr.test_connection(conn_id)
    conn_meta = mgr.connections.get(conn_id)
    if conn_meta:
        get_execution_center_service().record_database_result(
            action="连接测试",
            connection_name=conn_meta.name,
            db_type=conn_meta.db_type,
            database=conn_meta.database,
            success=bool(result.get("success")),
            message=result.get("message") or result.get("error") or "数据库连接测试完成",
            execution_group_id=execution_group_id,
            session_id=session_id,
            group_title=group_title,
        )
    return {"status": "success" if result["success"] else "error", **result}

@router.get("/connections/{conn_id}/tables")
async def get_db_tables_manager(conn_id: str):
    """Get tables in a database (via Manager)"""
    return {"status": "success", "tables": get_database_manager().get_tables(conn_id)}

@router.get("/connections/{conn_id}/tables/{table_name}/columns")
async def get_table_columns_manager(conn_id: str, table_name: str):
    """Get columns of a table (via Manager)"""
    return {"status": "success", "columns": get_database_manager().get_table_columns(conn_id, table_name)}

@router.get("/connections/{conn_id}/schema")
async def get_connection_schema_manager(conn_id: str):
    """Get schema overview for a managed connection"""
    result = get_database_manager().generate_schema_text(conn_id)
    return {"status": "success" if result.get("success") else "error", **result}

# === Data Operations ===

@router.post("/connections/{conn_id}/tables/{table_name}/inject")
async def inject_data(conn_id: str, table_name: str, req: DBInjectDataRequest):
    """Inject data into a table"""
    result = get_database_manager().inject_data(conn_id, table_name, req.data)
    return result

@router.delete("/connections/{conn_id}/tables/{table_name}/clean")
async def clean_table(conn_id: str, table_name: str, where_clause: str = ""):
    """Clean data from a table"""
    result = get_database_manager().clean_table(conn_id, table_name, where_clause)
    return result

def _run_managed_query(
    conn_id: str,
    sql: str,
    limit: int = 100,
    execution_group_id: Optional[str] = None,
    session_id: str = "default_session",
    group_title: Optional[str] = None,
):
    """执行托管数据库 SELECT 查询，并统一记录到执行中心。"""
    mgr = get_database_manager()
    result = mgr.query_data(conn_id, sql, limit)
    conn_meta = mgr.connections.get(conn_id)
    if conn_meta:
        preview = sql.strip().replace("\n", " ")
        preview = preview[:120] + ("..." if len(preview) > 120 else "")
        get_execution_center_service().record_database_result(
            action="查询",
            connection_name=conn_meta.name,
            db_type=conn_meta.db_type,
            database=conn_meta.database,
            success=bool(result.get("success")),
            message=result.get("error") or result.get("message") or f"{preview} · 返回 {result.get('count', 0)} 行",
            duration_ms=int(result.get("elapsed_ms") or 0),
            execution_group_id=execution_group_id,
            session_id=session_id,
            group_title=group_title,
        )
    return result


@router.post("/connections/{conn_id}/query")
async def query_data_post(conn_id: str, req: ManagedQueryRequest):
    """Execute a SELECT query via POST body."""
    return _run_managed_query(
        conn_id=conn_id,
        sql=req.sql,
        limit=req.limit,
        execution_group_id=req.execution_group_id,
        session_id=req.session_id,
        group_title=req.group_title,
    )


@router.get("/connections/{conn_id}/query")
async def query_data(
    conn_id: str,
    sql: str,
    limit: int = 100,
    execution_group_id: Optional[str] = None,
    session_id: str = "default_session",
    group_title: Optional[str] = None,
):
    """Execute a SELECT query via query string for backwards compatibility."""
    return _run_managed_query(
        conn_id=conn_id,
        sql=sql,
        limit=limit,
        execution_group_id=execution_group_id,
        session_id=session_id,
        group_title=group_title,
    )

@router.post("/connections/{conn_id}/validate")
async def validate_data(
    conn_id: str,
    req: DBValidationRequest,
    execution_group_id: Optional[str] = None,
    session_id: str = "default_session",
    group_title: Optional[str] = None,
):
    """Validate data against rules"""
    mgr = get_database_manager()
    result = mgr.validate_data(conn_id, req.rules)
    conn_meta = mgr.connections.get(conn_id)
    if conn_meta:
        detail_items = [
            {
                "target": f"{rule.get('table', '')}.{rule.get('column', '')}:{rule.get('operator', '')}",
                "passed": item.get("passed", False),
                "message": item.get("message", ""),
            }
            for rule, item in zip(req.rules, result.get("results", []))
        ]
        get_execution_center_service().record_database_result(
            action="验证",
            connection_name=conn_meta.name,
            db_type=conn_meta.db_type,
            database=conn_meta.database,
            success=bool(result.get("success")),
            message=f"通过 {result.get('passed', 0)} / 失败 {result.get('failed', 0)}",
            detail_items=detail_items,
            execution_group_id=execution_group_id,
            session_id=session_id,
            group_title=group_title,
        )
    return result
