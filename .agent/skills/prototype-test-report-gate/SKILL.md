---
name: prototype-test-report-gate
description: 原型测试中的报告与门禁收口技能。用于汇总各子 skill 的 finding、证据、覆盖率和风险，输出统一的问题清单、模块结论、覆盖矩阵、管理层摘要和门禁 verdict。适用于：完整测试收口、模块复核收口、工程化能力说明收口、将分散问题转成可决策的门禁结果。
---

# 报告汇总与门禁收口

把分散的发现统一整理成“放行结论、原因说明、下一步动作”的输出。

## 先读什么

- 本地 [references/report-gate-rules.md](references/report-gate-rules.md)
- 共享 [../prototype-test-engineering/references/evidence-spec.md](../prototype-test-engineering/references/evidence-spec.md)
- 共享 [../prototype-test-engineering/references/gate-metrics.md](../prototype-test-engineering/references/gate-metrics.md)
- 共享 [../prototype-test-engineering/references/issue-taxonomy.md](../prototype-test-engineering/references/issue-taxonomy.md)

## 执行步骤

1. 收集全部 finding，去重并标准化分类、严重级别、证据。
2. 计算覆盖率、映射率、关键缺口数、静态无法证明项数。
3. 输出：
   - 模块级结论
   - 总览结论
   - 门禁 verdict
4. 明确说明当前结论的边界，不隐去 `static_unprovable`。

## 强制规则

- 没有证据的 finding 不进最终计数。
- 同一问题不要在多个模块重复记 blocking。
- `pending_confirmation` 不得写成通过。
- 门禁 verdict 必须给出依据指标，不得只写主观判断。

## 交付物

- 总览报告
- 模块级 finding
- 覆盖矩阵
- 门禁 verdict

优先使用共享模板：
- [../prototype-test-engineering/templates/summary-report.md](../prototype-test-engineering/templates/summary-report.md)
- [../prototype-test-engineering/templates/finding-card.md](../prototype-test-engineering/templates/finding-card.md)
- [../prototype-test-engineering/templates/coverage-matrix.md](../prototype-test-engineering/templates/coverage-matrix.md)
