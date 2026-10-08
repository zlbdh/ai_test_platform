# AGENTS.md

This file records current repository facts for collaborators and coding agents. If documentation and code disagree, follow the code and document the discrepancy.

## Collaboration principles

- Use American English by default for communication, documentation, and explanations.
- Read the code before drawing conclusions; do not infer the current state from old documentation.
- This repository is under active development, and the working tree may contain many changes. Do not revert source changes in bulk.
- Cleanup is limited to caches, build artifacts, reports, temporary logs, and probe files. Preserve business databases, deployment snapshots, browser profiles, and large tool directories.

## Current architecture

- Backend entry point: `backend/main.py`
- Frontend entry point: `frontend/src/main.tsx`
- Main orchestration path: `Orchestrator + PlannerAgent + EventBus + ExecutorAgent + SessionState`
- Compatibility layer: `SharedBrowserState` still provides legacy interfaces, but its implementation delegates to `SessionState`.
- Main frontend services: `backendService.ts`, `commanderService.ts`, `deployService.ts`
- Main frontend stores: `appStore`, `aiSettingsStore`, `agentStore`, `executionStore`, `commanderStore`, `legionControlStore`

## Current directory structure

- `backend/routers/`: 40 route files, including newer domains such as `exploration`, `release`, `platform`, and `commander`
- `backend/services/`: 36 service files for specialized testing, platform governance, exploration, release risk, and the execution center
- `backend/workflows/`: retained for LangGraph workflow implementations
- `.agent/workflows/`: removed; no longer an entry point for built-in project workflows
- `docx/`: first-party documentation, with current sources of truth distinguished from historical archives

## Baseline commands

### Backend

```powershell
cd backend
uvicorn main:app --host 127.0.0.1 --port 8020 --reload
python -m pytest tests/ -v
python -m pytest tests/unit/test_orchestrator.py -q
```

### Frontend

```powershell
cd frontend
npm run dev
npm run build
npx vitest run
npx vitest run src/test/config.test.ts --reporter=dot
```

## Key public interfaces

- REST: route groups registered by `main.py`
- SSE: the core log stream includes `type`, `event`, `status`, `step_index`, and `ui_track`.
- Internal protocols: `TaskEvent`, `ResultEvent`, and the browser-thread command queue in `SessionState.run_browser()`
- Frontend contract: `TestOrchestrator.tsx` consumes both status polling and structured SSE logs.

## Known documentation drift

- Older documentation often describes `SharedBrowserState` as the primary state container; this no longer reflects the code.
- Some historical documents use obsolete module counts and page inventories. They have been moved to archive pages in `docx/`.
- A few historical generated artifacts remain tracked by Git. Restore these selectively rather than deleting them indiscriminately during source cleanup.
