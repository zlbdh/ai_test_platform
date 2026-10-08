---
name: prototype-test-report-gate
description: Reporting and gate consolidation for prototype testing. Consolidate child-skill findings, evidence, coverage, and risks into a consistent issue list, module conclusions, coverage matrix, management summary, and gate verdict. Use to conclude full tests, module reviews, or capability explanations and turn scattered findings into actionable gate decisions.
---

# Report Consolidation and Quality Gates

Organize findings into a release decision, reasons, and next actions.

## Read First

- Local: [references/report-gate-rules.md](references/report-gate-rules.md)
- Shared: [../prototype-test-engineering/references/evidence-spec.md](../prototype-test-engineering/references/evidence-spec.md)
- Shared: [../prototype-test-engineering/references/gate-metrics.md](../prototype-test-engineering/references/gate-metrics.md)
- Shared: [../prototype-test-engineering/references/issue-taxonomy.md](../prototype-test-engineering/references/issue-taxonomy.md)

## Execution Steps

1. Collect all findings, remove duplicates, and standardize categories, severities, and evidence.
2. Calculate coverage, mapping rates, critical gaps, and statically unprovable items.
3. Produce:
   - Module conclusions
   - Overall conclusion
   - Gate verdict
4. Explicitly state the conclusion's boundaries; never hide `static_unprovable` items.

## Mandatory Rules

- Exclude findings without evidence from final counts.
- Do not count the same issue as blocking in multiple modules.
- Never report `pending_confirmation` as passed.
- Support the gate verdict with metrics, not merely subjective judgment.

## Deliverables

- Overview report
- Module findings
- Coverage matrix
- Gate verdict

Prefer shared templates:
- [../prototype-test-engineering/templates/summary-report.md](../prototype-test-engineering/templates/summary-report.md)
- [../prototype-test-engineering/templates/finding-card.md](../prototype-test-engineering/templates/finding-card.md)
- [../prototype-test-engineering/templates/coverage-matrix.md](../prototype-test-engineering/templates/coverage-matrix.md)
