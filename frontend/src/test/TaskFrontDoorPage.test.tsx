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
    user_goal: "Check the login flow",
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
        summary: "General orchestration has failed test tracks. Review them in the execution center.",
        metrics: { failed: 1, total_tests: 3 },
    },
    recommendations: ["Review failed test tracks before deciding whether additional specialized scenarios are needed."],
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
            expect(screen.getByText("Recent tasks")).toBeInTheDocument();
        });
        expect(screen.getByText("Check the login flow")).toBeInTheDocument();
        expect(screen.getByText("The results page always includes")).toBeInTheDocument();
    });

    it('should create a general task and navigate to result page', async () => {
        mockListFrontdoorTasks.mockResolvedValue([]);
        mockCreateFrontdoorTask.mockResolvedValue(baseTask);

        render(
            <MemoryRouter>
                <TaskFrontDoorPage />
            </MemoryRouter>,
        );

        fireEvent.change(screen.getByPlaceholderText("Example: Check the login, ordering, and payment workflows"), {
            target: { value: "Check the primary login flow" },
        });
        fireEvent.change(screen.getByPlaceholderText('https://example.com/path'), {
            target: { value: 'https://demo.example.com/login' },
        });
        fireEvent.click(screen.getByRole('button', { name: "Start task and open results" }));

        await waitFor(() => {
            expect(mockCreateFrontdoorTask).toHaveBeenCalledWith({
                task_kind: 'general',
                user_goal: "Check the primary login flow",
                source_context: { target_url: 'https://demo.example.com/login' },
                strategy: { parallel: true },
            });
        });
        expect(mockNavigate).toHaveBeenCalledWith('/tasks/task001');
    });
});
