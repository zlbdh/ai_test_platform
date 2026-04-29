"""
知识库工具 - RAG 相关工具
"""
from typing import Dict, Any, List
from langchain_core.tools import tool
from core.vector_store import get_vector_store


@tool
def store_document(collection_name: str, content: str, metadata: Dict[str, Any] = None) -> str:
    """
    存储文档到 Vector DB
    
    Args:
        collection_name: 集合名称 (bugs, prd, api_docs, test_plans)
        content: 文档内容
        metadata: 元数据（可选）
        
    Returns:
        文档 ID
    """
    vector_store = get_vector_store()
    doc_id = vector_store.store_document(collection_name, content, metadata)
    return f"文档已存储，ID: {doc_id}"


@tool
def search_similar_bugs(error_message: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """
    搜索相似的历史 Bug
    
    Args:
        error_message: 错误消息
        n_results: 返回结果数量
        
    Returns:
        相似 Bug 列表
    """
    vector_store = get_vector_store()
    return vector_store.search_similar_bugs(error_message, n_results)


@tool
def get_api_documentation(query: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """
    检索 API 文档
    
    Args:
        query: 查询文本
        n_results: 返回结果数量
        
    Returns:
        API 文档列表
    """
    vector_store = get_vector_store()
    return vector_store.get_api_documentation(query, n_results)


@tool
def get_prd_context(query: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """
    获取 PRD 上下文
    
    Args:
        query: 查询文本
        n_results: 返回结果数量
        
    Returns:
        PRD 文档列表
    """
    vector_store = get_vector_store()
    return vector_store.get_prd_context(query, n_results)


@tool
def get_similar_test_plans(scenario: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """
    获取相似的测试计划
    
    Args:
        scenario: 测试场景
        n_results: 返回结果数量
        
    Returns:
        相似测试计划列表
    """
    vector_store = get_vector_store()
    return vector_store.get_similar_test_plans(scenario, n_results)


# 工具列表
KNOWLEDGE_TOOLS = [
    store_document,
    search_similar_bugs,
    get_api_documentation,
    get_prd_context,
    get_similar_test_plans,
]
