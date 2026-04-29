"""
KnowledgeBase 单元测试
覆盖: 初始化(disabled), add/query/ingest 在 disabled 时返回 False/[],
      get_status, 单例(get_instance)
注: 不依赖 langchain/chroma/openai 等重库，全部 mock
"""
import pytest
from unittest.mock import patch, MagicMock

from services.knowledge import KnowledgeBase


# ---------------------------------------------------------------------------
# 基础状态
# ---------------------------------------------------------------------------
class TestKnowledgeBaseInit:
    def test_defaults(self):
        kb = KnowledgeBase()
        assert kb.enabled is False
        assert kb.initialized is False
        assert kb.embedding_type == "none"


# ---------------------------------------------------------------------------
# initialize — RAG 禁用
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
        kb.initialize()  # 不应重新执行
        assert kb.initialized is True


# ---------------------------------------------------------------------------
# initialize — 所有嵌入策略失败
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
# disabled 状态下各方法应安全返回
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
# 单例 (get_instance)
# ---------------------------------------------------------------------------
class TestSingleton:
    def test_same_instance(self):
        KnowledgeBase._instance = None
        k1 = KnowledgeBase.get_instance()
        k2 = KnowledgeBase.get_instance()
        assert k1 is k2
        KnowledgeBase._instance = None
