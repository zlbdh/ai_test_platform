import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const mockNavigate = vi.fn();
const {
    mockCreateFrontdoorTask,
    mockListFrontdoorTasks,
} = vi.hoisted(() => ({
    mockCreateFrontdoorTask: vi.fn(),
    mockListFrontdoorTasks: vi.fn(),
}));

vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
    return {
        ...actual,
        useNavigate: () => mockNavigate,
    };
});

vi.mock('../services/frontdoorTaskService', () => ({
    createFrontdoorTask: mockCreateFrontdoorTask,
    listFrontdoorTasks: mockListFrontdoorTasks,
}));

import TaskFrontDoorPage from '../pages/TaskFrontDoorPage';
import { useFrontdoorTaskStore } from '../stores';

const baseTask = {
    task_id: 'task001',
    mission_kind: 'commander',
    task_kind: 'general' as const,
    user_goal: '检查登录链路',
    status: 'completed',
    created_at: '2026-04-02T15:00:00',
    started_at: '2026-04-02T15:00:01',
    completed_at: '2026-04-02T15:00:10',
    source_context: { target_url: 'https://demo.example.com' },
    strategy: { parallel: true },
    agent_states: { commander: 'success' },
    evidence_summary: {
        log_count: 1,
        finding_count: 1,
        has_report: true,
        execution_group_id: 'task001',
        summary_keys: ['total_tests'],
    },
    findings: [],
    gate_summary: {
        status: 'failed' as const,
        summary: '通用编排存在失败测试线，建议进入执行中心复核。',
        metrics: { failed: 1, total_tests: 3 },
    },
    recommendations: ['先复核失败测试线，再决定是否需要补专项场景。'],
    result_summary: { total_tests: 3, failed: 1 },
    logs: [],
    execution_group_id: 'task001',
    execution_center_path: '/history?group=task001',
    expert_path: '/orchestrator',
    raw_report: {},
};

describe('TaskFrontDoorPage', () => {
    beforeEach(() => {
        mockNavigate.mockReset();
        mockCreateFrontdoorTask.mockReset();
        mockListFrontdoorTasks.mockReset();
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

    it('should render recent tasks without loading detail panel', async () => {
        mockListFrontdoorTasks.mockResolvedValue([baseTask]);

        render(
            <MemoryRouter>
                <TaskFrontDoorPage />
            </MemoryRouter>,
        );

        await waitFor(() => {
            expect(screen.getByText('最近任务')).toBeInTheDocument();
        });
        expect(screen.getByText('检查登录链路')).toBeInTheDocument();
        expect(screen.getByText('结果页将固定展示')).toBeInTheDocument();
    });

    it('should create a general task and navigate to result page', async () => {
        mockListFrontdoorTasks.mockResolvedValue([]);
        mockCreateFrontdoorTask.mockResolvedValue(baseTask);

        render(
            <MemoryRouter>
                <TaskFrontDoorPage />
            </MemoryRouter>,
        );

        fireEvent.change(screen.getByPlaceholderText('比如：检查登录、下单和支付主链路'), {
            target: { value: '检查登录主链路' },
        });
        fireEvent.change(screen.getByPlaceholderText('https://example.com/path'), {
            target: { value: 'https://demo.example.com/login' },
        });
        fireEvent.click(screen.getByRole('button', { name: '发起任务并进入结果页' }));

        await waitFor(() => {
            expect(mockCreateFrontdoorTask).toHaveBeenCalledWith({
                task_kind: 'general',
                user_goal: '检查登录主链路',
                source_context: { target_url: 'https://demo.example.com/login' },
                strategy: { parallel: true },
            });
        });
        expect(mockNavigate).toHaveBeenCalledWith('/tasks/task001');
    });
});
