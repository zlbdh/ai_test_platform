---
name: prototype-test-exception-boundary-check
description: 原型测试中的异常与边界检查技能。用于验证空态、失败态、删除/解绑等危险操作确认、异常提示、加载态、防重复提交、边界条件和阻断逻辑已被原型明确表达。适用于：发现正常流程之外的设计缺口、复核危险操作拦截、排查看起来完整但缺少保护措施的页面。
---

# 异常与边界检查

原型测试不能只盯正常流程；异常态和危险操作常常决定后期返工成本。

## 先读什么

- 本地 [references/exception-boundary-checklist.md](references/exception-boundary-checklist.md)
- 共享 [../prototype-test-engineering/references/issue-taxonomy.md](../prototype-test-engineering/references/issue-taxonomy.md)

## 执行步骤

1. 列出页面的高风险动作和高风险数据状态。
2. 检查以下设计元素：
   - 空态
   - 无结果态
   - 失败提示
   - 危险操作确认
   - 加载态或防重复提交表达
   - 删除/解绑/停用的前置拦截
3. 明确哪些已可验证，哪些仅是静态原型无法证明。
4. 对缺口打 `exception_gap`。

## 强制规则

- 危险操作没有确认文案或确认动作时，不算已承接。
- 只有“暂无数据”文案但无页面空态布局时，只能算弱承接。
- 需要后端参与的失败提示，若静态原型无表达，应标记为 `static_unprovable` 或 `exception_gap`。

## 交付物

- 异常/边界检查表
- 危险操作保护缺口
- 静态无法证明项

使用 [templates/output.md](templates/output.md) 输出。
