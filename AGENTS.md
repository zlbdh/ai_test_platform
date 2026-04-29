# AGENTS.md

本文件是当前仓库给协作者和编码代理使用的事实说明。若文档与代码不一致，以代码为准，并在文档里登记漂移点。

## 协作原则

- 默认以中文交流、写文档、写说明
- 优先先读代码再做判断，不根据旧文档臆断现状
- 仓库长期处于活跃开发态，工作区可能很脏；不要批量回退源码改动
- 涉及清理时，只清缓存、构建产物、报告、临时日志和探针文件，不碰业务数据库、部署快照、浏览器 profile 和大型工具目录

## 当前架构事实

- 后端入口：`backend/main.py`
- 前端入口：`frontend/src/main.tsx`
- 编排主链：`Orchestrator + PlannerAgent + EventBus + ExecutorAgent + SessionState`
- 兼容层：`SharedBrowserState` 仍提供旧接口，但底层已桥接到 `SessionState`
- 前端主服务：`backendService.ts`、`commanderService.ts`、`deployService.ts`
- 前端主状态：`appStore`、`aiSettingsStore`、`agentStore`、`executionStore`、`commanderStore`、`legionControlStore`

## 当前目录事实

- `backend/routers/`：40 个路由文件，已纳入 `exploration`、`release`、`platform`、`commander` 等新域
- `backend/services/`：36 个服务文件，承担专项测试、平台治理、探索、发布风险和执行中心能力
- `backend/workflows/`：保留，属于 LangGraph 工作流实现
- `.agent/workflows/`：已移除，不再作为项目内置工作流入口
- `docx/`：中文第一方文档目录，已区分当前事实源与历史归档页

## 命令基线

### 后端

```powershell
cd backend
uvicorn main:app --host 127.0.0.1 --port 8020 --reload
python -m pytest tests/ -v
python -m pytest tests/unit/test_orchestrator.py -q
```

### 前端

```powershell
cd frontend
npm run dev
npm run build
npx vitest run
npx vitest run src/test/config.test.ts --reporter=dot
```

## 关键公共面

- REST：由 `main.py` 注册的路由族统一暴露
- SSE：核心日志流包含 `type`、`event`、`status`、`step_index`、`ui_track`
- 内部协议：`TaskEvent`、`ResultEvent`、`SessionState.run_browser()` 的浏览器线程命令队列
- 前端契约：`TestOrchestrator.tsx` 同时消费状态轮询和 SSE 结构化日志

## 当前已知漂移点

- 旧文档常把 `SharedBrowserState` 当成主要状态容器，这在当前代码里已经不成立
- 部分历史文档仍沿用旧模块规模和旧页面清单，现已在 `docx/` 中转成归档页
- 仓库里仍存在少量被 Git 跟踪的历史生成物，这类文件会优先做定点恢复，不在源码清理里粗暴移除

