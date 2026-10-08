"""
VisualRegressionTester unit tests.
Covers enums and data classes, baseline saving, hash-based comparison, baseline
update/list/delete operations, report generation, and the singleton.
"""
import pytest
import json
import os
from unittest.mock import patch, MagicMock

from services.visual_regression import (
    ComparisonResult, ScreenshotData, DiffResult,
    VisualRegressionTester
)


# ---------------------------------------------------------------------------
# Enums.
# ---------------------------------------------------------------------------
class TestComparisonResult:
    def test_values(self):
        assert ComparisonResult.MATCH.value == "match"
        assert ComparisonResult.MISMATCH.value == "mismatch"
        assert ComparisonResult.NEW_BASELINE.value == "new_baseline"
        assert ComparisonResult.ERROR.value == "error"


# ---------------------------------------------------------------------------
# Data classes.
# ---------------------------------------------------------------------------
class TestScreenshotData:
    def test_creation(self):
        sd = ScreenshotData(name="login", filepath="/a/b.png", width=100, height=200,
                            timestamp="2026-01-01", hash="abc")
        assert sd.name == "login"
        assert sd.width == 100


class TestDiffResult:
    def test_creation(self):
        b = ScreenshotData("a", "/a", 10, 10, "", "")
        c = ScreenshotData("a", "/b", 10, 10, "", "")
        dr = DiffResult(baseline=b, current=c, result=ComparisonResult.MATCH,
                        diff_percentage=0.0, diff_filepath=None, threshold=0.01)
        assert dr.result == ComparisonResult.MATCH


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def tester(tmp_path):
    """Create a tester with Pillow disabled to force hash mode."""
    t = VisualRegressionTester(baseline_dir=str(tmp_path))
    t._pillow_available = False
    return t


IMAGE_DATA = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # Mock PNG content.
IMAGE_DATA2 = b"\x89PNG\r\n\x1a\n" + b"\xff" * 100  # Different content.


# ---------------------------------------------------------------------------
# save_baseline tests.
# ---------------------------------------------------------------------------
class TestSaveBaseline:
    def test_saves_file(self, tester, tmp_path):
        sd = tester.save_baseline("homepage", IMAGE_DATA)
        assert sd.name == "homepage"
        assert os.path.exists(os.path.join(str(tmp_path), "homepage.png"))
        assert os.path.exists(os.path.join(str(tmp_path), "homepage.json"))
        assert sd.hash != ""

    def test_saves_metadata(self, tester, tmp_path):
        tester.save_baseline("page", IMAGE_DATA, metadata={"browser": "chrome"})
        with open(os.path.join(str(tmp_path), "page.json")) as f:
            meta = json.load(f)
        assert meta["custom"]["browser"] == "chrome"
        assert meta["name"] == "page"


# ---------------------------------------------------------------------------
# compare tests in hash mode.
# ---------------------------------------------------------------------------
class TestCompare:
    def test_new_baseline(self, tester, tmp_path):
        """Create a new baseline when none exists."""
        result = tester.compare("login", IMAGE_DATA)
        assert result.result == ComparisonResult.NEW_BASELINE
        # Save the baseline automatically.
        assert os.path.exists(os.path.join(str(tmp_path), "login.png"))

    def test_match(self, tester, tmp_path):
        """Identical images should match."""
        tester.save_baseline("page", IMAGE_DATA)
        result = tester.compare("page", IMAGE_DATA)
        assert result.result == ComparisonResult.MATCH
        assert result.diff_percentage == 0

    def test_mismatch(self, tester, tmp_path):
        """Different images should not match."""
        tester.save_baseline("page", IMAGE_DATA)
        result = tester.compare("page", IMAGE_DATA2)
        assert result.result == ComparisonResult.MISMATCH
        assert result.diff_percentage == 100


# ---------------------------------------------------------------------------
# update_baseline tests.
# ---------------------------------------------------------------------------
class TestUpdateBaseline:
    def test_update_success(self, tester, tmp_path):
        tester.save_baseline("page", IMAGE_DATA)
        assert tester.update_baseline("page", IMAGE_DATA2) is True
        # Overwrite with the new data.
        with open(os.path.join(str(tmp_path), "page.png"), "rb") as f:
            assert f.read() == IMAGE_DATA2


# ---------------------------------------------------------------------------
# list_baselines tests.
# ---------------------------------------------------------------------------
class TestListBaselines:
    def test_empty(self, tester):
        assert tester.list_baselines() == []

    def test_with_baselines(self, tester):
        tester.save_baseline("a", IMAGE_DATA)
        tester.save_baseline("b", IMAGE_DATA)
        baselines = tester.list_baselines()
        assert len(baselines) == 2
        names = {b["name"] for b in baselines}
        assert names == {"a", "b"}


# ---------------------------------------------------------------------------
# delete_baseline tests.
# ---------------------------------------------------------------------------
class TestDeleteBaseline:
    def test_delete_existing(self, tester, tmp_path):
        tester.save_baseline("page", IMAGE_DATA)
        assert tester.delete_baseline("page") is True
        assert not os.path.exists(os.path.join(str(tmp_path), "page.png"))
        assert not os.path.exists(os.path.join(str(tmp_path), "page.json"))

    def test_delete_nonexistent(self, tester):
        # A missing file returns True without raising because the source catches exceptions.
        assert tester.delete_baseline("nonexistent") is True


# ---------------------------------------------------------------------------
# generate_report tests.
# ---------------------------------------------------------------------------
class TestGenerateReport:
    def test_empty_results(self, tester):
        report = tester.generate_report([])
        assert report["summary"]["total"] == 0
        assert report["summary"]["pass_rate"] == 0

    def test_mixed_results(self, tester):
        b = ScreenshotData("a", "/a", 10, 10, "", "")
        c = ScreenshotData("a", "/b", 10, 10, "", "")
        results = [
            DiffResult(b, c, ComparisonResult.MATCH, 0.0, None, 0.01),
            DiffResult(b, c, ComparisonResult.MISMATCH, 5.5, "/diff.png", 0.01),
            DiffResult(b, c, ComparisonResult.NEW_BASELINE, 0.0, None, 0.01),
        ]
        report = tester.generate_report(results)
        assert report["summary"]["total"] == 3
        assert report["summary"]["passed"] == 1
        assert report["summary"]["failed"] == 1
        assert report["summary"]["new_baselines"] == 1
        assert len(report["results"]) == 3


# ---------------------------------------------------------------------------
# Singleton.
# ---------------------------------------------------------------------------
class TestSingleton:
    def test_singleton(self, tmp_path):
        import services.visual_regression as mod
        mod._visual_tester = None
        s1 = mod.get_visual_tester()
        s2 = mod.get_visual_tester()
        assert s1 is s2
        mod._visual_tester = None
