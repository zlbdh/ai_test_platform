"""
RAG knowledge service with multiple embedding models
Priority: OpenAI-compatible API -> local HuggingFace -> disabled
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
        """Lazy initialization: try multiple embedding models"""
        if self.initialized:
            return
        
        # Check whether explicitly disabled
        if not getattr(settings, 'ENABLE_RAG', True):
            logger.info("RAG is disabled by configuration")
            self.initialized = True
            return
        
        # Strategy 1: OpenAI-compatible API through the gateway
        if self._try_openai_embeddings():
            self.initialized = True
            return
            
        # Strategy 2: local HuggingFace sentence-transformers
        if self._try_huggingface_embeddings():
            self.initialized = True
            return
            
        # All strategies failed
        logger.warning("RAG knowledge service disabled: no embedding model is available")
        self.initialized = True

    def _try_openai_embeddings(self) -> bool:
        """Try an OpenAI-compatible embedding API"""
        try:
            from langchain_openai import OpenAIEmbeddings
            from langchain_chroma import Chroma
            
            # Get the embedding model name
            embedding_model = getattr(settings, 'EMBEDDING_MODEL', 'text-embedding-3-small')
            
            logger.info(f"Trying OpenAI-compatible embedding model: {embedding_model}...")
            
            self.embeddings = OpenAIEmbeddings(
                model=embedding_model,
                api_key=settings.OPENAI_API_KEY,
                openai_api_base=settings.OPENAI_BASE_URL,
                timeout=3
            )
            
            # Test whether embeddings work
            test_result = self.embeddings.embed_query("test")
            if not test_result or len(test_result) < 10:
                raise ValueError("Invalid embedding result")
            
            # Initialize the vector store
            os.makedirs(settings.CHROMA_PATH, exist_ok=True)
            self.vector_store = Chroma(
                persist_directory=settings.CHROMA_PATH,
                embedding_function=self.embeddings,
                collection_name="test_knowledge",
            )
            
            self.enabled = True
            self.embedding_type = "openai"
            logger.info(f"RAG enabled (OpenAI-compatible mode: {embedding_model})")
            return True
            
        except Exception as e:
            logger.error(f"OpenAI embedding initialization failed: {e}")
            return False

    def _try_huggingface_embeddings(self) -> bool:
        """Try a local HuggingFace embedding model"""
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            from langchain_chroma import Chroma
            
            # Use a compact multilingual model
            model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            logger.info(f"Trying local HuggingFace embedding model: {model_name}...")
            
            self.embeddings = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
            
            # Test
            test_result = self.embeddings.embed_query("Test")
            if not test_result or len(test_result) < 10:
                raise ValueError("Invalid embedding result")
            
            # Initialize the vector store
            os.makedirs(settings.CHROMA_PATH, exist_ok=True)
            self.vector_store = Chroma(
                persist_directory=settings.CHROMA_PATH,
                embedding_function=self.embeddings,
                collection_name="test_knowledge",
            )
            
            self.enabled = True
            self.embedding_type = "huggingface"
            logger.info("RAG enabled (local HuggingFace mode)")
            return True
            
        except ImportError:
            logger.warning("langchain-huggingface is not installed; skipping local embeddings")
            return False
        except Exception as e:
            logger.error(f"HuggingFace embedding initialization failed: {e}")
            return False

    def ingest_file(self, file_path: str, metadata: Optional[Dict] = None) -> bool:
        """Ingest knowledge from a file (.md, .sql, or .txt)"""
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False
            
        self.initialize()
        if not self.enabled:
            return False
            
        try:
            # Read file contents
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            filename = os.path.basename(file_path)
            file_ext = os.path.splitext(filename)[1].lower()
            
            meta_base = dict(metadata or {})
            meta_base["filename"] = filename
            meta_base["source_path"] = file_path
            
            parsed_docs = []
            
            # Choose a parsing strategy by extension
            if file_ext == ".md":
                parsed_docs = DocumentParser.parse_markdown(content, source_name=filename)
            elif file_ext == ".sql":
                parsed_docs = DocumentParser.parse_sql(content, source_name=filename)
            elif file_ext == ".json":
                # Detect OpenAPI by checking for "openapi" or "swagger"
                if '"openapi"' in content or '"swagger"' in content:
                    parsed_docs = DocumentParser.parse_openapi(content, source_name=filename)
                else:
                    parsed_docs = DocumentParser.parse_text(content, source_name=filename)
            else:
                parsed_docs = DocumentParser.parse_text(content, source_name=filename)
                
            if not parsed_docs:
                logger.warning(f"File parsing produced no content: {filename}")
                return False
                
            # Convert the batch into LangChain Document objects
            lc_docs = []
            for d in parsed_docs:
                # Merge metadata
                final_meta = {**meta_base, **d["metadata"]}
                lc_docs.append(Document(page_content=d["content"], metadata=final_meta))
                
            # Write the batch to the vector store
            self.vector_store.add_documents(lc_docs)
            logger.info(f"File ingested successfully: {filename} ({len(lc_docs)} chunks)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to ingest file {file_path}: {e}")
            return False

    def add_knowledge(self, text: str, metadata: Optional[Dict] = None) -> bool:
        """Add a knowledge entry"""
        self.initialize()
        if not self.enabled:
            return False
        try:
            meta = dict(metadata or {})
            meta.setdefault("source", "user_input")
            doc = Document(page_content=text, metadata=meta)
            self.vector_store.add_documents([doc])
            logger.info(f"Knowledge added: {text[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to add knowledge: {e}")
            return False

    def query_knowledge(self, query: str, k: int = 3) -> List[str]:
        """Query relevant knowledge"""
        self.initialize()
        if not self.enabled:
            return []
        try:
            docs = self.vector_store.similarity_search(query, k=k)
            return [d.page_content for d in docs]
        except Exception as e:
            logger.error(f"Knowledge query failed: {e}")
            return []

    def list_knowledge(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List all knowledge entries"""
        self.initialize()
        if not self.enabled:
            return []
        try:
            # Chroma get() retrieves all documents
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
            logger.error(f"Failed to list knowledge: {e}")
            return []

    def get_knowledge_item(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get one knowledge entry"""
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
            logger.error(f"Failed to get knowledge {doc_id}: {e}")
            return None

    def delete_knowledge(self, doc_id: str) -> bool:
        """Delete a knowledge entry"""
        self.initialize()
        if not self.enabled:
            return False
        try:
            collection = self.vector_store._collection
            collection.delete(ids=[doc_id])
            logger.info(f"Knowledge deleted: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete knowledge: {e}")
            return False

    def clear_knowledge(self) -> bool:
        """Clear all knowledge"""
        self.initialize()
        if not self.enabled:
            return False
        try:
            # Get all IDs and delete them
            collection = self.vector_store._collection
            results = collection.get()
            ids = results.get("ids", [])
            if ids:
                collection.delete(ids=ids)
            logger.info(f"Cleared {len(ids)} knowledge entries")
            return True
        except Exception as e:
            logger.error(f"Failed to clear knowledge: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get knowledge service status"""
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

# Singleton instance
kb = KnowledgeBase()
