import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockFetch = vi.fn();
global.fetch = mockFetch;

function mockResponse(body: unknown, ok = true, status = 200): Response {
    return {
        ok,
        status,
        statusText: ok ? 'OK' : 'ERROR',
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

import {
    executeCommand,
    getNotificationPlatformBindingMe,
    getExplorationFinding,
    issueNotificationPlatformBindingCode,
    listCommandRuns,
    listExplorationFindings,
    listExplorationReviewQueue,
    listExplorationSessions,
    listReleaseRiskAssessments,
    revokeNotificationPlatformBinding,
} from '../services/legionControlService';
import { saveControlAuthSession } from '../services/controlAuthService';

describe('legionControlService', () => {
    beforeEach(() => {
        mockFetch.mockReset();
        localStorage.clear();
    });

    it('会为命令运行查询附带项目、来源筛选和 Bearer token', async () => {
        saveControlAuthSession({ token: 'legion-token' });
        mockFetch.mockResolvedValue(mockResponse({
            status: 'success',
            runs: [{ run_id: 'run-1', command_id: 'release.risk.assess', status: 'running', approval_status: 'not_required' }],
            count: 1,
        }));

        const payload = await listCommandRuns({ project_key: 'demo', approval_status: 'pending', source: 'notification_platform', limit: 5 });

        expect(payload.count).toBe(1);
        expect(payload.runs[0].run_id).toBe('run-1');
        const [url, options] = mockFetch.mock.calls[0];
        expect(String(url)).toContain('/api/commander/commands/runs?');
        expect(String(url)).toContain('project_key=demo');
        expect(String(url)).toContain('approval_status=pending');
        expect(String(url)).toContain('source=notification_platform');
        const headers = options.headers as Headers;
        expect(headers.get('Authorization')).toBe('Bearer legion-token');
    });

    it('能通过命令网关执行探索和发布风险写动作', async () => {
        saveControlAuthSession({ token: 'legion-token' });
        mockFetch
            .mockResolvedValueOnce(mockResponse({
                status: 'success',
                command_id: 'exploration.session.create',
                result: {
                    command_id: 'exploration.session.create',
                    risk_level: 'medium',
                    read_only: false,
                    run: { run_id: 'run-explore', status: 'succeeded' },
                    approval: null,
                    result: {
                        session: { session_id: 'session-1', project_key: 'demo' },
                    },
                },
            }))
            .mockResolvedValueOnce(mockResponse({
                status: 'success',
                sessions: [{ session_id: 'session-1', project_key: 'demo', status: 'completed', target_url: 'https://demo.example.com' }],
                count: 1,
            }))
            .mockResolvedValueOnce(mockResponse({
                status: 'success',
                assessments: [{
                    assessment_id: 'assessment-1',
                    project_key: 'demo',
                    environment: 'staging',
                    auto_release_eligible: true,
                    blockers: [],
                    evidence: {
                        review_summary: {
                            pending: 0,
                            confirmed: 0,
                            dismissed: 0,
                            active: 0,
                            effective: 1,
                        },
                    },
                    policy_hit: {
                        review_blocked: false,
                        review_policy_mode: 'conservative',
                    },
                }],
                count: 1,
            }));

        const execution = await executeCommand('exploration.session.create', {
            project_key: 'demo',
            target_url: 'https://demo.example.com',
            charter: '围绕登录链路做探索',
        });
        const sessions = await listExplorationSessions({ project_key: 'demo' });
        const assessments = await listReleaseRiskAssessments({ project_key: 'demo', auto_release_eligible: true });

        expect(execution.run.run_id).toBe('run-explore');
        expect(sessions.sessions[0].session_id).toBe('session-1');
        expect(assessments.assessments[0].assessment_id).toBe('assessment-1');
        expect(assessments.assessments[0].evidence.review_summary?.effective).toBe(1);
        expect(assessments.assessments[0].policy_hit.review_policy_mode).toBe('conservative');
        expect(mockFetch).toHaveBeenNthCalledWith(
            1,
            expect.stringContaining('/api/commander/commands/execute'),
            expect.objectContaining({
                method: 'POST',
                body: JSON.stringify({
                    command_id: 'exploration.session.create',
                    arguments: {
                        project_key: 'demo',
                        target_url: 'https://demo.example.com',
                        charter: '围绕登录链路做探索',
                    },
                    confirm: false,
                }),
            }),
        );
    });

    it('能读取探索发现详情、复核队列与 review_status 筛选', async () => {
        saveControlAuthSession({ token: 'legion-token' });
        mockFetch
            .mockResolvedValueOnce(mockResponse({
                status: 'success',
                session_id: 'session-1',
                findings: [{
                    finding_id: 'finding-1',
                    session_id: 'session-1',
                    project_key: 'demo',
                    severity: 'high',
                    finding_type: 'business',
                    title: '登录主链路需重点复核',
                    summary: '认证提示与失败重试链路需要人工复核。',
                    confidence: 0.74,
                    evidence: { impact_scope: '认证主链路' },
                    requires_human_review: true,
                    review_status: 'pending',
                    review_comment: '',
                    reviewed_by: '',
                    reviewed_at: '',
                    created_at: '2026-03-24T10:00:00',
                }],
                count: 1,
            }))
            .mockResolvedValueOnce(mockResponse({
                status: 'success',
                finding: {
                    finding_id: 'finding-1',
                    session_id: 'session-1',
                    project_key: 'demo',
                    severity: 'high',
                    finding_type: 'business',
                    title: '登录主链路需重点复核',
                    summary: '认证提示与失败重试链路需要人工复核。',
                    confidence: 0.74,
                    evidence: { impact_scope: '认证主链路' },
                    requires_human_review: true,
                    review_status: 'confirmed',
                    review_comment: '人工确认',
                    reviewed_by: 'alice',
                    reviewed_at: '2026-03-24T10:05:00',
                    created_at: '2026-03-24T10:00:00',
                },
            }))
            .mockResolvedValueOnce(mockResponse({
                status: 'success',
                review_status: 'pending',
                findings: [{
                    finding_id: 'finding-1',
                    session_id: 'session-1',
                    project_key: 'demo',
                    severity: 'high',
                    finding_type: 'business',
                    title: '登录主链路需重点复核',
                    summary: '认证提示与失败重试链路需要人工复核。',
                    confidence: 0.74,
                    evidence: { impact_scope: '认证主链路' },
                    requires_human_review: true,
                    review_status: 'pending',
                    review_comment: '',
                    reviewed_by: '',
                    reviewed_at: '',
                    created_at: '2026-03-24T10:00:00',
                }],
                count: 1,
            }));

        const findings = await listExplorationFindings('session-1', { review_status: 'pending', review_only: true });
        const finding = await getExplorationFinding('finding-1');
        const queue = await listExplorationReviewQueue({ project_key: 'demo', review_status: 'pending' });

        expect(findings.count).toBe(1);
        expect(finding.review_status).toBe('confirmed');
        expect(queue.review_status).toBe('pending');
        expect(String(mockFetch.mock.calls[0][0])).toContain('review_status=pending');
        expect(String(mockFetch.mock.calls[0][0])).toContain('review_only=true');
        expect(String(mockFetch.mock.calls[2][0])).toContain('/api/exploration/review-queue');
    });

    it('能获取、签发并撤销通知平台绑定', async () => {
        saveControlAuthSession({ token: 'legion-token' });
        mockFetch
            .mockResolvedValueOnce(mockResponse({
                status: 'success',
                binding: null,
                pending_code: null,
            }))
            .mockResolvedValueOnce(mockResponse({
                status: 'success',
                binding: null,
                pending_code: {
                    code: 'BIND-ABC123',
                    user_id: 'user_1',
                    username: 'alice',
                    status: 'issued',
                    created_at: '2026-03-24T12:00:00',
                    expires_at: '2026-03-24T12:10:00',
                    used_at: '',
                    revoked_at: '',
                    issued_by: 'user_1',
                },
            }))
            .mockResolvedValueOnce(mockResponse({
                status: 'success',
                revoked: true,
                binding: {
                    notification_platform_open_id: 'ou_demo',
                    user_id: 'user_1',
                    username: 'alice',
                    chat_id: 'oc_demo',
                    source: 'notification_platform',
                    status: 'active',
                    bound_at: '2026-03-24T12:01:00',
                    last_seen_at: '2026-03-24T12:02:00',
                    revoked_at: '',
                },
                pending_code: null,
                revoked_at: '2026-03-24T12:03:00',
            }));

        const me = await getNotificationPlatformBindingMe();
        const issued = await issueNotificationPlatformBindingCode();
        const revoked = await revokeNotificationPlatformBinding();

        expect(me.binding).toBeNull();
        expect(issued.pending_code?.code).toBe('BIND-ABC123');
        expect(revoked.revoked).toBe(true);
        expect(mockFetch).toHaveBeenNthCalledWith(
            2,
            expect.stringContaining('/api/commander/chatops/bindings/me/issue'),
            expect.objectContaining({ method: 'POST' }),
        );
        expect(mockFetch).toHaveBeenNthCalledWith(
            3,
            expect.stringContaining('/api/commander/chatops/bindings/me/revoke'),
            expect.objectContaining({ method: 'POST' }),
        );
    });
});
