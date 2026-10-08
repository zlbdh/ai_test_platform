# Workflow SOP

## 0. Entry Conditions

- Determine whether the user wants a capability explanation, test plan, full test, or targeted review.
- Establish requirement sources, prototype sources, and source-of-truth boundaries.
- Establish whether embedded destinations may count as coverage.
- Establish whether a real system is connected; otherwise default to static prototype mode.

## 1. Define Scope

- List modules, exclusions, key workflows, and key pages.
- If the user specifies a sole source of truth, use only that source.
- Mark incomplete scope as `scope_gap`; do not fill it in without authorization.

## 2. Analyze Requirements

- Extract modules, pages, roles, workflows, rules, states, fields, and constraints.
- Produce a structured matrix as the sole upstream input for mapping and verification.

## 3. Inventory Prototype Assets

- Identify entry pages, module pages, detail pages, dialog destinations, and dashboards.
- Distinguish directly accessible pages from embedded destinations.

## 4. Map Pages

- Assign each required page one of these states:
  - `standalone_mapped`
  - `embedded_covered`
  - `missing_page`
  - `mis_mapping`
  - `out_of_scope_prototype`
- Attach evidence to every mapping; filenames alone are insufficient.

## 5. Verify Modules

- Cover at least:
  - Navigation entry points
  - Main lists or main forms
  - Details/reviews/dashboards
- Verify structure, workflows, fields, states/permissions, and exception boundaries separately.

## 6. Cross-Module Workflows

- Verify actual upstream/downstream integration; do not mistake the existence of pages for a complete workflow.
- Explain evidence for entry points, actions, results, and writebacks or displayed results.

## 7. Visual Semantics

- Focus on key information hierarchy, dashboard layout, and primary list/form/detail structures.
- If there is no pixel-level comparison, explicitly label the work as a semantic visual check.

## 8. Consolidation and Gates

- Standardize issue taxonomy, severity, and evidence.
- Report coverage, mapping rates, critical gaps, and statically unprovable items consistently.
- Give a verdict: `pass`, `pass_with_risk`, or `fail`.

## 9. Remediation Recommendations

- Provide separate recommendations for product, design, frontend, backend, and testing teams.
- Every recommendation must correspond to one or more findings.
