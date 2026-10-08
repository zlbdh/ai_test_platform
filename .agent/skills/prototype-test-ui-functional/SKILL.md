---
name: prototype-test-ui-functional
description: HTML prototype testing — UI functional correctness. Verify page rendering, interactions, form validation, search/filtering, pagination, dialogs, and other core UI features.
---

# UI Functional Correctness Testing

## When to Use
Use this skill to systematically verify **interface functionality** in HTML prototypes. Focus on whether visible features work correctly.

---

## Test Checklist

### 1. Page Rendering and Initialization
- [ ] The page opens without JavaScript errors; check the browser console.
- [ ] Initial loading renders list data correctly and automatically calls `renderTable()`.
- [ ] Empty data shows a placeholder such as “No data” with an icon.
- [ ] Statistics cards and metrics display correctly; inspect `innerHTML` assignments if useful.

### 2. Search and Filtering
- [ ] **Every search field participates in filtering**: Inspect `handleSearch()` and verify that every `<input>/<select>` search condition is referenced in `.filter()`.
- [ ] Searching updates both table data and the “X total” count.
- [ ] Reset clears every search field and restores all data.
- [ ] Keyword search uses partial matching such as `includes()` rather than `===`.
- [ ] Dropdown `<option>` values match source-data fields, such as `value="Pending review"` corresponding to `status==='Pending review'`.

### 3. Pagination
- [ ] Pagination follows the data, updating total counts and page numbers after a search.
- [ ] Pagination is not hardcoded HTML; avoid a fixed `<span>5 total</span>`.
- [ ] Page buttons are clickable and change the displayed data.
- [ ] First-page and last-page boundaries are handled correctly.

### 4. Forms and Dialogs
- [ ] Opening an add dialog automatically clears the form.
- [ ] **Edit dialogs** populate the current record's values when opened; this is a frequent omission.
- [ ] Submitting an empty form shows errors for required fields.
- [ ] Field-length limits use attributes such as `maxlength`.
- [ ] Phone numbers, identity-document numbers, email addresses, and similar fields have format validation.
- [ ] The ✕ button, Cancel button, and backdrop all close the dialog.
- [ ] Dialog titles clearly distinguish “Add XXX” from “Edit XXX.”

### 5. State Changes and Actions
- [ ] Enable/disable changes require a confirmation dialog.
- [ ] Deletion requires a confirmation dialog.
- [ ] State changes refresh the list and display the latest state.
- [ ] Button enabled/disabled logic is correct; for example, completed orders do not show a Process button.

### 6. List ↔ Detail Navigation
- [ ] Details/View opens the correct detail view.
- [ ] Back to list restores the list view.
- [ ] Breadcrumb text updates accordingly.
- [ ] Detail data matches the selected record rather than fixed data.

### 7. Tabs
- [ ] Switching tabs shows and hides the appropriate content.
- [ ] The current tab uses the `.active` highlight style.
- [ ] Tab contents render correctly without blank regions.

---

## Test Methods

### Method A: Static Source Review
```
1. Inspect each module's source with view_file.
2. Locate core functions such as handleSearch(), renderTable(), openForm(), and showDetail().
3. Verify that every search field participates in filtering.
4. Verify that editing includes code to populate existing values.
```

### Method B: Dynamic Browser Testing
```
1. Open the target HTML file with browser_subagent.
2. Search and observe the results.
3. Click Edit and inspect the populated form.
4. Submit an empty form and inspect validation messages.
5. Capture screenshots of test results.
```

---

## Output Template

```markdown
## UI Functional Test Results — [Module]

| Check | Result | Description |
|-------|------|------|
| Page rendering | ✅/❌ | |
| All search fields participate | ✅/❌ | Missing fields: XXX |
| Pagination follows data | ✅/❌ | |
| Edit form population | ✅/❌ | |
| Deletion confirmation | ✅/❌ | |
| Correct detail data | ✅/❌ | |
```

---

## Typical Issue Patterns

1. **Hardcoded pagination**: `.pagination` contains static HTML, and `renderTable()` does not update it.
2. **Partial search support**: `handleSearch()` filters only 1–2 fields and ignores the rest.
3. **Unpopulated edit forms**: `openForm(id)` only sets `editId=id` and changes the title without populating fields.
4. **Mismatched state values**: Search dropdown `value` text differs from values in the data array.
