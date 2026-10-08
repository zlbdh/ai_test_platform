"""
Text-to-SQL converter
Use an LLM to convert natural language into SQL queries
"""
from typing import Dict, Any, Optional
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from core.config import Config
from core.llm_manager import get_llm
from core.prompts import TEXT_TO_SQL_PROMPT, EXPLAIN_SQL_PROMPT


def _get_llm():
    """Get an LLM instance"""
    return get_llm(fake_responses=[
        "SELECT * FROM orders WHERE user_id = 1 AND status = 'paid'",
        "SELECT COUNT(*) FROM users WHERE created_at > '2024-01-01'",
        "SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id WHERE o.status = 'pending'"
    ])


@tool
def query_db_natural_language(natural_language_query: str, table_schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convert a natural-language query to SQL

    Args:
        natural_language_query: Natural-language query (such as "Get Zhang San's order status")
        table_schema: Optional table schema information (helps generate more accurate SQL)

    Returns:
        Dictionary containing the SQL query
    """
    try:
        llm = _get_llm()

        # Build the prompt
        schema_info = ""
        if table_schema:
            schema_info = f"\n\nTable schema information:\n{table_schema}"

        prompt = ChatPromptTemplate.from_template(TEXT_TO_SQL_PROMPT)

        chain = prompt | llm | StrOutputParser()
        sql_query = chain.invoke({
            "query": natural_language_query,
            "schema_info": schema_info
        })

        # Clean the SQL by removing any Markdown fences
        sql_query = sql_query.strip()
        if sql_query.startswith("```sql"):
            sql_query = sql_query[6:]
        if sql_query.startswith("```"):
            sql_query = sql_query[3:]
        if sql_query.endswith("```"):
            sql_query = sql_query[:-3]
        sql_query = sql_query.strip()

        return {
            "status": "success",
            "natural_language": natural_language_query,
            "sql": sql_query,
            "table_schema": table_schema
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "natural_language": natural_language_query
        }


@tool
def explain_sql(sql_query: str) -> Dict[str, Any]:
    """
    Explain the meaning of an SQL query

    Args:
        sql_query: SQL query statement

    Returns:
        Natural-language explanation of the SQL
    """
    try:
        llm = _get_llm()

        prompt = ChatPromptTemplate.from_template(EXPLAIN_SQL_PROMPT)

        chain = prompt | llm | StrOutputParser()
        explanation = chain.invoke({"sql": sql_query})

        return {
            "status": "success",
            "sql": sql_query,
            "explanation": explanation
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@tool
def validate_sql(sql_query: str) -> Dict[str, Any]:
    """
    Validate SQL query syntax

    Args:
        sql_query: SQL query statement

    Returns:
        Validation result
    """
    try:
        # Basic SQL validation (a production implementation should use a dedicated SQL parser)
        sql_upper = sql_query.upper().strip()

        # Check for basic SQL keywords
        valid_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "FROM", "WHERE", "JOIN"]
        has_keyword = any(keyword in sql_upper for keyword in valid_keywords)

        # Check for dangerous SQL operations (in the test environment)
        dangerous_keywords = ["DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE"]
        has_dangerous = any(keyword in sql_upper for keyword in dangerous_keywords)

        return {
            "status": "success",
            "sql": sql_query,
            "is_valid": has_keyword and not has_dangerous,
            "has_dangerous_operations": has_dangerous,
            "warnings": ["Contains dangerous operations; review recommended"] if has_dangerous else []
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


# Tool list
TEXT_TO_SQL_TOOLS = [
    query_db_natural_language,
    explain_sql,
    validate_sql,
]
