# Current System Mapping

## 现有平台能力与文件锚点

### 1. 需求解析层

- 后端路由：[D:\workspace\ai_test_platform\backend\routers\requirement.py](D:/workspace/ai_test_platform/backend/routers/requirement.py)
- 现有能力：
  - `/api/requirement/analyze`
  - `/api/requirement/parse`
  - `/api/requirement/parse-file`
  - `/api/requirement/parse-upload`
  - `/api/requirement/generate-tests`
- 结构化结果包含：
  - `quality_score`
  - `completeness_score`
  - `testability_score`
  - `issues`
  - `extracted`
  - `next_actions`

### 2. 场景链层

- 后端路由：[D:\workspace\ai_test_platform\backend\routers\scenario.py](D:/workspace/ai_test_platform/backend/routers/scenario.py)
- 现有能力：
  - `/api/scenarios`
  - `/api/scenarios/import-playbook/{playbook_id}`
  - `/api/scenarios/{scenario_id}/execute`
- 适合承接：
  - 页面结构检查
  - 主操作检查
  - 异常边界检查
  - 跨模块链路检查

### 3. 视觉层

- 后端路由：[D:\workspace\ai_test_platform\backend\routers\visual.py](D:/workspace/ai_test_platform/backend/routers/visual.py)
- 现有能力：
  - `/api/visual/baselines`
  - `/api/visual/compare`
  - `/api/visual/capture`
  - `/api/visual/baselines/{name}/approve`
- 适合承接：
  - 关键页面基线
  - 视觉差异图
  - 视觉语义的证据补充

### 4. 门禁层

- 后端路由：[D:\workspace\ai_test_platform\backend\routers\quality_gate.py](D:/workspace/ai_test_platform/backend/routers/quality_gate.py)
- 现有能力：
  - `/api/quality-gate/check`
  - `/api/quality-gate/rules`
  - `/api/quality-gate/rules/import/{playbook_id}`
  - `/api/quality-gate/history`

### 5. Playbook / 项目级编排层

- 现有样板：[D:\workspace\ai_test_platform\backend\core\sample_platform_playbook.py](D:/workspace/ai_test_platform/backend/core/sample_platform_playbook.py)
- 现有事实：
  - 已内置模块蓝图、关键页面、页面映射、场景骨架、门禁规则。
  - `mapping_status` 当前存在 `mapped` 与 `pending_prototype` 两类基础状态。
  - 质量门禁已使用：
    - `module_coverage_rate`
    - `page_mapping_rate`
    - `critical_page_missing_count`
    - `blocking_prototype_gap_count`
    - `critical_field_missing_count`
    - `critical_state_transition_gap_count`

## 新 skill 套件与现有系统的关系

- 新 skill 套件不替代平台 API；它在 agent 层组织、解释和使用这些能力。
- 新 skill 套件补的是：
  - 工程化 SOP
  - 统一 taxonomy
  - 证据规范
  - 防误判规则
  - 按角色输出整改建议
- 新 skill 套件不直接承诺：
  - 真实接口联调
  - 真实权限与落库验证
  - 静态 HTML 无法证明的动态行为
