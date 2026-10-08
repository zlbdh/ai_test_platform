import pytest
import shutil
from pathlib import Path
from core.cookie_manager import CookieManager, COOKIE_DIR, PRESETS_FILE

@pytest.fixture
def mock_cookie_manager():
    # Use an isolated test directory.
    test_dir = Path(__file__).parent / "_test_cookies"
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True)
    
    # Temporarily override the value.
    cm = CookieManager()
    
    # Replace the global directory for testing.
    import core.cookie_manager as cm_module
    old_dir = cm_module.COOKIE_DIR
    old_presets = cm_module.PRESETS_FILE
    
    cm_module.COOKIE_DIR = test_dir
    cm_module.PRESETS_FILE = test_dir / "_presets.json"
    
    yield cm
    
    # Cleanup.
    cm_module.COOKIE_DIR = old_dir
    cm_module.PRESETS_FILE = old_presets
    shutil.rmtree(test_dir, ignore_errors=True)

class MockPage:
    class MockContext:
        async def cookies(self):
            return [
                {"name": "session", "value": "123", "domain": "example.com"},
                {"name": "track", "value": "abc", "domain": ".demo.org"}
            ]
        async def add_cookies(self, cookies):
            self.added = cookies
    
    def __init__(self):
        self.context = self.MockContext()


class MockSyncPage:
    class MockContext:
        def cookies(self):
            return [
                {"name": "session", "value": "123", "domain": "example.com"},
                {"name": "track", "value": "abc", "domain": ".demo.org"}
            ]

        def add_cookies(self, cookies):
            self.added = cookies

    def __init__(self):
        self.context = self.MockContext()

@pytest.mark.asyncio
async def test_export_import_cookies(mock_cookie_manager):
    page = MockPage()
    
    # Export.
    res = await mock_cookie_manager.export_cookies(page, "test_export")
    assert res["count"] == 2
    assert "test_export.json" in res["file"]
    
    # List.
    saved = mock_cookie_manager.list_saved()
    assert len(saved) == 1
    assert saved[0]["name"] == "test_export"
    assert saved[0]["count"] == 2
    
    # Import.
    res2 = await mock_cookie_manager.import_cookies(page.context, "test_export")
    assert res2["count"] == 2
    assert len(page.context.added) == 2
    assert page.context.added[0]["name"] == "session"

@pytest.mark.asyncio
async def test_export_with_domain(mock_cookie_manager):
    page = MockPage()
    res = await mock_cookie_manager.export_cookies(page, "domain_export", domain="example.com")
    assert res["count"] == 1


@pytest.mark.asyncio
async def test_export_import_sync_cookies(mock_cookie_manager):
    page = MockSyncPage()

    export_res = await mock_cookie_manager.export_cookies(page, "sync_export")
    assert export_res["count"] == 2

    import_res = await mock_cookie_manager.import_cookies(page.context, "sync_export")
    assert import_res["count"] == 2
    assert len(page.context.added) == 2

def test_preset_management(mock_cookie_manager):
    import json
    # Create a mock cookie file.
    (mock_cookie_manager.COOKIE_DIR if hasattr(mock_cookie_manager, 'COOKIE_DIR') else Path(__file__).parent / "_test_cookies" / "fake.json").write_text("[]")
    
    # Create this manually because the fixture above changes module-level state.
    import core.cookie_manager as cm_module
    (cm_module.COOKIE_DIR / "fake.json").write_text("[]")
    
    res = mock_cookie_manager.save_preset("my_preset", "fake")
    assert res is True
    
    presets = mock_cookie_manager.list_presets()
    assert len(presets) == 1
    assert presets[0]["name"] == "my_preset"
    assert presets[0]["cookie_file"] == "fake"
    
    mock_cookie_manager.delete_preset("my_preset")
    assert len(mock_cookie_manager.list_presets()) == 0
