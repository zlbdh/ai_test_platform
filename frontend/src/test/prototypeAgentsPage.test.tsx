import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

const {
    mockCommanderCancel,
    mockCommanderPrototypeMissions,
    mockCommanderPrototypeRun,
    mockCommanderPrototypeStatus,
    mockCommanderPrototypeStream,
} = vi.hoisted(() => ({
    mockCommanderCancel: vi.fn(),
    mockCommanderPrototypeMissions: vi.fn(),
    mockCommanderPrototypeRun: vi.fn(),
    mockCommanderPrototypeStatus: vi.fn(),
    mockCommanderPrototypeStream: vi.fn(),
}));

vi.mock('../services/commanderService', () => ({
    commanderCancel: mockCommanderCancel,
    commanderPrototypeMissions: mockCommanderPrototypeMissions,
    commanderPrototypeRun: mockCommanderPrototypeRun,
    commanderPrototypeStatus: mockCommanderPrototypeStatus,
    commanderPrototypeStream: mockCommanderPrototypeStream,
}));

import PrototypeAgentsPage, { buildSeveritySummary, getPrototypeAgentNodes } from '../pages/PrototypeAgentsPage';

const baseMission = {
    mission_id: 'proto001',
    mission_kind: 'prototype_agents',
    user_input: '原型测试 · https://demo.example.com/prototype',
    target_url: 'https://demo.example.com/prototype',
    status: 'completed',
    created_at: '2026-03-31T10:00:00',
    started_at: '2026-03-31T10:00:01',
    completed_at: '2026-03-31T10:00:12',
    strategy: null,
    test_tasks_count: 5,
    test_results_count: 5,
    trace_id: null,
    execution_group_id: 'proto001',
    execution_center_path: '/history?group=proto001',
    bug_summary: [],
    source_type: 'url',
    source: 'https://demo.example.com/prototype',
    compare_source: '',
    playbook_id: 'sample-platform-prototype',
    worker_switches: {
        visual: true,
        flow: true,
        ab: true,
        a11y: true,
        perf: true,
    },
    providers: {
        visual: 'local-visual-regression',
        flow: 'playwright-flow',
        ab: 'mock-chromatic',
        a11y: 'local-a11y-audit',
        perf: 'mock-lighthouse',
    },
    agent_states: {
        orchestrator: 'success',
        visual: 'success',
        flow: 'error',
        ab: 'skipped',
        a11y: 'success',
        perf: 'success',
        reporter: 'success',
    },
    worker_results: [
        {
            agent_id: 'visual',
            status: 'success',
            provider: 'local-visual-regression',
            started_at: '2026-03-31T10:00:02',
            finished_at: '2026-03-31T10:00:04',
            payload: {
                diffPixels: 960,
                diffPercentage: 4.6,
                screenshots: [],
            },
            normalized_findings: [
                {
                    finding_id: 'visual-1',
                    agent_id: 'visual',
                    severity: 'high',
                    title: '视觉回归存在明显差异',
                    summary: '像素差异 4.60%',
                    category: 'visual_regression_gap',
                    provider: 'local-visual-regression',
                },
            ],
        },
        {
            agent_id: 'flow',
            status: 'error',
            provider: 'playwright-flow',
            started_at: '2026-03-31T10:00:03',
            finished_at: '2026-03-31T10:00:05',
            payload: {
                steps: [{ step: 'goto:index.html', status: 'success' }],
                failures: [{ type: 'critical_page_missing', page: '审批流', message: '关键页面未映射到原型：审批流' }],
            },
            normalized_findings: [
                {
                    finding_id: 'flow-1',
                    agent_id: 'flow',
                    severity: 'blocking',
                    title: '流程连通性存在问题',
                    summary: '关键页面未映射到原型：审批流',
                    category: 'blocking_prototype_gap',
                    provider: 'playwright-flow',
                },
            ],
        },
        {
            agent_id: 'ab',
            status: 'skipped',
            provider: 'mock-chromatic',
            started_at: '2026-03-31T10:00:03',
            finished_at: '2026-03-31T10:00:03',
            payload: {
                reason: '未提供 compare_source，A/B 结构对比已跳过',
                changedComponents: [],
                comparedVersions: [],
            },
            normalized_findings: [],
        },
        {
            agent_id: 'a11y',
            status: 'success',
            provider: 'local-a11y-audit',
            started_at: '2026-03-31T10:00:04',
            finished_at: '2026-03-31T10:00:06',
            payload: {
                violations: [],
                wcagLevel: 'AA',
                score: 94,
            },
            normalized_findings: [],
        },
        {
            agent_id: 'perf',
            status: 'success',
            provider: 'mock-lighthouse',
            started_at: '2026-03-31T10:00:05',
            finished_at: '2026-03-31T10:00:08',
            payload: {
                score: 72,
                lcp: 2.8,
                cls: 0.08,
                fid: 34,
            },
            normalized_findings: [
                {
                    finding_id: 'perf-1',
                    agent_id: 'perf',
                    severity: 'medium',
                    title: '性能预警（Mock Lighthouse）',
                    summary: '当前 mock 性能评分为 72，建议后续接入真实 Lighthouse 复核。',
                    category: 'mock_perf_warning',
                    provider: 'mock-lighthouse',
                },
            ],
        },
    ],
    report: {
        summary: {
            mission_id: 'proto001',
            total_workers: 5,
            success_workers: 3,
            error_workers: 1,
            skipped_workers: 1,
            finding_count: 3,
        },
        findings: [
            {
                finding_id: 'flow-1',
                agent_id: 'flow',
                severity: 'blocking',
                title: '流程连通性存在问题',
                summary: '关键页面未映射到原型：审批流',
                category: 'blocking_prototype_gap',
                provider: 'playwright-flow',
            },
            {
                finding_id: 'visual-1',
                agent_id: 'visual',
                severity: 'high',
                title: '视觉回归存在明显差异',
                summary: '像素差异 4.60%',
                category: 'visual_regression_gap',
                provider: 'local-visual-regression',
            },
            {
                finding_id: 'perf-1',
                agent_id: 'perf',
                severity: 'medium',
                title: '性能预警（Mock Lighthouse）',
                summary: '当前 mock 性能评分为 72，建议后续接入真实 Lighthouse 复核。',
                category: 'mock_perf_warning',
                provider: 'mock-lighthouse',
            },
        ],
        recommendations: [
            '优先补齐阻断级原型差异和关键页面，先恢复主流程骨架，再处理样式细节。',
            '当前性能结果来自 Mock Lighthouse，先把它作为预警信号，再决定是否接入真实 Lighthouse 复核。',
        ],
        worker_results: [],
        quality_gate_metrics: {
            module_coverage_rate: 0.75,
            page_mapping_rate: 0.5,
            blocking_prototype_gap_count: 1,
            critical_field_missing_count: 0,
            critical_state_transition_gap_count: 1,
        },
    },
    logs: [
        {
            timestamp: '2026-03-31T10:00:01',
            level: 'info',
            message: '开始解析原型来源与项目包上下文',
            data: {
                agent_id: 'orchestrator',
                agent_status: 'running',
            },
        },
        {
            timestamp: '2026-03-31T10:00:05',
            level: 'error',
            message: 'flow Worker 完成',
            data: {
                agent_id: 'flow',
                agent_status: 'error',
                provider: 'playwright-flow',
            },
        },
    ],
    source_context: {
        entry_url: 'https://demo.example.com/prototype',
        discovered_pages: [
            { title: 'home', relative_path: '/', url: 'https://demo.example.com/prototype' },
            { title: 'approval', relative_path: '/approval', url: 'https://demo.example.com/prototype/approval' },
        ],
        playbook_context: {
            critical_pages: [
                { page_name: '审批流', route: '/approval' },
            ],
        },
    },
};

describe('PrototypeAgentsPage', () => {
    beforeEach(() => {
        mockCommanderCancel.mockReset();
        mockCommanderPrototypeMissions.mockReset();
        mockCommanderPrototypeRun.mockReset();
        mockCommanderPrototypeStatus.mockReset();
        mockCommanderPrototypeStream.mockReset();
        mockCommanderPrototypeMissions.mockResolvedValue([baseMission]);
        mockCommanderPrototypeStatus.mockResolvedValue(baseMission);
        mockCommanderPrototypeRun.mockResolvedValue(baseMission);
        mockCommanderCancel.mockResolvedValue({ mission_id: 'proto001', cancelled: true });
        mockCommanderPrototypeStream.mockReturnValue(() => {});
    });

    it('should build severity summary and agent states', () => {
        expect(buildSeveritySummary(baseMission.report.findings)).toContain('blocking:1');
        expect(buildSeveritySummary(baseMission.report.findings)).toContain('high:1');
        expect(buildSeveritySummary(baseMission.report.findings)).toContain('medium:1');

        const nodes = getPrototypeAgentNodes(baseMission as never);
        expect(nodes.map((item) => item.id)).toEqual([
            'orchestrator',
            'visual',
            'flow',
            'ab',
            'a11y',
            'perf',
            'reporter',
        ]);
        expect(nodes.find((item) => item.id === 'flow')?.status).toBe('error');
        expect(nodes.find((item) => item.id === 'ab')?.status).toBe('skipped');
    });

    it('should render mission overview, timeline and raw json tab', async () => {
        render(<PrototypeAgentsPage />);

        expect(await screen.findByText('原型测试 7 Agent 编排台')).toBeInTheDocument();
        await waitFor(() => expect(mockCommanderPrototypeMissions).toHaveBeenCalledWith(12));

        expect(screen.getByText('Agent 状态图')).toBeInTheDocument();
        expect(screen.getByText('Worker 结果')).toBeInTheDocument();
        expect(screen.getByText('时间线')).toBeInTheDocument();
        expect(screen.getAllByText('#proto001').length).toBeGreaterThan(0);
        expect(screen.getAllByText('流程连通性存在问题').length).toBeGreaterThan(0);
        expect(screen.getByText('flow Worker 完成')).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: '原始 JSON' }));

        expect(await screen.findByText(/"mission_id": "proto001"/)).toBeInTheDocument();
    });
});
