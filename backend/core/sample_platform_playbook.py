# -*- coding: utf-8 -*-
'\nSample project platform prototype test package\n'
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from pathlib import Path
import re
from typing import Any

from core.config import Config


PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE = "sample-platform-prototype"

_PROJECT_NAME = 'Sample Project Platform'
_PLAYBOOK_TITLE = 'Sample Project Platform Prototype Test Package'
_DOCS_REPO_URL = "https://example.com/example-org/sample_platform.git"
_PLATFORM_FRONTEND_REPO_URL = "https://example.com/example-org/sample-product-qdpt.git"
_PLATFORM_BACKEND_REPO_URL = "https://example.com/example-org/sample-product-hd.git"
_PROTOTYPE_RELATIVE_PATH = "docx/XQ/Second/html/示例项目大平台htmlV1.0"
# Preserve scenario identity, module keys, prototype selectors, and external asset paths.
_SCENARIO_PREFIX = "[平台管理员角色]-"
_ARTIFACT_PREFIX = "SAMPLE_PLATFORM_PROTO"

_PLAYBOOK_TEST_TYPES = [
    "ui_e2e",
    "business_flow",
    "data_validation",
    "visual_regression",
]

_MODULE_BLUEPRINTS = [
    {
        "module_name": "登录与认证",
        "doc_title": 'Login and Authentication',
        "relative_path": "docx/XQ/Second/示例项目大平台需求/01-登录与认证模块.md",
        "role": "primary",
        "focus": 'Platform administrator sign-in, CAPTCHA, platform menu loading after sign-in, and isolation between platform and enterprise sign-in',
        "state_focus": 'Role isolation, lockout after failures, and login audit records',
        "boundary_focus": 'Required fields, errors, CAPTCHA refresh, and repeated failure handling',
        "critical_page_names": {"平台管理员登录"},
    },
    {
        "module_name": "企业管理",
        "doc_title": 'Enterprise Management Requirements',
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/01_企业管理_需求.md",
        "role": "reference",
        "focus": 'Assisted enterprise onboarding, enterprise list, information review, plan review, and key/contract dialogs',
        "state_focus": 'Enterprise and review status transitions, and visibility of key actions',
        "boundary_focus": 'Multistep form validation, termination confirmation, and delete/edit restrictions',
        "critical_page_names": {"企业列表页", "企业入驻代办表单", "企业详情页"},
    },
    {
        "module_name": "站点管理",
        "doc_title": 'Site Management Requirements',
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/02_站点管理_需求.md",
        "role": "reference",
        "focus": 'Site list and details, community management, site enable/disable actions, and deletion constraints',
        "state_focus": 'Site enable/disable status, linked community lists, and enterprise assignment visibility',
        "boundary_focus": 'Empty-site deletion restrictions, form validation, and disable messages',
        "critical_page_names": {"站点列表页", "站点详情页", "社区管理列表（站点子页）"},
    },
    {
        "module_name": "服务管理",
        "doc_title": 'Service Management Requirements',
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/03_服务管理_需求.md",
        "role": "reference",
        "focus": 'Service publication review, review details, published services, and service category tree',
        "state_focus": 'Approval/rejection transitions, published service status, and category-tree permissions',
        "boundary_focus": 'Required review comments, category creation/edit validation, empty states, and error states',
        "critical_page_names": {"服务上架审核列表", "服务上架审核详情", "已上架服务列表"},
    },
    {
        "module_name": "商品管理",
        "doc_title": 'Product Management Requirements',
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/04_商品管理_需求.md",
        "role": "reference",
        "focus": 'Product review list and details, SKU display, category tree, and rereview rules',
        "state_focus": 'Product review status transitions, removal for violations, and category visibility',
        "boundary_focus": 'Empty SKU states, image previews, and required rejection comments',
        "critical_page_names": {"商品上架审核列表", "商品上架审核详情", "已上架商品列表"},
    },
    {
        "module_name": "订单路由与监控",
        "doc_title": 'Order Routing and Monitoring Requirements',
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/05_订单路由与监控_需求.md",
        "role": "reference",
        "focus": 'Order monitoring and details, routing records, exception handling, and large-screen dashboards',
        "state_focus": 'Exception states, support intervention entry points, and traceable routing rules',
        "boundary_focus": 'Empty filter results, dashboard refresh, and required exception-handling notes',
        "critical_page_names": {"订单监控列表", "订单详情页", "订单大屏看板"},
    },
    {
        "module_name": "财务结算管理",
        "doc_title": 'Financial Settlement Requirements',
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/06_财务结算管理_需求.md",
        "role": "reference",
        "focus": 'Transaction data, service-fee bills, refund data, and financial dashboards',
        "state_focus": 'Bill status display, linked refund data, and dashboard metric definitions',
        "boundary_focus": 'Empty bill states, export, populated detail fields, and errors',
        "critical_page_names": {"交易数据列表", "服务费账单列表", "财务统计看板"},
    },
    {
        "module_name": "消费者投诉处理",
        "doc_title": 'Consumer Complaint Handling Requirements',
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/07_消费者投诉处理_需求.md",
        "role": "reference",
        "focus": 'Complaint list, detail processing, penalty records, and the complete resolution workflow',
        "state_focus": 'Pending/in-progress/completed transitions and synchronized penalty records',
        "boundary_focus": 'Required handling notes, exception messages, and read-only states',
        "critical_page_names": {"投诉列表页", "投诉详情/处理页"},
    },
    {
        "module_name": "消费者中心",
        "doc_title": 'Consumer Center Requirements',
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/08_消费者中心_需求.md",
        "role": "reference",
        "focus": 'Consumer list and details, tag management, blacklist, and data ownership',
        "state_focus": 'Tag and blacklist states, and cross-enterprise data definitions',
        "boundary_focus": 'Masked data display, empty states, read-only fields, and export',
        "critical_page_names": {"消费者列表页", "消费者详情页", "黑名单管理页"},
    },
    {
        "module_name": "会员与营销",
        "doc_title": 'Membership and Marketing Requirements',
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/09_会员与营销_需求.md",
        "role": "reference",
        "focus": 'Membership levels, points rules, coupons, campaigns, and campaign review',
        "state_focus": 'Campaign and coupon states, and visibility of review actions',
        "boundary_focus": 'Form validation, time-range constraints, and empty statistics',
        "critical_page_names": {"会员等级管理", "优惠券列表页", "营销活动列表"},
    },
    {
        "module_name": "小程序管理",
        "doc_title": 'Mini App Management Requirements',
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/10_小程序管理_需求.md",
        "role": "reference",
        "focus": 'Ad placements, category-page configuration, campaign-page configuration, and platform announcements',
        "state_focus": 'Publication status, configuration placement, and page-section visibility',
        "boundary_focus": 'Upload validation, ordering rules, empty states, and fallback messages',
        "critical_page_names": {"广告位管理", "分类页配置", "活动页配置"},
    },
    {
        "module_name": "数据统计与报表",
        "doc_title": 'Statistics and Reporting Requirements',
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/11_数据统计与报表_需求.md",
        "role": "reference",
        "focus": 'Global operations and property dashboards, enterprise comparisons, and trend analysis',
        "state_focus": 'Dashboard refresh, filter definitions, and time-range switching',
        "boundary_focus": 'Empty chart containers, no-data messages, and loading states',
        "critical_page_names": {"全局经营看板", "智慧物业数据看板", "趋势分析"},
    },
    {
        "module_name": "加盟管理",
        "doc_title": 'Franchise Management Requirements',
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/12_加盟管理_需求.md",
        "role": "reference",
        "focus": 'Franchise participant list, registration and details, franchise orders, and withdrawal review',
        "state_focus": 'Franchise participant status, withdrawal review status, and linked orders',
        "boundary_focus": 'Registration form validation, review comments, and empty states',
        "critical_page_names": {"加盟人员列表", "加盟人员详情", "加盟人员提现审核"},
    },
    {
        "module_name": "商家对接管理",
        "doc_title": 'Merchant Integration Requirements',
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/13_商家对接管理_需求.md",
        "role": "reference",
        "focus": 'Merchant list and details, site assignment, and merchant dashboards',
        "state_focus": 'Site assignment and merchant states, and dashboard metric definitions',
        "boundary_focus": 'Assignment-dialog validation, unauthorized actions, and empty states',
        "critical_page_names": {"商家列表页", "商家详情页", "商家数据监控看板"},
    },
    {
        "module_name": "培训课程管理",
        "doc_title": 'Training Course Management Requirements',
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/14_培训课程管理_需求.md",
        "role": "reference",
        "focus": 'Course categories, lists and editing, content management, review, distribution, question banks, exams, orders, and statistics',
        "state_focus": 'Course review, distribution, exam, and order states',
        "boundary_focus": 'Chapter validation, empty question banks, and course publication/removal messages',
        "critical_page_names": {"课程列表", "新增/编辑课程", "课程审核列表+详情"},
    },
    {
        "module_name": "系统管理",
        "doc_title": 'System Management Requirements',
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/15_系统管理_需求.md",
        "role": "reference",
        "focus": 'Administrators, role permission trees, operation logs, login logs, and system configuration',
        "state_focus": 'Role-based permission visibility, enabled/disabled states, and log states',
        "boundary_focus": 'Password rules, partially selected permission trees, and log-clearing confirmation',
        "critical_page_names": {"管理员列表", "角色管理列表", "系统配置页"},
    },
]

_PLAYBOOK_SUMMARY_DOCS = [
    {
        "title": 'Sample Project Platform - Module Overview',
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/00_模块总览.md",
        "role": "primary",
    },
    {
        "title": 'Sample Project Platform - Project Overview and Architecture',
        "relative_path": "docx/XQ/Second/示例项目大平台需求/00-项目总览与平台架构.md",
        "role": "reference",
    },
]

_PLATFORM_WAVES = [
    {"id": "wave0", "name": 'Wave 0: Login and Entry Baseline', "focus": ['Login and authentication', 'Platform menu loading', 'Platform and enterprise sign-in isolation']},
    {"id": "wave1", "name": 'Wave 1: Core Governance Workflows', "focus": ['Enterprise management', 'Site management', 'Service management', 'Product management']},
    {"id": "wave2", "name": 'Wave 2: Transactions and Oversight', "focus": ['Order routing and monitoring', 'Financial settlement', 'Consumer complaint handling']},
    {"id": "wave3", "name": 'Wave 3: Operations and Growth', "focus": ['Consumer center', 'Membership and marketing', 'Mini app management', 'Statistics and reporting']},
    {"id": "wave4", "name": 'Wave 4: Organization and Platform Governance', "focus": ['Franchise management', 'Merchant integration', 'Training course management', 'System management']},
]

_CROSS_MODULE_SCENARIOS = [
    {
        "name": f"{_SCENARIO_PREFIX}跨模块-企业入驻到站点分配-原型阶段",
        "description": 'Connect assisted enterprise onboarding, plan review, site assignment, and community management to verify the complete core structure.',
        "tags": ['Sample Project Platform', 'Prototype testing', 'Cross-module', 'Enterprise onboarding', 'Site assignment'],
        "focus": [
            'The assisted enterprise onboarding form has a complete multistep structure',
            'Plan purchase review connects to key and contract dialogs',
            'Site lists and community management provide a configuration path from enterprises to geographic units',
        ],
    },
    {
        "name": f"{_SCENARIO_PREFIX}跨模块-服务审核上架到小程序展示-原型阶段",
        "description": 'Connect service review, published services, and mini app configuration to verify the service publication workflow.',
        "tags": ['Sample Project Platform', 'Prototype testing', 'Cross-module', 'Service review', 'Mini app management'],
        "focus": [
            'Service review lists and detail views form a consistent structure',
            'Published service pages reflect review outcomes',
            'Category pages, campaign pages, and ad placements provide space to display published services',
        ],
    },
    {
        "name": f"{_SCENARIO_PREFIX}跨模块-商品审核上架到商家对接-原型阶段",
        "description": 'Connect product review, merchant integration, product categories, and mini app presentation to verify the main product workflow.',
        "tags": ['Sample Project Platform', 'Prototype testing', 'Cross-module', 'Product review', 'Merchant integration'],
        "focus": [
            'Product review details include image, SKU, and merchant information areas',
            'Merchant details and site assignment dialogs support merchant product sources',
            'Product category trees and platform display configuration have no structural gaps',
        ],
    },
    {
        "name": f"{_SCENARIO_PREFIX}跨模块-订单路由到财务与投诉闭环-原型阶段",
        "description": 'Connect order monitoring, order exceptions, financial settlement, and complaints to verify the complete oversight workflow.',
        "tags": ['Sample Project Platform', 'Prototype testing', 'Cross-module', 'Order routing', 'Finance', 'Complaints'],
        "focus": [
            'Order detail pages include routing records and operation logs',
            'Financial settlement pages support order, refund, and bill data',
            'Complaint handling connects order exceptions and penalty records into a complete resolution workflow',
        ],
    },
]

_QUALITY_GATE_RULES = [
    {
        "name": "sample_platform_platform_module_coverage_gate",
        "description": 'Module coverage must reach 100%.',
        "metric": "module_coverage_rate",
        "operator": ">=",
        "threshold": 1.0,
        "severity": "blocking",
    },
    {
        "name": "sample_platform_platform_page_mapping_gate",
        "description": 'Page mapping must reach 95%.',
        "metric": "page_mapping_rate",
        "operator": ">=",
        "threshold": 0.95,
        "severity": "blocking",
    },
    {
        "name": "sample_platform_platform_critical_page_gate",
        "description": 'The number of missing critical pages must be 0.',
        "metric": "critical_page_missing_count",
        "operator": "<=",
        "threshold": 0,
        "severity": "blocking",
    },
    {
        "name": "sample_platform_platform_blocking_gap_gate",
        "description": 'The number of blocking prototype discrepancies must be 0.',
        "metric": "blocking_prototype_gap_count",
        "operator": "<=",
        "threshold": 0,
        "severity": "blocking",
    },
    {
        "name": "sample_platform_platform_critical_field_gate",
        "description": 'The number of missing critical fields must be 0.',
        "metric": "critical_field_missing_count",
        "operator": "<=",
        "threshold": 0,
        "severity": "blocking",
    },
    {
        "name": "sample_platform_platform_state_transition_gate",
        "description": 'The number of missing critical state transitions must be 0.',
        "metric": "critical_state_transition_gap_count",
        "operator": "<=",
        "threshold": 0,
        "severity": "blocking",
    },
]


def _repo_root() -> Path:
    return Path(Config.PROJECT_ROOT).resolve().parent


def _deployed_repo_path(repo_name: str) -> Path:
    return _repo_root() / "data" / "deploy" / repo_name


def _required_doc_relative_paths() -> list[str]:
    paths = [item["relative_path"] for item in _PLAYBOOK_SUMMARY_DOCS]
    paths.extend(item["relative_path"] for item in _MODULE_BLUEPRINTS)
    return paths


def _docs_repo_candidates() -> list[dict[str, Any]]:
    candidates = [
        {
            "source_id": "deploy_repo",
            "title": 'Deployed documentation repository',
            "root_path": _deployed_repo_path("sample_platform"),
            "priority": 20,
        },
        {
            "source_id": "local_download_repo",
            "title": 'Local downloaded repository',
            "root_path": _repo_root() / "daice" / "sample_platform-main",
            "priority": 10,
        },
    ]

    required_docs = _required_doc_relative_paths()
    for candidate in candidates:
        root_path = candidate["root_path"]
        prototype_root = root_path / Path(_PROTOTYPE_RELATIVE_PATH)
        prototype_file_count = len(list(prototype_root.rglob("*.html"))) if prototype_root.exists() else 0
        candidate["doc_count"] = sum(1 for relative in required_docs if (root_path / relative).exists())
        candidate["prototype_exists"] = prototype_root.exists()
        candidate["prototype_file_count"] = prototype_file_count
    return candidates


def _resolved_docs_repo() -> dict[str, Any]:
    candidates = _docs_repo_candidates()
    return max(
        candidates,
        key=lambda item: (
            item.get("doc_count", 0),
            item.get("prototype_file_count", 0),
            item.get("priority", 0),
        ),
    )


def _docs_repo_path() -> Path:
    return _resolved_docs_repo()["root_path"]


def _safe_read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _doc_entry(relative_path: str, title: str, role: str, module_name: str = "") -> dict[str, Any]:
    source = _resolved_docs_repo()
    full_path = source["root_path"] / relative_path
    return {
        "title": title,
        "role": role,
        "module_name": module_name,
        "relative_path": relative_path.replace("\\", "/"),
        "local_path": str(full_path),
        "exists": full_path.exists(),
        "source_id": source["source_id"],
        "source_title": source["title"],
        "content": _safe_read_text(full_path),
    }


def _platform_doc_entries() -> list[dict[str, Any]]:
    entries = [
        _doc_entry(item["relative_path"], item["title"], item["role"])
        for item in _PLAYBOOK_SUMMARY_DOCS
    ]
    entries.extend(
        _doc_entry(
            item["relative_path"],
            f"Sample Project Platform - {item['module_name']}",
            item["role"],
            item["module_name"],
        )
        for item in _MODULE_BLUEPRINTS
    )
    return entries


def _prototype_dir_candidates() -> list[dict[str, Any]]:
    assets = []
    for source in _docs_repo_candidates():
        prototype_root = source["root_path"] / Path(_PROTOTYPE_RELATIVE_PATH)
        assets.append(
            {
                "asset_id": f"sample-platform-prototype-{source['source_id']}",
                "title": f"Sample Project Platform HTML prototype directory ({source['title']})",
                "role": "prototype",
                "relative_path": _PROTOTYPE_RELATIVE_PATH,
                "local_path": str(prototype_root),
                "exists": prototype_root.exists(),
                "asset_scope": source["source_id"],
                "source_title": source["title"],
            }
        )

    workspace_path = _repo_root() / Path(_PROTOTYPE_RELATIVE_PATH)
    assets.append(
        {
            "asset_id": "sample-platform-prototype-workspace",
            "title": 'Sample Project Platform HTML prototype directory (current workspace)',
            "role": "prototype",
            "relative_path": _PROTOTYPE_RELATIVE_PATH,
            "local_path": str(workspace_path),
            "exists": workspace_path.exists(),
            "asset_scope": "workspace",
            "source_title": 'Current workspace',
        }
    )
    return assets


def _normalize_token(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", (value or "").lower())


def _tokenize_page_match(module_name: str, page_name: str, route: str) -> list[str]:
    route_segments = [segment for segment in route.strip("/").split("/") if segment and not segment.startswith(":")]
    simplified_page_name = (
        page_name.replace("新增/编辑", "")
        .replace("新增", "")
        .replace("编辑", "")
        .replace("列表页", "列表")
        .replace("详情页", "详情")
        .replace("管理页", "管理")
        .replace("弹窗", "")
        .strip()
    )
    raw_tokens = {
        page_name,
        simplified_page_name,
        page_name.replace("页", ""),
        page_name.replace("弹窗", ""),
        page_name.replace("列表（树形）", "列表"),
        simplified_page_name.replace("页", ""),
        module_name + page_name.replace("页", ""),
        module_name + simplified_page_name.replace("页", ""),
        route,
        route.strip("/"),
        "/".join(route_segments),
        "-".join(route_segments),
        "".join(route_segments),
        *route_segments,
    }
    if "登录" in page_name or "login" in route.lower():
        raw_tokens.update({"登录", "login"})
    tokens = []
    for token in raw_tokens:
        normalized = _normalize_token(token)
        if len(normalized) >= 2:
            tokens.append(normalized)
    return sorted(set(tokens), key=len, reverse=True)


def _prototype_files() -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    candidates = _prototype_dir_candidates()
    active_candidate = None
    active_file_count = -1
    for candidate in candidates:
        if not candidate["exists"]:
            continue
        file_count = len(list(Path(candidate["local_path"]).rglob("*.html")))
        if file_count > active_file_count:
            active_candidate = candidate
            active_file_count = file_count
    if not active_candidate:
        return [], None

    prototype_root = Path(active_candidate["local_path"])
    files = []
    for file_path in sorted(prototype_root.rglob("*.html")):
        relative = file_path.relative_to(prototype_root).as_posix()
        content = _safe_read_text(file_path)
        files.append(
            {
                "title": file_path.stem,
                "relative_path": f"{_PROTOTYPE_RELATIVE_PATH}/{relative}",
                "local_path": str(file_path),
                "file_uri": file_path.resolve().as_uri(),
                "exists": True,
                "normalized_title": _normalize_token(file_path.stem),
                "normalized_path": _normalize_token(relative),
                "normalized_content": _normalize_token(content),
            }
        )

    return files, {
        **active_candidate,
        "file_count": len(files),
        "files": [item["relative_path"] for item in files[:20]],
    }


def _find_best_prototype_match(module_name: str, page_name: str, route: str, prototype_files: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not prototype_files:
        return None

    best_match: dict[str, Any] | None = None
    best_score = 0
    for candidate in prototype_files:
        title_path_haystack = f"{candidate['normalized_title']} {candidate['normalized_path']}"
        content_haystack = candidate.get("normalized_content", "")
        if candidate["title"] == "index" and "弹窗" not in page_name and "登录" not in page_name:
            content_haystack = ""
        score = 0
        for token in _tokenize_page_match(module_name, page_name, route):
            if not token:
                continue
            if token in title_path_haystack:
                score += len(token) * 4
            elif token in content_haystack:
                score += len(token)
        if "登录" in page_name and "login" in candidate["normalized_title"]:
            score += 100
        if "退出登录" in page_name and candidate["title"] == "index":
            score += 40
        if "个人信息" in page_name and candidate["title"] == "index":
            score += 40
        if score > best_score:
            best_score = score
            best_match = candidate

    return best_match if best_score > 0 else None


def _extract_page_table(content: str) -> list[dict[str, str]]:
    lines = content.splitlines()
    table_lines: list[str] = []
    in_page_section = False

    for line in lines:
        stripped = line.strip()
        if re.match(r"^##\s*(二、|2\.)\s*页面清单$", stripped):
            in_page_section = True
            table_lines = []
            continue
        if in_page_section and stripped.startswith("## ") and table_lines:
            break
        if not in_page_section:
            continue
        if stripped.startswith("|"):
            table_lines.append(stripped)
        elif table_lines:
            break

    if len(table_lines) < 2:
        return []

    headers = [item.strip() for item in table_lines[0].strip("|").split("|")]
    rows = []
    for raw_line in table_lines[2:]:
        cells = [item.strip() for item in raw_line.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows


def _infer_page_type(page_name: str, row: dict[str, str]) -> str:
    for key in ("页面类型", "类型"):
        value = row.get(key, "").strip()
        if value and value != "-":
            return value
    if "登录" in page_name:
        return "登录页"
    if "看板" in page_name:
        return "看板页"
    if "弹窗" in page_name:
        return "弹窗"
    if "详情" in page_name:
        return "详情页"
    if "新增" in page_name or "编辑" in page_name or "表单" in page_name:
        return "表单页"
    return 'Page'


def _recommended_test_types(page_type: str) -> list[str]:
    if "登录" in page_type:
        return ["ui_e2e", "data_validation", "visual_regression"]
    if "列表" in page_type:
        return ["ui_e2e", "business_flow", "data_validation"]
    if "详情" in page_type:
        return ["ui_e2e", "business_flow", "data_validation"]
    if "表单" in page_type or "弹窗" in page_type:
        return ["ui_e2e", "business_flow", "data_validation"]
    if "看板" in page_type:
        return ["ui_e2e", "visual_regression", "data_validation"]
    return ["ui_e2e", "business_flow"]


def _key_assertions_for_page(page_type: str, page_name: str) -> list[str]:
    if "登录" in page_type:
        return [
            'The page includes core controls for username, password, CAPTCHA, and sign-in',
            'The platform menu loading path after sign-in matches requirements',
            'Errors, CAPTCHA refresh, and failure-lockout rules provide explicit feedback',
        ]
    if "列表" in page_type:
        return [
            'Search, table, pagination, and action-button areas are complete',
            'Key columns, status labels, and action visibility match requirements',
            'Empty and loading states, confirmation dialogs, and export/filter entry points are defined',
        ]
    if "详情" in page_type:
        return [
            'Detail cards, timelines, logs, and status sections match requirements',
            'Primary action buttons, review entry points, or related-record sections are present',
            'Key fields are fully populated, with exception and read-only states explained',
        ]
    if "表单" in page_type or "弹窗" in page_type:
        return [
            'Required fields, defaults, grouped layouts, and validation rules are complete',
            'Submit, cancel, previous/next, and other key buttons are present',
            'Validation failure, close confirmation, and success feedback paths are explicit',
        ]
    if "看板" in page_type:
        return [
            'Dashboard sections, chart containers, metric cards, and real-time areas are complete',
            'Refresh messages, date switching, no-data messages, and loading states are defined',
            'The key visual structure matches the required layout sections',
        ]
    return [
        f'{page_name} has complete entry points, main areas, and key action structures',
        'Page states, messages, and interaction feedback are defined',
        'Routes and menu entry points match the requirements document',
    ]


def _build_page_mappings() -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    doc_entries = _platform_doc_entries()
    doc_map = {entry["module_name"]: entry for entry in doc_entries if entry["module_name"]}
    prototype_files, active_prototype_asset = _prototype_files()
    prototype_assets = []
    for asset in _prototype_dir_candidates():
        file_count = 0
        if active_prototype_asset and asset["asset_id"] == active_prototype_asset["asset_id"]:
            file_count = active_prototype_asset.get("file_count", 0)
        prototype_assets.append({**asset, "file_count": file_count})

    page_mappings: list[dict[str, Any]] = []
    module_coverage = defaultdict(int)

    for blueprint in _MODULE_BLUEPRINTS:
        doc_entry = doc_map[blueprint["module_name"]]
        rows = _extract_page_table(doc_entry["content"])
        for index, row in enumerate(rows, 1):
            page_name = row.get("页面名称") or row.get("页面")
            route = row.get("页面路由") or row.get("路径") or "-"
            description = row.get("说明") or row.get("描述") or ""
            if not page_name:
                continue

            page_name = page_name.strip()
            route = route.strip().strip("`")
            page_type = _infer_page_type(page_name, row)
            prototype_match = _find_best_prototype_match(
                blueprint["module_name"],
                page_name,
                route,
                prototype_files,
            )
            critical = (
                page_name in blueprint["critical_page_names"]
                or index <= 2
                or "看板" in page_name
                or "登录" in page_name
            )
            page_mappings.append(
                {
                    "mapping_id": f"{PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE}-{blueprint['module_name']}-{index}",
                    "module_name": blueprint["module_name"],
                    "page_name": page_name,
                    "route": route,
                    "page_type": page_type,
                    "description": description.strip(),
                    "requirement_source": {
                        "title": doc_entry["title"],
                        "relative_path": doc_entry["relative_path"],
                        "local_path": doc_entry["local_path"],
                        "exists": doc_entry["exists"],
                    },
                    "prototype_source": {
                        "title": prototype_match["title"] if prototype_match else "",
                        "relative_path": prototype_match["relative_path"] if prototype_match else "",
                        "local_path": prototype_match["local_path"] if prototype_match else "",
                        "file_uri": prototype_match["file_uri"] if prototype_match else "",
                        "exists": bool(prototype_match),
                    },
                    "mapping_status": "mapped" if prototype_match else "pending_prototype",
                    "recommended_test_types": _recommended_test_types(page_type),
                    "key_assertions": _key_assertions_for_page(page_type, page_name),
                    "baseline_candidate": "登录" in page_type or any(token in page_type for token in ("列表", "表单", "详情", "看板")),
                    "critical": critical,
                }
            )
            module_coverage[blueprint["module_name"]] += 1

    total_pages = len(page_mappings)
    mapped_pages = sum(1 for item in page_mappings if item["prototype_source"]["exists"])
    critical_pages = sum(1 for item in page_mappings if item["critical"])
    critical_missing_pages = sum(1 for item in page_mappings if item["critical"] and not item["prototype_source"]["exists"])
    baseline_candidates = sum(1 for item in page_mappings if item["baseline_candidate"])

    summary = {
        "module_count": len(module_coverage),
        "total_pages": total_pages,
        "mapped_pages": mapped_pages,
        "mapping_rate": round(mapped_pages / total_pages, 4) if total_pages else 0,
        "critical_pages": critical_pages,
        "critical_missing_pages": critical_missing_pages,
        "baseline_candidates": baseline_candidates,
    }
    return page_mappings, summary, prototype_assets


def _build_asset_checks(mapping_summary: dict[str, Any], prototype_assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    docs = _platform_doc_entries()
    existing_docs = sum(1 for item in docs if item["exists"])
    prototype_asset = next((item for item in prototype_assets if item["exists"]), None)
    prototype_file_count = prototype_asset.get("file_count", 0) if prototype_asset else 0
    return [
        {
            "check_id": "platform_docs_ready",
            "label": 'Requirement document synchronization',
            "status": "success" if existing_docs == len(docs) else "warning",
            "message": f'Synchronized {existing_docs}/{len(docs)} platform requirement documents.',
            "value": f"{existing_docs}/{len(docs)}",
        },
        {
            "check_id": "platform_prototype_dir_ready",
            "label": 'Prototype directory synchronization',
            "status": "success" if prototype_asset else "warning",
            "message": (
                f"Prototype directory detected: {prototype_asset['local_path']}"
                if prototype_asset
                else f'No prototype directory detected. Synchronize {_PROTOTYPE_RELATIVE_PATH}'
            ),
            "value": prototype_asset["relative_path"] if prototype_asset else _PROTOTYPE_RELATIVE_PATH,
        },
        {
            "check_id": "platform_prototype_file_count",
            "label": 'Prototype file count',
            "status": "success" if prototype_file_count > 0 else "warning",
            "message": f'Currently detected {prototype_file_count} HTML prototype files.',
            "value": prototype_file_count,
        },
        {
            "check_id": "platform_page_mapping_rate",
            "label": 'Page mapping rate',
            "status": "success" if mapping_summary["mapping_rate"] >= 0.95 else "warning",
            "message": f"Mapped {mapping_summary['mapped_pages']}/{mapping_summary['total_pages']} pages.",
            "value": mapping_summary["mapping_rate"],
        },
        {
            "check_id": "platform_critical_page_gap",
            "label": 'Critical page gaps',
            "status": "success" if mapping_summary["critical_missing_pages"] == 0 else "warning",
            "message": f"There are still {mapping_summary['critical_missing_pages']} critical pages without matching HTML prototypes.",
            "value": mapping_summary["critical_missing_pages"],
        },
    ]


def _build_requirement_content(mapping_summary: dict[str, Any], asset_checks: list[dict[str, Any]]) -> str:
    module_lines = "\n".join(f"- {item['module_name']}: {item['focus']}" for item in _MODULE_BLUEPRINTS)
    asset_lines = "\n".join(f"- {item['label']}: {item['message']}" for item in asset_checks)
    return f"# Sample Project Platform Prototype Test Package\n\n## Project Purpose\n- System under test: Sample Project Platform administration system (Vue3 + Element Plus)\n- Method: Check consistency between requirements and HTML prototypes\n- Current mode: Complete prototype testing first; live-system integration is not enabled by default\n- Target repository: {_DOCS_REPO_URL}\n\n## Asset Checks\n{asset_lines}\n\n## Scope\n- Covers login and authentication plus 15 top-level business modules\n- Current page mapping: {mapping_summary['mapped_pages']}/{mapping_summary['total_pages']}\n- Critical page gaps: {mapping_summary['critical_missing_pages']}\n- Recommended visual baseline pages: {mapping_summary['baseline_candidates']}\n\n## Shared Checks\n- Complete menus and routes\n- Page layouts match the prototypes\n- Search areas, tables, pagination, dialogs, and drawers are present\n- Form fields, required fields, validation, and defaults are complete\n- Button visibility, permission markers, and state transitions match requirements\n- Empty, loading, and error states and confirmation dialogs are defined\n- Key visual structures match the main prototype framework\n\n## Module Inventory\n{module_lines}\n\n## Prototype Gates\n- module_coverage_rate = 1.0\n- page_mapping_rate >= 0.95\n- critical_page_missing_count <= 0\n- blocking_prototype_gap_count <= 0\n- critical_field_missing_count <= 0\n- critical_state_transition_gap_count <= 0\n"


def _primary_url_from_mapping(page_mappings: list[dict[str, Any]], module_name: str) -> str:
    candidates = [item for item in page_mappings if item["module_name"] == module_name]
    if not candidates:
        return "about:blank"
    with_file = next((item for item in candidates if item["prototype_source"]["exists"]), None)
    return with_file["prototype_source"]["file_uri"] if with_file else "about:blank"


def _module_pages_text(page_mappings: list[dict[str, Any]], module_name: str) -> str:
    names = [item["page_name"] for item in page_mappings if item["module_name"] == module_name][:3]
    return ", ".join(names) if names else 'Core pages'


def _build_module_scenarios(page_mappings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    for blueprint in _MODULE_BLUEPRINTS:
        url = _primary_url_from_mapping(page_mappings, blueprint["module_name"])
        pages_text = _module_pages_text(page_mappings, blueprint["module_name"])
        scenarios.extend(
            [
                {
                    "name": f"{_SCENARIO_PREFIX}{blueprint['module_name']}-页面结构检查-原型阶段",
                    "description": f"Check whether {blueprint['module_name']} menus, routes, page structure, and key sections match the requirements and prototypes.",
                    "tags": ['Sample Project Platform', 'Prototype testing', blueprint["module_name"], "structure"],
                    "steps": [
                        {
                            "name": f"{blueprint['module_name']} page structure check",
                            "url": url,
                            "instruction": (
                                f"Role: Platform prototype reviewer\nModule: {blueprint['module_name']}\nTarget pages: {pages_text}\nFocus: {blueprint['focus']}\nKey assertions:\n1. Top-level/secondary menus, page routes, and entry-point names match requirements\n2. Layouts contain the required search, list, detail, dialog, or dashboard sections\n3. If HTML prototypes have not been synchronized, record missing assets rather than classifying them directly as business defects"
                            ),
                            "mode": "smart",
                            "timeout": 120,
                            "on_failure": "continue",
                        }
                    ],
                },
                {
                    "name": f"{_SCENARIO_PREFIX}{blueprint['module_name']}-主操作检查-原型阶段",
                    "description": f"Check {blueprint['module_name']} core primary actions, button visibility, review paths, and state paths.",
                    "tags": ['Sample Project Platform', 'Prototype testing', blueprint["module_name"], "primary-flow"],
                    "steps": [
                        {
                            "name": f"{blueprint['module_name']} primary action check",
                            "url": url,
                            "instruction": (
                                f"Role: Platform prototype reviewer\nModule: {blueprint['module_name']}\nTarget pages: {pages_text}\nFocus: {blueprint['state_focus']}\nKey assertions:\n1. Visibility of primary buttons, action columns, review actions, and status labels matches requirements\n2. Detail, edit, review, and dashboard pages have explicit navigation or handoff relationships\n3. Prototypes define state transitions, permission differences, confirmation dialogs, and result feedback"
                            ),
                            "mode": "smart",
                            "timeout": 120,
                            "on_failure": "continue",
                        }
                    ],
                },
                {
                    "name": f"{_SCENARIO_PREFIX}{blueprint['module_name']}-异常边界检查-原型阶段",
                    "description": f"Check {blueprint['module_name']} validation rules, empty states, error states, and boundary messages.",
                    "tags": ['Sample Project Platform', 'Prototype testing', blueprint["module_name"], "boundary"],
                    "steps": [
                        {
                            "name": f"{blueprint['module_name']} exception and boundary check",
                            "url": url,
                            "instruction": (
                                f"Role: Platform prototype reviewer\nModule: {blueprint['module_name']}\nTarget pages: {pages_text}\nFocus: {blueprint['boundary_focus']}\nKey assertions:\n1. Required-field validation, defaults, errors, and boundary messages are defined\n2. Empty, unauthorized, and loading states, confirmation dialogs, and close feedback are identifiable\n3. Record blocking gaps, missing critical fields, and missing critical state transitions"
                            ),
                            "mode": "smart",
                            "timeout": 120,
                            "on_failure": "continue",
                        }
                    ],
                },
            ]
        )
    return scenarios


def _build_cross_module_scenarios(page_mappings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    default_url = _primary_url_from_mapping(page_mappings, "企业管理")
    scenarios = []
    for item in _CROSS_MODULE_SCENARIOS:
        scenarios.append(
            {
                "name": item["name"],
                "description": item["description"],
                "tags": item["tags"],
                "steps": [
                    {
                        "name": item["name"].split("-")[2] if "-" in item["name"] else 'Cross-module workflow check',
                        "url": default_url,
                        "instruction": (
                            f"Role: Platform prototype reviewer\nType: Cross-module prototype workflow check\nWorkflow objective: {item['description']}\nKey assertions:\n"
                            + "\n".join(f"{index}. {focus}" for index, focus in enumerate(item["focus"], 1))
                            + '\n4. Record missing pages, routes, or handoffs as prototype consistency discrepancies'
                        ),
                        "mode": "smart",
                        "timeout": 180,
                        "on_failure": "continue",
                    }
                ],
            }
        )
    return scenarios


def get_catalog_entry() -> dict[str, Any]:
    return {
        "playbook_id": PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE,
        "name": _PLAYBOOK_TITLE,
        "target_url": _PROTOTYPE_RELATIVE_PATH,
        "project_name": _PROJECT_NAME,
        "recommended_test_types": deepcopy(_PLAYBOOK_TEST_TYPES),
    }


def get_requirement_playbook() -> dict[str, Any]:
    doc_entries = _platform_doc_entries()
    page_mappings, mapping_summary, prototype_assets = _build_page_mappings()
    asset_checks = _build_asset_checks(mapping_summary, prototype_assets)
    references = [
        {
            "title": doc["title"],
            "content": doc["content"],
            "role": doc["role"],
            "relative_path": doc["relative_path"],
            "local_path": doc["local_path"],
            "exists": doc["exists"],
        }
        for doc in doc_entries
        if doc["content"].strip()
    ]
    target_url = next(
        (
            item["prototype_source"]["file_uri"]
            for item in page_mappings
            if item["module_name"] == "登录与认证" and item["prototype_source"]["exists"]
        ),
        f'Prototype directory awaiting synchronization: {_PROTOTYPE_RELATIVE_PATH}',
    )
    return {
        "playbook_id": PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE,
        "project_name": _PROJECT_NAME,
        "title": _PLAYBOOK_TITLE,
        "content": _build_requirement_content(mapping_summary, asset_checks),
        "references": references,
        "document_sources": [
            {
                "title": doc["title"],
                "role": doc["role"],
                "relative_path": doc["relative_path"],
                "local_path": doc["local_path"],
                "exists": doc["exists"],
            }
            for doc in doc_entries
        ],
        "prototype_assets": prototype_assets,
        "asset_checks": asset_checks,
        "page_mappings": page_mappings,
        "mapping_summary": mapping_summary,
        "target_url": target_url,
        "repositories": [
            {"label": 'Platform frontend repository', "url": _PLATFORM_FRONTEND_REPO_URL, "local_path": str(_deployed_repo_path("sample-product-qdpt"))},
            {"label": 'Shared backend repository', "url": _PLATFORM_BACKEND_REPO_URL, "local_path": str(_deployed_repo_path("sample-product-hd"))},
            {"label": 'Requirements and prototype repository', "url": _DOCS_REPO_URL, "local_path": str(_docs_repo_path())},
        ],
        "waves": deepcopy(_PLATFORM_WAVES),
        "recommended_test_types": deepcopy(_PLAYBOOK_TEST_TYPES),
        "naming_convention": {"scenario": '[Role]-[Module]-[Scenario]-[Environment]', "test_data_prefix": _ARTIFACT_PREFIX},
        "notes": [
            'This package checks consistency between requirements and HTML prototypes; live-system execution is not required by default.',
            'If prototypes have not been synchronized, mappings show pending_prototype. Add the assets before creating visual baselines.',
            'The page mapping inventory provides a shared source of truth for requirements, scenarios, and visual checks.',
        ],
    }


def get_scenario_playbook() -> list[dict[str, Any]]:
    page_mappings, _, _ = _build_page_mappings()
    scenarios = _build_module_scenarios(page_mappings)
    scenarios.extend(_build_cross_module_scenarios(page_mappings))
    return scenarios


def get_quality_gate_rules() -> list[dict[str, Any]]:
    return deepcopy(_QUALITY_GATE_RULES)


def get_test_data_convention() -> dict[str, Any]:
    return {
        "playbook_id": PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE,
        "prefix": _ARTIFACT_PREFIX,
        "cleanup_policy": 'Clean up screenshots, baselines, difference reports, and temporary prototype-check artifacts; preserve real business data.',
        "recommended_entities": ['Page mappings', 'Visual baselines', 'Difference screenshots', 'Prototype discrepancy reports'],
    }
