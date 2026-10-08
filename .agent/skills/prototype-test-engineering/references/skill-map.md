# Skill Map

## New Suite Overview

| Skill | Responsibility | Upstream input | Downstream output |
|---|---|---|---|
| `prototype-test-engineering` | Orchestration, scope, child-skill routing, consolidation requirements | User intent, scope, constraints | Execution plan, skill dispatch, final conclusion |
| `prototype-test-requirement-analysis` | Requirement analysis and structured extraction | Requirement documents | Module/page/role/workflow/rule/state/field matrix |
| `prototype-test-asset-inventory` | Prototype asset inventory | HTML/Figma/screenshots and other assets | Entry pages, page inventory, embedded destinations |
| `prototype-test-page-mapping` | Map required pages to prototype pages | Requirement matrix + asset inventory | Mapping matrix, missing pages, incorrect mappings, out-of-scope pages |
| `prototype-test-structure-check` | Menus, routes, structural skeleton | Page mappings | Structure findings |
| `prototype-test-interaction-flow` | Main action chains and complete outcomes | Page mappings + page skeletons | Workflow findings |
| `prototype-test-form-data-check` | Fields, validation, defaults, data display | Requirement rules + page skeletons | Field/display findings |
| `prototype-test-state-permission-check` | State transitions, role/button visibility, disabled states | Requirement rules + main workflows | State/permission findings |
| `prototype-test-exception-boundary-check` | Empty/failure states, dangerous-action confirmation | Page skeletons + main workflows | Exception/boundary findings |
| `prototype-test-cross-module-chain-check` | Cross-module integration | Module conclusions + page mappings | Cross-module workflow findings |
| `prototype-test-visual-semantic-check` | Visual structure, information hierarchy, key regions | Key pages | Visual-semantic findings |
| `prototype-test-report-gate` | Evidence, coverage, gate conclusions | All findings | Overview, finding cards, gate verdict |
| `prototype-test-remediation-advice` | Remediation recommendations and priorities | All findings + verdict | Product/design/development/testing remediation lists |

## Legacy Skill Mapping

| Legacy Skill | Suggested replacement | Description |
|---|---|---|
| `prototype-test-business-logic` | `prototype-test-interaction-flow` + `prototype-test-state-permission-check` + `prototype-test-cross-module-chain-check` | Legacy skill emphasizes business observations; the new combination emphasizes evidence and conclusive deliverables |
| `prototype-test-ui-functional` | `prototype-test-structure-check` + `prototype-test-interaction-flow` + `prototype-test-exception-boundary-check` | Legacy skill checks page features; the new combination adds boundary checks and safeguards against misjudgment |
| `prototype-test-data-display` | `prototype-test-form-data-check` + `prototype-test-visual-semantic-check` | Legacy skill emphasizes mock-data richness; the new combination also checks display semantics and field completeness |
| `prototype-test-ux-experience` | `prototype-test-visual-semantic-check` + `prototype-test-interaction-flow` | The new suite separates experience issues into verifiable structure and workflow issues |
| `prototype-test-code-quality` | Retain as a supplementary static-review skill | Outside the main prototype testing chain; not the new suite's entry point |

## Dispatch Principles

- Analyze requirements first, then map, then verify.
- Do not jump from structure checks to gates; gate conclusions are unreliable without a mapping matrix.
- Confirm each module issue once in its responsible skill to avoid duplicate counts.
- `prototype-test-report-gate` owns final counts and severities. It standardizes earlier findings without repeating verification.
