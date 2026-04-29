---
name: prototype-test-engineering
description: 工程化原型测试总编排技能。用于基于现有平台能力设计、解释、执行或复盘原型测试工作流，包括范围锁定、需求解析、原型资产盘点、页面映射、模块验证、跨模块链路、视觉语义检查、门禁收口与整改建议。适用于：解释现有原型测试能力、为项目制定测试计划、组织一次完整原型测试、复核某模块/某链路/某映射、沉淀 SOP 与工程化方案。
---

# 原型测试工程化总编排

统一把“原型测试”组织成一套可复用的工程能力，而不是一次性的项目报告。始终先锁定范围，再分发给子 skill 执行，最后按统一 taxonomy、证据规范和门禁指标收口。

## 先读取哪些共享资料

默认先读：
- [references/workflow-sop.md](references/workflow-sop.md)
- [references/skill-map.md](references/skill-map.md)

按任务补读：
- 解释现有系统能力时读 [references/current-system-mapping.md](references/current-system-mapping.md)
- 归类问题或定义严重级别时读 [references/issue-taxonomy.md](references/issue-taxonomy.md)
- 输出证据时读 [references/evidence-spec.md](references/evidence-spec.md)
- 输出门禁结论时读 [references/gate-metrics.md](references/gate-metrics.md)

## 固定编排顺序

1. 锁定需求来源、原型来源、范围、排除项、验证深度、嵌入式承接许可和真实系统接入边界。
2. 判断当前任务属于哪一类：
   - 解释现有平台的原型测试能力
   - 制定完整原型测试计划
   - 执行完整原型测试
   - 复核某模块、某链路或某映射
3. 先调 `prototype-test-requirement-analysis`，抽取模块、页面、流程、状态、字段和约束。
4. 如存在原型资产，再调 `prototype-test-asset-inventory` 与 `prototype-test-page-mapping`，建立可验证的页面矩阵。
5. 按需分发模块验证：
   - 结构问题 -> `prototype-test-structure-check`
   - 主流程问题 -> `prototype-test-interaction-flow`
   - 字段/展示问题 -> `prototype-test-form-data-check`
   - 状态/权限问题 -> `prototype-test-state-permission-check`
   - 异常/边界问题 -> `prototype-test-exception-boundary-check`
   - 跨模块问题 -> `prototype-test-cross-module-chain-check`
   - 视觉语义问题 -> `prototype-test-visual-semantic-check`
6. 汇总全部 finding 后调 `prototype-test-report-gate` 输出覆盖率、证据、门禁结论。
7. 如用户需要整改方案，再调 `prototype-test-remediation-advice` 输出按角色分发的建议。

## 路由规则

- 用户要“解释原型测试工程化能力”时：
  - 优先输出系统能力分层、工具映射、已解决问题、未解决问题。
  - 不进入项目级页面映射和模块测试。
- 用户要“对项目做完整原型测试”时：
  - 必须跑完整链：需求解析 -> 资产盘点 -> 页面映射 -> 模块检查 -> 跨模块链路 -> 收口。
- 用户只要“复核某模块/某链路/某映射”时：
  - 仅调用必要子 skill，不重复生成全量计划。
- 用户只有需求文档、没有原型时：
  - 只执行需求分析、问题归类、收口与整改建议。
- 用户只有 HTML 原型、没有需求时：
  - 先做资产盘点与结构/流程检查，但把“需求未提供”标成 `scope_gap`，不要伪造需求结论。

## 强制约束

- 始终区分三类结论：
  - 已验证通过
  - 已确认问题
  - 静态原型无法证明
- 不把“未找到证据”直接写成“通过”。
- 不把“文件名相似”直接写成“已映射”。
- 用户明确限制事实源时，只使用该事实源，不用补充目录“帮忙解释”。
- 输出必须可直接支撑 SOP、门禁和整改，不允许只给松散的观察笔记。

## 输出物选择

- 工程化能力说明：使用 [templates/summary-report.md](templates/summary-report.md)
- 测试执行计划：使用 [templates/coverage-matrix.md](templates/coverage-matrix.md) 和 [references/workflow-sop.md](references/workflow-sop.md)
- 模块级执行结果：使用 [templates/module-report.md](templates/module-report.md)
- 单条 finding：使用 [templates/finding-card.md](templates/finding-card.md)

## 与旧 skills 的关系

仓库里已有 `prototype-test-business-logic`、`prototype-test-ui-functional`、`prototype-test-data-display`、`prototype-test-ux-experience`、`prototype-test-code-quality` 等实验性 skills。保留它们，但不再把它们作为主入口；统一从本 skill 开始，再按 [references/skill-map.md](references/skill-map.md) 路由到新套件。
