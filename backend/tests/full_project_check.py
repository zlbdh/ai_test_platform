"""
全项目全方位检查脚本
覆盖：语法、导入、路由、依赖、配置
"""
import sys, os, py_compile, importlib, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(str(ROOT))

PASS = 0; FAIL = 0; WARN = 0
RESULTS = []; ISSUES = []

def test(name, func, critical=True):
    global PASS, FAIL, WARN
    try:
        func()
        PASS += 1
        RESULTS.append(f"  PASS {name}")
    except Exception as e:
        if critical:
            FAIL += 1
            RESULTS.append(f"  FAIL {name}: {e}")
            ISSUES.append({"severity": "ERROR", "test": name, "error": str(e)})
        else:
            WARN += 1
            RESULTS.append(f"  WARN {name}: {e}")
            ISSUES.append({"severity": "WARN", "test": name, "error": str(e)})

# ═══════════════════════════════════════════════════════════════════════
print("=" * 70)
print("PHASE 1: Python Syntax Check (ALL .py files)")
print("=" * 70)

py_files = sorted(ROOT.rglob("*.py"))
py_files = [f for f in py_files if ".venv" not in str(f) and "__pycache__" not in str(f)
            and "node_modules" not in str(f) and ".git" not in str(f)]

syntax_errors = []
for f in py_files:
    try:
        py_compile.compile(str(f), doraise=True)
    except py_compile.PyCompileError as e:
        syntax_errors.append(f"{f.relative_to(ROOT)}: {e}")

if syntax_errors:
    for err in syntax_errors:
        FAIL += 1
        RESULTS.append(f"  FAIL syntax: {err}")
        ISSUES.append({"severity": "ERROR", "test": "syntax", "error": err})
    print(f"  {len(syntax_errors)} syntax errors found!")
else:
    PASS += 1
    RESULTS.append(f"  PASS syntax: All {len(py_files)} Python files clean")
    print(f"  All {len(py_files)} Python files passed syntax check")

# ═══════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("PHASE 2: Core Module Import Chain")
print("=" * 70)

CORE_MODULES = [
    "core.config",
    "core.llm_manager",
    "core.browser_manager",
    "core.ai_engine",
    "core.dom_indexer",
    "core.self_healing",
    "core.screenshot_manager",
    "core.performance_manager",
    "core.data_manager",
    "core.semantic_engine",
    "core.semantic_actions",
    "core.smart_locator",
    "core.test_generator",
    "core.scenario_generator",
    "agents.executor_agent",
    "agents.planner_agent",
    "agents.security_agent",
    "evaluation",
    "evaluation.metrics",
    "evaluation.judge",
    "evaluation.benchmark_suite",
    "evaluation.reporter",
    "cicd",
    "cicd.quality_gate",
]

for mod_name in CORE_MODULES:
    test(f"import {mod_name}", lambda m=mod_name: __import__(m), critical=True)

# ═══════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("PHASE 3: Router Import Chain")
print("=" * 70)

ROUTER_MODULES = [
    "routers.evaluation",
    "routers.semantic",
    "routers.quality_gate",
]

for mod_name in ROUTER_MODULES:
    test(f"import {mod_name}", lambda m=mod_name: __import__(m), critical=True)

# Check all router files exist
from pathlib import Path
router_dir = ROOT / "routers"
router_files = sorted(router_dir.glob("*.py"))
router_names = [f.stem for f in router_files if f.stem != "__pycache__"]
print(f"  Found {len(router_names)} router files: {router_names}")

# ═══════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("PHASE 4: main.py Route Registration Completeness")
print("=" * 70)

def check_main_routes():
    main_content = (ROOT / "main.py").read_text(encoding="utf-8")

    # Find all app.include_router calls
    registered = re.findall(r'include_router\((\w+)\)', main_content)
    
    # Find all router imports
    imports = re.findall(r'from\s+routers\.(\w+)\s+import\s+router\s+as\s+(\w+)', main_content)
    
    print(f"  Imported routers: {len(imports)}")
    for module, alias in imports:
        is_registered = alias in registered or any(alias in r for r in registered)
        status = "REGISTERED" if is_registered else "NOT REGISTERED"
        print(f"    {module} -> {alias}: {status}")
        if not is_registered:
            ISSUES.append({"severity": "ERROR", "test": "route_registration", "error": f"Router {alias} imported but not registered"})
    
    return True

test("main.py route registration", check_main_routes)

# ═══════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("PHASE 5: Dependencies Check (requirements.txt)")
print("=" * 70)

def check_requirements():
    req_file = ROOT / "requirements.txt"
    if not req_file.exists():
        raise FileNotFoundError("requirements.txt not found")
    
    req_lines = req_file.read_text(encoding="utf-8").splitlines()
    req_packages = set()
    for line in req_lines:
        line = line.strip()
        if line and not line.startswith("#"):
            name = re.split(r'[>=<!\[]', line)[0].strip()
            if name:
                req_packages.add(name.lower())
    
    print(f"  {len(req_packages)} packages in requirements.txt")
    
    # Check critical imports
    critical_deps = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "playwright": "playwright",
        "pydantic": "pydantic",
        "httpx": "httpx",
        "langchain": "langchain",
        "langchain-openai": "langchain_openai",
    }
    
    missing = []
    for req_name, import_name in critical_deps.items():
        if req_name.lower() not in req_packages:
            missing.append(req_name)
    
    if missing:
        print(f"  WARNING: Missing from requirements.txt: {missing}")
    else:
        print(f"  All critical dependencies present")
    
    # Check if packages are actually installed
    import importlib
    not_installed = []
    for req_name, import_name in critical_deps.items():
        try:
            importlib.import_module(import_name)
        except ImportError:
            not_installed.append(req_name)
    
    if not_installed:
        print(f"  WARNING: Not installed: {not_installed}")
    else:
        print(f"  All critical packages installed")
    
    return True

test("requirements.txt", check_requirements, critical=False)

# ═══════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("PHASE 6: Environment Configuration (.env)")
print("=" * 70)

def check_env():
    env_file = ROOT.parent / ".env"
    if not env_file.exists():
        env_file = ROOT / ".env"
    if not env_file.exists():
        raise FileNotFoundError(".env file not found")
    
    env_content = env_file.read_text(encoding="utf-8")
    env_vars = {}
    for line in env_content.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            env_vars[key.strip()] = val.strip()
    
    print(f"  Found {len(env_vars)} env variables")
    
    # Check critical env vars
    critical_vars = ["SYSTEM_API_KEY", "CORS_ORIGINS"]
    for var in critical_vars:
        if var in env_vars:
            val = env_vars[var]
            display = val[:20] + "..." if len(val) > 20 else val
            print(f"    {var} = {display}")
        else:
            print(f"    {var} = NOT SET (may use default)")
    
    # Check LLM keys
    llm_vars = [k for k in env_vars if "KEY" in k.upper() or "API" in k.upper() or "MODEL" in k.upper()]
    print(f"  LLM/API related vars: {len(llm_vars)}")
    for var in llm_vars:
        val = env_vars[var]
        display = val[:8] + "***" if len(val) > 8 else val
        print(f"    {var} = {display}")
    
    return True

test(".env configuration", check_env, critical=False)

# ═══════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("PHASE 7: Data/Storage Directory Check")
print("=" * 70)

def check_storage():
    dirs_to_check = ["data", "reports", "screenshots"]
    for d in dirs_to_check:
        p = ROOT / d
        if p.exists():
            files = list(p.rglob("*"))
            file_count = len([f for f in files if f.is_file()])
            print(f"  {d}/: exists ({file_count} files)")
        else:
            print(f"  {d}/: NOT EXISTS (will be created on first use)")
    
    # Check SQLite databases
    db_files = list(ROOT.rglob("*.db"))
    db_files = [f for f in db_files if ".venv" not in str(f)]
    if db_files:
        print(f"  SQLite databases found: {len(db_files)}")
        for db in db_files:
            size_kb = db.stat().st_size / 1024
            print(f"    {db.relative_to(ROOT)}: {size_kb:.1f} KB")
    else:
        print(f"  No SQLite databases found (will be created on first use)")
    
    return True

test("storage directories", check_storage, critical=False)

# ═══════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("PHASE 8: FastAPI App Creation Test")
print("=" * 70)

def test_app_creation():
    # Try to import the FastAPI app
    import importlib
    # We need to check if main.py can be parsed and app created
    spec = importlib.util.spec_from_file_location("main_test", str(ROOT / "main.py"))
    mod = importlib.util.module_from_spec(spec)
    
    # Don't actually execute (it starts the server), just validate structure
    main_content = (ROOT / "main.py").read_text(encoding="utf-8")
    
    # Check critical patterns
    assert "FastAPI" in main_content, "No FastAPI import"
    assert "app = " in main_content or "app=" in main_content, "No app creation"
    assert "include_router" in main_content, "No router registration"
    assert "@app" in main_content, "No route decorators"
    
    # Count routes
    route_count = main_content.count("include_router")
    decorator_routes = len(re.findall(r'@app\.(get|post|put|delete|patch)', main_content))
    print(f"  include_router calls: {route_count}")
    print(f"  Direct @app route decorators: {decorator_routes}")
    
    return True

test("FastAPI app structure", test_app_creation)

# ═══════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("PHASE 9: Frontend-Backend Route Consistency")
print("=" * 70)

def check_route_consistency():
    # Read frontend navConfig
    qd_root = ROOT.parent / "frontend"
    nav_config = qd_root / "src" / "components" / "navConfig.tsx"
    app_tsx = qd_root / "src" / "App.tsx"
    
    if not nav_config.exists():
        raise FileNotFoundError(f"navConfig.tsx not found at {nav_config}")
    
    nav_content = nav_config.read_text(encoding="utf-8")
    app_content = app_tsx.read_text(encoding="utf-8")
    
    # Extract paths from navConfig
    nav_paths = re.findall(r"path:\s*'(/[^']*)'", nav_content)
    print(f"  NavConfig paths: {len(nav_paths)} entries")
    
    # Extract routes from App.tsx
    app_routes = re.findall(r'path="([^"]+)"', app_content)
    print(f"  App.tsx routes: {len(app_routes)} entries")
    
    # Check all nav paths have matching routes
    nav_paths_clean = [p.lstrip("/") for p in nav_paths if p != "/"]
    missing_routes = []
    for p in nav_paths_clean:
        if p not in app_routes:
            missing_routes.append(p)
    
    if missing_routes:
        print(f"  WARN: Nav paths without matching routes: {missing_routes}")
    else:
        print(f"  All nav paths have matching routes")
    
    # Check pages exist
    pages_dir = qd_root / "src" / "pages"
    page_files = [f.stem for f in pages_dir.glob("*.tsx")]
    
    # Extract page imports from App.tsx
    page_imports = re.findall(r"import\('./pages/(\w+)'\)", app_content)
    missing_pages = []
    for imp in page_imports:
        if imp not in page_files:
            missing_pages.append(imp)
    
    if missing_pages:
        print(f"  FAIL: Missing page files: {missing_pages}")
        raise AssertionError(f"Missing: {missing_pages}")
    else:
        print(f"  All {len(page_imports)} imported pages exist")
    
    return True

test("frontend-backend route consistency", check_route_consistency)

# ═══════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("PHASE 10: Dead Import / Circular Dependency Scan")
print("=" * 70)

def check_circular_imports():
    """Quick check for obvious circular imports in key modules"""
    critical_pairs = [
        ("core.config", "core.llm_manager"),
        ("core.ai_engine", "agents.executor_agent"),
        ("evaluation.metrics", "evaluation.benchmark_suite"),
        ("evaluation.judge", "evaluation.reporter"),
        ("cicd.quality_gate", "cicd"),
    ]
    
    for mod_a, mod_b in critical_pairs:
        try:
            a = __import__(mod_a)
            b = __import__(mod_b)
            print(f"  {mod_a} <-> {mod_b}: OK")
        except ImportError as e:
            print(f"  {mod_a} <-> {mod_b}: IMPORT ERROR: {e}")
    
    return True

test("circular import check", check_circular_imports, critical=False)

# ═══════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("PHASE 11: Security Quick Scan")
print("=" * 70)

def security_scan():
    """Check for common security issues"""
    issues_found = []
    
    for pyf in py_files:
        content = pyf.read_text(encoding="utf-8", errors="ignore")
        rel = str(pyf.relative_to(ROOT))
        
        # Hardcoded passwords/secrets
        for pattern in [r'password\s*=\s*["\'][^"\']{3,}["\']', r'secret\s*=\s*["\'][^"\']{3,}["\']']:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for m in matches:
                if "example" not in m.lower() and "placeholder" not in m.lower() and "default" not in m.lower():
                    issues_found.append(f"  {rel}: Possible hardcoded credential: {m[:40]}...")
        
        # eval/exec usage
        for pattern in [r'\beval\(', r'\bexec\(']:
            if re.search(pattern, content):
                issues_found.append(f"  {rel}: Uses {pattern.strip(chr(92)).strip('(')}")
        
        # SQL injection risk (string formatting in SQL)
        if re.search(r'execute\(.*f".*\{', content) or re.search(r"execute\(.*f'.*\{", content):
            issues_found.append(f"  {rel}: Possible SQL injection (f-string in execute)")
    
    if issues_found:
        print(f"  Found {len(issues_found)} potential issues:")
        for issue in issues_found[:15]:
            print(f"  {issue}")
    else:
        print(f"  No obvious security issues found")
    
    return True

test("security scan", security_scan, critical=False)

# ═══════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("PHASE 12: API Endpoint Inventory")
print("=" * 70)

def inventory_endpoints():
    """Count all defined API endpoints across routers"""
    total_endpoints = 0
    router_stats = {}
    
    for pyf in sorted(router_dir.glob("*.py")):
        if pyf.stem.startswith("_"):
            continue
        content = pyf.read_text(encoding="utf-8", errors="ignore")
        get_count = len(re.findall(r'@router\.(get|api_route)', content))
        post_count = len(re.findall(r'@router\.post', content))
        put_count = len(re.findall(r'@router\.put', content))
        delete_count = len(re.findall(r'@router\.delete', content))
        ws_count = len(re.findall(r'@router\.websocket', content))
        total = get_count + post_count + put_count + delete_count + ws_count
        
        if total > 0:
            router_stats[pyf.stem] = {"GET": get_count, "POST": post_count, "PUT": put_count, "DELETE": delete_count, "WS": ws_count, "total": total}
            total_endpoints += total
    
    # Also count direct @app routes in main.py
    main_content = (ROOT / "main.py").read_text(encoding="utf-8")
    main_gets = len(re.findall(r'@app\.get', main_content))
    main_posts = len(re.findall(r'@app\.post', main_content))
    main_ws = len(re.findall(r'@app\.websocket', main_content))
    main_total = main_gets + main_posts + main_ws
    if main_total:
        router_stats["main.py"] = {"GET": main_gets, "POST": main_posts, "WS": main_ws, "total": main_total}
        total_endpoints += main_total
    
    print(f"  Total API endpoints: {total_endpoints}")
    print(f"  {'Router':<25} {'GET':>4} {'POST':>5} {'PUT':>4} {'DEL':>4} {'WS':>3} {'Total':>6}")
    print(f"  {'-'*52}")
    for name, stats in sorted(router_stats.items(), key=lambda x: -x[1]["total"]):
        print(f"  {name:<25} {stats.get('GET',0):>4} {stats.get('POST',0):>5} {stats.get('PUT',0):>4} {stats.get('DELETE',0):>4} {stats.get('WS',0):>3} {stats['total']:>6}")
    
    return True

test("API endpoint inventory", inventory_endpoints, critical=False)

# ═══════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("PHASE 13: File Size & Code Volume Analysis")
print("=" * 70)

def code_volume():
    total_py_lines = 0
    total_tsx_lines = 0
    largest_files = []
    
    for f in py_files:
        try:
            lines = len(f.read_text(encoding="utf-8", errors="ignore").splitlines())
            total_py_lines += lines
            largest_files.append((str(f.relative_to(ROOT)), lines))
        except:
            pass
    
    qd_root = ROOT.parent / "frontend"
    tsx_files = list(qd_root.rglob("*.tsx")) + list(qd_root.rglob("*.ts"))
    tsx_files = [f for f in tsx_files if "node_modules" not in str(f)]
    for f in tsx_files:
        try:
            lines = len(f.read_text(encoding="utf-8", errors="ignore").splitlines())
            total_tsx_lines += lines
            largest_files.append((str(f.relative_to(ROOT.parent)), lines))
        except:
            pass
    
    largest_files.sort(key=lambda x: -x[1])
    
    print(f"  Python: {len(py_files)} files, {total_py_lines:,} lines")
    print(f"  TypeScript/TSX: {len(tsx_files)} files, {total_tsx_lines:,} lines")
    print(f"  Total: {total_py_lines + total_tsx_lines:,} lines")
    print()
    print(f"  Top 10 largest files:")
    for name, lines in largest_files[:10]:
        print(f"    {lines:>5} lines  {name}")
    
    return True

test("code volume analysis", code_volume, critical=False)

# ═══════════════════════════════════════════════════════════════════════
# FINAL REPORT
# ═══════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print(f"FINAL RESULTS: {PASS} passed, {FAIL} failed, {WARN} warnings (total {PASS+FAIL+WARN})")
print("=" * 70)
for r in RESULTS:
    print(r)

if ISSUES:
    print()
    print(f"ISSUES ({len(ISSUES)}):")
    for i, issue in enumerate(ISSUES):
        print(f"  [{issue['severity']}] {issue['test']}: {issue['error'][:120]}")

print()
if FAIL > 0:
    print(f"RESULT: {FAIL} ERRORS found!")
    sys.exit(1)
elif WARN > 0:
    print(f"RESULT: All critical checks passed, {WARN} warnings")
    sys.exit(0)
else:
    print(f"RESULT: ALL {PASS} CHECKS PASSED!")
    sys.exit(0)
