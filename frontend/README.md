# Frontend

The frontend workbench provides UI capabilities for test orchestration, the legion center, the execution center, specialized testing, deployment governance, and knowledge analysis.

## Current facts

- Stack: React 19, TypeScript 5.9, Vite 7, Zustand 5, TailwindCSS 3.4
- Default port: `8010`
- Page count: `31` page files
- Service entry points: `backendService.ts`, `commanderService.ts`, `deployService.ts`, `notificationService.ts`, `requirementService.ts`
- State management: multiple Zustand stores organized by domain, including `executionStore`, `commanderStore`, and `legionControlStore`

## Development commands

```powershell
npm run dev
npm run build
npm run lint
npx tsc -b --noEmit
npx vitest run
```

## Main frontend contracts

- `TestOrchestrator.tsx` consumes both the backend SSE log stream and status polling API.
- `backendService.ts` uses native `fetch` and `AbortController`.
- Navigation covers orchestration, legions, exploration, release risk, deployment, notifications, knowledge, and specialized testing.

## Documentation boundaries

- Documentation in this directory records current frontend facts only.
- For project architecture and cleanup policies, see the root `README.md` and `docx/` documentation.
- `.agent/workflows/` has been removed; it is not a frontend runtime capability.
