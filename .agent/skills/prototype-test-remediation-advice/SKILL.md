---
name: prototype-test-remediation-advice
description: Remediation recommendations for prototype testing. Turn requirement and mapping gaps, structural issues, broken workflows, state/permission gaps, exception/boundary issues, and visual-semantic issues into prioritized actions for product, design, frontend, backend, testing, and platform teams. Use after testing, when management needs next steps, or to convert findings into executable work items.
---

# Remediation Recommendations and Priorities

Turn the issue list into execution guidance: who acts first, what changes, why, and how to retest.

## Read First

- Local: [references/remediation-prioritization.md](references/remediation-prioritization.md)
- Shared: [../prototype-test-engineering/references/issue-taxonomy.md](../prototype-test-engineering/references/issue-taxonomy.md)

## Execution Steps

1. Read confirmed findings and the verdict.
2. Group by role:
   - Product
   - Design
   - Frontend
   - Backend
   - Testing
   - Platform
3. For each group, explain:
   - What to change
   - Why it takes priority
   - How to retest the change
4. Assign `P0 / P1 / P2` priorities.

## Mandatory Rules

- Every recommendation must address a specific finding; generic slogans are insufficient.
- Distinguish requirements updates from prototype changes and identify their respective responsibilities.
- For `static_unprovable` items, recommend a path to obtain evidence rather than pretending they can be directly fixed.

## Deliverables

- Role-specific remediation lists
- Priorities
- Retest recommendations

Use [templates/output.md](templates/output.md) for the output.
