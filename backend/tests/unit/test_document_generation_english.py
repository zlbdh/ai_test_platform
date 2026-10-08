"""English document analysis and legacy input compatibility regressions."""
from types import SimpleNamespace
import re
import pytest

from core.document_analysis import DocumentAnalyzer
from core.document_bundle_analysis import DocumentBundleAnalyzer
from core.document_test_designer import DocumentTestDesigner
from core.requirement_parser import RequirementParser
from core.scenario_generator import ScenarioGenerator, BOUNDARY_TEMPLATES
from core.test_data_generator import TestDataGenerator


def test_english_requirements_extract_original_roles_rules_and_constraints():
    content = """# Functional Requirements
1. Users must sign in before placing an order.
2. Administrators must verify permissions.
3. Response time must be less than 500 ms under concurrent load.
## Acceptance Criteria
- Password length must be at least 8 characters.
- Invalid credentials must produce a failure response.
"""
    result = DocumentAnalyzer().analyze(content, "Requirements document")
    assert result.document_type == "requirement_prd"
    assert result.document_label == "Requirements document"
    assert "Users" in result.extracted["actors"]
    assert "Administrators" in result.extracted["actors"]
    assert "Password length must be at least 8 characters." in result.extracted["data_constraints"]
    assert "security" in result.recommended_test_types
    assert "performance" in result.recommended_test_types
    assert all(not re.search(r"[\u3400-\u9fff]", issue.message + issue.suggestion) for issue in result.issues)


@pytest.mark.parametrize("content,expected", [
    ("Development document: architecture design", "development_design"),
    ("API specification: GET /orders", "api_spec"),
    ("Database schema with tables", "database_schema"),
    ("开发文档：架构设计", "development_design"),
    ("需求文档：业务规则", "requirement_prd"),
])
def test_document_type_detection_accepts_english_and_legacy(content, expected):
    assert DocumentAnalyzer().analyze(content).document_type == expected


@pytest.mark.parametrize("constraint,expected", [
    ("amount must be at least 1", ("amount", ">=1")),
    ("amount is no more than 100", ("amount", "<=100")),
    ("amount MUST BE greater than 0", ("amount", ">0")),
    ("amount less than 10", ("amount", "<10")),
    ("amount equals 3", ("amount", "=3")),
    ("amount >= 1", ("amount", ">=1")),
    ("金额至少 1", ("金额", ">=1")),
])
def test_constraint_operators_keep_field_and_threshold(constraint, expected):
    assert DocumentBundleAnalyzer()._parse_constraint(constraint) == expected


@pytest.mark.parametrize("message", ["Field/constraint 'amount' differs", "字段约束不一致"])
def test_translated_bundle_findings_keep_data_validation_routing(message):
    bundle = SimpleNamespace(findings=[SimpleNamespace(category="consistency", severity="warning", message=message, suggestion="Align thresholds")])
    result = DocumentTestDesigner()._build_bundle_alignment_tests(bundle)
    assert result[0]["type"] == "data_validation"
    assert result[0]["priority"] == "high"
    assert result[0]["basis"] == [message]
    assert result[0]["id"] == "BUNDLE-001"


@pytest.mark.parametrize("text,condition,behavior", [
    ("If the password is invalid, then access must be denied", "the password is invalid", "access must be denied"),
    ("When the order is canceled, the payment must be refunded", "the order is canceled", "the payment must be refunded"),
    ("如果密码无效，则必须拒绝登录", "密码无效", "必须拒绝登录"),
])
def test_conditional_rules_preserve_verbatim_input_and_negative_coverage(text, condition, behavior):
    result = RequirementParser().parse_text(text)
    assert result.rules[0].source_text == text
    assert result.rules[0].conditions == [condition]
    assert result.rules[0].expected_behavior == behavior
    assert len(result.test_cases) == 2


@pytest.mark.parametrize("action", ["Enter account details", "Fill account details", "输入账号信息"])
def test_input_actions_generate_invalid_input_scenarios(action):
    result = ScenarioGenerator().generate_negative_scenarios([{"action": action}])
    assert any(item.get("modification") == "Use invalid data" for item in result)


def test_synthetic_address_defaults_are_english_with_stable_field_keys():
    result = TestDataGenerator.generate("address", count=3, include_edge=False)
    assert result["fields"] == ["province", "city", "district", "street", "zipcode"]
    assert len(result["data"]) == 3
    for row in result["data"]:
        assert all(value.isascii() for value in row.values())
        assert len(row["zipcode"]) == 5 and row["zipcode"].isdigit()


def test_sample_platform_enum_values_and_cleanup_contract_remain_compatible():
    row = TestDataGenerator.generate("sample_platform_work_order", count=1, include_edge=False)["data"][0]
    assert row["businessType"] in {"家政服务", "物业服务", "养老服务"}
    assert row["urgencyLevel"] in {"普通", "紧急", "非常紧急"}
    assert row["source"] in {"自有", "平台"}
    assert row["cleanupTag"].startswith("TEST_SAMPLE_WO_")
    row = TestDataGenerator.generate("sample_platform_announcement", count=1, include_edge=False)["data"][0]
    assert row["publishStatus"] in {"草稿", "已发布", "已下线"}


def test_unicode_boundary_values_are_preserved_as_test_payloads():
    assert any(item["value"] == "🎯测试émoji" for item in BOUNDARY_TEMPLATES["string"])
    rows = TestDataGenerator.generate("boundary", count=20)["data"]
    assert any(item["type"] == "multibyte" and item["value"] == "中文テスト한국어" for item in rows)


def test_navigation_to_account_center_does_not_imply_input():
    result = ScenarioGenerator().generate_negative_scenarios([{"action": "Open the account center"}])
    assert not any(item.get("modification") == "Use invalid data" for item in result)
