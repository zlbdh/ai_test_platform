# -*- coding: utf-8 -*-
"""Module import verification"""
import importlib
import sys
sys.path.insert(0, ".")

modules = [
    # Core
    "core.requirement_parser", "core.db_tools", "core.api_doc_generator",
    # Services
    "services.grpc_testing", "services.enhanced_security",
    "services.batch_runner", "services.data_factory",
    "services.accessibility_testing", "services.i18n_testing",
    "services.compliance_testing", "services.chaos_engineering",
    "services.mobile_emulation",
    # Routers
    "routers.core", "routers.testing", "routers.knowledge",
    "routers.graphql", "routers.websocket_test", "routers.grpc",
    "routers.database", "routers.accessibility", "routers.i18n",
    "routers.compliance", "routers.chaos", "routers.mobile",
    # Agent
    "agents.planner_agent", "agents.executor_agent", "agents.exploratory_agent",
]

ok = 0
fail = 0
for m in modules:
    try:
        importlib.import_module(m)
        ok += 1
        print(f"  OK  {m}")
    except Exception as e:
        fail += 1
        err = str(e).split("\n")[0][:80]
        print(f"  ERR {m}: {err}")

print(f"\nResult: {ok}/{ok+fail} modules loaded ({fail} failed)")
