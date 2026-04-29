# -*- coding: utf-8 -*-
"""
测试 - Data Factory 模块
"""
import pytest
from core.data_factory import generate_test_data, DataFactory


class TestDataFactory:
    """Data Factory 单元测试"""

    def test_generate_name(self):
        """测试姓名生成"""
        result = generate_test_data({"name": "name"})
        assert "name" in result
        assert len(result["name"]) > 0

    def test_generate_email(self):
        """测试邮箱生成"""
        result = generate_test_data({"email": "email"})
        assert "email" in result
        assert "@" in result["email"]

    def test_generate_phone(self):
        """测试电话生成"""
        result = generate_test_data({"phone": "phone"})
        assert "phone" in result
        assert len(result["phone"]) >= 10

    def test_generate_multiple_fields(self):
        """测试多字段生成"""
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
        """测试批量生成"""
        template = {"name": "name"}
        results = [generate_test_data(template) for _ in range(5)]
        
        assert len(results) == 5
        # 确保每次生成的数据不同
        names = [r["name"] for r in results]
        assert len(set(names)) > 1  # 至少有2个不同的名字

    def test_unknown_field_type(self):
        """测试未知字段类型"""
        result = generate_test_data({"unknown": "unknown_type"})
        # 应该返回原始值或空字符串
        assert "unknown" in result

    def test_data_factory_class(self):
        """测试 DataFactory 类"""
        factory = DataFactory()
        
        # 测试可用类型列表
        types = factory.get_available_types()
        assert isinstance(types, list)
        assert "name" in types
        assert "email" in types

    def test_generate_batch(self):
        """测试批量数据生成"""
        factory = DataFactory()
        template = {"name": "name", "email": "email"}
        
        results = factory.generate_batch(template, count=10)
        assert len(results) == 10
        for item in results:
            assert "name" in item
            assert "email" in item
