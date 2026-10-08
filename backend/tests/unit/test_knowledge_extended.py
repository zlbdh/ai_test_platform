"""
Extended knowledge unit tests.
Covers embedding initialization success/failure and enabled ingest/add/query/list/
delete/clear/get_status operations.
"""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, mock_open, patch

from services.knowledge import KnowledgeBase


class _FakeEmbeddings:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    def embed_query(self, query):
        return [0.1] * 16


class _FakeBadEmbeddings(_FakeEmbeddings):
    def embed_query(self, query):
        return [0.1]


class _FakeChroma:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs


class TestEmbeddingInitialization:
    def test_try_openai_embeddings_success(self):
        kb = KnowledgeBase()
        fake_openai_module = SimpleNamespace(OpenAIEmbeddings=_FakeEmbeddings)
        fake_chroma_module = SimpleNamespace(Chroma=_FakeChroma)
        fake_settings = SimpleNamespace(
            OPENAI_API_KEY="key",
            OPENAI_BASE_URL="https://api.example.com",
            CHROMA_PATH="D:/tmp/chroma",
            EMBEDDING_MODEL="text-embedding-3-small",
        )

        with patch.dict(sys.modules, {
            "langchain_openai": fake_openai_module,
            "langchain_chroma": fake_chroma_module,
        }), patch("services.knowledge.settings", fake_settings), \
             patch("os.makedirs") as mock_makedirs:
            assert kb._try_openai_embeddings() is True

        assert kb.enabled is True
        assert kb.embedding_type == "openai"
        assert isinstance(kb.embeddings, _FakeEmbeddings)
        assert isinstance(kb.vector_store, _FakeChroma)
        mock_makedirs.assert_called_once_with("D:/tmp/chroma", exist_ok=True)

    def test_try_openai_embeddings_invalid_result_returns_false(self):
        kb = KnowledgeBase()
        fake_openai_module = SimpleNamespace(OpenAIEmbeddings=_FakeBadEmbeddings)
        fake_chroma_module = SimpleNamespace(Chroma=_FakeChroma)

        with patch.dict(sys.modules, {
            "langchain_openai": fake_openai_module,
            "langchain_chroma": fake_chroma_module,
        }):
            assert kb._try_openai_embeddings() is False

    def test_try_huggingface_embeddings_success(self):
        kb = KnowledgeBase()
        fake_hf_module = SimpleNamespace(HuggingFaceEmbeddings=_FakeEmbeddings)
        fake_chroma_module = SimpleNamespace(Chroma=_FakeChroma)
        fake_settings = SimpleNamespace(CHROMA_PATH="D:/tmp/chroma")

        with patch.dict(sys.modules, {
            "langchain_huggingface": fake_hf_module,
            "langchain_chroma": fake_chroma_module,
        }), patch("services.knowledge.settings", fake_settings), \
             patch("os.makedirs"):
            assert kb._try_huggingface_embeddings() is True

        assert kb.enabled is True
        assert kb.embedding_type == "huggingface"

    def test_try_huggingface_import_error_returns_false(self):
        kb = KnowledgeBase()
        original_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "langchain_huggingface":
                raise ImportError("missing")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            assert kb._try_huggingface_embeddings() is False


class TestEnabledOperations:
    def _make_enabled_kb(self):
        kb = KnowledgeBase()
        kb.initialized = True
        kb.enabled = True
        kb.vector_store = MagicMock()
        kb.vector_store._collection = MagicMock()
        return kb

    def test_ingest_file_uses_parser_and_does_not_mutate_metadata(self, tmp_path):
        kb = self._make_enabled_kb()
        file_path = tmp_path / "spec.md"
        file_path.write_text("# title", encoding="utf-8")
        metadata = {"team": "qa"}

        with patch.object(kb, "initialize"), \
             patch("services.knowledge.DocumentParser.parse_markdown", return_value=[
                 {"content": "chunk-1", "metadata": {"section": "intro"}}
             ]) as mock_parser:
            result = kb.ingest_file(str(file_path), metadata)

        assert result is True
        mock_parser.assert_called_once()
        docs = kb.vector_store.add_documents.call_args[0][0]
        assert docs[0].page_content == "chunk-1"
        assert docs[0].metadata["team"] == "qa"
        assert docs[0].metadata["filename"] == "spec.md"
        assert metadata == {"team": "qa"}

    def test_ingest_file_routes_json_openapi_and_plain_text(self, tmp_path):
        kb = self._make_enabled_kb()
        openapi_path = tmp_path / "openapi.json"
        plain_json_path = tmp_path / "sample.json"
        openapi_path.write_text('{"openapi":"3.0.0"}', encoding="utf-8")
        plain_json_path.write_text('{"name":"demo"}', encoding="utf-8")

        with patch.object(kb, "initialize"), \
             patch("services.knowledge.DocumentParser.parse_openapi", return_value=[
                 {"content": "api", "metadata": {}}
             ]) as mock_openapi, \
             patch("services.knowledge.DocumentParser.parse_text", return_value=[
                 {"content": "text", "metadata": {}}
             ]) as mock_text:
            assert kb.ingest_file(str(openapi_path)) is True
            assert kb.ingest_file(str(plain_json_path)) is True

        mock_openapi.assert_called_once()
        assert mock_text.call_count == 1

    def test_ingest_file_returns_false_for_empty_parsed_docs(self, tmp_path):
        kb = self._make_enabled_kb()
        file_path = tmp_path / "demo.txt"
        file_path.write_text("demo", encoding="utf-8")

        with patch.object(kb, "initialize"), \
             patch("services.knowledge.DocumentParser.parse_text", return_value=[]):
            assert kb.ingest_file(str(file_path)) is False

    def test_add_query_list_delete_clear_and_status(self):
        kb = self._make_enabled_kb()
        kb.vector_store.similarity_search.return_value = [
            SimpleNamespace(page_content="doc-1"),
            SimpleNamespace(page_content="doc-2"),
        ]
        kb.vector_store._collection.get.side_effect = [
            {
                "ids": ["1", "2"],
                "documents": ["A", "B"],
                "metadatas": [{"k": 1}, {"k": 2}],
            },
            {"ids": ["1", "2"]},
        ]
        kb.vector_store._collection.count.return_value = 2

        with patch.object(kb, "initialize"):
            assert kb.add_knowledge("hello", {"source": "manual"}) is True
            docs = kb.vector_store.add_documents.call_args[0][0]
            assert docs[0].page_content == "hello"
            assert docs[0].metadata["source"] == "manual"

            assert kb.query_knowledge("hello", k=2) == ["doc-1", "doc-2"]
            assert kb.list_knowledge() == [
                {"id": "1", "content": "A", "metadata": {"k": 1}},
                {"id": "2", "content": "B", "metadata": {"k": 2}},
            ]
            assert kb.delete_knowledge("1") is True
            kb.vector_store._collection.delete.assert_any_call(ids=["1"])
            assert kb.clear_knowledge() is True
            assert kb.get_status() == {
                "enabled": True,
                "embedding_type": "none",
                "document_count": 2,
            }

    def test_get_knowledge_item_returns_single_document(self):
        kb = self._make_enabled_kb()
        kb.vector_store._collection.get.return_value = {
            "ids": ["doc-1"],
            "documents": ["hello world"],
            "metadatas": [{"filename": "demo.md"}],
        }

        with patch.object(kb, "initialize"):
            assert kb.get_knowledge_item("doc-1") == {
                "id": "doc-1",
                "content": "hello world",
                "metadata": {"filename": "demo.md"},
            }

    def test_add_knowledge_defaults_source_and_handles_exceptions(self):
        kb = self._make_enabled_kb()
        kb.vector_store.add_documents.side_effect = RuntimeError("boom")

        with patch.object(kb, "initialize"):
            assert kb.add_knowledge("hello") is False

    def test_query_list_delete_clear_handle_exceptions(self):
        kb = self._make_enabled_kb()
        kb.vector_store.similarity_search.side_effect = RuntimeError("query boom")
        kb.vector_store._collection.get.side_effect = RuntimeError("list boom")
        kb.vector_store._collection.delete.side_effect = RuntimeError("delete boom")

        with patch.object(kb, "initialize"):
            assert kb.query_knowledge("x") == []
            assert kb.list_knowledge() == []
            assert kb.get_knowledge_item("1") is None
            assert kb.delete_knowledge("1") is False
            assert kb.clear_knowledge() is False
