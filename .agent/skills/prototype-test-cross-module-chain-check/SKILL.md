---
name: prototype-test-cross-module-chain-check
description: Cross-module workflow checking for prototype testing. Verify that entry points, navigation, writebacks, displayed results, and state transitions form a complete business workflow across upstream and downstream modules rather than isolated pages. Use for company-to-site, review-to-publication, order-to-finance/complaint, and merchant-to-product/site workflows.
---

# Cross-Module Workflow Completion Check

Verify whether modules actually connect, preventing workflows from breaking even when each page works independently.

## Read First

- Local: [references/cross-module-chain-patterns.md](references/cross-module-chain-patterns.md)
- Shared: [../prototype-test-engineering/references/issue-taxonomy.md](../prototype-test-engineering/references/issue-taxonomy.md)

## Execution Steps

1. List the starting point, endpoint, and key intermediate nodes of the workflow.
2. Verify each node's entry point, action, result, and downstream integration.
3. Focus on these integration patterns:
   - Documented upstream/downstream relationships without entry points
   - Entry points without result writebacks or displayed results
   - State changes without downstream handling
4. Mark confirmed breaks as `chain_gap`.

## Mandatory Rules

- The existence of every page does not prove a complete workflow.
- A dependency described only in documentation, with no prototype entry point or displayed result, is a workflow gap.
- A downstream page with the same name does not complete the workflow unless it handles the current object or state.

## Deliverables

- Cross-module workflow matrix
- Description of workflow breaks
- Prioritized remediation recommendations

Use [templates/output.md](templates/output.md) for the output.
