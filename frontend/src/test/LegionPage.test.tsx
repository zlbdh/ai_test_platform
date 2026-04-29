import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';

const authMocks = vi.hoisted(() => ({
    getStoredControlAuthToken: vi.fn(),
    fetchControlAuthProfile: vi.fn(),
    loginControl: vi.fn(),
    logoutControl: vi.fn(),
    clearControlAuthSession: vi.fn(),
}));

const serviceMocks = vi.hoisted(() => ({
    listCommands: vi.fn(),
    listCommandRuns: vi.fn(),
    getCommandRun: vi.fn(),
    approveRun: vi.fn(),
    rejectRun: vi.fn(),
    executeCommand: vi.fn(),
    getNotificationPlatformBindingMe: vi.fn(),
    issueNotificationPlatformBindingCode: vi.fn(),
    revokeNotificationPlatformBinding: vi.fn(),
    listExplorationSessions: vi.fn(),
    getExplorationSession: vi.fn(),
    listExplorationFindings: vi.fn(),
    getExplorationFinding: vi.fn(),
    listExplorationReviewQueue: vi.fn(),
    listReleaseRiskAssessments: vi.fn(),
    getReleaseRiskAssessment: vi.fn(),
}));

vi.mock('../pages/CommanderPage', () => ({
    default: () => <div>CommanderPage Stub</div>,
}));

vi.mock('../pages/WarRoomPage', () => ({
    default: () => <div>WarRoomPage Stub</div>,
}));

vi.mock('../pages/SkillsPanel', () => ({
    default: () => <div>SkillsPanel Stub</div>,
}));

vi.mock('../services/controlAuthService', () => ({
    getStoredControlAuthToken: authMocks.getStoredControlAuthToken,
    fetchControlAuthProfile: authMocks.fetchControlAuthProfile,
    loginControl: authMocks.loginControl,
    logoutControl: authMocks.logoutControl,
    clearControlAuthSession: authMocks.clearControlAuthSession,
}));

vi.mock('../services/legionControlService', () => ({
    listCommands: serviceMocks.listCommands,
    listCommandRuns: serviceMocks.listCommandRuns,
    getCommandRun: serviceMocks.getCommandRun,
    approveRun: serviceMocks.approveRun,
    rejectRun: serviceMocks.rejectRun,
    executeCommand: serviceMocks.executeCommand,
    getNotificationPlatformBindingMe: serviceMocks.getNotificationPlatformBindingMe,
    issueNotificationPlatformBindingCode: serviceMocks.issueNotificationPlatformBindingCode,
    revokeNotificationPlatformBinding: serviceMocks.revokeNotificationPlatformBinding,
    listExplorationSessions: serviceMocks.listExplorationSessions,
    getExplorationSession: serviceMocks.getExplorationSession,
    listExplorationFindings: serviceMocks.listExplorationFindings,
    getExplorationFinding: serviceMocks.getExplorationFinding,
    listExplorationReviewQueue: serviceMocks.listExplorationReviewQueue,
    listReleaseRiskAssessments: serviceMocks.listReleaseRiskAssessments,
    getReleaseRiskAssessment: serviceMocks.getReleaseRiskAssessment,
}));

import LegionPage from '../pages/LegionPage';
import { useLegionControlStore } from '../stores';

function LocationProbe() {
    const location = useLocation();
    return <div data-testid="location-search">{location.search}</div>;
}

function renderLegion(initialEntry: string) {
    return render(
        <MemoryRouter initialEntries={[initialEntry]}>
            <Routes>
                <Route
                    path="/legion"
                    element={(
                        <>
                            <LocationProbe />
                            <LegionPage />
                        </>
                    )}
                />
            </Routes>
        </MemoryRouter>,
    );
}

const sampleProfile = {
    user_id: 'user-1',
    username: 'alice',
    email: 'alice@example.com',
    role: 'developer',
    project_ids: ['demo'],
    permissions: ['run_test', 'view_results', 'deploy_view', 'deploy_request'],
    token: 'demo-token',
};

const sampleRun = {
    run_id: 'run-pending',
    command_id: 'deploy.job.cancel',
    requester_id: 'alice',
    source: 'notification_platform',
    source_context: {
        channel: 'notification_platform',
        from_user: 'ou_demo',
        chat_id: 'oc_demo',
        raw_message: '报告 mission-1',
        binding_status: 'bound',
    },
    project_key: 'demo',
    arguments: { job_id: 'job-1' },
    status: 'approval_pending',
    risk_level: 'high',
    approval_status: 'pending',
    approval_id: 'approval-1',
    sandbox_profile: 'deploy_control',
    result: null,
    error: null,
    command_summary: '取消部署作业',
    read_only: false,
    env_scope: 'nonprod',
    project_scope: 'project',
    requires_confirmation: true,
    approval_policy: 'required',
    timeout_s: 30,
    created_at: '2026-03-23T12:00:00',
    started_at: '',
    finished_at: '',
    approval: {
        approval_id: 'approval-1',
        run_id: 'run-pending',
        command_id: 'deploy.job.cancel',
        requester_id: 'alice',
        approver_id: '',
        project_key: 'demo',
        status: 'pending',
        reason: '',
        comment: '',
        created_at: '2026-03-23T12:00:00',
        decided_at: '',
    },
};

const sampleAssessment = {
    assessment_id: 'assessment-1',
    project_key: 'demo',
    environment: 'staging',
    requester_id: 'alice',
    input: {
        project_key: 'demo',
        exploration_session_ids: ['session-1'],
        change_summary: '首页样式微调',
    },
    business_risk: 'low',
    ux_risk: 'high',
    release_risk: 'high',
    blockers: [{ type: 'human_review_pending', title: '登录主链路需重点复核' }],
    auto_release_eligible: false,
    evidence: {
        finding_count: 1,
        human_review_count: 1,
        review_summary: {
            pending: 1,
            confirmed: 0,
            dismissed: 0,
            active: 1,
            effective: 1,
        },
        pending_review_findings: ['finding-1'],
        confirmed_findings: [],
    },
    policy_hit: {
        auto_release_eligible: false,
        review_blocked: true,
        review_policy_mode: 'conservative',
    },
    created_at: '2026-03-23T12:30:00',
};

const sampleSession = {
    session_id: 'session-1',
    group_id: 'grp-1',
    project_key: 'demo',
    target_url: 'https://demo.example.com/login',
    charter: '围绕登录和认证链路做探索',
    requester_id: 'alice',
    status: 'completed',
    summary: { finding_count: 1, requires_human_review_count: 1 },
    risk_score: 0.86,
    finding_count: 1,
    human_review_count: 1,
    created_at: '2026-03-23T11:50:00',
    updated_at: '2026-03-23T11:55:00',
};

const sampleFinding = {
    finding_id: 'finding-1',
    session_id: 'session-1',
    project_key: 'demo',
    severity: 'high',
    finding_type: 'business',
    title: '登录主链路需重点复核',
    summary: '认证提示与失败重试链路需要人工复核。',
    confidence: 0.74,
    evidence: {
        reproduction_steps: ['打开登录页', '输入账号密码', '观察失败提示'],
        impact_scope: '认证主链路',
        ai_confidence: 0.74,
    },
    requires_human_review: true,
    review_status: 'pending',
    review_comment: '',
    reviewed_by: '',
    reviewed_at: '',
    created_at: '2026-03-23T11:55:00',
};

describe('LegionPage', () => {
    beforeEach(() => {
        vi.resetAllMocks();
        useLegionControlStore.setState({
            activeTab: 'command',
            commandRunFilters: { commandId: '', projectKey: '', status: '', approvalStatus: '', source: '' },
            explorationFilters: { projectKey: '', status: '', severity: '', reviewOnly: false, reviewStatus: '' },
            selectedRunId: null,
            selectedSessionId: null,
            selectedAssessmentId: null,
            selectedFindingId: null,
            lastRefreshedAt: '',
        });
        authMocks.getStoredControlAuthToken.mockReturnValue('demo-token');
        authMocks.fetchControlAuthProfile.mockResolvedValue(sampleProfile);
        authMocks.loginControl.mockResolvedValue(sampleProfile);
        authMocks.logoutControl.mockResolvedValue(undefined);
        serviceMocks.listCommands.mockResolvedValue([
            {
                command_id: 'deploy.job.cancel',
                summary: '取消部署作业',
                description: '取消一个部署作业',
                permission: 'admin',
                risk_level: 'high',
                read_only: false,
                requires_confirmation: true,
                approval_required: true,
                approval_permission: 'deploy_approve',
                approval_policy: 'required',
                sandbox_required: false,
                sandbox_profile: 'deploy_control',
                project_scope: 'project',
                env_scope: 'nonprod',
                timeout_s: 30,
                aliases: [],
                arguments: [
                    {
                        name: 'job_id',
                        type: 'string',
                        required: true,
                        description: '部署作业 ID',
                    },
                ],
                allowed: true,
                denial_reason: '',
            },
            {
                command_id: 'exploration.session.create',
                summary: '启动探索性测试会话',
                description: '创建探索会话',
                permission: 'run_test',
                risk_level: 'medium',
                read_only: false,
                requires_confirmation: false,
                approval_required: false,
                approval_permission: '',
                approval_policy: 'none',
                sandbox_required: false,
                sandbox_profile: 'exploration',
                project_scope: 'project',
                env_scope: 'testing',
                timeout_s: 120,
                aliases: [],
                arguments: [
                    {
                        name: 'project_key',
                        type: 'string',
                        required: false,
                        description: '项目标识',
                    },
                    {
                        name: 'target_url',
                        type: 'string',
                        required: true,
                        description: '目标 URL',
                    },
                    {
                        name: 'charter',
                        type: 'string',
                        required: true,
                        description: '探索章程',
                    },
                ],
                allowed: true,
                denial_reason: '',
            },
        ]);
        serviceMocks.listCommandRuns.mockResolvedValue({ runs: [sampleRun], count: 1 });
        serviceMocks.getCommandRun.mockResolvedValue(sampleRun);
        serviceMocks.approveRun.mockResolvedValue({
            run: { ...sampleRun, status: 'succeeded', approval_status: 'approved' },
            approval: { ...sampleRun.approval, status: 'approved', comment: '批准执行' },
            result: { job: { id: 'job-1', status: 'cancelled' } },
        });
        serviceMocks.rejectRun.mockResolvedValue({
            run: { ...sampleRun, status: 'rejected', approval_status: 'rejected' },
            approval: { ...sampleRun.approval, status: 'rejected', comment: '人工驳回' },
        });
        serviceMocks.listReleaseRiskAssessments.mockResolvedValue({ assessments: [sampleAssessment], count: 1 });
        serviceMocks.getReleaseRiskAssessment.mockResolvedValue(sampleAssessment);
        serviceMocks.listExplorationSessions.mockResolvedValue({ sessions: [sampleSession], count: 1 });
        serviceMocks.getExplorationSession.mockResolvedValue(sampleSession);
        serviceMocks.listExplorationFindings.mockResolvedValue({ session_id: 'session-1', findings: [sampleFinding], count: 1 });
        serviceMocks.getExplorationFinding.mockResolvedValue(sampleFinding);
        serviceMocks.listExplorationReviewQueue.mockImplementation(async (filters?: { review_status?: string }) => {
            const reviewStatus = filters?.review_status || 'pending';
            if (reviewStatus === 'pending') {
                return { review_status: 'pending', findings: [sampleFinding], count: 1 };
            }
            return { review_status: reviewStatus, findings: [], count: 0 };
        });
        serviceMocks.executeCommand.mockResolvedValue({
            command_id: 'exploration.session.create',
            risk_level: 'medium',
            read_only: false,
            run: { ...sampleRun, run_id: 'run-explore', command_id: 'exploration.session.create', approval_status: 'not_required', status: 'succeeded', risk_level: 'medium', requires_confirmation: false, approval_policy: 'none' },
            approval: null,
            result: {
                session: { ...sampleSession, session_id: 'session-new', target_url: 'https://demo.example.com/account' },
            },
        });
        serviceMocks.getNotificationPlatformBindingMe.mockResolvedValue({
            binding: {
                notification_platform_open_id: 'ou_demo',
                user_id: 'user-1',
                username: 'alice',
                chat_id: 'oc_demo',
                source: 'notification_platform',
                status: 'active',
                bound_at: '2026-03-24T12:00:00',
                last_seen_at: '2026-03-24T12:01:00',
                revoked_at: '',
            },
            pending_code: {
                code: 'BIND-ABC123',
                user_id: 'user-1',
                username: 'alice',
                status: 'issued',
                created_at: '2026-03-24T12:00:00',
                expires_at: '2026-03-24T12:10:00',
                used_at: '',
                revoked_at: '',
                issued_by: 'user-1',
            },
        });
        serviceMocks.issueNotificationPlatformBindingCode.mockResolvedValue({
            binding: null,
            pending_code: {
                code: 'BIND-NEW123',
                user_id: 'user-1',
                username: 'alice',
                status: 'issued',
                created_at: '2026-03-24T12:02:00',
                expires_at: '2026-03-24T12:12:00',
                used_at: '',
                revoked_at: '',
                issued_by: 'user-1',
            },
        });
        serviceMocks.revokeNotificationPlatformBinding.mockResolvedValue({
            revoked: true,
            binding: null,
            pending_code: null,
            revoked_at: '2026-03-24T12:03:00',
        });
    });

    it('开发免登录旁路开启时，无 token 也能直接进入 Legion', async () => {
        authMocks.getStoredControlAuthToken.mockReturnValue('');
        authMocks.fetchControlAuthProfile.mockResolvedValue({
            ...sampleProfile,
            token: '',
        });

        renderLegion('/legion');

        expect(await screen.findByText('AI 指挥中台')).toBeInTheDocument();
        expect(screen.getByText('开发模式免登录')).toBeInTheDocument();
        expect(screen.getByText('访问方式：开发免登录')).toBeInTheDocument();
        expect(screen.getByText('当前用户：')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: '登录控制中台' })).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: '退出登录' })).not.toBeInTheDocument();
    });

    it('能根据 URL 深链接打开控制中心并执行批准动作', async () => {
        renderLegion('/legion?tab=control&run=run-pending&assessment=assessment-1&session=session-1');

        expect(await screen.findByText('命令运行与审批')).toBeInTheDocument();
        expect(await screen.findByText('我的通知平台绑定')).toBeInTheDocument();
        expect(screen.getByTestId('location-search').textContent).toContain('tab=control');
        expect(await screen.findByText('待人工复核，禁止自动发布')).toBeInTheDocument();
        expect(await screen.findByText('待 1 / 确 0 / 驳 0')).toBeInTheDocument();
        expect(screen.getByText('报告 mission-1')).toBeInTheDocument();

        fireEvent.change(screen.getByPlaceholderText('填写审批备注或驳回原因'), {
            target: { value: '批准执行' },
        });
        fireEvent.click(screen.getByRole('button', { name: '批准执行' }));

        await waitFor(() => {
            expect(serviceMocks.approveRun).toHaveBeenCalledWith('run-pending', '批准执行', true);
        });
    });

    it('能在控制中心按来源筛选并签发/撤销通知平台绑定', async () => {
        renderLegion('/legion?tab=control&run=run-pending');

        expect(await screen.findByText('命令运行与审批')).toBeInTheDocument();
        fireEvent.change(screen.getByLabelText('来源筛选'), { target: { value: 'notification_platform' } });

        await waitFor(() => {
            expect(serviceMocks.listCommandRuns).toHaveBeenLastCalledWith(expect.objectContaining({ source: 'notification_platform' }));
        });

        fireEvent.click(screen.getByRole('button', { name: '生成绑定码' }));
        await waitFor(() => {
            expect(serviceMocks.issueNotificationPlatformBindingCode).toHaveBeenCalled();
        });
        expect(await screen.findByText('BIND-NEW123')).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: '撤销绑定' }));
        await waitFor(() => {
            expect(serviceMocks.revokeNotificationPlatformBinding).toHaveBeenCalled();
        });
    });

    it('能在控制中心通过命令发起器提交受控命令', async () => {
        serviceMocks.executeCommand.mockResolvedValueOnce({
            command_id: 'deploy.job.cancel',
            risk_level: 'high',
            read_only: false,
            run: {
                ...sampleRun,
                run_id: 'run-cancel',
                command_id: 'deploy.job.cancel',
                arguments: { job_id: 'job-2' },
            },
            approval: sampleRun.approval,
            result: null,
        });

        renderLegion('/legion?tab=control');

        expect(await screen.findByText('命令运行与审批')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: '发起受控命令' }));

        const dialog = await screen.findByRole('dialog', { name: '受控命令发起器' });
        fireEvent.change(within(dialog).getByLabelText('job_id *'), {
            target: { value: 'job-2' },
        });
        fireEvent.click(within(dialog).getByLabelText(/我已确认这是高风险动作/));
        fireEvent.click(within(dialog).getByRole('button', { name: '提交命令' }));

        await waitFor(() => {
            expect(serviceMocks.executeCommand).toHaveBeenCalledWith(
                'deploy.job.cancel',
                { job_id: 'job-2' },
                true,
            );
        });
        await waitFor(() => {
            expect(screen.getByTestId('location-search').textContent).toContain('run=run-cancel');
        });
    });

    it('能切换到探索发现标签并同步 URL', async () => {
        renderLegion('/legion?tab=control');

        expect(await screen.findByText('命令运行与审批')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: '探索发现' }));

        expect(await screen.findByRole('button', { name: '启动探索会话' })).toBeInTheDocument();
        expect(screen.getByTestId('location-search').textContent).toContain('tab=exploration');
    });

    it('能在命令详情里查看关联证据摘要并联动到探索与风险对象', async () => {
        serviceMocks.getCommandRun.mockResolvedValueOnce({
            ...sampleRun,
            run_id: 'run-evidence',
            command_id: 'release.risk.assess',
            source: 'web',
            approval_status: 'not_required',
            status: 'succeeded',
            risk_level: 'medium',
            requires_confirmation: false,
            approval_policy: 'none',
            result: {
                session: sampleSession,
                assessment: sampleAssessment,
            },
        });

        renderLegion('/legion?tab=control&run=run-evidence');

        expect(await screen.findByText('命令运行与审批')).toBeInTheDocument();
        expect(await screen.findByText('关联证据摘要')).toBeInTheDocument();
        expect(await screen.findByText('共 1 条关联发现，优先展示最需要人工关注的证据。')).toBeInTheDocument();
        expect(await screen.findByText('发布风险结论')).toBeInTheDocument();
        expect(await screen.findAllByText('登录主链路需重点复核')).toHaveLength(1);
        expect(screen.getByText('待复核阻断')).toBeInTheDocument();
        expect(screen.getByText('待人工复核，禁止自动发布')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: '查看探索发现' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: '进入人工复核' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: '查看风险评估' })).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: '查看风险评估' }));
        await waitFor(() => {
            expect(screen.getByTestId('location-search').textContent).toContain('assessment=assessment-1');
        });

        fireEvent.click(screen.getByRole('button', { name: '查看探索发现' }));
        await waitFor(() => {
            expect(screen.getByTestId('location-search').textContent).toContain('session=session-1');
        });

        fireEvent.click(screen.getByRole('button', { name: '进入人工复核' }));
        await waitFor(() => {
            expect(screen.getByTestId('location-search').textContent).toContain('tab=exploration');
            expect(screen.getByTestId('location-search').textContent).toContain('finding=finding-1');
        });
    });

    it('能按当前评估发起受控发布并展示自动执行结果', async () => {
        const autoAssessment = {
            ...sampleAssessment,
            blockers: [],
            auto_release_eligible: true,
            release_risk: 'low',
            evidence: {
                ...sampleAssessment.evidence,
                review_summary: {
                    pending: 0,
                    confirmed: 0,
                    dismissed: 1,
                    active: 0,
                    effective: 1,
                },
                pending_review_findings: [],
            },
            policy_hit: {
                ...sampleAssessment.policy_hit,
                review_blocked: false,
                auto_release_eligible: true,
            },
        };
        const releaseRun = {
            ...sampleRun,
            run_id: 'run-release-auto',
            command_id: 'release.deploy.request',
            source: 'web',
            approval_status: 'not_required',
            approval_id: '',
            status: 'succeeded',
            result: {
                assessment_id: 'assessment-1',
                assessment: autoAssessment,
                release_decision: 'auto_executed',
                approval_id: 'approval-auto',
                job_id: 'job-auto',
                approval: { id: 'approval-auto', status: 'approved' },
                job: { id: 'job-auto', status: 'queued' },
                deploy_target: {
                    target_type: 'repo',
                    project_key: 'demo',
                    repo_id: 'repo-web',
                    branch: 'main',
                },
            },
        };
        serviceMocks.listReleaseRiskAssessments.mockResolvedValue(autoAssessment ? { assessments: [autoAssessment], count: 1 } : { assessments: [], count: 0 });
        serviceMocks.getReleaseRiskAssessment.mockResolvedValue(autoAssessment);
        serviceMocks.executeCommand.mockResolvedValueOnce({
            command_id: 'release.deploy.request',
            risk_level: 'high',
            read_only: false,
            run: releaseRun,
            approval: null,
            result: releaseRun.result,
        });
        serviceMocks.getCommandRun.mockResolvedValueOnce(releaseRun);

        renderLegion('/legion?tab=control&assessment=assessment-1&session=session-1');

        expect(await screen.findByText('发布风险评估')).toBeInTheDocument();
        expect(await screen.findByText('复核通过，可自动发布')).toBeInTheDocument();

        fireEvent.click((await screen.findAllByRole('button', { name: '按当前评估发起发布' }))[0]);
        const dialog = await screen.findByRole('dialog', { name: '受控发布对话框' });
        fireEvent.change(within(dialog).getByLabelText('repo_id'), {
            target: { value: 'repo-web' },
        });
        fireEvent.change(within(dialog).getByLabelText('branch'), {
            target: { value: 'main' },
        });
        fireEvent.change(within(dialog).getByLabelText('发布备注'), {
            target: { value: '自动发布' },
        });
        fireEvent.click(within(dialog).getByRole('button', { name: '提交受控发布' }));

        await waitFor(() => {
            expect(serviceMocks.executeCommand).toHaveBeenCalledWith(
                'release.deploy.request',
                {
                    assessment_id: 'assessment-1',
                    target_type: 'repo',
                    repo_id: 'repo-web',
                    branch: 'main',
                    comment: '自动发布',
                },
                true,
            );
        });
        await waitFor(() => {
            expect(screen.getByTestId('location-search').textContent).toContain('run=run-release-auto');
        });
        expect(await screen.findByText('已自动创建并执行受控发布')).toBeInTheDocument();
        expect(screen.getByText('approval-auto')).toBeInTheDocument();
        expect(screen.getByText('job-auto')).toBeInTheDocument();
    });

    it('命中复核阻断时会创建待审批发布申请', async () => {
        const releaseRun = {
            ...sampleRun,
            run_id: 'run-release-pending',
            command_id: 'release.deploy.request',
            source: 'web',
            approval_status: 'not_required',
            approval_id: '',
            status: 'succeeded',
            result: {
                assessment_id: 'assessment-1',
                assessment: sampleAssessment,
                release_decision: 'approval_created',
                approval_id: 'approval-pending',
                job_id: '',
                approval: { id: 'approval-pending', status: 'pending' },
                job: null,
                deploy_target: {
                    target_type: 'project',
                    project_key: 'demo',
                    repo_id: '',
                    branch: '',
                },
            },
        };
        serviceMocks.executeCommand.mockResolvedValueOnce({
            command_id: 'release.deploy.request',
            risk_level: 'high',
            read_only: false,
            run: releaseRun,
            approval: null,
            result: releaseRun.result,
        });
        serviceMocks.getCommandRun.mockResolvedValueOnce(releaseRun);

        renderLegion('/legion?tab=control&assessment=assessment-1&session=session-1');

        expect(await screen.findByText('待人工复核，禁止自动发布')).toBeInTheDocument();
        fireEvent.click((await screen.findAllByRole('button', { name: '按当前评估发起发布' }))[0]);
        const dialog = await screen.findByRole('dialog', { name: '受控发布对话框' });
        expect(within(dialog).getByText('当前发布策略：当前仅允许人工审批发布')).toBeInTheDocument();
        fireEvent.change(within(dialog).getByLabelText('发布目标'), {
            target: { value: 'project' },
        });
        fireEvent.click(within(dialog).getByRole('button', { name: '提交受控发布' }));

        await waitFor(() => {
            expect(serviceMocks.executeCommand).toHaveBeenCalledWith(
                'release.deploy.request',
                {
                    assessment_id: 'assessment-1',
                    target_type: 'project',
                    repo_id: '',
                    branch: '',
                    comment: '',
                },
                true,
            );
        });
        expect(await screen.findByText('已创建待审批发布申请')).toBeInTheDocument();
        expect(screen.getByText('approval-pending')).toBeInTheDocument();
    });

    it('命令发起器会按当前上下文预填探索命令参数', async () => {
        serviceMocks.executeCommand.mockResolvedValueOnce({
            command_id: 'exploration.session.create',
            risk_level: 'medium',
            read_only: false,
            run: {
                ...sampleRun,
                run_id: 'run-prefill',
                command_id: 'exploration.session.create',
                approval_status: 'not_required',
                status: 'succeeded',
                risk_level: 'medium',
                requires_confirmation: false,
                approval_policy: 'none',
            },
            approval: null,
            result: {
                session: {
                    ...sampleSession,
                    session_id: 'session-prefill',
                },
            },
        });

        renderLegion('/legion?tab=control&session=session-1');

        expect(await screen.findByText('命令运行与审批')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: '发起受控命令' }));

        const dialog = await screen.findByRole('dialog', { name: '受控命令发起器' });
        fireEvent.change(within(dialog).getByLabelText('命令'), {
            target: { value: 'exploration.session.create' },
        });

        await waitFor(() => {
            expect(within(dialog).getByLabelText('project_key')).toHaveValue('demo');
            expect(within(dialog).getByLabelText('target_url *')).toHaveValue('https://demo.example.com/login');
        });

        fireEvent.change(within(dialog).getByLabelText('charter *'), {
            target: { value: '围绕账户入口做补充探索' },
        });
        fireEvent.click(within(dialog).getByRole('button', { name: '提交命令' }));

        await waitFor(() => {
            expect(serviceMocks.executeCommand).toHaveBeenCalledWith(
                'exploration.session.create',
                {
                    project_key: 'demo',
                    target_url: 'https://demo.example.com/login',
                    charter: '围绕账户入口做补充探索',
                },
                false,
            );
        });
        await waitFor(() => {
            expect(screen.getByTestId('location-search').textContent).toContain('run=run-prefill');
            expect(screen.getByTestId('location-search').textContent).toContain('session=session-prefill');
        });
    });

    it('能从探索发现中发起新的探索会话命令', async () => {
        renderLegion('/legion?tab=exploration&session=session-1');

        expect(await screen.findByRole('button', { name: '启动探索会话' })).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: '启动探索会话' }));

        fireEvent.change(screen.getByPlaceholderText('https://demo.example.com/login'), {
            target: { value: 'https://demo.example.com/account' },
        });
        fireEvent.change(screen.getByLabelText('探索章程'), {
            target: { value: '围绕账户中心做探索性测试' },
        });
        fireEvent.click(screen.getByRole('button', { name: '提交探索命令' }));

        await waitFor(() => {
            expect(serviceMocks.executeCommand).toHaveBeenCalledWith(
                'exploration.session.create',
                expect.objectContaining({
                    project_key: 'demo',
                    target_url: 'https://demo.example.com/account',
                    charter: '围绕账户中心做探索性测试',
                }),
            );
        });
        await waitFor(() => {
            expect(screen.getByTestId('location-search').textContent).toContain('run=run-explore');
            expect(screen.getByTestId('location-search').textContent).toContain('session=session-new');
        });
    });

    it('能在探索发现中展示待复核队列并通过命令网关提交人工复核', async () => {
        serviceMocks.listExplorationReviewQueue
            .mockResolvedValueOnce({ review_status: 'pending', findings: [sampleFinding], count: 1 })
            .mockResolvedValueOnce({ review_status: 'confirmed', findings: [], count: 0 })
            .mockResolvedValueOnce({ review_status: 'dismissed', findings: [], count: 0 })
            .mockResolvedValueOnce({ review_status: 'pending', findings: [], count: 0 })
            .mockResolvedValueOnce({ review_status: 'confirmed', findings: [{ ...sampleFinding, review_status: 'confirmed', review_comment: '人工确认', reviewed_by: 'alice', reviewed_at: '2026-03-24T12:10:00' }], count: 1 })
            .mockResolvedValueOnce({ review_status: 'dismissed', findings: [], count: 0 });
        serviceMocks.executeCommand.mockResolvedValueOnce({
            command_id: 'exploration.finding.review',
            risk_level: 'medium',
            read_only: false,
            run: {
                ...sampleRun,
                run_id: 'run-review',
                command_id: 'exploration.finding.review',
                source: 'web',
                approval_status: 'not_required',
                status: 'succeeded',
                risk_level: 'medium',
                requires_confirmation: false,
                approval_policy: 'none',
            },
            approval: null,
            result: {
                finding: {
                    ...sampleFinding,
                    review_status: 'confirmed',
                    review_comment: '人工确认',
                    reviewed_by: 'alice',
                    reviewed_at: '2026-03-24T12:10:00',
                },
            },
        });
        serviceMocks.listExplorationFindings.mockResolvedValue({
            session_id: 'session-1',
            findings: [{
                ...sampleFinding,
                review_status: 'confirmed',
                review_comment: '人工确认',
                reviewed_by: 'alice',
                reviewed_at: '2026-03-24T12:10:00',
            }],
            count: 1,
        });

        renderLegion('/legion?tab=exploration&session=session-1&finding=finding-1');

        expect((await screen.findAllByText('待复核队列')).length).toBeGreaterThan(0);
        expect(await screen.findByText('复核备注')).toBeInTheDocument();
        fireEvent.change(screen.getByPlaceholderText('可选：补充确认依据、驳回原因或后续跟进建议'), {
            target: { value: '人工确认' },
        });
        fireEvent.click(screen.getByRole('button', { name: '确认问题' }));

        await waitFor(() => {
            expect(serviceMocks.executeCommand).toHaveBeenCalledWith(
                'exploration.finding.review',
                {
                    finding_id: 'finding-1',
                    decision: 'confirmed',
                    comment: '人工确认',
                },
            );
        });
        expect(await screen.findByText('复核备注：人工确认')).toBeInTheDocument();
        const backToControlButton = await screen.findByRole('button', { name: '回到控制中心重新生成发布风险评估' });
        fireEvent.click(backToControlButton);
        await waitFor(() => {
            expect(screen.getByTestId('location-search').textContent).toContain('tab=control');
            expect(screen.getByTestId('location-search').textContent).toContain('finding=finding-1');
        });
    });

    it('finding 深链接在当前列表过滤不命中时仍能展示详情', async () => {
        serviceMocks.listExplorationFindings.mockResolvedValue({
            session_id: 'session-1',
            findings: [],
            count: 0,
        });
        serviceMocks.getExplorationFinding.mockResolvedValue({
            ...sampleFinding,
            review_comment: '保留深链接详情',
        });

        renderLegion('/legion?tab=exploration&finding=finding-1');

        expect(await screen.findByText('发现详情')).toBeInTheDocument();
        expect((await screen.findAllByText('登录主链路需重点复核')).length).toBeGreaterThan(0);
        await waitFor(() => {
            expect(screen.getByTestId('location-search').textContent).toContain('session=session-1');
            expect(screen.getByTestId('location-search').textContent).toContain('finding=finding-1');
        });
    });
});
