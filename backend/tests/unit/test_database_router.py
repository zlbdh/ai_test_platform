# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from routers.database import ManagedQueryRequest, SQLExecuteRequest, db_execute, query_data, query_data_post


@pytest.mark.asyncio
async def test_db_execute_records_success_to_execution_center():
    recorder = MagicMock()

    with patch("core.db_tools.execute_sql", return_value={"status": "success", "count": 2}), \
         patch("routers.database.get_execution_center_service", return_value=recorder):
        result = await db_execute(
            SQLExecuteRequest(
                sql="SELECT * FROM demo",
                session_id="sess_demo",
                execution_group_id="batch_demo",
                group_title="数据库专项测试",
            )
        )

    assert result["status"] == "success"
    recorder.record_database_result.assert_called_once()
    kwargs = recorder.record_database_result.call_args.kwargs
    assert kwargs["action"] == "SQL 执行"
    assert kwargs["success"] is True
    assert kwargs["execution_group_id"] == "batch_demo"
    assert kwargs["session_id"] == "sess_demo"


@pytest.mark.asyncio
async def test_db_execute_records_failure_to_execution_center():
    recorder = MagicMock()

    with patch("core.db_tools.execute_sql", side_effect=RuntimeError("boom")), \
         patch("routers.database.get_execution_center_service", return_value=recorder):
        with pytest.raises(HTTPException):
            await db_execute(
                SQLExecuteRequest(
                    sql="SELECT * FROM broken",
                    session_id="sess_demo",
                    execution_group_id="batch_demo",
                    group_title="数据库专项测试",
                )
            )

    recorder.record_database_result.assert_called_once()
    kwargs = recorder.record_database_result.call_args.kwargs
    assert kwargs["action"] == "SQL 执行"
    assert kwargs["success"] is False
    assert kwargs["message"] == "boom"


@pytest.mark.asyncio
async def test_managed_query_post_records_success_to_execution_center():
    recorder = MagicMock()
    manager = MagicMock()
    manager.query_data.return_value = {
        "success": True,
        "rows": [{"total": 24}],
        "count": 1,
        "elapsed_ms": 128,
        "message": "查询完成，返回 1 行，用时 128 ms",
    }
    manager.connections = {
        "conn_demo": MagicMock(name="ry_cloud", db_type="mysql", database="ry_cloud")
    }
    manager.connections["conn_demo"].name = "ry_cloud"
    manager.connections["conn_demo"].db_type = "mysql"
    manager.connections["conn_demo"].database = "ry_cloud"

    with patch("routers.database.get_database_manager", return_value=manager), \
         patch("routers.database.get_execution_center_service", return_value=recorder):
        result = await query_data_post(
            "conn_demo",
            ManagedQueryRequest(
                sql="SELECT COUNT(*) AS total FROM distributor",
                limit=50,
                session_id="sess_demo",
                execution_group_id="batch_demo",
                group_title="数据库专项测试",
            ),
        )

    assert result["success"] is True
    manager.query_data.assert_called_once_with("conn_demo", "SELECT COUNT(*) AS total FROM distributor", 50)
    recorder.record_database_result.assert_called_once()
    kwargs = recorder.record_database_result.call_args.kwargs
    assert kwargs["action"] == "查询"
    assert kwargs["success"] is True
    assert "128 ms" in kwargs["message"]
    assert kwargs["execution_group_id"] == "batch_demo"
    assert kwargs["session_id"] == "sess_demo"


@pytest.mark.asyncio
async def test_managed_query_get_keeps_backwards_compatibility():
    recorder = MagicMock()
    manager = MagicMock()
    manager.query_data.return_value = {"success": False, "error": "Only SELECT queries are allowed", "rows": []}
    manager.connections = {
        "conn_demo": MagicMock(name="ry_cloud", db_type="mysql", database="ry_cloud")
    }
    manager.connections["conn_demo"].name = "ry_cloud"
    manager.connections["conn_demo"].db_type = "mysql"
    manager.connections["conn_demo"].database = "ry_cloud"

    with patch("routers.database.get_database_manager", return_value=manager), \
         patch("routers.database.get_execution_center_service", return_value=recorder):
        result = await query_data(
            "conn_demo",
            sql="DELETE FROM distributor",
            limit=10,
            session_id="sess_demo",
            execution_group_id="batch_demo",
            group_title="数据库专项测试",
        )

    assert result["success"] is False
    manager.query_data.assert_called_once_with("conn_demo", "DELETE FROM distributor", 10)
    recorder.record_database_result.assert_called_once()
    kwargs = recorder.record_database_result.call_args.kwargs
    assert kwargs["action"] == "查询"
    assert kwargs["success"] is False
    assert "Only SELECT" in kwargs["message"]
