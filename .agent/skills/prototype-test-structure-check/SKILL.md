---
name: prototype-test-structure-check
description: Structural checking for prototype testing. Verify that menus, routes, page skeletons, search/list/detail/dashboard/dialog/pagination regions match required page types. Use to assess structural completeness, review missing regions on key pages, and explain why an existing page does not necessarily implement the required page.
---

# Page Structure Checks

Verify that the page has the correct structure, not merely that it exists.

## Read First

- Local: [references/structure-checklist.md](references/structure-checklist.md)
- Shared: [../prototype-test-engineering/references/issue-taxonomy.md](../prototype-test-engineering/references/issue-taxonomy.md)

## Execution Steps

1. Identify the target page and its type from page mappings.
2. Check that menus, breadcrumbs, route names, and headings match requirements.
3. Verify that the page skeleton includes the regions expected for its type.
4. Record missing, misplaced, and placeholder-only regions.
5. Pass results to workflow, field, and exception skills; do not declare their checks passed on their behalf.

## Mandatory Rules

- An empty container does not prove that a region is implemented.
- Suspect an incorrect mapping when the page title and main content disagree.
- Structure checks establish only region coverage; they do not replace workflow or state conclusions.

## Deliverables

- Structural coverage matrix
- Key-region gaps
- Explanation of page-type mismatches

Use [templates/output.md](templates/output.md) for the output.
