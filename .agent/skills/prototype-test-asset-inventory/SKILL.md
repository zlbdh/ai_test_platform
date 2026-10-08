---
name: prototype-test-asset-inventory
description: Prototype testing asset inventory skill. Scan HTML, screenshots, Figma exports, and other prototype assets to identify entry pages, module pages, detail pages, dashboards, dialog destinations, and out-of-scope pages. Provide a reliable page inventory for mapping and module verification. Use before a full prototype test, to confirm synchronization status, explain coverage, or find embedded destinations.
---

# Prototype Asset Inventory

Establish which prototype assets actually exist before mapping or testing them.

## Read First

- Local: [references/asset-inventory-rules.md](references/asset-inventory-rules.md)
- Shared: [../prototype-test-engineering/references/evidence-spec.md](../prototype-test-engineering/references/evidence-spec.md)

## Execution Steps

1. Establish the prototype source directory, entry page, and exclusions.
2. Inventory:
   - Standalone HTML pages
   - Technical entry pages
   - Module list pages
   - Detail, review, and dashboard pages
   - Pages that may contain dialogs, tabs, or drawers
3. Mark each asset's verification level:
   - Directly accessible page
   - Accessible through an entry point
   - Embedded destination within a page
   - Static container only
4. Identify out-of-scope pages and missing-asset risks.
5. Pass the results to `prototype-test-page-mapping`; do not immediately mark them as covered.

## Mandatory Rules

- Do not assume a page implements a requirement merely because its filename looks relevant.
- Record technical entry pages separately from business pages.
- Record tabs, dialog buttons, and drawer entry points as candidate destinations; do not count them as coverage yet.
- Do not infer that an asset exists from requirements when it is absent from the directory.

## Deliverables

- Prototype asset inventory
- Relationships between entry pages and module pages
- Candidate embedded destinations
- List of out-of-scope pages
- Prototype synchronization risks

Use [templates/output.md](templates/output.md) for the output.
