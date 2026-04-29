"""
全面功能逻辑检查脚本
检查内容：
1. 后端 API 端点连通性
2. 模块导入完整性
3. 关键业务逻辑验证
"""
import sys
import os
import json
import traceback
import importlib
import ast

# 设置项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

PASS = 0
FAIL = 0
WARN = 0
RESULTS = []

def test(name, func):
    global PASS, FAIL
    try:
        func()
        PASS += 1
        RESULTS.append(("PASS", name))
        print(f"  ✅ PASS: {name}")
    except Exception as e:
        FAIL += 1
        RESULTS.append(("FAIL", name, str(e)))
        print(f"  ❌ FAIL: {name}")
        print(f"         → {e}")

def warn(name, msg):
    global WARN
    WARN += 1
    RESULTS.append(("WARN", name, msg))
    print(f"  ⚠️  WARN: {name}")
    print(f"         → {msg}")

# ==========================================================
# 第一部分：API 端点连通性
# ==========================================================
print("=" * 70)
print("1️⃣  后端 API 端点连通性检查")
print("=" * 70)

import urllib.request
import urllib.error

BASE_URL = "http://localhost:8020"

API_ENDPOINTS = [
    ("GET", "/", "根路径"),
    ("GET", "/api/health", "健康检查"),
    ("GET", "/api/status", "系统状态"),
    ("GET", "/api/history", "测试历史"),
    ("GET", "/api/config/ai", "AI 配置"),
    ("GET", "/api/knowledge/status", "知识库状态"),
    ("GET", "/api/knowledge/list", "知识列表"),
    ("GET", "/api/data-factory/types", "数据工厂类型"),
    ("GET", "/api/commander/agents", "Agent 列表"),
    ("GET", "/api/performance/status", "性能测试状态"),
    ("GET", "/api/security/status", "安全扫描状态"),
    ("GET", "/api/evaluation/scenarios", "评估场景"),
    ("GET", "/api/scheduler/tasks", "定时任务列表"),
    ("GET", "/api/report/history", "报告历史"),
    ("GET", "/api/workbench/collections", "API 集合"),
    ("GET", "/api/workbench/environments", "环境列表"),
    ("GET", "/api/platform/capabilities", "平台能力"),
    ("GET", "/api/scenarios", "场景列表"),
    ("GET", "/api/visual/baselines", "视觉基线"),
    ("GET", "/api/oauth/tokens", "OAuth Tokens"),
    ("GET", "/api/ci/config", "CI/CD 配置"),
    ("GET", "/api/db/connections", "数据库连接"),
    ("GET", "/api/notify/webhooks", "通知 Webhook"),
    ("GET", "/api/deploy/projects", "部署项目"),
]

for method, path, desc in API_ENDPOINTS:
    def check_endpoint(p=path, d=desc):
        try:
            req = urllib.request.Request(f"{BASE_URL}{p}", method="GET")
            req.add_header("Accept", "application/json")
            resp = urllib.request.urlopen(req, timeout=10)
            status = resp.status
            if status != 200:
                raise AssertionError(f"HTTP {status}")
        except urllib.error.HTTPError as e:
            raise AssertionError(f"HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise AssertionError(f"连接失败: {e.reason}")
    test(f"API {method} {path} ({desc})", check_endpoint)

# ==========================================================
# 第二部分：核心模块导入验证
# ==========================================================
print()
print("=" * 70)
print("2️⃣  核心模块导入验证 (Core)")
print("=" * 70)

CORE_MODULES = [
    "core.browser", "core.config", "core.event_bus", "core.shared",
    "core.llm_manager", "core.self_healing", "core.vector_store",
    "core.allure_reporter", "core.semantic_engine", "core.smart_locator",
    "core.test_scheduler", "core.notify_gateway", "core.tracing",
    "core.prompts", "core.data_factory", "core.dom_indexer",
    "core.strategy_selector", "core.models", "core.state",
    "core.scenario_chain", "core.scenario_generator",
    "core.knowledge_base", "core.requirement_parser",
    "core.report_generator", "core.test_data_generator",
    "core.test_generator", "core.session_manager",
    "core.agent_bus", "core.agent_profile",
    "core.cookie_manager", "core.db_helper", "core.db_tools",
    "core.env_validator", "core.history_manager", "core.log_tools",
    "core.logging_config", "core.notify_helper", "core.parsers",
    "core.protocol", "core.reporter", "core.semantic_actions",
    "core.skill_loader", "core.snapshot_compressor",
    "core.acceptance_engine", "core.api_doc_generator",
    "core.api_tools", "core.visual_tools",
]

for mod in CORE_MODULES:
    test(f"import {mod}", lambda m=mod: importlib.import_module(m))

# ==========================================================
# 第三部分：Agent 模块导入验证
# ==========================================================
print()
print("=" * 70)
print("3️⃣  Agent 模块导入验证")
print("=" * 70)

AGENT_MODULES = [
    "agents.planner_agent", "agents.executor_agent",
    "agents.inspector_agent", "agents.orchestrator",
    "agents.commander", "agents.exploratory_agent",
    "agents.healer", "agents.judge", "agents.react",
    "agents.scout_agent", "agents.rca_agent", "agents.ops_agent",
    "agents.master_agent", "agents.ui_agent", "agents.api_agent",
    "agents.data_agent", "agents.test_architect",
    "agents.planner", "agents.executor", "agents.state",
]

for mod in AGENT_MODULES:
    test(f"import {mod}", lambda m=mod: importlib.import_module(m))

# ==========================================================
# 第四部分：Service 模块导入验证
# ==========================================================
print()
print("=" * 70)
print("4️⃣  Service 模块导入验证")
print("=" * 70)

SERVICES_DIR = os.path.join(PROJECT_ROOT, "services")
if os.path.isdir(SERVICES_DIR):
    for f in sorted(os.listdir(SERVICES_DIR)):
        if f.endswith(".py") and f != "__init__.py":
            mod_name = f"services.{f[:-3]}"
            test(f"import {mod_name}", lambda m=mod_name: importlib.import_module(m))

# ==========================================================
# 第五部分：Router 模块导入验证
# ==========================================================
print()
print("=" * 70)
print("5️⃣  Router 模块导入验证")
print("=" * 70)

ROUTERS_DIR = os.path.join(PROJECT_ROOT, "routers")
if os.path.isdir(ROUTERS_DIR):
    for f in sorted(os.listdir(ROUTERS_DIR)):
        if f.endswith(".py") and f != "__init__.py" and f != "__pycache__":
            mod_name = f"routers.{f[:-3]}"
            test(f"import {mod_name}", lambda m=mod_name: importlib.import_module(m))

# ==========================================================
# 第六部分：Skills 模块导入验证
# ==========================================================
print()
print("=" * 70)
print("6️⃣  Skills 模块导入验证")
print("=" * 70)

SKILLS_DIR = os.path.join(PROJECT_ROOT, "skills")
if os.path.isdir(SKILLS_DIR):
    for f in sorted(os.listdir(SKILLS_DIR)):
        if f.endswith(".py") and f != "__init__.py" and f != "__pycache__":
            mod_name = f"skills.{f[:-3]}"
            test(f"import {mod_name}", lambda m=mod_name: importlib.import_module(m))

# ==========================================================
# 第七部分：Workflow 模块导入验证
# ==========================================================
print()
print("=" * 70)
print("7️⃣  Workflow 模块导入验证")
print("=" * 70)

WORKFLOWS_DIR = os.path.join(PROJECT_ROOT, "workflows")
if os.path.isdir(WORKFLOWS_DIR):
    for f in sorted(os.listdir(WORKFLOWS_DIR)):
        if f.endswith(".py") and f != "__init__.py" and f != "__pycache__":
            mod_name = f"workflows.{f[:-3]}"
            test(f"import {mod_name}", lambda m=mod_name: importlib.import_module(m))

# ==========================================================
# 第八部分：关键业务逻辑验证
# ==========================================================
print()
print("=" * 70)
print("8️⃣  关键业务逻辑验证")
print("=" * 70)

# 8.1 Config 逻辑
def test_config_logic():
    from core.config import Config
    cfg = Config()
    assert hasattr(cfg, 'LLM_PROVIDER'), "缺少 LLM_PROVIDER"
    assert hasattr(cfg, 'LLM_MODEL'), "缺少 LLM_MODEL"
    assert hasattr(cfg, 'PROJECT_ROOT'), "缺少 PROJECT_ROOT"
test("Config 关键属性", test_config_logic)

# 8.2 Models 逻辑
def test_models():
    from core.models import APIError
    err = APIError(message="test", status_code=400)
    assert err.status_code == 400
test("Models APIError 构造", test_models)

# 8.3 EventBus 逻辑
def test_event_bus():
    from core.event_bus import EventBus
    bus = EventBus(session_id="test_verify")
    assert hasattr(bus, 'publish_task') or hasattr(bus, 'publish_task_sync')
test("EventBus 实例化", test_event_bus)

# 8.4 SharedBrowserState 逻辑
def test_shared_state():
    from core.shared import SharedBrowserState
    state = SharedBrowserState()
    assert hasattr(state, 'get_page') or hasattr(state, 'page')
test("SharedBrowserState 实例化", test_shared_state)

# 8.5 DataFactory 逻辑
def test_data_factory():
    from core.data_factory import get_data_factory
    factory = get_data_factory()
    types = factory.get_available_types()
    assert len(types) > 0, "数据工厂类型为空"
test("DataFactory 获取类型", test_data_factory)

# 8.6 评估指标
def test_eval_metrics():
    from evaluation.metrics import ALL_METRICS
    assert len(ALL_METRICS) >= 8, f"评估指标不足8个: {len(ALL_METRICS)}"
test("评估指标 >= 8", test_eval_metrics)

# 8.7 基准场景
def test_benchmark():
    from evaluation.benchmark_suite import BenchmarkSuite
    suite = BenchmarkSuite()
    scenarios = suite.list_scenarios()
    assert len(scenarios) >= 8, f"基准场景不足8个: {len(scenarios)}"
test("基准场景 >= 8", test_benchmark)

# 8.8 Allure Reporter
def test_allure_reporter():
    from core.allure_reporter import AllureReporter
    reporter = AllureReporter()
    assert hasattr(reporter, 'generate_report') or hasattr(reporter, 'generate')
test("AllureReporter 实例化", test_allure_reporter)

# 8.9 LLM Manager
def test_llm_manager():
    from core.llm_manager import get_llm
    # 不实际创建 LLM，只验证函数存在
    assert callable(get_llm)
test("LLM Manager get_llm 可调用", test_llm_manager)

# 8.10 SemanticEngine
def test_semantic_engine():
    from core.semantic_engine import SemanticLocator
    assert SemanticLocator is not None
test("SemanticLocator 类存在", test_semantic_engine)

# 8.11 Scenario Chain
def test_scenario_chain():
    from core.scenario_chain import ScenarioChainEngine
    assert ScenarioChainEngine is not None
test("ScenarioChainEngine 类存在", test_scenario_chain)

# 8.12 StrategySelector
def test_strategy():
    from core.strategy_selector import AITestStrategySelector
    selector = AITestStrategySelector()
    assert hasattr(selector, 'select_strategy') or hasattr(selector, 'analyze_requirement')
test("AITestStrategySelector 实例化", test_strategy)

# 8.13 TestScheduler
def test_scheduler():
    from core.test_scheduler import TestScheduler
    assert TestScheduler is not None
test("TestScheduler 类存在", test_scheduler)

# 8.14 NotifyGateway
def test_notify():
    from core.notify_gateway import NotifyGateway
    gw = NotifyGateway()
    assert gw is not None
test("NotifyGateway 实例化", test_notify)

# ==========================================================
# 第九部分：代码静态检查 - 寻找潜在问题
# ==========================================================
print()
print("=" * 70)
print("9️⃣  代码静态分析 - 潜在问题扫描")
print("=" * 70)

issues_found = []

def check_python_file(filepath):
    """检查 Python 文件的常见问题"""
    file_issues = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
        
        # 检查语法
        try:
            ast.parse(content)
        except SyntaxError as e:
            file_issues.append(f"语法错误: 行{e.lineno}: {e.msg}")
        
        # 检查裸 except
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped == "except:" or stripped.startswith("except: "):
                file_issues.append(f"行{i}: 裸 except (应指定异常类型)")
            if "except Exception: pass" in stripped or "except: pass" in stripped:
                file_issues.append(f"行{i}: 静默吞噬异常 (except: pass)")
        
        # 检查硬编码密码/密钥
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if any(kw in stripped.lower() for kw in ['password = "', "password = '", 'secret = "', "secret = '"]):
                if not stripped.startswith('#') and 'example' not in stripped.lower() and 'test' not in stripped.lower():
                    file_issues.append(f"行{i}: 可能的硬编码密码/密钥")
        
    except Exception as e:
        file_issues.append(f"文件读取错误: {e}")
    
    return file_issues

# 扫描所有 Python 文件
scan_dirs = ['core', 'agents', 'services', 'routers', 'skills', 'workflows', 'evaluation']
total_files_scanned = 0

for scan_dir in scan_dirs:
    full_dir = os.path.join(PROJECT_ROOT, scan_dir)
    if not os.path.isdir(full_dir):
        continue
    for root, dirs, files in os.walk(full_dir):
        dirs[:] = [d for d in dirs if d != '__pycache__' and d != '.hypothesis']
        for f in files:
            if f.endswith('.py'):
                filepath = os.path.join(root, f)
                total_files_scanned += 1
                file_issues = check_python_file(filepath)
                if file_issues:
                    rel_path = os.path.relpath(filepath, PROJECT_ROOT)
                    for issue in file_issues:
                        issues_found.append(f"{rel_path}: {issue}")

print(f"  扫描文件数: {total_files_scanned}")
print(f"  发现问题数: {len(issues_found)}")
for issue in issues_found[:20]:  # 只显示前20个
    print(f"  ⚠️  {issue}")
if len(issues_found) > 20:
    print(f"  ... 还有 {len(issues_found) - 20} 个问题")

# ==========================================================
# 第十部分：main.py 路由注册完整性
# ==========================================================
print()
print("=" * 70)
print("🔟  main.py 路由注册完整性检查")
print("=" * 70)

main_py_path = os.path.join(PROJECT_ROOT, "main.py")
with open(main_py_path, 'r', encoding='utf-8') as f:
    main_content = f.read()

# 检查所有 router 文件是否在 main.py 中注册
router_files = []
for f in os.listdir(os.path.join(PROJECT_ROOT, "routers")):
    if f.endswith(".py") and f != "__init__.py":
        router_files.append(f[:-3])

# 同时检查 main.py 和 routers/__init__.py
init_py_path = os.path.join(PROJECT_ROOT, "routers", "__init__.py")
with open(init_py_path, 'r', encoding='utf-8') as f:
    init_content = f.read()

registered = []
not_registered = []
for rf in router_files:
    if rf in main_content or rf in init_content:
        registered.append(rf)
    else:
        not_registered.append(rf)

print(f"  Router 文件总数: {len(router_files)}")
print(f"  已在 main.py 注册: {len(registered)}")
print(f"  未注册: {len(not_registered)}")
for nr in not_registered:
    print(f"  ⚠️  未注册路由: routers/{nr}.py")

# ==========================================================
# 汇总报告
# ==========================================================
print()
print("=" * 70)
print("📊 汇总报告")
print("=" * 70)
print(f"  ✅ 通过: {PASS}")
print(f"  ❌ 失败: {FAIL}")
print(f"  ⚠️  警告: {WARN}")
print(f"  📝 代码问题: {len(issues_found)}")
print(f"  📄 扫描文件: {total_files_scanned}")
print()

# 列出所有失败项
if FAIL > 0:
    print("=" * 70)
    print("失败项汇总:")
    print("=" * 70)
    for r in RESULTS:
        if r[0] == "FAIL":
            print(f"  ❌ {r[1]}: {r[2]}")

print()
print(f"退出码: {'0 (全部通过)' if FAIL == 0 else '1 (存在失败)'}")
sys.exit(1 if FAIL > 0 else 0)
