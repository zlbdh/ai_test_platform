---
name: prototype-test-visual-semantic-check
description: Visual-semantic checking for prototype testing. Verify that page structure, information hierarchy, key regions, dashboard layouts, tag semantics, important-action visibility, and overall presentation match the business page type, beyond pixel comparison. Use to assess dashboards, complex lists, detail pages, and key forms, or explain layouts that exist but communicate the wrong meaning.
---

# Visual-Semantic Checks

Focus on whether the page communicates the correct business meaning, not only colors and pixel differences.

## Read First

- Local: [references/visual-semantic-checklist.md](references/visual-semantic-checklist.md)
- Shared: [../prototype-test-engineering/references/current-system-mapping.md](../prototype-test-engineering/references/current-system-mapping.md)

## Execution Steps

1. Identify key pages or regions.
2. Check:
   - Information hierarchy
   - Key-region visibility
   - Tag/state semantics
   - Dashboard layout and chart containers
- Key actions are positioned appropriately
3. Incorporate visual baseline evidence if available; otherwise report a semantic-level check.
4. Classify results as `visual_gap` or `static_unprovable`.

## Mandatory Rules

- Without pixel-level comparison, explicitly call the work a semantic visual check; do not present it as visual regression testing.
- A page that opens but has squeezed, misplaced, or semantically unclear key regions still has a `visual_gap`.
- Placeholder chart containers do not establish complete visualization semantics.

## Deliverables

- Visual-semantic issue list
- Explanation of key-region visibility
- Dashboard and complex-page layout conclusions

Use [templates/output.md](templates/output.md) for the output.
