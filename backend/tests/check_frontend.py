# -*- coding: utf-8 -*-
"""Static analysis of frontend component completeness"""
import os
import re

SRC = r"d:\workspace\ai_test_platform\frontend\src"

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ============================================================
# 1. Check App.tsx navigation completeness
# ============================================================
section("App.tsx navigation completeness check")
app_path = os.path.join(SRC, "App.tsx")
with open(app_path, "r", encoding="utf-8") as f:
    app_content = f.read()

# Extract all imported components
imports = re.findall(r"import\s+(\w+)\s+from\s+'./components/(\w+)'", app_content)
print(f"  Imported components ({len(imports)}):")
for name, path in imports:
    print(f"    {name} <- ./components/{path}")

# Extract activeTab types
tab_types = re.findall(r"'(\w+)'", re.findall(r"useState<(.+?)>", app_content)[0])
print(f"\n  Registered tab types ({len(tab_types)}):")
for t in tab_types:
    print(f"    '{t}'")

# Extract sidebar buttons
sidebar_tabs = re.findall(r"setActiveTab\('(\w+)'\)", app_content)
unique_tabs = sorted(set(sidebar_tabs))
print(f"\n  Sidebar buttons ({len(unique_tabs)}):")
for t in unique_tabs:
    print(f"    '{t}'")

# Extract content-area rendering
render_tabs = re.findall(r"activeTab\s*===\s*'(\w+)'", app_content)
unique_renders = sorted(set(render_tabs))
print(f"\n  Content-area rendering ({len(unique_renders)}):")
for t in unique_renders:
    print(f"    '{t}'")

# Cross-check
missing_renders = set(unique_tabs) - set(unique_renders)
missing_buttons = set(unique_renders) - set(unique_tabs)
if missing_renders:
    print(f"\n  ❌ Sidebar buttons without rendered content: {missing_renders}")
else:
    print(f"\n  ✅ Every sidebar button has a corresponding content area")
if missing_buttons:
    print(f"  ❌ Rendered content without sidebar buttons: {missing_buttons}")

# ============================================================
# 2. Check component file completeness
# ============================================================
section("Component file completeness check")
comp_dir = os.path.join(SRC, "components")
tsx_files = [f for f in os.listdir(comp_dir) if f.endswith(".tsx")]
print(f"  Component files ({len(tsx_files)}):")

for f in sorted(tsx_files):
    fpath = os.path.join(comp_dir, f)
    with open(fpath, "r", encoding="utf-8") as fp:
        content = fp.read()
    
    lines = content.count("\n") + 1
    has_export = "export default" in content
    has_react = "React" in content or "react" in content
    api_calls = len(re.findall(r"fetch\(|API_ENDPOINTS\.", content))
    state_count = len(re.findall(r"useState", content))
    
    status = "✅" if has_export and has_react else "❌"
    print(f"    {status} {f:35s} {lines:4d} lines  exports:{has_export}  states:{state_count}  api_calls:{api_calls}")

# ============================================================
# 3. Check config.ts API endpoint completeness
# ============================================================
section("config.ts API endpoint check")
config_path = os.path.join(SRC, "config.ts")
with open(config_path, "r", encoding="utf-8") as f:
    config_content = f.read()

# Extract all endpoint groups
groups = re.findall(r"//\s*(.+?)\n\s*(\w+):\s*\{([^}]+)\}", config_content)
total_endpoints = 0
for comment, group_name, endpoints_block in groups:
    ep_count = len(re.findall(r"(\w+):\s*`", endpoints_block))
    total_endpoints += ep_count
    print(f"  [{group_name}] {comment.strip()} — {ep_count} endpoints")

print(f"\n  📊 Total configured frontend endpoints: {total_endpoints}")

# ============================================================
# 4. Check CSS style completeness
# ============================================================
section("Stylesheet checks")
css_files = [f for f in os.listdir(SRC) if f.endswith(".css")]
for f in css_files:
    fpath = os.path.join(SRC, f)
    with open(fpath, "r", encoding="utf-8") as fp:
        content = fp.read()
    lines = content.count("\n") + 1
    print(f"  {f}: {lines} lines")

print("\n✅ Frontend static analysis completed")
