# Current System Mapping

## Existing Platform Capabilities and File Anchors

### 1. Requirement Analysis Layer

- Backend route: [D:\workspace\ai_test_platform\backend\routers\requirement.py](D:/workspace/ai_test_platform/backend/routers/requirement.py)
- Existing capabilities:
  - `/api/requirement/analyze`
  - `/api/requirement/parse`
  - `/api/requirement/parse-file`
  - `/api/requirement/parse-upload`
  - `/api/requirement/generate-tests`
- Structured results include:
  - `quality_score`
  - `completeness_score`
  - `testability_score`
  - `issues`
  - `extracted`
  - `next_actions`

### 2. Scenario Workflow Layer

- Backend route: [D:\workspace\ai_test_platform\backend\routers\scenario.py](D:/workspace/ai_test_platform/backend/routers/scenario.py)
- Existing capabilities:
  - `/api/scenarios`
  - `/api/scenarios/import-playbook/{playbook_id}`
  - `/api/scenarios/{scenario_id}/execute`
- Suitable for:
  - Page structure checks
  - Main action checks
  - Exception and boundary checks
  - Cross-module workflow checks

### 3. Visual Layer

- Backend route: [D:\workspace\ai_test_platform\backend\routers\visual.py](D:/workspace/ai_test_platform/backend/routers/visual.py)
- Existing capabilities:
  - `/api/visual/baselines`
  - `/api/visual/compare`
  - `/api/visual/capture`
  - `/api/visual/baselines/{name}/approve`
- Suitable for:
  - Key-page baselines
  - Visual difference images
  - Supporting evidence for visual semantics

### 4. Gate Layer

- Backend route: [D:\workspace\ai_test_platform\backend\routers\quality_gate.py](D:/workspace/ai_test_platform/backend/routers/quality_gate.py)
- Existing capabilities:
  - `/api/quality-gate/check`
  - `/api/quality-gate/rules`
  - `/api/quality-gate/rules/import/{playbook_id}`
  - `/api/quality-gate/history`

### 5. Playbook / Project Orchestration Layer

- Existing example: [D:\workspace\ai_test_platform\backend\core\sample_platform_playbook.py](D:/workspace/ai_test_platform/backend/core/sample_platform_playbook.py)
- Current facts:
  - Built-in module blueprints, key pages, page mappings, scenario skeletons, and gate rules already exist.
  - `mapping_status` currently has two basic states: `mapped` and `pending_prototype`.
  - Quality gates already use:
    - `module_coverage_rate`
    - `page_mapping_rate`
    - `critical_page_missing_count`
    - `blocking_prototype_gap_count`
    - `critical_field_missing_count`
    - `critical_state_transition_gap_count`

## Relationship Between the New Skill Suite and the System

- The new skills do not replace platform APIs; they organize, explain, and use those capabilities at the agent layer.
- The new suite adds:
  - Engineering SOPs
  - Shared taxonomy
  - Evidence requirements
  - Rules against misjudgment
  - Role-specific remediation recommendations
- The new suite does not directly promise:
  - Live API integration testing
  - Verification of actual permissions and database persistence
  - Dynamic behavior that static HTML cannot prove
