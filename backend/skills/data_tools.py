"""
Data testing tools
For database validation, data consistency checks, and related tasks
Use core.db_tools (SQLite / SQLAlchemy) consistently instead of pymysql
"""
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
from core.config import Config
from core.db_tools import execute_sql, get_db_schema as _get_db_schema
from skills.text_to_sql import query_db_natural_language


@tool
def execute_query(query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """
    Execute an SQL query

    Args:
        query: SQL query statement
        params: Query parameters (retained for interface compatibility; parameterization is not currently enabled)

    Returns:
        Query results
    """
    try:
        result = execute_sql(query)
        if result.get("status") == "error":
            return [{"error": result.get("error") or result.get("message", "Unknown error")}]
        # SELECT queries return the data list
        if "data" in result:
            return result["data"]
        # INSERT/UPDATE/DELETE return affected_rows
        return [{"affected_rows": result.get("affected_rows", 0)}]
    except Exception as e:
        return [{"error": str(e)}]


@tool
def verify_data_consistency(table: str, condition: str, expected_count: int) -> Dict[str, Any]:
    """
    Validate data consistency

    Args:
        table: Table name
        condition: WHERE condition
        expected_count: Expected record count

    Returns:
        Validation result
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
            "status": "consistent" if is_consistent else "inconsistent"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@tool
def check_table_exists(table: str) -> bool:
    """
    Check whether a table exists

    Args:
        table: Table name

    Returns:
        Whether the table exists
    """
    try:
        # SQLite compatibility: query sqlite_master
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
    Get the table schema

    Args:
        table: Table name

    Returns:
        Table schema information
    """
    try:
        # SQLite compatibility: use PRAGMA table_info
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
    Clean up test data

    Args:
        table: Table name
        condition: WHERE condition

    Returns:
        Cleanup result
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
    Validate transaction status (such as an order's status after placement)

    Args:
        table: Table name (such as orders)
        transaction_id: Transaction ID (such as order_id)
        expected_status: Expected status (such as 'paid' or 'pending')

    Returns:
        Validation result
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
                "message": f"No record found with ID {transaction_id}"
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
    Query the database using natural language (Text-to-SQL)

    Args:
        natural_language_query: Natural-language query (such as "Get Zhang San's order status")
        table_schema: Optional table schema information

    Returns:
        Query results
    """
    try:
        # Convert to SQL
        sql_result = query_db_natural_language.invoke({
            "natural_language_query": natural_language_query,
            "table_schema": table_schema
        })

        if sql_result.get("status") != "success":
            return sql_result

        sql_query = sql_result.get("sql", "")

        # Execute SQL
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


# Tool list
DATA_TOOLS = [
    execute_query,
    query_db_natural_language_tool,
    verify_data_consistency,
    check_table_exists,
    get_table_schema,
    verify_transaction,
    cleanup_test_data,
]
