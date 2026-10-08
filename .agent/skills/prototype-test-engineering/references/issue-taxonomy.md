# Issue Taxonomy

## Issue Categories

| code | Meaning | Typical scenario |
|---|---|---|
| `doc_gap` | Requirements are missing, incomplete, or untestable | Missing transitions, field constraints, or exception paths |
| `asset_gap` | Prototype assets are incomplete | Missing module page, entry point, or dialog destination |
| `missing_page` | Required page not found in the prototype | Requirements specify a detail page, but HTML has no page or embedded destination |
| `mis_mapping` | Requirement mapped to the wrong prototype page | Mapping a purchasing-management list to a property-management page |
| `broken_flow` | Pages exist but the workflow is incomplete | List opens details, but no submit/back/result state exists |
| `field_gap` | Missing field, validation, default, or display | Required field absent or key detail column missing |
| `state_gap` | Missing state definitions or transitions | State column exists without transition conditions or results |
| `permission_gap` | Missing permissions, visibility, or disabled states | Every button is visible without role differences |
| `exception_gap` | Missing empty/failure states, blocking, or confirmation | Deletion lacks confirmation or an empty list lacks an empty state |
| `visual_gap` | Missing visual structure or semantic representation | Misplaced dashboard layout, key areas, or information hierarchy |
| `chain_gap` | Incomplete cross-module workflow | Module A initiates an action without module B handling it |
| `scope_gap` | Scope or source of truth is incomplete | User omitted requirements or excluded key sources |

## Severity

| severity | Explanation | Handling |
|---|---|---|
| `blocking` | Critical gap blocking development or verification | Fail by default |
| `major` | Affects a main workflow, primary page, or key rule | High-priority remediation by default |
| `normal` | Issue does not block the main workflow | Add to the standard remediation list |
| `pending_confirmation` | Evidence is insufficient; human or live-system confirmation is needed | Explicitly list as pending, not passed |

## Three-State Conclusions

- `verified_pass`: clear evidence proves coverage.
- `verified_gap`: clear evidence proves a gap.
- `static_unprovable`: a static prototype cannot prove the behavior; never report it as passed.
