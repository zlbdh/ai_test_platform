"""
Comprehensive functional logic check script
Checks:
1. Backend API endpoint connectivity
2. Module import completeness
3. Key business logic checks
"""
import sys
import os
import json
import traceback
import importlib
import ast

# Set the project root
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
# Part 1: API endpoint connectivity
# ==========================================================
print("=" * 70)
print("1️⃣  Backend API endpoint connectivity checks")
print("=" * 70)

import urllib.request
import urllib.error

BASE_URL = "http://localhost:8020"

API_ENDPOINTS = [
    ("GET", "/", "Root path"),
    ("GET", "/api/health", "Health check"),
    ("GET", "/api/status", "System status"),
    ("GET", "/api/history", "Test history"),
    ("GET", "/api/config/ai", "AI configuration"),
    ("GET", "/api/knowledge/status", "Knowledge base status"),
    ("GET", "/api/knowledge/list", "Knowledge entries"),
    ("GET", "/api/data-factory/types", "Data factory types"),
    ("GET", "/api/commander/agents", "Agent list"),
    ("GET", "/api/performance/status", "Performance test status"),
    ("GET", "/api/security/status", "Security scan status"),
    ("GET", "/api/evaluation/scenarios", "Evaluation scenarios"),
    ("GET", "/api/scheduler/tasks", "Scheduled task list"),
    ("GET", "/api/report/history", "Report history"),
    ("GET", "/api/workbench/collections", "API collections"),
    ("GET", "/api/workbench/environments", "Environment list"),
    ("GET", "/api/platform/capabilities", "Platform capabilities"),
    ("GET", "/api/scenarios", "Scenario list"),
    ("GET", "/api/visual/baselines", "Visual baselines"),
    ("GET", "/api/oauth/tokens", "OAuth Tokens"),
    ("GET", "/api/ci/config", "CI/CD configuration"),
    ("GET", "/api/db/connections", "Database connections"),
    ("GET", "/api/notify/webhooks", "Notification webhooks"),
    ("GET", "/api/deploy/projects", "Deployed projects"),
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
            raise AssertionError(f"Connection failed: {e.reason}")
    test(f"API {method} {path} ({desc})", check_endpoint)

# ==========================================================
# Part 2: Core module import verification
# ==========================================================
print()
print("=" * 70)
print("2️⃣  Core module import verification (Core)")
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
# Part 3: Agent module import verification
# ==========================================================
print()
print("=" * 70)
print("3️⃣  Agent module import verification")
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
# Part 4: Service module import verification
# ==========================================================
print()
print("=" * 70)
print("4️⃣  Service module import verification")
print("=" * 70)

SERVICES_DIR = os.path.join(PROJECT_ROOT, "services")
if os.path.isdir(SERVICES_DIR):
    for f in sorted(os.listdir(SERVICES_DIR)):
        if f.endswith(".py") and f != "__init__.py":
            mod_name = f"services.{f[:-3]}"
            test(f"import {mod_name}", lambda m=mod_name: importlib.import_module(m))

# ==========================================================
# Part 5: Router module import verification
# ==========================================================
print()
print("=" * 70)
print("5️⃣  Router module import verification")
print("=" * 70)

ROUTERS_DIR = os.path.join(PROJECT_ROOT, "routers")
if os.path.isdir(ROUTERS_DIR):
    for f in sorted(os.listdir(ROUTERS_DIR)):
        if f.endswith(".py") and f != "__init__.py" and f != "__pycache__":
            mod_name = f"routers.{f[:-3]}"
            test(f"import {mod_name}", lambda m=mod_name: importlib.import_module(m))

# ==========================================================
# Part 6: Skill module import verification
# ==========================================================
print()
print("=" * 70)
print("6️⃣  Skill module import verification")
print("=" * 70)

SKILLS_DIR = os.path.join(PROJECT_ROOT, "skills")
if os.path.isdir(SKILLS_DIR):
    for f in sorted(os.listdir(SKILLS_DIR)):
        if f.endswith(".py") and f != "__init__.py" and f != "__pycache__":
            mod_name = f"skills.{f[:-3]}"
            test(f"import {mod_name}", lambda m=mod_name: importlib.import_module(m))

# ==========================================================
# Part 7: Workflow module import verification
# ==========================================================
print()
print("=" * 70)
print("7️⃣  Workflow module import verification")
print("=" * 70)

WORKFLOWS_DIR = os.path.join(PROJECT_ROOT, "workflows")
if os.path.isdir(WORKFLOWS_DIR):
    for f in sorted(os.listdir(WORKFLOWS_DIR)):
        if f.endswith(".py") and f != "__init__.py" and f != "__pycache__":
            mod_name = f"workflows.{f[:-3]}"
            test(f"import {mod_name}", lambda m=mod_name: importlib.import_module(m))

# ==========================================================
# Part 8: Key business logic checks
# ==========================================================
print()
print("=" * 70)
print("8️⃣  Key business logic checks")
print("=" * 70)

# 8.1 Config logic
def test_config_logic():
    from core.config import Config
    cfg = Config()
    assert hasattr(cfg, 'LLM_PROVIDER'), "Missing LLM_PROVIDER"
    assert hasattr(cfg, 'LLM_MODEL'), "Missing LLM_MODEL"
    assert hasattr(cfg, 'PROJECT_ROOT'), "Missing PROJECT_ROOT"
test("Config key attributes", test_config_logic)

# 8.2 Models logic
def test_models():
    from core.models import APIError
    err = APIError(message="test", status_code=400)
    assert err.status_code == 400
test("Models APIError construction", test_models)

# 8.3 EventBus logic
def test_event_bus():
    from core.event_bus import EventBus
    bus = EventBus(session_id="test_verify")
    assert hasattr(bus, 'publish_task') or hasattr(bus, 'publish_task_sync')
test("EventBus instantiation", test_event_bus)

# 8.4 SharedBrowserState logic
def test_shared_state():
    from core.shared import SharedBrowserState
    state = SharedBrowserState()
    assert hasattr(state, 'get_page') or hasattr(state, 'page')
test("SharedBrowserState instantiation", test_shared_state)

# 8.5 DataFactory logic
def test_data_factory():
    from core.data_factory import get_data_factory
    factory = get_data_factory()
    types = factory.get_available_types()
    assert len(types) > 0, "Data factory types are empty"
test("DataFactory type lookup", test_data_factory)

# 8.6 Evaluation metrics
def test_eval_metrics():
    from evaluation.metrics import ALL_METRICS
    assert len(ALL_METRICS) >= 8, f"Fewer than 8 evaluation metrics: {len(ALL_METRICS)}"
test("Evaluation metrics >= 8", test_eval_metrics)

# 8.7 Benchmark scenarios
def test_benchmark():
    from evaluation.benchmark_suite import BenchmarkSuite
    suite = BenchmarkSuite()
    scenarios = suite.list_scenarios()
    assert len(scenarios) >= 8, f"Fewer than 8 benchmark scenarios: {len(scenarios)}"
test("Benchmark scenarios >= 8", test_benchmark)

# 8.8 Allure Reporter
def test_allure_reporter():
    from core.allure_reporter import AllureReporter
    reporter = AllureReporter()
    assert hasattr(reporter, 'generate_report') or hasattr(reporter, 'generate')
test("AllureReporter instantiation", test_allure_reporter)

# 8.9 LLM Manager
def test_llm_manager():
    from core.llm_manager import get_llm
    # Verify that the function exists without creating an LLM
    assert callable(get_llm)
test("LLM Manager get_llm is callable", test_llm_manager)

# 8.10 SemanticEngine
def test_semantic_engine():
    from core.semantic_engine import SemanticLocator
    assert SemanticLocator is not None
test("SemanticLocator class exists", test_semantic_engine)

# 8.11 Scenario Chain
def test_scenario_chain():
    from core.scenario_chain import ScenarioChainEngine
    assert ScenarioChainEngine is not None
test("ScenarioChainEngine class exists", test_scenario_chain)

# 8.12 StrategySelector
def test_strategy():
    from core.strategy_selector import AITestStrategySelector
    selector = AITestStrategySelector()
    assert hasattr(selector, 'select_strategy') or hasattr(selector, 'analyze_requirement')
test("AITestStrategySelector instantiation", test_strategy)

# 8.13 TestScheduler
def test_scheduler():
    from core.test_scheduler import TestScheduler
    assert TestScheduler is not None
test("TestScheduler class exists", test_scheduler)

# 8.14 NotifyGateway
def test_notify():
    from core.notify_gateway import NotifyGateway
    gw = NotifyGateway()
    assert gw is not None
test("NotifyGateway instantiation", test_notify)

# ==========================================================
# Part 9: Static code checks for potential issues
# ==========================================================
print()
print("=" * 70)
print("9️⃣  Static code analysis: potential issue scan")
print("=" * 70)

issues_found = []

def check_python_file(filepath):
    """Check Python files for common issues"""
    file_issues = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
        
        # Check syntax
        try:
            ast.parse(content)
        except SyntaxError as e:
            file_issues.append(f"Syntax error: line {e.lineno}: {e.msg}")
        
        # Check bare except clauses
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped == "except:" or stripped.startswith("except: "):
                file_issues.append(f"Line {i}: Bare except clause (specify an exception type)")
            if "except Exception: pass" in stripped or "except: pass" in stripped:
                file_issues.append(f"Line {i}: Silently swallowed exception (except: pass)")
        
        # Check hard-coded passwords/keys
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if any(kw in stripped.lower() for kw in ['password = "', "password = '", 'secret = "', "secret = '"]):
                if not stripped.startswith('#') and 'example' not in stripped.lower() and 'test' not in stripped.lower():
                    file_issues.append(f"Line {i}: Possible hard-coded password/key")
        
    except Exception as e:
        file_issues.append(f"File read error: {e}")
    
    return file_issues

# Scan all Python files
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

print(f"  Files scanned: {total_files_scanned}")
print(f"  Issues found: {len(issues_found)}")
for issue in issues_found[:20]:  # Show only the first 20
    print(f"  ⚠️  {issue}")
if len(issues_found) > 20:
    print(f"  ... {len(issues_found) - 20} more issues")

# ==========================================================
# Part 10: main.py route registration completeness
# ==========================================================
print()
print("=" * 70)
print("🔟  main.py route registration completeness check")
print("=" * 70)

main_py_path = os.path.join(PROJECT_ROOT, "main.py")
with open(main_py_path, 'r', encoding='utf-8') as f:
    main_content = f.read()

# Check that all router files are registered in main.py
router_files = []
for f in os.listdir(os.path.join(PROJECT_ROOT, "routers")):
    if f.endswith(".py") and f != "__init__.py":
        router_files.append(f[:-3])

# Check both main.py and routers/__init__.py
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

print(f"  Total router files: {len(router_files)}")
print(f"  Registered in main.py: {len(registered)}")
print(f"  Unregistered: {len(not_registered)}")
for nr in not_registered:
    print(f"  ⚠️  Unregistered router: routers/{nr}.py")

# ==========================================================
# Summary report
# ==========================================================
print()
print("=" * 70)
print("📊 Summary report")
print("=" * 70)
print(f"  ✅ Passed: {PASS}")
print(f"  ❌ Failed: {FAIL}")
print(f"  ⚠️  Warnings: {WARN}")
print(f"  📝 Code issues: {len(issues_found)}")
print(f"  📄 Files scanned: {total_files_scanned}")
print()

# List all failed checks
if FAIL > 0:
    print("=" * 70)
    print("Failed check summary:")
    print("=" * 70)
    for r in RESULTS:
        if r[0] == "FAIL":
            print(f"  ❌ {r[1]}: {r[2]}")

print()
print(f"Exit code: {'0 (All passed)' if FAIL == 0 else '1 (Failures present)'}")
sys.exit(1 if FAIL > 0 else 0)
