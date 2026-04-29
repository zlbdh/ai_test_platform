---
name: prototype-test-state-permission-check
description: 原型测试中的状态与权限检查技能。用于验证状态集合、状态流转条件、按钮显隐、角色可见性、只读态、禁用态、审核/上下架/启停等关键规则已被原型和需求共同承接。适用于：查状态流转不清、假通过按钮、角色差异缺失、审核类页面规则不闭环。
---

# 状态流转与权限显隐检查

把“状态”和“权限”当成高风险逻辑点单独验证，不把状态列或按钮存在误判为规则完整。

## 先读什么

- 本地 [references/state-permission-rules.md](references/state-permission-rules.md)
- 共享 [../prototype-test-engineering/references/issue-taxonomy.md](../prototype-test-engineering/references/issue-taxonomy.md)

## 执行步骤

1. 从需求解析结果中列出状态集合与状态变化条件。
2. 逐状态检查：
- 当前状态表达清晰
- 允许动作表达清晰
- 禁止动作具备禁用、隐藏或只读表现
3. 逐角色检查：
   - 谁能看见
   - 谁能操作
   - 谁只能查看
4. 对状态缺口打 `state_gap`，对权限缺口打 `permission_gap`。

## 强制规则

- 只有状态标签，没有流转条件，不算状态逻辑完整。
- 按钮存在但没有角色或状态约束，不算权限已承接。
- 审核类页面至少要确认通过/驳回/退回或等价结果态，不得只看一个主按钮。

## 交付物

- 状态矩阵
- 角色/按钮显隐矩阵
- 假通过风险清单

使用 [templates/output.md](templates/output.md) 输出。
