---
name: prototype-test-requirement-analysis
description: Requirement analysis for prototype testing. Read requirements and extract modules, pages, roles, workflows, rules, states, fields, constraints, and acceptance signals into a structured baseline for page mapping, module verification, and gates. Use when only requirements are available, as the first step of full testing, to review module completeness, or to explain untestable documents and inconsistencies with overviews.
---

# Requirement Analysis and Structured Extraction

Convert requirements into a fact matrix that downstream skills can use; a reading summary alone is insufficient.

## Read First

- Local: [references/requirement-signals.md](references/requirement-signals.md)
- Shared: [../prototype-test-engineering/references/issue-taxonomy.md](../prototype-test-engineering/references/issue-taxonomy.md)
- To explain existing platform capabilities, also read [../prototype-test-engineering/references/current-system-mapping.md](../prototype-test-engineering/references/current-system-mapping.md).

## Execution Steps

1. Establish the sole source of truth and list requirement files permitted for this task.
2. Extract from each document:
   - Modules
   - Pages
   - Roles
   - Main workflows
   - States and transitions
   - Fields and constraints
   - Exception paths
   - Cross-module dependencies
3. Build three baseline matrices:
   - Module-to-page matrix
   - Page-to-field/action matrix
   - Workflow-to-state matrix
4. Classify issues with categories such as `doc_gap`, `scope_gap`, `state_gap`, `field_gap`, and `permission_gap`.
5. Identify what later static-prototype verification must check, as input for downstream skills.

## Mandatory Rules

- Do not invent definitions that the requirements do not contain.
- Explicitly record conflicts between overview and module documents as `doc_gap` or `scope_gap`; do not silently choose one and ignore the other.
- A document that names pages without actions and states is not sufficiently testable.
- Requirements pass based on evidence-supported completeness, not because the text seems fine.

## Deliverables

- Structured summary of modules/pages/roles/workflows/rules/states/fields
- Document issue list
- Recommended downstream verification points
- Page inventory ready for `prototype-test-page-mapping`

Use [templates/output.md](templates/output.md) for the output.
