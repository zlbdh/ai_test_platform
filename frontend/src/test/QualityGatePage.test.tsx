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
                            playbook_title: "Sample enterprise platform initial live regression",
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
                                { name: 'sample_platform_login_success_gate', description: "Login", metric: 'login_success_rate', operator: '>=', threshold: 1, severity: 'blocking', enabled: true },
                                { name: 'sample_platform_core_flow_pass_gate', description: "Core workflow", metric: 'core_flow_pass_rate', operator: '>=', threshold: 0.95, severity: 'blocking', enabled: true },
                                { name: 'sample_platform_blocking_bug_gate', description: "Blocking defect", metric: 'blocking_bug_count', operator: '<=', threshold: 0, severity: 'blocking', enabled: true },
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
                                summary: "✅ All quality gates passed",
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
        fireEvent.click(screen.getByRole('button', { name: "Import sample project rules" }));

        await waitFor(() => expect(screen.getByText("Sample enterprise platform initial live regression")).toBeInTheDocument());
        expect(screen.getByText("Imported 5 rules")).toBeInTheDocument();
        expect(screen.getByText('sample_platform_login_success_gate')).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: "Run checks" }));

        await waitFor(() => expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/api/quality-gate/check'),
            expect.objectContaining({ method: 'POST' }),
        ));

        expect(await screen.findByText("✅ All quality gates passed")).toBeInTheDocument();
        expect(screen.getByText("Passed: 1/1 | Failed: 0")).toBeInTheDocument();
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
                            playbook_title: "Sample project platform prototype test package",
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
                                { name: 'sample_platform_platform_module_coverage_gate', description: "Module coverage", metric: 'module_coverage_rate', operator: '>=', threshold: 1, severity: 'blocking', enabled: true },
                                { name: 'sample_platform_platform_page_mapping_gate', description: "Page mapping rate", metric: 'page_mapping_rate', operator: '>=', threshold: 0.95, severity: 'blocking', enabled: true },
                                { name: 'sample_platform_platform_critical_page_gate', description: "Critical pages", metric: 'critical_page_missing_count', operator: '<=', threshold: 0, severity: 'blocking', enabled: true },
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
        fireEvent.click(screen.getByRole('button', { name: "Import platform prototype rules" }));

        await waitFor(() => expect(screen.getByText("Sample project platform prototype test package")).toBeInTheDocument());
        expect(screen.getByText("Imported 6 rules")).toBeInTheDocument();
        expect(screen.getByText("Rules cover module coverage, page mapping, missing critical pages, blocking prototype differences, missing critical fields, and missing critical state transitions.")).toBeInTheDocument();
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
                                { name: 'prototype_mapping_gate', description: "Page mapping rate", metric: 'page_mapping_rate', operator: '>=', threshold: 0.95, severity: 'blocking', enabled: true },
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
                                summary: "Task context gate",
                                checks: [
                                    {
                                        rule_name: 'prototype_mapping_gate',
                                        status: 'warning',
                                        actual_value: 0.98,
                                        threshold: 0.95,
                                        message: "Page mapping rate decreased",
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
                                    summary: "The previous gate passed.",
                                    checks: [
                                        {
                                            rule_name: 'prototype_mapping_gate',
                                            status: 'passed',
                                            actual_value: 1,
                                            threshold: 0.95,
                                            message: "Page mapping rate stable",
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
                                summary: "Task context gate",
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
                                summary: "Other task gate",
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
            user_goal: "Review quality gates for the order prototype",
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
                summary: "Some items still require confirmation.",
                metrics: { page_mapping_rate: 0.98, static_unprovable_count: 1 },
                decision_reason: "Some items cannot be proven statically.",
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
                user_goal: "Review quality gates for the order prototype",
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
                    summary: "Some items still require confirmation.",
                    metrics: { page_mapping_rate: 0.98, static_unprovable_count: 1 },
                    decision_reason: "Some items cannot be proven statically.",
                },
                verification_state: {
                    status: 'context_unprovable',
                    label: "Not provable in the current context",
                    summary: "Some items still require confirmation.",
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
                user_goal: "Previous prototype gate review",
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
                    summary: "The previous gate passed.",
                    metrics: { page_mapping_rate: 1 },
                    decision_reason: "The previous run had no blocking issues.",
                },
                verification_state: {
                    status: 'verified_passed',
                    label: "Verified",
                    summary: "The previous run passed.",
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

        await waitFor(() => expect(screen.getByText("From unified testing task")).toBeInTheDocument());
        expect(screen.getByText("Review quality gates for the order prototype")).toBeInTheDocument();
        expect(screen.getByText("Focused on gate history for run_id = task001 , with task metrics loaded into Business metrics input.")).toBeInTheDocument();
        expect(screen.getByText("Most recent comparable rerun")).toBeInTheDocument();
        expect(screen.getByText("Current run vs. most recent rerun")).toBeInTheDocument();
        expect(screen.getByText("Decision reason: Some items cannot be proven statically.")).toBeInTheDocument();
        expect(screen.getByText("Previous: The previous run had no blocking issues.")).toBeInTheDocument();
        expect(screen.getByText("Key metric changes")).toBeInTheDocument();
        expect(screen.getByText("Check changes")).toBeInTheDocument();
        await screen.findByText("1 rule change");
        await screen.findByText('prototype_mapping_gate');
        expect(screen.getAllByText("Task: task000").length).toBeGreaterThan(0);
        expect(screen.getByText('task001')).toBeInTheDocument();
        expect(screen.queryByText('task999')).not.toBeInTheDocument();
        expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/api/quality-gate/history?limit=20&run_id=task001'),
        );
    });
});
