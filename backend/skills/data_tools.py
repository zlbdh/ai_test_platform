"""
数据测试工具
用于数据库验证、数据一致性检查等
统一使用 core.db_tools (SQLite / SQLAlchemy) 而非 pymysql
"""
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
from core.config import Config
from core.db_tools import execute_sql, get_db_schema as _get_db_schema
from skills.text_to_sql import query_db_natural_language


@tool
def execute_query(query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """
    执行 SQL 查询

    Args:
        query: SQL 查询语句
        params: 查询参数（保留接口兼容，当前未启用参数化）

    Returns:
        查询结果
    """
    try:
        result = execute_sql(query)
        if result.get("status") == "error":
            return [{"error": result.get("error") or result.get("message", "Unknown error")}]
        # SELECT 查询返回 data 列表
        if "data" in result:
            return result["data"]
        # INSERT/UPDATE/DELETE 返回 affected_rows
        return [{"affected_rows": result.get("affected_rows", 0)}]
    except Exception as e:
        return [{"error": str(e)}]


@tool
def verify_data_consistency(table: str, condition: str, expected_count: int) -> Dict[str, Any]:
    """
    验证数据一致性

    Args:
        table: 表名
        condition: WHERE 条件
        expected_count: 期望的记录数

    Returns:
        验证结果
    """
    try:
        query = f"SELECT COUNT(*) as count FROM {table} WHERE {condition}"
        result = execute_sql(query)

        if result.get("status") == "error":
            return {"status": "error", "error": result.get("error")}

        data = result.get("data", [])
        actual_count = data[0].get("count", 0) if data else 0
        is_consistent = actual_count == expected_count

        return {
            "table": table,
            "condition": condition,
            "expected_count": expected_count,
            "actual_count": actual_count,
            "is_consistent": is_consistent,
            "status": "一致" if is_consistent else "不一致"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@tool
def check_table_exists(table: str) -> bool:
    """
    检查表是否存在

    Args:
        table: 表名

    Returns:
        表是否存在
    """
    try:
        # SQLite 兼容：查询 sqlite_master
        query = f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
        result = execute_sql(query)
        if result.get("status") == "error":
            return False
        return len(result.get("data", [])) > 0
    except Exception as e:
        return False


@tool
def get_table_schema(table: str) -> List[Dict[str, Any]]:
    """
    获取表结构

    Args:
        table: 表名

    Returns:
        表结构信息
    """
    try:
        # SQLite 兼容：使用 PRAGMA table_info
        query = f"PRAGMA table_info({table})"
        result = execute_sql(query)
        if result.get("status") == "error":
            return [{"error": result.get("error")}]
        return result.get("data", [])
    except Exception as e:
        return [{"error": str(e)}]


@tool
def cleanup_test_data(table: str, condition: str) -> Dict[str, Any]:
    """
    清理测试数据

    Args:
        table: 表名
        condition: WHERE 条件

    Returns:
        清理结果
    """
    try:
        query = f"DELETE FROM {table} WHERE {condition}"
        result = execute_sql(query)

        if result.get("status") == "error":
            return {"status": "error", "error": result.get("error") or result.get("message")}

        return {
            "status": "success",
            "table": table,
            "affected_rows": result.get("affected_rows", 0)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@tool
def verify_transaction(table: str, transaction_id: str, expected_status: str) -> Dict[str, Any]:
    """
    验证事务状态（如下单后订单状态）

    Args:
        table: 表名（如 orders）
        transaction_id: 事务 ID（如 order_id）
        expected_status: 期望的状态（如 'paid', 'pending'）

    Returns:
        验证结果
    """
    try:
        query = f"SELECT * FROM {table} WHERE id = '{transaction_id}'"
        result = execute_sql(query)

        if result.get("status") == "error":
            return {"status": "error", "error": result.get("error")}

        data = result.get("data", [])
        if not data:
            return {
                "status": "error",
                "message": f"未找到 ID 为 {transaction_id} 的记录"
            }

        record = data[0]
        actual_status = record.get("status", "")
        is_correct = actual_status == expected_status

        return {
            "transaction_id": transaction_id,
            "expected_status": expected_status,
            "actual_status": actual_status,
            "is_correct": is_correct,
            "record": record
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@tool
def query_db_natural_language_tool(natural_language_query: str, table_schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    使用自然语言查询数据库（Text-to-SQL）

    Args:
        natural_language_query: 自然语言查询（如"查询张三的订单状态"）
        table_schema: 可选，表结构信息

    Returns:
        查询结果
    """
    try:
        # 转换为 SQL
        sql_result = query_db_natural_language.invoke({
            "natural_language_query": natural_language_query,
            "table_schema": table_schema
        })

        if sql_result.get("status") != "success":
            return sql_result

        sql_query = sql_result.get("sql", "")

        # 执行 SQL
        query_result = execute_sql(sql_query)
        if query_result.get("status") == "error":
            return {"status": "error", "error": query_result.get("error"), "sql": sql_query}

        query_data = query_result.get("data", [])

        return {
            "status": "success",
            "natural_language": natural_language_query,
            "sql": sql_query,
            "results": query_data,
            "row_count": len(query_data)
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "natural_language": natural_language_query
        }


# 工具列表
DATA_TOOLS = [
    execute_query,
    query_db_natural_language_tool,
    verify_data_consistency,
    check_table_exists,
    get_table_schema,
    verify_transaction,
    cleanup_test_data,
]
