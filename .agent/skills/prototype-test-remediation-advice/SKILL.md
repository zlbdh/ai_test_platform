---
name: prototype-test-remediation-advice
description: 原型测试中的整改建议技能。用于把需求缺口、映射缺口、结构问题、流程断裂、状态/权限缺口、异常边界问题和视觉语义问题转成面向产品、设计、前端、后端、测试和平台的分角色整改建议与优先级。适用于：测试收口后的整改规划、管理层要看“下一步怎么办”、把问题清单转成可执行工作项。
---

# 整改建议与优先级

把问题清单翻译成“谁先改、改什么、为什么、改完怎么复测”的执行输入。

## 先读什么

- 本地 [references/remediation-prioritization.md](references/remediation-prioritization.md)
- 共享 [../prototype-test-engineering/references/issue-taxonomy.md](../prototype-test-engineering/references/issue-taxonomy.md)

## 执行步骤

1. 读取已确认 finding 和 verdict。
2. 按角色分组：
   - 产品
   - 设计
   - 前端
   - 后端
   - 测试
   - 平台
3. 为每组建议写清：
   - 要改什么
   - 为什么先改
   - 改完如何复测
4. 按 `P0 / P1 / P2` 排优先级。

## 强制规则

- 建议必须对应具体 finding，不能写成空泛口号。
- 不能把“补充需求”和“修改原型”混写；要区分责任面。
- 对 `static_unprovable` 项，要建议补证路径，而不是假装能直接修。

## 交付物

- 分角色整改清单
- 优先级
- 复测建议

使用 [templates/output.md](templates/output.md) 输出。
