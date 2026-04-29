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
    user_goal: '对订单原型做统一核查',
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
            title: '页面映射存在风险',
            summary: '代购管理列表未正确承接。',
            category: 'mis_mapping',
            agent_id: 'orchestrator',
            source_type: 'html',
            locator: 'modules/site-list.html',
        },
    ],
    gate_summary: {
        status: 'warning' as const,
        summary: '当前仍有上下文无法证明的点。',
        metrics: { static_unprovable_count: 1, page_mapping_rate: 0.98 },
        decision_reason: '存在静态无法证明项，不能直接视为通过。',
    },
    verification_state: {
        status: 'context_unprovable' as const,
        label: '当前上下文无法证明',
        summary: '当前任务仍有静态原型或上下文无法直接证明的点。',
    },
    recommendations: ['先复核误映射项，再决定是否进入视觉回归。'],
    result_summary: { page_mapping_rate: 0.98 },
    logs: [
        { timestamp: '2026-04-02T15:00:02', level: 'info', message: '开始执行', data: {} },
        { timestamp: '2026-04-02T15:00:03', level: 'warn', message: '发现待确认项', data: {} },
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
                    user_goal: '上一次原型核查',
                    status: 'completed',
                    rerun_from_task_id: '',
                    gate_summary: {
                        ...runningTask.gate_summary,
                        status: 'passed',
                        summary: '上一轮已通过。',
                        metrics: {
                            page_mapping_rate: 1,
                            static_unprovable_count: 0,
                        },
                        decision_reason: '上一轮无阻断问题。',
                    },
                    verification_state: {
                        status: 'verified_passed' as const,
                        label: '已验证通过',
                        summary: '上一轮已通过。',
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
            expect(screen.getByText('1. 任务意图与输入上下文')).toBeInTheDocument();
        });
        expect(screen.getAllByText('当前上下文无法证明').length).toBeGreaterThan(0);
        expect(screen.getByText('页面映射存在风险')).toBeInTheDocument();
        expect(screen.getByText('5. Gate 结论与核心指标')).toBeInTheDocument();
        expect(screen.getAllByText(/存在静态无法证明项/).length).toBeGreaterThan(0);
        expect(screen.getByText('证据：evi001')).toBeInTheDocument();
        expect(screen.getByText('定位：modules/site-list.html')).toBeInTheDocument();
        expect(screen.getByText('复跑链摘要')).toBeInTheDocument();
        expect(screen.getByText('当前来源：task000')).toBeInTheDocument();
        expect(screen.getByText('最近复跑对比')).toBeInTheDocument();
        expect(screen.getByText('严重级别变化')).toBeInTheDocument();
        expect(screen.getByText('关键 Metrics 变化')).toBeInTheDocument();
        expect(screen.getByText('2 项变化')).toBeInTheDocument();
        expect(screen.getAllByText('page_mapping_rate').length).toBeGreaterThan(0);
        expect(screen.getAllByText('static_unprovable_count').length).toBeGreaterThan(0);
        expect(screen.getAllByText(/本次 1 \/ 上次 1/).length).toBeGreaterThan(0);
    });

    it('should call cancel action and show action feedback', async () => {
        mockGetFrontdoorTask.mockResolvedValue(runningTask);
        mockListFrontdoorTasks.mockResolvedValue([]);
        mockCancelFrontdoorTask.mockResolvedValue({
            task_id: 'task001',
            cancelled: false,
            status: 'executing',
            message: '探索任务当前无法可靠停止。',
        });

        render(
            <MemoryRouter initialEntries={['/tasks/task001']}>
                <Routes>
                    <Route path="/tasks/:taskId" element={<TaskResultPage />} />
                </Routes>
            </MemoryRouter>,
        );

        await waitFor(() => {
            expect(screen.getByRole('button', { name: '停止任务' })).toBeInTheDocument();
        });
        fireEvent.click(screen.getByRole('button', { name: '停止任务' }));

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
            expect(screen.getByRole('button', { name: '重新运行' })).toBeInTheDocument();
        });
        fireEvent.click(screen.getByRole('button', { name: '重新运行' }));

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
            expect(screen.getByRole('button', { name: '质量门禁' })).toBeInTheDocument();
        });
        fireEvent.click(screen.getByRole('button', { name: '质量门禁' }));

        expect(mockNavigate).toHaveBeenCalledWith('/quality-gate?task_id=task001&run_id=task001&focus=history');
    });
});
