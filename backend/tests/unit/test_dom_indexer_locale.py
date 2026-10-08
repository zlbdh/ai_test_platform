import pytest

from core.dom_indexer import DomIndexer


@pytest.mark.parametrize("description, tag", [
    ("input field", "input"),
    ("输入框", "input"),
    ("click button", "button"),
    ("点击按钮", "button"),
    ("navigation link", "a"),
    ("链接", "a"),
    ("select dropdown", "select"),
    ("下拉框", "select"),
    ("comment box", "textarea"),
    ("评论框", "textarea"),
])
def test_semantic_role_fallback_accepts_english_and_legacy_descriptions(description, tag):
    indexer = DomIndexer()
    expected = {"tag": tag, "text": "XYZ", "_all_text": "xyz", "selector": "#target"}
    indexer._index_map = {1: expected}
    assert indexer.find_by_text(description) == expected


@pytest.mark.parametrize("description", ["search field", "搜索框"])
def test_search_role_prefers_search_control_over_larger_input(description):
    indexer = DomIndexer()
    generic = {"tag": "input", "_all_text": "", "selector": "#other", "rect": {"w": 500, "h": 100}}
    search = {"tag": "input", "_all_text": "", "selector": "#query", "rect": {"w": 100, "h": 20}}
    indexer._index_map = {1: generic, 2: search}
    assert indexer.find_by_text(description) == search
