import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockFetch = vi.fn();
global.fetch = mockFetch;

function mockResponse(body: unknown): Response {
    return {
        ok: true,
        status: 200,
        statusText: 'OK',
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
    cancelDeployJob,
    approveDeployApproval,
    aiAnalyzeRepo,
    fullDeployRepo,
    getDeployApprovalDetail,
    getDeployHistory,
    getDeployJobDetail,
    getProjects,
    getRecordDetail,
    getRepoLogs,
    listDeployAuditLogs,
    listDeployApprovals,
    listDeployJobs,
    rejectDeployApproval,
    requestFullDeployAll,
    requestFullDeployRepo,
} from '../services/deployService';
import { saveDeployAuthSession } from '../services/deployAuthService';

describe('deployService', () => {
    beforeEach(() => {
        mockFetch.mockReset();
        localStorage.clear();
    });

    it('能从 APIResponse.data.projects 解包项目列表', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            status: 'ok',
            message: 'success',
            data: {
                projects: [{ key: 'p1', name: '示例项目', repos: [], has_token: true }],
            },
        }));

        const projects = await getProjects();

        expect(projects).toHaveLength(1);
        expect(projects[0].key).toBe('p1');
    });

    it('兼容旧的裸 history 响应结构', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            history: [{ id: 'r1', status: 'success', logs: [] }],
        }));

        const history = await getDeployHistory();

        expect(history).toHaveLength(1);
        expect(history[0].id).toBe('r1');
    });

    it('能解包 fullDeployRepo 返回的 record_id', async () => {
        saveDeployAuthSession({ token: 'demo-token' });
        mockFetch.mockResolvedValue(mockResponse({
            status: 'ok',
            message: 'success',
            data: { repo_id: 'repo-1', record_id: 'rec-1' },
        }));

        const result = await fullDeployRepo('pk', 'rid');

        expect(result.repo_id).toBe('repo-1');
        expect(result.record_id).toBe('rec-1');
        expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/api/deploy/repo/pk/rid/full'),
            expect.objectContaining({
                headers: expect.any(Headers),
            }),
        );
        const headers = mockFetch.mock.calls[0][1]?.headers as Headers;
        expect(headers.get('Authorization')).toBe('Bearer demo-token');
    });

    it('能从包装响应中读取记录详情、日志和 AI 分析', async () => {
        mockFetch
            .mockResolvedValueOnce(mockResponse({
                status: 'ok',
                data: { record: { id: 'rec-2', status: 'running', logs: ['a'] } },
            }))
            .mockResolvedValueOnce(mockResponse({
                status: 'ok',
                data: { logs: ['line-1', 'line-2'] },
            }))
            .mockResolvedValueOnce(mockResponse({
                status: 'ok',
                data: {
                    analysis: {
                        tech_stack: 'Vue 3',
                        install_cmd: 'npm install',
                        start_cmd: 'npm run dev',
                        build_cmd: 'npm run build',
                        port: 81,
                        env_vars: {},
                        notes: '',
                        confidence: 0.9,
                        source: 'ai',
                    },
                },
            }));

        const record = await getRecordDetail('rec-2');
        const logs = await getRepoLogs('repo-1');
        const analysis = await aiAnalyzeRepo('pk', 'rid');

        expect(record.id).toBe('rec-2');
        expect(logs).toEqual(['line-1', 'line-2']);
        expect(analysis.source).toBe('ai');
        expect(analysis.port).toBe(81);
    });

    it('能创建仓库和项目级部署审批单', async () => {
        mockFetch
            .mockResolvedValueOnce(mockResponse({
                status: 'ok',
                data: { approval: { id: 'approval-repo', status: 'pending', repo_id: 'rid' } },
            }))
            .mockResolvedValueOnce(mockResponse({
                status: 'ok',
                data: { approval: { id: 'approval-project', status: 'pending', repo_id: '' } },
            }));

        const repoApproval = await requestFullDeployRepo('pk', 'rid', 'release');
        const projectApproval = await requestFullDeployAll('pk');

        expect(repoApproval.id).toBe('approval-repo');
        expect(projectApproval.id).toBe('approval-project');
        expect(mockFetch).toHaveBeenNthCalledWith(
            1,
            expect.stringContaining('/api/deploy/repo/pk/rid/full/request'),
            expect.objectContaining({
                method: 'POST',
                body: JSON.stringify({ branch: 'release' }),
            }),
        );
        expect(mockFetch).toHaveBeenNthCalledWith(
            2,
            expect.stringContaining('/api/deploy/repo/pk/deploy-all/request'),
            expect.objectContaining({ method: 'POST' }),
        );
    });

    it('能查询审批列表并提交批准与驳回动作', async () => {
        mockFetch
            .mockResolvedValueOnce(mockResponse({
                status: 'ok',
                data: { approvals: [{ id: 'approval-1', status: 'pending' }] },
            }))
            .mockResolvedValueOnce(mockResponse({
                status: 'ok',
                data: { approval: { id: 'approval-1', status: 'approved' } },
            }))
            .mockResolvedValueOnce(mockResponse({
                status: 'ok',
                data: { approval: { id: 'approval-2', status: 'rejected' } },
            }));

        const approvals = await listDeployApprovals('pending', 10);
        const approved = await approveDeployApproval('approval-1', '批准发布');
        const rejected = await rejectDeployApproval('approval-2', '窗口关闭');

        expect(approvals).toEqual([{ id: 'approval-1', status: 'pending' }]);
        expect(approved.status).toBe('approved');
        expect(rejected.status).toBe('rejected');
        expect(mockFetch).toHaveBeenNthCalledWith(
            1,
            expect.stringContaining('/api/deploy/approvals?status=pending&limit=10'),
            expect.objectContaining({
                headers: expect.any(Headers),
            }),
        );
        expect(mockFetch).toHaveBeenNthCalledWith(
            2,
            expect.stringContaining('/api/deploy/approvals/approval-1/approve'),
            expect.objectContaining({
                method: 'POST',
                body: JSON.stringify({ comment: '批准发布' }),
            }),
        );
        expect(mockFetch).toHaveBeenNthCalledWith(
            3,
            expect.stringContaining('/api/deploy/approvals/approval-2/reject'),
            expect.objectContaining({
                method: 'POST',
                body: JSON.stringify({ comment: '窗口关闭' }),
            }),
        );
    });

    it('能查询部署审计日志并携带筛选参数', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            status: 'ok',
            data: {
                logs: [{
                    log_id: 'audit-1',
                    user_id: 'user-1',
                    username: 'deploy-admin',
                    action: 'deploy_job_cancel',
                    resource_type: 'deploy_job',
                    resource_id: 'job-1',
                    project_key: 'demo',
                    details: { project_key: 'demo' },
                    timestamp: '2026-03-23T10:00:00',
                    ip_address: '127.0.0.1',
                }],
            },
        }));

        const logs = await listDeployAuditLogs({
            limit: 15,
            action: 'deploy_job_cancel',
            projectKey: 'demo',
            userId: 'user-1',
        });

        expect(logs).toHaveLength(1);
        expect(logs[0].log_id).toBe('audit-1');
        expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/api/deploy/audit?limit=15&action=deploy_job_cancel&project_key=demo&user_id=user-1'),
            expect.objectContaining({
                headers: expect.any(Headers),
            }),
        );
    });

    it('能读取部署审批详情与作业详情', async () => {
        mockFetch
            .mockResolvedValueOnce(mockResponse({
                status: 'ok',
                data: {
                    approval: {
                        id: 'approval-1',
                        status: 'approved',
                        repo_label: '后端服务',
                        record_id: 'record-1',
                    },
                },
            }))
            .mockResolvedValueOnce(mockResponse({
                status: 'ok',
                data: {
                    job: {
                        id: 'job-1',
                        status: 'success',
                        repo_label: '后端服务',
                        record_id: 'record-1',
                    },
                },
            }));

        const approval = await getDeployApprovalDetail('approval-1');
        const job = await getDeployJobDetail('job-1');

        expect(approval.id).toBe('approval-1');
        expect(approval.record_id).toBe('record-1');
        expect(job.id).toBe('job-1');
        expect(job.record_id).toBe('record-1');
        expect(mockFetch).toHaveBeenNthCalledWith(
            1,
            expect.stringContaining('/api/deploy/approvals/approval-1'),
            expect.objectContaining({
                headers: expect.any(Headers),
            }),
        );
        expect(mockFetch).toHaveBeenNthCalledWith(
            2,
            expect.stringContaining('/api/deploy/jobs/job-1'),
            expect.objectContaining({
                headers: expect.any(Headers),
            }),
        );
    });

    it('能查询部署作业列表并取消作业', async () => {
        mockFetch
            .mockResolvedValueOnce(mockResponse({
                status: 'ok',
                data: {
                    jobs: [{
                        id: 'job-1',
                        status: 'running',
                        repo_label: '后端服务',
                        record_id: 'record-1',
                    }],
                },
            }))
            .mockResolvedValueOnce(mockResponse({
                status: 'ok',
                data: {
                    job: {
                        id: 'job-1',
                        status: 'cancel_requested',
                        repo_label: '后端服务',
                        record_id: 'record-1',
                    },
                },
            }));

        const jobs = await listDeployJobs('running', 12);
        const cancelled = await cancelDeployJob('job-1');

        expect(jobs).toHaveLength(1);
        expect(jobs[0].id).toBe('job-1');
        expect(cancelled.status).toBe('cancel_requested');
        expect(mockFetch).toHaveBeenNthCalledWith(
            1,
            expect.stringContaining('/api/deploy/jobs?status=running&limit=12'),
            expect.objectContaining({
                headers: expect.any(Headers),
            }),
        );
        expect(mockFetch).toHaveBeenNthCalledWith(
            2,
            expect.stringContaining('/api/deploy/jobs/job-1/cancel'),
            expect.objectContaining({
                method: 'POST',
                headers: expect.any(Headers),
            }),
        );
    });
});
