# -*- coding: utf-8 -*-
"""
Data Factory 服务代理
实际实现在 core/data_factory.py，此文件提供 services.data_factory 导入路径兼容
"""
from core.data_factory import (
    DataFactory,
    get_data_factory,
    generate_test_data,
    generate_test_data_batch,
)


def create_data_factory(locale: str = "zh_CN") -> DataFactory:
    """创建数据工厂实例"""
    return get_data_factory(locale)


__all__ = [
    "DataFactory",
    "get_data_factory",
    "create_data_factory",
    "generate_test_data",
    "generate_test_data_batch",
]
