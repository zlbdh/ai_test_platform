/**
 * backendService.ts unit tests (P2-2)
 *
 * Covers:
 * - fetch request format (URL / method / headers / body)
 * - Error handling (HTTP errors / network failures / timeouts)
 * - Data conversion (plan steps / dashboard aggregation)
 * - Edge cases (empty responses / unreachable servers)
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock global fetch before importing service
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Need to mock AbortController's abort for timeout tests
const mockAbort = vi.fn();
class MockAbortController {
    signal = { aborted: false, addEventListener: vi.fn(), removeEventListener: vi.fn(), onabort: null, reason: undefined, throwIfAborted: vi.fn(), dispatchEvent: vi.fn().mockReturnValue(true) };
    abort = mockAbort;
}
global.AbortController = MockAbortController as unknown as typeof AbortController;

import {
    archivePlatformMaintenanceSuspects,
    cleanupPlatformMaintenanceArchive,
    exportPlatformMaintenanceArchive,
    startExecution,
    stopExecution,
    pauseExecution,
    resumeExecution,
    suspendExecution,
    checkBackendHealth,
    generateTestPlanWithCoverage,
    generateTestPlan,
    getSystemStatus,
    getExecutionHistory,
    getExecutionDetail,
    getAgentStats,
    getDashboardStats,
    getPlatformInfo,
    getPlatformMaintenance,
    getPlatformReadiness,
    getPlatformRemediation,
    quarantinePlatformShadowDbs,
    runPlatformMaintenance,
} from '../services/backendService';

// Helper to create a mock Response
function mockResponse(body: unknown, ok = true, status = 200): Response {
    return {
        ok,
        status,
        statusText: ok ? 'OK' : 'Error',
        json: vi.fn().mockResolvedValue(body),
        text: vi.fn().mockResolvedValue(JSON.stringify(body)),
        headers: new Headers(),
        redirected: false,
        type: 'basic',
        url: '',
        clone: vi.fn(),
        body: null,
        bodyUsed: false,
        arrayBuffer: vi.fn(),
        blob: vi.fn(),
        formData: vi.fn(),
        bytes: vi.fn(),
    } as unknown as Response;
}

describe('backendService.ts', () => {
    let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
        vi.useFakeTimers();
        mockFetch.mockReset();
        mockAbort.mockReset();
        consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    });

    afterEach(() => {
        vi.useRealTimers();
        consoleErrorSpy.mockRestore();
    });

    // ============================================================
    // startExecution
    // ============================================================
    describe('startExecution', () => {
        it('should POST with correct body format', async () => {
            mockFetch.mockResolvedValue(mockResponse({ task_id: 'task-1' }));

            const result = await startExecution("Test login", true, true, 'http://example.com');

            expect(mockFetch).toHaveBeenCalled();
            const [url, options] = mockFetch.mock.calls[0];
            expect(url).toContain('/api/start');
            expect(options.method).toBe('POST');
            expect(options.headers['Content-Type']).toBe('application/json');

            const body = JSON.parse(options.body);
            expect(body.requirement).toBe("Test login");
            expect(body.mode).toBe('CLOUD');
            expect(body.planner_mode).toBe('smart');
            expect(body.target_url).toBe('http://example.com');
            expect(result.task_id).toBe('task-1');
        });

        it('should use "quick" planner when multiAgent=false', async () => {
            mockFetch.mockResolvedValue(mockResponse({ task_id: 'task-2' }));

            await startExecution('test', false);

            const body = JSON.parse(mockFetch.mock.calls[0][1].body);
            expect(body.planner_mode).toBe('quick');
        });

        it('should include execution_group_id when provided', async () => {
            mockFetch.mockResolvedValue(mockResponse({ task_id: 'task-3' }));

            await startExecution('test', true, true, 'http://example.com', 'sess_a', 'chromium', 'batch_demo');

            const body = JSON.parse(mockFetch.mock.calls[0][1].body);
            expect(body.execution_group_id).toBe('batch_demo');
            expect(body.session_id).toBe('sess_a');
        });

        it('should include probe execution fields when enabled', async () => {
            mockFetch.mockResolvedValue(mockResponse({ task_id: 'task-probe' }));

            await startExecution("Read-only probe", true, true, 'http://example.com', 'sess_probe', 'chromium', 'group_probe', 'probe', 'read_only');

            const body = JSON.parse(mockFetch.mock.calls[0][1].body);
            expect(body.execution_mode).toBe('probe');
            expect(body.interaction_policy).toBe('read_only');
        });

        it('should throw on HTTP error', async () => {
            mockFetch.mockResolvedValue(mockResponse('Server Error', false, 500));

            await expect(startExecution('test')).rejects.toThrow("API request failed");
        });

        it('should throw on network failure', async () => {
            mockFetch.mockRejectedValue(new TypeError('Failed to fetch'));

            await expect(startExecution('test')).rejects.toThrow('Failed to fetch');
        });
    });

    // ============================================================
    // stopExecution / pauseExecution / resumeExecution / suspendExecution
    // ============================================================
    describe('execution control', () => {
        it('stopExecution should POST to control/stop', async () => {
            mockFetch.mockResolvedValue(mockResponse({ status: 'stopped' }));

            const result = await stopExecution();
            expect(result.status).toBe('stopped');
            expect(mockFetch.mock.calls[0][1].method).toBe('POST');
        });

        it('pauseExecution should POST to control/pause', async () => {
            mockFetch.mockResolvedValue(mockResponse({ status: 'paused' }));

            const result = await pauseExecution();
            expect(result.status).toBe('paused');
        });

        it('resumeExecution should POST to control/resume', async () => {
            mockFetch.mockResolvedValue(mockResponse({ status: 'running' }));

            const result = await resumeExecution();
            expect(result.status).toBe('running');
        });

        it('suspendExecution should POST to control/suspend', async () => {
            mockFetch.mockResolvedValue(mockResponse({ status: 'paused' }));

            const result = await suspendExecution();
            expect(result.status).toBe('paused');
        });
    });

    // ============================================================
    // checkBackendHealth
    // ============================================================
    describe('checkBackendHealth', () => {
        it('should return true when server is reachable', async () => {
            mockFetch.mockResolvedValue(mockResponse({ status: 'ok' }));

            const healthy = await checkBackendHealth();
            expect(healthy).toBe(true);
        });

        it('should return false when server is unreachable', async () => {
            mockFetch.mockRejectedValue(new TypeError('Failed to fetch'));

            const healthy = await checkBackendHealth();
            expect(healthy).toBe(false);
        });

        it('should return false when server returns non-ok', async () => {
            mockFetch.mockResolvedValue(mockResponse({}, false, 503));

            const healthy = await checkBackendHealth();
            expect(healthy).toBe(false);
        });
    });

    // ============================================================
    // generateTestPlanWithCoverage
    // ============================================================
    describe('generateTestPlanWithCoverage', () => {
        it('should convert backend format to TestStep[]', async () => {
            const backendData = {
                status: 'ok',
                steps: [
                    { action: 'goto', target: 'https://example.com', value: '', description: "Open the home page" },
                    { action: 'click', target: '#login-btn', value: '', description: "Click login" },
                ],
                coverage_summary: {
                    total_scenarios: 2,
                    by_priority: { P0: 1, P1: 1, P2: 0 },
                    dimensions_covered: ["Functional", "Security"],
                },
            };
            mockFetch.mockResolvedValue(mockResponse(backendData));

            const result = await generateTestPlanWithCoverage("Test login", 'https://example.com');

            expect(result.steps).toHaveLength(2);
            expect(result.steps[0].id).toBe('step-1');
            expect(result.steps[0].action).toBe('goto');
            expect(result.steps[0].target).toBe('https://example.com');
            expect(result.steps[0].agent).toBe('PLANNER');
            expect(result.steps[0].status).toBe('pending');
            expect(result.coverage_summary?.total_scenarios).toBe(2);
        });

        it('should POST with enable_rag=true', async () => {
            mockFetch.mockResolvedValue(mockResponse({ steps: [], coverage_summary: null }));

            await generateTestPlanWithCoverage('req', 'http://target.com');

            const body = JSON.parse(mockFetch.mock.calls[0][1].body);
            expect(body.enable_rag).toBe(true);
            expect(body.requirement).toBe('req');
            expect(body.target_url).toBe('http://target.com');
        });

        it('should include probe plan fields when generating a probe plan', async () => {
            mockFetch.mockResolvedValue(mockResponse({ steps: [], coverage_summary: null }));

            await generateTestPlanWithCoverage("Read-only probe", 'http://target.com', 'probe', 'read_only');

            const body = JSON.parse(mockFetch.mock.calls[0][1].body);
            expect(body.execution_mode).toBe('probe');
            expect(body.interaction_policy).toBe('read_only');
        });

        it('should throw when response has error status', async () => {
            mockFetch.mockResolvedValue(mockResponse({ status: 'error', message: 'LLM failure' }));

            await expect(generateTestPlanWithCoverage('test'))
                .rejects.toThrow('LLM failure');
        });

        it('should handle empty steps gracefully', async () => {
            mockFetch.mockResolvedValue(mockResponse({ status: 'ok' }));

            const result = await generateTestPlanWithCoverage('req');
            expect(result.steps).toEqual([]);
            expect(result.coverage_summary).toBeNull();
        });
    });

    // ============================================================
    // generateTestPlan (deprecated wrapper)
    // ============================================================
    describe('generateTestPlan', () => {
        it('should return only steps from plan result', async () => {
            mockFetch.mockResolvedValue(mockResponse({
                status: 'ok',
                steps: [{ action: 'click', target: '#btn', value: '', description: 'Click' }],
                coverage_summary: { total_scenarios: 1, by_priority: { P0: 1, P1: 0, P2: 0 }, dimensions_covered: [] },
            }));

            const steps = await generateTestPlan('req');
            expect(steps).toHaveLength(1);
            expect(steps[0].action).toBe('click');
        });
    });

    // ============================================================
    // getExecutionDetail
    // ============================================================
    describe('getExecutionDetail', () => {
        it('should fetch task detail by ID', async () => {
            const detail = { task_id: 't-1', requirement: 'test', status: 'completed', log_count: 5, error_count: 0, duration_ms: 1234, target_url: '', mode: 'CLOUD', logs: [], created_at: '' };
            mockFetch.mockResolvedValue(mockResponse(detail));

            const result = await getExecutionDetail('t-1');
            expect(result.task_id).toBe('t-1');
            expect(mockFetch.mock.calls[0][0]).toContain('/api/history/t-1');
        });
    });

    // ============================================================
    // getSystemStatus
    // ============================================================
    describe('getSystemStatus', () => {
        it('should return status and logs on success', async () => {
            mockFetch.mockResolvedValue(mockResponse({
                status: 'IDLE',
                logs: ['log1'],
                task: '??????? Wave0 ???????',
                task_display: 'https://example.com/login',
                task_text_state: 'broken_fallback',
                execution_mode: 'probe',
                interaction_policy: 'read_only',
                step_budget: 8,
                signal: 'RUNNING',
                is_running: true,
            }));

            const result = await getSystemStatus();
            expect(result.status).toBe('IDLE');
            expect(result.logs).toEqual(['log1']);
            expect(result.task).toBe('??????? Wave0 ???????');
            expect(result.task_display).toBe('https://example.com/login');
            expect(result.task_text_state).toBe('broken_fallback');
            expect(result.execution_mode).toBe('probe');
            expect(result.interaction_policy).toBe('read_only');
            expect(result.step_budget).toBe(8);
            expect(result.signal).toBe('RUNNING');
            expect(result.is_running).toBe(true);
        });

        it('should return UNKNOWN on failure', async () => {
            mockFetch.mockRejectedValue(new Error('offline'));

            const result = await getSystemStatus();
            expect(result.status).toBe('UNKNOWN');
            expect(result.logs).toEqual([]);
        });
    });

    // ============================================================
    // getExecutionHistory
    // ============================================================
    describe('getExecutionHistory', () => {
        it('should return records on success', async () => {
            const records = [{ task_id: 't-1', status: 'completed' }];
            mockFetch.mockResolvedValue(mockResponse(records));

            const result = await getExecutionHistory();
            expect(result).toHaveLength(1);
            expect(result[0].status).toBe('completed');
        });

        it('should return empty array on failure', async () => {
            mockFetch.mockRejectedValue(new Error('offline'));

            const result = await getExecutionHistory();
            expect(result).toEqual([]);
        });
    });

    // ============================================================
    // getAgentStats
    // ============================================================
    describe('getAgentStats', () => {
        it('should return stats on success', async () => {
            mockFetch.mockResolvedValue(mockResponse({ stats: { healed: 5 } }));

            const result = await getAgentStats();
            expect(result).toEqual({ healed: 5 });
        });

        it('should return empty object on failure', async () => {
            mockFetch.mockRejectedValue(new Error('offline'));

            const result = await getAgentStats();
            expect(result).toEqual({});
        });
    });

    describe('platform maintenance', () => {
        it('getPlatformInfo should request platform info', async () => {
            mockFetch.mockResolvedValue(mockResponse({
                name: 'AI Test Platform',
                version: '2.7.0',
                operations: {
                    business_db_path: 'D:\\demo\\business.db',
                    business_db_size_bytes: 1024,
                    business_db_updated_at: '2026-03-16T10:00:00',
                    shadow_business_dbs: ['D:\\legacy\\business.db'],
                    shadow_business_db_count: 1,
                    business_db_risk_level: 'warning',
                    notification_webhook_count: 2,
                    notification_tested_webhook_count: 2,
                    notification_healthy_webhook_count: 1,
                    notification_untested_webhook_count: 0,
                    notification_ready: true,
                    notification_summary: "2 Webhooks configured; 1 passed its latest test",
                    commander_chatops_ready: false,
                    commander_chatops_platform_ready: true,
                    commander_chatops_webhook_ready: true,
                    commander_chatops_external_connected: false,
                    commander_chatops_external_connected_current: false,
                    commander_chatops_external_connected_history_observed: true,
                    commander_chatops_external_connection_stale: true,
                    commander_chatops_external_self_check_recent_success: true,
                    commander_chatops_subscription_endpoint_verified: true,
                    commander_chatops_verification_token_configured: true,
                    commander_chatops_verification_token_masked: 'CLIy...6Qxa',
                    commander_chatops_verification_token_updated_at: '2026-03-18T12:00:00',
                    commander_chatops_callback_url: 'http://localhost:8020/api/commander/notification_platform/events',
                    commander_chatops_callback_url_public: false,
                    commander_chatops_callback_provider: {
                        key: 'local',
                        label: "Local URL",
                        host: 'localhost',
                    },
                    commander_chatops_callback_recommendation: "Set PUBLIC_API_BASE_URL to a public address accessible to the notification platform before running the challenge probe.",
                    commander_chatops_summary: "Platform event subscription is ready, but the callback address is still local or private. Configure a public callback URL accessible to the notification platform first.",
                    commander_chatops_recent_event_at: '2026-03-18T12:05:00',
                    commander_chatops_recent_success_at: '2026-03-18T12:05:00',
                    commander_chatops_latest_external_success_at: '2026-03-18T11:59:00',
                    commander_chatops_latest_external_self_check_at: '2026-03-18T12:08:00',
                    commander_chatops_recent_delivery_count: 1,
                    maintenance_suspect_history_count: 3,
                    maintenance_archived_history_count: 4,
                    maintenance_history_clean: false,
                    maintenance_history_summary: "Detected 3 suspicious maintenance records; hidden from the main view by default",
                    readiness_stage: 'pre-production',
                    readiness_score: 78,
                    readiness_summary: "Core capabilities are ready for preproduction, but alert integration and environment governance remain the main constraints.",
                },
            }));

            const result = await getPlatformInfo();

            expect(mockFetch.mock.calls[0][0]).toContain('/api/platform/info');
            expect(result.operations?.business_db_path).toBe('D:\\demo\\business.db');
            expect(result.operations?.shadow_business_dbs).toEqual(['D:\\legacy\\business.db']);
            expect(result.operations?.business_db_risk_level).toBe('warning');
            expect(result.operations?.notification_ready).toBe(true);
            expect(result.operations?.notification_tested_webhook_count).toBe(2);
            expect(result.operations?.notification_healthy_webhook_count).toBe(1);
            expect(result.operations?.notification_untested_webhook_count).toBe(0);
            expect(result.operations?.commander_chatops_platform_ready).toBe(true);
            expect(result.operations?.commander_chatops_external_connected).toBe(false);
            expect(result.operations?.commander_chatops_external_connected_history_observed).toBe(true);
            expect(result.operations?.commander_chatops_external_connection_stale).toBe(true);
            expect(result.operations?.commander_chatops_external_self_check_recent_success).toBe(true);
            expect(result.operations?.commander_chatops_callback_url_public).toBe(false);
            expect(result.operations?.commander_chatops_callback_provider?.label).toBe("Local URL");
            expect(result.operations?.commander_chatops_callback_recommendation).toContain('PUBLIC_API_BASE_URL');
            expect(result.operations?.commander_chatops_verification_token_masked).toBe('CLIy...6Qxa');
            expect(result.operations?.commander_chatops_latest_external_self_check_at).toBe('2026-03-18T12:08:00');
            expect(result.operations?.maintenance_suspect_history_count).toBe(3);
            expect(result.operations?.maintenance_archived_history_count).toBe(4);
            expect(result.operations?.readiness_stage).toBe('pre-production');
            expect(result.operations?.readiness_score).toBe(78);
        });

        it('getPlatformReadiness should request readiness snapshot', async () => {
            mockFetch.mockResolvedValue(mockResponse({
                status: 'success',
                readiness: {
                    stage: 'pre-production',
                    score: 78,
                    local_score: 72,
                    global_score: 84,
                    summary: "Core capabilities are ready for preproduction, but alert integration and environment governance remain the main constraints.",
                    computed_at: '2026-03-16T18:00:00',
                    local: [
                        { key: 'maintenance_module', name: "Maintenance module", score: 100, status: 'good', summary: 'ok' },
                    ],
                    global: [
                        { key: 'architecture', name: "Architecture stability", score: 88, status: 'good', summary: 'ok' },
                    ],
                    recommendations: ["Connect at least one production alert Webhook so maintenance failures and risk warnings enter the notification workflow."],
                },
            }));

            const result = await getPlatformReadiness();

            expect(mockFetch.mock.calls[0][0]).toContain('/api/platform/readiness');
            expect(result.readiness.stage).toBe('pre-production');
            expect(result.readiness.local[0].name).toBe("Maintenance module");
            expect(result.readiness.global[0].name).toBe("Architecture stability");
        });

        it('getPlatformRemediation should request remediation actions', async () => {
            mockFetch.mockResolvedValue(mockResponse({
                status: 'success',
                remediation: {
                    computed_at: '2026-03-16T18:00:00',
                    status: 'attention',
                    summary: "Further production readiness actions are required.",
                    counts: { total: 2, blocking: 1, local: 1, global: 1, p0: 1, p1: 1 },
                    risk: { shadow_count: 1, notification_ready: false, readiness_stage: 'pre-production' },
                    items: [
                        {
                            key: 'notification_webhook',
                            title: "Connect a production alert Webhook",
                            scope: 'local',
                            priority: 'P0',
                            blocking: true,
                            status: 'open',
                            route: '/notifications',
                            summary: "No production alert Webhook is currently enabled",
                            impact: 'impact',
                            next_step: 'step',
                            evidence: { webhook_count: 0 },
                        },
                    ],
                },
            }));

            const result = await getPlatformRemediation();

            expect(mockFetch.mock.calls[0][0]).toContain('/api/platform/remediation');
            expect(result.remediation.counts.total).toBe(2);
            expect(result.remediation.items[0].route).toBe('/notifications');
        });

        it('getPlatformMaintenance should request maintenance snapshot', async () => {
            mockFetch.mockResolvedValue(mockResponse({
                status: 'success',
                current: {
                    status: 'success',
                    reason: 'startup',
                    timestamp: '2026-03-16T10:00:00',
                    duration_ms: 123,
                    skipped: false,
                    sync: { performance: 0, security: 0 },
                    repair: { group_updates: 0, record_updates: 0, legacy_groups: 0 },
                    report_history: { history_entries: 5, updated_entries: 1 },
                    risk: { level: 'warning', shadow_count: 1, summary: "Detected 1 shadow business database" },
                    notification: { webhook_count: 1, tested_enabled: 1, healthy_enabled: 1, untested_enabled: 0, ready: true, summary: "1 Webhook configured; 1 passed its latest test" },
                    data_quality: { suspect_history_count: 2, archived_history_count: 5, clean: false, summary: "Detected 2 suspicious maintenance records; hidden from the main view by default" },
                    warning_detected: true,
                    risk_alert_sent: true,
                },
                latest_activity: {
                    status: 'success',
                    reason: 'history_list',
                    timestamp: '2026-03-16T10:01:00',
                    duration_ms: 98,
                    skipped: false,
                    sync: { performance: 0, security: 0 },
                    repair: { group_updates: 0, record_updates: 0, legacy_groups: 0 },
                    report_history: { history_entries: 5, updated_entries: 1 },
                    risk: { level: 'warning', shadow_count: 1, summary: "Detected 1 shadow business database" },
                    notification: { webhook_count: 1, tested_enabled: 1, healthy_enabled: 1, untested_enabled: 0, ready: true, summary: "1 Webhook configured; 1 passed its latest test" },
                    data_quality: { suspect_history_count: 2, archived_history_count: 5, clean: false, summary: "Detected 2 suspicious maintenance records; hidden from the main view by default" },
                    warning_detected: true,
                    risk_alert_sent: false,
                },
                history: { items: [], total: 0, raw_total: 2, suspect_count: 2, archived_count: 5, filtered: true, include_suspect: false, include_archived: false },
            }));

            const result = await getPlatformMaintenance(5);

            expect(mockFetch.mock.calls[0][0]).toContain('/api/platform/maintenance?limit=5&include_suspect=false&include_archived=false');
            expect(result.current.reason).toBe('startup');
            expect(result.latest_activity?.reason).toBe('history_list');
            expect(result.current.warning_detected).toBe(true);
            expect(result.current.risk_alert_sent).toBe(true);
            expect(result.current.notification?.ready).toBe(true);
            expect(result.current.notification?.healthy_enabled).toBe(1);
            expect(result.current.data_quality?.suspect_history_count).toBe(2);
            expect(result.current.data_quality?.archived_history_count).toBe(5);
            expect(result.history.suspect_count).toBe(2);
            expect(result.history.archived_count).toBe(5);
        });

        it('getPlatformMaintenance should support includeSuspect query flag', async () => {
            mockFetch.mockResolvedValue(mockResponse({
                status: 'success',
                current: { status: 'success', reason: 'startup', timestamp: '2026-03-16T10:00:00', duration_ms: 1, skipped: false, sync: { performance: 0, security: 0 }, repair: { group_updates: 0, record_updates: 0, legacy_groups: 0 }, report_history: { history_entries: 0, updated_entries: 0 } },
                history: { items: [], total: 0, raw_total: 2, suspect_count: 2, filtered: false, include_suspect: true },
            }));

            await getPlatformMaintenance(3, true);

            expect(mockFetch.mock.calls[0][0]).toContain('/api/platform/maintenance?limit=3&include_suspect=true&include_archived=false');
        });

        it('getPlatformMaintenance should support includeArchived query flag', async () => {
            mockFetch.mockResolvedValue(mockResponse({
                status: 'success',
                current: { status: 'success', reason: 'startup', timestamp: '2026-03-16T10:00:00', duration_ms: 1, skipped: false, sync: { performance: 0, security: 0 }, repair: { group_updates: 0, record_updates: 0, legacy_groups: 0 }, report_history: { history_entries: 0, updated_entries: 0 } },
                history: { items: [], total: 2, raw_total: 2, suspect_count: 0, archived_count: 1, filtered: true, include_suspect: false, include_archived: true },
            }));

            await getPlatformMaintenance(3, false, true);

            expect(mockFetch.mock.calls[0][0]).toContain('/api/platform/maintenance?limit=3&include_suspect=false&include_archived=true');
        });

        it('runPlatformMaintenance should POST manual trigger', async () => {
            mockFetch.mockResolvedValue(mockResponse({
                status: 'success',
                result: { status: 'success', reason: 'dashboard_manual', timestamp: '2026-03-16T10:00:00', duration_ms: 222, skipped: false, sync: { performance: 0, security: 0 }, repair: { group_updates: 0, record_updates: 0, legacy_groups: 0 }, report_history: { history_entries: 5, updated_entries: 0 } },
            }));

            const result = await runPlatformMaintenance(true, 'dashboard_manual');

            const [url, options] = mockFetch.mock.calls[0];
            expect(url).toContain('/api/platform/maintenance/run');
            expect(options.method).toBe('POST');
            expect(JSON.parse(options.body)).toEqual({ force: true, reason: 'dashboard_manual' });
            expect(result.duration_ms).toBe(222);
        });

        it('archivePlatformMaintenanceSuspects should POST archive request', async () => {
            mockFetch.mockResolvedValue(mockResponse({
                status: 'success',
                result: {
                    archived_count: 4,
                    archived_ids: [1, 2, 3, 4],
                    reason: 'dashboard_archive_suspect',
                    archived_at: '2026-03-16T12:00:00',
                    remaining: 0,
                    data_quality: { suspect_history_count: 0, raw_history_count: 128, archived_history_count: 44, visible_history_count: 84, clean: true, summary: "Archived 44 historical maintenance records" },
                },
            }));

            const result = await archivePlatformMaintenanceSuspects('dashboard_archive_suspect', 0);

            const [url, options] = mockFetch.mock.calls[0];
            expect(url).toContain('/api/platform/maintenance/archive-suspect');
            expect(options.method).toBe('POST');
            expect(JSON.parse(options.body)).toEqual({ reason: 'dashboard_archive_suspect', limit: 0 });
            expect(result.archived_count).toBe(4);
            expect(result.data_quality.archived_history_count).toBe(44);
        });

        it('exportPlatformMaintenanceArchive should POST export request', async () => {
            mockFetch.mockResolvedValue(mockResponse({
                status: 'success',
                result: {
                    reason: 'dashboard_export_archive',
                    format: 'json',
                    exported_at: '2026-03-16T16:00:00',
                    file_path: 'D:\\workspace\\ai_test_platform\\data\\platform_maintenance_exports\\platform_maintenance_archive_dashboard_export_archive_20260316_160000.json',
                    count: 60,
                    bytes_written: 2048,
                    data_quality: {
                        suspect_history_count: 0,
                        raw_history_count: 140,
                        archived_history_count: 60,
                        visible_history_count: 80,
                        archive_export_count: 1,
                        last_archive_export_at: '2026-03-16T16:00:00',
                        last_archive_export_reason: 'dashboard_export_archive',
                        last_archive_export_path: 'D:\\workspace\\ai_test_platform\\data\\platform_maintenance_exports\\platform_maintenance_archive_dashboard_export_archive_20260316_160000.json',
                        last_archive_export_format: 'json',
                        archive_export_fresh: true,
                        clean: true,
                        summary: "Archived 60 historical maintenance records; export completed recently",
                    },
                },
            }));

            const result = await exportPlatformMaintenanceArchive('dashboard_export_archive', 'json');

            const [url, options] = mockFetch.mock.calls[0];
            expect(url).toContain('/api/platform/maintenance/export-archive');
            expect(options.method).toBe('POST');
            expect(JSON.parse(options.body)).toEqual({ reason: 'dashboard_export_archive', format: 'json' });
            expect(result.count).toBe(60);
            expect(result.data_quality.archive_export_fresh).toBe(true);
        });

        it('cleanupPlatformMaintenanceArchive should POST cleanup request', async () => {
            mockFetch.mockResolvedValue(mockResponse({
                status: 'success',
                result: {
                    reason: 'dashboard_cleanup_archive_dry_run',
                    retention_days: 30,
                    dry_run: true,
                    cutoff: '2026-02-15T00:00:00',
                    candidate_runs: 0,
                    candidate_exports: 0,
                    deleted_runs: 0,
                    deleted_exports: 0,
                    deleted_export_files: [],
                    data_quality: {
                        suspect_history_count: 0,
                        raw_history_count: 140,
                        archived_history_count: 60,
                        visible_history_count: 80,
                        archive_export_count: 1,
                        last_archive_export_at: '2026-03-16T16:00:00',
                        last_archive_export_reason: 'dashboard_export_archive',
                        last_archive_export_path: 'D:\\workspace\\ai_test_platform\\data\\platform_maintenance_exports\\platform_maintenance_archive_dashboard_export_archive_20260316_160000.json',
                        last_archive_export_format: 'json',
                        archive_export_fresh: true,
                        archive_retention_days: 30,
                        archive_cleanup_needed: false,
                        archive_cleanup_candidate_count: 0,
                        archive_run_cleanup_candidates: 0,
                        archive_export_cleanup_candidates: 0,
                        last_archive_cleanup_at: '2026-03-16T16:10:00',
                        last_archive_cleanup_reason: 'dashboard_cleanup_archive_dry_run',
                        last_archive_cleanup_dry_run: true,
                        last_archive_cleanup_deleted_runs: 0,
                        last_archive_cleanup_deleted_exports: 0,
                        clean: true,
                        summary: "Archived 60 historical maintenance records; export completed recently",
                    },
                },
            }));

            const result = await cleanupPlatformMaintenanceArchive('dashboard_cleanup_archive_dry_run', 30, true);

            const [url, options] = mockFetch.mock.calls[0];
            expect(url).toContain('/api/platform/maintenance/cleanup-archive');
            expect(options.method).toBe('POST');
            expect(JSON.parse(options.body)).toEqual({ reason: 'dashboard_cleanup_archive_dry_run', retention_days: 30, dry_run: true });
            expect(result.candidate_runs).toBe(0);
            expect(result.data_quality.archive_retention_days).toBe(30);
        });

        it('quarantinePlatformShadowDbs should POST quarantine request', async () => {
            mockFetch.mockResolvedValue(mockResponse({
                status: 'success',
                result: {
                    reason: 'dashboard_shadow_db_quarantine',
                    archive_dir: 'D:\\archive',
                    moved_count: 1,
                    moved: [{ source_path: 'D:\\shadow\\business.db', archived_path: 'D:\\archive\\business.shadow.db', size_bytes: 123 }],
                    skipped_count: 0,
                    skipped: [],
                    observability: {
                        path: 'D:\\workspace\\ai_test_platform\\backend\\data\\business.db',
                        shadow_paths: [],
                        shadow_count: 0,
                        risk_level: 'normal',
                        current_db: { exists: true, size_bytes: 1024, updated_at: '2026-03-16T15:00:00' },
                    },
                },
            }));

            const result = await quarantinePlatformShadowDbs('dashboard_shadow_db_quarantine');

            const [url, options] = mockFetch.mock.calls[0];
            expect(url).toContain('/api/platform/shadow-db/quarantine');
            expect(options.method).toBe('POST');
            expect(JSON.parse(options.body)).toEqual({ reason: 'dashboard_shadow_db_quarantine' });
            expect(result.moved_count).toBe(1);
            expect(result.observability.shadow_count).toBe(0);
        });
    });

    // ============================================================
    // getDashboardStats
    // ============================================================
    describe('getDashboardStats', () => {
        it('should aggregate history records into dashboard stats', async () => {
            const today = new Date().toISOString();
            const records = [
                { task_id: 't-1', status: 'completed', created_at: today },
                { task_id: 't-2', status: 'failed', created_at: today },
                { task_id: 't-3', status: 'completed', created_at: today },
            ];
            mockFetch.mockResolvedValue(mockResponse(records));

            const stats = await getDashboardStats();

            expect(stats.todayExecutions).toBeGreaterThanOrEqual(0);
            expect(typeof stats.todaySuccessRate).toBe('number');
            expect(Array.isArray(stats.trend7Days)).toBe(true);
            expect(Array.isArray(stats.typeDistribution)).toBe(true);
        });

        it('should return zero-value stats on empty history', async () => {
            mockFetch.mockResolvedValue(mockResponse([]));

            const stats = await getDashboardStats();

            expect(stats.todayExecutions).toBe(0);
            expect(stats.todaySuccessRate).toBe(0);
            expect(stats.avgDurationMs).toBe(0);
        });

        it('should return zero-value stats on network failure', async () => {
            mockFetch.mockRejectedValue(new Error('offline'));

            const stats = await getDashboardStats();

            expect(stats.todayExecutions).toBe(0);
            expect(stats.trend7Days).toHaveLength(7);
        });
    });
});
