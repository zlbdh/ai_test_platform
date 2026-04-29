# -*- coding: utf-8 -*-
"""
示例项目大平台原型测试项目包
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from pathlib import Path
import re
from typing import Any

from core.config import Config


PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE = "sample-platform-prototype"

_PROJECT_NAME = "示例项目大平台"
_PLAYBOOK_TITLE = "示例项目大平台原型测试包"
_DOCS_REPO_URL = "https://example.com/example-org/sample_platform.git"
_PLATFORM_FRONTEND_REPO_URL = "https://example.com/example-org/sample-product-qdpt.git"
_PLATFORM_BACKEND_REPO_URL = "https://example.com/example-org/sample-product-hd.git"
_PROTOTYPE_RELATIVE_PATH = "docx/XQ/Second/html/示例项目大平台htmlV1.0"
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
        "doc_title": "登录与认证模块",
        "relative_path": "docx/XQ/Second/示例项目大平台需求/01-登录与认证模块.md",
        "role": "primary",
        "focus": "平台管理员登录入口、验证码、登录成功后平台菜单加载、平台与企业登录隔离",
        "state_focus": "角色隔离、失败锁定、登录日志留痕",
        "boundary_focus": "必填校验、错误提示、验证码刷新、连续失败处理",
        "critical_page_names": {"平台管理员登录"},
    },
    {
        "module_name": "企业管理",
        "doc_title": "企业管理需求",
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/01_企业管理_需求.md",
        "role": "reference",
        "focus": "企业入驻代办、企业列表、信息审核、套餐审核、密钥与合同弹窗",
        "state_focus": "企业状态流转、审核状态变化、关键操作显隐",
        "boundary_focus": "分步表单校验、终止二次确认、删除/编辑限制",
        "critical_page_names": {"企业列表页", "企业入驻代办表单", "企业详情页"},
    },
    {
        "module_name": "站点管理",
        "doc_title": "站点管理需求",
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/02_站点管理_需求.md",
        "role": "reference",
        "focus": "站点列表、站点详情、社区管理、站点启停与删除约束",
        "state_focus": "站点启用/停用、社区列表联动、企业分配可见性",
        "boundary_focus": "空站点删除限制、表单校验、停用提示",
        "critical_page_names": {"站点列表页", "站点详情页", "社区管理列表（站点子页）"},
    },
    {
        "module_name": "服务管理",
        "doc_title": "服务管理需求",
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/03_服务管理_需求.md",
        "role": "reference",
        "focus": "服务上架审核、审核详情、已上架服务、服务分类树",
        "state_focus": "通过/驳回流转、已上架服务状态、分类树操作权限",
        "boundary_focus": "审核意见必填、分类树新增编辑校验、空态与错误态",
        "critical_page_names": {"服务上架审核列表", "服务上架审核详情", "已上架服务列表"},
    },
    {
        "module_name": "商品管理",
        "doc_title": "商品管理需求",
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/04_商品管理_需求.md",
        "role": "reference",
        "focus": "商品审核列表、审核详情、SKU 展示、分类树、重新审核规则",
        "state_focus": "商品审核状态流转、违规下架、分类显隐",
        "boundary_focus": "SKU 空态、图片预览、审核驳回必填",
        "critical_page_names": {"商品上架审核列表", "商品上架审核详情", "已上架商品列表"},
    },
    {
        "module_name": "订单路由与监控",
        "doc_title": "订单路由与监控需求",
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/05_订单路由与监控_需求.md",
        "role": "reference",
        "focus": "订单监控、订单详情、路由记录、异常订单处理、大屏看板",
        "state_focus": "异常状态、客服介入入口、路由规则可追溯",
        "boundary_focus": "筛选空态、看板刷新、异常处理必填说明",
        "critical_page_names": {"订单监控列表", "订单详情页", "订单大屏看板"},
    },
    {
        "module_name": "财务结算管理",
        "doc_title": "财务结算管理需求",
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/06_财务结算管理_需求.md",
        "role": "reference",
        "focus": "交易数据、服务费账单、退款数据、财务统计看板",
        "state_focus": "账单状态展示、退款数据联动、统计看板口径",
        "boundary_focus": "账单空态、导出、详情回显和错误提示",
        "critical_page_names": {"交易数据列表", "服务费账单列表", "财务统计看板"},
    },
    {
        "module_name": "消费者投诉处理",
        "doc_title": "消费者投诉处理需求",
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/07_消费者投诉处理_需求.md",
        "role": "reference",
        "focus": "投诉列表、投诉详情处理、处罚记录、处理闭环",
        "state_focus": "待处理/处理中/已处理流转、处罚记录同步",
        "boundary_focus": "处理说明必填、异常提示、只读态",
        "critical_page_names": {"投诉列表页", "投诉详情/处理页"},
    },
    {
        "module_name": "消费者中心",
        "doc_title": "消费者中心需求",
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/08_消费者中心_需求.md",
        "role": "reference",
        "focus": "消费者列表、详情、标签管理、黑名单、数据归属",
        "state_focus": "标签状态、黑名单状态、跨企业数据口径",
        "boundary_focus": "脱敏展示、空态、只读字段与导出",
        "critical_page_names": {"消费者列表页", "消费者详情页", "黑名单管理页"},
    },
    {
        "module_name": "会员与营销",
        "doc_title": "会员与营销需求",
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/09_会员与营销_需求.md",
        "role": "reference",
        "focus": "会员等级、积分规则、优惠券、营销活动、活动审核",
        "state_focus": "活动状态、优惠券状态、审核操作显隐",
        "boundary_focus": "表单校验、时间范围约束、统计空态",
        "critical_page_names": {"会员等级管理", "优惠券列表页", "营销活动列表"},
    },
    {
        "module_name": "小程序管理",
        "doc_title": "小程序管理需求",
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/10_小程序管理_需求.md",
        "role": "reference",
        "focus": "广告位管理、分类页配置、活动页配置、平台公告",
        "state_focus": "发布状态、配置落位、页面区域可见性",
        "boundary_focus": "上传校验、排序规则、空态和回退提示",
        "critical_page_names": {"广告位管理", "分类页配置", "活动页配置"},
    },
    {
        "module_name": "数据统计与报表",
        "doc_title": "数据统计与报表需求",
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/11_数据统计与报表_需求.md",
        "role": "reference",
        "focus": "全局经营看板、物业看板、企业对比、趋势分析",
        "state_focus": "看板刷新、筛选口径、时间切换",
        "boundary_focus": "图表容器空态、无数据提示、加载状态",
        "critical_page_names": {"全局经营看板", "智慧物业数据看板", "趋势分析"},
    },
    {
        "module_name": "加盟管理",
        "doc_title": "加盟管理需求",
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/12_加盟管理_需求.md",
        "role": "reference",
        "focus": "加盟人员列表、注册、详情、加盟订单、提现审核",
        "state_focus": "加盟人员状态、提现审核状态、订单关联",
        "boundary_focus": "注册表单校验、审核意见、空态",
        "critical_page_names": {"加盟人员列表", "加盟人员详情", "加盟人员提现审核"},
    },
    {
        "module_name": "商家对接管理",
        "doc_title": "商家对接管理需求",
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/13_商家对接管理_需求.md",
        "role": "reference",
        "focus": "商家列表、详情、站点分配、商家数据看板",
        "state_focus": "站点分配状态、商家状态、看板口径",
        "boundary_focus": "分配弹窗校验、无权限操作、空态",
        "critical_page_names": {"商家列表页", "商家详情页", "商家数据监控看板"},
    },
    {
        "module_name": "培训课程管理",
        "doc_title": "培训课程管理需求",
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/14_培训课程管理_需求.md",
        "role": "reference",
        "focus": "课程分类、课程列表、课程编辑、内容管理、审核、推送、题库、考试、订单、统计",
        "state_focus": "课程审核状态、推送状态、考试状态、订单状态",
        "boundary_focus": "章节校验、题库空态、课程上下架提示",
        "critical_page_names": {"课程列表", "新增/编辑课程", "课程审核列表+详情"},
    },
    {
        "module_name": "系统管理",
        "doc_title": "系统管理需求",
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/15_系统管理_需求.md",
        "role": "reference",
        "focus": "管理员、角色权限树、操作日志、登录日志、系统配置",
        "state_focus": "角色权限显隐、启用禁用状态、日志状态",
        "boundary_focus": "密码规则、权限树半选、清空日志确认",
        "critical_page_names": {"管理员列表", "角色管理列表", "系统配置页"},
    },
]

_PLAYBOOK_SUMMARY_DOCS = [
    {
        "title": "示例项目大平台-模块总览",
        "relative_path": "docx/XQ/Second/业务需求/示例项目大平台/00_模块总览.md",
        "role": "primary",
    },
    {
        "title": "示例项目大平台-项目总览与平台架构",
        "relative_path": "docx/XQ/Second/示例项目大平台需求/00-项目总览与平台架构.md",
        "role": "reference",
    },
]

_PLATFORM_WAVES = [
    {"id": "wave0", "name": "Wave 0 登录与入口基线", "focus": ["登录与认证", "平台菜单装载", "平台与企业登录隔离"]},
    {"id": "wave1", "name": "Wave 1 核心治理链路", "focus": ["企业管理", "站点管理", "服务管理", "商品管理"]},
    {"id": "wave2", "name": "Wave 2 交易与监管链路", "focus": ["订单路由与监控", "财务结算管理", "消费者投诉处理"]},
    {"id": "wave3", "name": "Wave 3 运营与增长链路", "focus": ["消费者中心", "会员与营销", "小程序管理", "数据统计与报表"]},
    {"id": "wave4", "name": "Wave 4 组织与平台治理", "focus": ["加盟管理", "商家对接管理", "培训课程管理", "系统管理"]},
]

_CROSS_MODULE_SCENARIOS = [
    {
        "name": f"{_SCENARIO_PREFIX}跨模块-企业入驻到站点分配-原型阶段",
        "description": "串联企业入驻代办、套餐审核、站点分配与社区管理，检查主骨架是否完整。",
        "tags": ["示例项目大平台", "原型测试", "跨模块", "企业入驻", "站点分配"],
        "focus": [
            "企业入驻代办表单分步结构完整",
            "套餐购买审核可衔接密钥与合同弹窗",
            "站点列表与社区管理存在从企业到地理单元的配置路径",
        ],
    },
    {
        "name": f"{_SCENARIO_PREFIX}跨模块-服务审核上架到小程序展示-原型阶段",
        "description": "串联服务审核、已上架服务、小程序配置，检查服务上架链路。",
        "tags": ["示例项目大平台", "原型测试", "跨模块", "服务审核", "小程序管理"],
        "focus": [
            "服务审核列表与审核详情结构连贯",
            "已上架服务页面承接审核结果",
            "分类页/活动页/广告位对已上架服务有展示承载位",
        ],
    },
    {
        "name": f"{_SCENARIO_PREFIX}跨模块-商品审核上架到商家对接-原型阶段",
        "description": "串联商品审核、商家对接、商品分类与小程序展示，检查商品主链路。",
        "tags": ["示例项目大平台", "原型测试", "跨模块", "商品审核", "商家对接"],
        "focus": [
            "商品审核详情存在图片、SKU、商家信息承载区",
            "商家详情与站点分配弹窗能承接商家商品来源",
            "商品分类树与平台展示配置间不存在结构断层",
        ],
    },
    {
        "name": f"{_SCENARIO_PREFIX}跨模块-订单路由到财务与投诉闭环-原型阶段",
        "description": "串联订单监控、异常订单、财务结算、投诉处理，检查监管闭环。",
        "tags": ["示例项目大平台", "原型测试", "跨模块", "订单路由", "财务", "投诉"],
        "focus": [
            "订单详情页存在路由记录与操作日志",
            "财务结算页可承接订单/退款/账单数据",
            "投诉处理可承接异常订单与处罚记录闭环",
        ],
    },
]

_QUALITY_GATE_RULES = [
    {
        "name": "sample_platform_platform_module_coverage_gate",
        "description": "模块覆盖率必须达到 100%。",
        "metric": "module_coverage_rate",
        "operator": ">=",
        "threshold": 1.0,
        "severity": "blocking",
    },
    {
        "name": "sample_platform_platform_page_mapping_gate",
        "description": "页面映射率必须达到 95%。",
        "metric": "page_mapping_rate",
        "operator": ">=",
        "threshold": 0.95,
        "severity": "blocking",
    },
    {
        "name": "sample_platform_platform_critical_page_gate",
        "description": "关键页面缺失数必须为 0。",
        "metric": "critical_page_missing_count",
        "operator": "<=",
        "threshold": 0,
        "severity": "blocking",
    },
    {
        "name": "sample_platform_platform_blocking_gap_gate",
        "description": "阻断级原型差异数必须为 0。",
        "metric": "blocking_prototype_gap_count",
        "operator": "<=",
        "threshold": 0,
        "severity": "blocking",
    },
    {
        "name": "sample_platform_platform_critical_field_gate",
        "description": "关键字段缺失数必须为 0。",
        "metric": "critical_field_missing_count",
        "operator": "<=",
        "threshold": 0,
        "severity": "blocking",
    },
    {
        "name": "sample_platform_platform_state_transition_gate",
        "description": "关键状态流转缺失数必须为 0。",
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
            "title": "部署文档仓",
            "root_path": _deployed_repo_path("sample_platform"),
            "priority": 20,
        },
        {
            "source_id": "local_download_repo",
            "title": "本地下载仓",
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
            f"示例项目大平台-{item['module_name']}",
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
                "title": f"示例项目大平台 HTML 原型目录（{source['title']}）",
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
            "title": "示例项目大平台 HTML 原型目录（当前工作区）",
            "role": "prototype",
            "relative_path": _PROTOTYPE_RELATIVE_PATH,
            "local_path": str(workspace_path),
            "exists": workspace_path.exists(),
            "asset_scope": "workspace",
            "source_title": "当前工作区",
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
    return "页面"


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
            "页面存在用户名、密码、验证码和登录按钮等核心控件",
            "登录成功后的平台菜单装载路径与需求一致",
            "错误提示、验证码刷新和失败锁定规则有显式反馈",
        ]
    if "列表" in page_type:
        return [
            "搜索区、表格区、分页区和操作按钮区结构完整",
            "关键列、状态标签和操作显隐符合需求定义",
            "空态、加载态、确认弹窗和导出/筛选入口有定义",
        ]
    if "详情" in page_type:
        return [
            "详情信息卡片、时间轴/日志/状态区块与需求一致",
            "主操作按钮、审核入口或关联记录区存在",
            "关键字段回显完整，异常态和只读态有说明",
        ]
    if "表单" in page_type or "弹窗" in page_type:
        return [
            "必填字段、默认值、分组布局和校验规则完整",
            "提交、取消、上一步/下一步等关键按钮齐全",
            "校验失败、关闭确认和成功反馈路径明确",
        ]
    if "看板" in page_type:
        return [
            "看板分区、图表容器、统计卡片和实时区块结构完整",
            "刷新提示、日期切换、无数据提示和加载态有定义",
            "关键视觉框架与需求中的布局分区一致",
        ]
    return [
        f"{page_name} 的入口、主区域和关键操作结构完整",
        "页面状态、提示信息和交互反馈有定义",
        "路由与菜单入口与需求文档保持一致",
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
            "label": "需求文档同步",
            "status": "success" if existing_docs == len(docs) else "warning",
            "message": f"已同步 {existing_docs}/{len(docs)} 份大平台需求文档。",
            "value": f"{existing_docs}/{len(docs)}",
        },
        {
            "check_id": "platform_prototype_dir_ready",
            "label": "原型目录同步",
            "status": "success" if prototype_asset else "warning",
            "message": (
                f"已检测到原型目录：{prototype_asset['local_path']}"
                if prototype_asset
                else f"未检测到原型目录，请先同步 {_PROTOTYPE_RELATIVE_PATH}"
            ),
            "value": prototype_asset["relative_path"] if prototype_asset else _PROTOTYPE_RELATIVE_PATH,
        },
        {
            "check_id": "platform_prototype_file_count",
            "label": "原型文件数量",
            "status": "success" if prototype_file_count > 0 else "warning",
            "message": f"当前识别到 {prototype_file_count} 个 HTML 原型文件。",
            "value": prototype_file_count,
        },
        {
            "check_id": "platform_page_mapping_rate",
            "label": "页面映射率",
            "status": "success" if mapping_summary["mapping_rate"] >= 0.95 else "warning",
            "message": f"已映射 {mapping_summary['mapped_pages']}/{mapping_summary['total_pages']} 个页面。",
            "value": mapping_summary["mapping_rate"],
        },
        {
            "check_id": "platform_critical_page_gap",
            "label": "关键页面缺口",
            "status": "success" if mapping_summary["critical_missing_pages"] == 0 else "warning",
            "message": f"仍有 {mapping_summary['critical_missing_pages']} 个关键页面未匹配到 HTML 原型。",
            "value": mapping_summary["critical_missing_pages"],
        },
    ]


def _build_requirement_content(mapping_summary: dict[str, Any], asset_checks: list[dict[str, Any]]) -> str:
    module_lines = "\n".join(f"- {item['module_name']}：{item['focus']}" for item in _MODULE_BLUEPRINTS)
    asset_lines = "\n".join(f"- {item['label']}：{item['message']}" for item in asset_checks)
    return f"""# 示例项目大平台原型测试包

## 项目定位
- 被测对象：示例项目大平台管理系统（Vue3 + Element Plus）
- 测试方式：需求文档 + HTML 原型一致性检查
- 当前模式：先完成原型测试，不默认接真实系统联调
- 目标仓库：{_DOCS_REPO_URL}

## 资产检查
{asset_lines}

## 范围说明
- 覆盖登录与认证 + 15 个一级业务模块
- 当前页面映射：{mapping_summary['mapped_pages']}/{mapping_summary['total_pages']}
- 关键页面缺口：{mapping_summary['critical_missing_pages']}
- 推荐视觉基线页面：{mapping_summary['baseline_candidates']} 个

## 统一检查维度
- 菜单与路由是否完整
- 页面布局是否与原型一致
- 搜索区、表格区、分页区、弹窗/抽屉是否齐全
- 表单字段、必填、校验、默认值是否齐全
- 按钮显隐、权限标识、状态流转是否符合需求
- 空态、加载态、错误态、确认弹窗是否有定义
- 关键视觉结构是否与原型主框架一致

## 模块清单
{module_lines}

## 原型门禁
- module_coverage_rate = 1.0
- page_mapping_rate >= 0.95
- critical_page_missing_count <= 0
- blocking_prototype_gap_count <= 0
- critical_field_missing_count <= 0
- critical_state_transition_gap_count <= 0
"""


def _primary_url_from_mapping(page_mappings: list[dict[str, Any]], module_name: str) -> str:
    candidates = [item for item in page_mappings if item["module_name"] == module_name]
    if not candidates:
        return "about:blank"
    with_file = next((item for item in candidates if item["prototype_source"]["exists"]), None)
    return with_file["prototype_source"]["file_uri"] if with_file else "about:blank"


def _module_pages_text(page_mappings: list[dict[str, Any]], module_name: str) -> str:
    names = [item["page_name"] for item in page_mappings if item["module_name"] == module_name][:3]
    return "、".join(names) if names else "核心页面"


def _build_module_scenarios(page_mappings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    for blueprint in _MODULE_BLUEPRINTS:
        url = _primary_url_from_mapping(page_mappings, blueprint["module_name"])
        pages_text = _module_pages_text(page_mappings, blueprint["module_name"])
        scenarios.extend(
            [
                {
                    "name": f"{_SCENARIO_PREFIX}{blueprint['module_name']}-页面结构检查-原型阶段",
                    "description": f"检查 {blueprint['module_name']} 的菜单、路由、页面骨架与关键区块是否与需求和原型一致。",
                    "tags": ["示例项目大平台", "原型测试", blueprint["module_name"], "structure"],
                    "steps": [
                        {
                            "name": f"{blueprint['module_name']} 页面结构检查",
                            "url": url,
                            "instruction": (
                                f"角色：平台原型审查角色\n模块：{blueprint['module_name']}\n目标页面：{pages_text}\n"
                                f"检查重点：{blueprint['focus']}\n关键断言：\n"
                                "1. 一级/二级菜单、页面路由和入口名称与需求一致\n"
                                "2. 页面布局包含需求约定的搜索区、列表区、详情区、弹窗区或看板分区\n"
                                "3. 若 HTML 原型尚未同步，则记录为资产缺失，不直接归类为业务缺陷"
                            ),
                            "mode": "smart",
                            "timeout": 120,
                            "on_failure": "continue",
                        }
                    ],
                },
                {
                    "name": f"{_SCENARIO_PREFIX}{blueprint['module_name']}-主操作检查-原型阶段",
                    "description": f"检查 {blueprint['module_name']} 的核心主操作、按钮显隐、审核与状态路径。",
                    "tags": ["示例项目大平台", "原型测试", blueprint["module_name"], "primary-flow"],
                    "steps": [
                        {
                            "name": f"{blueprint['module_name']} 主操作检查",
                            "url": url,
                            "instruction": (
                                f"角色：平台原型审查角色\n模块：{blueprint['module_name']}\n目标页面：{pages_text}\n"
                                f"检查重点：{blueprint['state_focus']}\n关键断言：\n"
                                "1. 主按钮、操作列、审核动作和状态标签显隐符合需求\n"
                                "2. 详情页、编辑页、审核页、看板页之间存在明确跳转或承接关系\n"
                                "3. 状态流转、权限差异、确认弹窗和结果反馈在原型中有定义"
                            ),
                            "mode": "smart",
                            "timeout": 120,
                            "on_failure": "continue",
                        }
                    ],
                },
                {
                    "name": f"{_SCENARIO_PREFIX}{blueprint['module_name']}-异常边界检查-原型阶段",
                    "description": f"检查 {blueprint['module_name']} 的校验规则、空态、错误态与边界提示。",
                    "tags": ["示例项目大平台", "原型测试", blueprint["module_name"], "boundary"],
                    "steps": [
                        {
                            "name": f"{blueprint['module_name']} 异常边界检查",
                            "url": url,
                            "instruction": (
                                f"角色：平台原型审查角色\n模块：{blueprint['module_name']}\n目标页面：{pages_text}\n"
                                f"检查重点：{blueprint['boundary_focus']}\n关键断言：\n"
                                "1. 必填校验、默认值、错误提示和边界提示有定义\n"
                                "2. 空态、无权限态、加载态、确认弹窗和关闭反馈可识别\n"
                                "3. 对阻断级缺口、关键字段缺失、关键状态流转缺失做差异登记"
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
                        "name": item["name"].split("-")[2] if "-" in item["name"] else "跨模块链路检查",
                        "url": default_url,
                        "instruction": (
                            "角色：平台原型审查角色\n类型：跨模块原型链路检查\n"
                            f"链路目标：{item['description']}\n关键断言：\n"
                            + "\n".join(f"{index}. {focus}" for index, focus in enumerate(item["focus"], 1))
                            + "\n4. 若链路中出现页面、路由或承接关系缺口，记录为原型一致性差异"
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
        f"待同步原型目录：{_PROTOTYPE_RELATIVE_PATH}",
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
            {"label": "大平台前端仓库", "url": _PLATFORM_FRONTEND_REPO_URL, "local_path": str(_deployed_repo_path("sample-product-qdpt"))},
            {"label": "共享后端仓库", "url": _PLATFORM_BACKEND_REPO_URL, "local_path": str(_deployed_repo_path("sample-product-hd"))},
            {"label": "需求与原型仓库", "url": _DOCS_REPO_URL, "local_path": str(_docs_repo_path())},
        ],
        "waves": deepcopy(_PLATFORM_WAVES),
        "recommended_test_types": deepcopy(_PLAYBOOK_TEST_TYPES),
        "naming_convention": {"scenario": "[角色]-[模块]-[场景]-[环境]", "test_data_prefix": _ARTIFACT_PREFIX},
        "notes": [
            "当前项目包用于需求文档与 HTML 原型一致性检查，不默认要求真实系统执行。",
            "若原型目录未同步，页面映射状态会显示为 pending_prototype，需要先补资产再做视觉基线。",
            "页面映射清单可作为需求页、场景页、视觉页共用的事实源。",
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
        "cleanup_policy": "清理截图、基线、差异报告和临时原型检查产物，不涉及业务真实数据。",
        "recommended_entities": ["页面映射", "视觉基线", "差异截图", "原型差异报告"],
    }
