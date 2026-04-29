import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TestOrchestrator, { resolveTaskDisplayText } from '../components/TestOrchestrator';
import { AIProvider, AgentType, StepStatus } from '../types';
import type { AISettings, TestStep } from '../types';

const {
    mockGenerateTestPlanWithCoverage,
    mockStartExecution,
    mockStopExecution,
    mockCheckBackendHealth,
    mockShowToast,
} = vi.hoisted(() => ({
    mockGenerateTestPlanWithCoverage: vi.fn(),
    mockStartExecution: vi.fn(),
    mockStopExecution: vi.fn(),
    mockCheckBackendHealth: vi.fn(),
    mockShowToast: vi.fn(),
}));

vi.mock('../services/backendService', () => ({
    generateTestPlanWithCoverage: mockGenerateTestPlanWithCoverage,
    startExecution: mockStartExecution,
    stopExecution: mockStopExecution,
    checkBackendHealth: mockCheckBackendHealth,
}));

interface MockPlanPreviewProps {
    testPlan: TestStep[];
    stepStatuses: Map<number, string>;
    onExecute: () => void;
}

interface MockConfigPanelProps {
    setRequirement: (value: string) => void;
    probeMode?: boolean;
    setProbeMode?: (value: boolean) => void;
    onGeneratePlan: () => void;
}

vi.mock('../components/TestConfigPanel', () => ({
    default: ({ setRequirement, probeMode, setProbeMode, onGeneratePlan }: MockConfigPanelProps) => (
        <div>
            <button onClick={() => setRequirement('登录流程测试')}>填写需求</button>
            <button onClick={() => setProbeMode?.(!probeMode)}>切换探针</button>
            <button onClick={onGeneratePlan}>生成计划</button>
        </div>
    ),
}));

vi.mock('../components/PlanPreview', () => ({
    default: ({ testPlan, stepStatuses, onExecute }: MockPlanPreviewProps) => (
        <div>
            <button onClick={onExecute}>执行计划</button>
            <div data-testid="step-statuses">
                {testPlan.map((_, idx) => `${idx}:${stepStatuses.get(idx) || 'pending'}`).join('|')}
            </div>
        </div>
    ),
}));

vi.mock('../components/RemoteBrowserView', () => ({
    default: ({ currentAction }: { currentAction: string }) => <div>{currentAction || 'RemoteBrowserView'}</div>,
}));

vi.mock('../components/AIReasoningPanel', () => ({
    default: () => <div>AIReasoningPanel</div>,
}));

vi.mock('../components/LogTerminal', () => ({
    default: () => <div>LogTerminal</div>,
}));

vi.mock('../components/ui/Toast', () => ({
    useToast: () => ({ showToast: mockShowToast }),
}));

class MockEventSource {
    static instances: MockEventSource[] = [];

    onmessage: ((event: MessageEvent<string>) => void) | null = null;
    onerror: ((event: Event) => void) | null = null;
    readonly url: string;
    close = vi.fn();

    constructor(url: string) {
        this.url = url;
        MockEventSource.instances.push(this);
    }

    emit(payload: unknown) {
        this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent<string>);
    }
}

describe('TestOrchestrator', () => {
    const aiSettings: AISettings = {
        provider: AIProvider.GEMINI,
        apiKey: 'test-key',
        modelName: 'gemini-test',
    };

    const planSteps: TestStep[] = [
        {
            id: 'step-1',
            agent: AgentType.PLANNER,
            description: '登录: 打开页面',
            status: StepStatus.PENDING,
            logs: [],
            action: 'goto',
            target: 'http://example.com',
        },
        {
            id: 'step-2',
            agent: AgentType.PLANNER,
            description: '登录: 点击提交',
            status: StepStatus.PENDING,
            logs: [],
            action: 'click',
            target: '#submit',
        },
    ];

    beforeEach(() => {
        MockEventSource.instances = [];
        mockGenerateTestPlanWithCoverage.mockResolvedValue({ steps: planSteps, coverage_summary: null });
        mockStartExecution.mockResolvedValue({ task_id: 'task-1' });
        mockStopExecution.mockResolvedValue({ status: 'stopped' });
        mockCheckBackendHealth.mockResolvedValue(true);
        vi.stubGlobal('EventSource', MockEventSource as unknown as typeof EventSource);
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ is_running: true, signal: 'RUNNING' }),
        }));
    });

    afterEach(() => {
        vi.clearAllMocks();
        vi.unstubAllGlobals();
    });

    it('tracks step status from structured SSE events', async () => {
        render(
            <TestOrchestrator
                updateAgentStatus={() => { }}
                incrementAgentTasks={() => { }}
                enableVision
                setEnableVision={() => { }}
                useMultiAgent
                setUseMultiAgent={() => { }}
                onShowHistory={() => { }}
                aiSettings={aiSettings}
                sessionId="session-1"
                browserMode="chromium"
            />
        );

        fireEvent.click(screen.getByText('填写需求'));
        fireEvent.click(screen.getByText('生成计划'));

        await waitFor(() => {
            expect(mockGenerateTestPlanWithCoverage).toHaveBeenCalledWith('登录流程测试', '', 'default', 'default');
        });
        expect(screen.getByTestId('step-statuses')).toHaveTextContent('0:pending|1:pending');

        fireEvent.click(screen.getByText('执行计划'));

        await waitFor(() => {
            expect(mockStartExecution).toHaveBeenCalledTimes(1);
            expect(MockEventSource.instances).toHaveLength(1);
        });

        const stream = MockEventSource.instances[0];

        act(() => {
            stream.emit({
                type: 'action',
                event: 'step_start',
                task_id: 'task-1',
                step_index: 0,
                action: 'goto',
                target: 'http://example.com',
                content: '▶ goto(http://example.com)',
            });
        });

        await waitFor(() => {
            expect(screen.getByTestId('step-statuses')).toHaveTextContent('0:running|1:pending');
        });

        act(() => {
            stream.emit({
                type: 'result',
                event: 'step_result',
                task_id: 'task-1',
                status: 'success',
                content: '✅ success (0.3s)',
            });
        });

        await waitFor(() => {
            expect(screen.getByTestId('step-statuses')).toHaveTextContent('0:success|1:pending');
        });

        act(() => {
            stream.emit({
                type: 'action',
                event: 'step_start',
                task_id: 'task-2',
                action: 'click',
                target: '#submit',
                content: '▶ click(#submit)',
            });
        });

        await waitFor(() => {
            expect(screen.getByTestId('step-statuses')).toHaveTextContent('0:success|1:running');
        });

        act(() => {
            stream.emit({
                type: 'result',
                event: 'step_result',
                task_id: 'task-2',
                status: 'error',
                content: '❌ error (0.5s)',
            });
        });

        await waitFor(() => {
            expect(screen.getByTestId('step-statuses')).toHaveTextContent('0:success|1:error');
        });
    });

    it('prefers task_display helper when backend returns display title', () => {
        expect(resolveTaskDisplayText('??????? Wave0 ???????', 'https://example.com/login'))
            .toBe('https://example.com/login');
        expect(resolveTaskDisplayText('正常中文任务', ''))
            .toBe('正常中文任务');
        expect(resolveTaskDisplayText('', ''))
            .toBe('');
    });

    it('passes probe execution flags when readonly probe is enabled', async () => {
        render(
            <TestOrchestrator
                updateAgentStatus={() => { }}
                incrementAgentTasks={() => { }}
                enableVision
                setEnableVision={() => { }}
                useMultiAgent
                setUseMultiAgent={() => { }}
                onShowHistory={() => { }}
                aiSettings={aiSettings}
                sessionId="session-1"
                browserMode="chromium"
            />
        );

        fireEvent.click(screen.getByText('填写需求'));
        fireEvent.click(screen.getByText('切换探针'));
        fireEvent.click(screen.getByText('生成计划'));

        await waitFor(() => {
            expect(mockGenerateTestPlanWithCoverage).toHaveBeenCalledWith('登录流程测试', '', 'probe', 'read_only');
        });

        fireEvent.click(screen.getByText('执行计划'));

        await waitFor(() => {
            expect(mockStartExecution).toHaveBeenCalledWith(
                expect.stringContaining('登录流程测试'),
                true,
                true,
                '',
                'session-1',
                'chromium',
                expect.any(String),
                'probe',
                'read_only',
            );
        });

        expect(screen.getByText('当前执行模式：')).toBeInTheDocument();
        expect(screen.getByText('只读探针')).toBeInTheDocument();
    });
});
