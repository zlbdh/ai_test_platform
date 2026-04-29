# Skill Map

## 新套件总览

| Skill | 负责内容 | 上游输入 | 下游输出 |
|---|---|---|---|
| `prototype-test-engineering` | 总编排、范围锁定、子 skill 路由、收口要求 | 用户意图、范围、约束 | 执行计划、子 skill 调度、最终结论 |
| `prototype-test-requirement-analysis` | 需求解析与结构化抽取 | 需求文档 | 模块/页面/角色/流程/规则/状态/字段矩阵 |
| `prototype-test-asset-inventory` | 原型资产盘点 | HTML/Figma/截图等原型资产 | 入口页、页面清单、嵌入式承接点清单 |
| `prototype-test-page-mapping` | 需求页到原型页映射 | 需求矩阵 + 资产清单 | 映射矩阵、缺页、误映射、范围外页面 |
| `prototype-test-structure-check` | 菜单、路由、骨架结构 | 页面映射 | 结构类 finding |
| `prototype-test-interaction-flow` | 主操作链与动作闭环 | 页面映射 + 页面骨架 | 流程类 finding |
| `prototype-test-form-data-check` | 字段、校验、默认值、数据展示 | 需求规则 + 页面骨架 | 字段/展示类 finding |
| `prototype-test-state-permission-check` | 状态流转、角色/按钮显隐、禁用态 | 需求规则 + 主流程 | 状态/权限类 finding |
| `prototype-test-exception-boundary-check` | 空态、失败态、危险操作确认 | 页面骨架 + 主流程 | 异常/边界类 finding |
| `prototype-test-cross-module-chain-check` | 跨模块链路承接 | 模块结论 + 页面映射 | 跨模块链路 finding |
| `prototype-test-visual-semantic-check` | 视觉骨架、信息层级、关键区域 | 关键页面 | 视觉语义类 finding |
| `prototype-test-report-gate` | 证据、覆盖率、门禁结论 | 全部 finding | 总览、finding 卡片、门禁 verdict |
| `prototype-test-remediation-advice` | 整改建议与优先级 | 全部 finding + verdict | 产品/设计/开发/测试整改清单 |

## 旧 skills 映射

| Legacy Skill | 建议替代关系 | 说明 |
|---|---|---|
| `prototype-test-business-logic` | `prototype-test-interaction-flow` + `prototype-test-state-permission-check` + `prototype-test-cross-module-chain-check` | 旧 skill 偏业务观察，新组合更强调证据和可收口输出 |
| `prototype-test-ui-functional` | `prototype-test-structure-check` + `prototype-test-interaction-flow` + `prototype-test-exception-boundary-check` | 旧 skill 偏页面功能核查，新组合增加边界与误判约束 |
| `prototype-test-data-display` | `prototype-test-form-data-check` + `prototype-test-visual-semantic-check` | 旧 skill 偏 mock 数据丰富度，新组合兼顾展示语义与字段完整性 |
| `prototype-test-ux-experience` | `prototype-test-visual-semantic-check` + `prototype-test-interaction-flow` | 新套件把体验问题拆成可验证的结构和流程问题 |
| `prototype-test-code-quality` | 保留为补充性静态审查技能 | 不属于原型测试主链，不作为新套件主入口 |

## 调度原则

- 先做需求解析，再做映射，再做验证。
- 不直接从结构检查跳到门禁；没有映射矩阵时，门禁结论不可信。
- 模块问题只在对应 skill 内确认一次，避免多 skill 重复计数。
- `prototype-test-report-gate` 负责最终计数与 severities，对前序 skill 的 finding 做标准化，不重跑验证。
