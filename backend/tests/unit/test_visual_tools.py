# -*- coding: utf-8 -*-
"""
Tests for Visual Tools.
"""
import pytest
from unittest.mock import patch, MagicMock
from core.visual_tools import assert_visual_snapshot


class TestVisualTools:
    @patch("core.visual_tools.expect")
    @patch("core.visual_tools.os.makedirs")
    def test_assert_visual_snapshot_success(self, mock_makedirs, mock_expect):
        """Test successful visual verification."""
        # mock playwright expect(...).to_have_screenshot
        mock_page = MagicMock()
        mock_expect_obj = MagicMock()
        mock_expect.return_value = mock_expect_obj
        
        result = assert_visual_snapshot(mock_page, "test_snap")
        
        assert result["status"] == "success"
        assert "test_snap.png" in result["message"]
        mock_expect_obj.to_have_screenshot.assert_called_once()

    @patch("core.visual_tools.expect")
    @patch("core.visual_tools.os.makedirs")
    def test_assert_visual_snapshot_failure(self, mock_makedirs, mock_expect):
        """Test visual verification failure with AssertionError."""
        mock_page = MagicMock()
        mock_expect_obj = MagicMock()
        mock_expect_obj.to_have_screenshot.side_effect = AssertionError("Pixels differ")
        mock_expect.return_value = mock_expect_obj
        
        result = assert_visual_snapshot(mock_page, "test_snap")
        
        assert result["status"] == "error"
        assert "Visual comparison failed" in result["message"]
        assert "Pixels differ" in result["details"]["error"]

    @patch("core.visual_tools.expect")
    @patch("core.visual_tools.os.makedirs")
    @patch("core.visual_tools.os.path.exists")
    def test_assert_visual_snapshot_fallback_no_baseline(self, mock_exists, mock_makedirs, mock_expect):
        """Without to_have_screenshot, use the fallback when no baseline exists."""
        mock_page = MagicMock()
        mock_expect_obj = object() # No to_have_screenshot -> AttributeError
        mock_expect.return_value = mock_expect_obj
        
        mock_exists.return_value = False
        
        result = assert_visual_snapshot(mock_page, "test_snap")
        
        assert result["status"] == "success"
        assert "First run: baseline screenshot saved" in result["message"]
        mock_page.screenshot.assert_called()

    @patch("core.visual_tools.expect")
    @patch("core.visual_tools.os.makedirs")
    @patch("core.visual_tools.os.path.exists")
    @patch("PIL.Image.open")
    @patch("PIL.ImageChops.difference")
    def test_assert_visual_snapshot_fallback_compare_success(
        self, mock_diff, mock_img_open, mock_exists, mock_makedirs, mock_expect
    ):
        """Test successful image comparison in fallback mode."""
        mock_page = MagicMock()
        mock_expect.return_value = object()
        
        mock_exists.return_value = True
        
        # mock image
        mock_img = MagicMock()
        mock_img.size = (100, 100)
        mock_img_open.return_value.convert.return_value = mock_img
        
        # mock identical images -> histogram is all zeros
        mock_diff_img = MagicMock()
        mock_diff_img.histogram.return_value = [0] * 256
        mock_diff.return_value = mock_diff_img
        
        result = assert_visual_snapshot(mock_page, "test_snap")
        
        assert result["status"] == "success"
        assert "Visual comparison passed (Manual" in result["message"]

    @patch("core.visual_tools.expect")
    @patch("core.visual_tools.os.makedirs")
    @patch("core.visual_tools.os.path.exists")
    @patch("PIL.Image.open")
    @patch("PIL.ImageChops.difference")
    def test_assert_visual_snapshot_fallback_compare_fail(
        self, mock_diff, mock_img_open, mock_exists, mock_makedirs, mock_expect
    ):
        """Test fallback image comparison failure when RMS is too high."""
        mock_page = MagicMock()
        mock_expect.return_value = object()
        
        mock_exists.return_value = True
        
        # mock image
        mock_img = MagicMock()
        mock_img.size = (100, 100)
        mock_img_open.return_value.convert.return_value = mock_img
        
        # mock different images -> high RMS
        mock_diff_img = MagicMock()
        # [255] diff in one channel for all pixels
        hist = [0] * 256
        hist[-1] = 10000  # large diff
        mock_diff_img.histogram.return_value = hist
        mock_diff.return_value = mock_diff_img
        
        result = assert_visual_snapshot(mock_page, "test_snap", threshold=0.1)
        
        assert result["status"] == "error"
        assert "Visual comparison failed (RMS" in result["message"]
