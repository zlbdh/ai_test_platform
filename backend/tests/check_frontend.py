# -*- coding: utf-8 -*-
"""前端组件完整性静态分析"""
import os
import re

SRC = r"d:\workspace\ai_test_platform\frontend\src"

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ============================================================
# 1. 检查 App.tsx 导航完整性
# ============================================================
section("App.tsx 导航完整性检查")
app_path = os.path.join(SRC, "App.tsx")
with open(app_path, "r", encoding="utf-8") as f:
    app_content = f.read()

# 提取所有导入的组件
imports = re.findall(r"import\s+(\w+)\s+from\s+'./components/(\w+)'", app_content)
print(f"  导入的组件 ({len(imports)}):")
for name, path in imports:
    print(f"    {name} <- ./components/{path}")

# 提取 activeTab 类型
tab_types = re.findall(r"'(\w+)'", re.findall(r"useState<(.+?)>", app_content)[0])
print(f"\n  注册的 Tab 类型 ({len(tab_types)}):")
for t in tab_types:
    print(f"    '{t}'")

# 提取侧栏按钮
sidebar_tabs = re.findall(r"setActiveTab\('(\w+)'\)", app_content)
unique_tabs = sorted(set(sidebar_tabs))
print(f"\n  侧栏按钮 ({len(unique_tabs)}):")
for t in unique_tabs:
    print(f"    '{t}'")

# 提取内容区域渲染
render_tabs = re.findall(r"activeTab\s*===\s*'(\w+)'", app_content)
unique_renders = sorted(set(render_tabs))
print(f"\n  内容区域渲染 ({len(unique_renders)}):")
for t in unique_renders:
    print(f"    '{t}'")

# 交叉检查
missing_renders = set(unique_tabs) - set(unique_renders)
missing_buttons = set(unique_renders) - set(unique_tabs)
if missing_renders:
    print(f"\n  ❌ 有侧栏按钮但缺少渲染: {missing_renders}")
else:
    print(f"\n  ✅ 所有侧栏按钮都有对应渲染区域")
if missing_buttons:
    print(f"  ❌ 有渲染但缺少侧栏按钮: {missing_buttons}")

# ============================================================
# 2. 检查组件文件完整性
# ============================================================
section("组件文件完整性检查")
comp_dir = os.path.join(SRC, "components")
tsx_files = [f for f in os.listdir(comp_dir) if f.endswith(".tsx")]
print(f"  组件文件 ({len(tsx_files)}):")

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
    print(f"    {status} {f:35s} {lines:4d}行  exports:{has_export}  states:{state_count}  api_calls:{api_calls}")

# ============================================================
# 3. 检查 config.ts API 端点完整性
# ============================================================
section("config.ts API 端点检查")
config_path = os.path.join(SRC, "config.ts")
with open(config_path, "r", encoding="utf-8") as f:
    config_content = f.read()

# 提取所有端点组
groups = re.findall(r"//\s*(.+?)\n\s*(\w+):\s*\{([^}]+)\}", config_content)
total_endpoints = 0
for comment, group_name, endpoints_block in groups:
    ep_count = len(re.findall(r"(\w+):\s*`", endpoints_block))
    total_endpoints += ep_count
    print(f"  [{group_name}] {comment.strip()} — {ep_count} 端点")

print(f"\n  📊 前端配置端点总数: {total_endpoints}")

# ============================================================
# 4. 检查 CSS 样式完整性
# ============================================================
section("样式文件检查")
css_files = [f for f in os.listdir(SRC) if f.endswith(".css")]
for f in css_files:
    fpath = os.path.join(SRC, f)
    with open(fpath, "r", encoding="utf-8") as fp:
        content = fp.read()
    lines = content.count("\n") + 1
    print(f"  {f}: {lines} 行")

print("\n✅ 前端静态分析完成")
