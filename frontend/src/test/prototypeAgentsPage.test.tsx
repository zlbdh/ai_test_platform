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
    user_input: "Prototype testing · https://demo.example.com/prototype",
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
                    title: "Visual regression has significant differences",
                    summary: "Pixel difference 4.60%",
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
                failures: [{ type: 'critical_page_missing', page: "Approval flow", message: "Key page not mapped to the prototype: Approval flow" }],
            },
            normalized_findings: [
                {
                    finding_id: 'flow-1',
                    agent_id: 'flow',
                    severity: 'blocking',
                    title: "Workflow connectivity issues",
                    summary: "Key page not mapped to the prototype: Approval flow",
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
                reason: "No compare_source provided; A/B structure comparison skipped",
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
                    title: "Performance warning (Mock Lighthouse)",
                    summary: "The mock performance score is 72. Verify it with real Lighthouse results later.",
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
                title: "Workflow connectivity issues",
                summary: "Key page not mapped to the prototype: Approval flow",
                category: 'blocking_prototype_gap',
                provider: 'playwright-flow',
            },
            {
                finding_id: 'visual-1',
                agent_id: 'visual',
                severity: 'high',
                title: "Visual regression has significant differences",
                summary: "Pixel difference 4.60%",
                category: 'visual_regression_gap',
                provider: 'local-visual-regression',
            },
            {
                finding_id: 'perf-1',
                agent_id: 'perf',
                severity: 'medium',
                title: "Performance warning (Mock Lighthouse)",
                summary: "The mock performance score is 72. Verify it with real Lighthouse results later.",
                category: 'mock_perf_warning',
                provider: 'mock-lighthouse',
            },
        ],
        recommendations: [
            "Resolve blocking prototype differences and missing key pages first, restore the main workflow structure, then address styling details.",
            "Current performance results come from Mock Lighthouse. Treat them as a warning signal before deciding whether to run real Lighthouse verification.",
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
            message: "Start parsing the prototype source and project package context",
            data: {
                agent_id: 'orchestrator',
                agent_status: 'running',
            },
        },
        {
            timestamp: '2026-03-31T10:00:05',
            level: 'error',
            message: "flow Worker completed",
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
                { page_name: "Approval flow", route: '/approval' },
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

        expect(await screen.findByText("Seven-agent prototype testing workspace")).toBeInTheDocument();
        await waitFor(() => expect(mockCommanderPrototypeMissions).toHaveBeenCalledWith(12));

        expect(screen.getByText("Agent status graph")).toBeInTheDocument();
        expect(screen.getByText("Worker results")).toBeInTheDocument();
        expect(screen.getByText("Timeline")).toBeInTheDocument();
        expect(screen.getAllByText('#proto001').length).toBeGreaterThan(0);
        expect(screen.getAllByText("Workflow connectivity issues").length).toBeGreaterThan(0);
        expect(screen.getByText("flow Worker completed")).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: "Raw JSON" }));

        expect(await screen.findByText(/"mission_id": "proto001"/)).toBeInTheDocument();
    });
});
