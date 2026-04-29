---
name: prototype-test-interaction-flow
description: 原型测试中的交互流程检查技能。用于验证导航入口、主操作链、页面跳转、弹窗开启、提交确认、返回路径和结果态已形成真实闭环。适用于：检查页面存在但动作不通的问题、复核主链路闭环情况、解释“看起来有功能但实际走不通”的场景。
---

# 主操作链与交互闭环检查

沿着用户的动作链去验证，不把“页面都在”误判成“流程闭环”。

## 先读什么

- 本地 [references/flow-checklist.md](references/flow-checklist.md)
- 共享 [../prototype-test-engineering/references/evidence-spec.md](../prototype-test-engineering/references/evidence-spec.md)

## 执行步骤

1. 选择一个明确的入口页。
2. 列出用户完成该任务必须经过的动作节点。
3. 逐步验证入口、跳转、弹窗打开、确认、返回、结果态。
4. 遇到中断时明确记 `broken_flow` 或 `static_unprovable`。
5. 把完成路径和断裂点都写清楚。

## 强制规则

- 看到按钮不等于动作可执行。
- 弹窗按钮存在但弹窗内容未证实，不得判定流程闭环。
- 详情页能打开但无返回、无保存、无结果态时，仍算流程缺口。

## 交付物

- 关键流程路径
- 断裂点与原因
- 主流程闭环结论

使用 [templates/output.md](templates/output.md) 输出。
