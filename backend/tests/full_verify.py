# -*- coding: utf-8 -*-
"""全项目验证脚本"""
import requests
import json
import importlib
import sys
import os

BASE = "http://localhost:8020"

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ============================================================
# 1.1 健康检查
# ============================================================
section("1.1 服务健康检查")
for path, label in [("/", "根路径"), ("/docs", "Swagger UI"), ("/openapi.json", "OpenAPI")]:
    try:
        r = requests.get(f"{BASE}{path}", timeout=5)
        print(f"  ✅ {label}: HTTP {r.status_code}")
    except Exception as e:
        print(f"  ❌ {label}: {e}")

# ============================================================
# 1.2 全量端点清单
# ============================================================
section("1.2 全量 API 端点清单")
r = requests.get(f"{BASE}/openapi.json", timeout=5)
spec = r.json()
info = spec["info"]
print(f"  API: {info['title']} v{info['version']}")
paths = spec["paths"]
groups = {}
for p in sorted(paths.keys()):
    prefix = "/".join(p.split("/")[:3])
    groups.setdefault(prefix, []).append((p, list(paths[p].keys())))

total = 0
for g, routes in sorted(groups.items()):
    print(f"\n  [{g}] — {len(routes)} 端点")
    for path, methods in routes:
        ms = ", ".join(m.upper() for m in methods)
        print(f"    {ms:10s} {path}")
        total += 1
print(f"\n  📊 API 端点总数: {total}")

# ============================================================
# 1.2b GET 可达性
# ============================================================
section("1.2b GET 端点可达性测试")
get_paths = [p for p in paths if "get" in paths[p] and "{" not in p]
ok = fail = 0
for p in sorted(get_paths):
    try:
        r = requests.get(f"{BASE}{p}", timeout=5)
        if r.status_code < 500:
            ok += 1
            print(f"  ✅ {p} -> {r.status_code}")
        else:
            fail += 1
            print(f"  ❌ {p} -> {r.status_code}")
    except Exception as e:
        fail += 1
        print(f"  ❌ {p} -> ERROR")
print(f"\n  GET 可达: {ok}/{ok+fail}")

# ============================================================
# 1.2c POST 端点冒烟测试
# ============================================================
section("1.2c POST 端点冒烟测试 (空请求)")
post_paths = [p for p in paths if "post" in paths[p] and "{" not in p]
alive = dead = 0
for p in sorted(post_paths):
    try:
        r = requests.post(f"{BASE}{p}", json={}, timeout=5)
        if r.status_code < 500:
            alive += 1
            print(f"  ✅ {p} -> {r.status_code}")
        else:
            # 422 = validation error (expected for empty body), 500 = server error
            if r.status_code == 422:
                alive += 1
                print(f"  ✅ {p} -> 422 (validation expected)")
            else:
                dead += 1
                print(f"  ❌ {p} -> {r.status_code}")
    except Exception as e:
        dead += 1
        print(f"  ❌ {p} -> ERROR/TIMEOUT")
print(f"\n  POST 存活: {alive}/{alive+dead}")

# ============================================================
# 2. 模块导入验证
# ============================================================
section("2. 后端模块导入验证")

modules_to_check = {
    "核心模块": [
        "core.requirement_parser",
        "core.db_tools",
        "core.api_doc_generator",
    ],
    "服务模块": [
        "services.grpc_testing",
        "services.enhanced_security",
        "services.performance_testing",
        "services.batch_runner",
        "services.data_factory",
        "services.accessibility_testing",
        "services.i18n_testing",
        "services.compliance_testing",
        "services.chaos_engineering",
        "services.mobile_emulation",
    ],
    "路由模块": [
        "routers.core",
        "routers.testing",
        "routers.knowledge",
        "routers.graphql",
        "routers.websocket_test",
        "routers.grpc",
        "routers.database",
        "routers.accessibility",
        "routers.i18n",
        "routers.compliance",
        "routers.chaos",
        "routers.mobile",
    ],
    "Agent 模块": [
        "agents.planner_agent",
        "agents.executor_agent",
        "agents.exploratory_agent",
    ],
}

total_ok = total_fail = 0
for group, mods in modules_to_check.items():
    print(f"\n  [{group}]")
    for mod in mods:
        try:
            importlib.import_module(mod)
            total_ok += 1
            print(f"    ✅ {mod}")
        except Exception as e:
            total_fail += 1
            err = str(e).split("\n")[0][:60]
            print(f"    ❌ {mod}: {err}")

print(f"\n  模块导入: {total_ok}/{total_ok+total_fail}")

# ============================================================
# 总结
# ============================================================
section("验证总结")
print(f"  API 端点总数: {total}")
print(f"  GET 可达:     {ok}/{ok+fail}")
print(f"  POST 存活:    {alive}/{alive+dead}")
print(f"  模块导入:     {total_ok}/{total_ok+total_fail}")
print()
