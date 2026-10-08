---
name: prototype-test-data-display
description: HTML prototype testing — data display richness audit. Check mock-data volume, dashboard dimension coverage, dynamic detail-page data, and chart interaction.
---

# Data Display Richness Audit

## When to Use
Use this skill to assess the **data display quality** of HTML prototypes. Focus on data richness, dimension coverage, and support for understanding and demonstrating requirements.

---

## Audit Checklist

### 1. Mock-Data Volume
- [ ] **List volume**: Provide at least 10–15 mock records per list page.
  - Fewer than 5: insufficient to demonstrate pagination and search effectively.
  - 5–10: basically usable, but may not cover all states.
  - More than 15: ideal for demonstrating pagination and search fully.
- [ ] **State coverage**: Include mock data for every business state.
  - For orders: awaiting acceptance/in progress/completed/canceled/exception/refunding.
- [ ] **Role coverage**: Represent differences between entity types or roles.
  - For companies: property management/housekeeping/senior care/products.
- [ ] **Time distribution**: Spread mock data across a reasonable period.
  - Avoid concentrating all records on the same day or in the same month.

### 2. Dashboards
- [ ] **Metric completeness**: Inventory core dashboard metrics and add missing key dimensions.
  - Basic metrics: totals, increments, proportions.
  - Advanced metrics: year-over-year growth, period-over-period changes, trend direction.
- [ ] **Time dimensions**: Support switching among day/week/month/quarter/year views.
- [ ] **Comparison dimensions**: Include comparisons across business lines, companies, regions, and other dimensions.
- [ ] **Metric explanations**: State comparison baselines, such as “+12.5% vs. last month,” instead of only “↑ 12.5%.”
- [ ] **Chart interaction**: Support drilldowns, filtering, and hover tooltips.

### 3. Dynamic Detail-Page Data
- [ ] **Record context**: Make detail-page data change with the selected record.
  - Common issue: every record's statistics cards show the same hardcoded numbers.
- [ ] **Related records**: Associate detail-page subtables and tabs with the current record.
  - Example: customer purchase history uses that customer's records.
- [ ] **Profile/chart data**: Generate charts from the object's actual attributes.
  - Common issue: pie/bar charts use random or fixed values rather than object data.

### 4. Charts and Visualization
- [ ] **Chart implementation**: Determine whether charts use CSS approximations or a chart library such as ECharts/Chart.js.
  - CSS approximations (`conic-gradient`, `div.bar`) are acceptable in prototypes, but document their implementation-stage replacements.
- [ ] **Data labels**: Display values or percentages on charts.
- [ ] **Legends and annotations**: Include legends and axis labels.
- [ ] **Empty states**: Show an empty-state message rather than a blank area when chart data is unavailable.

### 5. Exports and Reports
- [ ] **Export actions**: Provide export buttons for lists or reports.
- [ ] **Export formats**: Support formats such as Excel/PDF/CSV.
- [ ] **Export scope**: State whether the export includes current search results or all data.

---

## Audit Method

### Step 1: Scan Data Volume
```javascript
// Find mock-data arrays in the source
// Check record counts (array lengths)
const dataArray = [...]; // Find similar variables
console.log(dataArray.length); // Target: >= 10
```

### Step 2: Check State Coverage
```
1. List every business state in the module.
2. Confirm that mock data includes at least one record in each state.
3. Mark missing states.
```

### Step 3: Analyze Dashboard Dimensions
```
1. Capture the current dashboard.
2. List every displayed metric.
3. Compare with business requirements and add missing key metrics.
4. Confirm that the page supports changing time granularity.
```

### Step 4: Verify Dynamic Detail Data
```
1. Open the page with browser_subagent.
2. Open Details for several records in turn.
3. Compare changes in the detail-page statistics.
4. If the values do not change, flag hardcoded data.
```

---

## Output Template

```markdown
## Data Display Audit Results — [Module]

### Mock-Data Volume
| Assessment | Current | Recommended | Status |
|-------|------|------|------|
| List records | 5 | 15+ | ❌ Insufficient |
| State coverage | 3/6 | 6/6 | ❌ Incomplete |
| Time distribution | 1 month | 6+ months | ❌ Concentrated |

### Dashboard Metrics
| Metric category | Covered | Missing |
|---------|-------|------|
| Basic totals | ✅ | — |
| Year-over-year/period-over-period | ❌ | Add comparisons |
| Category statistics | ❌ | Break down by type |

### Dynamic Detail Pages
| Check | Dynamic result | Description |
|-------|---------|------|
| Statistics cards | ❌ Hardcoded | Every record shows the same data |
| Subtable data | ✅ Dynamic | Related records selected with .filter() |
```

---

## Typical Issue Patterns

1. **Too little data**: Lists contain only 3–5 records, preventing effective pagination and search demonstrations.
2. **Incomplete state coverage**: Some states are absent, so certain search options return no results.
3. **Limited dashboard dimensions**: Only absolute values appear, without year-over-year/period-over-period comparisons or trends.
4. **Hardcoded detail data**: Statistics and charts always show fixed values regardless of the selected record.
5. **Placeholder charts**: Emoji or “Map placeholder” text replaces actual visualizations.
