import pytest
from core.snapshot_compressor import SnapshotCompressor

def test_snapshot_compression():
    compressor = SnapshotCompressor()
    
    elements_text = """[1] input "search" (focused)
[2] button "submit"
[3] link "home" """
    
    page_state = {
        "url": "https://example.com/search",
        "title": "Search Page",
        "scroll_info": {"percent": 45, "at_top": False, "at_bottom": False},
        "alerts": ["Login failed", "Please try again"],
        "visible_text": "Welcome to the site. Please login."
    }
    
    # Compress a snapshot that contains elements.
    snapshot = compressor.compress(elements_text, page_state, max_visible_text=100)
    
    assert "URL: https://example.com/search | Search Page" in snapshot
    assert "[2] button \"submit\"" in snapshot
    assert "Scroll: 45%" in snapshot
    assert "Alerts: 2" in snapshot
    assert "⚠ Login failed" in snapshot
    assert "Text:" not in snapshot  # Hide the text summary when elements are present.
    
    # Estimate token usage.
    tokens = compressor.estimate_tokens(snapshot)
    assert tokens > 10 and tokens < 100

def test_snapshot_no_elements():
    compressor = SnapshotCompressor()
    
    page_state = {
        "url": "https://example.com/about",
        "title": "About Us",
        "visible_text": "This is a very long text " * 20
    }
    
    snapshot = compressor.compress("", page_state, max_visible_text=50)
    assert "(Page not loaded or no interactive elements)" in snapshot
    assert "Text: This is a very long text This is a very l" in snapshot
    assert "Scroll: 0%" in snapshot

def test_snapshot_compressor_empty_state():
    compressor = SnapshotCompressor()
    snapshot = compressor.compress("", {})
    assert "URL: (Unknown)" in snapshot
    assert "Scroll: 0%" in snapshot


@pytest.mark.parametrize("sentinel", ["(Page not loaded)", "（页面未加载）"])
def test_snapshot_accepts_english_and_legacy_empty_page_sentinels(sentinel):
    snapshot = SnapshotCompressor().compress(sentinel, {"visible_text": "Loading content"})
    assert "(Page not loaded or no interactive elements)" in snapshot
    assert "Text: Loading content" in snapshot
    assert sentinel not in snapshot
