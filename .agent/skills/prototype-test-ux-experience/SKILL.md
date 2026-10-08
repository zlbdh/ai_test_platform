---
name: prototype-test-ux-experience
description: HTML prototype testing — user experience audit. Check information architecture, action-path efficiency, batch actions, navigation consistency, responsive behavior, accessibility, and other experience dimensions.
---

# User Experience Audit

## When to Use
Use this skill to assess HTML prototypes from the perspective of **user efficiency and visual experience**. Focus on ease of operation, findability, and overall efficiency.

---

## Audit Checklist

### 1. Information Architecture and Layout
- [ ] **Table columns**: Keep lists within 10 columns and avoid horizontal scrolling on a 1366px screen.
- [ ] **Column priority**: Keep frequently used state/action columns on the right and fixed in view.
- [ ] **Information density**: Prevent key dashboard information from being squeezed or clipped on a 1366×768 laptop screen.
- [ ] **Truncated content**: Provide tooltips, popovers, or expand buttons for long text.
- [ ] **Card layout**: Make statistics-card `grid-template-columns` wrap responsively on smaller screens.

### 2. Action-Path Efficiency
- [ ] **Core action steps**: Limit steps for core business actions and continually streamline paths.
  - Best: 1–2 steps, such as direct list editing or inline actions.
  - Acceptable: 3–4 steps, such as list → details → action → confirm.
  - Needs improvement: 5 or more steps.
- [ ] **Common action visibility**: Keep the most-used buttons visible without scrolling.
- [ ] **Return paths**: Keep the path from details or child pages back to the list short and direct.
- [ ] **Context preservation**: Preserve search filters and page numbers when returning from details.

### 3. Batch Actions
- [ ] **Multi-selection**: Provide list checkboxes for selecting multiple records.
- [ ] **Batch buttons**: Provide batch export, deletion, state changes, and similar actions.
- [ ] **Select/deselect all**: Provide a select-all checkbox in the table header.
- [ ] **Selection count**: Display “X selected” after multi-selection.

### 4. Navigation Consistency
- [ ] **Breadcrumbs**: Provide breadcrumbs on every page, with links to parent levels.
- [ ] **Back button placement**: Use a consistent position, preferably the upper-right corner.
- [ ] **Tab order**: Put frequently used tabs first; provide collapsing or scrolling when there are more than five.
- [ ] **Previous/next record**: Provide quick record switching for frequent approval and processing tasks.
- [ ] **Keyboard shortcuts**: Support `Esc` to close dialogs or return to the list.

### 5. Feedback and Confirmation
- [ ] **Success feedback**: Clearly confirm submission, saving, and deletion.
- [ ] **Failure feedback**: Give specific validation errors instead of a generic “Operation failed.”
- [ ] **Dangerous-action confirmation**: Require confirmation dialogs for irreversible actions such as deletion, disabling, or terminating a partnership.
- [ ] **Extra confirmation for critical actions**: Require a typed confirmation phrase, such as “Confirm penalty,” for major actions such as suspending business operations.
- [ ] **Loading states**: Show loading feedback for long operations and disable buttons to prevent duplicate submission.

### 6. Visual Consistency
- [ ] **Color semantics**: Use consistent colors throughout: success (green), warning (orange), danger (red), information (gray).
- [ ] **Tag styles**: Keep `.tag-success / .tag-warning / .tag-danger` colors consistent with their meanings.
- [ ] **Font sizes**: Establish clear size levels for body text, headings, labels, and buttons.
- [ ] **Spacing**: Keep card gaps, table padding, and dialog padding consistent throughout.

### 7. Responsive Behavior
- [ ] **Minimum width**: Keep pages usable at 1280px width.
- [ ] **Table scrolling**: Allow wide tables to scroll horizontally without breaking layout.
- [ ] **Dialog sizing**: Constrain `max-width` and `max-height` with `vw/vh` units.

---

## Audit Method

### Method A: Experience Walkthrough
```
1. Open the page at 1366×768 with browser_subagent.
2. Capture the initial viewport.
3. Simulate common paths: search → view → edit → save → return.
4. Record action counts and experience issues.
```

### Method B: Consistency Review
```
1. List Back button positions across modules.
2. Compare tab ordering across modules.
3. Check consistency of .tag styles throughout.
4. Compare dialog sizes and layout patterns.
```

### Method C: Efficiency Testing
```
1. Select five core business scenarios.
2. Count the minimum steps from entry to completion for each scenario.
3. Identify improvements such as shortcuts or fewer dialog layers.
```

---

## Output Template

```markdown
## User Experience Audit Results — [Module]

### Action-Path Efficiency
| Scenario | Current steps | Recommended steps | Improvement |
|------|---------|---------|---------|
| Approve a complaint | 6 | 3 | Add inline list actions |

### Consistency Checks
| Check | Status | Description |
|-------|------|------|
| Back button placement | ❌ Inconsistent | Upper-left on some pages, upper-right on others |
| Tag color semantics | ❌ Inconsistent | tag-success uses a blue background |

### Missing Batch Actions
| Module | Missing action | Recommendation |
|------|---------|------|
| enterprise-list | Batch export/suspend | Add multi-selection and a batch-action bar |
```

---

## Typical Issue Patterns

1. **Inconsistent Back placement**: Back to list alternates between upper-left and upper-right across modules.
2. **Missing batch actions**: List pages provide select-all checkboxes without corresponding batch buttons.
3. **Too many columns**: More than 10 columns require horizontal scrolling to reach actions on laptops.
4. **Long action paths**: Routine actions require 5+ steps, such as view → return → search → view → act.
5. **Lost context**: Returning from details resets filters and page numbers.
