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
    name: "Sample project",
    has_token: true,
    repos: [
        {
            id: 'repo-1',
            label: "Backend service",
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
        repo_label: "Backend service",
        action: 'full',
        status: 'success',
        message: "Deployment succeeded",
        started_at: '2026-03-23T09:00:00',
        finished_at: '2026-03-23T09:05:00',
        duration_ms: 300000,
        logs: ['ok'],
    },
    {
        id: 'record-2',
        project_key: 'demo',
        repo_id: 'repo-2',
        repo_label: "Frontend portal",
        action: 'full',
        status: 'failed',
        message: "Deployment failed",
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
        repo_label: "Backend service",
        branch: 'main',
        status: 'pending',
        message: "Awaiting approval",
        requested_by: 'tester-1',
        requested_by_name: "Test operator",
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
        repo_label: "Frontend portal",
        branch: 'release-ui',
        status: 'pending',
        message: "Awaiting frontend approval",
        requested_by: 'tester-2',
        requested_by_name: "Frontend test",
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
        repo_label: "Backend service",
        record_id: 'record-9',
        branch: 'release/2026-03',
        status: 'running',
        message: "Deploying the backend service",
        created_at: '2026-03-23T10:10:00',
        started_at: '2026-03-23T10:11:00',
        finished_at: '',
        record_status: 'running',
        record_message: "Deploying",
    },
    {
        id: 'job-2',
        action: 'full',
        project_key: 'demo',
        repo_id: 'repo-2',
        repo_label: "Frontend portal",
        record_id: 'record-2',
        branch: 'release-ui',
        status: 'success',
        message: "Frontend deployment completed",
        created_at: '2026-03-23T10:12:00',
        started_at: '2026-03-23T10:13:00',
        finished_at: '2026-03-23T10:16:00',
        record_status: 'success',
        record_message: "Release succeeded",
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
            repo_label: "Backend service",
            comment: "Window confirmed",
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
            comment: "Manually stopped",
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
    repo_label: "Backend service",
    record_id: 'record-9',
    branch: 'release/2026-03',
    status: 'cancelled',
    message: "Manually stop deployment",
    created_at: '2026-03-23T10:10:00',
    started_at: '2026-03-23T10:11:00',
    finished_at: '2026-03-23T10:15:00',
    record_status: 'cancelled',
    record_message: "Deployment canceled",
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
        expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
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
            message: "Cancellation request submitted",
        });

        authServiceMocks.fetchDeployAuthProfile.mockResolvedValue(null);
        authServiceMocks.attachDeployToken.mockResolvedValue(makeProfile());
        authServiceMocks.loginDeployControl.mockResolvedValue(makeProfile());
        authServiceMocks.logoutDeployControl.mockResolvedValue(undefined);

        vi.stubGlobal('confirm', vi.fn(() => true));
    });

    it("shows authentication and disables management actions when signed out", async () => {
        render(<DeployPage />);
        await waitForDeployPageReady();

        expect(screen.getByText("Deployment control authentication")).toBeInTheDocument();
        expect(screen.getByRole('button', { name: "Sign in to deployment control" })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: "Save and validate token" })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: "Add project" })).toBeDisabled();
        expect(screen.getByRole('button', { name: "Add your first project" })).toBeDisabled();
        expect(deployServiceMocks.getProjects).not.toHaveBeenCalled();
    });

    it("loads the deployment panel without a token when the development authentication bypass is enabled", async () => {
        authServiceMocks.fetchDeployAuthProfile.mockResolvedValue(makeProfile({
            token: '',
        }));
        deployServiceMocks.getProjects.mockResolvedValue([sampleProject]);
        deployServiceMocks.getDeployHistory.mockResolvedValue(sampleHistory);
        deployServiceMocks.listDeployApprovals.mockResolvedValue(sampleApprovals);
        deployServiceMocks.listDeployJobs.mockResolvedValue(sampleJobs);
        deployServiceMocks.listDeployAuditLogs.mockResolvedValue(sampleAuditLogs);

        render(<DeployPage />);

        expect(await screen.findByText("Sample project")).toBeInTheDocument();
        expect(screen.getByText("Development sign-in bypass")).toBeInTheDocument();
        expect(screen.getByText("Local development mode bypasses sign-in and automatically attaches developer permissions so you can test the deployment flow.")).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: "Sign in to deployment control" })).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: "Sign out" })).not.toBeInTheDocument();
        expect(screen.getByRole('button', { name: "Add project" })).toBeEnabled();
    });

    it("shows a clear permission message without fetching deployment data when viewing is denied", async () => {
        authServiceMocks.state.storedToken = 'viewer-token';
        authServiceMocks.fetchDeployAuthProfile.mockResolvedValue(makeProfile({
            username: 'viewer-user',
            role: 'viewer',
            permissions: [],
            project_ids: ['proj-locked'],
            token: 'viewer-token',
        }));

        render(<DeployPage />);

        expect(await screen.findByText("Your role lacks deployment viewing permission. Sign in with another account or ask an administrator for deploy_view.")).toBeInTheDocument();
        expect(screen.getByText("Role: viewer")).toBeInTheDocument();
        expect(deployServiceMocks.getProjects).not.toHaveBeenCalled();
        expect(deployServiceMocks.getDeployHistory).not.toHaveBeenCalled();
        expect(deployServiceMocks.listDeployApprovals).not.toHaveBeenCalled();
    });

    it("allows read-only users to view projects but not request or directly execute deployments", async () => {
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

        expect(await screen.findByText("Sample project")).toBeInTheDocument();
        expect(await screen.findByText("Deployment history")).toBeInTheDocument();
        expect(screen.getByText("Deployment jobs")).toBeInTheDocument();
        expect(screen.getByText("Deployment audit")).toBeInTheDocument();
        expect(screen.getByText("Project scope")).toBeInTheDocument();
        expect(screen.getAllByText('demo').length).toBeGreaterThan(0);
        expect(screen.getByRole('button', { name: "Add project" })).toBeDisabled();
        expect(screen.getByRole('button', { name: "Request approval for all" })).toBeDisabled();
        expect(screen.getByRole('button', { name: "Deploy all directly" })).toBeDisabled();
        expect(screen.getByRole('button', { name: "Request deployment approval" })).toBeDisabled();
        expect(screen.getByRole('button', { name: "Direct deployment" })).toBeDisabled();
        expect(screen.getByRole('button', { name: "Clear all" })).toBeDisabled();
    });

    it("shows approval actions and deployment controls for administrators", async () => {
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

        expect(await screen.findByText("Sample project")).toBeInTheDocument();
        expect(screen.getByText("Role: admin")).toBeInTheDocument();
        expect(screen.getByText("All projects (administrator)")).toBeInTheDocument();
        expect(screen.getByText("Active jobs")).toBeInTheDocument();
        expect(screen.getAllByText("Approval granted").length).toBeGreaterThan(0);
        expect(screen.getByText(/Window confirmed/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: "Add project" })).toBeEnabled();
        expect(screen.getByRole('button', { name: "Request approval for all" })).toBeEnabled();
        expect(screen.getByRole('button', { name: "Deploy all directly" })).toBeEnabled();
        expect(screen.getByRole('button', { name: "Request deployment approval" })).toBeEnabled();
        expect(screen.getByRole('button', { name: "Direct deployment" })).toBeEnabled();
        expect(screen.getAllByTitle("Approve").length).toBeGreaterThan(0);
        expect(screen.getAllByTitle("Reject").length).toBeGreaterThan(0);
    });

    it("starts deployment tracking and shows progress after approval", async () => {
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
            review_comment: "Window confirmed",
            record_id: 'record-approved',
        });
        deployServiceMocks.getRecordDetail.mockResolvedValue({
            ...sampleHistory[0],
            id: 'record-approved',
            status: 'success',
            message: "Deployment succeeded",
            logs: ["✅ Approval granted; deployment task started...", "✅ Deployment completed"],
            steps: [
                { name: 'clone', status: 'success', message: "Repository cloned", duration_ms: 1000, logs: [] },
                { name: 'install', status: 'success', message: "Dependencies installed", duration_ms: 2000, logs: [] },
                { name: 'start', status: 'success', message: "Service started", duration_ms: 1000, logs: [] },
            ],
        });

        render(<DeployPage />);

        expect(await screen.findByText("Sample project")).toBeInTheDocument();

        fireEvent.click(screen.getAllByTitle("Approve")[0]);
        expect(await screen.findByText("Approve deployment")).toBeInTheDocument();

        fireEvent.change(screen.getByPlaceholderText("Example: The deployment window is confirmed. Proceed."), {
            target: { value: "Window confirmed" },
        });
        vi.useFakeTimers();
        try {
            fireEvent.click(screen.getByRole('button', { name: "Confirm approval" }));

            await act(async () => {
                await Promise.resolve();
                await Promise.resolve();
            });

            expect(deployServiceMocks.approveDeployApproval).toHaveBeenCalledWith('approval-1', "Window confirmed");
            expect(screen.getByText("Direct deployment · Backend service")).toBeInTheDocument();
            expect(screen.getByText("✅ Approval granted; deployment task started...")).toBeInTheDocument();

            await act(async () => {
                await vi.advanceTimersByTimeAsync(2000);
                await Promise.resolve();
            });

            expect(deployServiceMocks.getRecordDetail).toHaveBeenCalledWith('record-approved');
            expect(screen.getByText("✅ Deployment completed")).toBeInTheDocument();
        } finally {
            vi.useRealTimers();
        }
    });

    it("supports filtering deployment audits and viewing details", async () => {
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

        expect(await screen.findByText("Deployment audit")).toBeInTheDocument();
        expect(screen.getAllByText("Approval granted").length).toBeGreaterThan(0);

        fireEvent.change(screen.getByLabelText("Filter audit actions"), {
            target: { value: 'deploy_job_cancel' },
        });
        fireEvent.change(screen.getByLabelText("Filter audit operators"), {
            target: { value: 'user-2' },
        });
        fireEvent.click(screen.getByRole('button', { name: "Filter audit" }));

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

        expect(await screen.findByText("Audit details")).toBeInTheDocument();
        expect(screen.getAllByText('release-operator').length).toBeGreaterThan(0);
        expect(screen.getAllByText('job-9').length).toBeGreaterThan(0);
        expect(screen.getAllByText(/Manually stopped/).length).toBeGreaterThan(0);
    });

    it("links audit details to approval requests, jobs, and deployment records", async () => {
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
            reviewed_by_name: "Release owner",
            review_comment: "Window confirmed",
            record_id: 'record-approved',
            record_status: 'success',
        });
        deployServiceMocks.getDeployJobDetail.mockResolvedValue(sampleJobDetail);
        deployServiceMocks.getRecordDetail.mockResolvedValue({
            ...sampleHistory[0],
            id: 'record-9',
            status: 'cancelled',
            message: "Deployment canceled",
            logs: ["🔍 Opening deployment record from audit details...", "⏹ Canceled"],
            steps: [
                { name: 'clone', status: 'success', message: "Repository cloned", duration_ms: 1000, logs: [] },
                { name: 'install', status: 'success', message: "Dependencies installed", duration_ms: 1000, logs: [] },
                { name: 'start', status: 'skipped', message: "Task canceled", duration_ms: 0, logs: [] },
            ],
        });

        render(<DeployPage />);

        expect(await screen.findByText("Deployment audit")).toBeInTheDocument();

        fireEvent.click(screen.getByText(/Window confirmed/));
        expect(await screen.findByText("Audit details")).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: "View approval request" }));

        await waitFor(() => {
            expect(deployServiceMocks.getDeployApprovalDetail).toHaveBeenCalledWith('approval-1');
        });
        expect(await screen.findByText("Linked approval request")).toBeInTheDocument();
        expect(screen.getByText("Release owner")).toBeInTheDocument();
        expect(screen.getByText("Located approval request approval-1")).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: "Filter approval context" }));
        expect(await screen.findByText(/Showing only approval request/)).toBeInTheDocument();
        expect(screen.queryByText('approval-2')).not.toBeInTheDocument();

        fireEvent.click(screen.getByText(/Manually stopped/));
        fireEvent.click(screen.getByRole('button', { name: "View job" }));

        await waitFor(() => {
            expect(deployServiceMocks.getDeployJobDetail).toHaveBeenCalledWith('job-9');
        });
        expect(await screen.findByText("Linked job")).toBeInTheDocument();
        expect(screen.getAllByText("Manually stop deployment").length).toBeGreaterThan(0);
        expect(screen.getByText("Located job job-9")).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: "Filter job context" }));
        expect(await screen.findByText(/Showing only job/)).toBeInTheDocument();
        expect(screen.queryByText('job-2')).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: "Filter deployment context" }));
        expect(await screen.findByText(/Showing only record/)).toBeInTheDocument();
        expect(screen.queryByText('record-2')).not.toBeInTheDocument();

        vi.useFakeTimers();
        try {
            fireEvent.click(screen.getByRole('button', { name: "Open deployment record" }));

            await act(async () => {
                await Promise.resolve();
                await Promise.resolve();
            });

            expect(deployServiceMocks.getRecordDetail).toHaveBeenCalledWith('record-9');
            expect(screen.getByText("Direct deployment · Backend service")).toBeInTheDocument();
            expect(screen.getByText("🔍 Opening deployment record from audit details...")).toBeInTheDocument();
            expect(screen.getByText("Located record record-9")).toBeInTheDocument();

            await act(async () => {
                await vi.advanceTimersByTimeAsync(2000);
                await Promise.resolve();
            });

            expect(screen.getByText("Deployment canceled")).toBeInTheDocument();
        } finally {
            vi.useRealTimers();
        }
    });

    it("supports canceling a running deployment from the job list", async () => {
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
            .mockResolvedValue([{ ...sampleJobs[0], status: 'cancel_requested', message: "Cancellation request submitted" }, sampleJobs[1]]);
        deployServiceMocks.listDeployAuditLogs.mockResolvedValue(sampleAuditLogs);
        deployServiceMocks.cancelDeployJob.mockResolvedValue({
            ...sampleJobs[0],
            status: 'cancel_requested',
            message: "Cancellation request submitted",
        });

        render(<DeployPage />);

        expect(await screen.findByText("Deployment jobs")).toBeInTheDocument();
        fireEvent.click(screen.getByTitle("Cancel job"));

        await waitFor(() => {
            expect(deployServiceMocks.cancelDeployJob).toHaveBeenCalledWith('job-9');
        });
        await waitFor(() => {
            expect(screen.getAllByText("Canceling").length).toBeGreaterThan(0);
        });
    });
});
