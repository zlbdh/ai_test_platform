# -*- coding: utf-8 -*-
'\nProject regression package presets\n\nProvide shared project presets for requirements, scenario chains, quality gates, and test data.\n'
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from core.config import Config
from core.sample_platform_playbook import (
    PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE,
    get_catalog_entry as get_sample_platform_platform_catalog_entry,
    get_quality_gate_rules as get_sample_platform_platform_quality_gate_rules,
    get_requirement_playbook as get_sample_platform_platform_requirement_playbook,
    get_scenario_playbook as get_sample_platform_platform_scenario_playbook,
    get_test_data_convention as get_sample_platform_platform_test_data_convention,
)


PLAYBOOK_ID_SAMPLE_PLATFORM_FIRST_REGRESSION = "sample-first-regression"

_TARGET_URL = "https://example.com/login"
_FRONTEND_REPO_URL = "https://example.com/example-org/sample-product-qd.git"
_BACKEND_REPO_URL = "https://example.com/example-org/sample-product-hd.git"
_DOCS_REPO_URL = "https://example.com/example-org/sample_platform.git"
_TEST_DATA_PREFIX = "TEST_SAMPLE"
# Preserve the target role name and existing scenario names as external/persisted identifiers.
_ROLE_NAME = "业务运营角色"


def _repo_root() -> Path:
    return Path(Config.PROJECT_ROOT).resolve().parent


def _deployed_repo_path(repo_name: str) -> Path:
    return _repo_root() / "data" / "deploy" / repo_name


def _docs_repo_path() -> Path:
    return _deployed_repo_path("sample_platform")


def _safe_read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _docs_entry(relative_path: str, title: str, role: str = "reference") -> dict[str, Any]:
    docs_root = _docs_repo_path()
    full_path = docs_root / relative_path
    return {
        "title": title,
        "role": role,
        "relative_path": relative_path.replace("\\", "/"),
        "local_path": str(full_path),
        "exists": full_path.exists(),
        "content": _safe_read_text(full_path),
    }


_SAMPLE_PLATFORM_DOCS = [
    _docs_entry(
        r"docx\XQ\Second\企业平台端需求\00-项目总览与技术架构.md",
        'Enterprise platform - Project overview and technical architecture',
        "primary",
    ),
    _docs_entry(
        r"docx\XQ\Second\企业平台端需求\01-登录与认证模块.md",
        'Enterprise platform - Sign-in and authentication',
    ),
    _docs_entry(
        r"docx\XQ\Second\企业平台端需求\03-工单调度模块.md",
        'Enterprise platform - Work order dispatch',
    ),
    _docs_entry(
        r"docx\XQ\Second\企业平台端需求\07-智慧物业模块.md",
        'Enterprise platform - Property management',
    ),
    _docs_entry(
        r"docx\XQ\Second\企业平台端需求\06-养老管理模块.md",
        'Enterprise platform - Senior care management',
    ),
    _docs_entry(
        r"docx\XQ\Second\企业平台端需求\09-系统管理模块.md",
        'Enterprise platform - System administration',
    ),
]


def _build_requirement_content() -> str:
    available_docs = [doc for doc in _SAMPLE_PLATFORM_DOCS if doc["exists"]]
    available_doc_lines = "\n".join(
        f"- {doc['title']}: {doc['relative_path']}" for doc in available_docs
    ) or '- The requirements repository is not available in this workspace. Clone the sample_platform repository first.'

    return f"# Sample Enterprise Platform Initial Live Regression\n\n## Project overview\n- System under test: Sample Enterprise Platform administration system\n- Sign-in URL: {_TARGET_URL}\n- Target users: Enterprise administrators and module operators\n- Scope: Work order dispatch, property management, senior care, system administration, store management, finance, and training\n\n## Repositories\n- Frontend repository: {_FRONTEND_REPO_URL}\n- Backend repository: {_BACKEND_REPO_URL}\n- Requirements repository: {_DOCS_REPO_URL}\n\n## Initial regression goals\n- Run live regression tests against the requirements\n- Use {_ROLE_NAME} as the primary role\n- Test data may be created and cleaned up\n- Prioritize ui_e2e, business_flow, api_rest, and data_validation tests\n- Performance and security checks do not block this initial regression\n\n## Priorities and waves\n1. Wave 0: Authentication and session baseline\n2. Wave 1: Work order dispatch, property management, announcements, and incident flows\n3. Wave 2: Parking, security, energy use, equipment, and alerts\n4. Wave 3: Senior care and merchant capabilities\n5. Wave 4: System administration, profile, password changes, and role-specific menu permissions\n\n## Default acceptance criteria\n- Primary sign-in flow passes\n- Core business flow pass rate >= 95%\n- Blocking defects <= 0\n- Unexplained 5xx errors <= 0\n- Blank pages, broken links, or severe console errors on key pages <= 0\n\n## Recommended documents\n{available_doc_lines}\n\n## Execution constraints\n- Use the scenario naming pattern `[role]-[module]-[scenario]-[environment]`\n- All newly created data must use the `{_TEST_DATA_PREFIX}` prefix\n- Delete removable test objects at the end; record nonremovable objects in the cleanup list\n- Specify each scenario's role, prerequisite data, entry URL, key assertions, and failure screenshot requirements\n"


_SAMPLE_PLATFORM_WAVES = [
    {
        "id": "wave0",
        "name": 'Wave 0 Authentication and session baseline',
        "focus": ['Sign-in and authentication', 'Verification codes', 'Menu loading', 'Session persistence', 'Sign-out'],
    },
    {
        "id": "wave1",
        "name": 'Wave 1 Core business flows',
        "focus": ['Work order dispatch', 'Property management', 'Announcements and incidents'],
    },
    {
        "id": "wave2",
        "name": 'Wave 2 Assets and on-site capabilities',
        "focus": ['Parking', 'Security', 'Energy use', 'Equipment maintenance', 'Alert handling'],
    },
    {
        "id": "wave3",
        "name": 'Wave 3 Senior care and merchants',
        "focus": ['Senior resident records', 'Care devices', 'Care alerts', 'Merchant onboarding and review'],
    },
    {
        "id": "wave4",
        "name": 'Wave 4 System regression',
        "focus": ['Profile', 'Password changes', 'System configuration reads', 'Business-role menu permissions'],
    },
]


def _step(
    name: str,
    url: str,
    instruction: str,
    timeout: int = 120,
    on_failure: str = "stop",
    depends_on: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": name,
        "url": url,
        "instruction": instruction.strip(),
        "mode": "smart",
        "timeout": timeout,
        "on_failure": on_failure,
    }
    if depends_on:
        payload["depends_on"] = depends_on
    return payload


_SAMPLE_PLATFORM_SCENARIOS = [
    {
        "name": f"[{_ROLE_NAME}]-登录认证-Wave0基线-测试环境",
        "description": (
            'Cover the sign-in page baseline, verification codes, valid and invalid sign-in, menu loading, session persistence after refresh, and sign-out. Use a real test account and retain sign-in/homepage screenshots on failure.'
        ),
        "tags": ['Sample project', 'Live regression', "wave0", 'Authentication'],
        "steps": [
            _step(
                'Sign-in page baseline',
                _TARGET_URL,
                f'\nRole: {_ROLE_NAME}\nPrerequisites: No sign-in required; record whether verification codes are enabled\nGoal: Verify that the sign-in page is reachable and the input, verification-code, Remember Me, and agreement controls are visible\nKey assertions:\n1. The page title or brand is visible\n2. Username, password, and verification-code inputs exist when enabled\n3. The sign-in button is clickable; there are no blank pages, broken links, or severe console errors\nFailure screenshots: Retain a full-page screenshot and console error summary\n',
            ),
            _step(
                'Valid sign-in and homepage menu checks',
                _TARGET_URL,
                f'\nRole: {_ROLE_NAME}\nPrerequisites: A valid test account, verification-code handling method, and permission to access business menus\nGoal: Sign in and verify the homepage and top-level menus associated with `/system/user/getInfo` and `/system/menu/getRouters`\nKey assertions:\n1. Successful sign-in opens the homepage or default workspace\n2. The role can see its permitted menus among work order dispatch, property management, senior care, and system administration\n3. Refreshing the page preserves the signed-in session\nFailure screenshots: Retain screenshots before sign-in, after sign-in, and of any menu errors\n',
                depends_on=None,
            ),
            _step(
                'Sign out to the sign-in page',
                _TARGET_URL,
                f'\nRole: {_ROLE_NAME}\nPrerequisites: An active signed-in session\nGoal: Sign out through the profile or system entry point\nKey assertions:\n1. Sign-out returns to the sign-in page\n2. Restricted pages cannot be accessed afterward\nFailure screenshots: Retain the pages before and after sign-out\n',
                depends_on=None,
                on_failure="continue",
            ),
        ],
    },
    {
        "name": f"[{_ROLE_NAME}]-工单调度-Wave1主流程-测试环境",
        "description": (
            'Use the requirements to cover work order lists, filters, details, creation, editing, status transitions, dispatch, and export.'
        ),
        "tags": ['Sample project', 'Live regression', "wave1", 'Work order dispatch'],
        "steps": [
            _step(
                'Work order list and filter baseline',
                _TARGET_URL,
                f'\nRole: {_ROLE_NAME}\nPrerequisites: Signed in with work order dispatch permission\nEntry: Open `工单调度 > 工单管理` from the top-level menu\nGoal: Verify statistics, status tabs, search filters, pagination, and the export entry point\nKey assertions:\n1. Summary cards show total work orders, in-progress orders, completed-today counts, and related metrics\n2. Business type, work order type, urgency, creation time, and keyword filters work\n3. The platform orders tab is visible and switching to it refreshes the list\nFailure screenshots: Retain the statistics, filters, and list areas\n',
            ),
            _step(
                'Work order creation, editing, and details',
                _TARGET_URL,
                f'\nRole: {_ROLE_NAME}\nPrerequisites: Prepare the test-data prefix `{_TEST_DATA_PREFIX}_WO_`\nGoal: Create a test work order, inspect its details, then edit its title or urgency\nKey assertions:\n1. The created order can be found using its test prefix\n2. Details include order number, title, customer, address, status, and payment status\n3. After editing, the list and detail values agree\nRollback: Delete the order if supported; otherwise add it to the cleanup list\nFailure screenshots: Retain form validation, success feedback, and displayed details\n',
            ),
            _step(
                'Work order status transitions and dispatch',
                _TARGET_URL,
                f"\nRole: {_ROLE_NAME}\nPrerequisites: A test work order awaiting assignment or acceptance\nGoal: Verify at least one complete transition through dispatch, handling, acceptance, cancellation, or cancellation review\nKey assertions:\n1. Status transitions follow the requirements, with clear feedback for invalid states\n2. Dispatch or handling updates the order's handling history\n3. Unavailable batch operations show clear feedback and never fail silently\nFailure screenshots: Retain states before and after the transition and handling history\n",
                on_failure="continue",
            ),
        ],
    },
    {
        "name": f"[{_ROLE_NAME}]-智慧物业-Wave1社区公告报事-测试环境",
        "description": 'Cover frequent queries and writes in community/property management, incident reporting, repairs, and announcements.',
        "tags": ['Sample project', 'Live regression', "wave1", 'Property management', 'Announcements and incidents'],
        "steps": [
            _step(
                'Community and property list baseline',
                _TARGET_URL,
                f'\nRole: {_ROLE_NAME}\nPrerequisites: Signed in with property-module permissions\nEntry: `智慧物业 > 小区/社区管理` and `物业管理`\nGoal: Verify community lists, building/unit entry points, pagination, search, and detail entry points\nKey assertions:\n1. Community lists load without obvious misalignment or blank areas\n2. Filtering and pagination update the results\n3. Unit and owner information entry points are visible and open details\nFailure screenshots: Retain lists, filters, and detail entry points\n',
            ),
            _step(
                'Incident, repair, and announcement flows',
                _TARGET_URL,
                f'\nRole: {_ROLE_NAME}\nPrerequisites: Prepare `{_TEST_DATA_PREFIX}_NOTICE_` or `{_TEST_DATA_PREFIX}_REPORT_` test data\nEntry: `智慧物业 > 报事/公告`\nGoal: Verify incident lists and handling, and announcement creation, editing, publishing, or unpublishing\nKey assertions:\n1. Lists support queries, filters, and details\n2. Created or edited records appear correctly in the list\n3. Publication state agrees between the list and details\nRollback: Delete test announcements or add them to the cleanup list\nFailure screenshots: Retain creation forms, success feedback, and status changes\n',
                on_failure="continue",
            ),
        ],
    },
    {
        "name": f"[{_ROLE_NAME}]-智慧物业-Wave2停车安防能耗-测试环境",
        "description": 'Cover asset-management queries, details, and status changes for parking, security, and energy use.',
        "tags": ['Sample project', 'Live regression', "wave2", 'Property management', 'Parking', 'Security', 'Energy use'],
        "steps": [
            _step(
                'Parking contracts and entry/exit records',
                _TARGET_URL,
                f'\nRole: {_ROLE_NAME}\nPrerequisites: Parking-module permissions and `{_TEST_DATA_PREFIX}_PK_` test contract data\nEntry: `智慧物业 > 智能停车`\nGoal: Verify parking space lists, details, renewal/termination, entry/exit dialogs, and export\nKey assertions:\n1. License plate, parking space, contract status, and fee status fields are complete\n2. Renewal or termination updates the list status\n3. Entry/exit dialogs open with complete data structures\nFailure screenshots: Retain lists, dialogs, and status changes\n',
            ),
            _step(
                'Security and energy overview',
                _TARGET_URL,
                f'\nRole: {_ROLE_NAME}\nPrerequisites: Determine whether the role has the energy module enabled; record a configuration difference if it is disabled\nEntry: `智慧物业 > 安防监控` and `能耗管理`\nGoal: Verify device lists, geofences, energy data tables, and visibility rules\nKey assertions:\n1. Security lists and geofence entry points are available\n2. Enabled energy modules expose energy lists/statistics; disabled modules hide menus appropriately or explain the restriction\n3. No blank pages, broken links, or severe console errors occur\nFailure screenshots: Retain module visibility and error states\n',
                on_failure="continue",
            ),
        ],
    },
    {
        "name": f"[{_ROLE_NAME}]-养老管理-Wave3老人设备告警-测试环境",
        "description": 'Cover senior care flows for resident records, devices, alerts, and handling history.',
        "tags": ['Sample project', 'Live regression', "wave3", 'Senior care'],
        "steps": [
            _step(
                'Senior resident lists and record creation',
                _TARGET_URL,
                f'\nRole: {_ROLE_NAME}\nPrerequisites: Senior care permissions and `{_TEST_DATA_PREFIX}_ELDER_` test resident data\nEntry: `养老管理 > 老人信息管理`\nGoal: Verify filtering, masked display, creation/editing, and detail navigation\nKey assertions:\n1. Names and contact details are masked by default\n2. After creation or editing, lists and details agree\n3. Linked community, care level, and emergency contact values display correctly\nRollback: Delete test resident records or add them to the cleanup list\nFailure screenshots: Retain masked lists, details, and successful edits\n',
            ),
            _step(
                'Device and alert handling',
                _TARGET_URL,
                f'\nRole: {_ROLE_NAME}\nPrerequisites: Viewable test devices or alert records\nEntry: `养老管理 > 设备管理` and `告警管理`\nGoal: Verify device details, online status, alert lists, handling, and traceable history\nKey assertions:\n1. Device details open with complete fields\n2. Handling an alert changes its status and records the action\n3. Failures, batch operations, and multiselect actions give clear feedback\nFailure screenshots: Retain device details and alerts before and after handling\n',
                on_failure="continue",
            ),
        ],
    },
    {
        "name": f"[{_ROLE_NAME}]-系统管理-Wave4个人中心权限差异-测试环境",
        "description": 'Cover profiles, password changes, role-specific menu permissions, and configuration reads.',
        "tags": ['Sample project', 'Live regression', "wave4", 'System administration'],
        "steps": [
            _step(
                'Profile and password changes',
                _TARGET_URL,
                f'\nRole: {_ROLE_NAME}\nPrerequisites: Signed in with a recoverable test-password strategy\nEntry: Profile / user details\nGoal: Verify personal information, the password-change form, and session continuity\nKey assertions:\n1. The profile is accessible\n2. Password rules and validation messages are clear\n3. If the password is changed, restore the original password at the end\nFailure screenshots: Retain the profile and password validation states\n',
            ),
            _step(
                'Menu permissions and system configuration reads',
                _TARGET_URL,
                f'\nRole: {_ROLE_NAME}\nPrerequisites: A business-operations account, without unrestricted administrator permissions\nGoal: Verify role-visible and hidden menus and system configuration reads\nKey assertions:\n1. Only menus allowed for the role are shown\n2. Unauthorized pages cannot be accessed directly or show a clear restriction\n3. Configuration pages load only data permitted for the role\nFailure screenshots: Retain the menu tree and permission-denied feedback\n',
                on_failure="continue",
            ),
        ],
    },
]


_SAMPLE_PLATFORM_GATE_RULES = [
    {
        "name": "sample_platform_login_success_gate",
        "description": 'The entire primary sign-in flow must pass.',
        "metric": "login_success_rate",
        "operator": ">=",
        "threshold": 1.0,
        "severity": "blocking",
    },
    {
        "name": "sample_platform_core_flow_pass_gate",
        "description": 'The core business flow pass rate must reach 95%.',
        "metric": "core_flow_pass_rate",
        "operator": ">=",
        "threshold": 0.95,
        "severity": "blocking",
    },
    {
        "name": "sample_platform_blocking_bug_gate",
        "description": 'No blocking defects are allowed in the initial regression.',
        "metric": "blocking_bug_count",
        "operator": "<=",
        "threshold": 0,
        "severity": "blocking",
    },
    {
        "name": "sample_platform_unexplained_5xx_gate",
        "description": 'No unexplained 5xx errors are allowed.',
        "metric": "unexplained_5xx_count",
        "operator": "<=",
        "threshold": 0,
        "severity": "blocking",
    },
    {
        "name": "sample_platform_critical_ui_error_gate",
        "description": 'Key pages must have no blank pages, broken links, or severe console errors.',
        "metric": "critical_ui_error_count",
        "operator": "<=",
        "threshold": 0,
        "severity": "blocking",
    },
]


def list_playbooks() -> list[dict[str, Any]]:
    return [
        {
            "playbook_id": PLAYBOOK_ID_SAMPLE_PLATFORM_FIRST_REGRESSION,
            "name": 'Sample Enterprise Platform Initial Live Regression',
            "target_url": _TARGET_URL,
            "project_name": 'Sample Enterprise Platform',
            "recommended_test_types": ["ui_e2e", "business_flow", "api_rest", "data_validation"],
        },
        get_sample_platform_platform_catalog_entry(),
    ]


def get_requirement_playbook(playbook_id: str) -> dict[str, Any] | None:
    if playbook_id == PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE:
        return get_sample_platform_platform_requirement_playbook()
    if playbook_id != PLAYBOOK_ID_SAMPLE_PLATFORM_FIRST_REGRESSION:
        return None

    references = [
        {
            "title": doc["title"],
            "content": doc["content"],
            "role": doc["role"],
            "relative_path": doc["relative_path"],
            "local_path": doc["local_path"],
            "exists": doc["exists"],
        }
        for doc in _SAMPLE_PLATFORM_DOCS
        if doc["content"].strip()
    ]

    doc_sources = [
        {
            "title": doc["title"],
            "role": doc["role"],
            "relative_path": doc["relative_path"],
            "local_path": doc["local_path"],
            "exists": doc["exists"],
        }
        for doc in _SAMPLE_PLATFORM_DOCS
    ]

    return {
        "playbook_id": PLAYBOOK_ID_SAMPLE_PLATFORM_FIRST_REGRESSION,
        "project_name": 'Sample Enterprise Platform',
        "title": 'Sample Enterprise Platform Initial Live Regression',
        "content": _build_requirement_content(),
        "references": references,
        "document_sources": doc_sources,
        "target_url": _TARGET_URL,
        "repositories": [
            {
                "label": 'Frontend repository',
                "url": _FRONTEND_REPO_URL,
                "local_path": str(_deployed_repo_path("sample-product-qd")),
            },
            {
                "label": 'Backend repository',
                "url": _BACKEND_REPO_URL,
                "local_path": str(_deployed_repo_path("sample-product-hd")),
            },
            {
                "label": 'Requirements repository',
                "url": _DOCS_REPO_URL,
                "local_path": str(_docs_repo_path()),
            },
        ],
        "waves": deepcopy(_SAMPLE_PLATFORM_WAVES),
        "recommended_test_types": ["ui_e2e", "business_flow", "api_rest", "data_validation"],
        "naming_convention": {
            "scenario": '[role]-[module]-[scenario]-[environment]',
            "test_data_prefix": _TEST_DATA_PREFIX,
        },
        "notes": [
            'Run Wave 0 first, then continue through Waves 1–4.',
            'Capture business API requests during UI regression before adding them to API Workbench.',
            'Record differences between requirements and live behavior as requirements drift; do not automatically label them defects.',
        ],
    }


def get_scenario_playbook(playbook_id: str) -> list[dict[str, Any]]:
    if playbook_id == PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE:
        return get_sample_platform_platform_scenario_playbook()
    if playbook_id != PLAYBOOK_ID_SAMPLE_PLATFORM_FIRST_REGRESSION:
        return []
    return deepcopy(_SAMPLE_PLATFORM_SCENARIOS)


def get_quality_gate_rules(playbook_id: str) -> list[dict[str, Any]]:
    if playbook_id == PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE:
        return get_sample_platform_platform_quality_gate_rules()
    if playbook_id != PLAYBOOK_ID_SAMPLE_PLATFORM_FIRST_REGRESSION:
        return []
    return deepcopy(_SAMPLE_PLATFORM_GATE_RULES)


def get_test_data_convention(playbook_id: str) -> dict[str, Any] | None:
    if playbook_id == PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE:
        return get_sample_platform_platform_test_data_convention()
    if playbook_id != PLAYBOOK_ID_SAMPLE_PLATFORM_FIRST_REGRESSION:
        return None
    return {
        "playbook_id": playbook_id,
        "prefix": _TEST_DATA_PREFIX,
        "cleanup_policy": 'Delete removable test objects at the end; add nonremovable objects to the cleanup list.',
        "recommended_entities": ['Work orders', 'Announcements', 'Parking contracts', 'Senior resident records'],
    }


def get_playbook_catalog_entry(playbook_id: str) -> dict[str, Any] | None:
    for item in list_playbooks():
        if item["playbook_id"] == playbook_id:
            return deepcopy(item)
    return None
