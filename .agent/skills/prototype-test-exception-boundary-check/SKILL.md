---
name: prototype-test-exception-boundary-check
description: Exception and boundary checking for prototype testing. Verify that prototypes explicitly represent empty/failure states, confirmation for dangerous actions such as deletion or unlinking, error messages, loading states, duplicate-submission prevention, boundary conditions, and blocking logic. Use to find gaps beyond the happy path, review safeguards for dangerous actions, and inspect apparently complete pages that lack protection.
---

# Exception and Boundary Checks

Prototype testing must cover more than the happy path; exception states and dangerous actions often determine later rework costs.

## Read First

- Local: [references/exception-boundary-checklist.md](references/exception-boundary-checklist.md)
- Shared: [../prototype-test-engineering/references/issue-taxonomy.md](../prototype-test-engineering/references/issue-taxonomy.md)

## Execution Steps

1. List the page's high-risk actions and data states.
2. Check these design elements:
   - Empty states
   - No-results states
   - Failure messages
   - Dangerous-action confirmations
   - Loading states or duplicate-submission prevention
   - Preconditions that block deletion, unlinking, or deactivation
3. Distinguish verified behavior from behavior that a static prototype cannot prove.
4. Mark gaps as `exception_gap`.

## Mandatory Rules

- A dangerous action without confirmation text or a confirmation action is not covered.
- “No data” text without an empty-state layout provides only weak coverage.
- If a backend-dependent failure message is not represented in the static prototype, mark it as `static_unprovable` or `exception_gap`.

## Deliverables

- Exception/boundary checklist
- Gaps in dangerous-action safeguards
- Statically unprovable items

Use [templates/output.md](templates/output.md) for the output.
