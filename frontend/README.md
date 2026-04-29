# frontend

前端工作台负责承接测试编排、军团中心、执行中心、专项测试、部署治理和知识分析等 UI 能力。

## 当前事实

- 技术栈：React 19、TypeScript 5.9、Vite 7、Zustand 5、TailwindCSS 3.4
- 默认端口：`8010`
- 页面规模：`31` 个页面文件
- 服务入口：`backendService.ts`、`commanderService.ts`、`deployService.ts`、`notificationService.ts`、`requirementService.ts`
- 状态管理：以多个 Zustand store 分域维护，关键包括 `executionStore`、`commanderStore`、`legionControlStore`

## 开发命令

```powershell
npm run dev
npm run build
npm run lint
npx tsc -b --noEmit
npx vitest run
```

## 前端主契约

- `TestOrchestrator.tsx` 同时消费后端 SSE 日志流和状态轮询接口
- `backendService.ts` 使用原生 `fetch` + `AbortController`
- 页面导航已扩展到编排、军团、探索、发布风险、部署、通知、知识和专项测试等多个域

## 文档边界

- 本目录文档只记录前端当前事实
- 项目级架构与清理策略请回到仓根 `README.md` 和 `docx/` 文档
- `.agent/workflows/` 已移除，这不是前端运行时能力的一部分

