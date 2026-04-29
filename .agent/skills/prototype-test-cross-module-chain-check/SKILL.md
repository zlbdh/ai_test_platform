---
name: prototype-test-cross-module-chain-check
description: 原型测试中的跨模块链路检查技能。用于验证上下游模块之间的入口、跳转、回写、回显和状态承接已形成真实业务闭环，而不是只有若干孤立页面。适用于：检查企业到站点、审核到上架、订单到财务/投诉、商家到商品/站点等跨模块链路。
---

# 跨模块链路闭环检查

把“模块之间真的连起来了吗”单独验证，避免单页都正常但业务链中途断掉。

## 先读什么

- 本地 [references/cross-module-chain-patterns.md](references/cross-module-chain-patterns.md)
- 共享 [../prototype-test-engineering/references/issue-taxonomy.md](../prototype-test-engineering/references/issue-taxonomy.md)

## 执行步骤

1. 先列出待检链路的起点、终点、关键中间节点。
2. 逐节点确认入口、动作、结果和下游承接。
3. 重点查看以下承接关系：
   - 只写上下游关系、但无入口
   - 有入口、但无结果回写或回显
   - 状态改变后无下游承接
4. 对真实断裂点打 `chain_gap`。

## 强制规则

- 页面都存在，不等于链路闭环。
- 只有文档里写有依赖，原型中无入口或回显时，算链路缺口。
- 下游如果只是同名页面，但没有承接当前对象或状态，不算闭环。

## 交付物

- 跨模块链路矩阵
- 断链点说明
- 优先修复建议

使用 [templates/output.md](templates/output.md) 输出。
