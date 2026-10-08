"""Regression checks for synthetic-data locale defaults and legacy providers."""
from core.data_factory import DataFactory


def test_default_factory_supports_american_english_address_fields():
    factory = DataFactory()
    assert factory.fake.locales == ["en_US"]
    record = factory.generate({"region": "province", "name": "name", "address": "address"})
    assert set(record) == {"region", "name", "address"}
    assert all(isinstance(value, str) and value for value in record.values())
    assert record["region"].isascii()


def test_explicit_chinese_locale_retains_province_provider():
    factory = DataFactory("zh_CN")
    assert factory.fake.locales == ["zh_CN"]
    record = factory.generate({"region": "province"})
    assert isinstance(record["region"], str) and record["region"]
    assert not record["region"].isascii()
