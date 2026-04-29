import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const mockFetch = vi.fn();
global.fetch = mockFetch;

const { mockGetFrontdoorTask, mockListFrontdoorTasks } = vi.hoisted(() => ({
    mockGetFrontdoorTask: vi.fn(),
    mockListFrontdoorTasks: vi.fn(),
}));

vi.mock('../services/frontdoorTaskService', () => ({
    getFrontdoorTask: mockGetFrontdoorTask,
    listFrontdoorTasks: mockListFrontdoorTasks,
}));

import ExecutionHistory from '../components/ExecutionHistory';

describe('ExecutionHistory task context', () => {
    beforeEach(() => {
        mockFetch.mockReset();
        mockGetFrontdoorTask.mockReset();
        mockListFrontdoorTasks.mockReset();
    });

    it('should keep task and lineage context when opened from unified result page', async () => {
        mockFetch.mockImplementation(async (input: RequestInfo | URL) => {
            const url = String(input);
            if (url.includes('/api/history?view=groups&limit=200')) {
                return {
                    ok: true,
                    json: vi.fn().mockResolvedValue({
                        items: [
                            {
                                group_id: 'task001',
                                title: '订单原型检查批次',
                                requirement: '对订单原型做统一核查',
                                requirement_display: '对订单原型做统一核查',
                                status: 'failed',
                                target_url: 'https://demo.example.com/order',
                                mode: 'commander',
                                created_at: '2026-04-02 15:00:00',
                                updated_at: '2026-04-02 15:00:10',
                                record_count: 1,
                                log_count: 2,
                                error_count: 1,
                                duration_ms: 1200,
                                root_task_id: 'task001',
                                records: [
                                    {
                                        task_id: 'task001',
                                        requirement: '对订单原型做统一核查',
                                        requirement_display: '对订单原型做统一核查',
                                        status: 'failed',
                                        log_count: 2,
                                        error_count: 1,
                                        duration_ms: 1200,
                                        target_url: 'https://demo.example.com/order',
                                        mode: 'commander',
                                        created_at: '2026-04-02 15:00:00',
                                        execution_group_id: 'task001',
                                        record_kind: 'root',
                                    },
                                ],
                            },
                        ],
                    }),
                } as unknown as Response;
            }
            if (url.includes('/api/report/history?limit=200')) {
                return {
                    ok: true,
                    json: vi.fn().mockResolvedValue({ history: [] }),
                } as unknown as Response;
            }
            throw new Error(`Unhandled fetch: ${url}`);
        });

        mockGetFrontdoorTask.mockResolvedValue({
            task_id: 'task001',
            mission_kind: 'prototype_agents',
            task_kind: 'prototype',
            user_goal: '对订单原型做统一核查',
            status: 'completed',
            created_at: '2026-04-02T15:00:00',
            started_at: '2026-04-02T15:00:01',
            completed_at: '2026-04-02T15:00:10',
            source_context: {},
            strategy: {},
            agent_states: {},
            evidence_summary: {
                log_count: 2,
                finding_count: 1,
                has_report: true,
                execution_group_id: 'task001',
            },
            findings: [],
            gate_summary: {
                status: 'warning',
                summary: '仍有待确认项。',
                metrics: { static_unprovable_count: 1 },
            },
            verification_state: {
                status: 'context_unprovable',
                label: '当前上下文无法证明',
                summary: '仍有待确认项。',
            },
            recommendations: [],
            result_summary: {},
            logs: [],
            execution_group_id: 'task001',
            lineage_root_id: 'chain_1',
            rerun_from_task_id: 'task000',
            execution_center_path: '/history?group=task001&record=task001&task_id=task001&lineage_root_id=chain_1',
            quality_gate_path: '/quality-gate?task_id=task001&run_id=task001&focus=history',
            expert_path: '/prototype-agents',
            raw_report: {},
        });

        mockListFrontdoorTasks.mockImplementation(async (filters?: { lineageRootId?: string; taskKind?: string }) => {
            if (filters?.lineageRootId === 'chain_1') {
                return [
                    {
                        task_id: 'task001',
                        mission_kind: 'prototype_agents',
                        task_kind: 'prototype',
                        user_goal: '对订单原型做统一核查',
                        status: 'completed',
                        created_at: '2026-04-02T15:00:00',
                        started_at: '2026-04-02T15:00:01',
                        completed_at: '2026-04-02T15:00:10',
                        source_context: {},
                        strategy: {},
                        agent_states: {},
                        evidence_summary: {
                            log_count: 2,
                            finding_count: 1,
                            has_report: true,
                            execution_group_id: 'task001',
                        },
                        findings: [],
                        gate_summary: {
                            status: 'warning',
                            summary: '仍有待确认项。',
                            metrics: { static_unprovable_count: 1 },
                        },
                        verification_state: {
                            status: 'context_unprovable',
                            label: '当前上下文无法证明',
                            summary: '仍有待确认项。',
                        },
                        recommendations: [],
                        result_summary: {},
                        logs: [],
                        execution_group_id: 'task001',
                        lineage_root_id: 'chain_1',
                        rerun_from_task_id: 'task000',
                        execution_center_path: '/history?group=task001&record=task001&task_id=task001&lineage_root_id=chain_1',
                        quality_gate_path: '/quality-gate?task_id=task001&run_id=task001&focus=history',
                        expert_path: '/prototype-agents',
                        raw_report: {},
                    },
                    {
                        task_id: 'task000',
                        mission_kind: 'prototype_agents',
                        task_kind: 'prototype',
                        user_goal: '上一轮原型核查',
                        status: 'completed',
                        created_at: '2026-04-02T14:00:00',
                        started_at: '2026-04-02T14:00:01',
                        completed_at: '2026-04-02T14:00:08',
                        source_context: {},
                        strategy: {},
                        agent_states: {},
                        evidence_summary: {
                            log_count: 1,
                            finding_count: 0,
                            has_report: true,
                            execution_group_id: 'task000',
                        },
                        findings: [],
                        gate_summary: {
                            status: 'passed',
                            summary: '上一轮已通过。',
                            metrics: {},
                        },
                        verification_state: {
                            status: 'verified_passed',
                            label: '已验证通过',
                            summary: '上一轮已通过。',
                        },
                        recommendations: [],
                        result_summary: {},
                        logs: [],
                        execution_group_id: 'task000',
                        lineage_root_id: 'chain_1',
                        rerun_from_task_id: '',
                        execution_center_path: '/history?group=task000&record=task000&task_id=task000&lineage_root_id=chain_1',
                        quality_gate_path: '/quality-gate?task_id=task000&run_id=task000&focus=history',
                        expert_path: '/prototype-agents',
                        raw_report: {},
                    },
                ];
            }
            return [
                {
                    task_id: 'task900',
                    mission_kind: 'prototype_agents',
                    task_kind: 'prototype',
                    user_goal: '同类型参考任务',
                    status: 'completed',
                    created_at: '2026-04-02T13:00:00',
                    started_at: '2026-04-02T13:00:01',
                    completed_at: '2026-04-02T13:00:08',
                    source_context: {},
                    strategy: {},
                    agent_states: {},
                    evidence_summary: {
                        log_count: 1,
                        finding_count: 0,
                        has_report: true,
                        execution_group_id: 'task900',
                    },
                    findings: [],
                    gate_summary: {
                        status: 'passed',
                        summary: '参考任务已通过。',
                        metrics: {},
                    },
                    verification_state: {
                        status: 'verified_passed',
                        label: '已验证通过',
                        summary: '参考任务已通过。',
                    },
                    recommendations: [],
                    result_summary: {},
                    logs: [],
                    execution_group_id: 'task900',
                    lineage_root_id: 'chain_9',
                    rerun_from_task_id: '',
                    execution_center_path: '/history?group=task900&record=task900&task_id=task900&lineage_root_id=chain_9',
                    quality_gate_path: '/quality-gate?task_id=task900&run_id=task900&focus=history',
                    expert_path: '/prototype-agents',
                    raw_report: {},
                },
            ];
        });

        render(
            <MemoryRouter initialEntries={['/history?group=task001&task_id=task001&lineage_root_id=chain_1']}>
                <ExecutionHistory />
            </MemoryRouter>,
        );

        await waitFor(() => expect(screen.getByText('当前任务上下文')).toBeInTheDocument());
        expect(screen.getAllByText('对订单原型做统一核查').length).toBeGreaterThan(0);
        expect(screen.getByText('复跑链摘要')).toBeInTheDocument();
        expect(screen.getByText('链路时间线')).toBeInTheDocument();
        expect(screen.getByText('最近一次可比任务：task000')).toBeInTheDocument();
        expect(screen.getByText('同任务类型参考')).toBeInTheDocument();
        expect(screen.getByText('同类型参考任务')).toBeInTheDocument();
        expect(screen.getByText('当前任务执行组')).toBeInTheDocument();
        expect(screen.getByText('第 2 次')).toBeInTheDocument();
    });
});
