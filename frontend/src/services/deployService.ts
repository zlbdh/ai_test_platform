/**
 * 待测项目部署服务 — 对接后端 /api/deploy/* 接口
 * 数据模型: Project → Repos (二级结构)
 */
import { API_ENDPOINTS } from '../config';
import { getDeployAuthHeaders, getStoredDeployAuthToken } from './deployAuthService';

// ── Types ──
export interface RepoStatus {
    id: string;
    label: string;
    repo_url: string;
    tech_stack: string;
    local_dir: string;
    exists: boolean;
    status: 'not_deployed' | 'cloned' | 'running';
    port: number;
    port_open: boolean;
    pid: number | null;
    install_cmd: string;
    start_cmd: string;
    branch: string;
    has_memory?: boolean;
    deploy_count?: number;
}

export interface ProjectDetail {
    key: string;
    name: string;
    repos: RepoStatus[];
    has_token: boolean;
}

export interface DeployStep {
    name: string;
    status: string;       // pending | running | success | failed | skipped
    message: string;
    duration_ms: number;
    logs: string[];
}

export interface DeployRecord {
    id: string;
    project_key: string;
    repo_id: string;
    repo_label: string;
    action: string;
    status: string;
    message: string;
    started_at: string;
    finished_at: string;
    duration_ms: number;
    logs: string[];
    steps?: DeployStep[];
}

export interface DeployApproval {
    id: string;
    action: string;
    project_key: string;
    repo_id: string;
    repo_label: string;
    branch: string;
    status: 'pending' | 'approved' | 'rejected';
    message: string;
    requested_by: string;
    requested_by_name: string;
    requested_at: string;
    reviewed_by: string;
    reviewed_by_name: string;
    reviewed_at: string;
    review_comment: string;
    job_id: string;
    record_id: string;
    record_status?: string;
    record_message?: string;
    job?: {
        id: string;
        status: string;
        record_id: string;
    };
}

export interface DeployAuditLog {
    log_id: string;
    user_id: string;
    username: string;
    action: string;
    resource_type: string;
    resource_id: string;
    project_key: string;
    details: Record<string, unknown>;
    timestamp: string;
    ip_address: string;
}

export interface DeployJob {
    id: string;
    action: string;
    project_key: string;
    repo_id: string;
    repo_label: string;
    record_id: string;
    branch: string;
    status: string;
    message: string;
    created_at: string;
    started_at: string;
    finished_at: string;
    record_status?: string;
    record_message?: string;
}

export interface RepoInput {
    label: string;
    repo_url: string;
    branch?: string;
    install_cmd?: string;
    start_cmd?: string;
    port?: number;
    tech_stack?: string;
}

export interface AddProjectPayload {
    name: string;
    repos: RepoInput[];
    git_token?: string;
}

const API = API_ENDPOINTS.deploy;

type ApiPayload = Record<string, unknown>;

const deployFetch = async (url: string, options: RequestInit = {}) => {
    const headers = getDeployAuthHeaders(options.headers);
    const response = await fetch(url, { ...options, headers });
    if (!response.ok) {
        let detail = response.statusText || '请求失败';
        try {
            const payload = await response.json();
            if (payload && typeof payload === 'object') {
                const root = payload as Record<string, unknown>;
                detail = String(root.detail || root.message || detail);
            }
        } catch { /* ignore parse failure */ }
        throw new Error(detail);
    }
    return response;
};

const unwrapData = (payload: unknown): ApiPayload => {
    if (!payload || typeof payload !== 'object') return {};
    const root = payload as ApiPayload;
    if (root.data && typeof root.data === 'object') {
        return root.data as ApiPayload;
    }
    return root;
};

const getField = <T>(payload: unknown, field: string, fallback: T): T => {
    const data = unwrapData(payload);
    const value = data[field];
    return value === undefined ? fallback : value as T;
};

// ── CRUD ──
export const getProjects = async (): Promise<ProjectDetail[]> => {
    const r = await deployFetch(API.projects);
    return getField<ProjectDetail[]>(await r.json(), 'projects', []);
};

export const addProject = async (payload: AddProjectPayload): Promise<ProjectDetail> => {
    const r = await deployFetch(API.projects, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    return getField<ProjectDetail>(await r.json(), 'project', {} as ProjectDetail);
};

export const updateProject = async (key: string, payload: Partial<AddProjectPayload>): Promise<ProjectDetail> => {
    const r = await deployFetch(API.project(key), {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    return getField<ProjectDetail>(await r.json(), 'project', {} as ProjectDetail);
};

export const deleteProject = async (key: string): Promise<void> => {
    await deployFetch(API.project(key), { method: 'DELETE' });
};

// ── Git Token (项目级) ──
export const setProjectToken = async (projectKey: string, git_token: string): Promise<void> => {
    await deployFetch(API.project(projectKey) + '/token', {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ git_token }),
    });
};

// ── Repo-level Deploy Actions ──
const DEPLOY_BASE = API.projects.replace('/projects', '');

const repoAction = async (projectKey: string, repoId: string, action: string, body?: object): Promise<DeployRecord> => {
    const url = `${DEPLOY_BASE}/repo/${projectKey}/${repoId}/${action}`;
    const r = await deployFetch(url, {
        method: 'POST',
        ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}),
    });
    return getField<DeployRecord>(await r.json(), 'record', {} as DeployRecord);
};

export const cloneRepo = (pk: string, rid: string, branch = '') => repoAction(pk, rid, 'clone', { branch });
export const installRepo = (pk: string, rid: string) => repoAction(pk, rid, 'install');
export const startRepo = (pk: string, rid: string) => repoAction(pk, rid, 'start');
export const stopRepo = (pk: string, rid: string) => repoAction(pk, rid, 'stop');

export const fullDeployRepo = async (
    pk: string,
    rid: string,
    branch = '',
): Promise<{ repo_id: string; record_id?: string }> => {
    const url = `${DEPLOY_BASE}/repo/${pk}/${rid}/full`;
    const r = await deployFetch(url, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ branch }),
    });
    return unwrapData(await r.json()) as { repo_id: string; record_id?: string };
};

export const fullDeployAll = async (projectKey: string): Promise<DeployRecord> => {
    const url = `${DEPLOY_BASE}/repo/${projectKey}/deploy-all`;
    const r = await deployFetch(url, { method: 'POST' });
    return getField<DeployRecord>(await r.json(), 'record', {} as DeployRecord);
};

export const requestFullDeployRepo = async (
    pk: string,
    rid: string,
    branch = '',
): Promise<DeployApproval> => {
    const url = `${DEPLOY_BASE}/repo/${pk}/${rid}/full/request`;
    const r = await deployFetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ branch }),
    });
    return getField<DeployApproval>(await r.json(), 'approval', {} as DeployApproval);
};

export const requestFullDeployAll = async (projectKey: string): Promise<DeployApproval> => {
    const url = `${DEPLOY_BASE}/repo/${projectKey}/deploy-all/request`;
    const r = await deployFetch(url, { method: 'POST' });
    return getField<DeployApproval>(await r.json(), 'approval', {} as DeployApproval);
};

export const listDeployApprovals = async (status = '', limit = 30): Promise<DeployApproval[]> => {
    const query = new URLSearchParams();
    if (status) query.set('status', status);
    query.set('limit', String(limit));
    const suffix = query.toString();
    const r = await deployFetch(`${DEPLOY_BASE}/approvals${suffix ? `?${suffix}` : ''}`);
    return getField<DeployApproval[]>(await r.json(), 'approvals', []);
};

export const listDeployJobs = async (status = '', limit = 30): Promise<DeployJob[]> => {
    const query = new URLSearchParams();
    if (status) query.set('status', status);
    query.set('limit', String(limit));
    const suffix = query.toString();
    const r = await deployFetch(`${DEPLOY_BASE}/jobs${suffix ? `?${suffix}` : ''}`);
    return getField<DeployJob[]>(await r.json(), 'jobs', []);
};

export const listDeployAuditLogs = async ({
    limit = 30,
    action = '',
    projectKey = '',
    userId = '',
}: {
    limit?: number;
    action?: string;
    projectKey?: string;
    userId?: string;
} = {}): Promise<DeployAuditLog[]> => {
    const query = new URLSearchParams();
    query.set('limit', String(limit));
    if (action) query.set('action', action);
    if (projectKey) query.set('project_key', projectKey);
    if (userId) query.set('user_id', userId);
    const suffix = query.toString();
    const r = await deployFetch(`${DEPLOY_BASE}/audit${suffix ? `?${suffix}` : ''}`);
    return getField<DeployAuditLog[]>(await r.json(), 'logs', []);
};

const reviewDeployApproval = async (approvalId: string, action: 'approve' | 'reject', comment = ''): Promise<DeployApproval> => {
    const r = await deployFetch(`${DEPLOY_BASE}/approvals/${approvalId}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comment }),
    });
    return getField<DeployApproval>(await r.json(), 'approval', {} as DeployApproval);
};

export const approveDeployApproval = (approvalId: string, comment = '') =>
    reviewDeployApproval(approvalId, 'approve', comment);

export const rejectDeployApproval = (approvalId: string, comment = '') =>
    reviewDeployApproval(approvalId, 'reject', comment);

export const getDeployApprovalDetail = async (approvalId: string): Promise<DeployApproval> => {
    const r = await deployFetch(`${DEPLOY_BASE}/approvals/${approvalId}`);
    return getField<DeployApproval>(await r.json(), 'approval', {} as DeployApproval);
};

export const getDeployJobDetail = async (jobId: string): Promise<DeployJob> => {
    const r = await deployFetch(`${DEPLOY_BASE}/jobs/${jobId}`);
    return getField<DeployJob>(await r.json(), 'job', {} as DeployJob);
};

export const cancelDeployJob = async (jobId: string): Promise<DeployJob> => {
    const r = await deployFetch(`${DEPLOY_BASE}/jobs/${jobId}/cancel`, {
        method: 'POST',
    });
    return getField<DeployJob>(await r.json(), 'job', {} as DeployJob);
};

// ── SSE 实时部署流 ──
export interface DeployEvent {
    type: 'deploy_start' | 'step_start' | 'step_done' | 'deploy_done';
    step?: string;
    label?: string;
    status?: string;
    message?: string;
    duration_ms?: number;
    record_id?: string;
    repo_label?: string;
    steps?: string[];
    logs?: string[];           // 步骤完成时的构建日志
}

export const subscribeDeployStream = (
    pk: string, rid: string,
    onEvent: (event: DeployEvent) => void,
    onError?: () => void,
): (() => void) => {
    const token = getStoredDeployAuthToken();
    const query = token ? `?token=${encodeURIComponent(token)}` : '';
    const url = `${DEPLOY_BASE}/repo/${pk}/${rid}/stream${query}`;
    const es = new EventSource(url);
    es.onmessage = (e) => {
        try {
            const event = JSON.parse(e.data) as DeployEvent;
            onEvent(event);
            if (event.type === 'deploy_done') es.close();
        } catch { /* ignore */ }
    };
    es.onerror = () => { es.close(); onError?.(); };
    return () => es.close();
};

// ── 单条记录详情 ──
export const getRecordDetail = async (recordId: string): Promise<DeployRecord> => {
    const r = await deployFetch(`${DEPLOY_BASE.replace('/repo', '')}/record/${recordId}`);
    return getField<DeployRecord>(await r.json(), 'record', {} as DeployRecord);
};

// ── Logs / History ──
export const getRepoLogs = async (repoId: string, lines = 100): Promise<string[]> => {
    const r = await deployFetch(API.logs(repoId) + `?lines=${lines}`);
    return getField<string[]>(await r.json(), 'logs', []);
};

export const getDeployHistory = async (): Promise<DeployRecord[]> => {
    const r = await deployFetch(API.history);
    return getField<DeployRecord[]>(await r.json(), 'history', []);
};

export const deleteHistoryRecord = async (recordId: string): Promise<void> => {
    await deployFetch(`${API.history}/${recordId}`, { method: 'DELETE' });
};

export const clearHistory = async (): Promise<void> => {
    await deployFetch(API.history, { method: 'DELETE' });
};

// ── AI 智能分析 ──
export interface AIAnalysis {
    tech_stack: string;
    install_cmd: string;
    start_cmd: string;
    build_cmd: string;
    port: number;
    env_vars: Record<string, string>;
    effective_env_vars?: Record<string, string>;
    effective_env_text?: string;
    effective_env_source?: string;
    saved_env_vars?: Record<string, string>;
    saved_env_text?: string;
    saved_context?: DeployContext;
    env_apply_behavior?: string;
    notes: string;
    confidence: number;
    source: string;
    error?: string;
    has_memory?: boolean;
    deploy_count?: number;
    last_success?: string;
    suggested_changes?: Array<{
        file: string;
        type: string;
        module: string;
        description: string;
    }>;
}

export const aiAnalyzeRepo = async (pk: string, rid: string): Promise<AIAnalysis> => {
    const url = `${DEPLOY_BASE}/repo/${pk}/${rid}/ai-analyze`;
    const r = await deployFetch(url, { method: 'POST' });
    return getField<AIAnalysis>(await r.json(), 'analysis', {} as AIAnalysis);
};

export const applyAIConfig = async (pk: string, rid: string, config: Partial<AIAnalysis>, deployContext?: DeployContext): Promise<RepoStatus> => {
    const url = `${DEPLOY_BASE}/repo/${pk}/${rid}/apply-ai-config`;
    const r = await deployFetch(url, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            tech_stack: config.tech_stack || '',
            install_cmd: config.install_cmd || '',
            start_cmd: config.start_cmd || '',
            port: config.port || 0,
            deploy_context: deployContext || {},
        }),
    });
    return getField<RepoStatus>(await r.json(), 'repo', {} as RepoStatus);
};

// ── 部署上下文 & AI 二次确认 ──
export interface DeployContext {
    server_address: string;
    db_connection: string;
    env_vars: string;          // KEY=VALUE 格式，每行一个
    user_notes: string;
}

export const aiRefineConfig = async (
    pk: string, rid: string,
    context: DeployContext, initialConfig: Partial<AIAnalysis>,
): Promise<AIAnalysis> => {
    const url = `${DEPLOY_BASE}/repo/${pk}/${rid}/ai-refine`;
    const r = await deployFetch(url, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...context, initial_config: initialConfig }),
    });
    return getField<AIAnalysis>(await r.json(), 'analysis', {} as AIAnalysis);
};
