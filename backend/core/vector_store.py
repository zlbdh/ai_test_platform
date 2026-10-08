"""
Vector database integration - RAG knowledge base
Use ChromaDB to store prior bugs, PRD documents, and API specifications
"""
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from langchain_community.embeddings import FakeEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from core.llm_manager import LLMManager
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from core.config import Config


class VectorStore:
    """Vector database manager"""

    def __init__(self):
        """Initialize the vector store"""
        self.persist_directory = Config.VECTOR_DB_PATH if hasattr(Config, 'VECTOR_DB_PATH') else "./vector_db"

        # Initialize the embedding model through LLM Manager
        self.embeddings = LLMManager.get_embeddings()

        # Initialize the ChromaDB client
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )

        # Create collections
        self.collections = {
            "bugs": self._get_or_create_collection("bugs", "Historical bug records"),
            "prd": self._get_or_create_collection("prd", "PRD documents"),
            "api_docs": self._get_or_create_collection("api_docs", "API documentation"),
            "test_plans": self._get_or_create_collection("test_plans", "Previous test plans")
        }

        # Text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )

    def _get_or_create_collection(self, name: str, description: str):
        """Get or create a collection"""
        try:
            return self.client.get_collection(name=name)
        except Exception:
            return self.client.create_collection(
                name=name,
                metadata={"description": description}
            )

    def store_document(self, collection_name: str, content: str, metadata: Dict[str, Any] = None) -> str:
        """
        Store a document in the vector database

        Args:
            collection_name: Collection name (bugs, prd, api_docs, test_plans)
            content: Document content
            metadata: Metadata

        Returns:
            Document ID
        """
        if collection_name not in self.collections:
            raise ValueError(f"Unknown collection name: {collection_name}")

        collection = self.collections[collection_name]
        metadata = metadata or {}

        # Split the document
        documents = self.text_splitter.split_text(content)

        # Store each chunk
        ids = []
        for i, doc in enumerate(documents):
            doc_id = f"{collection_name}_{len(collection.get()['ids'])}"
            collection.add(
                documents=[doc],
                ids=[doc_id],
                metadatas=[{**metadata, "chunk_index": i}]
            )
            ids.append(doc_id)

        return ",".join(ids)

    def search(self, collection_name: str, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar documents

        Args:
            collection_name: Collection name
            query: Query text
            n_results: Number of results to return

        Returns:
            List of similar documents
        """
        if collection_name not in self.collections:
            raise ValueError(f"Unknown collection name: {collection_name}")

        collection = self.collections[collection_name]

        # Use ChromaDB queries
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )

        # Format results
        formatted_results = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    "id": results['ids'][0][i],
                    "content": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i] if 'distances' in results else None
                })

        return formatted_results

    def search_similar_bugs(self, error_message: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Search for similar historical bugs"""
        return self.search("bugs", error_message, n_results)

    def get_api_documentation(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Retrieve API documentation"""
        return self.search("api_docs", query, n_results)

    def get_prd_context(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Get PRD context"""
        return self.search("prd", query, n_results)

    def get_similar_test_plans(self, scenario: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Get similar test plans"""
        return self.search("test_plans", scenario, n_results)

    def delete_collection(self, collection_name: str):
        """Delete a collection"""
        if collection_name in self.collections:
            self.client.delete_collection(name=collection_name)
            del self.collections[collection_name]


# Global instance
_vector_store = None

def get_vector_store() -> VectorStore:
    """Get the vector-store singleton"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
