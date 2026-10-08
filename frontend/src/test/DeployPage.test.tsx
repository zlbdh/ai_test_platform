import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const deployServiceMocks = vi.hoisted(() => ({
    getProjects: vi.fn(),
    cloneRepo: vi.fn(),
    installRepo: vi.fn(),
    startRepo: vi.fn(),
    stopRepo: vi.fn(),
    fullDeployRepo: vi.fn(),
    fullDeployAll: vi.fn(),
    getRepoLogs: vi.fn(),
    getDeployHistory: vi.fn(),
    deleteHistoryRecord: vi.fn(),
    clearHistory: vi.fn(),
    addProject: vi.fn(),
    updateProject: vi.fn(),
    deleteProject: vi.fn(),
    aiAnalyzeRepo: vi.fn(),
    applyAIConfig: vi.fn(),
    getRecordDetail: vi.fn(),
    aiRefineConfig: vi.fn(),
    requestFullDeployRepo: vi.fn(),
    requestFullDeployAll: vi.fn(),
    listDeployApprovals: vi.fn(),
    listDeployJobs: vi.fn(),
    listDeployAuditLogs: vi.fn(),
    approveDeployApproval: vi.fn(),
    rejectDeployApproval: vi.fn(),
    getDeployApprovalDetail: vi.fn(),
    getDeployJobDetail: vi.fn(),
    cancelDeployJob: vi.fn(),
}));

const authServiceMocks = vi.hoisted(() => {
    const state = {
        storedToken: '',
    };

    return {
        state,
        attachDeployToken: vi.fn(),
        clearDeployAuthSession: vi.fn(() => {
            state.storedToken = '';
        }),
        fetchDeployAuthProfile: vi.fn(),
        getStoredDeployAuthToken: vi.fn(() => state.storedToken),
        hasDeployPermission: vi.fn((profile: { permissions?: string[] } | null | undefined, permission: string) =>
            Boolean(profile && profile.permissions?.includes(permission))),
        loginDeployControl: vi.fn(),
        logoutDeployControl: vi.fn(),
    };
});

vi.mock('../services/deployService', () => ({
    getProjects: deployServiceMocks.getProjects,
    cloneRepo: deployServiceMocks.cloneRepo,
    installRepo: deployServiceMocks.installRepo,
    startRepo: deployServiceMocks.startRepo,
    stopRepo: deployServiceMocks.stopRepo,
    fullDeployRepo: deployServiceMocks.fullDeployRepo,
    fullDeployAll: deployServiceMocks.fullDeployAll,
    getRepoLogs: deployServiceMocks.getRepoLogs,
    getDeployHistory: deployServiceMocks.getDeployHistory,
    deleteHistoryRecord: deployServiceMocks.deleteHistoryRecord,
    clearHistory: deployServiceMocks.clearHistory,
    addProject: deployServiceMocks.addProject,
    updateProject: deployServiceMocks.updateProject,
    deleteProject: deployServiceMocks.deleteProject,
    aiAnalyzeRepo: deployServiceMocks.aiAnalyzeRepo,
    applyAIConfig: deployServiceMocks.applyAIConfig,
    getRecordDetail: deployServiceMocks.getRecordDetail,
    aiRefineConfig: deployServiceMocks.aiRefineConfig,
    requestFullDeployRepo: deployServiceMocks.requestFullDeployRepo,
    requestFullDeployAll: deployServiceMocks.requestFullDeployAll,
    listDeployApprovals: deployServiceMocks.listDeployApprovals,
    listDeployJobs: deployServiceMocks.listDeployJobs,
    listDeployAuditLogs: deployServiceMocks.listDeployAuditLogs,
    approveDeployApproval: deployServiceMocks.approveDeployApproval,
    rejectDeployApproval: deployServiceMocks.rejectDeployApproval,
    getDeployApprovalDetail: deployServiceMocks.getDeployApprovalDetail,
    getDeployJobDetail: deployServiceMocks.getDeployJobDetail,
    cancelDeployJob: deployServiceMocks.cancelDeployJob,
}));

vi.mock('../services/deployAuthService', () => ({
    attachDeployToken: authServiceMocks.attachDeployToken,
    clearDeployAuthSession: authServiceMocks.clearDeployAuthSession,
    fetchDeployAuthProfile: authServiceMocks.fetchDeployAuthProfile,
    getStoredDeployAuthToken: authServiceMocks.getStoredDeployAuthToken,
    hasDeployPermission: authServiceMocks.hasDeployPermission,
    loginDeployControl: authServiceMocks.loginDeployControl,
    logoutDeployControl: authServiceMocks.logoutDeployControl,
}));

import DeployPage from '../pages/DeployPage';

const sampleProject = {
    key: 'demo',
    name: '示例项目',
    has_token: true,
    repos: [
        {
            id: 'repo-1',
            label: '后端服务',
            repo_url: 'https://git.example.com/team/backend.git',
            tech_stack: 'FastAPI',
            local_dir: 'D:/deploy/backend',
            exists: true,
            status: 'cloned',
            port: 8020,
            port_open: false,
            pid: null,
            install_cmd: 'pip install -r requirements.txt',
            start_cmd: 'uvicorn main:app --host 0.0.0.0 --port 8020',
            branch: 'main',
            has_memory: false,
            deploy_count: 0,
        },
    ],
};

const sampleHistory = [
    {
        id: 'record-1',
        project_key: 'demo',
        repo_id: 'repo-1',
        repo_label: '后端服务',
        action: 'full',
        status: 'success',
        message: '部署成功',
        started_at: '2026-03-23T09:00:00',
        finished_at: '2026-03-23T09:05:00',
        duration_ms: 300000,
        logs: ['ok'],
    },
    {
        id: 'record-2',
        project_key: 'demo',
        repo_id: 'repo-2',
        repo_label: '前端门户',
        action: 'full',
        status: 'failed',
        message: '部署失败',
        started_at: '2026-03-23T09:10:00',
        finished_at: '2026-03-23T09:15:00',
        duration_ms: 300000,
        logs: ['failed'],
    },
];

const sampleApprovals = [
    {
        id: 'approval-1',
        action: 'full',
        project_key: 'demo',
        repo_id: 'repo-1',
        repo_label: '后端服务',
        branch: 'main',
        status: 'pending',
        message: '等待审批',
        requested_by: 'tester-1',
        requested_by_name: '测试同学',
        requested_at: '2026-03-23T10:00:00',
        reviewed_by: '',
        reviewed_by_name: '',
        reviewed_at: '',
        review_comment: '',
        job_id: '',
        record_id: '',
    },
    {
        id: 'approval-2',
        action: 'full',
        project_key: 'demo',
        repo_id: 'repo-2',
        repo_label: '前端门户',
        branch: 'release-ui',
        status: 'pending',
        message: '等待前端审批',
        requested_by: 'tester-2',
        requested_by_name: '前端测试',
        requested_at: '2026-03-23T10:30:00',
        reviewed_by: '',
        reviewed_by_name: '',
        reviewed_at: '',
        review_comment: '',
        job_id: '',
        record_id: '',
    },
];

const sampleJobs = [
    {
        id: 'job-9',
        action: 'full',
        project_key: 'demo',
        repo_id: 'repo-1',
        repo_label: '后端服务',
        record_id: 'record-9',
        branch: 'release/2026-03',
        status: 'running',
        message: '正在发布后端服务',
        created_at: '2026-03-23T10:10:00',
        started_at: '2026-03-23T10:11:00',
        finished_at: '',
        record_status: 'running',
        record_message: '发布中',
    },
    {
        id: 'job-2',
        action: 'full',
        project_key: 'demo',
        repo_id: 'repo-2',
        repo_label: '前端门户',
        record_id: 'record-2',
        branch: 'release-ui',
        status: 'success',
        message: '前端发布完成',
        created_at: '2026-03-23T10:12:00',
        started_at: '2026-03-23T10:13:00',
        finished_at: '2026-03-23T10:16:00',
        record_status: 'success',
        record_message: '发布成功',
    },
];

const sampleAuditLogs = [
    {
        log_id: 'audit-1',
        user_id: 'user-1',
        username: 'release-admin',
        action: 'deploy_approval_approve',
        resource_type: 'deploy_approval',
        resource_id: 'approval-1',
        project_key: 'demo',
        details: {
            project_key: 'demo',
            repo_label: '后端服务',
            comment: '窗口已确认',
            record_id: 'record-approved',
        },
        timestamp: '2026-03-23T10:05:00',
        ip_address: '127.0.0.1',
    },
];

const filteredAuditLogs = [
    {
        log_id: 'audit-2',
        user_id: 'user-2',
        username: 'release-operator',
        action: 'deploy_job_cancel',
        resource_type: 'deploy_job',
        resource_id: 'job-9',
        project_key: 'demo',
        details: {
            project_key: 'demo',
            job_id: 'job-9',
            comment: '人工终止',
            record_id: 'record-9',
        },
        timestamp: '2026-03-23T10:15:00',
        ip_address: '10.0.0.8',
    },
];

const sampleJobDetail = {
    id: 'job-9',
    action: 'full',
    project_key: 'demo',
    repo_id: 'repo-1',
    repo_label: '后端服务',
    record_id: 'record-9',
    branch: 'release/2026-03',
    status: 'cancelled',
    message: '人工终止部署',
    created_at: '2026-03-23T10:10:00',
    started_at: '2026-03-23T10:11:00',
    finished_at: '2026-03-23T10:15:00',
    record_status: 'cancelled',
    record_message: '部署已取消',
};

function makeProfile(overrides: Partial<{
    user_id: string;
    username: string;
    email: string;
    role: 'admin' | 'developer' | 'tester' | 'viewer';
    project_ids: string[];
    permissions: Array<'deploy_view' | 'deploy_request' | 'deploy_approve' | 'admin'>;
    token: string;
    expires_at: string;
}> = {}) {
    return {
        user_id: 'user-1',
        username: 'deploy-admin',
        email: 'deploy@example.com',
        role: 'admin' as const,
        project_ids: ['demo'],
        permissions: ['deploy_view', 'deploy_request', 'deploy_approve', 'admin'] as Array<'deploy_view' | 'deploy_request' | 'deploy_approve' | 'admin'>,
        token: 'token-admin',
        expires_at: '2026-03-23T18:00:00',
        ...overrides,
    };
}

async function waitForDeployPageReady() {
    await waitFor(() => {
        expect(screen.queryByText('加载中...')).not.toBeInTheDocument();
    });
}

describe('DeployPage', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        localStorage.clear();
        authServiceMocks.state.storedToken = '';

        deployServiceMocks.getProjects.mockResolvedValue([]);
        deployServiceMocks.getDeployHistory.mockResolvedValue([]);
        deployServiceMocks.listDeployApprovals.mockResolvedValue([]);
        deployServiceMocks.getRepoLogs.mockResolvedValue([]);
        deployServiceMocks.getRecordDetail.mockResolvedValue(null);
        deployServiceMocks.cloneRepo.mockResolvedValue({});
        deployServiceMocks.installRepo.mockResolvedValue({});
        deployServiceMocks.startRepo.mockResolvedValue({});
        deployServiceMocks.stopRepo.mockResolvedValue({});
        deployServiceMocks.fullDeployRepo.mockResolvedValue({ repo_id: 'repo-1', record_id: 'record-1' });
        deployServiceMocks.fullDeployAll.mockResolvedValue({});
        deployServiceMocks.deleteHistoryRecord.mockResolvedValue(undefined);
        deployServiceMocks.clearHistory.mockResolvedValue(undefined);
        deployServiceMocks.addProject.mockResolvedValue(undefined);
        deployServiceMocks.updateProject.mockResolvedValue(undefined);
        deployServiceMocks.deleteProject.mockResolvedValue(undefined);
        deployServiceMocks.aiAnalyzeRepo.mockResolvedValue({ error: 'skip' });
        deployServiceMocks.applyAIConfig.mockResolvedValue(undefined);
        deployServiceMocks.aiRefineConfig.mockResolvedValue({});
        deployServiceMocks.requestFullDeployRepo.mockResolvedValue({});
        deployServiceMocks.requestFullDeployAll.mockResolvedValue({});
        deployServiceMocks.listDeployAuditLogs.mockResolvedValue([]);
        deployServiceMocks.listDeployJobs.mockResolvedValue([]);
        deployServiceMocks.approveDeployApproval.mockResolvedValue({});
        deployServiceMocks.rejectDeployApproval.mockResolvedValue({});
        deployServiceMocks.getDeployApprovalDetail.mockResolvedValue(sampleApprovals[0]);
        deployServiceMocks.getDeployJobDetail.mockResolvedValue(sampleJobDetail);
        deployServiceMocks.cancelDeployJob.mockResolvedValue({
            ...sampleJobDetail,
            status: 'cancel_requested',
            message: '已提交取消请求',
        });

        authServiceMocks.fetchDeployAuthProfile.mockResolvedValue(null);
        authServiceMocks.attachDeployToken.mockResolvedValue(makeProfile());
        authServiceMocks.loginDeployControl.mockResolvedValue(makeProfile());
        authServiceMocks.logoutDeployControl.mockResolvedValue(undefined);

        vi.stubGlobal('confirm', vi.fn(() => true));
    });

    it('未登录时展示认证入口并禁用管理动作', async () => {
        render(<DeployPage />);
        await waitForDeployPageReady();

        expect(screen.getByText('部署控制面认证')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: '登录部署控制面' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: '保存并校验 Token' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: '添加项目' })).toBeDisabled();
        expect(screen.getByRole('button', { name: '添加第一个项目' })).toBeDisabled();
        expect(deployServiceMocks.getProjects).not.toHaveBeenCalled();
    });

    it('开发免登录旁路开启时，无 token 也会直接加载部署面板', async () => {
        authServiceMocks.fetchDeployAuthProfile.mockResolvedValue(makeProfile({
            token: '',
        }));
        deployServiceMocks.getProjects.mockResolvedValue([sampleProject]);
        deployServiceMocks.getDeployHistory.mockResolvedValue(sampleHistory);
        deployServiceMocks.listDeployApprovals.mockResolvedValue(sampleApprovals);
        deployServiceMocks.listDeployJobs.mockResolvedValue(sampleJobs);
        deployServiceMocks.listDeployAuditLogs.mockResolvedValue(sampleAuditLogs);

        render(<DeployPage />);

        expect(await screen.findByText('示例项目')).toBeInTheDocument();
        expect(screen.getByText('开发免登录')).toBeInTheDocument();
        expect(screen.getByText('当前处于本地开发免登录模式，已自动附加开发用户权限，可直接验证部署链路。')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: '登录部署控制面' })).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: '退出认证' })).not.toBeInTheDocument();
        expect(screen.getByRole('button', { name: '添加项目' })).toBeEnabled();
    });

    it('无部署查看权限时给出明确提示且不拉取部署数据', async () => {
        authServiceMocks.state.storedToken = 'viewer-token';
        authServiceMocks.fetchDeployAuthProfile.mockResolvedValue(makeProfile({
            username: 'viewer-user',
            role: 'viewer',
            permissions: [],
            project_ids: ['proj-locked'],
            token: 'viewer-token',
        }));

        render(<DeployPage />);

        expect(await screen.findByText('当前角色没有部署查看权限，可登录其他账号或联系管理员开通 deploy_view。')).toBeInTheDocument();
        expect(screen.getByText('角色：viewer')).toBeInTheDocument();
        expect(deployServiceMocks.getProjects).not.toHaveBeenCalled();
        expect(deployServiceMocks.getDeployHistory).not.toHaveBeenCalled();
        expect(deployServiceMocks.listDeployApprovals).not.toHaveBeenCalled();
    });

    it('只读权限可查看项目，但不能申请或直接执行部署', async () => {
        authServiceMocks.state.storedToken = 'tester-token';
        authServiceMocks.fetchDeployAuthProfile.mockResolvedValue(makeProfile({
            username: 'tester-user',
            role: 'tester',
            permissions: ['deploy_view'],
            project_ids: ['demo'],
            token: 'tester-token',
        }));
        deployServiceMocks.getProjects.mockResolvedValue([sampleProject]);
        deployServiceMocks.getDeployHistory.mockResolvedValue(sampleHistory);
        deployServiceMocks.listDeployJobs.mockResolvedValue(sampleJobs);
        deployServiceMocks.listDeployAuditLogs.mockResolvedValue(sampleAuditLogs);

        render(<DeployPage />);

        expect(await screen.findByText('示例项目')).toBeInTheDocument();
        expect(await screen.findByText('部署历史')).toBeInTheDocument();
        expect(screen.getByText('部署作业')).toBeInTheDocument();
        expect(screen.getByText('部署审计')).toBeInTheDocument();
        expect(screen.getByText('项目范围')).toBeInTheDocument();
        expect(screen.getAllByText('demo').length).toBeGreaterThan(0);
        expect(screen.getByRole('button', { name: '添加项目' })).toBeDisabled();
        expect(screen.getByRole('button', { name: '申请全部审批' })).toBeDisabled();
        expect(screen.getByRole('button', { name: '全部直接部署' })).toBeDisabled();
        expect(screen.getByRole('button', { name: '申请审批部署' })).toBeDisabled();
        expect(screen.getByRole('button', { name: '直接部署' })).toBeDisabled();
        expect(screen.getByRole('button', { name: '清空全部' })).toBeDisabled();
    });

    it('管理员权限下展示审批动作并开放部署控制按钮', async () => {
        authServiceMocks.state.storedToken = 'admin-token';
        authServiceMocks.fetchDeployAuthProfile.mockResolvedValue(makeProfile({
            username: 'release-admin',
            token: 'admin-token',
        }));
        deployServiceMocks.getProjects.mockResolvedValue([sampleProject]);
        deployServiceMocks.getDeployHistory.mockResolvedValue(sampleHistory);
        deployServiceMocks.listDeployApprovals.mockResolvedValue(sampleApprovals);
        deployServiceMocks.listDeployJobs.mockResolvedValue(sampleJobs);
        deployServiceMocks.listDeployAuditLogs.mockResolvedValue(sampleAuditLogs);

        render(<DeployPage />);

        expect(await screen.findByText('示例项目')).toBeInTheDocument();
        expect(screen.getByText('角色：admin')).toBeInTheDocument();
        expect(screen.getByText('全部项目（管理员）')).toBeInTheDocument();
        expect(screen.getByText('活跃作业')).toBeInTheDocument();
        expect(screen.getAllByText('审批通过').length).toBeGreaterThan(0);
        expect(screen.getByText(/窗口已确认/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: '添加项目' })).toBeEnabled();
        expect(screen.getByRole('button', { name: '申请全部审批' })).toBeEnabled();
        expect(screen.getByRole('button', { name: '全部直接部署' })).toBeEnabled();
        expect(screen.getByRole('button', { name: '申请审批部署' })).toBeEnabled();
        expect(screen.getByRole('button', { name: '直接部署' })).toBeEnabled();
        expect(screen.getAllByTitle('批准').length).toBeGreaterThan(0);
        expect(screen.getAllByTitle('驳回').length).toBeGreaterThan(0);
    });

    it('批准审批后会启动部署跟踪并展示进度面板', async () => {
        authServiceMocks.state.storedToken = 'admin-token';
        authServiceMocks.fetchDeployAuthProfile.mockResolvedValue(makeProfile({
            username: 'release-admin',
            token: 'admin-token',
        }));
        deployServiceMocks.getProjects.mockResolvedValue([sampleProject]);
        deployServiceMocks.getDeployHistory.mockResolvedValue(sampleHistory);
        deployServiceMocks.listDeployApprovals.mockResolvedValue(sampleApprovals);
        deployServiceMocks.listDeployJobs.mockResolvedValue(sampleJobs);
        deployServiceMocks.listDeployAuditLogs.mockResolvedValue(sampleAuditLogs);
        deployServiceMocks.approveDeployApproval.mockResolvedValue({
            ...sampleApprovals[0],
            status: 'approved',
            review_comment: '窗口已确认',
            record_id: 'record-approved',
        });
        deployServiceMocks.getRecordDetail.mockResolvedValue({
            ...sampleHistory[0],
            id: 'record-approved',
            status: 'success',
            message: '部署成功',
            logs: ['✅ 审批已通过，部署任务已启动...', '✅ 部署完成'],
            steps: [
                { name: 'clone', status: 'success', message: '仓库已克隆', duration_ms: 1000, logs: [] },
                { name: 'install', status: 'success', message: '依赖安装完成', duration_ms: 2000, logs: [] },
                { name: 'start', status: 'success', message: '服务启动完成', duration_ms: 1000, logs: [] },
            ],
        });

        render(<DeployPage />);

        expect(await screen.findByText('示例项目')).toBeInTheDocument();

        fireEvent.click(screen.getAllByTitle('批准')[0]);
        expect(await screen.findByText('Approve deployment')).toBeInTheDocument();

        fireEvent.change(screen.getByPlaceholderText('Example: The deployment window is confirmed. Proceed.'), {
            target: { value: '窗口已确认' },
        });
        vi.useFakeTimers();
        try {
            fireEvent.click(screen.getByRole('button', { name: 'Confirm approval' }));

            await act(async () => {
                await Promise.resolve();
                await Promise.resolve();
            });

            expect(deployServiceMocks.approveDeployApproval).toHaveBeenCalledWith('approval-1', '窗口已确认');
            expect(screen.getByText('Direct deployment · 后端服务')).toBeInTheDocument();
            expect(screen.getByText('✅ 审批已通过，部署任务已启动...')).toBeInTheDocument();

            await act(async () => {
                await vi.advanceTimersByTimeAsync(2000);
                await Promise.resolve();
            });

            expect(deployServiceMocks.getRecordDetail).toHaveBeenCalledWith('record-approved');
            expect(screen.getByText('✅ 部署完成')).toBeInTheDocument();
        } finally {
            vi.useRealTimers();
        }
    });

    it('支持筛选部署审计并查看详情', async () => {
        authServiceMocks.state.storedToken = 'admin-token';
        authServiceMocks.fetchDeployAuthProfile.mockResolvedValue(makeProfile({
            username: 'release-admin',
            token: 'admin-token',
        }));
        deployServiceMocks.getProjects.mockResolvedValue([sampleProject]);
        deployServiceMocks.getDeployHistory.mockResolvedValue(sampleHistory);
        deployServiceMocks.listDeployApprovals.mockResolvedValue(sampleApprovals);
        deployServiceMocks.listDeployJobs.mockResolvedValue(sampleJobs);
        deployServiceMocks.listDeployAuditLogs
            .mockResolvedValueOnce(sampleAuditLogs)
            .mockResolvedValueOnce(filteredAuditLogs);

        render(<DeployPage />);

        expect(await screen.findByText('部署审计')).toBeInTheDocument();
        expect(screen.getAllByText('审批通过').length).toBeGreaterThan(0);

        fireEvent.change(screen.getByLabelText('审计动作筛选'), {
            target: { value: 'deploy_job_cancel' },
        });
        fireEvent.change(screen.getByLabelText('审计操作人筛选'), {
            target: { value: 'user-2' },
        });
        fireEvent.click(screen.getByRole('button', { name: '筛选审计' }));

        await waitFor(() => {
            expect(deployServiceMocks.listDeployAuditLogs).toHaveBeenLastCalledWith({
                limit: 20,
                action: 'deploy_job_cancel',
                projectKey: '',
                userId: 'user-2',
            });
        });

        expect(await screen.findByText('release-operator')).toBeInTheDocument();
        fireEvent.click(screen.getByText('release-operator'));

        expect(await screen.findByText('审计详情')).toBeInTheDocument();
        expect(screen.getAllByText('release-operator').length).toBeGreaterThan(0);
        expect(screen.getAllByText('job-9').length).toBeGreaterThan(0);
        expect(screen.getAllByText(/人工终止/).length).toBeGreaterThan(0);
    });

    it('支持从审计详情联动审批单、作业和部署记录', async () => {
        authServiceMocks.state.storedToken = 'admin-token';
        authServiceMocks.fetchDeployAuthProfile.mockResolvedValue(makeProfile({
            username: 'release-admin',
            token: 'admin-token',
        }));
        deployServiceMocks.getProjects.mockResolvedValue([sampleProject]);
        deployServiceMocks.getDeployHistory.mockResolvedValue(sampleHistory);
        deployServiceMocks.listDeployApprovals.mockResolvedValue(sampleApprovals);
        deployServiceMocks.listDeployJobs.mockResolvedValue(sampleJobs);
        deployServiceMocks.listDeployAuditLogs.mockResolvedValue([
            ...sampleAuditLogs,
            ...filteredAuditLogs,
        ]);
        deployServiceMocks.getDeployApprovalDetail.mockResolvedValue({
            ...sampleApprovals[0],
            status: 'approved',
            reviewed_by_name: '发布负责人',
            review_comment: '窗口已确认',
            record_id: 'record-approved',
            record_status: 'success',
        });
        deployServiceMocks.getDeployJobDetail.mockResolvedValue(sampleJobDetail);
        deployServiceMocks.getRecordDetail.mockResolvedValue({
            ...sampleHistory[0],
            id: 'record-9',
            status: 'cancelled',
            message: '部署已取消',
            logs: ['🔍 从审计详情打开部署记录...', '⏹ 已取消'],
            steps: [
                { name: 'clone', status: 'success', message: '仓库已克隆', duration_ms: 1000, logs: [] },
                { name: 'install', status: 'success', message: '依赖安装完成', duration_ms: 1000, logs: [] },
                { name: 'start', status: 'skipped', message: '任务已取消', duration_ms: 0, logs: [] },
            ],
        });

        render(<DeployPage />);

        expect(await screen.findByText('部署审计')).toBeInTheDocument();

        fireEvent.click(screen.getByText(/窗口已确认/));
        expect(await screen.findByText('审计详情')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: '查看审批单' }));

        await waitFor(() => {
            expect(deployServiceMocks.getDeployApprovalDetail).toHaveBeenCalledWith('approval-1');
        });
        expect(await screen.findByText('关联审批单')).toBeInTheDocument();
        expect(screen.getByText('发布负责人')).toBeInTheDocument();
        expect(screen.getByText('已定位审批单 approval-1')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: '筛选审批上下文' }));
        expect(await screen.findByText(/仅显示审批单/)).toBeInTheDocument();
        expect(screen.queryByText('approval-2')).not.toBeInTheDocument();

        fireEvent.click(screen.getByText(/人工终止/));
        fireEvent.click(screen.getByRole('button', { name: '查看作业' }));

        await waitFor(() => {
            expect(deployServiceMocks.getDeployJobDetail).toHaveBeenCalledWith('job-9');
        });
        expect(await screen.findByText('关联作业')).toBeInTheDocument();
        expect(screen.getAllByText('人工终止部署').length).toBeGreaterThan(0);
        expect(screen.getByText('已定位作业 job-9')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: '筛选作业上下文' }));
        expect(await screen.findByText(/仅显示作业/)).toBeInTheDocument();
        expect(screen.queryByText('job-2')).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: '筛选部署上下文' }));
        expect(await screen.findByText(/仅显示记录/)).toBeInTheDocument();
        expect(screen.queryByText('record-2')).not.toBeInTheDocument();

        vi.useFakeTimers();
        try {
            fireEvent.click(screen.getByRole('button', { name: '打开部署记录' }));

            await act(async () => {
                await Promise.resolve();
                await Promise.resolve();
            });

            expect(deployServiceMocks.getRecordDetail).toHaveBeenCalledWith('record-9');
            expect(screen.getByText('Direct deployment · 后端服务')).toBeInTheDocument();
            expect(screen.getByText('🔍 从审计详情打开部署记录...')).toBeInTheDocument();
            expect(screen.getByText('已定位记录 record-9')).toBeInTheDocument();

            await act(async () => {
                await vi.advanceTimersByTimeAsync(2000);
                await Promise.resolve();
            });

            expect(screen.getByText('部署已取消')).toBeInTheDocument();
        } finally {
            vi.useRealTimers();
        }
    });

    it('支持从作业列表取消运行中的部署作业', async () => {
        authServiceMocks.state.storedToken = 'admin-token';
        authServiceMocks.fetchDeployAuthProfile.mockResolvedValue(makeProfile({
            username: 'release-admin',
            token: 'admin-token',
        }));
        deployServiceMocks.getProjects.mockResolvedValue([sampleProject]);
        deployServiceMocks.getDeployHistory.mockResolvedValue(sampleHistory);
        deployServiceMocks.listDeployApprovals.mockResolvedValue(sampleApprovals);
        deployServiceMocks.listDeployJobs
            .mockResolvedValueOnce(sampleJobs)
            .mockResolvedValue([{ ...sampleJobs[0], status: 'cancel_requested', message: '已提交取消请求' }, sampleJobs[1]]);
        deployServiceMocks.listDeployAuditLogs.mockResolvedValue(sampleAuditLogs);
        deployServiceMocks.cancelDeployJob.mockResolvedValue({
            ...sampleJobs[0],
            status: 'cancel_requested',
            message: '已提交取消请求',
        });

        render(<DeployPage />);

        expect(await screen.findByText('部署作业')).toBeInTheDocument();
        fireEvent.click(screen.getByTitle('取消作业'));

        await waitFor(() => {
            expect(deployServiceMocks.cancelDeployJob).toHaveBeenCalledWith('job-9');
        });
        await waitFor(() => {
            expect(screen.getAllByText('取消中').length).toBeGreaterThan(0);
        });
    });
});
