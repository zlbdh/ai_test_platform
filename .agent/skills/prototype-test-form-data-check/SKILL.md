---
name: prototype-test-form-data-check
description: 原型测试中的表单与数据检查技能。用于验证字段、必填、默认值、校验提示、详情展示、列表列、统计卡片和关联数据展示对需求的承接情况。适用于：发现字段缺口、详情展示不足、表单规则不清、假展示或硬编码数据问题。
---

# 字段、校验与数据展示检查

确认“该看见的数据、该填写的字段、该提示的规则”已经被原型完整承接。

## 先读什么

- 本地 [references/form-data-checklist.md](references/form-data-checklist.md)
- 共享 [../prototype-test-engineering/references/issue-taxonomy.md](../prototype-test-engineering/references/issue-taxonomy.md)

## 执行步骤

1. 从需求解析结果中拿到页面字段清单。
2. 对照原型检查：
- 字段已存在
- 必填标识清晰可见
- 默认值表达完整
- 校验提示表达完整
- 列表列、详情区和统计卡片承接关键数据
3. 区分“字段未出现”“字段出现但规则缺失”“展示存在但数据含义不清”。
4. 对高风险缺口打 `field_gap`。

## 强制规则

- 只出现标签文字，不等于字段已可输入或可校验。
- 列表页有搜索项但无结果列承接时，不算完整展示。
- 详情页固定文案或固定数字，不能证明是动态承接。

## 交付物

- 字段覆盖矩阵
- 校验与默认值缺口
- 列表/详情/统计展示缺口

使用 [templates/output.md](templates/output.md) 输出。
