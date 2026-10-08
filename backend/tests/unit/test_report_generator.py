# -*- coding: utf-8 -*-
"""
Tests for Report Generator.
"""
import pytest
import os
from unittest.mock import patch, mock_open, MagicMock
from core.report_generator import (
    EnhancedReportGenerator,
    TestSuite,
    TestResult,
    ReportFormat,
    create_report_generator
)


@pytest.fixture
def sample_suite():
    return TestSuite(
        name="API Regression V1",
        start_time="2026-02-26 10:00:00",
        end_time="2026-02-26 10:05:00",
        tests=[
            TestResult(name="test_login", status="passed", duration_ms=150),
            TestResult(name="test_pay", status="failed", duration_ms=3000, error_message="Timeout"),
            TestResult(name="test_skip", status="skipped", duration_ms=0),
        ]
    )

class TestReportGenerator:
    @patch("core.report_generator.os.makedirs")
    def test_calculate_stats(self, mock_makedirs, sample_suite):
        generator = EnhancedReportGenerator("/dummy")
        stats = generator._calculate_stats(sample_suite)
        
        assert stats["total"] == 3
        assert stats["passed"] == 1
        assert stats["failed"] == 1
        assert stats["skipped"] == 1
        assert stats["duration_ms"] == 3150
        assert stats["pass_rate"] == 33.3

    @patch("core.report_generator.os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_generate_html(self, mock_file, mock_makedirs, sample_suite):
        generator = EnhancedReportGenerator("/dummy")
        filepath = generator.generate(sample_suite, format=ReportFormat.HTML)
        
        assert filepath.endswith(".html")
        assert "/dummy" in filepath.replace("\\", "/") # cross-platform check
        
        # Verify write
        written_content = "".join(call.args[0] for call in mock_file().write.mock_calls)
        assert "API Regression V1" in written_content
        assert "test_login" in written_content
        assert "test_pay" in written_content
        assert "Timeout" in written_content

    @patch("core.report_generator.os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_generate_junit_xml(self, mock_file, mock_makedirs, sample_suite):
        generator = EnhancedReportGenerator("/dummy")
        filepath = generator.generate(sample_suite, format=ReportFormat.JUNIT_XML)
        
        assert filepath.endswith("_junit.xml")
        
        written_content = "".join(call.args[0] for call in mock_file().write.mock_calls)
        assert "<testsuite name=\"API Regression V1\"" in written_content
        assert "<failure message=\"Timeout\">" in written_content
        assert "<skipped />" in written_content

    @patch("core.report_generator.os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_generate_json(self, mock_file, mock_makedirs, sample_suite):
        generator = EnhancedReportGenerator("/dummy")
        filepath = generator.generate(sample_suite, format=ReportFormat.JSON)
        
        assert filepath.endswith(".json")
        written_content = "".join(call.args[0] for call in mock_file().write.mock_calls)
        assert '"suite": "API Regression V1"' in written_content
        assert '"status": "passed"' in written_content

    @patch("core.report_generator.os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_generate_markdown(self, mock_file, mock_makedirs, sample_suite):
        generator = EnhancedReportGenerator("/dummy")
        filepath = generator.generate(sample_suite, format=ReportFormat.MARKDOWN)
        
        assert filepath.endswith(".md")
        written_content = "".join(call.args[0] for call in mock_file().write.mock_calls)
        assert "# Test report - API Regression V1" in written_content
        assert "✅ passed" in written_content
        assert "❌ failed" in written_content

    @patch("core.report_generator.EnhancedReportGenerator")
    def test_create_report_generator(self, mock_class):
        gen = create_report_generator("/test")
        mock_class.assert_called_with("/test")
