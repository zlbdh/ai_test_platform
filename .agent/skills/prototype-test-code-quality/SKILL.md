---
name: prototype-test-code-quality
description: HTML prototype testing — code standards and migration readiness audit. Check CSS design-system consistency, JavaScript conventions, component portability, semantic HTML, security risks, and other code-quality dimensions.
---

# Code Standards and Migration Readiness Audit

## When to Use
Use this skill to assess HTML prototype code quality and readiness for framework migration from a **developer/architect perspective**. Focus on coding conventions and readiness to migrate to the target administration framework.

---

## Audit Checklist

### 1. CSS Design-System Consistency
- [ ] **CSS variables**: Define global variables in `:root` with consistent naming.
  ```css
  :root {
    --primary: #409EFF;
    --success: #67C23A;
    --warning: #E6A23C;
    --danger: #F56C6C;
  }
  ```
- [ ] **Variable reuse**: Use `var(--xxx)` throughout styles rather than hardcoded colors.
- [ ] **Correct color semantics**: Keep `.tag-success` backgrounds green; avoid incorrect blue palettes such as `#f0f9ff`.
- [ ] **Type scale**: Establish clear font-size levels, such as 11px/12px/13px/14px/16px.
- [ ] **Cross-module CSS consistency**: Compare `:root` definitions from five modules and confirm that they match exactly.

### 2. JavaScript Conventions
- [ ] **Global function names**: Use consistent names such as `renderTable()`, `handleSearch()`, `handleReset()`, `showDetail()`, and `backToList()`.
- [ ] **Data array names**: Use the `xxxList` + `filtered` naming pattern consistently for primary arrays.
- [ ] **State maps**: Manage label styles centrally with maps such as `statusMap` and `typeMap`.
- [ ] **Event binding**: Use a consistent convention rather than mixing inline `onclick=""` with `addEventListener`.
- [ ] **Code comments**: Add module headers containing the filename, purpose, and requirement source.
  ```javascript
  // =============================================
  // Module: XXX — List page
  // File: modules/xxx-list.html
  // Requirement source: xx_requirements.md § 3.1
  // =============================================
  ```

### 3. Component Portability
- [ ] **Clear function boundaries**: Provide separate functions such as renderTable, handleSearch, and showDetail instead of mixing responsibilities.
- [ ] **Separate data and views**: Store data in JavaScript arrays and render it through functions rather than hardcoding it in HTML.
- [ ] **Consistent dialogs**: Use the `.modal-mask + .modal` pattern for all dialogs.
- [ ] **Reusable confirmations**: Provide a shared `showConfirm(msg, callback)` function.
- [ ] **Reusable toasts**: Provide a shared `showToast(msg, type)` function.
- [ ] **Migration difficulty**:
  - Low: data arrays → `ref([])`, `renderTable()` → `v-for`, `onclick` → `@click`
  - Medium: dialogs → `el-dialog + v-model` (refer to dialog_v_model_pattern)
  - High: complex charts → ECharts components

### 4. HTML Structure and Semantics
- [ ] **Form name attributes**: Set `name` on `<input>`, `<select>`, and `<textarea>` elements.
- [ ] **Unique form IDs**: Ensure that every element's `id` is globally unique.
- [ ] **Semantic elements**: Use HTML5 elements such as `<header>`, `<main>`, `<footer>`, and `<section>` appropriately.
- [ ] **Accessible tables**: Separate `<thead>` and `<tbody>` within `<table>`.
- [ ] **Image alt attributes**: Provide an `alt` description for `<img>`.

### 5. Security and Performance
- [ ] **XSS risks**: Escape user input before assigning it to `innerHTML`.
  - Mock data does not pose this risk during prototyping, but document the implementation-stage handling.
- [ ] **Password security**: Use secure randomness instead of `Math.random()` to generate passwords.
- [ ] **Timer cleanup**: Pair `setInterval` and `setTimeout` with `clearInterval` and `clearTimeout`.
- [ ] **Memory leaks**: Remove dynamically created DOM elements such as toasts when no longer needed.

---

## Audit Method

### Step 1: Scan CSS Consistency
```bash
# Extract and compare :root definitions from all modules
grep -h ":root{" modules/*.html | sort | uniq -c
```

### Step 2: Scan Function Naming
```bash
# Extract function definitions from all modules
grep -oh "function [a-zA-Z]*(" modules/*.html | sort | uniq -c | sort -rn
```

### Step 3: Check Component Patterns
```
1. Compare renderTable() patterns in five list modules.
2. Compare openForm() / submitForm() patterns in five form modules.
3. List the dialog function signatures (showConfirm/showToast) used by all modules.
```

### Step 4: Assess Migration Readiness
```
Assess each layer against the target administration framework:
- Data: mock arrays → API calls
- Views: innerHTML → Vue templates
- Interaction: onclick → @click + methods
- Components: custom dialogs → Element Plus
- Routing: display:none → Vue Router
```

---

## Output Template

```markdown
## Code Quality Audit Results — [Module/Global]

### CSS Design System
| Check | Status | Description |
|-------|------|------|
| :root variable definitions | ✅ Consistent | Identical definitions across 70 modules |
| Correct color semantics | ❌ Incorrect | tag-success uses a blue background |

### Coding Conventions
| Check | Status | Description |
|-------|------|------|
| Consistent function names | ✅ | Uniform renderTable/handleSearch patterns |
| Module comments | ✅ | Every file has a header comment |
| name attributes | ❌ | All forms lack name attributes |

### Migration Readiness
| Migration item | Difficulty | Description |
|-------|------|------|
| Data → API | Low | Clear data-array structure |
| Dialogs → el-dialog | Medium | Requires the v-model pattern |
| Charts → ECharts | High | All CSS placeholder charts need rewriting |
```

---

## Typical Issue Patterns

1. **Incorrect CSS variable semantics**: `.tag-success` uses a blue background instead of green.
2. **Missing form name attributes**: All inputs have id but no name.
3. **innerHTML XSS risks**: Data is interpolated directly into HTML strings without escaping.
4. **Math.random() passwords**: Password generation is insecure.
5. **Uncleared setInterval timers**: Timers keep running after page changes.
