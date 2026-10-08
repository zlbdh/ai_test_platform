import { API_BASE_URL } from '../config';
import { getControlAuthHeaders } from './controlAuthService';

async function ensureJsonResponse<T>(response: Response): Promise<T> {
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        const detail = typeof payload === 'object' && payload && 'detail' in payload
            ? String((payload as Record<string, unknown>).detail)
            : `Request failed (${response.status})`;
        throw new Error(detail);
    }
    return payload as T;
}

function buildQuery(params: Record<string, string | number | boolean | null | undefined>): string {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value === '' || value === null || value === undefined) return;
        query.set(key, String(value));
    });
    const result = query.toString();
    return result ? `?${result}` : '';
}

async function fetchControlJson<T>(url: string, options: RequestInit = {}): Promise<T> {
    const response = await fetch(url, {
        ...options,
        headers: getControlAuthHeaders(options.headers),
    });
    return ensureJsonResponse<T>(response);
}

export interface CommandArgumentDefinition {
    name: string;
    type: string;
    required: boolean;
    description: string;
    default?: unknown;
}

export interface CommandDefinition {
    command_id: string;
    summary: string;
    description: string;
    permission: string;
    risk_level: string;
    read_only: boolean;
    requires_confirmation: boolean;
    approval_required: boolean;
    approval_permission: string;
    approval_policy: string;
    sandbox_required: boolean;
    sandbox_profile: string;
    project_scope: string;
    env_scope: string;
    timeout_s: number;
    aliases: string[];
    arguments: CommandArgumentDefinition[];
    allowed: boolean;
    denial_reason: string;
}

export interface CommandApproval {
    approval_id: string;
    run_id: string;
    command_id: string;
    requester_id: string;
    approver_id: string;
    project_key: string;
    status: string;
    reason: string;
    comment: string;
    created_at: string;
    decided_at: string;
}

export interface CommandRun {
    run_id: string;
    command_id: string;
    requester_id: string;
    source: string;
    source_context?: Record<string, unknown>;
    project_key: string;
    arguments: Record<string, unknown>;
    status: string;
    risk_level: string;
    approval_status: string;
    approval_id: string;
    sandbox_profile: string;
    result: unknown;
    error: unknown;
    command_summary: string;
    read_only: boolean;
    env_scope: string;
    project_scope: string;
    requires_confirmation: boolean;
    approval_policy: string;
    timeout_s: number;
    created_at: string;
    started_at: string;
    finished_at: string;
    approval?: CommandApproval | null;
}

export interface NotificationPlatformBinding {
    notification_platform_open_id: string;
    user_id: string;
    username: string;
    chat_id: string;
    source: string;
    status: string;
    bound_at: string;
    last_seen_at: string;
    revoked_at: string;
}

export interface NotificationPlatformBindingCode {
    code: string;
    user_id: string;
    username: string;
    status: string;
    created_at: string;
    expires_at: string;
    used_at: string;
    revoked_at: string;
    issued_by: string;
}

export interface ExplorationSession {
    session_id: string;
    group_id: string;
    project_key: string;
    target_url: string;
    charter: string;
    requester_id: string;
    status: string;
    summary: Record<string, unknown>;
    risk_score: number;
    finding_count: number;
    human_review_count: number;
    created_at: string;
    updated_at: string;
    findings?: ExperienceFinding[];
}

export interface ExperienceFinding {
    finding_id: string;
    session_id: string;
    project_key: string;
    severity: string;
    finding_type: string;
    title: string;
    summary: string;
    confidence: number;
    evidence: Record<string, unknown>;
    requires_human_review: boolean;
    review_status: string;
    review_comment: string;
    reviewed_by: string;
    reviewed_at: string;
    created_at: string;
}

export interface ReleaseRiskBlocker {
    type: string;
    message?: string;
    title?: string;
    severity?: string;
    finding_id?: string;
    review_status?: string;
}

export interface ReleaseRiskReviewSummary {
    pending: number;
    confirmed: number;
    dismissed: number;
    active: number;
    effective: number;
}

export interface ReleaseRiskEvidence {
    finding_count?: number;
    effective_finding_count?: number;
    high_risk_findings?: string[];
    human_review_count?: number;
    review_summary?: ReleaseRiskReviewSummary;
    pending_review_findings?: string[];
    confirmed_findings?: string[];
    [key: string]: unknown;
}

export interface ReleaseRiskPolicyHit {
    nonprod_only?: boolean;
    required_tests_passed?: boolean;
    review_policy_mode?: string;
    review_blocked?: boolean;
    auto_release_eligible?: boolean;
    [key: string]: unknown;
}

export interface ReleaseRiskAssessment {
    assessment_id: string;
    project_key: string;
    environment: string;
    requester_id: string;
    input: {
        project_key?: string;
        environment?: string;
        exploration_session_ids?: string[];
        required_tests_passed?: boolean;
        change_summary?: string;
    };
    business_risk: string;
    ux_risk: string;
    release_risk: string;
    blockers: ReleaseRiskBlocker[];
    auto_release_eligible: boolean;
    evidence: ReleaseRiskEvidence;
    policy_hit: ReleaseRiskPolicyHit;
    created_at: string;
}

export interface ReleaseDeployTarget {
    target_type: 'repo' | 'project';
    project_key: string;
    repo_id: string;
    branch: string;
}

export interface ReleaseDeployResult {
    assessment_id: string;
    assessment?: ReleaseRiskAssessment;
    release_decision: 'auto_executed' | 'approval_created' | string;
    approval_id: string;
    job_id: string;
    approval?: Record<string, unknown> | null;
    job?: Record<string, unknown> | null;
    deploy_target: ReleaseDeployTarget;
}

export interface CommandExecutionResult {
    command_id: string;
    risk_level: string;
    read_only: boolean;
    run: CommandRun;
    approval: CommandApproval | null;
    result: unknown;
}

const COMMANDER_BASE = `${API_BASE_URL}/api/commander`;
const EXPLORATION_BASE = `${API_BASE_URL}/api/exploration`;
const RELEASE_BASE = `${API_BASE_URL}/api/release`;

export async function listCommands(): Promise<CommandDefinition[]> {
    const payload = await fetchControlJson<{ status: string; commands: CommandDefinition[] }>(
        `${COMMANDER_BASE}/commands`,
    );
    return payload.commands || [];
}

export async function listCommandRuns(filters: {
    status?: string;
    approval_status?: string;
    command_id?: string;
    project_key?: string;
    source?: string;
    limit?: number;
} = {}): Promise<{ runs: CommandRun[]; count: number }> {
    const payload = await fetchControlJson<{ status: string; runs: CommandRun[]; count: number }>(
        `${COMMANDER_BASE}/commands/runs${buildQuery(filters)}`,
    );
    return {
        runs: payload.runs || [],
        count: payload.count || 0,
    };
}

export async function getCommandRun(runId: string): Promise<CommandRun> {
    const payload = await fetchControlJson<{ status: string; run: CommandRun }>(
        `${COMMANDER_BASE}/commands/runs/${encodeURIComponent(runId)}`,
    );
    return payload.run;
}

export async function getNotificationPlatformBindingMe(): Promise<{
    binding: NotificationPlatformBinding | null;
    pending_code: NotificationPlatformBindingCode | null;
}> {
    const payload = await fetchControlJson<{
        status: string;
        binding: NotificationPlatformBinding | null;
        pending_code: NotificationPlatformBindingCode | null;
    }>(`${COMMANDER_BASE}/chatops/bindings/me`);
    return {
        binding: payload.binding || null,
        pending_code: payload.pending_code || null,
    };
}

export async function issueNotificationPlatformBindingCode(): Promise<{
    binding: NotificationPlatformBinding | null;
    pending_code: NotificationPlatformBindingCode | null;
}> {
    const payload = await fetchControlJson<{
        status: string;
        binding: NotificationPlatformBinding | null;
        pending_code: NotificationPlatformBindingCode | null;
    }>(`${COMMANDER_BASE}/chatops/bindings/me/issue`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
    });
    return {
        binding: payload.binding || null,
        pending_code: payload.pending_code || null,
    };
}

export async function revokeNotificationPlatformBinding(): Promise<{
    revoked: boolean;
    binding: NotificationPlatformBinding | null;
    pending_code: NotificationPlatformBindingCode | null;
    revoked_at: string;
}> {
    const payload = await fetchControlJson<{
        status: string;
        revoked: boolean;
        binding: NotificationPlatformBinding | null;
        pending_code: NotificationPlatformBindingCode | null;
        revoked_at: string;
    }>(`${COMMANDER_BASE}/chatops/bindings/me/revoke`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
    });
    return {
        revoked: Boolean(payload.revoked),
        binding: payload.binding || null,
        pending_code: payload.pending_code || null,
        revoked_at: payload.revoked_at || '',
    };
}

export async function executeCommand(
    commandId: string,
    argumentsPayload: Record<string, unknown>,
    confirm = false,
): Promise<CommandExecutionResult> {
    const payload = await fetchControlJson<{
        status: string;
        command_id: string;
        result: CommandExecutionResult;
    }>(`${COMMANDER_BASE}/commands/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            command_id: commandId,
            arguments: argumentsPayload,
            confirm,
        }),
    });
    return payload.result;
}

export async function approveRun(runId: string, comment = '', confirm = true): Promise<{
    run: CommandRun;
    approval: CommandApproval;
    result: unknown;
}> {
    return fetchControlJson(`${COMMANDER_BASE}/commands/runs/${encodeURIComponent(runId)}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comment, confirm }),
    });
}

export async function rejectRun(runId: string, comment = ''): Promise<{
    run: CommandRun;
    approval: CommandApproval;
}> {
    return fetchControlJson(`${COMMANDER_BASE}/commands/runs/${encodeURIComponent(runId)}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comment }),
    });
}

export async function listExplorationSessions(filters: {
    project_key?: string;
    status?: string;
    limit?: number;
} = {}): Promise<{ sessions: ExplorationSession[]; count: number }> {
    const payload = await fetchControlJson<{ status: string; sessions: ExplorationSession[]; count: number }>(
        `${EXPLORATION_BASE}/sessions${buildQuery(filters)}`,
    );
    return {
        sessions: payload.sessions || [],
        count: payload.count || 0,
    };
}

export async function getExplorationSession(sessionId: string): Promise<ExplorationSession> {
    const payload = await fetchControlJson<{ status: string; session: ExplorationSession }>(
        `${EXPLORATION_BASE}/sessions/${encodeURIComponent(sessionId)}`,
    );
    return payload.session;
}

export async function listExplorationFindings(
    sessionId: string,
    filters: {
        severity?: string;
        review_only?: boolean;
        review_status?: string;
    } = {},
): Promise<{ session_id: string; findings: ExperienceFinding[]; count: number }> {
    const payload = await fetchControlJson<{
        status: string;
        session_id: string;
        findings: ExperienceFinding[];
        count: number;
    }>(`${EXPLORATION_BASE}/sessions/${encodeURIComponent(sessionId)}/findings${buildQuery(filters)}`);
    return {
        session_id: payload.session_id,
        findings: payload.findings || [],
        count: payload.count || 0,
    };
}

export async function getExplorationFinding(findingId: string): Promise<ExperienceFinding> {
    const payload = await fetchControlJson<{ status: string; finding: ExperienceFinding }>(
        `${EXPLORATION_BASE}/findings/${encodeURIComponent(findingId)}`,
    );
    return payload.finding;
}

export async function listExplorationReviewQueue(filters: {
    project_key?: string;
    severity?: string;
    review_status?: string;
    limit?: number;
} = {}): Promise<{ review_status: string; findings: ExperienceFinding[]; count: number }> {
    const payload = await fetchControlJson<{
        status: string;
        review_status: string;
        findings: ExperienceFinding[];
        count: number;
    }>(`${EXPLORATION_BASE}/review-queue${buildQuery(filters)}`);
    return {
        review_status: payload.review_status || '',
        findings: payload.findings || [],
        count: payload.count || 0,
    };
}

export async function listReleaseRiskAssessments(filters: {
    project_key?: string;
    environment?: string;
    auto_release_eligible?: boolean | null;
    limit?: number;
} = {}): Promise<{ assessments: ReleaseRiskAssessment[]; count: number }> {
    const payload = await fetchControlJson<{
        status: string;
        assessments: ReleaseRiskAssessment[];
        count: number;
    }>(`${RELEASE_BASE}/risk-assessments${buildQuery(filters)}`);
    return {
        assessments: payload.assessments || [],
        count: payload.count || 0,
    };
}

export async function getReleaseRiskAssessment(assessmentId: string): Promise<ReleaseRiskAssessment> {
    const payload = await fetchControlJson<{ status: string; assessment: ReleaseRiskAssessment }>(
        `${RELEASE_BASE}/risk-assessments/${encodeURIComponent(assessmentId)}`,
    );
    return payload.assessment;
}
