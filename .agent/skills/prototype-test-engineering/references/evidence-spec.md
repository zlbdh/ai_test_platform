# Evidence Spec

## 一条 finding 至少包含

- `evidence_id`
- `source_type`
- `source_path_or_url`
- `locator`
- `excerpt_or_snapshot`
- `why_it_matters`

## source_type 取值建议

- `requirement_doc`
- `html_file`
- `screenshot`
- `router_code`
- `playbook_data`
- `manual_observation`

## locator 规范

- 文档：章节名、页面名、字段名、标题
- HTML：文件名、元素文本、函数名、Tab 名、按钮名
- 截图：页面区域名或动作前后状态
- 代码：接口名、路由、配置项、函数名

## 证据采集约束

- 映射结论必须至少给 1 条需求证据 + 1 条原型证据。
- 缺页结论必须说明已检查哪些候选文件和承接点。
- 误映射结论必须说明“为什么当前页面不属于该需求页”。
- 静态无法证明的结论也要附证据，说明为何当前资料不足。
