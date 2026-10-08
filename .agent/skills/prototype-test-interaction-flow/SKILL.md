---
name: prototype-test-interaction-flow
description: Interaction workflow checking for prototype testing. Verify that navigation entry points, main action chains, page transitions, dialog opening, submission confirmation, return paths, and result states form complete workflows. Use to identify pages with broken actions, review main workflow completion, and explain features that appear present but cannot be used end to end.
---

# Main Action Chain and Interaction Completion Checks

Follow the user's action chain; do not mistake the existence of pages for a complete workflow.

## Read First

- Local: [references/flow-checklist.md](references/flow-checklist.md)
- Shared: [../prototype-test-engineering/references/evidence-spec.md](../prototype-test-engineering/references/evidence-spec.md)

## Execution Steps

1. Choose a specific entry page.
2. List the action nodes the user must traverse to complete the task.
3. Verify entry, navigation, dialog opening, confirmation, return, and result states step by step.
4. Record interruptions explicitly as `broken_flow` or `static_unprovable`.
5. Explain both the completion path and the break points.

## Mandatory Rules

- Seeing a button does not prove that its action works.
- A dialog button without verified dialog contents does not prove a complete workflow.
- A detail page that opens but lacks a return path, save action, or result state still has a workflow gap.

## Deliverables

- Key workflow paths
- Break points and causes
- Main workflow completion conclusion

Use [templates/output.md](templates/output.md) for the output.
