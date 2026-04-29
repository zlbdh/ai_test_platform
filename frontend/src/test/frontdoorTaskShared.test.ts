import { describe, expect, it } from 'vitest';

import {
    buildFrontdoorDeepView,
    buildGateCheckDiff,
    buildMetricComparisonItems,
    buildTaskComparisonSummary,
    resolveExecutionGroupTagSummary,
} from '../pages/frontdoorTaskShared';

const baseTask = {
    task_id: 'task001',
    mission_kind: 'prototype_agents',
    task_kind: 'prototype' as const,
    user_goal: '原型测试',
    status: 'completed',
    created_at: '2026-04-03T10:00:00',
    source_context: {},
    strategy: {},
    agent_states: {},
    evidence_summary: {
        log_count: 2,
        finding_count: 2,
        has_report: true,
        execution_group_id: 'task001',
        evidence_ids: ['evi001'],
        latest_log_at: '2026-04-03T10:00:10',
        static_unprovable_count: 1,
    },
    findings: [
        {
            severity: 'major',
            title: '页面映射风险',
            summary: '映射存在偏差。',
            category: 'mis_mapping',
            agent_id: 'orchestrator',
            evidence_id: 'evi001',
            source_type: 'html',
            locator: 'modules/site-list.html',
        },
        {
            severity: 'normal',
            title: '提示文案缺失',
            summary: '提示文案不够完整。',
            category: 'field_gap',
            agent_id: 'reporter',
            evidence_id: 'evi002',
            source_type: 'html',
            locator: 'modules/order.html',
        },
    ],
    gate_summary: {
        status: 'warning' as const,
        summary: '当前仍有待确认项。',
        metrics: {
            page_mapping_rate: 0.98,
            static_unprovable_count: 1,
        },
        decision_reason: '存在静态无法证明项。',
    },
    verification_state: {
        status: 'context_unprovable' as const,
        label: '当前上下文无法证明',
        summary: '仍有静态无法证明项。',
    },
    recommendations: [],
    result_summary: {},
    logs: [],
    execution_group_id: 'task001',
    lineage_root_id: 'chain_1',
    rerun_from_task_id: '',
    execution_center_path: '/history?group=task001',
    quality_gate_path: '/quality-gate?task_id=task001&run_id=task001',
    expert_path: '/prototype-agents',
    raw_report: {},
};

describe('frontdoorTaskShared', () => {
    it('buildMetricComparisonItems should mark changed and unchanged metrics', () => {
        const items = buildMetricComparisonItems(
            { page_mapping_rate: 0.98, static_unprovable_count: 1 },
            { page_mapping_rate: 1, static_unprovable_count: 1 },
        );

        expect(items).toHaveLength(2);
        expect(items.find((item) => item.key === 'page_mapping_rate')?.changed).toBe(true);
        expect(items.find((item) => item.key === 'static_unprovable_count')?.changed).toBe(false);
    });

    it('buildGateCheckDiff should surface rule-level changes', () => {
        const items = buildGateCheckDiff(
            [
                { rule_name: 'mapping_gate', status: 'warning', message: '页面映射率下降' },
                { rule_name: 'page_gate', status: 'passed', message: '关键页面齐全' },
            ],
            [
                { rule_name: 'mapping_gate', status: 'passed', message: '页面映射率稳定' },
                { rule_name: 'page_gate', status: 'passed', message: '关键页面齐全' },
            ],
        );

        expect(items).toHaveLength(2);
        expect(items.find((item) => item.ruleName === 'mapping_gate')?.changed).toBe(true);
        expect(items.find((item) => item.ruleName === 'page_gate')?.changed).toBe(false);
    });

    it('buildTaskComparisonSummary should aggregate metric and gate changes', () => {
        const summary = buildTaskComparisonSummary(
            baseTask,
            {
                ...baseTask,
                task_id: 'task000',
                evidence_summary: {
                    ...baseTask.evidence_summary,
                    finding_count: 1,
                    execution_group_id: 'task000',
                    static_unprovable_count: 0,
                },
                findings: [baseTask.findings[0]],
                gate_summary: {
                    status: 'passed' as const,
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
                execution_group_id: 'task000',
            },
        );

        expect(summary).not.toBeNull();
        expect(summary?.findingDelta).toBe(1);
        expect(summary?.highRiskDelta).toBe(0);
        expect(summary?.gateChanged).toBe(true);
        expect(summary?.verificationChanged).toBe(true);
        expect(summary?.decisionReasonChanged).toBe(true);
        expect(summary?.changedMetricCount).toBe(2);
    });

    it('buildFrontdoorDeepView should unify lineage, comparable task and same-kind references', () => {
        const currentTask = { ...baseTask };
        const previousTask = {
            ...baseTask,
            task_id: 'task000',
            execution_group_id: 'task000',
            rerun_from_task_id: '',
            created_at: '2026-04-03T09:00:00',
            gate_summary: {
                ...baseTask.gate_summary,
                status: 'passed' as const,
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
            findings: [baseTask.findings[0]],
            evidence_summary: {
                ...baseTask.evidence_summary,
                finding_count: 1,
                execution_group_id: 'task000',
                static_unprovable_count: 0,
            },
        };
        const sameKindReference = {
            ...baseTask,
            task_id: 'task900',
            execution_group_id: 'task900',
            lineage_root_id: 'chain_9',
            rerun_from_task_id: '',
            user_goal: '同类参考任务',
            created_at: '2026-04-03T08:00:00',
        };

        const deepView = buildFrontdoorDeepView({
            currentTask,
            currentTaskId: currentTask.task_id,
            lineageTasks: [currentTask, previousTask],
            sameTaskKindTasks: [currentTask, previousTask, sameKindReference],
            currentGateHistory: {
                run_id: 'task001',
                status: 'warning',
                verdict: {
                    status: 'warning',
                    summary: '当前门禁需确认。',
                    checks: [
                        { rule_name: 'mapping_gate', status: 'warning', message: '页面映射率下降' },
                    ],
                    total_checks: 1,
                    passed_checks: 0,
                    failed_checks: 1,
                },
            },
            comparableGateHistory: {
                run_id: 'task000',
                status: 'passed',
                verdict: {
                    status: 'passed',
                    summary: '上一轮门禁通过。',
                    checks: [
                        { rule_name: 'mapping_gate', status: 'passed', message: '页面映射率稳定' },
                    ],
                    total_checks: 1,
                    passed_checks: 1,
                    failed_checks: 0,
                },
            },
        });

        expect(deepView.lineageContext.comparableTask?.task_id).toBe('task000');
        expect(deepView.comparisonSummary?.gateChanged).toBe(true);
        expect(deepView.sameTaskKindReferences.map((task) => task.task_id)).toEqual(['task900']);
        expect(deepView.currentLineageGroupIds.has('task001')).toBe(true);
        expect(deepView.currentLineageGroupIds.has('task000')).toBe(true);
        expect(deepView.sameTaskKindGroupIds.has('task900')).toBe(true);
        expect(deepView.gateDeepRead.currentHistory?.run_id).toBe('task001');
        expect(deepView.gateDeepRead.comparableHistory?.run_id).toBe('task000');
        expect(deepView.gateDeepRead.changedGateChecks).toHaveLength(1);
        expect(deepView.gateDeepRead.changedGateChecks[0]?.ruleName).toBe('mapping_gate');
    });

    it('resolveExecutionGroupTagSummary should classify group tags consistently', () => {
        const deepView = buildFrontdoorDeepView({
            currentTask: baseTask,
            currentTaskId: baseTask.task_id,
            lineageTasks: [
                baseTask,
                {
                    ...baseTask,
                    task_id: 'task000',
                    execution_group_id: 'task000',
                    rerun_from_task_id: '',
                },
            ],
            sameTaskKindTasks: [
                {
                    ...baseTask,
                    task_id: 'task900',
                    execution_group_id: 'task900',
                    lineage_root_id: 'chain_9',
                    rerun_from_task_id: '',
                },
            ],
        });

        expect(resolveExecutionGroupTagSummary('task001', deepView)).toEqual({
            isCurrentTaskGroup: true,
            isSameLineageGroup: false,
            isSameTaskKindReferenceGroup: false,
        });
        expect(resolveExecutionGroupTagSummary('task000', deepView)).toEqual({
            isCurrentTaskGroup: false,
            isSameLineageGroup: true,
            isSameTaskKindReferenceGroup: false,
        });
        expect(resolveExecutionGroupTagSummary('task900', deepView)).toEqual({
            isCurrentTaskGroup: false,
            isSameLineageGroup: false,
            isSameTaskKindReferenceGroup: true,
        });
    });
});
