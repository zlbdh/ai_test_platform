# AI Test Platform 公开脱敏版

这是从本机真实项目整理出的公开脱敏版，用于展示 AI 驱动测试平台的后端、前端、Agent 编排、技能说明与基础验证结构。仓库中的项目专名、客户/业务名称、内部路径、真实仓库地址、运行数据和历史测试材料已删除或泛化；请不要把这里的示例路径、示例 URL 当成真实环境配置。

AI 驱动的测试自动化平台，核心目标是把自然语言测试意图转成可执行的浏览器、接口、数据与专项测试任务，并把执行过程、日志、报告和治理能力统一收敛到一个工作台里。

## 当前事实

- 时间基线：2026-03-24
- 后端：`backend/`，FastAPI + Playwright + LangGraph/LangChain，默认端口 `8020`
- 前端：`frontend/`，React 19 + TypeScript 5.9 + Vite 7，默认端口 `8010`
- 规模快照：后端 `40` 个路由文件、`36` 个服务文件、`56` 个 core 文件、`117` 个测试文件；前端 `31` 个页面、`56` 个 `tsx` 组件文件
- 当前主运行时：`Orchestrator -> PlannerAgent -> EventBus -> ExecutorAgent -> SessionState`
- 兼容层说明：`core/shared.py` 中的 `SharedBrowserState` 仍在，但已退化为兼容代理；真实状态载体以 `core/session_manager.py` 的 `SessionState` 为准
- 仓库辅助流程说明：`.agent/workflows/` 已移除；后端 `backend/workflows/` 仍是受支持的 LangGraph 工作流目录

## 目录结构

- `backend/`：后端应用、路由、服务、代理、工作流、测试
- `frontend/`：前端工作台、页面、组件、服务、状态管理、测试
- `data/`：运行数据目录，公开版不包含本机运行数据
- `docx/`：公开版说明，不包含原始项目调研、回归材料或业务文档
- `.agent/skills/`：本地技能说明，保留

## 运行时主链路

1. `backend/main.py` 启动 FastAPI，注册路由、中间件、异常处理和浏览器直播入口。
2. 核心编排请求进入 `agents/orchestrator.py`，创建任务上下文、事件总线、会话状态和日志流。
3. `PlannerAgent` 在异步侧生成步骤或逐步推理，向 `EventBus` 投递 `TaskEvent`。
4. `ExecutorAgent` 在同步 Playwright 线程消费任务，执行导航、点击、填写、断言、自愈和视觉检查。
5. 执行结果通过 `ResultEvent` 回流给 orchestrator，并由日志流、状态接口和持久化层对外暴露。
6. 执行结果、批次上下文、历史记录、Allure 报告和专项产物分别落到 SQLite、JSON、Chroma 或报告目录。

## 能力域

- 核心编排：`core`、`plan`、`testing`、`report`、`history`
- 军团与批次：`commander`、`execution_center_service`、`LegionPage`
- 探索与发布风险：`exploration`、`release`、`quality_gate`
- 部署与平台治理：`deploy`、`platform`、`notification`、`scheduler`、`cicd`
- 专项测试工具：`graphql`、`grpc`、`database`、`mobile`、`security`、`accessibility`、`i18n`
- 知识与文档分析：`knowledge`、`document_*`、`RequirementPage`

## 启动命令

### 后端

```powershell
cd backend
uvicorn main:app --host 127.0.0.1 --port 8020 --reload
```

### 前端

```powershell
cd frontend
npm run dev
```

## 常用验证命令

默认不在清理后立即运行测试，因为会重新生成缓存、覆盖率和报告。

```powershell
cd backend
python -m pytest tests/unit/test_orchestrator.py -q

cd frontend
npx vitest run src/test/config.test.ts --reporter=dot
```

## 数据与清理边界

- 可清理：缓存目录、`dist`、PID、stdout/stderr 日志、临时截图、探针输出、Allure 生成物
- 默认保留：`data/deploy/`、`data/chrome_*_profile/`、`data/shadow_db_archive/`、`data/platform_maintenance_exports/`、`data/python311-embed/`、`data/sysinternals/`、所有 `*.db`、`chroma_db/`、auth/cookies/workbench 运行数据
- 被 Git 跟踪但本质属于生成物的路径，优先定点恢复到仓库基线，而不是直接从版本库中删除

## 公开发布边界

- 真实业务文档、原型资产、测试报告、运行日志、浏览器 profile、数据库、截图和部署快照不在公开版中。
- 第三方通知、LLM、数据库和系统管理密钥只保留环境变量名与 `.env.example` 占位，不包含真实凭据。
- 示例项目 playbook 已泛化为 sample platform，仅用于展示平台如何承载项目级测试包。
- 架构蓝图：`claw_architecture_blueprint_v3.md`
