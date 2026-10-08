---
name: prototype-test-engineering
description: Overall orchestration for systematic prototype testing. Design, explain, execute, or review prototype testing workflows using existing platform capabilities, including scope definition, requirement analysis, asset inventory, page mapping, module verification, cross-module workflows, visual semantics, quality gates, and remediation. Use to explain platform capabilities, plan a project's tests, organize a complete test, review a module/workflow/mapping, or establish reusable SOPs and engineering practices.
---

# Prototype Testing Orchestration

Organize prototype testing as a reusable engineering capability, not a one-time project report. Always define scope first, dispatch work to child skills, and consolidate results using shared taxonomy, evidence requirements, and gate metrics.

## Shared Resources to Read First

Read by default:
- [references/workflow-sop.md](references/workflow-sop.md)
- [references/skill-map.md](references/skill-map.md)

Read additional resources as needed:
- To explain system capabilities: [references/current-system-mapping.md](references/current-system-mapping.md)
- To classify issues or define severity: [references/issue-taxonomy.md](references/issue-taxonomy.md)
- To present evidence: [references/evidence-spec.md](references/evidence-spec.md)
- To produce gate conclusions: [references/gate-metrics.md](references/gate-metrics.md)

## Fixed Orchestration Order

1. Establish requirement sources, prototype sources, scope, exclusions, verification depth, permission to count embedded destinations, and boundaries for accessing real systems.
2. Identify the task type:
   - Explain the platform's existing prototype testing capabilities
   - Create a complete prototype testing plan
   - Execute complete prototype testing
   - Review a specific module, workflow, or mapping
3. Call `prototype-test-requirement-analysis` first to extract modules, pages, workflows, states, fields, and constraints.
4. If prototype assets exist, call `prototype-test-asset-inventory` and `prototype-test-page-mapping` to establish a verifiable page matrix.
5. Dispatch module verification as needed:
   - Structure -> `prototype-test-structure-check`
   - Main workflows -> `prototype-test-interaction-flow`
   - Fields/display -> `prototype-test-form-data-check`
   - States/permissions -> `prototype-test-state-permission-check`
   - Exceptions/boundaries -> `prototype-test-exception-boundary-check`
   - Cross-module issues -> `prototype-test-cross-module-chain-check`
   - Visual semantics -> `prototype-test-visual-semantic-check`
6. Consolidate all findings, then call `prototype-test-report-gate` to report coverage, evidence, and the gate verdict.
7. If the user needs a remediation plan, call `prototype-test-remediation-advice` to provide role-specific recommendations.

## Routing Rules

- When the user asks to explain prototype testing capabilities:
  - Prioritize capability layers, tool mappings, solved problems, and remaining problems.
  - Do not enter project-level page mapping or module testing.
- When the user asks for complete prototype testing of a project:
  - Run the complete chain: requirement analysis -> asset inventory -> page mapping -> module checks -> cross-module workflows -> consolidation.
- When the user asks only to review a module, workflow, or mapping:
  - Call only the necessary child skills; do not regenerate a complete plan.
- When the user has requirements but no prototype:
  - Perform only requirement analysis, issue classification, consolidation, and remediation recommendations.
- When the user has an HTML prototype but no requirements:
  - Start with asset inventory and structure/workflow checks, but mark missing requirements as `scope_gap`; do not invent requirement conclusions.

## Mandatory Constraints

- Always distinguish three kinds of conclusions:
  - Verified pass
  - Confirmed issue
  - Cannot be proven by a static prototype
- Never report missing evidence as a pass.
- Never report similar filenames as a confirmed mapping.
- If the user explicitly limits the source of truth, use only that source; do not supplement it with other directories to explain gaps.
- Outputs must directly support SOPs, gates, and remediation; loose observation notes alone are insufficient.

## Choose Deliverables

- Capability explanation: [templates/summary-report.md](templates/summary-report.md)
- Test execution plan: [templates/coverage-matrix.md](templates/coverage-matrix.md) and [references/workflow-sop.md](references/workflow-sop.md)
- Module execution results: [templates/module-report.md](templates/module-report.md)
- Individual finding: [templates/finding-card.md](templates/finding-card.md)

## Relationship to Legacy Skills

The repository contains experimental skills including `prototype-test-business-logic`, `prototype-test-ui-functional`, `prototype-test-data-display`, `prototype-test-ux-experience`, and `prototype-test-code-quality`. Retain them, but no longer use them as the primary entry point. Start with this skill and route to the new suite using [references/skill-map.md](references/skill-map.md).
