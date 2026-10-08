# -*- coding: utf-8 -*-
import pytest

from core import sample_platform_playbook as prototype_playbook

from core.project_playbooks import (
    PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE,
    PLAYBOOK_ID_SAMPLE_PLATFORM_FIRST_REGRESSION,
    get_quality_gate_rules,
    get_requirement_playbook,
    get_scenario_playbook,
    get_test_data_convention,
    list_playbooks,
)
from routers.quality_gate import import_rules_from_playbook
from routers.requirement import get_requirement_playbook_detail


@pytest.fixture
def prototype_documents(monkeypatch):
    """Exercise mapping with local fixtures, without deployed requirement repositories."""
    entries = []
    for index, blueprint in enumerate(prototype_playbook._MODULE_BLUEPRINTS):
        rows = [
            f"| Fixture page {number} | /fixture/{index}/{number} | 列表页 | Fixture description |"
            for number in range(1, 5)
        ]
        content = "\n".join([
            "## 2. 页面清单",
            "| 页面名称 | 页面路由 | 页面类型 | 说明 |",
            "| --- | --- | --- | --- |",
            *rows,
        ])
        entries.append({
            "module_name": blueprint["module_name"],
            "title": blueprint["doc_title"],
            "role": blueprint["role"],
            "relative_path": f"fixtures/module-{index}.md",
            "local_path": f"/fixtures/module-{index}.md",
            "exists": True,
            "content": content,
        })
    monkeypatch.setattr(prototype_playbook, "_platform_doc_entries", lambda: entries)
    monkeypatch.setattr(prototype_playbook, "_prototype_files", lambda: ([], None))
    monkeypatch.setattr(prototype_playbook, "_prototype_dir_candidates", lambda: [
        {"asset_id": "fixture-primary", "exists": False},
        {"asset_id": "fixture-secondary", "exists": False},
    ])
    return entries


def test_requirement_playbook_contains_target_and_waves():
    playbook = get_requirement_playbook(PLAYBOOK_ID_SAMPLE_PLATFORM_FIRST_REGRESSION)

    assert playbook is not None
    assert playbook["project_name"] == "Sample Enterprise Platform"
    assert playbook["target_url"] == "https://example.com/login"
    assert playbook["recommended_test_types"] == ["ui_e2e", "business_flow", "api_rest", "data_validation"]
    assert len(playbook["waves"]) == 5
    assert playbook["naming_convention"]["test_data_prefix"] == "TEST_SAMPLE"
    assert len(playbook["document_sources"]) >= 6


def test_playbook_catalog_lists_sample_platform():
    items = list_playbooks()

    assert any(item["playbook_id"] == PLAYBOOK_ID_SAMPLE_PLATFORM_FIRST_REGRESSION for item in items)
    assert any(item["playbook_id"] == PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE for item in items)


def test_scenario_playbook_uses_role_based_naming():
    scenarios = get_scenario_playbook(PLAYBOOK_ID_SAMPLE_PLATFORM_FIRST_REGRESSION)

    assert len(scenarios) >= 5
    assert all(scenario["name"].startswith("[业务运营角色]-") for scenario in scenarios)
    assert any("工单调度" in scenario["name"] for scenario in scenarios)


def test_quality_gate_rules_match_first_regression_policy():
    rules = get_quality_gate_rules(PLAYBOOK_ID_SAMPLE_PLATFORM_FIRST_REGRESSION)

    metrics = {rule["metric"] for rule in rules}
    assert metrics == {
        "login_success_rate",
        "core_flow_pass_rate",
        "blocking_bug_count",
        "unexplained_5xx_count",
        "critical_ui_error_count",
    }


def test_platform_prototype_playbook_contains_asset_checks_and_page_mappings(prototype_documents):
    playbook = get_requirement_playbook(PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE)

    assert playbook is not None
    assert playbook["project_name"] == "Sample Project Platform"
    assert playbook["recommended_test_types"] == ["ui_e2e", "business_flow", "data_validation", "visual_regression"]
    assert len(playbook["asset_checks"]) >= 5
    assert len(playbook["prototype_assets"]) >= 2
    assert playbook["mapping_summary"]["module_count"] == 16
    assert playbook["mapping_summary"]["total_pages"] >= 50
    assert any(item["module_name"] == "登录与认证" for item in playbook["page_mappings"])
    assert any(item["module_name"] == "系统管理" for item in playbook["page_mappings"])


def test_platform_prototype_scenarios_cover_modules_and_cross_flows():
    scenarios = get_scenario_playbook(PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE)

    assert len(scenarios) >= 50
    assert any("企业管理-页面结构检查" in scenario["name"] for scenario in scenarios)
    assert any("跨模块-订单路由到财务与投诉闭环" in scenario["name"] for scenario in scenarios)


def test_platform_prototype_quality_gate_rules_match_policy():
    rules = get_quality_gate_rules(PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE)

    metrics = {rule["metric"] for rule in rules}
    assert metrics == {
        "module_coverage_rate",
        "page_mapping_rate",
        "critical_page_missing_count",
        "blocking_prototype_gap_count",
        "critical_field_missing_count",
        "critical_state_transition_gap_count",
    }


def test_test_data_convention_exposes_prefix():
    convention = get_test_data_convention(PLAYBOOK_ID_SAMPLE_PLATFORM_FIRST_REGRESSION)

    assert convention is not None
    assert convention["prefix"] == "TEST_SAMPLE"


def test_platform_prototype_test_data_convention_exposes_artifact_prefix():
    convention = get_test_data_convention(PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE)

    assert convention is not None
    assert convention["prefix"] == "SAMPLE_PLATFORM_PROTO"


@pytest.mark.asyncio
async def test_requirement_router_returns_playbook_detail():
    payload = await get_requirement_playbook_detail(PLAYBOOK_ID_SAMPLE_PLATFORM_FIRST_REGRESSION)

    assert payload["title"] == "Sample Enterprise Platform Initial Live Regression"
    assert payload["target_url"] == "https://example.com/login"


@pytest.mark.asyncio
async def test_requirement_router_returns_platform_prototype_playbook_detail(prototype_documents):
    payload = await get_requirement_playbook_detail(PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE)

    assert payload["title"] == "Sample Project Platform Prototype Test Package"
    assert payload["mapping_summary"]["module_count"] == 16


@pytest.mark.asyncio
async def test_quality_gate_router_imports_playbook_rules():
    response = await import_rules_from_playbook(PLAYBOOK_ID_SAMPLE_PLATFORM_FIRST_REGRESSION)

    assert response["status"] == "ok"
    assert response["data"]["imported_count"] == 5
    assert any(rule["metric"] == "login_success_rate" for rule in response["data"]["rules"])


@pytest.mark.asyncio
async def test_quality_gate_router_imports_platform_prototype_rules():
    response = await import_rules_from_playbook(PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE)

    assert response["status"] == "ok"
    assert response["data"]["imported_count"] == 6
    assert any(rule["metric"] == "module_coverage_rate" for rule in response["data"]["rules"])
