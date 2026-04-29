---
name: prototype-test-structure-check
description: 原型测试中的结构检查技能。用于核查菜单、路由、页面骨架、搜索区、列表区、详情区、看板区、弹窗区、分页区等结构承接与需求页面类型的匹配度。适用于：判断页面骨架完整度、复核关键页面缺失区块情况、解释为什么某页面虽然存在但不等于需求页。
---

# 页面结构检查

验证“页面长得对不对”，不是只验证“页面在不在”。

## 先读什么

- 本地 [references/structure-checklist.md](references/structure-checklist.md)
- 共享 [../prototype-test-engineering/references/issue-taxonomy.md](../prototype-test-engineering/references/issue-taxonomy.md)

## 执行步骤

1. 根据页面映射锁定目标页和页面类型。
2. 检查菜单、面包屑、路由命名和标题与需求的一致性。
3. 检查页面骨架具备该类型应有的区块。
4. 记录缺失区块、错位区块、假容器区块。
5. 把结果交给后续流程、字段、异常 skill，不替它们代判通过。

## 强制规则

- 有个空容器不等于该区块已实现。
- 页面标题与页面主体内容不一致时，优先怀疑误映射。
- 结构检查只确认“区块承接”，不替代流程和状态结论。

## 交付物

- 结构承接矩阵
- 关键区块缺口
- 页面类型错配说明

使用 [templates/output.md](templates/output.md) 输出。
