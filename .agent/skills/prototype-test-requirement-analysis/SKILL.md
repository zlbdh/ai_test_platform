---
name: prototype-test-requirement-analysis
description: 原型测试中的需求解析技能。用于读取需求文档并抽取模块、页面、角色、流程、规则、状态、字段、约束和验收线索，形成可用于页面映射、模块验证和门禁收口的结构化基线。适用于：只有需求文档时的需求测试、完整原型测试的第一步、复核某模块定义完整度、解释文档为什么不可测或与总览不一致。
---

# 需求解析与结构化抽取

把需求文档转成“后续 skill 可消费的事实矩阵”，不要停留在阅读摘要层。

## 先读什么

- 本地 [references/requirement-signals.md](references/requirement-signals.md)
- 共享 [../prototype-test-engineering/references/issue-taxonomy.md](../prototype-test-engineering/references/issue-taxonomy.md)
- 需要解释平台现有能力时，再读 [../prototype-test-engineering/references/current-system-mapping.md](../prototype-test-engineering/references/current-system-mapping.md)

## 执行步骤

1. 锁定唯一事实源，列出本轮允许使用的需求文件。
2. 逐份抽取：
   - 模块
   - 页面
   - 角色
   - 主流程
   - 状态与状态变化
   - 字段与约束
   - 异常分支
   - 跨模块依赖
3. 建立三个基线矩阵：
   - 模块-页面矩阵
   - 页面-字段/动作矩阵
   - 流程-状态矩阵
4. 用 `doc_gap`、`scope_gap`、`state_gap`、`field_gap`、`permission_gap` 等分类标问题。
5. 把“静态原型后续需要验证什么”也标出来，作为下游 skill 的输入。

## 强制规则

- 需求里没写的，不要替作者脑补成已定义。
- 总览文档和模块文档不一致时，显式记为 `doc_gap` 或 `scope_gap`，不要擅自择一忽略。
- 文档只写了页面名、没写动作和状态时，不得判定为“可测充分”。
- 需求测试的通过条件是“有证据支持的完整性”，不是“读起来像没问题”。

## 交付物

- 模块/页面/角色/流程/规则/状态/字段结构化摘要
- 文档问题清单
- 下游建议验证点
- 可直接交给 `prototype-test-page-mapping` 的页面清单

使用 [templates/output.md](templates/output.md) 输出。
