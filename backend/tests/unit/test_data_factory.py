# -*- coding: utf-8 -*-
"""
Tests for the Data Factory module.
"""
import pytest
from core.data_factory import generate_test_data, DataFactory


class TestDataFactory:
    """Data Factory unit tests."""

    def test_generate_name(self):
        """Test name generation."""
        result = generate_test_data({"name": "name"})
        assert "name" in result
        assert len(result["name"]) > 0

    def test_generate_email(self):
        """Test email generation."""
        result = generate_test_data({"email": "email"})
        assert "email" in result
        assert "@" in result["email"]

    def test_generate_phone(self):
        """Test phone number generation."""
        result = generate_test_data({"phone": "phone"})
        assert "phone" in result
        assert len(result["phone"]) >= 10

    def test_generate_multiple_fields(self):
        """Test multiple-field generation."""
        template = {
            "name": "name",
            "email": "email",
            "phone": "phone",
            "address": "address"
        }
        result = generate_test_data(template)
        
        assert len(result) == 4
        assert all(key in result for key in template.keys())

    def test_generate_with_count(self):
        """Test batch generation."""
        template = {"name": "name"}
        results = [generate_test_data(template) for _ in range(5)]
        
        assert len(results) == 5
        # Ensure that generated records vary.
        names = [r["name"] for r in results]
        assert len(set(names)) > 1  # Expect at least two distinct names.

    def test_unknown_field_type(self):
        """Test an unknown field type."""
        result = generate_test_data({"unknown": "unknown_type"})
        # Return the original value or an empty string.
        assert "unknown" in result

    def test_data_factory_class(self):
        """Test the DataFactory class."""
        factory = DataFactory()
        
        # Test the list of available types.
        types = factory.get_available_types()
        assert isinstance(types, list)
        assert "name" in types
        assert "email" in types

    def test_generate_batch(self):
        """Test batch data generation."""
        factory = DataFactory()
        template = {"name": "name", "email": "email"}
        
        results = factory.generate_batch(template, count=10)
        assert len(results) == 10
        for item in results:
            assert "name" in item
            assert "email" in item
