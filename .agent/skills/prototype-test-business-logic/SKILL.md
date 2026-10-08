---
name: prototype-test-business-logic
description: HTML prototype testing — business logic completeness audit. Check cross-module integration, workflow completeness, business rule coverage, field completeness, and other missing business requirements.
---

# Business Logic Completeness Audit

## When to Use
Use this skill to audit HTML prototype business logic from a **product/business perspective**. Focus on complete workflows and integration between modules.

---

## Audit Checklist

### 1. Cross-Module Business Integration
- [ ] **Cascading state changes**: Confirm that a state change in module A updates data or available actions in module B.
  - Example: suspending a company blocks orders; blocklisting a customer prevents order placement.
- [ ] **Bidirectional data relationships**: Confirm that module A's detail page shows related records from module B.
  - Example: customer details show complaints; order details show the associated bill.
- [ ] **Write back action results**: Confirm that an action initiated in module A creates a record in module B.
  - Example: initiating a penalty from a complaint automatically creates a penalty-management record.

### 2. Workflow Completeness
- [ ] **Approval chain**: Confirm that workflows requiring approval have a complete approval prototype.
  - Check: initiate → initial review → secondary review → approve/reject → revise after rejection → resubmit.
- [ ] **Complete state machine**: Confirm that entity transitions cover all core scenarios.
  - Check: draft/pending review/approved/rejected/published/unpublished, with the correct action buttons for each state.
- [ ] **Exception paths**: Cover scenarios such as resubmission after rejection, overdue processing, and refunds after cancellation.
- [ ] **End-to-end completion**: Confirm that workflows reach a complete outcome without dead-end states.

### 3. Business Rule Coverage
- [ ] **Access control**: Provide role-specific action buttons, or at least document the differences in prototype comments.
- [ ] **Time constraints**: Set reasonable minimum and maximum values for date fields.
- [ ] **Amount calculations**: Ensure financial calculations are correct, such as unit price × quantity − discount = amount paid.
- [ ] **Quota limits**: Include necessary count or frequency limits, such as daily order limits or per-person claim limits.
- [ ] **Mutually exclusive rules**: Link conflicting choices, such as hiding the amount field when a free order is selected.

### 4. Field Completeness
- [ ] **Missing required fields**: Add key fields missing from the business scenario.
  - Common omissions: SLA deadlines, membership levels, audit logs, and supporting-document uploads.
- [ ] **Hardcoded settings**: Avoid hardcoding thresholds or rules, such as a 30-day contract expiration warning or a CNY 800 income-tax threshold.
- [ ] **Missing relationship fields**: Include related module information on detail pages, such as service personnel on order details.

---

## Audit Method

### Step 1: Map Module Relationships
```
List all modules and their business relationships:
- Company management → Order center (company order acceptance)
- Customer center → Complaint handling (customer complaints)
- Complaint handling → Penalty management (complaint-driven penalties)
- Order center → Financial settlement (orders generate bills)
- Training center → Exam management → Question bank (exams after training)
```

### Step 2: Verify Each Integration
```
For every pair of related modules:
1. Open module A's source and confirm that data or links point to module B.
2. Open module B's source and confirm that it displays related module A data.
3. Confirm that state-changing actions account for their effects on the other module.
```

### Step 3: Walk Through Workflows
```
For each workflow:
1. List the complete sequence of state transitions.
2. Confirm that each state has corresponding action buttons in the prototype.
3. Confirm that exception paths such as resubmission after rejection are handled.
```

---

## Output Template

```markdown
## Business Logic Audit Results — [Module/Business Domain]

### Cross-Module Integration
| Relationship | Integration result | Missing behavior | Priority |
|---------|---------|---------|-------|
| A → B | ❌ | Missing XXX relationship | 🔴 High |

### Workflow Completeness
| Workflow | Node coverage | Missing steps | Priority |
|------|---------|---------|-------|
| Company onboarding | 3/6 | Missing initial/financial/legal review | 🔴 High |

### Missing Fields
| Module | Missing field | Business scenario | Priority |
|------|---------|---------|-------|
| consumer-list | Membership level | Distinguish customer tiers | 🟡 Medium |
```

---

## Typical Issue Patterns

1. **Isolated modules**: Each module works independently, but data and state are not linked across modules.
2. **Broken approval chains**: Only submission and results are present; intermediate approvals are missing.
3. **Missing exception paths**: Only the happy path is covered, without rejection, timeout, or cancellation.
4. **Hardcoded settings**: Thresholds, rules, and policies cannot be configured because they are embedded in code.
5. **Missing related data**: Detail pages show only their own data, without records from related modules.
