"""
Knowledge base tools - RAG utilities
"""
from typing import Dict, Any, List
from langchain_core.tools import tool
from core.vector_store import get_vector_store


@tool
def store_document(collection_name: str, content: str, metadata: Dict[str, Any] = None) -> str:
    """
    Store a document in the vector database

    Args:
        collection_name: Collection name (bugs, prd, api_docs, test_plans)
        content: Document content
        metadata: Metadata (optional)

    Returns:
        Document ID
    """
    vector_store = get_vector_store()
    doc_id = vector_store.store_document(collection_name, content, metadata)
    return f"Document stored; ID: {doc_id}"


@tool
def search_similar_bugs(error_message: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search for similar historical bugs

    Args:
        error_message: Error message
        n_results: Number of results to return

    Returns:
        List of similar bugs
    """
    vector_store = get_vector_store()
    return vector_store.search_similar_bugs(error_message, n_results)


@tool
def get_api_documentation(query: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """
    Retrieve API documentation

    Args:
        query: Query text
        n_results: Number of results to return

    Returns:
        API document list
    """
    vector_store = get_vector_store()
    return vector_store.get_api_documentation(query, n_results)


@tool
def get_prd_context(query: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """
    Get PRD context

    Args:
        query: Query text
        n_results: Number of results to return

    Returns:
        PRD document list
    """
    vector_store = get_vector_store()
    return vector_store.get_prd_context(query, n_results)


@tool
def get_similar_test_plans(scenario: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """
    Get similar test plans

    Args:
        scenario: Test scenario
        n_results: Number of results to return

    Returns:
        List of similar test plans
    """
    vector_store = get_vector_store()
    return vector_store.get_similar_test_plans(scenario, n_results)


# Tool list
KNOWLEDGE_TOOLS = [
    store_document,
    search_similar_bugs,
    get_api_documentation,
    get_prd_context,
    get_similar_test_plans,
]
