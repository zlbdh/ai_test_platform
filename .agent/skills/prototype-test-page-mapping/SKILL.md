---
name: prototype-test-page-mapping
description: 原型测试中的页面映射技能。用于把需求文档里的页面、弹窗和关键动作映射到 HTML 原型页面或嵌入式承接点，识别独立映射、嵌入式承接、缺页、误映射和范围外页面。适用于：完整原型测试中的页面对齐、复核某条映射的可靠性、排查假覆盖和误映射。
---

# 页面映射与承接判定

把“需求页在原型里的承接情况”做成有证据的判断，不凭感觉。

## 先读什么

- 本地 [references/mapping-rules.md](references/mapping-rules.md)
- 共享 [../prototype-test-engineering/references/evidence-spec.md](../prototype-test-engineering/references/evidence-spec.md)
- 共享 [../prototype-test-engineering/references/issue-taxonomy.md](../prototype-test-engineering/references/issue-taxonomy.md)

## 固定映射状态

- `standalone_mapped`：存在独立原型页并有直接证据。
- `embedded_covered`：无独立页，但在现有页面动作、Tab、弹窗、抽屉中有明确承接。
- `missing_page`：需求页存在，原型中未找到独立页也未找到嵌入式承接。
- `mis_mapping`：当前映射对象明显不是该需求页。
- `out_of_scope_prototype`：原型里存在，但需求范围没定义。

## 执行步骤

1. 读取需求页清单和原型资产清单。
2. 对每个需求页依次查找：
   - 同名/近义独立页
   - 详情页或列表页中的动作入口
   - Tab / 弹窗 / 抽屉 / 二级区块承接
3. 为每条映射补两侧证据：
   - 需求侧证据：页面名、动作、字段、章节
   - 原型侧证据：HTML 文件、按钮文本、Tab 名、标题、元素区块
4. 无法匹配时优先给 `missing_page` 或 `pending_confirmation`，不要勉强找“最像的页面”。
5. 把 `mis_mapping`、`missing_page`、`embedded_covered` 明确输出给下游 skill。

## 强制规则

- 文件名相似但内容不符时，判 `mis_mapping`。
- 没有动作入口、只有疑似容器时，不得判 `embedded_covered`。
- 范围外原型页单列展示，不计入需求覆盖率。
- 静态 HTML 里无法证明动作会打开某弹窗时，只能写“嵌入式待确认”或 `static_unprovable`。

## 交付物

- 需求页到原型页映射矩阵
- 缺页清单
- 误映射清单
- 嵌入式承接清单
- 范围外原型页清单

使用 [templates/output.md](templates/output.md) 输出。
