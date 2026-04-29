"""
Vector DB 集成 - RAG 知识库
使用 ChromaDB 存储历史 Bug、PRD 文档、API 规范
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
    """Vector DB 管理器"""
    
    def __init__(self):
        """初始化 Vector Store"""
        self.persist_directory = Config.VECTOR_DB_PATH if hasattr(Config, 'VECTOR_DB_PATH') else "./vector_db"
        
        # 初始化嵌入模型（使用 LLM Manager）
        self.embeddings = LLMManager.get_embeddings()
        
        # 初始化 ChromaDB 客户端
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # 创建集合
        self.collections = {
            "bugs": self._get_or_create_collection("bugs", "历史 Bug 记录"),
            "prd": self._get_or_create_collection("prd", "PRD 文档"),
            "api_docs": self._get_or_create_collection("api_docs", "API 文档"),
            "test_plans": self._get_or_create_collection("test_plans", "历史测试计划")
        }
        
        # 文本分割器
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
    
    def _get_or_create_collection(self, name: str, description: str):
        """获取或创建集合"""
        try:
            return self.client.get_collection(name=name)
        except Exception:
            return self.client.create_collection(
                name=name,
                metadata={"description": description}
            )
    
    def store_document(self, collection_name: str, content: str, metadata: Dict[str, Any] = None) -> str:
        """
        存储文档到 Vector DB
        
        Args:
            collection_name: 集合名称 (bugs, prd, api_docs, test_plans)
            content: 文档内容
            metadata: 元数据
            
        Returns:
            文档 ID
        """
        if collection_name not in self.collections:
            raise ValueError(f"未知的集合名称: {collection_name}")
        
        collection = self.collections[collection_name]
        metadata = metadata or {}
        
        # 分割文档
        documents = self.text_splitter.split_text(content)
        
        # 存储每个分块
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
        搜索相似文档
        
        Args:
            collection_name: 集合名称
            query: 查询文本
            n_results: 返回结果数量
            
        Returns:
            相似文档列表
        """
        if collection_name not in self.collections:
            raise ValueError(f"未知的集合名称: {collection_name}")
        
        collection = self.collections[collection_name]
        
        # 使用 ChromaDB 的查询功能
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        # 格式化结果
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
        """搜索相似的历史 Bug"""
        return self.search("bugs", error_message, n_results)
    
    def get_api_documentation(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """检索 API 文档"""
        return self.search("api_docs", query, n_results)
    
    def get_prd_context(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """获取 PRD 上下文"""
        return self.search("prd", query, n_results)
    
    def get_similar_test_plans(self, scenario: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """获取相似的测试计划"""
        return self.search("test_plans", scenario, n_results)
    
    def delete_collection(self, collection_name: str):
        """删除集合"""
        if collection_name in self.collections:
            self.client.delete_collection(name=collection_name)
            del self.collections[collection_name]


# 全局实例
_vector_store = None

def get_vector_store() -> VectorStore:
    """获取 Vector Store 单例"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
