"""
RAG 知识库服务 - 支持多嵌入模型
优先级: OpenAI 兼容 API -> 本地 HuggingFace -> 禁用
"""
import logging
import os
from typing import List, Optional, Dict, Any
from langchain_core.documents import Document
from core.config import Config as settings
from core.parsers import DocumentParser

logger = logging.getLogger(__name__)

class KnowledgeBase:
    _instance = None

    def __init__(self):
        self.enabled = False
        self.vector_store = None
        self.embeddings = None
        self.initialized = False
        self.embedding_type = "none"  # "openai", "huggingface", "none"

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = KnowledgeBase()
        return cls._instance

    def initialize(self):
        """Lazy init - 尝试多种嵌入模型"""
        if self.initialized:
            return
        
        # 检查是否显式禁用
        if not getattr(settings, 'ENABLE_RAG', True):
            logger.info("RAG 已通过配置禁用")
            self.initialized = True
            return
        
        # 策略 1: OpenAI 兼容 API (通过网关)
        if self._try_openai_embeddings():
            self.initialized = True
            return
            
        # 策略 2: 本地 HuggingFace sentence-transformers
        if self._try_huggingface_embeddings():
            self.initialized = True
            return
            
        # 所有策略都失败
        logger.warning("RAG 知识库已禁用: 无可用的嵌入模型")
        self.initialized = True

    def _try_openai_embeddings(self) -> bool:
        """尝试使用 OpenAI 兼容的嵌入 API"""
        try:
            from langchain_openai import OpenAIEmbeddings
            from langchain_chroma import Chroma
            
            # 获取嵌入模型名称
            embedding_model = getattr(settings, 'EMBEDDING_MODEL', 'text-embedding-3-small')
            
            logger.info(f"尝试 OpenAI 兼容嵌入模型: {embedding_model}...")
            
            self.embeddings = OpenAIEmbeddings(
                model=embedding_model,
                api_key=settings.OPENAI_API_KEY,
                openai_api_base=settings.OPENAI_BASE_URL,
                timeout=3
            )
            
            # 测试嵌入是否工作
            test_result = self.embeddings.embed_query("test")
            if not test_result or len(test_result) < 10:
                raise ValueError("嵌入结果无效")
            
            # 初始化向量存储
            os.makedirs(settings.CHROMA_PATH, exist_ok=True)
            self.vector_store = Chroma(
                persist_directory=settings.CHROMA_PATH,
                embedding_function=self.embeddings,
                collection_name="test_knowledge",
            )
            
            self.enabled = True
            self.embedding_type = "openai"
            logger.info(f"RAG 已启用 (OpenAI 兼容模式: {embedding_model})")
            return True
            
        except Exception as e:
            logger.error(f"OpenAI 嵌入初始化失败: {e}")
            return False

    def _try_huggingface_embeddings(self) -> bool:
        """尝试使用本地 HuggingFace 嵌入模型"""
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            from langchain_chroma import Chroma
            
            # 使用小型中文/多语言模型
            model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            logger.info(f"尝试本地 HuggingFace 嵌入模型: {model_name}...")
            
            self.embeddings = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
            
            # 测试
            test_result = self.embeddings.embed_query("测试")
            if not test_result or len(test_result) < 10:
                raise ValueError("嵌入结果无效")
            
            # 初始化向量存储
            os.makedirs(settings.CHROMA_PATH, exist_ok=True)
            self.vector_store = Chroma(
                persist_directory=settings.CHROMA_PATH,
                embedding_function=self.embeddings,
                collection_name="test_knowledge",
            )
            
            self.enabled = True
            self.embedding_type = "huggingface"
            logger.info("RAG 已启用 (HuggingFace 本地模式)")
            return True
            
        except ImportError:
            logger.warning("langchain-huggingface 未安装，跳过本地嵌入")
            return False
        except Exception as e:
            logger.error(f"HuggingFace 嵌入初始化失败: {e}")
            return False

    def ingest_file(self, file_path: str, metadata: Optional[Dict] = None) -> bool:
        """从文件摄入知识 (支持 .md, .sql, .txt)"""
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return False
            
        self.initialize()
        if not self.enabled:
            return False
            
        try:
            # 读取文件内容
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            filename = os.path.basename(file_path)
            file_ext = os.path.splitext(filename)[1].lower()
            
            meta_base = dict(metadata or {})
            meta_base["filename"] = filename
            meta_base["source_path"] = file_path
            
            parsed_docs = []
            
            # 根据后缀选择解析策略
            if file_ext == ".md":
                parsed_docs = DocumentParser.parse_markdown(content, source_name=filename)
            elif file_ext == ".sql":
                parsed_docs = DocumentParser.parse_sql(content, source_name=filename)
            elif file_ext == ".json":
                # 简单判断是否是 OpenAPI (检查 "openapi" 或 "swagger" 关键字)
                if '"openapi"' in content or '"swagger"' in content:
                    parsed_docs = DocumentParser.parse_openapi(content, source_name=filename)
                else:
                    parsed_docs = DocumentParser.parse_text(content, source_name=filename)
            else:
                parsed_docs = DocumentParser.parse_text(content, source_name=filename)
                
            if not parsed_docs:
                logger.warning(f"文件解析为空: {filename}")
                return False
                
            # 批量转换为 LangChain Document 对象
            lc_docs = []
            for d in parsed_docs:
                # 合并元数据
                final_meta = {**meta_base, **d["metadata"]}
                lc_docs.append(Document(page_content=d["content"], metadata=final_meta))
                
            # 批量写入向量库
            self.vector_store.add_documents(lc_docs)
            logger.info(f"成功摄入文件: {filename} ({len(lc_docs)} chunks)")
            return True
            
        except Exception as e:
            logger.error(f"摄入文件失败 {file_path}: {e}")
            return False

    def add_knowledge(self, text: str, metadata: Optional[Dict] = None) -> bool:
        """添加知识条目"""
        self.initialize()
        if not self.enabled:
            return False
        try:
            meta = dict(metadata or {})
            meta.setdefault("source", "user_input")
            doc = Document(page_content=text, metadata=meta)
            self.vector_store.add_documents([doc])
            logger.info(f"知识已添加: {text[:50]}...")
            return True
        except Exception as e:
            logger.error(f"添加知识失败: {e}")
            return False

    def query_knowledge(self, query: str, k: int = 3) -> List[str]:
        """查询相关知识"""
        self.initialize()
        if not self.enabled:
            return []
        try:
            docs = self.vector_store.similarity_search(query, k=k)
            return [d.page_content for d in docs]
        except Exception as e:
            logger.error(f"查询知识失败: {e}")
            return []

    def list_knowledge(self, limit: int = 100) -> List[Dict[str, Any]]:
        """列出所有知识条目"""
        self.initialize()
        if not self.enabled:
            return []
        try:
            # Chroma 的 get() 方法获取所有文档
            collection = self.vector_store._collection
            results = collection.get(limit=limit, include=["documents", "metadatas"])
            
            items = []
            ids = results.get("ids", [])
            docs = results.get("documents", [])
            metas = results.get("metadatas", [])
            
            for i, doc_id in enumerate(ids):
                items.append({
                    "id": doc_id,
                    "content": docs[i] if i < len(docs) else "",
                    "metadata": metas[i] if i < len(metas) else {}
                })
            return items
        except Exception as e:
            logger.error(f"列出知识失败: {e}")
            return []

    def get_knowledge_item(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """获取单条知识内容"""
        self.initialize()
        if not self.enabled:
            return None
        try:
            collection = self.vector_store._collection
            results = collection.get(ids=[doc_id], include=["documents", "metadatas"])
            ids = results.get("ids", [])
            if not ids:
                return None
            docs = results.get("documents", [])
            metas = results.get("metadatas", [])
            return {
                "id": ids[0],
                "content": docs[0] if docs else "",
                "metadata": metas[0] if metas else {},
            }
        except Exception as e:
            logger.error(f"获取知识失败 {doc_id}: {e}")
            return None

    def delete_knowledge(self, doc_id: str) -> bool:
        """删除指定知识条目"""
        self.initialize()
        if not self.enabled:
            return False
        try:
            collection = self.vector_store._collection
            collection.delete(ids=[doc_id])
            logger.info(f"知识已删除: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"删除知识失败: {e}")
            return False

    def clear_knowledge(self) -> bool:
        """清空所有知识"""
        self.initialize()
        if not self.enabled:
            return False
        try:
            # 获取所有 ID 并删除
            collection = self.vector_store._collection
            results = collection.get()
            ids = results.get("ids", [])
            if ids:
                collection.delete(ids=ids)
            logger.info(f"已清空 {len(ids)} 条知识")
            return True
        except Exception as e:
            logger.error(f"清空知识失败: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """获取知识库状态"""
        self.initialize()
        count = 0
        if self.enabled:
            try:
                collection = self.vector_store._collection
                count = collection.count()
            except Exception:
                pass
        return {
            "enabled": self.enabled,
            "embedding_type": self.embedding_type,
            "document_count": count
        }

# 单例实例
kb = KnowledgeBase()
