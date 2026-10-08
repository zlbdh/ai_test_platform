---
name: prototype-test-page-mapping
description: Page mapping for prototype testing. Map required pages, dialogs, and key actions to HTML prototype pages or embedded destinations. Identify standalone mappings, embedded coverage, missing pages, incorrect mappings, and out-of-scope pages. Use to align pages during full testing, review mapping reliability, and detect false coverage or incorrect mappings.
---

# Page Mapping and Coverage Assessment

Use evidence to determine how each required page is implemented in the prototype; do not rely on intuition.

## Read First

- Local: [references/mapping-rules.md](references/mapping-rules.md)
- Shared: [../prototype-test-engineering/references/evidence-spec.md](../prototype-test-engineering/references/evidence-spec.md)
- Shared: [../prototype-test-engineering/references/issue-taxonomy.md](../prototype-test-engineering/references/issue-taxonomy.md)

## Fixed Mapping States

- `standalone_mapped`: a standalone prototype page exists with direct evidence.
- `embedded_covered`: no standalone page exists, but an existing action, tab, dialog, or drawer clearly implements the requirement.
- `missing_page`: a required page has neither a standalone page nor an embedded destination in the prototype.
- `mis_mapping`: the current mapped target clearly is not the required page.
- `out_of_scope_prototype`: a prototype page exists but is not defined in the requirement scope.

## Execution Steps

1. Read the required-page inventory and prototype asset inventory.
2. For each required page, look in order for:
   - Standalone pages with matching or equivalent names
   - Action entry points on detail or list pages
   - Tabs, dialogs, drawers, or secondary regions that implement it
3. Add evidence from both sides for every mapping:
   - Requirements: page name, action, field, section
   - Prototype: HTML file, button text, tab name, heading, element region
4. If no match can be established, prefer `missing_page` or `pending_confirmation`; do not force a match to the most similar page.
5. Explicitly pass `mis_mapping`, `missing_page`, and `embedded_covered` results to downstream skills.

## Mandatory Rules

- If filenames are similar but contents differ, use `mis_mapping`.
- A suspected container without an action entry point cannot be `embedded_covered`.
- Report out-of-scope prototype pages separately and exclude them from requirement coverage.
- If static HTML cannot prove that an action opens a particular dialog, report an unconfirmed embedded destination or `static_unprovable`.

## Deliverables

- Requirement-to-prototype page mapping matrix
- Missing-page list
- Incorrect-mapping list
- Embedded-destination list
- Out-of-scope prototype page list

Use [templates/output.md](templates/output.md) for the output.
