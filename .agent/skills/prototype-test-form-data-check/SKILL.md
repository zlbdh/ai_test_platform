---
name: prototype-test-form-data-check
description: Form and data checking for prototype testing. Verify that fields, required markers, defaults, validation messages, detail displays, list columns, statistics cards, and related records implement requirements. Use to identify missing fields, insufficient details, unclear form rules, superficial displays, and hardcoded data.
---

# Field, Validation, and Data Display Checks

Confirm that the prototype fully represents the data users need to see, fields they need to complete, and rules they need to understand.

## Read First

- Local: [references/form-data-checklist.md](references/form-data-checklist.md)
- Shared: [../prototype-test-engineering/references/issue-taxonomy.md](../prototype-test-engineering/references/issue-taxonomy.md)

## Execution Steps

1. Obtain the page field inventory from requirement analysis.
2. Check the prototype against it:
- Fields exist
- Required-field markers are clearly visible
- Default values are fully represented
- Validation messages are fully represented
- List columns, detail regions, and statistics cards include key data
3. Distinguish absent fields, present fields with missing rules, and displays with unclear data meaning.
4. Mark high-risk gaps as `field_gap`.

## Mandatory Rules

- A label alone does not prove that a field accepts input or supports validation.
- A search filter without a corresponding result column is not complete display coverage.
- Fixed text or numbers on a detail page do not prove dynamic data behavior.

## Deliverables

- Field coverage matrix
- Validation and default-value gaps
- List/detail/statistics display gaps

Use [templates/output.md](templates/output.md) for the output.
