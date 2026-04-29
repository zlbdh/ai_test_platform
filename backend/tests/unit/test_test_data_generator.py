# -*- coding: utf-8 -*-
from core.test_data_generator import TestDataGenerator


class TestTestDataGenerator:
    def test_list_templates_contains_sample_platform_presets(self):
        templates = TestDataGenerator.list_templates()
        template_ids = {item["id"] for item in templates}

        assert "sample_platform_work_order" in template_ids
        assert "sample_platform_property_parking" in template_ids
        assert "sample_platform_elder_profile" in template_ids
        assert "sample_platform_announcement" in template_ids

    def test_generate_rejects_negative_count(self):
        result = TestDataGenerator.generate("user", count=-1)

        assert result == {"error": "count must be >= 0"}

    def test_search_template_zero_count_returns_empty_dataset(self):
        result = TestDataGenerator.generate("search", count=0, include_edge=True)

        assert result["count"] == 0
        assert result["data"] == []

    def test_generate_custom_rejects_invalid_range(self):
        result = TestDataGenerator.generate_custom(
            [{"name": "age", "type": "integer", "min": 10, "max": 1}],
            count=1,
        )

        assert result == {"error": "Invalid range for field 'age': min cannot be greater than max"}

    def test_generate_custom_rejects_large_count(self):
        result = TestDataGenerator.generate_custom(
            [{"name": "username", "type": "string", "min": 3, "max": 8}],
            count=1001,
        )

        assert result == {"error": "count must be <= 1000"}

    def test_sample_platform_work_order_template_uses_recycle_prefix(self):
        result = TestDataGenerator.generate("sample_platform_work_order", count=2, include_edge=False)

        assert result["count"] == 2
        assert all(row["cleanupTag"].startswith("TEST_SAMPLE_WO_") for row in result["data"])

    def test_sample_platform_elder_template_contains_edge_rows(self):
        result = TestDataGenerator.generate("sample_platform_elder_profile", count=1, include_edge=True)

        assert result["count"] >= 3
        assert any(row.get("_edge") == "空档案" for row in result["data"])
