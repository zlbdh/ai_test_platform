"""
KnowledgeBase unit tests.
Covers disabled initialization, safe add/query/ingest returns while disabled,
get_status, and get_instance. Heavy dependencies such as langchain, Chroma, and
OpenAI are all mocked.
"""
import pytest
from unittest.mock import patch, MagicMock

from services.knowledge import KnowledgeBase


# ---------------------------------------------------------------------------
# Basic status.
# ---------------------------------------------------------------------------
class TestKnowledgeBaseInit:
    def test_defaults(self):
        kb = KnowledgeBase()
        assert kb.enabled is False
        assert kb.initialized is False
        assert kb.embedding_type == "none"


# ---------------------------------------------------------------------------
# initialize with RAG disabled.
# ---------------------------------------------------------------------------
class TestInitializeDisabled:
    def test_rag_disabled_by_config(self):
        kb = KnowledgeBase()
        mock_config = MagicMock()
        mock_config.ENABLE_RAG = False
        with patch("services.knowledge.settings", mock_config):
            kb.initialize()
        assert kb.initialized is True
        assert kb.enabled is False

    def test_already_initialized(self):
        kb = KnowledgeBase()
        kb.initialized = True
        kb.initialize()  # Do not initialize again.
        assert kb.initialized is True


# ---------------------------------------------------------------------------
# initialize when every embedding strategy fails.
# ---------------------------------------------------------------------------
class TestInitializeAllFail:
    def test_all_strategies_fail(self):
        kb = KnowledgeBase()
        with patch.object(kb, "_try_openai_embeddings", return_value=False), \
             patch.object(kb, "_try_huggingface_embeddings", return_value=False):
            with patch("services.knowledge.settings") as mock_cfg:
                mock_cfg.ENABLE_RAG = True
                kb.initialize()
        assert kb.initialized is True
        assert kb.enabled is False


# ---------------------------------------------------------------------------
# Methods should return safely while disabled.
# ---------------------------------------------------------------------------
class TestDisabledOperations:
    @pytest.fixture
    def kb_disabled(self):
        kb = KnowledgeBase()
        kb.initialized = True
        kb.enabled = False
        return kb

    def test_add_knowledge(self, kb_disabled):
        assert kb_disabled.add_knowledge("test text") is False

    def test_query_knowledge(self, kb_disabled):
        assert kb_disabled.query_knowledge("test") == []

    def test_ingest_file_not_exists(self):
        kb = KnowledgeBase()
        kb.initialized = True
        kb.enabled = False
        with patch("os.path.exists", return_value=False):
            assert kb.ingest_file("/nonexistent.txt") is False

    def test_list_knowledge(self, kb_disabled):
        assert kb_disabled.list_knowledge() == []

    def test_delete_knowledge(self, kb_disabled):
        assert kb_disabled.delete_knowledge("doc-1") is False

    def test_clear_knowledge(self, kb_disabled):
        assert kb_disabled.clear_knowledge() is False


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------
class TestGetStatus:
    def test_disabled(self):
        kb = KnowledgeBase()
        kb.initialized = True
        status = kb.get_status()
        assert status["enabled"] is False
        assert status["embedding_type"] == "none"
        assert status["document_count"] == 0


# ---------------------------------------------------------------------------
# get_instance singleton.
# ---------------------------------------------------------------------------
class TestSingleton:
    def test_same_instance(self):
        KnowledgeBase._instance = None
        k1 = KnowledgeBase.get_instance()
        k2 = KnowledgeBase.get_instance()
        assert k1 is k2
        KnowledgeBase._instance = None
