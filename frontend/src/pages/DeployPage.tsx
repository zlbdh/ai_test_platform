import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
    Rocket, RefreshCw, Play, Square, Download, GitBranch,
    CheckCircle2, XCircle, Clock, Terminal, Server, Globe,
    Package, Activity, Key, FolderGit2,
    Loader2, Plus, Trash2, Pencil, X, Layers, Sparkles,
    ShieldCheck, ShieldAlert, Users,
} from '../components/icons';

import PageHeader from '../components/ui/PageHeader';
import DataTable, { type DataTableColumn } from '../components/ui/DataTable';
import {
    getProjects, cloneRepo, installRepo,
    startRepo, stopRepo, fullDeployRepo, fullDeployAll,
    getRepoLogs, getDeployHistory, deleteHistoryRecord, clearHistory,
    addProject, updateProject, deleteProject, aiAnalyzeRepo, applyAIConfig,
    getRecordDetail, aiRefineConfig, getDeployApprovalDetail, getDeployJobDetail,
    requestFullDeployRepo, requestFullDeployAll,
    listDeployApprovals, listDeployAuditLogs, listDeployJobs,
    approveDeployApproval, rejectDeployApproval, cancelDeployJob,
    type ProjectDetail, type DeployRecord, type DeployApproval, type DeployAuditLog, type DeployJob,
    type AddProjectPayload, type AIAnalysis, type DeployContext,
} from '../services/deployService';
import { statusBadge, actionLabel } from '../components/deploy/deployMeta';
import StatCard from '../components/ui/StatCard';
import DeployProgressPanel, { type ProgressState } from '../components/deploy/DeployProgressPanel';
import ApprovalReviewDialog from '../components/deploy/ApprovalReviewDialog';
import ProjectDialog, { type RepoFormItem } from '../components/deploy/ProjectDialog';
import {
    attachDeployToken,
    clearDeployAuthSession,
    fetchDeployAuthProfile,
    getStoredDeployAuthToken,
    hasDeployPermission,
    loginDeployControl,
    logoutDeployControl,
    type DeployAuthProfile,
} from '../services/deployAuthService';

const EMPTY_DEPLOY_CONTEXT: DeployContext = {
    server_address: '',
    db_connection: '',
    env_vars: '',
    user_notes: '',
};

const normalizeDeployContext = (value?: Partial<DeployContext> | null): DeployContext => ({
    server_address: value?.server_address || '',
    db_connection: value?.db_connection || '',
    env_vars: value?.env_vars || '',
    user_notes: value?.user_notes || '',
});

type AuditFilterState = {
    action: string;
    projectKey: string;
    userId: string;
};

const EMPTY_AUDIT_FILTER: AuditFilterState = {
    action: '',
    projectKey: '',
    userId: '',
};

const DEPLOY_AUDIT_ACTION_OPTIONS: Array<{ value: string; label: string }> = [
    { value: '', label: "All actions" },
    { value: 'deploy_full_request', label: "Submit for approval" },
    { value: 'deploy_approval_approve', label: "Approval granted" },
    { value: 'deploy_approval_reject', label: "Approval rejected" },
    { value: 'deploy_repo_full', label: "Direct deployment" },
    { value: 'deploy_project_full', label: "Deploy all directly" },
    { value: 'deploy_job_cancel', label: "Cancel job" },
    { value: 'deploy_history_delete', label: "Delete history" },
    { value: 'deploy_history_clear', label: "Clear history" },
];

const formatEnvVars = (envVars?: Record<string, string>): string => {
    if (!envVars || Object.keys(envVars).length === 0) return '';
    return Object.entries(envVars).map(([key, value]) => `${key}=${value}`).join('\n');
};

const hasDeployContextContent = (ctx: DeployContext): boolean =>
    Boolean(ctx.server_address || ctx.db_connection || ctx.env_vars || ctx.user_notes);

const formatDateTime = (value: string): string => {
    if (!value) return '-';
    return new Date(value).toLocaleString('en-US', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    });
};

const deployAuditActionLabel = (action: string): string => {
    const meta: Record<string, string> = {
        deploy_project_add: "Add project",
        deploy_project_update: "Update project",
        deploy_project_delete: "Delete project",
        deploy_project_token_update: "Update token",
        deploy_repo_clone: "Clone repository",
        deploy_repo_install: "Install dependencies",
        deploy_repo_start: "Start service",
        deploy_repo_stop: "Stop service",
        deploy_repo_full: "Direct deployment",
        deploy_project_full: "Deploy all directly",
        deploy_full_request: "Submit for approval",
        deploy_approval_approve: "Approval granted",
        deploy_approval_reject: "Approval rejected",
        deploy_job_cancel: "Cancel job",
        deploy_history_delete: "Delete history",
        deploy_history_clear: "Clear history",
        deploy_memory_clear: "Clear deployment memory",
    };
    return meta[action] || action;
};

const getDeployAuditTarget = (log: DeployAuditLog): string => {
    const repoLabel = typeof log.details.repo_label === 'string' ? log.details.repo_label : '';
    if (repoLabel) return repoLabel;
    if (log.project_key && log.resource_id && log.resource_id !== log.project_key) {
        return `${log.project_key} / ${log.resource_id}`;
    }
    return log.resource_id || log.project_key || '-';
};

const getDeployAuditSummary = (log: DeployAuditLog): string => {
    const comment = typeof log.details.comment === 'string' ? log.details.comment : '';
    const branch = typeof log.details.branch === 'string' ? log.details.branch : '';
    const jobId = typeof log.details.job_id === 'string' ? log.details.job_id : '';
    const recordId = typeof log.details.record_id === 'string' ? log.details.record_id : '';
    const parts = [comment, branch ? `Branch ${branch}` : '', jobId ? `Job ${jobId}` : '', recordId ? `Record ${recordId}` : '']
        .filter(Boolean);
    return parts.join(' · ') || '-';
};

const formatAuditDetails = (details: Record<string, unknown>): string =>
    JSON.stringify(details, null, 2);

const getAuditStringDetail = (details: Record<string, unknown>, key: string): string => {
    const value = details[key];
    return typeof value === 'string' ? value.trim() : '';
};

type AuditLinkedResources = {
    approvalId: string;
    jobId: string;
    recordId: string;
};

const getAuditLinkedResources = (log: DeployAuditLog | null): AuditLinkedResources => {
    if (!log) {
        return { approvalId: '', jobId: '', recordId: '' };
    }
    const approvalId = getAuditStringDetail(log.details, 'approval_id')
        || (log.resource_type === 'deploy_approval' ? log.resource_id : '');
    const jobId = getAuditStringDetail(log.details, 'job_id')
        || (log.resource_type === 'deploy_job' ? log.resource_id : '');
    const recordId = getAuditStringDetail(log.details, 'record_id')
        || (log.resource_type === 'deploy_record' || log.resource_type === 'deploy_history'
            ? log.resource_id
            : '');
    return { approvalId, jobId, recordId };
};

// ============================================================================
// Deploy Page
// ============================================================================
const DeployPage: React.FC = () => {
    const [projects, setProjects] = useState<ProjectDetail[]>([]);
    const [history, setHistory] = useState<DeployRecord[]>([]);
    const [approvals, setApprovals] = useState<DeployApproval[]>([]);
    const [jobs, setJobs] = useState<DeployJob[]>([]);
    const [auditLogs, setAuditLogs] = useState<DeployAuditLog[]>([]);
    const [auditFilter, setAuditFilter] = useState<AuditFilterState>(EMPTY_AUDIT_FILTER);
    const [auditDraft, setAuditDraft] = useState<AuditFilterState>(EMPTY_AUDIT_FILTER);
    const [auditLoading, setAuditLoading] = useState(false);
    const [auditError, setAuditError] = useState('');
    const [selectedAuditLog, setSelectedAuditLog] = useState<DeployAuditLog | null>(null);
    const [auditLinkedLoading, setAuditLinkedLoading] = useState<'' | 'approval' | 'job' | 'record'>('');
    const [auditLinkedError, setAuditLinkedError] = useState('');
    const [linkedApproval, setLinkedApproval] = useState<DeployApproval | null>(null);
    const [linkedJob, setLinkedJob] = useState<DeployJob | null>(null);
    const [focusedApprovalId, setFocusedApprovalId] = useState('');
    const [focusedJobId, setFocusedJobId] = useState('');
    const [focusedHistoryId, setFocusedHistoryId] = useState('');
    const [approvalContextFilterId, setApprovalContextFilterId] = useState('');
    const [jobContextFilterId, setJobContextFilterId] = useState('');
    const [historyContextFilterId, setHistoryContextFilterId] = useState('');
    const [loading, setLoading] = useState(true);
    const [authProfile, setAuthProfile] = useState<DeployAuthProfile | null>(null);
    const [authBusy, setAuthBusy] = useState(false);
    const [authError, setAuthError] = useState('');
    const [authForm, setAuthForm] = useState({ username: '', password: '', token: '' });
    const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});
    const [selectedRepo, setSelectedRepo] = useState<{ pk: string; rid: string; label: string } | null>(null);
    const [logs, setLogs] = useState<string[]>([]);
    const logEndRef = useRef<HTMLDivElement>(null);
    const approvalSectionRef = useRef<HTMLDivElement>(null);
    const jobsSectionRef = useRef<HTMLDivElement>(null);
    const historySectionRef = useRef<HTMLDivElement>(null);

    const [dialogOpen, setDialogOpen] = useState(false);
    const [dialogMode, setDialogMode] = useState<'add' | 'edit'>('add');
    const [editingKey, setEditingKey] = useState('');
    const [editInitialName, setEditInitialName] = useState('');
    const [editInitialRepos, setEditInitialRepos] = useState<RepoFormItem[]>([]);
    const [editInitialToken, setEditInitialToken] = useState('');

    // AI analysis status
    const [aiLoading, setAiLoading] = useState<Record<string, boolean>>({});
    const [aiResult, setAiResult] = useState<AIAnalysis | null>(null);
    const [aiResultRepo, setAiResultRepo] = useState<{ pk: string; rid: string; label: string } | null>(null);
    const [aiEditForm, setAiEditForm] = useState({ tech_stack: '', install_cmd: '', start_cmd: '', build_cmd: '', port: 0 });
    const [showContext, setShowContext] = useState(false);
    const [deployContext, setDeployContext] = useState<DeployContext>(EMPTY_DEPLOY_CONTEXT);
    const [aiRefining, setAiRefining] = useState(false);
    const [approvalDialog, setApprovalDialog] = useState<{
        open: boolean;
        approvalId: string;
        action: 'approve' | 'reject';
        targetLabel: string;
        comment: string;
    }>({
        open: false,
        approvalId: '',
        action: 'approve',
        targetLabel: '',
        comment: '',
    });

    // Deployment progress
    const [deployProgress, setDeployProgress] = useState<ProgressState>({
        open: false, repoLabel: '', steps: [], logs: [], finalStatus: '', finalMessage: '',
    });
    const closeRef = useRef<(() => void) | null>(null);
    const auditFilterRef = useRef<AuditFilterState>(EMPTY_AUDIT_FILTER);
    const isDevBypassAuth = Boolean(authProfile && !authProfile.token);

    const resetAuditLinkedState = useCallback(() => {
        setAuditLinkedLoading('');
        setAuditLinkedError('');
        setLinkedApproval(null);
        setLinkedJob(null);
    }, []);

    const focusApprovalRow = useCallback((approvalId: string) => {
        if (!approvalId) return;
        setFocusedApprovalId(approvalId);
        approvalSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, []);

    const focusJobRow = useCallback((jobId: string) => {
        if (!jobId) return;
        setFocusedJobId(jobId);
        jobsSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, []);

    const focusHistoryRow = useCallback((recordId: string) => {
        if (!recordId) return;
        setFocusedHistoryId(recordId);
        historySectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, []);

    const applyApprovalContextFilter = useCallback((approvalId: string) => {
        if (!approvalId) return;
        setApprovalContextFilterId(approvalId);
        focusApprovalRow(approvalId);
    }, [focusApprovalRow]);

    const clearApprovalContextFilter = useCallback(() => {
        setApprovalContextFilterId('');
    }, []);

    const applyJobContextFilter = useCallback((jobId: string) => {
        if (!jobId) return;
        setJobContextFilterId(jobId);
        focusJobRow(jobId);
    }, [focusJobRow]);

    const clearJobContextFilter = useCallback(() => {
        setJobContextFilterId('');
    }, []);

    const applyHistoryContextFilter = useCallback((recordId: string) => {
        if (!recordId) return;
        setHistoryContextFilterId(recordId);
        focusHistoryRow(recordId);
    }, [focusHistoryRow]);

    const clearHistoryContextFilter = useCallback(() => {
        setHistoryContextFilterId('');
    }, []);

    const upsertJob = useCallback((job: DeployJob) => {
        setJobs(prev => {
            const existingIndex = prev.findIndex(item => item.id === job.id);
            if (existingIndex >= 0) {
                const next = [...prev];
                next[existingIndex] = job;
                return next;
            }
            return [job, ...prev];
        });
    }, []);

    useEffect(() => {
        auditFilterRef.current = auditFilter;
    }, [auditFilter]);

    useEffect(() => {
        resetAuditLinkedState();
    }, [selectedAuditLog?.log_id, resetAuditLinkedState]);

    useEffect(() => {
        if (focusedApprovalId && !approvals.some(item => item.id === focusedApprovalId)) {
            setFocusedApprovalId('');
        }
    }, [approvals, focusedApprovalId]);

    useEffect(() => {
        if (approvalContextFilterId && !approvals.some(item => item.id === approvalContextFilterId)) {
            setApprovalContextFilterId('');
        }
    }, [approvals, approvalContextFilterId]);

    useEffect(() => {
        if (focusedJobId && !jobs.some(item => item.id === focusedJobId)) {
            setFocusedJobId('');
        }
    }, [jobs, focusedJobId]);

    useEffect(() => {
        if (jobContextFilterId && !jobs.some(item => item.id === jobContextFilterId)) {
            setJobContextFilterId('');
        }
    }, [jobs, jobContextFilterId]);

    useEffect(() => {
        if (focusedHistoryId && !history.some(item => item.id === focusedHistoryId)) {
            setFocusedHistoryId('');
        }
    }, [history, focusedHistoryId]);

    useEffect(() => {
        const linkedRecordIds = [
            linkedJob?.record_id,
            linkedApproval?.record_id,
            getAuditLinkedResources(selectedAuditLog).recordId,
        ].filter(Boolean);
        if (
            historyContextFilterId
            && !history.some(item => item.id === historyContextFilterId)
            && !linkedRecordIds.includes(historyContextFilterId)
        ) {
            setHistoryContextFilterId('');
        }
    }, [history, historyContextFilterId, linkedApproval?.record_id, linkedJob?.record_id, selectedAuditLog]);

    const loadAuditLogs = useCallback(async (filters?: AuditFilterState) => {
        const activeFilters = filters || auditFilterRef.current;
        setAuditLoading(true);
        try {
            const logs = await listDeployAuditLogs({
                limit: 20,
                action: activeFilters.action,
                projectKey: activeFilters.projectKey,
                userId: activeFilters.userId,
            });
            setAuditLogs(logs);
            setAuditError('');
            setSelectedAuditLog(current => {
                if (!current) return null;
                return logs.find(item => item.log_id === current.log_id) || null;
            });
        } catch (error) {
            setAuditLogs([]);
            setSelectedAuditLog(null);
            setAuditError(error instanceof Error ? error.message : "Failed to load deployment audit");
        } finally {
            setAuditLoading(false);
        }
    }, []);

    const load = useCallback(async () => {
        setLoading(true);
        const storedToken = getStoredDeployAuthToken();

        try {
            let profile = await fetchDeployAuthProfile(storedToken);
            if (!profile && storedToken) {
                clearDeployAuthSession();
                profile = await fetchDeployAuthProfile('');
            }
            if (!profile) {
                setAuthProfile(null);
                setProjects([]);
                setHistory([]);
                setApprovals([]);
                setJobs([]);
                setAuditLogs([]);
                setAuditError('');
                setSelectedAuditLog(null);
                setAuthError(storedToken ? "Deployment authentication has expired. Sign in again." : '');
                setLoading(false);
                return;
            }
            setAuthProfile(profile);
            setAuthError('');
            if (!hasDeployPermission(profile, 'deploy_view')) {
                setProjects([]);
                setHistory([]);
                setApprovals([]);
                setJobs([]);
                setAuditLogs([]);
                setAuditError('');
                setSelectedAuditLog(null);
                setAuthError("Your role lacks deployment viewing permission. Sign in with another account or ask an administrator for deploy_view.");
                setLoading(false);
                return;
            }
        } catch (error) {
            clearDeployAuthSession();
            setProjects([]);
            setHistory([]);
            setApprovals([]);
            setJobs([]);
            setAuditLogs([]);
            setAuditError('');
            setSelectedAuditLog(null);
            setAuthProfile(null);
            setAuthError(error instanceof Error ? error.message : "Failed to verify deployment authentication");
            setLoading(false);
            return;
        }

        try {
            const [p, h, a, j] = await Promise.all([
                getProjects(),
                getDeployHistory(),
                listDeployApprovals('', 20),
                listDeployJobs('', 20),
            ]);
            setProjects(p);
            setHistory(h);
            setApprovals(a);
            setJobs(j);
            await loadAuditLogs();
        } catch (error) {
            setProjects([]);
            setHistory([]);
            setApprovals([]);
            setJobs([]);
            setAuditLogs([]);
            setAuditError('');
            setSelectedAuditLog(null);
            setAuthError(error instanceof Error ? error.message : "Failed to load deployment data");
        }
        setLoading(false);
    }, [loadAuditLogs]);

    useEffect(() => { load(); }, [load]);
    useEffect(() => { logEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [logs]);

    const closeAiDialog = useCallback(() => {
        setAiResult(null);
        setAiResultRepo(null);
        setShowContext(false);
        setDeployContext(EMPTY_DEPLOY_CONTEXT);
    }, []);

    const refreshLogs = useCallback(async (rid: string) => {
        try { setLogs(await getRepoLogs(rid)); } catch { /* */ }
    }, []);

    const handleAuthLogin = async () => {
        if (!authForm.username || !authForm.password) {
            setAuthError("Enter a username and password");
            return;
        }
        setAuthBusy(true);
        try {
            const profile = await loginDeployControl(authForm.username, authForm.password);
            setAuthProfile(profile);
            setAuthError('');
            setAuthForm(prev => ({ ...prev, password: '' }));
            await load();
        } catch (error) {
            setAuthError(error instanceof Error ? error.message : "Sign-in failed");
        }
        setAuthBusy(false);
    };

    const handleAttachToken = async () => {
        if (!authForm.token.trim()) {
            setAuthError("Enter an access token");
            return;
        }
        setAuthBusy(true);
        try {
            const profile = await attachDeployToken(authForm.token.trim());
            setAuthProfile(profile);
            setAuthError('');
            setAuthForm(prev => ({ ...prev, token: '' }));
            await load();
        } catch (error) {
            setAuthError(error instanceof Error ? error.message : "Failed to save token");
        }
        setAuthBusy(false);
    };

    const handleLogout = async () => {
        setAuthBusy(true);
        await logoutDeployControl();
        setAuthProfile(null);
        setAuthError('');
        setProjects([]);
        setHistory([]);
        setApprovals([]);
        setJobs([]);
        setAuditLogs([]);
        setAuditError('');
        setSelectedAuditLog(null);
        setSelectedRepo(null);
        setLogs([]);
        setAuthBusy(false);
    };

    const doAction = async (id: string, fn: () => Promise<unknown>) => {
        setActionLoading(p => ({ ...p, [id]: true }));
        try {
            await fn();
            await load();
            if (selectedRepo) await refreshLogs(selectedRepo.rid);
        } catch { /* */ }
        setActionLoading(p => ({ ...p, [id]: false }));
    };

    const handleRequestRepoApproval = async (pk: string, rid: string) => {
        await doAction(`${rid}_approval_request`, () => requestFullDeployRepo(pk, rid));
    };

    const handleRequestProjectApproval = async (pk: string) => {
        await doAction(`approval_all_${pk}`, () => requestFullDeployAll(pk));
    };

    const openApprovalDialog = (approval: DeployApproval, action: 'approve' | 'reject') => {
        setApprovalDialog({
            open: true,
            approvalId: approval.id,
            action,
            targetLabel: approval.repo_label || approval.project_key,
            comment: '',
        });
    };

    const closeApprovalDialog = () => {
        setApprovalDialog({
            open: false,
            approvalId: '',
            action: 'approve',
            targetLabel: '',
            comment: '',
        });
    };

    // Step metadata
    const STEP_META: Record<string, { label: string }> = {
        clone: { label: "📥 Clone" },
        install: { label: "📦 Install" },
        start: { label: "🚀 Start" },
    };

    const trackDeployRecord = useCallback((
        recordId: string,
        label: string,
        initialLog: string,
        actionId?: string,
    ) => {
        closeRef.current?.();
        setDeployProgress({
            open: true,
            repoLabel: label,
            steps: [
                { name: 'clone', label: "📥 Clone", status: 'pending', message: '', duration_ms: 0 },
                { name: 'install', label: "📦 Install", status: 'pending', message: '', duration_ms: 0 },
                { name: 'start', label: "🚀 Start", status: 'pending', message: '', duration_ms: 0 },
            ],
            logs: [initialLog],
            finalStatus: '',
            finalMessage: '',
        });

        const finishActionLoading = () => {
            if (!actionId) return;
            setActionLoading(p => ({ ...p, [actionId]: false }));
        };

        const poll = setInterval(async () => {
            try {
                const rec = await getRecordDetail(recordId);
                if (!rec) return;

                setDeployProgress(prev => {
                    const updated = { ...prev };
                    if (rec.steps && rec.steps.length > 0) {
                        updated.steps = rec.steps.map(s => ({
                            name: s.name,
                            label: STEP_META[s.name]?.label || s.name,
                            status: s.status,
                            message: s.message,
                            duration_ms: s.duration_ms,
                        }));
                    }
                    if (rec.logs && rec.logs.length > 0) {
                        updated.logs = rec.logs.slice(-60);
                    }
                    if (['success', 'failed', 'cancelled'].includes(rec.status)) {
                        updated.finalStatus = rec.status;
                        updated.finalMessage = rec.message || '';
                        clearInterval(poll);
                        finishActionLoading();
                        load();
                    }
                    return updated;
                });
            } catch { /* ignore polling errors */ }
        }, 2000);

        closeRef.current = () => clearInterval(poll);
        setTimeout(() => clearInterval(poll), 600000);
    }, [load]);

    // Direct deployment with progress polling
    const startFullDeploy = async (pk: string, rid: string, label: string) => {
        const actionId = `${rid}_full`;
        setActionLoading(p => ({ ...p, [actionId]: true }));

        // Start deployment in the background and return record_id.
        let recordId = '';
        try {
            const res = await fullDeployRepo(pk, rid);
            recordId = res.record_id || '';
        } catch { /* ignore */ }

        if (!recordId) {
            setDeployProgress(p => ({ ...p, finalStatus: 'failed', finalMessage: "Failed to start deployment" }));
            setActionLoading(p => ({ ...p, [actionId]: false }));
            return;
        }
        trackDeployRecord(recordId, label, "🔄 Direct deployment started...", actionId);
    };

    const closeProgress = () => {
        closeRef.current?.();
        setDeployProgress(p => ({ ...p, open: false }));
        load();
    };

    const submitApprovalReview = async () => {
        const { approvalId, action, comment, targetLabel } = approvalDialog;
        const actionId = `${approvalId}_${action}`;
        setActionLoading(p => ({ ...p, [actionId]: true }));
        try {
            const approval = action === 'approve'
                ? await approveDeployApproval(approvalId, comment)
                : await rejectDeployApproval(approvalId, comment);

            setApprovals(prev => prev.map(item => item.id === approval.id ? approval : item));
            closeApprovalDialog();

            if (action === 'approve' && approval.record_id) {
                trackDeployRecord(
                    approval.record_id,
                    approval.repo_label || targetLabel,
                    "✅ Approval granted; deployment task started...",
                );
            }

            await load();
        } catch { /* */ }
        setActionLoading(p => ({ ...p, [actionId]: false }));
    };

    // AI configuration analysis
    const handleAiAnalyze = async (pk: string, rid: string, label: string) => {
        const loadKey = `${pk}_${rid}_ai`;
        setAiLoading(p => ({ ...p, [loadKey]: true }));
        try {
            const result = await aiAnalyzeRepo(pk, rid);
            setAiResult(result);
            setAiResultRepo({ pk, rid, label });
            const nextContext = normalizeDeployContext(result.saved_context);
            setDeployContext(nextContext);
            setShowContext(hasDeployContextContent(nextContext));
            if (!result.error) {
                setAiEditForm({
                    tech_stack: result.tech_stack || '',
                    install_cmd: result.install_cmd || '',
                    start_cmd: result.start_cmd || '',
                    build_cmd: result.build_cmd || '',
                    port: result.port || 0,
                });
            }
        } catch (e) {
            setAiResult({ error: "Request failed", source: 'ai' } as AIAnalysis);
            setAiResultRepo({ pk, rid, label });
            setDeployContext(EMPTY_DEPLOY_CONTEXT);
            setShowContext(false);
        } finally {
            setAiLoading(p => ({ ...p, [loadKey]: false }));
        }
    };

    const handleApplyAiConfig = async () => {
        if (!aiResultRepo || !aiResult || aiResult.error) return;
        const { pk, rid, label } = aiResultRepo;
        // Mark suggested pom changes for user confirmation.
        const ctxWithPom = {
            ...deployContext,
            ...(aiResult.suggested_changes?.length ? {
                apply_pom_changes: true,
                suggested_changes: aiResult.suggested_changes,
            } : {}),
        };
        await applyAIConfig(pk, rid, aiEditForm as any, ctxWithPom);
        closeAiDialog();
        await load();
        startFullDeploy(pk, rid, label);
    };

    // AI confirmation
    const handleAiRefine = async () => {
        if (!aiResultRepo || !aiResult || aiResult.error) return;
        const { pk, rid } = aiResultRepo;
        setAiRefining(true);
        try {
            const refined = await aiRefineConfig(pk, rid, deployContext, aiEditForm as any);
            setAiResult(refined);
            setAiEditForm({
                tech_stack: refined.tech_stack || '',
                install_cmd: refined.install_cmd || '',
                start_cmd: refined.start_cmd || '',
                build_cmd: refined.build_cmd || '',
                port: refined.port || 0,
            });
        } catch { /* ignore */ }
        setAiRefining(false);
    };

    // ── CRUD ──
    const handleAdd = () => {
        setDialogMode('add');
        setEditInitialName('');
        setEditInitialRepos([]);
        setEditInitialToken('');
        setDialogOpen(true);
    };

    const handleEdit = (proj: ProjectDetail) => {
        setDialogMode('edit');
        setEditingKey(proj.key);
        setEditInitialName(proj.name);
        setEditInitialToken(proj.has_token ? '••••••••' : '');
        setEditInitialRepos(proj.repos.map(r => ({
            label: r.label, repo_url: r.repo_url, branch: r.branch,
            install_cmd: r.install_cmd, start_cmd: r.start_cmd,
            port: r.port, tech_stack: r.tech_stack,
        })));
        setDialogOpen(true);
    };

    const handleDelete = async (key: string, name: string) => {
        if (!confirm(`Delete project "${name}" and all its repositories?`)) return;
        await deleteProject(key);
        await load();
    };

    const handleDialogSubmit = async (data: AddProjectPayload) => {
        if (dialogMode === 'add') await addProject(data);
        else await updateProject(editingKey, data);
        setDialogOpen(false);
        await load();
    };

    // ── History delete handlers ──
    const handleDeleteRecord = async (id: string) => {
        await deleteHistoryRecord(id);
        await load();
    };
    const handleClearHistory = async () => {
        if (!confirm("Clear all deployment history? This cannot be undone.")) return;
        await clearHistory();
        await load();
    };

    const handleApplyAuditFilter = async () => {
        const nextFilter = {
            action: auditDraft.action,
            projectKey: auditDraft.projectKey,
            userId: auditDraft.userId.trim(),
        };
        setAuditFilter(nextFilter);
        await loadAuditLogs(nextFilter);
    };

    const handleResetAuditFilter = async () => {
        setAuditDraft(EMPTY_AUDIT_FILTER);
        setAuditFilter(EMPTY_AUDIT_FILTER);
        await loadAuditLogs(EMPTY_AUDIT_FILTER);
    };

    const handleOpenAuditApproval = async () => {
        const { approvalId } = getAuditLinkedResources(selectedAuditLog);
        if (!approvalId) return;
        setAuditLinkedLoading('approval');
        setAuditLinkedError('');
        try {
            const approval = await getDeployApprovalDetail(approvalId);
            setApprovals(prev => {
                const existingIndex = prev.findIndex(item => item.id === approval.id);
                if (existingIndex >= 0) {
                    const next = [...prev];
                    next[existingIndex] = approval;
                    return next;
                }
                return [approval, ...prev];
            });
            if (approval.job?.id) {
                upsertJob({
                    id: approval.job.id,
                    action: approval.action,
                    project_key: approval.project_key,
                    repo_id: approval.repo_id,
                    repo_label: approval.repo_label,
                    record_id: approval.job.record_id || approval.record_id || '',
                    branch: approval.branch,
                    status: approval.job.status,
                    message: approval.record_message || approval.message || '',
                    created_at: approval.requested_at,
                    started_at: approval.reviewed_at || '',
                    finished_at: approval.reviewed_at || '',
                    record_status: approval.record_status,
                    record_message: approval.record_message,
                });
            }
            setLinkedApproval(approval);
            focusApprovalRow(approval.id);
        } catch (error) {
            setLinkedApproval(null);
            setAuditLinkedError(error instanceof Error ? error.message : "Failed to load linked approval request");
        } finally {
            setAuditLinkedLoading('');
        }
    };

    const handleOpenAuditJob = async () => {
        const { jobId } = getAuditLinkedResources(selectedAuditLog);
        if (!jobId) return;
        setAuditLinkedLoading('job');
        setAuditLinkedError('');
        try {
            const job = await getDeployJobDetail(jobId);
            upsertJob(job);
            setLinkedJob(job);
            focusJobRow(job.id);
        } catch (error) {
            setLinkedJob(null);
            setAuditLinkedError(error instanceof Error ? error.message : "Failed to load linked job");
        } finally {
            setAuditLinkedLoading('');
        }
    };

    const handleCancelJob = async (job: DeployJob) => {
        if (!canAdmin) return;
        if (!confirm(`Cancel job "${job.id}"?`)) return;
        const actionId = `job_cancel_${job.id}`;
        setActionLoading(prev => ({ ...prev, [actionId]: true }));
        try {
            const cancelledJob = await cancelDeployJob(job.id);
            upsertJob(cancelledJob);
            if (linkedJob?.id === cancelledJob.id) {
                setLinkedJob(cancelledJob);
            }
            focusJobRow(cancelledJob.id);
            await load();
        } catch {
            /* ignore */
        } finally {
            setActionLoading(prev => ({ ...prev, [actionId]: false }));
        }
    };

    const handleOpenAuditRecord = async () => {
        if (!selectedAuditLog) return;
        const { recordId } = getAuditLinkedResources(selectedAuditLog);
        if (!recordId) return;
        setAuditLinkedLoading('record');
        setAuditLinkedError('');
        try {
            const record = await getRecordDetail(recordId);
            if (!record?.id) {
                throw new Error("Linked deployment record not found");
            }
            setHistory(prev => {
                const existingIndex = prev.findIndex(item => item.id === record.id);
                if (existingIndex >= 0) {
                    const next = [...prev];
                    next[existingIndex] = record;
                    return next;
                }
                return [record, ...prev];
            });
            focusHistoryRow(record.id);
            trackDeployRecord(
                recordId,
                record.repo_label || getDeployAuditTarget(selectedAuditLog),
                "🔍 Opening deployment record from audit details...",
            );
        } catch (error) {
            setAuditLinkedError(error instanceof Error ? error.message : "Failed to load linked deployment record");
        } finally {
            setAuditLinkedLoading('');
        }
    };

    // ── History columns ──
    const jobColumns: DataTableColumn<DeployJob>[] = [
        { key: 'id', title: "Job", width: '120px', render: v => <code className="text-[11px] font-mono">{String(v)}</code> },
        { key: 'repo_label', title: "Target", sortable: true, render: v => <span className="text-xs font-medium">{String(v) || '-'}</span> },
        { key: 'action', title: "Action", render: v => <span className="text-xs">{actionLabel(String(v))}</span> },
        { key: 'status', title: "Status", sortable: true, render: v => statusBadge(String(v)) },
        {
            key: 'message',
            title: "Description",
            render: (_v, row) => (
                <div className="space-y-1">
                    <div className="text-xs text-slate-500 line-clamp-1" title={row.message || row.record_message || '-'}>
                        {row.message || row.record_message || '-'}
                    </div>
                    <div className="flex flex-wrap items-center gap-1">
                        {row.record_status ? statusBadge(row.record_status) : null}
                        {row.record_id ? <code className="text-[10px] font-mono text-slate-400">{row.record_id}</code> : null}
                    </div>
                </div>
            ),
        },
        {
            key: 'created_at',
            title: "Created at",
            sortable: true,
            render: v => formatDateTime(String(v)),
        },
        {
            key: '_actions' as any,
            title: '',
            width: '72px',
            render: (_v, row) => {
                const actionId = `job_cancel_${row.id}`;
                const cancelable = ['queued', 'running'].includes(row.status);
                if (!cancelable) {
                    return <span className="text-[11px] text-slate-400">{row.status === 'cancel_requested' ? "Canceling" : "Finished"}</span>;
                }
                return (
                    <button
                        onClick={(event) => {
                            event.stopPropagation();
                            handleCancelJob(row);
                        }}
                        title={"Cancel job"}
                        disabled={!canAdmin || !!actionLoading[actionId]}
                        className="inline-flex items-center gap-1 rounded-lg border border-red-200 dark:border-red-800 px-2 py-1 text-[11px] font-semibold text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-50"
                    >
                        {actionLoading[actionId] ? <Loader2 className="w-3 h-3 animate-spin" /> : <Square className="w-3 h-3" />}
                        Cancel
                    </button>
                );
            },
        },
    ];

    const historyColumns: DataTableColumn<DeployRecord>[] = [
        { key: 'id', title: 'ID', width: '70px', render: (v) => <code className="text-xs font-mono">{String(v)}</code> },
        { key: 'repo_label', title: "Repository", sortable: true, render: v => <span className="text-xs font-medium">{String(v) || '-'}</span> },
        { key: 'action', title: "Actions", render: v => <span className="text-xs">{actionLabel(String(v))}</span> },
        { key: 'status', title: "Status", sortable: true, render: v => statusBadge(String(v)) },
        { key: 'message', title: "Message", render: v => <span className="text-xs text-slate-500 line-clamp-1">{String(v)}</span> },
        { key: 'duration_ms', title: "Duration", sortable: true, align: 'right' as const, render: v => `${(Number(v) / 1000).toFixed(1)}s` },
        { key: 'started_at', title: "Time", sortable: true, render: v => new Date(String(v)).toLocaleString('en-US', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) },
        {
            key: '_actions' as any, title: '', width: '40px', render: (_v, row) => (
                <button onClick={() => handleDeleteRecord(String((row as DeployRecord).id))} title={"Delete"} disabled={!canAdmin}
                    className="p-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-slate-300 hover:text-red-500 transition-colors disabled:opacity-40">
                    <Trash2 className="w-3 h-3" />
                </button>
            )
        },
    ];

    const approvalColumns: DataTableColumn<DeployApproval>[] = [
        { key: 'id', title: "Approval request", width: '120px', render: v => <code className="text-[11px] font-mono">{String(v)}</code> },
        { key: 'repo_label', title: "Target", sortable: true, render: v => <span className="text-xs font-medium">{String(v) || '-'}</span> },
        { key: 'action', title: "Action", render: v => <span className="text-xs">{actionLabel(String(v))}</span> },
        { key: 'requested_by_name', title: "Requested by", render: v => <span className="text-xs text-slate-500">{String(v) || '-'}</span> },
        { key: 'status', title: "Status", sortable: true, render: v => statusBadge(String(v)) },
        {
            key: 'message',
            title: "Description",
            render: (_v, row) => (
                <div className="space-y-1">
                    <div className="text-xs text-slate-500 line-clamp-1" title={row.review_comment || row.message}>
                        {row.review_comment || row.message || '-'}
                    </div>
                    <div className="flex flex-wrap items-center gap-1">
                        {row.job?.status ? statusBadge(row.job.status) : null}
                        {row.record_status ? statusBadge(row.record_status) : null}
                    </div>
                </div>
            ),
        },
        {
            key: 'requested_at',
            title: "Requested at",
            sortable: true,
            render: v => new Date(String(v)).toLocaleString('en-US', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }),
        },
        {
            key: '_actions' as any,
            title: '',
            width: '100px',
            render: (_v, row) => (
                row.status === 'pending' && canApprove ? (
                    <div className="flex items-center justify-end gap-1">
                        <button
                            onClick={() => openApprovalDialog(row, 'approve')}
                            title={"Approve"}
                            className="p-1.5 rounded-lg border border-emerald-200 dark:border-emerald-800 text-emerald-500 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 transition-colors"
                        >
                            <CheckCircle2 className="w-3 h-3" />
                        </button>
                        <button
                            onClick={() => openApprovalDialog(row, 'reject')}
                            title={"Reject"}
                            className="p-1.5 rounded-lg border border-red-200 dark:border-red-800 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                        >
                            <XCircle className="w-3 h-3" />
                        </button>
                    </div>
                ) : (
                    <span className="text-[11px] text-slate-400">{row.status === 'pending' ? "Awaiting approval" : "Processed"}</span>
                )
            ),
        },
    ];

    const auditColumns: DataTableColumn<DeployAuditLog>[] = [
        {
            key: 'timestamp',
            title: "Time",
            sortable: true,
            width: '110px',
            render: v => <span className="text-xs text-slate-500">{formatDateTime(String(v))}</span>,
        },
        {
            key: 'action',
            title: "Action",
            render: v => <span className="text-xs font-medium text-slate-700 dark:text-slate-200">{deployAuditActionLabel(String(v))}</span>,
        },
        {
            key: 'project_key',
            title: "Project",
            sortable: true,
            render: v => <span className="text-xs text-cyan-600 dark:text-cyan-300">{String(v) || '-'}</span>,
        },
        {
            key: 'username',
            title: "Operator",
            sortable: true,
            render: (_v, row) => <span className="text-xs text-slate-500">{row.username || row.user_id || '-'}</span>,
        },
        {
            key: 'resource_id',
            title: "Target",
            render: (_v, row) => <span className="text-xs font-medium text-slate-600 dark:text-slate-300">{getDeployAuditTarget(row)}</span>,
        },
        {
            key: 'details',
            title: "Summary",
            render: (_v, row) => (
                <div className="space-y-1">
                    <div className="text-xs text-slate-500 line-clamp-1" title={getDeployAuditSummary(row)}>
                        {getDeployAuditSummary(row)}
                    </div>
                    {row.ip_address ? (
                        <div className="text-[10px] text-slate-400">IP {row.ip_address}</div>
                    ) : null}
                </div>
            ),
        },
    ];

    const totalDeploys = history.length;
    const successCount = history.filter(h => h.status === 'success').length;
    const failedCount = history.filter(h => h.status === 'failed').length;
    const allRepos = projects.flatMap(p => p.repos);
    const runningCount = allRepos.filter(r => r.status === 'running').length;
    const pendingApprovalCount = approvals.filter(a => a.status === 'pending').length;
    const activeJobCount = jobs.filter(job => ['queued', 'running', 'cancel_requested'].includes(job.status)).length;
    const auditUserCount = new Set(auditLogs.map(log => log.user_id).filter(Boolean)).size;
    const canView = hasDeployPermission(authProfile, 'deploy_view');
    const canRequest = hasDeployPermission(authProfile, 'deploy_request');
    const canApprove = hasDeployPermission(authProfile, 'deploy_approve');
    const canAdmin = hasDeployPermission(authProfile, 'admin');
    const visibleProjectScopes = authProfile?.project_ids || [];
    const auditProjectOptions = Array.from(new Set(
        (visibleProjectScopes.length > 0 ? visibleProjectScopes : projects.map(project => project.key)).filter(Boolean),
    ));
    const auditLinkedResources = getAuditLinkedResources(selectedAuditLog);
    const hasAuditLinkedResources = Boolean(
        auditLinkedResources.approvalId || auditLinkedResources.jobId || auditLinkedResources.recordId,
    );
    const visibleApprovals = approvalContextFilterId
        ? approvals.filter(item => item.id === approvalContextFilterId)
        : approvals;
    const visibleJobs = jobContextFilterId
        ? jobs.filter(item => item.id === jobContextFilterId)
        : jobs;
    const visibleHistory = historyContextFilterId
        ? history.filter(item => item.id === historyContextFilterId)
        : history;

    if (loading) {
        return <div className="flex items-center justify-center h-64 text-slate-400"><RefreshCw className="w-6 h-6 animate-spin mr-2" /> Loading...</div>;
    }

    const mainContent = (
        <div className="space-y-6 max-w-7xl mx-auto">
            <PageHeader
                icon={<Rocket className="w-5 h-5" />}
                title={"Deploy projects for testing"}
                description={"Add frontend and backend Git repositories for projects under test. Deploy directly or analyze the configuration with AI first."}
                accent="cyan"
                actions={
                    <div className="flex items-center gap-2">
                        <button onClick={handleAdd}
                            disabled={!canAdmin}
                            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600 text-white text-xs font-semibold shadow-sm transition-all">
                            <Plus className="w-3.5 h-3.5" /> Add project
                        </button>
                        <button onClick={load} className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400" title={"Refresh"}>
                            <RefreshCw className="w-4 h-4" />
                        </button>
                    </div>
                }
            />

            <div className={`rounded-2xl border overflow-hidden ${authProfile
                ? 'border-emerald-200/70 dark:border-emerald-800/50 bg-emerald-50/70 dark:bg-emerald-900/10'
                : 'border-amber-200/70 dark:border-amber-800/50 bg-amber-50/80 dark:bg-amber-900/10'
                }`}>
                <div className={`px-5 py-4 border-b ${authProfile
                    ? 'border-emerald-200/70 dark:border-emerald-800/40'
                    : 'border-amber-200/70 dark:border-amber-800/40'
                    } flex items-center justify-between gap-3`}>
                    <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-xl ${authProfile
                            ? 'bg-emerald-500 text-white'
                            : 'bg-amber-500 text-white'
                            }`}>
                            {authProfile ? <ShieldCheck className="w-4 h-4" /> : <ShieldAlert className="w-4 h-4" />}
                        </div>
                        <div>
                            <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">Deployment control authentication</h3>
                            <p className="text-[11px] text-slate-500 dark:text-slate-400">
                    {isDevBypassAuth
                        ? "Local development mode bypasses sign-in and automatically attaches developer permissions so you can test the deployment flow."
                        : authProfile
                            ? "Deployment requests are authenticated. The permissions below reflect your current role."
                            : "Deployment authentication is enabled. Sign in or paste a token before this page can make authorized requests."}
                            </p>
                        </div>
                    </div>
                    {authProfile?.token ? (
                        <button
                            onClick={handleLogout}
                            disabled={authBusy}
                            className="px-3 py-1.5 rounded-lg border border-emerald-200 dark:border-emerald-800 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300 hover:bg-emerald-100/70 dark:hover:bg-emerald-900/20 transition-colors disabled:opacity-50"
                        >
                            {authBusy ? "Signing out..." : "Sign out"}
                        </button>
                    ) : null}
                </div>

                <div className="p-5 space-y-4">
                    {authProfile ? (
                        <>
                            <div className="flex flex-wrap items-center gap-2">
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-white/80 dark:bg-slate-800/70 text-[11px] font-semibold text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700">
                                    <Users className="w-3 h-3" />
                                    {authProfile.username}
                                </span>
                                {isDevBypassAuth ? (
                                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-cyan-100 dark:bg-cyan-900/30 text-[11px] font-semibold text-cyan-700 dark:text-cyan-300">
                                        Development sign-in bypass
                                    </span>
                                ) : null}
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-cyan-100 dark:bg-cyan-900/30 text-[11px] font-semibold text-cyan-700 dark:text-cyan-300">
                                    Role: {authProfile.role}
                                </span>
                                {authProfile.expires_at ? (
                                    <span className="text-[11px] text-slate-500 dark:text-slate-400">
                                        Expires at: {new Date(authProfile.expires_at).toLocaleString('en-US')}
                                    </span>
                                ) : null}
                            </div>
                            <div className="rounded-xl border border-white/80 dark:border-slate-700 bg-white/80 dark:bg-slate-900/50 px-3 py-3">
                                <div className="text-[10px] uppercase tracking-wider text-slate-400">Project scope</div>
                                <div className="mt-2 flex flex-wrap items-center gap-2">
                                    {canAdmin ? (
                                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300">
                                            All projects (administrator)
                                        </span>
                                    ) : visibleProjectScopes.length > 0 ? (
                                        visibleProjectScopes.map(projectId => (
                                            <span
                                                key={projectId}
                                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-cyan-100 dark:bg-cyan-900/30 text-[11px] font-semibold text-cyan-700 dark:text-cyan-300"
                                            >
                                                {projectId}
                                            </span>
                                        ))
                                    ) : (
                                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-[11px] font-semibold text-slate-500 dark:text-slate-300">
                                            All projects (unrestricted)
                                        </span>
                                    )}
                                </div>
                            </div>
                            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                                {[
                                    { key: 'deploy_view', label: "Can view", enabled: canView },
                                    { key: 'deploy_request', label: "Can request approval", enabled: canRequest },
                                    { key: 'deploy_approve', label: "Can approve", enabled: canApprove },
                                    { key: 'admin', label: "Can execute directly", enabled: canAdmin },
                                ].map(item => (
                                    <div key={item.key} className="rounded-xl border border-white/80 dark:border-slate-700 bg-white/80 dark:bg-slate-900/50 px-3 py-3">
                                        <div className="text-[10px] uppercase tracking-wider text-slate-400">{item.key}</div>
                                        <div className={`mt-1 text-sm font-semibold ${item.enabled ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400'}`}>
                                            {item.label}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </>
                    ) : (
                        <div className="grid lg:grid-cols-2 gap-4">
                            <div className="rounded-xl border border-white/80 dark:border-slate-700 bg-white/80 dark:bg-slate-900/50 p-4 space-y-3">
                                <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Account sign-in</div>
                                <input
                                    value={authForm.username}
                                    onChange={e => setAuthForm(prev => ({ ...prev, username: e.target.value }))}
                                    placeholder={"Username"}
                                    className="w-full px-3 py-2 text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/70 outline-none focus:ring-2 focus:ring-cyan-500/30"
                                />
                                <input
                                    type="password"
                                    value={authForm.password}
                                    onChange={e => setAuthForm(prev => ({ ...prev, password: e.target.value }))}
                                    placeholder={"Password"}
                                    className="w-full px-3 py-2 text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/70 outline-none focus:ring-2 focus:ring-cyan-500/30"
                                />
                                <button
                                    onClick={handleAuthLogin}
                                    disabled={authBusy}
                                    className="w-full px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-500 text-white text-xs font-semibold hover:from-cyan-600 hover:to-blue-600 transition-all disabled:opacity-60"
                                >
                                    {authBusy ? "Signing in..." : "Sign in to deployment control"}
                                </button>
                            </div>

                            <div className="rounded-xl border border-white/80 dark:border-slate-700 bg-white/80 dark:bg-slate-900/50 p-4 space-y-3">
                                <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Attach token manually</div>
                                <textarea
                                    value={authForm.token}
                                    onChange={e => setAuthForm(prev => ({ ...prev, token: e.target.value }))}
                                    rows={4}
                                    placeholder={"Paste the token returned by /api/auth/login"}
                                    className="w-full px-3 py-2 text-xs font-mono rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/70 outline-none focus:ring-2 focus:ring-cyan-500/30 resize-none"
                                />
                                <button
                                    onClick={handleAttachToken}
                                    disabled={authBusy}
                                    className="w-full px-4 py-2.5 rounded-xl border border-cyan-200 dark:border-cyan-800 text-cyan-700 dark:text-cyan-300 text-xs font-semibold hover:bg-cyan-100/70 dark:hover:bg-cyan-900/20 transition-colors disabled:opacity-60"
                                >
                                    {authBusy ? "Validating..." : "Save and validate token"}
                                </button>
                            </div>
                        </div>
                    )}

                    {authError && (
                        <div className="rounded-xl border border-red-200 dark:border-red-800 bg-red-50/80 dark:bg-red-900/10 px-4 py-3 text-xs text-red-600 dark:text-red-300">
                            {authError}
                        </div>
                    )}
                </div>
            </div>


            {/* Stats */}
            <div className="grid grid-cols-2 lg:grid-cols-7 gap-4">
                <StatCard icon={<Activity className="w-5 h-5" />} label={"Total deployments"} value={totalDeploys} gradient="bg-gradient-to-br from-cyan-500 to-cyan-700" />
                <StatCard icon={<CheckCircle2 className="w-5 h-5" />} label={"Success"} value={successCount} gradient="bg-gradient-to-br from-emerald-500 to-emerald-700" />
                <StatCard icon={<XCircle className="w-5 h-5" />} label={"Failed"} value={failedCount} gradient="bg-gradient-to-br from-red-500 to-red-700" />
                <StatCard icon={<Server className="w-5 h-5" />} label={"Running"} value={runningCount} gradient="bg-gradient-to-br from-indigo-500 to-indigo-700" />
                <StatCard icon={<Clock className="w-5 h-5" />} label={"Awaiting approval"} value={pendingApprovalCount} gradient="bg-gradient-to-br from-amber-500 to-orange-600" />
                <StatCard icon={<Terminal className="w-5 h-5" />} label={"Active jobs"} value={activeJobCount} gradient="bg-gradient-to-br from-cyan-600 to-blue-700" />
                <StatCard icon={<Users className="w-5 h-5" />} label={"Audit operators"} value={auditUserCount} gradient="bg-gradient-to-br from-slate-500 to-slate-700" />
            </div>

            {/* Empty State */}
            {projects.length === 0 && (
                <div className="flex flex-col items-center justify-center py-16 rounded-2xl border-2 border-dashed border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                    <div className="p-4 rounded-2xl bg-cyan-100 dark:bg-cyan-900/30 text-cyan-500 mb-4"><FolderGit2 className="w-8 h-8" /></div>
                    <h3 className="text-sm font-bold text-slate-700 dark:text-slate-200 mb-1">No projects to test yet</h3>
                    <p className="text-xs text-slate-400 mb-4">Click Add project and enter a project name and Git repository URL</p>
                    <button onClick={handleAdd}
                        disabled={!canAdmin}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-500 text-white text-xs font-semibold shadow-sm transition-all">
                        <Plus className="w-3.5 h-3.5" /> Add your first project
                    </button>
                </div>
            )}

            {/* Project Cards */}
            {projects.map((proj) => (
                <div key={proj.key} className="card-hover-lift rounded-2xl border border-slate-200/60 dark:border-slate-800/60 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm overflow-hidden">
                    {/* Project Header */}
                    <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 dark:border-slate-800">
                        <div className="flex items-center gap-3">
                            <div className="p-2 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-500 text-white">
                                <Layers className="w-5 h-5" />
                            </div>
                            <div>
                                <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">{proj.name}</h3>
                                <p className="text-[11px] text-slate-400">
                                    {proj.repos.length} repositories
                                    {proj.has_token
                                        ? <span className="ml-2 inline-flex items-center gap-0.5 text-emerald-500"><Key className="w-2.5 h-2.5" />Token configured</span>
                                        : <span className="ml-2 inline-flex items-center gap-0.5 text-amber-400"><Key className="w-2.5 h-2.5" />No token configured</span>
                                    }
                                </p>
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <button onClick={() => handleRequestProjectApproval(proj.key)}
                                disabled={!canRequest || !!actionLoading[`approval_all_${proj.key}`]}
                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-300 text-[11px] font-semibold transition-all disabled:opacity-50">
                                {actionLoading[`approval_all_${proj.key}`] ? <Loader2 className="w-3 h-3 animate-spin" /> : <Clock className="w-3 h-3" />}
                                Request approval for all
                            </button>
                            <button onClick={() => doAction(`all_${proj.key}`, () => fullDeployAll(proj.key))}
                                disabled={!canAdmin || !!actionLoading[`all_${proj.key}`]}
                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600 text-white text-[11px] font-semibold transition-all disabled:opacity-50 shadow-sm">
                                {actionLoading[`all_${proj.key}`] ? <Loader2 className="w-3 h-3 animate-spin" /> : <Rocket className="w-3 h-3" />}
                                Deploy all directly
                            </button>
                            <button onClick={() => handleEdit(proj)}
                                disabled={!canAdmin}
                                className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 transition-colors" title={"Edit"}>
                                <Pencil className="w-3.5 h-3.5" />
                            </button>
                            <button onClick={() => handleDelete(proj.key, proj.name)}
                                disabled={!canAdmin}
                                className="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-slate-400 hover:text-red-500 transition-colors" title={"Delete"}>
                                <Trash2 className="w-3.5 h-3.5" />
                            </button>
                        </div>
                    </div>

                    {/* Repo Rows */}
                    <div className="divide-y divide-slate-100 dark:divide-slate-800">
                        {proj.repos.map((repo) => {
                            const aid = (a: string) => `${repo.id}_${a}`;
                            const isLoading = (a: string) => !!actionLoading[aid(a)];
                            const isSelected = selectedRepo?.rid === repo.id;

                            return (
                                <div key={repo.id} className={`px-5 py-3.5 transition-colors ${isSelected ? 'bg-cyan-50/50 dark:bg-cyan-900/10' : 'hover:bg-slate-50/50 dark:hover:bg-slate-800/30'}`}>
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-3 min-w-0 flex-1 cursor-pointer"
                                            onClick={() => { setSelectedRepo({ pk: proj.key, rid: repo.id, label: repo.label }); refreshLogs(repo.id); }}>
                                            <div className={`p-2 rounded-lg shrink-0 ${(repo.label.includes('前端') || repo.label.includes("Frontend")) || repo.label.toLowerCase().includes('front')
                                                ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600'
                                                : 'bg-violet-100 dark:bg-violet-900/30 text-violet-600'
                                                }`}>
                                                {(repo.label.includes('前端') || repo.label.includes("Frontend")) || repo.label.toLowerCase().includes('front')
                                                    ? <Globe className="w-4 h-4" />
                                                    : <Server className="w-4 h-4" />}
                                            </div>
                                            <div className="min-w-0 flex-1">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs font-bold text-slate-700 dark:text-slate-200">{repo.label || "Default"}</span>
                                                    {statusBadge(repo.status)}
                                                    {repo.has_memory && (
                                                        <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-gradient-to-r from-purple-100 to-fuchsia-100 dark:from-purple-900/30 dark:to-fuchsia-900/30 text-purple-600 dark:text-purple-400 text-[10px] font-semibold" title={`Successful deployments: ${repo.deploy_count || 0} occurrences`}>
                                                            🧠 {(repo.deploy_count || 0) > 0 ? `×${repo.deploy_count}` : "Deployment memory"}
                                                        </span>
                                                    )}
                                                    {repo.tech_stack && <span className="text-[10px] text-slate-400 bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded max-w-[200px] truncate inline-block align-middle" title={repo.tech_stack}>{repo.tech_stack}</span>}
                                                </div>
                                                <div className="flex items-center gap-3 mt-1 text-[10px] text-slate-400">
                                                    <span className="flex items-center gap-1 truncate">
                                                        <FolderGit2 className="w-2.5 h-2.5 shrink-0" />
                                                        <a href={repo.repo_url} target="_blank" rel="noreferrer" className="hover:text-cyan-500 truncate" onClick={e => e.stopPropagation()}>
                                                            {repo.repo_url.replace(/https?:\/\/[^/]+\//, '').replace('.git', '')}
                                                        </a>
                                                    </span>
                                                    <span className="flex items-center gap-1"><GitBranch className="w-2.5 h-2.5" />{repo.branch}</span>
                                                    {repo.port > 0 && <span>Port: {repo.port}{repo.port_open && <span className="text-emerald-500 ml-0.5">●</span>}</span>}
                                                    {repo.pid && <span>PID: {repo.pid}</span>}
                                                </div>
                                            </div>
                                        </div>

                                        {/* Repo Actions */}
                                        <div className="flex items-center gap-1.5 shrink-0 ml-3">
                                            <button onClick={() => handleRequestRepoApproval(proj.key, repo.id)}
                                                disabled={!canRequest || isLoading('approval_request')} title={"Request deployment approval"} aria-label={"Request deployment approval"}
                                                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 text-[11px] text-amber-600 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-900/40 transition disabled:opacity-50">
                                                {isLoading('approval_request') ? <Loader2 className="w-3 h-3 animate-spin" /> : <Clock className="w-3 h-3" />}
                                            </button>
                                            <button onClick={() => startFullDeploy(proj.key, repo.id, repo.label)}
                                                disabled={!canAdmin || isLoading('full')} title={"Direct deployment"} aria-label={"Direct deployment"}
                                                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-cyan-50 dark:bg-cyan-900/20 border border-cyan-200 dark:border-cyan-800 text-[11px] text-cyan-600 dark:text-cyan-400 hover:bg-cyan-100 dark:hover:bg-cyan-900/40 transition disabled:opacity-50">
                                                {isLoading('full') ? <Loader2 className="w-3 h-3 animate-spin" /> : <Rocket className="w-3 h-3" />}
                                            </button>
                                            <button onClick={() => doAction(aid('clone'), () => cloneRepo(proj.key, repo.id))}
                                                disabled={!canAdmin || isLoading('clone')} title={"Clone"}
                                                className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800 transition disabled:opacity-50">
                                                {isLoading('clone') ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                                            </button>
                                            <button onClick={() => handleAiAnalyze(proj.key, repo.id, repo.label)}
                                                disabled={!canAdmin || !!aiLoading[`${proj.key}_${repo.id}_ai`]} title={"Analyze configuration with AI"} aria-label={"Analyze configuration with AI"}
                                                className="p-1.5 rounded-lg border border-violet-200 dark:border-violet-800 text-violet-500 hover:bg-violet-50 dark:hover:bg-violet-900/20 transition disabled:opacity-50">
                                                {aiLoading[`${proj.key}_${repo.id}_ai`] ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                                            </button>
                                            <button onClick={() => doAction(aid('install'), () => installRepo(proj.key, repo.id))}
                                                disabled={!canAdmin || isLoading('install')} title={"Install dependencies"}
                                                className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800 transition disabled:opacity-50">
                                                {isLoading('install') ? <Loader2 className="w-3 h-3 animate-spin" /> : <Package className="w-3 h-3" />}
                                            </button>
                                            {repo.status === 'running' ? (
                                                <button onClick={() => doAction(aid('stop'), () => stopRepo(proj.key, repo.id))}
                                                    disabled={!canAdmin || isLoading('stop')} title={"Stop"}
                                                    className="p-1.5 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-500 hover:bg-red-100 transition disabled:opacity-50">
                                                    {isLoading('stop') ? <Loader2 className="w-3 h-3 animate-spin" /> : <Square className="w-3 h-3" />}
                                                </button>
                                            ) : (
                                                <button onClick={() => doAction(aid('start'), () => startRepo(proj.key, repo.id))}
                                                    disabled={!canAdmin || isLoading('start')} title={"Start"}
                                                    className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 text-emerald-500 hover:bg-emerald-100 transition disabled:opacity-50">
                                                    {isLoading('start') ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            ))}

            {/* Logs */}
            {selectedRepo && (
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden">
                    <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 dark:border-slate-800">
                        <h3 className="text-sm font-semibold flex items-center gap-2 text-slate-700 dark:text-slate-200">
                            <Terminal className="w-4 h-4 text-cyan-500" />
                            Logs — {selectedRepo.label}
                        </h3>
                        <div className="flex items-center gap-1.5">
                            <button onClick={() => refreshLogs(selectedRepo.rid)} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400" title={"Refresh"}>
                                <RefreshCw className="w-3.5 h-3.5" />
                            </button>
                            <button onClick={() => setSelectedRepo(null)} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400" title={"Close"}>
                                <X className="w-3.5 h-3.5" />
                            </button>
                        </div>
                    </div>
                    <div className="max-h-64 overflow-auto bg-slate-950 p-4 font-mono text-[11px] text-green-400 leading-relaxed">
                        {logs.length === 0 ? <span className="text-slate-500">No logs yet</span> : logs.map((l, i) => (
                            <div key={i} className="whitespace-pre-wrap break-all">
                                <span className="text-slate-600 mr-2 select-none">{String(i + 1).padStart(3, ' ')}</span>{l}
                            </div>
                        ))}
                        <div ref={logEndRef} />
                    </div>
                </div>
            )}

            <div ref={approvalSectionRef}>
                <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                        <Clock className="w-4 h-4 text-amber-500" /> Deployment approvals
                    </h3>
                    <div className="flex items-center gap-2">
                        {approvalContextFilterId ? (
                            <div className="flex items-center gap-2 rounded-full bg-amber-50 dark:bg-amber-900/20 px-2.5 py-1">
                                <span className="text-[10px] font-semibold text-amber-600 dark:text-amber-300">
                                    Showing only approval request {approvalContextFilterId}
                                </span>
                                <button
                                    onClick={clearApprovalContextFilter}
                                    className="text-[10px] font-semibold text-amber-500 hover:text-amber-700 dark:hover:text-amber-200"
                                >
                                    View all
                                </button>
                            </div>
                        ) : null}
                        {focusedApprovalId ? (
                            <span className="rounded-full bg-cyan-50 dark:bg-cyan-900/20 px-2.5 py-1 text-[10px] font-semibold text-cyan-600 dark:text-cyan-300">
                                Located approval request {focusedApprovalId}
                            </span>
                        ) : null}
                        <span className="text-[11px] text-slate-400">
                            Awaiting approval {pendingApprovalCount} requests
                        </span>
                    </div>
                </div>
                <DataTable<DeployApproval>
                    columns={approvalColumns}
                    data={visibleApprovals}
                    rowKey="id"
                    pageSize={6}
                    emptyText={"No approval requests yet"}
                    activeRowKey={focusedApprovalId || null}
                />
            </div>

            <div ref={jobsSectionRef}>
                <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                        <Activity className="w-4 h-4 text-cyan-500" /> Deployment jobs
                    </h3>
                    <div className="flex items-center gap-2">
                        {jobContextFilterId ? (
                            <div className="flex items-center gap-2 rounded-full bg-cyan-50 dark:bg-cyan-900/20 px-2.5 py-1">
                                <span className="text-[10px] font-semibold text-cyan-600 dark:text-cyan-300">
                                    Showing only job {jobContextFilterId}
                                </span>
                                <button
                                    onClick={clearJobContextFilter}
                                    className="text-[10px] font-semibold text-cyan-500 hover:text-cyan-700 dark:hover:text-cyan-200"
                                >
                                    View all
                                </button>
                            </div>
                        ) : null}
                        {focusedJobId ? (
                            <span className="rounded-full bg-cyan-50 dark:bg-cyan-900/20 px-2.5 py-1 text-[10px] font-semibold text-cyan-600 dark:text-cyan-300">
                                Located job {focusedJobId}
                            </span>
                        ) : null}
                        <span className="text-[11px] text-slate-400">
                            Active {activeJobCount} requests
                        </span>
                    </div>
                </div>
                <DataTable<DeployJob>
                    columns={jobColumns}
                    data={visibleJobs}
                    rowKey="id"
                    pageSize={6}
                    emptyText={"No deployment jobs yet"}
                    activeRowKey={focusedJobId || null}
                />
            </div>

            <div>
                <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                        <ShieldCheck className="w-4 h-4 text-slate-500" /> Deployment audit
                    </h3>
                    <span className="text-[11px] text-slate-400">
                        Latest {auditLogs.length} entries
                    </span>
                </div>
                <div className="mb-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-900/50 px-4 py-3">
                    <div className="grid gap-3 lg:grid-cols-[1fr_1fr_1fr_auto]">
                        <label className="space-y-1">
                            <span className="text-[10px] uppercase tracking-wider text-slate-400">Action</span>
                            <select
                                aria-label={"Filter audit actions"}
                                value={auditDraft.action}
                                onChange={(e) => setAuditDraft(prev => ({ ...prev, action: e.target.value }))}
                                className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/70 px-3 py-2 text-xs text-slate-600 dark:text-slate-200 outline-none focus:ring-2 focus:ring-cyan-500/30"
                            >
                                {DEPLOY_AUDIT_ACTION_OPTIONS.map(item => (
                                    <option key={item.value || 'all'} value={item.value}>{item.label}</option>
                                ))}
                            </select>
                        </label>
                        <label className="space-y-1">
                            <span className="text-[10px] uppercase tracking-wider text-slate-400">Project</span>
                            <select
                                aria-label={"Filter audit projects"}
                                value={auditDraft.projectKey}
                                onChange={(e) => setAuditDraft(prev => ({ ...prev, projectKey: e.target.value }))}
                                className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/70 px-3 py-2 text-xs text-slate-600 dark:text-slate-200 outline-none focus:ring-2 focus:ring-cyan-500/30"
                            >
                                <option value="">All projects</option>
                                {auditProjectOptions.map(projectKey => (
                                    <option key={projectKey} value={projectKey}>{projectKey}</option>
                                ))}
                            </select>
                        </label>
                        <label className="space-y-1">
                            <span className="text-[10px] uppercase tracking-wider text-slate-400">Operator ID</span>
                            <input
                                aria-label={"Filter audit operators"}
                                value={auditDraft.userId}
                                onChange={(e) => setAuditDraft(prev => ({ ...prev, userId: e.target.value }))}
                                placeholder={"Example: user-1"}
                                className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/70 px-3 py-2 text-xs text-slate-600 dark:text-slate-200 outline-none focus:ring-2 focus:ring-cyan-500/30"
                            />
                        </label>
                        <div className="flex items-end gap-2">
                            <button
                                onClick={handleApplyAuditFilter}
                                disabled={auditLoading}
                                className="px-3 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-500 text-white text-xs font-semibold hover:from-cyan-600 hover:to-blue-600 transition-all disabled:opacity-50"
                            >
                                {auditLoading ? "Filtering..." : "Filter audit"}
                            </button>
                            <button
                                onClick={handleResetAuditFilter}
                                disabled={auditLoading}
                                className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors disabled:opacity-50"
                            >
                                Reset
                            </button>
                        </div>
                    </div>
                    {auditError ? (
                        <div className="mt-3 rounded-lg border border-red-200 dark:border-red-800 bg-red-50/70 dark:bg-red-900/10 px-3 py-2 text-xs text-red-500">
                            {auditError}
                        </div>
                    ) : null}
                </div>
                <DataTable<DeployAuditLog>
                    columns={auditColumns}
                    data={auditLogs}
                    rowKey="log_id"
                    pageSize={6}
                    emptyText={"No audit records yet"}
                    loading={auditLoading}
                    onRowClick={setSelectedAuditLog}
                />
                {selectedAuditLog ? (
                    <div className="mt-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/70 overflow-hidden">
                        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 dark:border-slate-800">
                            <div>
                                <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Audit details</h4>
                                <p className="text-[11px] text-slate-400">
                                    {deployAuditActionLabel(selectedAuditLog.action)} · {formatDateTime(selectedAuditLog.timestamp)}
                                </p>
                            </div>
                            <button
                                onClick={() => setSelectedAuditLog(null)}
                                className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                                title={"Close audit details"}
                            >
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                        <div className="grid gap-4 px-4 py-4 lg:grid-cols-4">
                            <div className="rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-900/50 px-3 py-3">
                                <div className="text-[10px] uppercase tracking-wider text-slate-400">Project</div>
                                <div className="mt-1 text-xs font-semibold text-cyan-600 dark:text-cyan-300">{selectedAuditLog.project_key || '-'}</div>
                            </div>
                            <div className="rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-900/50 px-3 py-3">
                                <div className="text-[10px] uppercase tracking-wider text-slate-400">Operator</div>
                                <div className="mt-1 text-xs font-semibold text-slate-600 dark:text-slate-200">{selectedAuditLog.username || selectedAuditLog.user_id || '-'}</div>
                                <div className="text-[10px] text-slate-400 mt-1">{selectedAuditLog.user_id || '-'}</div>
                            </div>
                            <div className="rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-900/50 px-3 py-3">
                                <div className="text-[10px] uppercase tracking-wider text-slate-400">Resource</div>
                                <div className="mt-1 text-xs font-semibold text-slate-600 dark:text-slate-200">{selectedAuditLog.resource_type || '-'}</div>
                                <div className="text-[10px] text-slate-400 mt-1">{selectedAuditLog.resource_id || '-'}</div>
                            </div>
                            <div className="rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-900/50 px-3 py-3">
                                <div className="text-[10px] uppercase tracking-wider text-slate-400">Source IP</div>
                                <div className="mt-1 text-xs font-semibold text-slate-600 dark:text-slate-200">{selectedAuditLog.ip_address || '-'}</div>
                            </div>
                        </div>
                        {hasAuditLinkedResources ? (
                            <div className="px-4 pb-4">
                                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-900/40 px-4 py-3">
                                    <div className="flex flex-wrap items-start justify-between gap-3">
                                        <div>
                                            <div className="text-[10px] uppercase tracking-wider text-slate-400">Linked objects</div>
                                            <div className="mt-1 text-xs text-slate-500">
                                                Open approval requests, deployment jobs, and deployment records directly from the audit record.
                                            </div>
                                        </div>
                                        <div className="flex flex-wrap gap-2">
                                            {auditLinkedResources.approvalId ? (
                                                <button
                                                    onClick={handleOpenAuditApproval}
                                                    disabled={auditLinkedLoading === 'approval'}
                                                    className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-200 dark:border-emerald-800 px-3 py-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 transition-colors disabled:opacity-50"
                                                >
                                                    {auditLinkedLoading === 'approval' ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
                                                    View approval request
                                                </button>
                                            ) : null}
                                            {auditLinkedResources.jobId ? (
                                                <button
                                                    onClick={handleOpenAuditJob}
                                                    disabled={auditLinkedLoading === 'job'}
                                                    className="inline-flex items-center gap-1.5 rounded-lg border border-cyan-200 dark:border-cyan-800 px-3 py-1.5 text-xs font-semibold text-cyan-600 dark:text-cyan-300 hover:bg-cyan-50 dark:hover:bg-cyan-900/20 transition-colors disabled:opacity-50"
                                                >
                                                    {auditLinkedLoading === 'job' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Activity className="w-3 h-3" />}
                                                    View job
                                                </button>
                                            ) : null}
                                            {auditLinkedResources.recordId ? (
                                                <button
                                                    onClick={handleOpenAuditRecord}
                                                    disabled={auditLinkedLoading === 'record'}
                                                    className="inline-flex items-center gap-1.5 rounded-lg border border-violet-200 dark:border-violet-800 px-3 py-1.5 text-xs font-semibold text-violet-600 dark:text-violet-300 hover:bg-violet-50 dark:hover:bg-violet-900/20 transition-colors disabled:opacity-50"
                                                >
                                                    {auditLinkedLoading === 'record' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Terminal className="w-3 h-3" />}
                                                    Open deployment record
                                                </button>
                                            ) : null}
                                        </div>
                                    </div>
                                    <div className="mt-3 grid gap-3 md:grid-cols-3">
                                        {auditLinkedResources.approvalId ? (
                                            <div className="rounded-lg border border-slate-200/70 dark:border-slate-700/70 bg-white/80 dark:bg-slate-950/40 px-3 py-2">
                                                <div className="text-[10px] uppercase tracking-wider text-slate-400">Approval request ID</div>
                                                <div className="mt-1 text-xs font-mono text-slate-600 dark:text-slate-200">{auditLinkedResources.approvalId}</div>
                                            </div>
                                        ) : null}
                                        {auditLinkedResources.jobId ? (
                                            <div className="rounded-lg border border-slate-200/70 dark:border-slate-700/70 bg-white/80 dark:bg-slate-950/40 px-3 py-2">
                                                <div className="text-[10px] uppercase tracking-wider text-slate-400">Job ID</div>
                                                <div className="mt-1 text-xs font-mono text-slate-600 dark:text-slate-200">{auditLinkedResources.jobId}</div>
                                            </div>
                                        ) : null}
                                        {auditLinkedResources.recordId ? (
                                            <div className="rounded-lg border border-slate-200/70 dark:border-slate-700/70 bg-white/80 dark:bg-slate-950/40 px-3 py-2">
                                                <div className="text-[10px] uppercase tracking-wider text-slate-400">Record ID</div>
                                                <div className="mt-1 text-xs font-mono text-slate-600 dark:text-slate-200">{auditLinkedResources.recordId}</div>
                                            </div>
                                        ) : null}
                                    </div>
                                    {auditLinkedError ? (
                                        <div className="mt-3 rounded-lg border border-red-200 dark:border-red-800 bg-red-50/70 dark:bg-red-900/10 px-3 py-2 text-xs text-red-500">
                                            {auditLinkedError}
                                        </div>
                                    ) : null}
                                </div>
                            </div>
                        ) : null}
                        {linkedApproval ? (
                            <div className="px-4 pb-4">
                                <div className="rounded-xl border border-emerald-200 dark:border-emerald-800 bg-emerald-50/70 dark:bg-emerald-900/10 px-4 py-3">
                                    <div className="flex flex-wrap items-start justify-between gap-3">
                                        <div>
                                            <div className="text-[10px] uppercase tracking-wider text-emerald-500">Linked approval request</div>
                                            <div className="mt-1 text-sm font-semibold text-emerald-700 dark:text-emerald-300">{linkedApproval.repo_label || linkedApproval.project_key || '-'}</div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <button
                                                onClick={() => applyApprovalContextFilter(linkedApproval.id)}
                                                className="rounded-lg border border-emerald-200 dark:border-emerald-700 px-2.5 py-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-300 hover:bg-emerald-100/70 dark:hover:bg-emerald-900/20 transition-colors"
                                            >
                                                Filter approval context
                                            </button>
                                            <button
                                                onClick={() => focusApprovalRow(linkedApproval.id)}
                                                className="rounded-lg border border-emerald-200 dark:border-emerald-700 px-2.5 py-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-300 hover:bg-emerald-100/70 dark:hover:bg-emerald-900/20 transition-colors"
                                            >
                                                Go to approval list
                                            </button>
                                            <code className="rounded bg-white/80 dark:bg-slate-950/40 px-2 py-1 text-[11px] font-mono text-emerald-700 dark:text-emerald-200">{linkedApproval.id}</code>
                                            {statusBadge(linkedApproval.status)}
                                        </div>
                                    </div>
                                    <div className="mt-3 grid gap-3 md:grid-cols-3">
                                        <div>
                                            <div className="text-[10px] uppercase tracking-wider text-emerald-500/70">Requested by</div>
                                            <div className="mt-1 text-xs text-slate-600 dark:text-slate-200">{linkedApproval.requested_by_name || linkedApproval.requested_by || '-'}</div>
                                        </div>
                                        <div>
                                            <div className="text-[10px] uppercase tracking-wider text-emerald-500/70">Approver</div>
                                            <div className="mt-1 text-xs text-slate-600 dark:text-slate-200">{linkedApproval.reviewed_by_name || linkedApproval.reviewed_by || "Awaiting approval"}</div>
                                        </div>
                                        <div>
                                            <div className="text-[10px] uppercase tracking-wider text-emerald-500/70">Deployment record</div>
                                            <div className="mt-1 flex flex-wrap items-center gap-2">
                                                <code className="text-[11px] font-mono text-slate-600 dark:text-slate-200">{linkedApproval.record_id || '-'}</code>
                                                {linkedApproval.record_status ? statusBadge(linkedApproval.record_status) : null}
                                            </div>
                                        </div>
                                    </div>
                                    {linkedApproval.review_comment || linkedApproval.message ? (
                                        <div className="mt-3 text-xs text-emerald-700/80 dark:text-emerald-300/80">
                                            {linkedApproval.review_comment || linkedApproval.message}
                                        </div>
                                    ) : null}
                                </div>
                            </div>
                        ) : null}
                        {linkedJob ? (
                            <div className="px-4 pb-4">
                                <div className="rounded-xl border border-cyan-200 dark:border-cyan-800 bg-cyan-50/70 dark:bg-cyan-900/10 px-4 py-3">
                                    <div className="flex flex-wrap items-start justify-between gap-3">
                                        <div>
                                            <div className="text-[10px] uppercase tracking-wider text-cyan-500">Linked job</div>
                                            <div className="mt-1 text-sm font-semibold text-cyan-700 dark:text-cyan-300">{linkedJob.repo_label || linkedJob.project_key || '-'}</div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <button
                                                onClick={() => applyJobContextFilter(linkedJob.id)}
                                                className="rounded-lg border border-cyan-200 dark:border-cyan-700 px-2.5 py-1 text-[11px] font-semibold text-cyan-600 dark:text-cyan-300 hover:bg-cyan-100/70 dark:hover:bg-cyan-900/20 transition-colors"
                                            >
                                                Filter job context
                                            </button>
                                            <button
                                                onClick={() => focusJobRow(linkedJob.id)}
                                                className="rounded-lg border border-cyan-200 dark:border-cyan-700 px-2.5 py-1 text-[11px] font-semibold text-cyan-600 dark:text-cyan-300 hover:bg-cyan-100/70 dark:hover:bg-cyan-900/20 transition-colors"
                                            >
                                                Go to job list
                                            </button>
                                            {['queued', 'running'].includes(linkedJob.status) ? (
                                                <button
                                                    onClick={() => handleCancelJob(linkedJob)}
                                                    disabled={!canAdmin || !!actionLoading[`job_cancel_${linkedJob.id}`]}
                                                    className="rounded-lg border border-red-200 dark:border-red-700 px-2.5 py-1 text-[11px] font-semibold text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-50"
                                                >
                                                    {actionLoading[`job_cancel_${linkedJob.id}`] ? "Canceling..." : "Cancel job"}
                                                </button>
                                            ) : null}
                                            {linkedJob.record_id ? (
                                                <button
                                                    onClick={() => applyHistoryContextFilter(linkedJob.record_id)}
                                                    className="rounded-lg border border-cyan-200 dark:border-cyan-700 px-2.5 py-1 text-[11px] font-semibold text-cyan-600 dark:text-cyan-300 hover:bg-cyan-100/70 dark:hover:bg-cyan-900/20 transition-colors"
                                                >
                                                    Filter deployment context
                                                </button>
                                            ) : null}
                                            {linkedJob.record_id ? (
                                                <button
                                                    onClick={() => focusHistoryRow(linkedJob.record_id)}
                                                    className="rounded-lg border border-cyan-200 dark:border-cyan-700 px-2.5 py-1 text-[11px] font-semibold text-cyan-600 dark:text-cyan-300 hover:bg-cyan-100/70 dark:hover:bg-cyan-900/20 transition-colors"
                                                >
                                                    Go to deployment history
                                                </button>
                                            ) : null}
                                            <code className="rounded bg-white/80 dark:bg-slate-950/40 px-2 py-1 text-[11px] font-mono text-cyan-700 dark:text-cyan-200">{linkedJob.id}</code>
                                            {statusBadge(linkedJob.status)}
                                        </div>
                                    </div>
                                    <div className="mt-3 grid gap-3 md:grid-cols-3">
                                        <div>
                                            <div className="text-[10px] uppercase tracking-wider text-cyan-500/70">Action</div>
                                            <div className="mt-1 text-xs text-slate-600 dark:text-slate-200">{actionLabel(linkedJob.action)}</div>
                                        </div>
                                        <div>
                                            <div className="text-[10px] uppercase tracking-wider text-cyan-500/70">Branch</div>
                                            <div className="mt-1 text-xs text-slate-600 dark:text-slate-200">{linkedJob.branch || '-'}</div>
                                        </div>
                                        <div>
                                            <div className="text-[10px] uppercase tracking-wider text-cyan-500/70">Deployment record</div>
                                            <div className="mt-1 flex flex-wrap items-center gap-2">
                                                <code className="text-[11px] font-mono text-slate-600 dark:text-slate-200">{linkedJob.record_id || '-'}</code>
                                                {linkedJob.record_status ? statusBadge(linkedJob.record_status) : null}
                                            </div>
                                        </div>
                                    </div>
                                    {linkedJob.message ? (
                                        <div className="mt-3 text-xs text-cyan-700/80 dark:text-cyan-300/80">
                                            {linkedJob.message}
                                        </div>
                                    ) : null}
                                </div>
                            </div>
                        ) : null}
                        <div className="px-4 pb-4">
                            <div className="mb-2 text-[10px] uppercase tracking-wider text-slate-400">Raw details</div>
                            <pre className="max-h-64 overflow-auto rounded-xl bg-slate-950 px-4 py-3 text-[11px] leading-relaxed text-slate-200">
                                {formatAuditDetails(selectedAuditLog.details)}
                            </pre>
                        </div>
                    </div>
                ) : null}
            </div>

            {/* History */}
            {history.length > 0 && (
                <div ref={historySectionRef}>
                    <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                            <Clock className="w-4 h-4 text-slate-400" /> Deployment history
                        </h3>
                        <div className="flex items-center gap-2">
                            {historyContextFilterId ? (
                                <div className="flex items-center gap-2 rounded-full bg-amber-50 dark:bg-amber-900/20 px-2.5 py-1">
                                    <span className="text-[10px] font-semibold text-amber-600 dark:text-amber-300">
                                        Showing only record {historyContextFilterId}
                                    </span>
                                    <button
                                        onClick={clearHistoryContextFilter}
                                        className="text-[10px] font-semibold text-amber-500 hover:text-amber-700 dark:hover:text-amber-200"
                                    >
                                        View all
                                    </button>
                                </div>
                            ) : null}
                            {focusedHistoryId ? (
                                <span className="rounded-full bg-cyan-50 dark:bg-cyan-900/20 px-2.5 py-1 text-[10px] font-semibold text-cyan-600 dark:text-cyan-300">
                                    Located record {focusedHistoryId}
                                </span>
                            ) : null}
                            <button onClick={handleClearHistory}
                                disabled={!canAdmin}
                                className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-medium border border-red-200 dark:border-red-800 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors">
                                <Trash2 className="w-3 h-3" /> Clear all
                            </button>
                        </div>
                    </div>
                    <DataTable<DeployRecord>
                        columns={historyColumns}
                        data={visibleHistory}
                        rowKey="id"
                        pageSize={8}
                        emptyText={"No records yet"}
                        activeRowKey={focusedHistoryId || null}
                    />
                </div>
            )}

            <ProjectDialog
                open={dialogOpen} onClose={() => setDialogOpen(false)}
                onSubmit={handleDialogSubmit} mode={dialogMode}
                initialName={editInitialName} initialRepos={editInitialRepos}
                initialToken={editInitialToken}
            />

            {/* AI configuration analysis dialog*/}
            {aiResult && aiResultRepo && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-md z-50 overflow-y-auto flex justify-center py-8 px-4 animate-in fade-in duration-300" onClick={closeAiDialog}>
                    <div className="bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl rounded-2xl shadow-2xl shadow-black/20 dark:shadow-black/50 border border-slate-200/80 dark:border-slate-700/80 w-full max-w-xl flex flex-col overflow-hidden my-auto" onClick={e => e.stopPropagation()}
                        style={{ animation: 'fadeInScale .2s ease-out', maxHeight: 'calc(100vh - 4rem)' }}>
                        {/* Gradient title bar*/}
                        <div className="bg-gradient-to-r from-violet-500 via-purple-500 to-indigo-500 px-6 py-4 flex items-center justify-between">
                            <h3 className="text-white text-sm font-bold flex items-center gap-2">
                                <Sparkles className="w-4 h-4" />
                                AI configuration analysis · {aiResultRepo.label}
                            </h3>
                            <button onClick={closeAiDialog} className="text-white/70 hover:text-white transition">
                                <X className="w-4 h-4" />
                            </button>
                        </div>

                        {/* Deployment memory notice*/}
                        {aiResult.has_memory && (
                            <div className="mx-5 mt-4 px-3 py-2 rounded-lg bg-gradient-to-r from-purple-50 to-fuchsia-50 dark:from-purple-900/20 dark:to-fuchsia-900/20 border border-purple-200/50 dark:border-purple-700/30 flex items-center gap-2">
                                <span className="text-base">🧠</span>
                                <div className="text-[11px] text-purple-600 dark:text-purple-400">
                                    <span className="font-semibold">Deployment memory is active</span>
                                    <span className="text-purple-400 dark:text-purple-500 ml-1.5">
                                        · Total {aiResult.deploy_count || 0} successful deployments
                                        {aiResult.last_success && ` · Last: ${new Date(aiResult.last_success).toLocaleString('en-US', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}`}
                                    </span>
                                </div>
                            </div>
                        )}

                        <div className="mx-5 mt-4 rounded-lg border border-sky-200/70 dark:border-sky-800/40 bg-sky-50/80 dark:bg-sky-900/10 px-3 py-2.5 text-[11px] leading-relaxed text-sky-700 dark:text-sky-300">
                            This step only generates and reviews deployment configuration. Cloning, installation, and startup begin only after you click Apply configuration and deploy.
                        </div>

                        <div className="flex-1 overflow-y-auto">
                            {aiResult.error ? (
                                <div className="p-6 text-center">
                                    <XCircle className="w-10 h-10 text-red-400 mx-auto mb-3" />
                                    <p className="text-sm text-red-500 font-medium">{aiResult.error}</p>
                                </div>
                            ) : (
                                <div className="p-5 space-y-5">
                                    {/* Confidence and technology stack*/}
                                    <div className="flex items-start gap-4">
                                        <div className="flex-1 min-w-0">
                                            <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Technology stack</label>
                                            <input value={aiEditForm.tech_stack} onChange={e => setAiEditForm(p => ({ ...p, tech_stack: e.target.value }))}
                                                className="w-full mt-1 px-3 py-2 text-sm font-semibold rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 focus:ring-2 focus:ring-violet-500/30 focus:border-violet-400 outline-none transition" />
                                        </div>
                                        <div className="text-center shrink-0 pt-3">
                                            <div className="w-14 h-14 rounded-full border-4 flex items-center justify-center text-sm font-bold"
                                                style={{
                                                    borderColor: (aiResult.confidence || 0) > 0.8 ? '#10b981' : (aiResult.confidence || 0) > 0.5 ? '#f59e0b' : '#ef4444',
                                                    color: (aiResult.confidence || 0) > 0.8 ? '#10b981' : (aiResult.confidence || 0) > 0.5 ? '#f59e0b' : '#ef4444'
                                                }}>
                                                {((aiResult.confidence || 0) * 100).toFixed(0)}%
                                            </div>
                                            <span className="text-[9px] text-slate-400 mt-0.5 block">Confidence</span>
                                        </div>
                                    </div>

                                    {/* Editable command configuration*/}
                                    <div className="space-y-3">
                                        <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Deployment commands</div>
                                        {([['install_cmd', "📦 Install command"], ['start_cmd', "▶️ Start command"], ['build_cmd', "🔨 Build command"]] as const).map(([key, label]) => (
                                            <div key={key}>
                                                <label className="text-[11px] text-slate-500 mb-1 block">{label}</label>
                                                <input value={(aiEditForm as any)[key]} onChange={e => setAiEditForm(p => ({ ...p, [key]: e.target.value }))}
                                                    className="w-full px-3 py-2 text-xs font-mono rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 focus:ring-2 focus:ring-violet-500/30 focus:border-violet-400 outline-none transition"
                                                    placeholder={"Leave blank to omit"} />
                                            </div>
                                        ))}
                                        <div>
                                            <label className="text-[11px] text-slate-500 mb-1 block">🔌 Port</label>
                                            <input type="number" value={aiEditForm.port || ''} onChange={e => setAiEditForm(p => ({ ...p, port: parseInt(e.target.value) || 0 }))}
                                                className="w-24 px-3 py-2 text-xs font-mono rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 focus:ring-2 focus:ring-violet-500/30 focus:border-violet-400 outline-none transition"
                                                placeholder={"Port"} />
                                        </div>
                                    </div>

                                    {/* Notes*/}
                                    {aiResult.notes && (
                                        <div className="rounded-xl bg-amber-50/80 dark:bg-amber-900/10 border border-amber-200/60 dark:border-amber-800/40 p-4">
                                            <div className="text-[10px] font-semibold text-amber-600 dark:text-amber-400 uppercase tracking-wider mb-1.5">💡 AI suggestions</div>
                                            <p className="text-xs text-amber-700 dark:text-amber-300 leading-relaxed max-h-28 overflow-y-auto">{aiResult.notes}</p>
                                        </div>
                                    )}

                                    {/* Suggested pom.xml changes*/}
                                    {aiResult.suggested_changes && aiResult.suggested_changes.length > 0 && (
                                        <div className="rounded-xl bg-violet-50/80 dark:bg-violet-900/10 border border-violet-200/60 dark:border-violet-800/40 p-4">
                                            <div className="text-[10px] font-semibold text-violet-600 dark:text-violet-400 uppercase tracking-wider mb-2">🔧 Suggested code changes (applied automatically before deployment)</div>
                                            <div className="space-y-2">
                                                {aiResult.suggested_changes.map((ch, i) => (
                                                    <div key={i} className="flex items-start gap-2 text-xs">
                                                        <span className="text-violet-500 mt-0.5">📄</span>
                                                        <div>
                                                            <div className="font-mono text-violet-700 dark:text-violet-300">{ch.file}</div>
                                                            <div className="text-slate-500 dark:text-slate-400">{ch.description}</div>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                            <p className="text-[10px] text-violet-500/70 mt-2 italic">Apply configuration and deploy applies these changes before starting deployment</p>
                                        </div>
                                    )}

                                    {/* Environment variables*/}
                                    {aiResult.effective_env_vars && Object.keys(aiResult.effective_env_vars).length > 0 && (
                                        <div className="rounded-xl bg-emerald-50/80 dark:bg-emerald-900/10 border border-emerald-200/60 dark:border-emerald-800/40 p-4">
                                            <div className="flex items-center justify-between gap-3 mb-2">
                                                <div>
                                                    <div className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">Currently active environment variables</div>
                                                    <div className="text-[10px] text-emerald-500/80 mt-1">
                                                        Source: {aiResult.effective_env_source || "Current deployment directory"}
                                                        {' · '} Used by default for this and future deployments when no supplemental values are entered
                                                    </div>
                                                </div>
                                                <button
                                                    type="button"
                                                    onClick={() => {
                                                        setDeployContext(p => ({ ...p, env_vars: aiResult.effective_env_text || formatEnvVars(aiResult.effective_env_vars) }));
                                                        setShowContext(true);
                                                    }}
                                                    className="px-3 py-1.5 rounded-lg border border-emerald-200 dark:border-emerald-700 text-[10px] font-semibold text-emerald-600 dark:text-emerald-300 hover:bg-emerald-100/70 dark:hover:bg-emerald-900/30 transition-colors"
                                                >
                                                    Load into supplemental settings
                                                </button>
                                            </div>
                                            <div className="space-y-1 max-h-24 overflow-y-auto">
                                                {Object.entries(aiResult.effective_env_vars).map(([k, v]) => (
                                                    <div key={k} className="text-xs font-mono flex gap-1">
                                                        <span className="text-emerald-600 dark:text-emerald-400 font-semibold">{k}</span><span className="text-slate-400">=</span><span className="text-slate-600 dark:text-slate-300 break-all">{v}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {aiResult.env_vars && Object.keys(aiResult.env_vars).length > 0 && (
                                        <div className="rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/60 dark:border-slate-700/50 p-4">
                                            <div className="flex items-center justify-between gap-3 mb-2">
                                                <div>
                                                    <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">AI environment variable suggestions</div>
                                                    <div className="text-[10px] text-slate-400 mt-1">For reference only. Suggestions affect future deployments only after you add them to supplemental settings.</div>
                                                </div>
                                                <button
                                                    type="button"
                                                    onClick={() => {
                                                        setDeployContext(p => ({ ...p, env_vars: formatEnvVars(aiResult.env_vars) }));
                                                        setShowContext(true);
                                                    }}
                                                    className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-[10px] font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                                                >
                                                    Replace supplemental settings with suggestions
                                                </button>
                                            </div>
                                            <div className="space-y-1 max-h-24 overflow-y-auto">
                                                {Object.entries(aiResult.env_vars).map(([k, v]) => (
                                                    <div key={k} className="text-xs font-mono flex gap-1">
                                                        <span className="text-violet-500 font-semibold">{k}</span><span className="text-slate-400">=</span><span className="text-slate-600 dark:text-slate-300 break-all">{v}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Collapsible deployment context*/}
                                    {showContext && (
                                        <div className="rounded-xl bg-sky-50/60 dark:bg-sky-900/10 border border-sky-200/60 dark:border-sky-800/40 p-4 space-y-3">
                                            <div className="text-[10px] font-semibold text-sky-600 dark:text-sky-400 uppercase tracking-wider">📋 Deployment context</div>
                                            <div className="text-[11px] text-sky-700/80 dark:text-sky-300/80 leading-relaxed">
                                                {aiResult.env_apply_behavior || "Leave blank to keep active environment variables. Entered KEY=VALUE pairs are merged into the existing .env and remain effective for subsequent deployments."}
                                            </div>
                                            <div>
                                                <label className="text-[11px] text-slate-500 mb-1 block">🖥 Target server</label>
                                                <input value={deployContext.server_address}
                                                    onChange={e => setDeployContext(p => ({ ...p, server_address: e.target.value }))}
                                                    className="w-full px-3 py-2 text-xs font-mono rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 focus:ring-2 focus:ring-sky-500/30 focus:border-sky-400 outline-none transition"
                                                    placeholder={"Example: 192.168.1.100 or deploy.example.com"} />
                                            </div>
                                            <div>
                                                <label className="text-[11px] text-slate-500 mb-1 block">🗄 Database connection</label>
                                                <input value={deployContext.db_connection}
                                                    onChange={e => setDeployContext(p => ({ ...p, db_connection: e.target.value }))}
                                                    className="w-full px-3 py-2 text-xs font-mono rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 focus:ring-2 focus:ring-sky-500/30 focus:border-sky-400 outline-none transition"
                                                    placeholder={"Example: mysql://root:pwd@localhost:3306/mydb"} />
                                            </div>
                                            <div>
                                                <label className="text-[11px] text-slate-500 mb-1 block">🔑 Environment variables (one KEY=VALUE per line)</label>
                                                {deployContext.env_vars && (
                                                    <div className="mb-1 text-[10px] text-sky-600 dark:text-sky-300">Saved values override or supplement variables starting with the next deployment. Existing variables not listed here are preserved.</div>
                                                )}
                                                <textarea value={deployContext.env_vars}
                                                    onChange={e => setDeployContext(p => ({ ...p, env_vars: e.target.value }))}
                                                    className="w-full px-3 py-2 text-xs font-mono rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 focus:ring-2 focus:ring-sky-500/30 focus:border-sky-400 outline-none transition resize-y min-h-[60px]"
                                                    rows={3}
                                                    placeholder={"REDIS_HOST=127.0.0.1\nNACOS_SERVER=localhost:8848"} />
                                            </div>
                                            <div>
                                                <label className="text-[11px] text-slate-500 mb-1 block">📝 Other notes</label>
                                                <textarea value={deployContext.user_notes}
                                                    onChange={e => setDeployContext(p => ({ ...p, user_notes: e.target.value }))}
                                                    className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 focus:ring-2 focus:ring-sky-500/30 focus:border-sky-400 outline-none transition resize-y min-h-[40px]"
                                                    rows={2}
                                                    placeholder={"Example: Start Nacos and Redis first"} />
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>

                        {/* Bottom action bar with four buttons*/}
                        {!aiResult.error && (
                            <div className="px-5 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30">
                                <div className="flex gap-2 flex-wrap">
                                    <button onClick={() => setShowContext(v => !v)}
                                        className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold rounded-xl border transition-all active:scale-[0.98] ${showContext
                                            ? 'bg-sky-50 border-sky-300 text-sky-600 dark:bg-sky-900/20 dark:border-sky-700 dark:text-sky-400'
                                            : 'border-slate-200 dark:border-slate-700 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'
                                            }`}>
                                        💬 {showContext ? "Hide supplemental settings" : "Supplemental settings"}
                                    </button>
                                    {showContext && (
                                        <button onClick={handleAiRefine} disabled={aiRefining}
                                            className="flex items-center gap-1.5 px-4 py-2.5 bg-gradient-to-r from-sky-500 to-blue-500 hover:from-sky-600 hover:to-blue-600 disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow-lg shadow-sky-500/20 transition-all active:scale-[0.98]">
                                            {aiRefining ? "🔄 Analyzing again..." : "🤖 Analyze again"}
                                        </button>
                                    )}
                                    <div className="flex-1" />
                                    <button onClick={handleApplyAiConfig}
                                        className="flex items-center gap-1.5 px-5 py-2.5 bg-gradient-to-r from-emerald-500 to-green-500 hover:from-emerald-600 hover:to-green-600 text-white text-xs font-semibold rounded-xl shadow-lg shadow-emerald-500/20 transition-all active:scale-[0.98]">
                                        🚀 Apply configuration and deploy
                                    </button>
                                    <button onClick={closeAiDialog}
                                        className="px-4 py-2.5 border border-slate-200 dark:border-slate-700 rounded-xl text-xs text-slate-500 hover:bg-white dark:hover:bg-slate-800 transition-colors">
                                        Cancel
                                    </button>
                                </div>
                                {aiResult.source === 'ai_refined' && (
                                    <div className="mt-2 px-1 text-[10px] text-emerald-500 font-medium">✨ Analysis configuration updated using supplemental settings</div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );

    return (
        <>
            {mainContent}
            <ApprovalReviewDialog
                open={approvalDialog.open}
                action={approvalDialog.action}
                targetLabel={approvalDialog.targetLabel}
                comment={approvalDialog.comment}
                submitting={!!actionLoading[`${approvalDialog.approvalId}_${approvalDialog.action}`]}
                onCommentChange={(value) => setApprovalDialog(prev => ({ ...prev, comment: value }))}
                onCancel={closeApprovalDialog}
                onSubmit={submitApprovalReview}
            />
            <DeployProgressPanel state={deployProgress} onClose={closeProgress} />
        </>
    );
};

export default DeployPage;
