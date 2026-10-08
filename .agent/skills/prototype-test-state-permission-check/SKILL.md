---
name: prototype-test-state-permission-check
description: State and permission checking for prototype testing. Verify that requirements and prototypes jointly define state sets, transition conditions, button visibility, role visibility, read-only and disabled states, and key review/publication/activation rules. Use to detect unclear transitions, superficial approval buttons, missing role distinctions, and incomplete review-page rules.
---

# State Transition and Permission Visibility Checks

Verify states and permissions as separate high-risk logic areas; a state column or button does not prove complete rules.

## Read First

- Local: [references/state-permission-rules.md](references/state-permission-rules.md)
- Shared: [../prototype-test-engineering/references/issue-taxonomy.md](../prototype-test-engineering/references/issue-taxonomy.md)

## Execution Steps

1. List the state set and transition conditions from requirement analysis.
2. Check each state:
- The current state is clearly represented
- Allowed actions are clear
- Prohibited actions are disabled, hidden, or read-only
3. Check each role:
   - Who can see the content
   - Who can perform actions
   - Who has view-only access
4. Mark state gaps as `state_gap` and permission gaps as `permission_gap`.

## Mandatory Rules

- State labels without transition conditions do not establish complete state logic.
- Buttons without role or state constraints do not establish permission coverage.
- Review pages must cover approval/rejection/return or equivalent outcomes; checking a single primary button is insufficient.

## Deliverables

- State matrix
- Role/button visibility matrix
- False-pass risk list

Use [templates/output.md](templates/output.md) for the output.
