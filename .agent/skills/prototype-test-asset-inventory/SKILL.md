---
name: prototype-test-asset-inventory
description: 原型测试中的资产盘点技能。用于扫描 HTML、截图、Figma 导出页等原型资产，识别入口页、模块页、详情页、看板页、弹窗承接点与范围外页面，为页面映射和后续模块验证提供可信的页面资产清单。适用于：完整原型测试前的资产盘点、确认原型同步状态、解释原型覆盖面、寻找嵌入式承接点。
---

# 原型资产盘点

先搞清楚“现在到底有什么原型资产”，再谈映射和测试。

## 先读什么

- 本地 [references/asset-inventory-rules.md](references/asset-inventory-rules.md)
- 共享 [../prototype-test-engineering/references/evidence-spec.md](../prototype-test-engineering/references/evidence-spec.md)

## 执行步骤

1. 锁定原型来源目录、入口页和排除项。
2. 盘点：
   - 独立 HTML 页面
   - 技术入口页
   - 模块列表页
   - 详情/审核/看板页
   - 可能承接弹窗/Tab/抽屉的页面
3. 标出每个资产的可验证级别：
   - 直接访问页
   - 需从入口进入
   - 页面内嵌承接
   - 仅有静态容器
4. 找出范围外页面和缺失资产风险。
5. 把结果交给 `prototype-test-page-mapping`，不要直接跳到“已覆盖”。

## 强制规则

- 不因文件名看起来像某页面就认定它可承接。
- 技术入口页和业务页面分开记录。
- 发现页面内有 Tab、弹窗按钮、抽屉入口时，记录为“可能承接点”，不要直接算覆盖。
- 目录里没有的资产，不要靠需求反推成“应该存在”。

## 交付物

- 原型资产清单
- 入口页与模块页关系
- 嵌入式承接候选点
- 范围外页面清单
- 原型同步风险提示

使用 [templates/output.md](templates/output.md) 输出。
