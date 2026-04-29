import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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

import QualityGatePage from '../pages/QualityGatePage';

describe('QualityGatePage', () => {
    beforeEach(() => {
        mockFetch.mockReset();
        mockGetFrontdoorTask.mockReset();
        mockListFrontdoorTasks.mockReset();
    });

    it('should import sample_platform rules and run quality gate check', async () => {
        let imported = false;

        mockFetch.mockImplementation(async (input: RequestInfo | URL) => {
            const url = String(input);

            if (url.includes('/api/quality-gate/rules/import/sample-first-regression')) {
                imported = true;
                return {
                    ok: true,
                    json: vi.fn().mockResolvedValue({
                        status: 'ok',
                        data: {
                            playbook_id: 'sample-first-regression',
                            playbook_title: '示例项目企业平台端首轮真实回归',
                            imported_count: 5,
                        },
                    }),
                } as unknown as Response;
            }

            if (url.includes('/api/quality-gate/rules')) {
                return {
                    ok: true,
                    json: vi.fn().mockResolvedValue({
                        status: 'ok',
                        data: {
                            rules: imported ? [
                                { name: 'sample_platform_login_success_gate', description: '登录', metric: 'login_success_rate', operator: '>=', threshold: 1, severity: 'blocking', enabled: true },
                                { name: 'sample_platform_core_flow_pass_gate', description: '核心流程', metric: 'core_flow_pass_rate', operator: '>=', threshold: 0.95, severity: 'blocking', enabled: true },
                                { name: 'sample_platform_blocking_bug_gate', description: '阻断缺陷', metric: 'blocking_bug_count', operator: '<=', threshold: 0, severity: 'blocking', enabled: true },
                                { name: 'sample_platform_unexplained_5xx_gate', description: '5xx', metric: 'unexplained_5xx_count', operator: '<=', threshold: 0, severity: 'blocking', enabled: true },
                                { name: 'sample_platform_critical_ui_error_gate', description: 'UI', metric: 'critical_ui_error_count', operator: '<=', threshold: 0, severity: 'blocking', enabled: true },
                            ] : [],
                        },
                    }),
                } as unknown as Response;
            }

            if (url.includes('/api/quality-gate/history')) {
                return {
                    ok: true,
                    json: vi.fn().mockResolvedValue({
                        status: 'ok',
                        data: { history: [] },
                    }),
                } as unknown as Response;
            }

            if (url.includes('/api/quality-gate/check')) {
                return {
                    ok: true,
                    json: vi.fn().mockResolvedValue({
                        status: 'ok',
                        data: {
                            verdict: {
                                status: 'passed',
                                summary: '✅ 质量门禁全部通过',
                                checks: [
                                    {
                                        rule_name: 'sample_platform_login_success_gate',
                                        status: 'passed',
                                        actual_value: 1,
                                        threshold: 1,
                                        message: 'login_success_rate = 1.000 >= 1 ✅',
                                    },
                                ],
                                total_checks: 1,
                                passed_checks: 1,
                                failed_checks: 0,
                            },
                        },
                    }),
                } as unknown as Response;
            }

            throw new Error(`Unhandled fetch: ${url}`);
        });

        render(
            <MemoryRouter>
                <QualityGatePage />
            </MemoryRouter>,
        );

        await waitFor(() => expect(mockFetch).toHaveBeenCalled());
        fireEvent.click(screen.getByRole('button', { name: '导入示例项目规则' }));

        await waitFor(() => expect(screen.getByText('示例项目企业平台端首轮真实回归')).toBeInTheDocument());
        expect(screen.getByText('已导入 5 条规则')).toBeInTheDocument();
        expect(screen.getByText('sample_platform_login_success_gate')).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: '执行检查' }));

        await waitFor(() => expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/api/quality-gate/check'),
            expect.objectContaining({ method: 'POST' }),
        ));

        expect(await screen.findByText('✅ 质量门禁全部通过')).toBeInTheDocument();
        expect(screen.getByText('通过: 1/1 | 失败: 0')).toBeInTheDocument();
    });

    it('should import sample_platform platform prototype rules', async () => {
        let imported = false;

        mockFetch.mockImplementation(async (input: RequestInfo | URL) => {
            const url = String(input);

            if (url.includes('/api/quality-gate/rules/import/sample-platform-prototype')) {
                imported = true;
                return {
                    ok: true,
                    json: vi.fn().mockResolvedValue({
                        status: 'ok',
                        data: {
                            playbook_id: 'sample-platform-prototype',
                            playbook_title: '示例项目大平台原型测试包',
                            imported_count: 6,
                        },
                    }),
                } as unknown as Response;
            }

            if (url.includes('/api/quality-gate/rules')) {
                return {
                    ok: true,
                    json: vi.fn().mockResolvedValue({
                        status: 'ok',
                        data: {
                            rules: imported ? [
                                { name: 'sample_platform_platform_module_coverage_gate', description: '模块覆盖率', metric: 'module_coverage_rate', operator: '>=', threshold: 1, severity: 'blocking', enabled: true },
                                { name: 'sample_platform_platform_page_mapping_gate', description: '页面映射率', metric: 'page_mapping_rate', operator: '>=', threshold: 0.95, severity: 'blocking', enabled: true },
                                { name: 'sample_platform_platform_critical_page_gate', description: '关键页面', metric: 'critical_page_missing_count', operator: '<=', threshold: 0, severity: 'blocking', enabled: true },
                            ] : [],
                        },
                    }),
                } as unknown as Response;
            }

            if (url.includes('/api/quality-gate/history')) {
                return {
                    ok: true,
                    json: vi.fn().mockResolvedValue({
                        status: 'ok',
                        data: { history: [] },
                    }),
                } as unknown as Response;
            }

            throw new Error(`Unhandled fetch: ${url}`);
        });

        render(
            <MemoryRouter>
                <QualityGatePage />
            </MemoryRouter>,
        );

        await waitFor(() => expect(mockFetch).toHaveBeenCalled());
        fireEvent.click(screen.getByRole('button', { name: '导入大平台原型规则' }));

        await waitFor(() => expect(screen.getByText('示例项目大平台原型测试包')).toBeInTheDocument());
        expect(screen.getByText('已导入 6 条规则')).toBeInTheDocument();
        expect(screen.getByText('规则覆盖模块覆盖率、页面映射率、关键页面缺失、阻断级原型差异、关键字段缺失和关键状态流转缺失。')).toBeInTheDocument();
        expect(screen.getByText('sample_platform_platform_module_coverage_gate')).toBeInTheDocument();
    });

    it('should focus quality gate history when opened from unified task context', async () => {
        mockFetch.mockImplementation(async (input: RequestInfo | URL) => {
            const url = String(input);

            if (url.includes('/api/quality-gate/rules')) {
                return {
                    ok: true,
                    json: vi.fn().mockResolvedValue({
                        status: 'ok',
                        data: {
                            rules: [
                                { name: 'prototype_mapping_gate', description: '页面映射率', metric: 'page_mapping_rate', operator: '>=', threshold: 0.95, severity: 'blocking', enabled: true },
                            ],
                        },
                    }),
                } as unknown as Response;
            }

            if (url.includes('/api/quality-gate/history')) {
                const filteredHistory = url.includes('run_id=task001')
                    ? [
                        {
                            run_id: 'task001',
                            status: 'warning',
                            verdict: {
                                status: 'warning',
                                summary: '任务上下文门禁',
                                checks: [
                                    {
                                        rule_name: 'prototype_mapping_gate',
                                        status: 'warning',
                                        actual_value: 0.98,
                                        threshold: 0.95,
                                        message: '页面映射率下降',
                                    },
                                ],
                                total_checks: 1,
                                passed_checks: 0,
                                failed_checks: 1,
                            },
                            timestamp: 1712040000,
                        },
                    ]
                    : url.includes('run_id=task000')
                        ? [
                            {
                                run_id: 'task000',
                                status: 'passed',
                                verdict: {
                                    status: 'passed',
                                    summary: '上一轮门禁已通过。',
                                    checks: [
                                        {
                                            rule_name: 'prototype_mapping_gate',
                                            status: 'passed',
                                            actual_value: 1,
                                            threshold: 0.95,
                                            message: '页面映射率稳定',
                                        },
                                    ],
                                    total_checks: 1,
                                    passed_checks: 1,
                                    failed_checks: 0,
                                },
                                timestamp: 1712039900,
                            },
                        ]
                    : [
                        {
                            run_id: 'task001',
                            status: 'warning',
                            verdict: {
                                status: 'warning',
                                summary: '任务上下文门禁',
                                checks: [],
                                total_checks: 0,
                                passed_checks: 0,
                                failed_checks: 0,
                            },
                            timestamp: 1712040000,
                        },
                        {
                            run_id: 'task999',
                            status: 'passed',
                            verdict: {
                                status: 'passed',
                                summary: '其他任务门禁',
                                checks: [],
                                total_checks: 0,
                                passed_checks: 0,
                                failed_checks: 0,
                            },
                            timestamp: 1712040100,
                        },
                    ];
                return {
                    ok: true,
                    json: vi.fn().mockResolvedValue({
                        status: 'ok',
                        data: {
                            history: filteredHistory,
                        },
                    }),
                } as unknown as Response;
            }

            throw new Error(`Unhandled fetch: ${url}`);
        });

        mockGetFrontdoorTask.mockResolvedValue({
            task_id: 'task001',
            mission_kind: 'prototype_agents',
            task_kind: 'prototype',
            user_goal: '对订单原型执行门禁复核',
            status: 'completed',
            source_context: {},
            strategy: {},
            agent_states: {},
            evidence_summary: {
                log_count: 1,
                finding_count: 0,
                has_report: true,
                execution_group_id: 'task001',
            },
            findings: [],
            gate_summary: {
                status: 'warning',
                summary: '仍有待确认项。',
                metrics: { page_mapping_rate: 0.98, static_unprovable_count: 1 },
                decision_reason: '存在静态无法证明项。',
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
        mockListFrontdoorTasks.mockResolvedValue([
            {
                task_id: 'task001',
                mission_kind: 'prototype_agents',
                task_kind: 'prototype',
                user_goal: '对订单原型执行门禁复核',
                status: 'completed',
                source_context: {},
                strategy: {},
                agent_states: {},
                evidence_summary: {
                    log_count: 1,
                    finding_count: 0,
                    has_report: true,
                    execution_group_id: 'task001',
                },
                findings: [],
                gate_summary: {
                    status: 'warning',
                    summary: '仍有待确认项。',
                    metrics: { page_mapping_rate: 0.98, static_unprovable_count: 1 },
                    decision_reason: '存在静态无法证明项。',
                },
                verification_state: {
                    status: 'context_unprovable',
                    label: '当前上下文无法证明',
                    summary: '当前仍有待确认项。',
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
                user_goal: '上一轮原型门禁复核',
                status: 'completed',
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
                    summary: '上一轮门禁已通过。',
                    metrics: { page_mapping_rate: 1 },
                    decision_reason: '上一轮无阻断问题。',
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
        ]);

        render(
            <MemoryRouter initialEntries={['/quality-gate?task_id=task001&run_id=task001&focus=history']}>
                <QualityGatePage />
            </MemoryRouter>,
        );

        await waitFor(() => expect(screen.getByText('来自统一测试任务')).toBeInTheDocument());
        expect(screen.getByText('对订单原型执行门禁复核')).toBeInTheDocument();
        expect(screen.getByText('当前已聚焦 run_id = task001 的门禁历史，并把任务指标带入“业务指标录入”区域。')).toBeInTheDocument();
        expect(screen.getByText('最近一次可比复跑')).toBeInTheDocument();
        expect(screen.getByText('本次 vs 最近一次复跑')).toBeInTheDocument();
        expect(screen.getByText('判定原因：存在静态无法证明项。')).toBeInTheDocument();
        expect(screen.getByText('上次：上一轮无阻断问题。')).toBeInTheDocument();
        expect(screen.getByText('关键 Metrics 变化')).toBeInTheDocument();
        expect(screen.getByText('Checks 变化')).toBeInTheDocument();
        await screen.findByText('1 条规则变化');
        await screen.findByText('prototype_mapping_gate');
        expect(screen.getAllByText('任务：task000').length).toBeGreaterThan(0);
        expect(screen.getByText('task001')).toBeInTheDocument();
        expect(screen.queryByText('task999')).not.toBeInTheDocument();
        expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/api/quality-gate/history?limit=20&run_id=task001'),
        );
    });
});
