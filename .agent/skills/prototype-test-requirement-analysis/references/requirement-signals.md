# Requirement Signals

## Required Signals

- Module name
- Page name
- Page type: list / form / detail / review / dashboard / dialog
- Roles
- Main workflows
- Key actions
- State set
- State-transition conditions
- Key fields
- Field constraints
- Exception paths
- Cross-module dependencies

## Typical Document Issues

- Says review exists without defining states and buttons after approval or rejection.
- Says editing is supported without identifying editable and read-only fields.
- Says export is supported without defining its scope and conditions.
- The overview defines a route with no corresponding page in the module document.

## Minimum Questions to Answer

- What should be tested?
- Which pages should be tested first?
- Which rules must be checked in the prototype?
- What will remain unproven even after prototype testing?
