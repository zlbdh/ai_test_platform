"""
Text-to-SQL 转换器
使用 LLM 将自然语言转换为 SQL 查询
"""
from typing import Dict, Any, Optional
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from core.config import Config
from core.llm_manager import get_llm
from core.prompts import TEXT_TO_SQL_PROMPT, EXPLAIN_SQL_PROMPT


def _get_llm():
    """获取 LLM 实例"""
    return get_llm(fake_responses=[
        "SELECT * FROM orders WHERE user_id = 1 AND status = 'paid'",
        "SELECT COUNT(*) FROM users WHERE created_at > '2024-01-01'",
        "SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id WHERE o.status = 'pending'"
    ])


@tool
def query_db_natural_language(natural_language_query: str, table_schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    将自然语言查询转换为 SQL
    
    Args:
        natural_language_query: 自然语言查询（如"查询张三的订单状态"）
        table_schema: 可选，表结构信息（帮助生成更准确的 SQL）
        
    Returns:
        包含 SQL 查询的字典
    """
    try:
        llm = _get_llm()
        
        # 构建提示
        schema_info = ""
        if table_schema:
            schema_info = f"\n\n表结构信息：\n{table_schema}"
        
        prompt = ChatPromptTemplate.from_template(TEXT_TO_SQL_PROMPT)
        
        chain = prompt | llm | StrOutputParser()
        sql_query = chain.invoke({
            "query": natural_language_query,
            "schema_info": schema_info
        })
        
        # 清理 SQL（移除可能的 markdown 代码块）
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
    解释 SQL 查询的含义
    
    Args:
        sql_query: SQL 查询语句
        
    Returns:
        SQL 的自然语言解释
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
    验证 SQL 查询的语法
    
    Args:
        sql_query: SQL 查询语句
        
    Returns:
        验证结果
    """
    try:
        # 简单的 SQL 验证（实际应该使用更专业的 SQL 解析器）
        sql_upper = sql_query.upper().strip()
        
        # 检查基本 SQL 关键字
        valid_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "FROM", "WHERE", "JOIN"]
        has_keyword = any(keyword in sql_upper for keyword in valid_keywords)
        
        # 检查是否有危险的 SQL 操作（在测试环境中）
        dangerous_keywords = ["DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE"]
        has_dangerous = any(keyword in sql_upper for keyword in dangerous_keywords)
        
        return {
            "status": "success",
            "sql": sql_query,
            "is_valid": has_keyword and not has_dangerous,
            "has_dangerous_operations": has_dangerous,
            "warnings": ["包含危险操作，建议检查"] if has_dangerous else []
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


# 工具列表
TEXT_TO_SQL_TOOLS = [
    query_db_natural_language,
    explain_sql,
    validate_sql,
]
