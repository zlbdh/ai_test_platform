import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const mockNavigate = vi.fn();
const {
    mockCancelFrontdoorTask,
    mockGetFrontdoorTask,
    mockListFrontdoorTasks,
    mockRerunFrontdoorTask,
    mockStreamFrontdoorTask,
} = vi.hoisted(() => ({
    mockCancelFrontdoorTask: vi.fn(),
    mockGetFrontdoorTask: vi.fn(),
    mockListFrontdoorTasks: vi.fn(),
    mockRerunFrontdoorTask: vi.fn(),
    mockStreamFrontdoorTask: vi.fn(),
}));

vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
    return {
        ...actual,
        useNavigate: () => mockNavigate,
    };
});

vi.mock('../services/frontdoorTaskService', () => ({
    cancelFrontdoorTask: mockCancelFrontdoorTask,
    getFrontdoorTask: mockGetFrontdoorTask,
    listFrontdoorTasks: mockListFrontdoorTasks,
    rerunFrontdoorTask: mockRerunFrontdoorTask,
    streamFrontdoorTask: mockStreamFrontdoorTask,
}));

import TaskResultPage from '../pages/TaskResultPage';
import { useFrontdoorTaskStore } from '../stores';

const runningTask = {
    task_id: 'task001',
    mission_kind: 'commander',
    task_kind: 'prototype' as const,
    user_goal: "Perform a unified review of the order prototype",
    status: 'executing',
    created_at: '2026-04-02T15:00:00',
    started_at: '2026-04-02T15:00:01',
    completed_at: null,
    source_context: { source_type: 'directory', source: 'D:\\prototype' },
    strategy: { wcag_level: 'AA' },
    agent_states: { orchestrator: 'running', reporter: 'pending' },
    evidence_summary: {
        log_count: 2,
        finding_count: 1,
        has_report: true,
        execution_group_id: 'task001',
        summary_keys: ['page_mapping_rate'],
        evidence_ids: ['evi001'],
        latest_log_at: '2026-04-02T15:00:03',
        static_unprovable_count: 1,
    },
    findings: [
        {
            finding_id: 'finding001',
            evidence_id: 'evi001',
            severity: 'major',
            title: "Page mapping risk",
            summary: "The purchasing management list is not mapped correctly.",
            category: 'mis_mapping',
            agent_id: 'orchestrator',
            source_type: 'html',
            locator: 'modules/site-list.html',
        },
    ],
    gate_summary: {
        status: 'warning' as const,
        summary: "Some points cannot be proven in the current context.",
        metrics: { static_unprovable_count: 1, page_mapping_rate: 0.98 },
        decision_reason: "Some items cannot be proven statically and cannot be treated as passing.",
    },
    verification_state: {
        status: 'context_unprovable' as const,
        label: "Not provable in the current context",
        summary: "Some points cannot be proven directly from the static prototype or current context.",
    },
    recommendations: ["Review incorrect mappings before deciding whether to run visual regression tests."],
    result_summary: { page_mapping_rate: 0.98 },
    logs: [
        { timestamp: '2026-04-02T15:00:02', level: 'info', message: "Start execution", data: {} },
        { timestamp: '2026-04-02T15:00:03', level: 'warn', message: "Found items requiring confirmation", data: {} },
    ],
    execution_group_id: 'task001',
    lineage_root_id: 'chain_1',
    rerun_from_task_id: 'task000',
    execution_center_path: '/history?group=task001',
    quality_gate_path: '/quality-gate?task_id=task001&run_id=task001&focus=history',
    expert_path: '/prototype-agents',
    raw_report: {},
};

describe('TaskResultPage', () => {
    beforeEach(() => {
        mockNavigate.mockReset();
        mockCancelFrontdoorTask.mockReset();
        mockGetFrontdoorTask.mockReset();
        mockListFrontdoorTasks.mockReset();
        mockRerunFrontdoorTask.mockReset();
        mockStreamFrontdoorTask.mockReset();
        mockStreamFrontdoorTask.mockReturnValue(vi.fn());
        useFrontdoorTaskStore.setState({
            draft: {
                taskKind: 'general',
                userGoal: '',
                targetUrl: '',
                sourceType: 'url',
                source: '',
                compareSource: '',
                playbookId: 'sample-platform-prototype',
            },
            tasks: [],
            currentTask: null,
            currentTaskId: null,
            filters: { taskKind: '', status: '' },
            streamConnected: false,
        });
    });

    it('should render unified result sections and static_unprovable warning', async () => {
        mockGetFrontdoorTask.mockResolvedValue(runningTask);
        mockListFrontdoorTasks
            .mockResolvedValueOnce([])
            .mockResolvedValueOnce([
                runningTask,
                {
                    ...runningTask,
                    task_id: 'task000',
                    user_goal: "Previous prototype review",
                    status: 'completed',
                    rerun_from_task_id: '',
                    gate_summary: {
                        ...runningTask.gate_summary,
                        status: 'passed',
                        summary: "The previous run passed.",
                        metrics: {
                            page_mapping_rate: 1,
                            static_unprovable_count: 0,
                        },
                        decision_reason: "The previous run had no blocking issues.",
                    },
                    verification_state: {
                        status: 'verified_passed' as const,
                        label: "Verified",
                        summary: "The previous run passed.",
                    },
                },
            ]);

        render(
            <MemoryRouter initialEntries={['/tasks/task001']}>
                <Routes>
                    <Route path="/tasks/:taskId" element={<TaskResultPage />} />
                </Routes>
            </MemoryRouter>,
        );

        await waitFor(() => {
            expect(screen.getByText("1. Task intent and input context")).toBeInTheDocument();
        });
        expect(screen.getAllByText("Not provable in the current context").length).toBeGreaterThan(0);
        expect(screen.getByText("Page mapping risk")).toBeInTheDocument();
        expect(screen.getByText("5. Gate decision and core metrics")).toBeInTheDocument();
        expect(screen.getAllByText(/Some items cannot be proven statically/).length).toBeGreaterThan(0);
        expect(screen.getByText("Evidence: evi001")).toBeInTheDocument();
        expect(screen.getByText("Location: modules/site-list.html")).toBeInTheDocument();
        expect(screen.getByText("Rerun chain summary")).toBeInTheDocument();
        expect(screen.getByText("Current source: task000")).toBeInTheDocument();
        expect(screen.getByText("Latest rerun comparison")).toBeInTheDocument();
        expect(screen.getByText("Severity changes")).toBeInTheDocument();
        expect(screen.getByText("Key metric changes")).toBeInTheDocument();
        expect(screen.getByText("2 changes")).toBeInTheDocument();
        expect(screen.getAllByText('page_mapping_rate').length).toBeGreaterThan(0);
        expect(screen.getAllByText('static_unprovable_count').length).toBeGreaterThan(0);
        expect(screen.getAllByText(/Current 1 \/ Previous 1/).length).toBeGreaterThan(0);
    });

    it('should call cancel action and show action feedback', async () => {
        mockGetFrontdoorTask.mockResolvedValue(runningTask);
        mockListFrontdoorTasks.mockResolvedValue([]);
        mockCancelFrontdoorTask.mockResolvedValue({
            task_id: 'task001',
            cancelled: false,
            status: 'executing',
            message: "The exploratory task cannot currently be stopped reliably.",
        });

        render(
            <MemoryRouter initialEntries={['/tasks/task001']}>
                <Routes>
                    <Route path="/tasks/:taskId" element={<TaskResultPage />} />
                </Routes>
            </MemoryRouter>,
        );

        await waitFor(() => {
            expect(screen.getByRole('button', { name: "Stop task" })).toBeInTheDocument();
        });
        fireEvent.click(screen.getByRole('button', { name: "Stop task" }));

        await waitFor(() => {
            expect(mockCancelFrontdoorTask).toHaveBeenCalledWith('task001');
        });
    });

    it('should rerun task and navigate to new result page', async () => {
        mockGetFrontdoorTask.mockResolvedValue(runningTask);
        mockListFrontdoorTasks.mockResolvedValue([]);
        mockRerunFrontdoorTask.mockResolvedValue({ ...runningTask, task_id: 'task002', status: 'pending', rerun_from_task_id: 'task001' });

        render(
            <MemoryRouter initialEntries={['/tasks/task001']}>
                <Routes>
                    <Route path="/tasks/:taskId" element={<TaskResultPage />} />
                </Routes>
            </MemoryRouter>,
        );

        await waitFor(() => {
            expect(screen.getByRole('button', { name: "Rerun" })).toBeInTheDocument();
        });
        fireEvent.click(screen.getByRole('button', { name: "Rerun" }));

        await waitFor(() => {
            expect(mockRerunFrontdoorTask).toHaveBeenCalledWith('task001');
        });
        expect(mockNavigate).toHaveBeenCalledWith('/tasks/task002');
    });

    it('should navigate to quality gate with task context', async () => {
        mockGetFrontdoorTask.mockResolvedValue(runningTask);
        mockListFrontdoorTasks.mockResolvedValue([]);

        render(
            <MemoryRouter initialEntries={['/tasks/task001']}>
                <Routes>
                    <Route path="/tasks/:taskId" element={<TaskResultPage />} />
                </Routes>
            </MemoryRouter>,
        );

        await waitFor(() => {
            expect(screen.getByRole('button', { name: "Quality gate" })).toBeInTheDocument();
        });
        fireEvent.click(screen.getByRole('button', { name: "Quality gate" }));

        expect(mockNavigate).toHaveBeenCalledWith('/quality-gate?task_id=task001&run_id=task001&focus=history');
    });
});
