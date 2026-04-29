# -*- coding: utf-8 -*-
"""
项目回归包预置能力

为平台内的需求解析、场景链、质量门禁和测试数据提供统一的项目级预置。
"""
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
        "企业平台端-项目总览与技术架构",
        "primary",
    ),
    _docs_entry(
        r"docx\XQ\Second\企业平台端需求\01-登录与认证模块.md",
        "企业平台端-登录与认证模块",
    ),
    _docs_entry(
        r"docx\XQ\Second\企业平台端需求\03-工单调度模块.md",
        "企业平台端-工单调度模块",
    ),
    _docs_entry(
        r"docx\XQ\Second\企业平台端需求\07-智慧物业模块.md",
        "企业平台端-智慧物业模块",
    ),
    _docs_entry(
        r"docx\XQ\Second\企业平台端需求\06-养老管理模块.md",
        "企业平台端-养老管理模块",
    ),
    _docs_entry(
        r"docx\XQ\Second\企业平台端需求\09-系统管理模块.md",
        "企业平台端-系统管理模块",
    ),
]


def _build_requirement_content() -> str:
    available_docs = [doc for doc in _SAMPLE_PLATFORM_DOCS if doc["exists"]]
    available_doc_lines = "\n".join(
        f"- {doc['title']}：{doc['relative_path']}" for doc in available_docs
    ) or "- 当前工作区尚未同步需求文档仓，请先拉取 sample_platform 仓库"

    return f"""# 示例项目企业平台端首轮真实回归

## 项目定位
- 被测系统：示例项目企业平台端后台管理系统（示例系统管理系统）
- 登录地址：{_TARGET_URL}
- 目标用户：企业管理员与模块业务操作人员
- 业务范围：工单调度、智慧物业、养老管理、系统管理、商城管理、财务管理、培训中心

## 仓库信息
- 前端仓库：{_FRONTEND_REPO_URL}
- 后端仓库：{_BACKEND_REPO_URL}
- 需求文档仓：{_DOCS_REPO_URL}

## 首轮回归目标
- 按需求文档做真实回归测试
- 以 {_ROLE_NAME} 为主角色
- 允许创建与回收测试数据
- 优先产出 ui_e2e、business_flow、api_rest、data_validation 四类测试
- 首轮不纳入性能与安全专项阻断

## 优先级与波次
1. Wave 0：登录与会话基线
2. Wave 1：工单调度、智慧物业、公告/报事主流程
3. Wave 2：停车、安防、能耗、设备/告警
4. Wave 3：养老管理与商家能力
5. Wave 4：系统管理、个人中心、密码修改、菜单权限差异

## 默认准入标准
- 登录主流程通过
- 一级核心业务流通过率 >= 95%
- 阻断级缺陷数 <= 0
- 未解释 5xx 数 <= 0
- 关键页面白屏/死链/严重控制台错误 <= 0

## 推荐导入文档
{available_doc_lines}

## 执行约束
- 场景命名格式固定为 `[角色]-[模块]-[场景]-[环境]`
- 所有新增数据必须使用 `{_TEST_DATA_PREFIX}` 前缀
- 所有可删除对象在任务末尾清理；不可删除对象记录回收清单
- 每条场景都要写清角色、前置数据、入口 URL、关键断言、失败截图要求
"""


_SAMPLE_PLATFORM_WAVES = [
    {
        "id": "wave0",
        "name": "Wave 0 认证与会话基线",
        "focus": ["登录与认证", "验证码", "菜单加载", "会话保持", "退出登录"],
    },
    {
        "id": "wave1",
        "name": "Wave 1 核心业务流",
        "focus": ["工单调度", "智慧物业", "公告/报事"],
    },
    {
        "id": "wave2",
        "name": "Wave 2 资产与现场能力",
        "focus": ["停车", "安防", "能耗", "设备维护", "告警处理"],
    },
    {
        "id": "wave3",
        "name": "Wave 3 养老与商户能力",
        "focus": ["老人档案", "养老设备", "养老告警", "商户入驻与审核"],
    },
    {
        "id": "wave4",
        "name": "Wave 4 系统侧回归",
        "focus": ["个人中心", "密码修改", "系统配置读取", "业务角色菜单权限"],
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
            "覆盖登录页基线、验证码、正确/错误登录、菜单拉取、刷新会话保持和退出登录。"
            "使用真实测试账号执行，失败时保留登录页和首页截图。"
        ),
        "tags": ["示例项目", "真实回归", "wave0", "登录认证"],
        "steps": [
            _step(
                "登录页基线检查",
                _TARGET_URL,
                f"""
角色：{_ROLE_NAME}
前置数据：无需登录；记录当前验证码是否启用
目标：验证登录页可访问、输入框/验证码/记住我/协议勾选控件是否可见
关键断言：
1. 页面标题或品牌标识可见
2. 用户名、密码、验证码（若启用）输入控件存在
3. 登录按钮可点击且无白屏、死链、严重控制台报错
失败截图要求：保留整页截图和控制台错误摘要
""",
            ),
            _step(
                "正确登录并验证首页菜单",
                _TARGET_URL,
                f"""
角色：{_ROLE_NAME}
前置数据：准备有效测试账号、验证码识别方式、允许访问业务菜单
目标：完成登录并验证 `/system/user/getInfo`、`/system/menu/getRouters` 对应的首页与一级菜单加载
关键断言：
1. 登录成功后跳转到首页或默认工作台
2. 至少能看到工单调度、智慧物业、养老管理、系统管理中的角色可见菜单
3. 刷新页面后保持已登录态
失败截图要求：保留登录前、登录后首页、菜单异常状态截图
""",
                depends_on=None,
            ),
            _step(
                "退出登录回到登录页",
                _TARGET_URL,
                f"""
角色：{_ROLE_NAME}
前置数据：保持已登录态
目标：从个人中心或系统入口执行退出登录
关键断言：
1. 退出后回到登录页
2. 再访问受限页面会被拦截
失败截图要求：保留退出前后页面截图
""",
                depends_on=None,
                on_failure="continue",
            ),
        ],
    },
    {
        "name": f"[{_ROLE_NAME}]-工单调度-Wave1主流程-测试环境",
        "description": (
            "按需求文档覆盖工单列表、筛选、详情、创建、编辑、状态流转、派单和导出。"
        ),
        "tags": ["示例项目", "真实回归", "wave1", "工单调度"],
        "steps": [
            _step(
                "工单列表与筛选基线",
                _TARGET_URL,
                f"""
角色：{_ROLE_NAME}
前置数据：已登录；确保当前账号有工单调度访问权限
入口：从一级菜单进入 `工单调度 > 工单管理`
目标：验证统计看板、状态 Tab、搜索筛选、分页和导出入口
关键断言：
1. 顶部统计卡片可见，包含工单总数/处理中/今日完成等指标
2. 业务类型、工单类型、紧急程度、创建时间、关键词筛选可用
3. 平台订单 Tab 可见且切换后列表刷新
失败截图要求：保留统计区、筛选区、列表区截图
""",
            ),
            _step(
                "工单新增编辑与详情",
                _TARGET_URL,
                f"""
角色：{_ROLE_NAME}
前置数据：准备测试数据前缀 `{_TEST_DATA_PREFIX}_WO_`
目标：创建一条测试工单，查看详情，再修改标题或紧急程度
关键断言：
1. 创建成功后列表可按测试前缀检索到
2. 详情页展示工单编号、标题、客户、地址、状态、支付状态等字段
3. 编辑成功后列表与详情数据一致
回滚动作：如支持删除则删除；否则登记回收清单
失败截图要求：保留表单校验、成功提示、详情回显截图
""",
            ),
            _step(
                "工单状态流转与派单",
                _TARGET_URL,
                f"""
角色：{_ROLE_NAME}
前置数据：存在一条待分配或待接单测试工单
目标：验证派单、处理、验收、取消/审核取消中的至少一条完整状态流转
关键断言：
1. 状态按文档定义流转，异常状态有明确提示
2. 派单或处理后工单详情的处理记录更新
3. 批量操作若不可执行，应给出明确提示，不允许静默失败
失败截图要求：保留流转前后状态和处理记录截图
""",
                on_failure="continue",
            ),
        ],
    },
    {
        "name": f"[{_ROLE_NAME}]-智慧物业-Wave1社区公告报事-测试环境",
        "description": "覆盖社区/物业管理、报事报修、公告通知的高频查询与写操作。",
        "tags": ["示例项目", "真实回归", "wave1", "智慧物业", "公告报事"],
        "steps": [
            _step(
                "社区与物业列表基线",
                _TARGET_URL,
                f"""
角色：{_ROLE_NAME}
前置数据：已登录；具备物业模块权限
入口：`智慧物业 > 小区/社区管理` 与 `物业管理`
目标：验证社区列表、楼栋/房屋入口、分页、搜索和详情入口
关键断言：
1. 社区列表可加载，无明显错位或空白区域
2. 筛选与分页操作后列表结果更新
3. 房屋/业主信息入口可见且可进入详情
失败截图要求：保留列表、筛选、详情入口截图
""",
            ),
            _step(
                "报事报修与公告主流程",
                _TARGET_URL,
                f"""
角色：{_ROLE_NAME}
前置数据：准备 `{_TEST_DATA_PREFIX}_NOTICE_` 或 `{_TEST_DATA_PREFIX}_REPORT_` 测试数据
入口：`智慧物业 > 报事/公告`
目标：验证报事列表、处理动作、公告新增/编辑/发布或下线
关键断言：
1. 列表支持查询、筛选、详情查看
2. 新增或编辑成功后列表可回显
3. 发布状态变化后详情和列表状态一致
回滚动作：删除测试公告或记录回收清单
失败截图要求：保留新增表单、成功提示、状态变化截图
""",
                on_failure="continue",
            ),
        ],
    },
    {
        "name": f"[{_ROLE_NAME}]-智慧物业-Wave2停车安防能耗-测试环境",
        "description": "覆盖停车、安防、能耗等资产管理模块的查询、详情与状态变化。",
        "tags": ["示例项目", "真实回归", "wave2", "智慧物业", "停车", "安防", "能耗"],
        "steps": [
            _step(
                "停车管理合同与进出记录",
                _TARGET_URL,
                f"""
角色：{_ROLE_NAME}
前置数据：具备停车模块权限；准备 `{_TEST_DATA_PREFIX}_PK_` 测试合同数据
入口：`智慧物业 > 智能停车`
目标：验证车位列表、详情、续费/终止、进出记录弹窗、导出
关键断言：
1. 车牌号、车位信息、合同状态、费用状态字段完整
2. 续费或终止动作后列表状态同步
3. 进出记录弹窗可打开且数据结构完整
失败截图要求：保留列表、弹窗、状态变化截图
""",
            ),
            _step(
                "安防与能耗概览",
                _TARGET_URL,
                f"""
角色：{_ROLE_NAME}
前置数据：根据角色判断能耗模块是否开启；若未开启则记录为配置差异
入口：`智慧物业 > 安防监控`、`能耗管理`
目标：验证设备列表、围栏管理、能耗数据表和可见性规则
关键断言：
1. 安防列表和围栏管理入口可用
2. 能耗模块若开启，应可见能耗列表/统计；若关闭，应有合理菜单隐藏或提示
3. 页面无白屏、死链、严重控制台报错
失败截图要求：保留模块可见性和异常状态截图
""",
                on_failure="continue",
            ),
        ],
    },
    {
        "name": f"[{_ROLE_NAME}]-养老管理-Wave3老人设备告警-测试环境",
        "description": "覆盖老人档案、设备、告警、处理记录等养老主流程。",
        "tags": ["示例项目", "真实回归", "wave3", "养老管理"],
        "steps": [
            _step(
                "老人档案列表与新增",
                _TARGET_URL,
                f"""
角色：{_ROLE_NAME}
前置数据：具备养老模块权限；准备 `{_TEST_DATA_PREFIX}_ELDER_` 测试档案数据
入口：`养老管理 > 老人信息管理`
目标：验证筛选、脱敏展示、新增/编辑、详情跳转
关键断言：
1. 姓名和联系方式默认脱敏展示
2. 新增或编辑成功后列表与详情一致
3. 关联社区、护理等级、紧急联系人字段回显正确
回滚动作：删除测试老人档案或记录回收清单
失败截图要求：保留列表脱敏态、详情态、编辑成功截图
""",
            ),
            _step(
                "设备与告警处理",
                _TARGET_URL,
                f"""
角色：{_ROLE_NAME}
前置数据：存在可查看的测试设备或告警记录
入口：`养老管理 > 设备管理`、`告警管理`
目标：验证设备详情、在线状态、告警列表、告警处理与记录追溯
关键断言：
1. 设备详情可打开且字段完整
2. 告警处理动作有状态变化和处理记录
3. 失败提示、批处理或多选操作反馈明确
失败截图要求：保留设备详情、告警处理前后截图
""",
                on_failure="continue",
            ),
        ],
    },
    {
        "name": f"[{_ROLE_NAME}]-系统管理-Wave4个人中心权限差异-测试环境",
        "description": "覆盖个人中心、密码修改、菜单权限差异与配置读取。",
        "tags": ["示例项目", "真实回归", "wave4", "系统管理"],
        "steps": [
            _step(
                "个人中心与密码修改",
                _TARGET_URL,
                f"""
角色：{_ROLE_NAME}
前置数据：已登录；准备可恢复的测试密码策略
入口：个人中心 / 用户资料
目标：验证个人信息查看、密码修改表单、会话连续性
关键断言：
1. 个人中心可访问
2. 密码校验规则和错误提示明确
3. 若执行改密，需在任务末尾恢复原密码
失败截图要求：保留个人中心与改密校验截图
""",
            ),
            _step(
                "菜单权限与系统配置读取",
                _TARGET_URL,
                f"""
角色：{_ROLE_NAME}
前置数据：业务运营角色账号，不使用管理员全量权限
目标：验证业务角色可见菜单、不可见菜单和系统配置读取行为
关键断言：
1. 仅展示该角色应见菜单
2. 无权限页面不能直接访问或会返回明确提示
3. 配置页或参数读取页可正常加载角色允许范围内的数据
失败截图要求：保留菜单树和无权限提示截图
""",
                on_failure="continue",
            ),
        ],
    },
]


_SAMPLE_PLATFORM_GATE_RULES = [
    {
        "name": "sample_platform_login_success_gate",
        "description": "登录主流程必须全部通过。",
        "metric": "login_success_rate",
        "operator": ">=",
        "threshold": 1.0,
        "severity": "blocking",
    },
    {
        "name": "sample_platform_core_flow_pass_gate",
        "description": "一级核心业务流通过率必须达到 95%。",
        "metric": "core_flow_pass_rate",
        "operator": ">=",
        "threshold": 0.95,
        "severity": "blocking",
    },
    {
        "name": "sample_platform_blocking_bug_gate",
        "description": "首轮回归不允许存在阻断级缺陷。",
        "metric": "blocking_bug_count",
        "operator": "<=",
        "threshold": 0,
        "severity": "blocking",
    },
    {
        "name": "sample_platform_unexplained_5xx_gate",
        "description": "不允许存在未解释的 5xx 错误。",
        "metric": "unexplained_5xx_count",
        "operator": "<=",
        "threshold": 0,
        "severity": "blocking",
    },
    {
        "name": "sample_platform_critical_ui_error_gate",
        "description": "关键页面不允许出现白屏、死链或严重控制台错误。",
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
            "name": "示例项目企业平台端首轮真实回归",
            "target_url": _TARGET_URL,
            "project_name": "示例项目企业平台端",
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
        "project_name": "示例项目企业平台端",
        "title": "示例项目企业平台端首轮真实回归",
        "content": _build_requirement_content(),
        "references": references,
        "document_sources": doc_sources,
        "target_url": _TARGET_URL,
        "repositories": [
            {
                "label": "前端仓库",
                "url": _FRONTEND_REPO_URL,
                "local_path": str(_deployed_repo_path("sample-product-qd")),
            },
            {
                "label": "后端仓库",
                "url": _BACKEND_REPO_URL,
                "local_path": str(_deployed_repo_path("sample-product-hd")),
            },
            {
                "label": "需求文档仓",
                "url": _DOCS_REPO_URL,
                "local_path": str(_docs_repo_path()),
            },
        ],
        "waves": deepcopy(_SAMPLE_PLATFORM_WAVES),
        "recommended_test_types": ["ui_e2e", "business_flow", "api_rest", "data_validation"],
        "naming_convention": {
            "scenario": "[角色]-[模块]-[场景]-[环境]",
            "test_data_prefix": _TEST_DATA_PREFIX,
        },
        "notes": [
            "首轮执行建议先跑 Wave 0，再依次推进 Wave 1~4。",
            "业务 API 先通过 UI 回归抓包确认，再补录到 API 工作台。",
            "若需求与线上行为不一致，请单列为需求漂移，不直接判错。",
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
        "cleanup_policy": "所有可删除对象在任务末尾清理，不可删除对象进入回收清单。",
        "recommended_entities": ["工单", "公告", "停车合同", "老人档案"],
    }


def get_playbook_catalog_entry(playbook_id: str) -> dict[str, Any] | None:
    for item in list_playbooks():
        if item["playbook_id"] == playbook_id:
            return deepcopy(item)
    return None
