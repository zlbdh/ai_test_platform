# -*- coding: utf-8 -*-
"""
Data factory service proxy.
The implementation lives in core/data_factory.py; this module preserves the services.data_factory import path.
"""
from core.data_factory import (
    DataFactory,
    get_data_factory,
    generate_test_data,
    generate_test_data_batch,
)


def create_data_factory(locale: str = "en_US") -> DataFactory:
    """Create a data factory instance"""
    return get_data_factory(locale)


__all__ = [
    "DataFactory",
    "get_data_factory",
    "create_data_factory",
    "generate_test_data",
    "generate_test_data_batch",
]
