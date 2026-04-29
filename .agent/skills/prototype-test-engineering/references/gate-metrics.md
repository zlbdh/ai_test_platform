# Gate Metrics

## 推荐统一指标

| metric | 含义 | 默认目标 |
|---|---|---|
| `module_coverage_rate` | 已出结论模块数 / 目标模块数 | `1.0` |
| `page_mapping_rate` | 已建立可信映射页面数 / 需求页面数 | `>= 0.95` |
| `critical_page_missing_count` | 关键页面缺失数 | `<= 0` |
| `blocking_gap_count` | 阻断级问题数 | `<= 0` |
| `critical_field_gap_count` | 关键字段缺口数 | `<= 0` |
| `critical_state_gap_count` | 关键状态流转缺口数 | `<= 0` |
| `cross_module_chain_gap_count` | 跨模块链路缺口数 | 按项目设阈值 |
| `static_unprovable_count` | 静态原型无法证明项数 | 需要单列，不得吞掉 |

## verdict 建议

- `pass`：无 blocking，关键指标达标，待确认项可接受。
- `pass_with_risk`：无 blocking，但存在较多 `major` 或 `static_unprovable`。
- `fail`：存在 blocking，或关键指标未达标。

## 计数规则

- 同一问题不要在多个 skill 中重复记 blocking。
- `pending_confirmation` 不计入 blocking，但必须在总览显著列出。
- `mis_mapping` 一经确认，不能算 mapped。
