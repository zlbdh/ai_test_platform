"""
Comprehensive verification script: check syntax, imports, and basic functionality of all new modules
"""
import sys
import os
import traceback

# Set the project root one level above tests/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

PASS = 0
FAIL = 0
RESULTS = []

def test(name, func):
    global PASS, FAIL
    try:
        func()
        PASS += 1
        RESULTS.append(f"  PASS {name}")
    except Exception as e:
        FAIL += 1
        RESULTS.append(f"  FAIL {name}: {e}")

# ── 1. Python syntax checks ───────────────────────────────────────────

print("=" * 60)
print("1. Python Syntax Check")
print("=" * 60)

NEW_FILES = [
    "evaluation/__init__.py",
    "evaluation/metrics.py",
    "evaluation/judge.py",
    "evaluation/benchmark_suite.py",
    "evaluation/reporter.py",
    "routers/evaluation.py",
    "core/semantic_engine.py",
    "core/semantic_actions.py",
    "core/smart_locator.py",
    "core/test_generator.py",
    "core/scenario_generator.py",
    "cicd/__init__.py",
    "cicd/quality_gate.py",
    "routers/quality_gate.py",
    "routers/semantic.py",
]

# MCP files checked separately due to naming conflict
MCP_FILES = [
    "mcp/__init__.py",
    "mcp/tools.py",
    "mcp/server.py",
]

import py_compile
for f in NEW_FILES + MCP_FILES:
    fpath = os.path.join(PROJECT_ROOT, f)
    test(f"syntax: {f}", lambda fpath=fpath: py_compile.compile(fpath, doraise=True))

# ── 2. Module import verification ──────────────────────────────────────────────

print()
print("=" * 60)
print("2. Module Import")
print("=" * 60)

test("import evaluation", lambda: __import__("evaluation"))
test("import evaluation.metrics", lambda: __import__("evaluation.metrics"))
test("import evaluation.judge", lambda: __import__("evaluation.judge"))
test("import evaluation.benchmark_suite", lambda: __import__("evaluation.benchmark_suite"))
test("import evaluation.reporter", lambda: __import__("evaluation.reporter"))

# MCP: The installed mcp package requires loading this project's module directly with importlib
def import_our_mcp_tools():
    import importlib.util
    spec = importlib.util.spec_from_file_location("our_mcp_tools", os.path.join(PROJECT_ROOT, "mcp", "tools.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
test("import mcp/tools.py", import_our_mcp_tools)

def import_our_mcp_server():
    import importlib.util
    spec = importlib.util.spec_from_file_location("our_mcp_server", os.path.join(PROJECT_ROOT, "mcp", "server.py"))
    mod = importlib.util.module_from_spec(spec)
    # mcp/server.py has sys.path.insert at top, which is fine
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass  # __main__ guard
    return mod
test("import mcp/server.py", import_our_mcp_server)

test("import core.semantic_engine", lambda: __import__("core.semantic_engine"))
test("import core.smart_locator", lambda: __import__("core.smart_locator"))
test("import core.scenario_generator", lambda: __import__("core.scenario_generator"))
test("import cicd", lambda: __import__("cicd"))
test("import cicd.quality_gate", lambda: __import__("cicd.quality_gate"))

# ── 3. Evaluation metric functionality checks ──────────────────────────────────────────

print()
print("=" * 60)
print("3. Evaluation Metrics")
print("=" * 60)

def test_metrics():
    from evaluation.metrics import ALL_METRICS
    assert len(ALL_METRICS) == 8, f"Expected 8, got {len(ALL_METRICS)}"
    for m in ALL_METRICS:
        assert m.name, f"Missing name"
        assert m.description, f"Missing description for {m.name}"
test("ALL_METRICS count=8", test_metrics)

def test_metric_names():
    from evaluation.metrics import ALL_METRICS
    names = [m.name for m in ALL_METRICS]
    expected = ["plan_completeness", "execution_fidelity", "healing_success_rate",
                "hallucination_score", "token_efficiency", "consistency_score",
                "step_accuracy", "goal_achievement"]
    for e in expected:
        assert e in names, f"Missing: {e}"
test("metric names complete", test_metric_names)

def test_aggregate():
    from evaluation.metrics import compute_overall_score, MetricResult
    results = {"a": MetricResult(metric_name="a", score=0.8, raw_value={}), "b": MetricResult(metric_name="b", score=0.6, raw_value={})}
    score = compute_overall_score(results)
    assert 0.6 <= score <= 0.8, f"overall_score out of range: {score}"
test("compute_overall_score", test_aggregate)

# ── 4. Benchmark scenario checks ──────────────────────────────────────────────

print()
print("=" * 60)
print("4. Benchmark Suite")
print("=" * 60)

def test_builtin_scenarios():
    from evaluation.benchmark_suite import BUILTIN_SCENARIOS
    assert len(BUILTIN_SCENARIOS) == 8
    for s in BUILTIN_SCENARIOS:
        assert s.id and s.goal and s.target_url
test("builtin scenarios=8", test_builtin_scenarios)

def test_benchmark_list():
    from evaluation.benchmark_suite import BenchmarkSuite
    suite = BenchmarkSuite()
    all_s = suite.list_scenarios()
    assert len(all_s) >= 8
    search_s = suite.list_scenarios(category="search")
    assert len(search_s) >= 2
test("list+filter scenarios", test_benchmark_list)

def test_custom_scenario():
    from evaluation.benchmark_suite import BenchmarkSuite, BenchmarkScenario
    suite = BenchmarkSuite()
    custom = BenchmarkScenario(name="Test", goal="Test goal", category="custom", target_url="https://example.com")
    suite.add_custom_scenario(custom)
    assert custom.id
    assert suite.get_scenario(custom.id) is not None
test("custom scenario CRUD", test_custom_scenario)

def test_save_result():
    from evaluation.benchmark_suite import BenchmarkSuite, BenchmarkRunResult
    suite = BenchmarkSuite()
    result = BenchmarkRunResult(scenario_id="search_baidu", model="test-model", success=True, overall_score=0.85)
    suite.save_run_result(result, "test goal")
    results = suite.get_results(scenario_id="search_baidu", limit=5)
    assert len(results) >= 1
test("save+get run results", test_save_result)

def test_model_compare():
    from evaluation.benchmark_suite import BenchmarkSuite
    suite = BenchmarkSuite()
    comparison = suite.compare_models()
    assert "models" in comparison
test("model comparison", test_model_compare)

# ── 5. Report generation checks ──────────────────────────────────────────────

print()
print("=" * 60)
print("5. Reporter")
print("=" * 60)

def test_reporter_summary():
    from evaluation.reporter import EvaluationReporter
    reporter = EvaluationReporter()
    report = reporter.generate_summary(
        metric_results={"step_accuracy": {"score": 0.85, "name": "step_accuracy"}},
        overall_score=0.85,
    )
    assert report["report_type"] == "evaluation_summary"
    assert report["grade"] == "A"
test("summary report", test_reporter_summary)

def test_grades():
    from evaluation.reporter import EvaluationReporter
    g = EvaluationReporter._score_to_grade
    assert g(0.95) == "A+" and g(0.85) == "A" and g(0.75) == "B"
    assert g(0.65) == "C" and g(0.55) == "D" and g(0.3) == "F"
test("grade mapping", test_grades)

def test_comparison():
    from evaluation.reporter import EvaluationReporter
    r = EvaluationReporter()
    results = [
        {"run_id": "r1", "model": "gpt-4", "overall_score": 0.9, "success": True, "duration_ms": 5000, "total_tokens": 1000},
        {"run_id": "r2", "model": "gpt-3.5", "overall_score": 0.7, "success": True, "duration_ms": 3000, "total_tokens": 500},
    ]
    report = r.generate_comparison(results)
    assert report["best_model"] == "gpt-4"
test("comparison report", test_comparison)

def test_trend():
    from evaluation.reporter import EvaluationReporter
    import time
    r = EvaluationReporter()
    results = [
        {"overall_score": 0.5, "timestamp": time.time()-100, "model": "m1", "success": True},
        {"overall_score": 0.6, "timestamp": time.time()-50, "model": "m1", "success": True},
        {"overall_score": 0.8, "timestamp": time.time(), "model": "m1", "success": True},
    ]
    trend = r.generate_trend(results)
    assert trend["trend_direction"] == "improving"
test("trend report", test_trend)

# ── 6. MCP tool checks ──────────────────────────────────────────────

print()
print("=" * 60)
print("6. MCP Tools")
print("=" * 60)

def test_mcp_tools_count():
    mod = import_our_mcp_tools()
    assert len(mod.PLATFORM_TOOLS) == 12
    for t in mod.PLATFORM_TOOLS:
        schema = t.to_schema()
        assert "name" in schema and "inputSchema" in schema
test("12 tools with valid schema", test_mcp_tools_count)

def test_mcp_tool_names():
    mod = import_our_mcp_tools()
    names = [t.name for t in mod.PLATFORM_TOOLS]
    for expected in ["run_test", "get_test_status", "get_screenshot", "browse_and_verify",
                     "get_test_report", "list_sessions", "run_api_test", "evaluate_agent",
                     "generate_test_data", "get_analytics", "get_execution_history", "trigger_ci_test"]:
        assert expected in names, f"Missing: {expected}"
test("tool names complete", test_mcp_tool_names)

# ── 7. Quality gate checks ──────────────────────────────────────────────

print()
print("=" * 60)
print("7. Quality Gate")
print("=" * 60)

def test_gate_pass():
    from cicd.quality_gate import QualityGateEngine
    gate = QualityGateEngine()
    scores = {"goal_achievement": 0.95, "step_accuracy": 0.85, "hallucination_score": 0.9,
              "healing_success_rate": 0.8, "token_efficiency": 0.7}
    v = gate.check(scores, "tp")
    assert v.status.value == "passed", f"Got {v.status}"
test("gate PASS scenario", test_gate_pass)

def test_gate_fail():
    from cicd.quality_gate import QualityGateEngine
    gate = QualityGateEngine()
    scores = {"goal_achievement": 0.3, "step_accuracy": 0.4, "hallucination_score": 0.5}
    v = gate.check(scores, "tf")
    assert v.status.value == "failed"
    assert sum(1 for c in v.checks if c.status.value == "failed") >= 2
test("gate FAIL scenario", test_gate_fail)

def test_gate_warning():
    from cicd.quality_gate import QualityGateEngine
    gate = QualityGateEngine()
    scores = {"goal_achievement": 0.85, "step_accuracy": 0.75, "hallucination_score": 0.85,
              "healing_success_rate": 0.5, "token_efficiency": 0.4}
    v = gate.check(scores, "tw")
    assert v.status.value == "warning", f"Got {v.status}"
test("gate WARNING scenario", test_gate_warning)

def test_gate_rules():
    from cicd.quality_gate import QualityGateEngine
    gate = QualityGateEngine()
    assert len(gate.list_rules()) >= 5
test("gate rules >= 5", test_gate_rules)

def test_gate_custom_rule():
    from cicd.quality_gate import QualityGateEngine, GateRule
    gate = QualityGateEngine()
    gate.add_rule(GateRule(name="test_custom", metric="token_efficiency", threshold=0.9, severity="info"))
    assert any(r["name"] == "test_custom" for r in gate.list_rules())
test("gate add custom rule", test_gate_custom_rule)

def test_gate_verdict_dict():
    from cicd.quality_gate import QualityGateEngine
    gate = QualityGateEngine()
    v = gate.check({"goal_achievement": 0.9, "step_accuracy": 0.8, "hallucination_score": 0.85}, "td")
    d = v.to_dict()
    assert "status" in d and "checks" in d and "passed" in d
    assert "total_checks" in d and "passed_checks" in d
test("gate verdict to_dict", test_gate_verdict_dict)

# ── 8. CI/CD change analysis checks ─────────────────────────────────────────

print()
print("=" * 60)
print("8. CI/CD Change Impact")
print("=" * 60)

def test_impact_core():
    from cicd import ChangeImpactAnalyzer
    a = ChangeImpactAnalyzer()
    r = a.analyze(["core/llm_manager.py", "agents/executor_agent.py"])
    assert r.impact_score >= 0.9
    assert "full_regression" in r.selected_tests
test("core+agent -> full_regression", test_impact_core)

def test_impact_ui():
    from cicd import ChangeImpactAnalyzer
    a = ChangeImpactAnalyzer()
    r = a.analyze(["src/pages/DashboardPage.tsx"])
    assert "ui_functional" in r.selected_tests
test("tsx -> ui_functional", test_impact_ui)

def test_impact_empty():
    from cicd import ChangeImpactAnalyzer
    a = ChangeImpactAnalyzer()
    r = a.analyze([])
    assert r.reason == "No file changes"
test("empty -> no tests", test_impact_empty)

def test_github_webhook():
    from cicd import GitHubIntegration
    gh = GitHubIntegration()
    r = gh.process_webhook({
        "action": "opened",
        "pull_request": {"number": 1, "head": {"ref": "feat", "sha": "abc"}, "base": {"ref": "main"}, "title": "test"},
        "repository": {"full_name": "test/repo"},
        "files": [{"filename": "core/config.py"}],
    })
    assert r["action"] == "run_tests"
test("GitHub webhook", test_github_webhook)

def test_github_skip():
    from cicd import GitHubIntegration
    gh = GitHubIntegration()
    r = gh.process_webhook({"action": "closed", "pull_request": {"head": {"ref": "", "sha": ""}, "base": {"ref": ""}, "title": ""}})
    assert r["action"] == "skip"
test("GitHub skip closed", test_github_skip)

# ── 9. Semantic engine checks ──────────────────────────────────────────────

print()
print("=" * 60)
print("9. Semantic Engine")
print("=" * 60)

def test_sem_cache():
    from core.semantic_engine import SemanticCache
    c = SemanticCache(max_entries=5, ttl_seconds=10)
    c.set("k1", {"ok": True})
    assert c.get("k1") == {"ok": True}
    assert c.stats["hits"] == 1
test("SemanticCache read/write", test_sem_cache)

def test_sem_cache_evict():
    from core.semantic_engine import SemanticCache
    c = SemanticCache(max_entries=3, ttl_seconds=10)
    for i in range(5):
        c.set(f"k{i}", i)
    assert c.stats["size"] == 3
test("SemanticCache eviction", test_sem_cache_evict)

def test_sem_element():
    from core.semantic_engine import SemanticElement
    el = SemanticElement(element_id="e1", text="Login", role="button", confidence=0.95)
    assert el.to_dict()["confidence"] == 0.95
test("SemanticElement struct", test_sem_element)

def test_sem_locator_singleton():
    from core.semantic_engine import get_semantic_locator
    l1 = get_semantic_locator()
    l2 = get_semantic_locator()
    assert l1 is l2
test("SemanticLocator singleton", test_sem_locator_singleton)

def test_sem_cache_key():
    from core.semantic_engine import SemanticCache
    k = SemanticCache.make_key("https://example.com", "abc123")
    assert len(k) == 32  # md5 hex digest
test("SemanticCache.make_key", test_sem_cache_key)

# ── 10. Smart locator checks ────────────────────────────────────────────

print()
print("=" * 60)
print("10. Smart Locator")
print("=" * 60)

def test_fp_hash():
    from core.smart_locator import ElementFingerprint
    fp = ElementFingerprint(tag="button", text="Login", css_selector="#login-btn")
    assert len(fp.compute_hash()) == 12
test("Fingerprint hash", test_fp_hash)

def test_fp_match():
    from core.smart_locator import FingerprintMatcher, ElementFingerprint
    m = FingerprintMatcher()
    target = ElementFingerprint(tag="button", text="Login", css_selector="#login")
    candidates = [
        ElementFingerprint(tag="button", text="Login", css_selector="#login"),
        ElementFingerprint(tag="input", text="Search", css_selector="#q"),
    ]
    result = m.match(target, candidates)
    assert result and result[0].text == "Login" and result[1] >= 0.8
test("Fingerprint match", test_fp_match)

def test_fp_no_match():
    from core.smart_locator import FingerprintMatcher, ElementFingerprint
    m = FingerprintMatcher()
    target = ElementFingerprint(tag="button", text="Very Unique")
    candidates = [ElementFingerprint(tag="input", text="Search")]
    assert m.match(target, candidates, threshold=0.8) is None
test("Fingerprint no match", test_fp_no_match)

def test_locator_hist():
    from core.smart_locator import get_locator_history, ElementFingerprint
    h = get_locator_history()
    fp = ElementFingerprint(tag="button", text="Test", page_url_pattern="https://example.com")
    h.record(fp, "#test-btn", True, "selector")
    h.record(fp, "#test-btn", True, "selector")
    h.record(fp, "xpath://button", False, "xpath")
    best = h.get_best_selector(fp.compute_hash())
    assert best == "#test-btn"
test("LocatorHistory best selector", test_locator_hist)

def test_flaky():
    from core.smart_locator import get_flaky_detector
    d = get_flaky_detector()
    assert d.check("nonexistent")["is_flaky"] == False
test("FlakyDetector safe check", test_flaky)

# ── 11. Scenario generator checks ────────────────────────────────────────────

print()
print("=" * 60)
print("11. Scenario Generator")
print("=" * 60)

def test_string_boundary():
    from core.scenario_generator import ScenarioGenerator
    g = ScenarioGenerator()
    r = g.generate_boundary_scenarios("username", "string")
    assert len(r) >= 9
    assert any("SQL" in s["title"] for s in r)
test("string boundary >= 9", test_string_boundary)

def test_email_boundary2():
    from core.scenario_generator import ScenarioGenerator
    g = ScenarioGenerator()
    r = g.generate_boundary_scenarios("email", "email")
    assert len(r) >= 5
test("email boundary >= 5", test_email_boundary2)

def test_negative_gen():
    from core.scenario_generator import ScenarioGenerator
    g = ScenarioGenerator()
    flow = [{"action": "input username"}, {"action": "input password"}, {"action": "click login"}]
    r = g.generate_negative_scenarios(flow)
    assert len(r) >= 6
    assert any("skip" in s.get("title", "").lower() or "跳过" in s.get("title", "") for s in r)
test("negative scenarios >= 6", test_negative_gen)

def test_security_gen():
    from core.scenario_generator import ScenarioGenerator
    g = ScenarioGenerator()
    r = g.generate_security_scenarios("https://example.com")
    assert len(r) == 7
test("security scenarios = 7", test_security_gen)

def test_combo_gen():
    from core.scenario_generator import ScenarioGenerator
    g = ScenarioGenerator()
    r = g.generate_combination_scenarios({"role": ["admin", "user"], "status": ["active", "inactive", "pending"]})
    assert len(r) == 6
test("combination 2x3=6", test_combo_gen)

def test_perf_gen():
    from core.scenario_generator import ScenarioGenerator
    g = ScenarioGenerator()
    r = g.generate_performance_scenarios("https://example.com")
    assert len(r) == 3
test("performance scenarios = 3", test_perf_gen)

# ── 12. Semantic action parsing checks ──────────────────────────────────────────

print()
print("=" * 60)
print("12. Semantic Action Parsing")
print("=" * 60)

def test_parse_click2():
    from core.semantic_actions import _parse_instruction
    a, _, _ = _parse_instruction("点击登录按钮")
    assert a == "click"
test("parse: click", test_parse_click2)

def test_parse_fill2():
    from core.semantic_actions import _parse_instruction
    a, _, v = _parse_instruction("在搜索框中输入'AI测试'")
    assert a == "fill" and v == "AI测试"
test("parse: fill with value", test_parse_fill2)

def test_parse_select2():
    from core.semantic_actions import _parse_instruction
    a, _, v = _parse_instruction("选择下拉菜单中的'中文'选项")
    assert a == "select" and v == "中文"
test("parse: select", test_parse_select2)

def test_parse_nav():
    from core.semantic_actions import _parse_instruction
    a, _, _ = _parse_instruction("打开百度首页")
    assert a == "navigate"
test("parse: navigate", test_parse_nav)

def test_parse_english():
    from core.semantic_actions import _parse_instruction
    a, _, _ = _parse_instruction("click the submit button")
    assert a == "click"
test("parse: english click", test_parse_english)

# ── 13. Judge structure checks ────────────────────────────────────────────

print()
print("=" * 60)
print("13. LLM Judge")
print("=" * 60)

def test_judge_result2():
    from evaluation.judge import JudgeResult
    r = JudgeResult(scores={"completeness": 8, "accuracy": 9}, overall_score=8.5, reasoning="Good")
    d = r.to_dict()
    assert d["overall_score"] == 8.5 and len(d["scores"]) == 2
test("JudgeResult struct", test_judge_result2)

def test_judge_parse2():
    from evaluation.judge import LLMJudge
    j = LLMJudge()
    resp = '{"completeness": 8, "accuracy": 9, "efficiency": 7, "robustness": 6, "clarity": 8, "reasoning": "good", "suggestions": ["test"]}'
    r = j._parse_response(resp)
    assert r.overall_score == 7.6
    assert r.scores["efficiency"] == 7
test("Judge parse JSON", test_judge_parse2)

def test_judge_parse_md():
    from evaluation.judge import LLMJudge
    j = LLMJudge()
    resp = '```json\n{"completeness": 5, "accuracy": 5, "efficiency": 5, "robustness": 5, "clarity": 5, "reasoning": "ok", "suggestions": []}\n```'
    r = j._parse_response(resp)
    assert r.overall_score == 5.0
test("Judge parse markdown", test_judge_parse_md)

def test_judge_parse_bad():
    from evaluation.judge import LLMJudge
    j = LLMJudge()
    r = j._parse_response("not json at all")
    assert r.overall_score == 5.0  # fallback
test("Judge parse bad input", test_judge_parse_bad)

# ── Print results ──────────────────────────────────────────────────────

print()
print("=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed (total {PASS + FAIL})")
print("=" * 60)
for r in RESULTS:
    print(r)
print()
if FAIL > 0:
    print(f"FAILED: {FAIL} tests failed!")
    sys.exit(1)
else:
    print(f"ALL {PASS} TESTS PASSED!")
    sys.exit(0)
