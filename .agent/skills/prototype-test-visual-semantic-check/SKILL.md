---
name: prototype-test-visual-semantic-check
description: 原型测试中的视觉语义检查技能。用于验证页面视觉骨架、信息层级、关键区域、看板布局、标签语义、重点操作可见性和整体视觉承接符合业务页面类型，而不是只做像素对比。适用于：检查看板、复杂列表、详情页和关键表单的视觉语义质量，解释布局存在但表达错误的问题。
---

# 视觉语义检查

关注“页面传达的业务含义对不对”，不是只看颜色和像素差异。

## 先读什么

- 本地 [references/visual-semantic-checklist.md](references/visual-semantic-checklist.md)
- 共享 [../prototype-test-engineering/references/current-system-mapping.md](../prototype-test-engineering/references/current-system-mapping.md)

## 执行步骤

1. 锁定关键页面或关键区域。
2. 检查：
   - 信息层级
   - 关键区域可见性
   - 标签/状态语义
   - 看板布局与图表容器
- 关键操作位于合理位置
3. 如已接视觉基线，结合基线证据；否则按语义级检查输出。
4. 把结果打成 `visual_gap` 或 `static_unprovable`。

## 强制规则

- 没做像素级比较时，明确写“语义级视觉检查”，不要伪装成视觉回归。
- 页面可以打开，但关键区域被挤压、错位或语义不清时，仍算 `visual_gap`。
- 图表只有占位容器时，不等于可视化语义已完整承接。

## 交付物

- 视觉语义问题清单
- 关键区域可见性说明
- 看板与复杂页布局结论

使用 [templates/output.md](templates/output.md) 输出。
