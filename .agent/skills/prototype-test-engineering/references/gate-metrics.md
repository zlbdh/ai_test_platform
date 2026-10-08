# Gate Metrics

## Recommended Shared Metrics

| metric | Meaning | Default target |
|---|---|---|
| `module_coverage_rate` | Modules with conclusions / target modules | `1.0` |
| `page_mapping_rate` | Reliably mapped pages / required pages | `>= 0.95` |
| `critical_page_missing_count` | Missing critical pages | `<= 0` |
| `blocking_gap_count` | Blocking issues | `<= 0` |
| `critical_field_gap_count` | Critical field gaps | `<= 0` |
| `critical_state_gap_count` | Critical state-transition gaps | `<= 0` |
| `cross_module_chain_gap_count` | Cross-module workflow gaps | Set a project-specific threshold |
| `static_unprovable_count` | Items a static prototype cannot prove | Report separately; never omit |

## Suggested verdict Values

- `pass`: no blocking issues, key metrics meet targets, and pending confirmations are acceptable.
- `pass_with_risk`: no blocking issues, but many `major` or `static_unprovable` items remain.
- `fail`: blocking issues exist or key metrics miss targets.

## Counting Rules

- Do not count the same issue as blocking in multiple skills.
- `pending_confirmation` does not count as blocking, but must be prominent in the overview.
- A confirmed `mis_mapping` cannot count as mapped.
