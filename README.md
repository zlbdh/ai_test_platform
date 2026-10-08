# AI Test Platform: Sanitized Public Edition

This sanitized public edition was prepared from a real local project to demonstrate the backend, frontend, agent orchestration, skill instructions, and basic verification structure of an AI-driven testing platform. Project-specific names, customer and business names, internal paths, real repository URLs, runtime data, and historical test materials have been removed or generalized. Example paths and URLs are not real environment configuration.

The platform turns natural-language test intentions into executable browser, API, data, and specialized test tasks. A unified workbench brings together execution, logs, reports, and governance.

## Current facts

- Baseline date: March 24, 2026
- Backend: `backend/`, using FastAPI, Playwright, and LangGraph/LangChain; default port `8020`
- Frontend: `frontend/`, using React 19, TypeScript 5.9, and Vite 7; default port `8010`
- Size snapshot: backend has `40` route files, `36` service files, `56` core files, and `117` test files; frontend has `31` pages and `56` `tsx` component files.
- Main runtime: `Orchestrator -> PlannerAgent -> EventBus -> ExecutorAgent -> SessionState`
- Compatibility: `SharedBrowserState` in `core/shared.py` remains as a compatibility proxy. `SessionState` in `core/session_manager.py` is the authoritative state container.
- Repository workflows: `.agent/workflows/` has been removed; `backend/workflows/` remains the supported LangGraph workflow directory.

## Directory structure

- `backend/`: application, routes, services, agents, workflows, and tests
- `frontend/`: workbench, pages, components, services, state management, and tests
- `data/`: runtime data directory; local runtime data is excluded from this public edition
- `docx/`: public-edition notes; original project research, regression materials, and business documents are excluded
- `.agent/skills/`: retained local skill instructions

## Main runtime flow

1. `backend/main.py` starts FastAPI and registers routes, middleware, exception handlers, and browser streaming endpoints.
2. Core orchestration requests enter `agents/orchestrator.py`, which creates the task context, event bus, session state, and log stream.
3. `PlannerAgent` generates steps or reasons incrementally on the asynchronous side, publishing `TaskEvent` messages to `EventBus`.
4. `ExecutorAgent` consumes tasks on the synchronous Playwright thread, performing navigation, clicks, form entry, assertions, self-healing, and visual checks.
5. Results return to the orchestrator through `ResultEvent` and are exposed through log streams, status APIs, and persistence.
6. Results, batch context, history, Allure reports, and specialized artifacts are stored in SQLite, JSON, Chroma, or report directories as appropriate.

## Capability areas

- Core orchestration: `core`, `plan`, `testing`, `report`, `history`
- Legion and batch execution: `commander`, `execution_center_service`, `LegionPage`
- Exploration and release risk: `exploration`, `release`, `quality_gate`
- Deployment and platform governance: `deploy`, `platform`, `notification`, `scheduler`, `cicd`
- Specialized testing tools: `graphql`, `grpc`, `database`, `mobile`, `security`, `accessibility`, `i18n`
- Knowledge and document analysis: `knowledge`, `document_*`, `RequirementPage`

## Startup commands

### Backend

```powershell
cd backend
uvicorn main:app --host 127.0.0.1 --port 8020 --reload
```

### Frontend

```powershell
cd frontend
npm run dev
```

## Common verification commands

By default, do not run tests immediately after cleanup: they regenerate caches, coverage files, and reports.

```powershell
cd backend
python -m pytest tests/unit/test_orchestrator.py -q

cd frontend
npx vitest run src/test/config.test.ts --reporter=dot
```

## Data and cleanup boundaries

- Safe to clean: cache directories, `dist`, PID files, stdout/stderr logs, temporary screenshots, probe output, and generated Allure artifacts
- Preserve by default: `data/deploy/`, `data/chrome_*_profile/`, `data/shadow_db_archive/`, `data/platform_maintenance_exports/`, `data/python311-embed/`, `data/sysinternals/`, all `*.db` files, `chroma_db/`, and auth/cookies/workbench runtime data
- For generated artifacts tracked by Git, prefer selectively restoring the repository baseline over deleting them from version control.

## Public release boundaries

- Real business documents, prototype assets, test reports, runtime logs, browser profiles, databases, screenshots, and deployment snapshots are excluded.
- Notification service, LLM, database, and system administration credentials are represented only by environment-variable names and `.env.example` placeholders. No real credentials are included.
- The example project playbook has been generalized to sample platform. It demonstrates how the platform hosts project-specific test packages.
- Architecture blueprint: `claw_architecture_blueprint_v3.md`
