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
        raw_message: "report mission-1",
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
    command_summary: "Cancel deployment job",
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
        change_summary: "Minor home page styling adjustment",
    },
    business_risk: 'low',
    ux_risk: 'high',
    release_risk: 'high',
    blockers: [{ type: 'human_review_pending', title: "The primary login flow needs focused review" }],
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
    charter: "Explore the login and authentication flows",
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
    title: "The primary login flow needs focused review",
    summary: "Authentication messages and failure retries need human review.",
    confidence: 0.74,
    evidence: {
        reproduction_steps: ["Open the login page", "Enter the username and password", "Observe the failure message"],
        impact_scope: "Primary authentication flow",
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
                summary: "Cancel deployment job",
                description: "Cancel a deployment job",
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
                        description: "Deployment job ID",
                    },
                ],
                allowed: true,
                denial_reason: '',
            },
            {
                command_id: 'exploration.session.create',
                summary: "Start an exploratory testing session",
                description: "Create exploration session",
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
                        description: "Project identifier",
                    },
                    {
                        name: 'target_url',
                        type: 'string',
                        required: true,
                        description: "Target URL",
                    },
                    {
                        name: 'charter',
                        type: 'string',
                        required: true,
                        description: "Exploration charter",
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
            approval: { ...sampleRun.approval, status: 'approved', comment: "Approve execution" },
            result: { job: { id: 'job-1', status: 'cancelled' } },
        });
        serviceMocks.rejectRun.mockResolvedValue({
            run: { ...sampleRun, status: 'rejected', approval_status: 'rejected' },
            approval: { ...sampleRun.approval, status: 'rejected', comment: "Reject manually" },
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

    it("opens Legion without a token when the development authentication bypass is enabled", async () => {
        authMocks.getStoredControlAuthToken.mockReturnValue('');
        authMocks.fetchControlAuthProfile.mockResolvedValue({
            ...sampleProfile,
            token: '',
        });

        renderLegion('/legion');

        expect(await screen.findByText("AI command center")).toBeInTheDocument();
        expect(screen.getByText("Development mode sign-in bypass")).toBeInTheDocument();
        expect(screen.getByText("Access method: Development sign-in bypass")).toBeInTheDocument();
        expect(screen.getByText("Current user:")).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: "Sign in to the control center" })).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: "Sign out" })).not.toBeInTheDocument();
    });

    it("opens the control center from a URL deep link and performs approval", async () => {
        renderLegion('/legion?tab=control&run=run-pending&assessment=assessment-1&session=session-1');

        expect(await screen.findByText("Command runs and approvals")).toBeInTheDocument();
        expect(await screen.findByText("My notification platform bindings")).toBeInTheDocument();
        expect(screen.getByTestId('location-search').textContent).toContain('tab=control');
        expect(await screen.findByText("Pending human review; automatic release is prohibited")).toBeInTheDocument();
        expect(await screen.findByText("Pending 1 / Confirmed 0 / Rejected 0")).toBeInTheDocument();
        expect(screen.getByText("report mission-1")).toBeInTheDocument();

        fireEvent.change(screen.getByPlaceholderText("Enter an approval note or rejection reason"), {
            target: { value: "Approve execution" },
        });
        fireEvent.click(screen.getByRole('button', { name: "Approve execution" }));

        await waitFor(() => {
            expect(serviceMocks.approveRun).toHaveBeenCalledWith('run-pending', "Approve execution", true);
        });
    });

    it("filters by source and issues or revokes notification platform bindings in the control center", async () => {
        renderLegion('/legion?tab=control&run=run-pending');

        expect(await screen.findByText("Command runs and approvals")).toBeInTheDocument();
        fireEvent.change(screen.getByLabelText("Filter sources"), { target: { value: 'notification_platform' } });

        await waitFor(() => {
            expect(serviceMocks.listCommandRuns).toHaveBeenLastCalledWith(expect.objectContaining({ source: 'notification_platform' }));
        });

        fireEvent.click(screen.getByRole('button', { name: "Generate binding code" }));
        await waitFor(() => {
            expect(serviceMocks.issueNotificationPlatformBindingCode).toHaveBeenCalled();
        });
        expect(await screen.findByText('BIND-NEW123')).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: "Revoke binding" }));
        await waitFor(() => {
            expect(serviceMocks.revokeNotificationPlatformBinding).toHaveBeenCalled();
        });
    });

    it("submits controlled commands through the command launcher", async () => {
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

        expect(await screen.findByText("Command runs and approvals")).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: "Start controlled command" }));

        const dialog = await screen.findByRole('dialog', { name: "Controlled command launcher" });
        fireEvent.change(within(dialog).getByLabelText('job_id *'), {
            target: { value: 'job-2' },
        });
        fireEvent.click(within(dialog).getByLabelText(/I confirm this is a high-risk action/));
        fireEvent.click(within(dialog).getByRole('button', { name: "Submit command" }));

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

    it("switches to exploratory findings and synchronizes the URL", async () => {
        renderLegion('/legion?tab=control');

        expect(await screen.findByText("Command runs and approvals")).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: "Exploration findings" }));

        expect(await screen.findByRole('button', { name: "Start exploration session" })).toBeInTheDocument();
        expect(screen.getByTestId('location-search').textContent).toContain('tab=exploration');
    });

    it("shows linked evidence in command details and opens related exploration and risk objects", async () => {
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

        expect(await screen.findByText("Command runs and approvals")).toBeInTheDocument();
        expect(await screen.findByText("Linked evidence summary")).toBeInTheDocument();
        expect(await screen.findByText("Total: 1 linked findings, with evidence requiring human attention shown first.")).toBeInTheDocument();
        expect(await screen.findByText("Release risk conclusion")).toBeInTheDocument();
        expect(await screen.findAllByText("The primary login flow needs focused review")).toHaveLength(1);
        expect(screen.getByText("Blocked pending review")).toBeInTheDocument();
        expect(screen.getByText("Pending human review; automatic release is prohibited")).toBeInTheDocument();
        expect(screen.getByRole('button', { name: "View exploration findings" })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: "Open human review" })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: "View risk assessment" })).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: "View risk assessment" }));
        await waitFor(() => {
            expect(screen.getByTestId('location-search').textContent).toContain('assessment=assessment-1');
        });

        fireEvent.click(screen.getByRole('button', { name: "View exploration findings" }));
        await waitFor(() => {
            expect(screen.getByTestId('location-search').textContent).toContain('session=session-1');
        });

        fireEvent.click(screen.getByRole('button', { name: "Open human review" }));
        await waitFor(() => {
            expect(screen.getByTestId('location-search').textContent).toContain('tab=exploration');
            expect(screen.getByTestId('location-search').textContent).toContain('finding=finding-1');
        });
    });

    it("starts a controlled release for the current assessment and shows automatic execution results", async () => {
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

        expect(await screen.findByText("Release risk assessment")).toBeInTheDocument();
        expect(await screen.findByText("Review passed; automatic release is allowed")).toBeInTheDocument();

        fireEvent.click((await screen.findAllByRole('button', { name: "Start release using this assessment" }))[0]);
        const dialog = await screen.findByRole('dialog', { name: "Controlled release dialog" });
        fireEvent.change(within(dialog).getByLabelText('repo_id'), {
            target: { value: 'repo-web' },
        });
        fireEvent.change(within(dialog).getByLabelText('branch'), {
            target: { value: 'main' },
        });
        fireEvent.change(within(dialog).getByLabelText("Release notes"), {
            target: { value: "Automatic release" },
        });
        fireEvent.click(within(dialog).getByRole('button', { name: "Submit controlled release" }));

        await waitFor(() => {
            expect(serviceMocks.executeCommand).toHaveBeenCalledWith(
                'release.deploy.request',
                {
                    assessment_id: 'assessment-1',
                    target_type: 'repo',
                    repo_id: 'repo-web',
                    branch: 'main',
                    comment: "Automatic release",
                },
                true,
            );
        });
        await waitFor(() => {
            expect(screen.getByTestId('location-search').textContent).toContain('run=run-release-auto');
        });
        expect(await screen.findByText("Controlled release created and executed automatically")).toBeInTheDocument();
        expect(screen.getByText('approval-auto')).toBeInTheDocument();
        expect(screen.getByText('job-auto')).toBeInTheDocument();
    });

    it("creates a release approval request when a review blocker applies", async () => {
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

        expect(await screen.findByText("Pending human review; automatic release is prohibited")).toBeInTheDocument();
        fireEvent.click((await screen.findAllByRole('button', { name: "Start release using this assessment" }))[0]);
        const dialog = await screen.findByRole('dialog', { name: "Controlled release dialog" });
        expect(within(dialog).getByText("Current release policy: Only manually approved releases are currently allowed")).toBeInTheDocument();
        fireEvent.change(within(dialog).getByLabelText("Release target"), {
            target: { value: 'project' },
        });
        fireEvent.click(within(dialog).getByRole('button', { name: "Submit controlled release" }));

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
        expect(await screen.findByText("Release request created and awaiting approval")).toBeInTheDocument();
        expect(screen.getByText('approval-pending')).toBeInTheDocument();
    });

    it("prefills exploration command parameters from the current context", async () => {
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

        expect(await screen.findByText("Command runs and approvals")).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: "Start controlled command" }));

        const dialog = await screen.findByRole('dialog', { name: "Controlled command launcher" });
        fireEvent.change(within(dialog).getByLabelText("Command"), {
            target: { value: 'exploration.session.create' },
        });

        await waitFor(() => {
            expect(within(dialog).getByLabelText('project_key')).toHaveValue('demo');
            expect(within(dialog).getByLabelText('target_url *')).toHaveValue('https://demo.example.com/login');
        });

        fireEvent.change(within(dialog).getByLabelText('charter *'), {
            target: { value: "Perform additional exploration around account entry points" },
        });
        fireEvent.click(within(dialog).getByRole('button', { name: "Submit command" }));

        await waitFor(() => {
            expect(serviceMocks.executeCommand).toHaveBeenCalledWith(
                'exploration.session.create',
                {
                    project_key: 'demo',
                    target_url: 'https://demo.example.com/login',
                    charter: "Perform additional exploration around account entry points",
                },
                false,
            );
        });
        await waitFor(() => {
            expect(screen.getByTestId('location-search').textContent).toContain('run=run-prefill');
            expect(screen.getByTestId('location-search').textContent).toContain('session=session-prefill');
        });
    });

    it("starts a new exploration session command from exploratory findings", async () => {
        renderLegion('/legion?tab=exploration&session=session-1');

        expect(await screen.findByRole('button', { name: "Start exploration session" })).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: "Start exploration session" }));

        fireEvent.change(screen.getByPlaceholderText('https://demo.example.com/login'), {
            target: { value: 'https://demo.example.com/account' },
        });
        fireEvent.change(screen.getByLabelText("Exploration charter"), {
            target: { value: "Perform exploratory testing around the account center" },
        });
        fireEvent.click(screen.getByRole('button', { name: "Submit exploration command" }));

        await waitFor(() => {
            expect(serviceMocks.executeCommand).toHaveBeenCalledWith(
                'exploration.session.create',
                expect.objectContaining({
                    project_key: 'demo',
                    target_url: 'https://demo.example.com/account',
                    charter: "Perform exploratory testing around the account center",
                }),
            );
        });
        await waitFor(() => {
            expect(screen.getByTestId('location-search').textContent).toContain('run=run-explore');
            expect(screen.getByTestId('location-search').textContent).toContain('session=session-new');
        });
    });

    it("shows the review queue and submits human review through the command gateway", async () => {
        serviceMocks.listExplorationReviewQueue
            .mockResolvedValueOnce({ review_status: 'pending', findings: [sampleFinding], count: 1 })
            .mockResolvedValueOnce({ review_status: 'confirmed', findings: [], count: 0 })
            .mockResolvedValueOnce({ review_status: 'dismissed', findings: [], count: 0 })
            .mockResolvedValueOnce({ review_status: 'pending', findings: [], count: 0 })
            .mockResolvedValueOnce({ review_status: 'confirmed', findings: [{ ...sampleFinding, review_status: 'confirmed', review_comment: "Human confirmation", reviewed_by: 'alice', reviewed_at: '2026-03-24T12:10:00' }], count: 1 })
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
                    review_comment: "Human confirmation",
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
                review_comment: "Human confirmation",
                reviewed_by: 'alice',
                reviewed_at: '2026-03-24T12:10:00',
            }],
            count: 1,
        });

        renderLegion('/legion?tab=exploration&session=session-1&finding=finding-1');

        expect((await screen.findAllByText("Pending review queue")).length).toBeGreaterThan(0);
        expect(await screen.findByText("Review notes")).toBeInTheDocument();
        fireEvent.change(screen.getByPlaceholderText("Optional: add confirmation evidence, rejection reasons, or follow-up suggestions"), {
            target: { value: "Human confirmation" },
        });
        fireEvent.click(screen.getByRole('button', { name: "Confirm issue" }));

        await waitFor(() => {
            expect(serviceMocks.executeCommand).toHaveBeenCalledWith(
                'exploration.finding.review',
                {
                    finding_id: 'finding-1',
                    decision: 'confirmed',
                    comment: "Human confirmation",
                },
            );
        });
        expect(await screen.findByText("Review notes: Human confirmation")).toBeInTheDocument();
        const backToControlButton = await screen.findByRole('button', { name: "Return to the control center to regenerate the release risk assessment" });
        fireEvent.click(backToControlButton);
        await waitFor(() => {
            expect(screen.getByTestId('location-search').textContent).toContain('tab=control');
            expect(screen.getByTestId('location-search').textContent).toContain('finding=finding-1');
        });
    });

    it("shows a finding deep link even when the current list filter excludes it", async () => {
        serviceMocks.listExplorationFindings.mockResolvedValue({
            session_id: 'session-1',
            findings: [],
            count: 0,
        });
        serviceMocks.getExplorationFinding.mockResolvedValue({
            ...sampleFinding,
            review_comment: "Retain deep link details",
        });

        renderLegion('/legion?tab=exploration&finding=finding-1');

        expect(await screen.findByText("Finding details")).toBeInTheDocument();
        expect((await screen.findAllByText("The primary login flow needs focused review")).length).toBeGreaterThan(0);
        await waitFor(() => {
            expect(screen.getByTestId('location-search').textContent).toContain('session=session-1');
            expect(screen.getByTestId('location-search').textContent).toContain('finding=finding-1');
        });
    });
});
