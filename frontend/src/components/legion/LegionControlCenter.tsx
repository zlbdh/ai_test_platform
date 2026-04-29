import React, { useEffect, useMemo, useState } from 'react';
import {
    AlertTriangle,
    CheckCircle2,
    Clock,
    Filter,
    Loader2,
    PlayCircle,
    Shield,
    Sparkles,
    XCircle,
} from '../icons';
import DataTable, { type DataTableColumn } from '../ui/DataTable';
import {
    approveRun,
    executeCommand,
    getNotificationPlatformBindingMe,
    getCommandRun,
    getReleaseRiskAssessment,
    issueNotificationPlatformBindingCode,
    listCommandRuns,
    listCommands,
    listExplorationFindings,
    listExplorationSessions,
    listReleaseRiskAssessments,
    rejectRun,
    revokeNotificationPlatformBinding,
    type CommandDefinition,
    type CommandRun,
    type ExperienceFinding,
    type ExplorationSession,
    type NotificationPlatformBinding,
    type NotificationPlatformBindingCode,
    type ReleaseRiskAssessment,
    type ReleaseRiskBlocker,
    type ReleaseDeployResult,
    type ReleaseRiskReviewSummary,
} from '../../services/legionControlService';
import type { ControlAuthProfile } from '../../services/controlAuthService';
import { useLegionControlStore } from '../../stores';
import type { LegionTabId } from '../../stores/legionControlStore';

interface LegionControlCenterProps {
    profile: ControlAuthProfile;
    selectedRunId: string | null;
    selectedSessionId: string | null;
    selectedAssessmentId: string | null;
    selectedFindingId?: string | null;
    onSelectRun: (runId: string | null) => void;
    onSelectSession: (sessionId: string | null) => void;
    onSelectAssessment: (assessmentId: string | null) => void;
    onUpdateSelection?: (patch: {
        tab?: LegionTabId;
        runId?: string | null;
        sessionId?: string | null;
        assessmentId?: string | null;
        findingId?: string | null;
    }) => void;
}

interface ReleaseAssessmentDraft {
    sessionId: string;
    projectKey: string;
    environment: string;
    requiredTestsPassed: boolean;
    changeSummary: string;
}

interface ReleaseDeployDraft {
    assessmentId: string;
    projectKey: string;
    environment: string;
    targetType: 'repo' | 'project';
    repoId: string;
    branch: string;
    comment: string;
}

type CommandArgumentDraftValue = string | boolean;

interface CommandArgumentDraftContext {
    projectKey: string;
    sessionId: string;
    assessmentId: string;
    targetUrl: string;
}

const STATUS_BADGE: Record<string, string> = {
    created: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200',
    running: 'bg-blue-100 text-blue-700 dark:bg-blue-500/10 dark:text-blue-200',
    approval_pending: 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200',
    approved_pending_execution: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-200',
    succeeded: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200',
    failed: 'bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-200',
    rejected: 'bg-rose-100 text-rose-700 dark:bg-rose-500/10 dark:text-rose-200',
};

const RISK_BADGE: Record<string, string> = {
    low: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200',
    medium: 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200',
    high: 'bg-orange-100 text-orange-700 dark:bg-orange-500/10 dark:text-orange-200',
    critical: 'bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-200',
};

function formatDateTime(value?: string): string {
    if (!value) return '-';
    return value.replace('T', ' ');
}

function toneClass(
    value: string,
    map: Record<string, string>,
    fallback = 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200',
) {
    return map[value] || fallback;
}

function getReviewSummary(assessment?: ReleaseRiskAssessment | null): ReleaseRiskReviewSummary | null {
    const summary = assessment?.evidence?.review_summary;
    if (!summary || typeof summary !== 'object') return null;
    const payload = summary as Partial<ReleaseRiskReviewSummary>;
    return {
        pending: Number(payload.pending || 0),
        confirmed: Number(payload.confirmed || 0),
        dismissed: Number(payload.dismissed || 0),
        active: Number(payload.active || 0),
        effective: Number(payload.effective || 0),
    };
}

function getReviewImpact(assessment?: ReleaseRiskAssessment | null): 'pending' | 'confirmed' | '' {
    const blockers = assessment?.blockers || [];
    if (blockers.some((item) => item.type === 'human_review_pending')) {
        return 'pending';
    }
    if (blockers.some((item) => item.type === 'confirmed_issue_requires_manual_release')) {
        return 'confirmed';
    }
    return '';
}

function formatBlockerLabel(blocker: ReleaseRiskBlocker): string {
    switch (blocker.type) {
    case 'human_review_pending':
        return '待人工复核，禁止自动发布';
    case 'confirmed_issue_requires_manual_release':
        return '已确认问题，需人工放行';
    case 'human_review_required':
        return '命中历史人工复核阻断，需人工判断';
    case 'required_tests_failed':
        return '所需测试尚未全部通过，禁止自动发布';
    case 'production_requires_manual_approval':
        return '生产环境发布必须保留人工批准';
    default:
        return String(blocker.message || blocker.title || blocker.type || '未知阻断项');
    }
}

function formatAutoReleaseLabel(assessment?: ReleaseRiskAssessment | null): string {
    if (assessment?.auto_release_eligible) {
        return '复核通过，可自动发布';
    }
    const impact = getReviewImpact(assessment);
    if (impact === 'pending') {
        return '待复核，禁止自动发布';
    }
    if (impact === 'confirmed') {
        return '已确认问题，需人工放行';
    }
    return '需人工批准';
}

function isProductionEnvironment(environment?: string): boolean {
    return ['prod', 'production', 'online'].includes(String(environment || '').trim().toLowerCase());
}

function formatDeployActionHint(assessment?: ReleaseRiskAssessment | null): string {
    if (!assessment) return '请先选择一条发布风险评估。';
    if (isProductionEnvironment(assessment.environment || assessment.input?.environment)) {
        return '仅允许创建待审批发布申请';
    }
    if (getReviewImpact(assessment)) {
        return '当前仅允许人工审批发布';
    }
    if (assessment.auto_release_eligible) {
        return '允许自动发布';
    }
    return '当前会创建待审批发布申请';
}

function formatReleaseDecisionLabel(decision?: string): string {
    if (decision === 'auto_executed') {
        return '已自动创建并执行受控发布';
    }
    if (decision === 'approval_created') {
        return '已创建待审批发布申请';
    }
    return '受控发布已提交';
}

function extractNestedEntityId(resultPayload: unknown, nestedKey: string, idKey: string): string {
    if (!resultPayload || typeof resultPayload !== 'object') return '';
    const result = resultPayload as Record<string, unknown>;
    const nestedEntity = result[nestedKey];
    if (nestedEntity && typeof nestedEntity === 'object' && idKey in nestedEntity) {
        return String((nestedEntity as Record<string, unknown>)[idKey] || '');
    }
    return String(result[idKey] || '');
}

function extractSessionIdFromRun(run: CommandRun | null): string {
    return extractNestedEntityId(run?.result, 'session', 'session_id');
}

function extractAssessmentIdFromRun(run: CommandRun | null): string {
    return extractNestedEntityId(run?.result, 'assessment', 'assessment_id');
}

function extractReleaseDeployResult(resultPayload: unknown): ReleaseDeployResult | null {
    if (!resultPayload || typeof resultPayload !== 'object') return null;
    const payload = resultPayload as Record<string, unknown>;
    if (!('release_decision' in payload) || !('deploy_target' in payload)) {
        return null;
    }
    return payload as unknown as ReleaseDeployResult;
}

function buildCommandArgumentDrafts(
    definition: CommandDefinition | null,
    context: CommandArgumentDraftContext,
): Record<string, CommandArgumentDraftValue> {
    if (!definition) return {};
    return definition.arguments.reduce<Record<string, CommandArgumentDraftValue>>((acc, item) => {
        const contextualDrafts: Record<string, CommandArgumentDraftValue> = {
            project_key: context.projectKey,
            session_id: context.sessionId,
            assessment_id: context.assessmentId,
            target_url: context.targetUrl,
            exploration_session_ids: context.sessionId,
        };

        if (contextualDrafts[item.name]) {
            acc[item.name] = contextualDrafts[item.name];
            return acc;
        }

        if (item.type === 'boolean') {
            acc[item.name] = Boolean(item.default);
        } else if (Array.isArray(item.default)) {
            acc[item.name] = item.default.join(', ');
        } else if (item.default !== undefined && item.default !== null) {
            acc[item.name] = String(item.default);
        } else {
            acc[item.name] = '';
        }
        return acc;
    }, {});
}

function normalizeCommandArguments(
    definition: CommandDefinition | null,
    drafts: Record<string, CommandArgumentDraftValue>,
): Record<string, unknown> {
    if (!definition) return {};
    return definition.arguments.reduce<Record<string, unknown>>((acc, item) => {
        const raw = drafts[item.name];
        if (item.type === 'boolean') {
            acc[item.name] = Boolean(raw);
            return acc;
        }

        const text = String(raw ?? '').trim();
        if (!text) {
            if (item.required) {
                acc[item.name] = item.type === 'integer' ? 0 : item.type === 'csv' ? [] : '';
            }
            return acc;
        }

        if (item.type === 'integer') {
            acc[item.name] = Number.parseInt(text, 10) || 0;
            return acc;
        }
        if (item.type === 'csv') {
            acc[item.name] = text
                .split(/[\n,]/)
                .map((entry) => entry.trim())
                .filter(Boolean);
            return acc;
        }
        acc[item.name] = text;
        return acc;
    }, {});
}

function SummaryCard({
    label,
    value,
    hint,
    icon,
}: {
    label: string;
    value: string;
    hint: string;
    icon: React.ReactNode;
}) {
    return (
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center justify-between">
                <div>
                    <div className="text-xs uppercase tracking-[0.18em] text-slate-400">{label}</div>
                    <div className="mt-2 text-2xl font-semibold text-slate-900 dark:text-white">{value}</div>
                </div>
                <div className="rounded-xl bg-slate-100 p-3 text-slate-600 dark:bg-slate-800 dark:text-slate-200">
                    {icon}
                </div>
            </div>
            <div className="mt-3 text-sm text-slate-500 dark:text-slate-400">{hint}</div>
        </div>
    );
}

export default function LegionControlCenter({
    profile,
    selectedRunId,
    selectedSessionId,
    selectedAssessmentId,
    selectedFindingId,
    onSelectRun,
    onSelectSession,
    onSelectAssessment,
    onUpdateSelection,
}: LegionControlCenterProps) {
    const { commandRunFilters, setCommandRunFilters, markRefreshed } = useLegionControlStore();
    const [commands, setCommands] = useState<CommandDefinition[]>([]);
    const [runs, setRuns] = useState<CommandRun[]>([]);
    const [assessments, setAssessments] = useState<ReleaseRiskAssessment[]>([]);
    const [sessions, setSessions] = useState<ExplorationSession[]>([]);
    const [binding, setBinding] = useState<NotificationPlatformBinding | null>(null);
    const [pendingBindingCode, setPendingBindingCode] = useState<NotificationPlatformBindingCode | null>(null);
    const [runDetail, setRunDetail] = useState<CommandRun | null>(null);
    const [assessmentDetail, setAssessmentDetail] = useState<ReleaseRiskAssessment | null>(null);
    const [linkedRunFindings, setLinkedRunFindings] = useState<ExperienceFinding[]>([]);
    const [linkedRunAssessment, setLinkedRunAssessment] = useState<ReleaseRiskAssessment | null>(null);
    const [loading, setLoading] = useState(true);
    const [detailLoading, setDetailLoading] = useState(false);
    const [linkedEvidenceLoading, setLinkedEvidenceLoading] = useState(false);
    const [bindingLoading, setBindingLoading] = useState(false);
    const [bindingMutating, setBindingMutating] = useState<'issue' | 'revoke' | ''>('');
    const [error, setError] = useState('');
    const [reviewComment, setReviewComment] = useState('');
    const [reviewing, setReviewing] = useState<'approve' | 'reject' | ''>('');
    const [commandOpen, setCommandOpen] = useState(false);
    const [selectedCommandIdForLaunch, setSelectedCommandIdForLaunch] = useState('');
    const [commandArgumentDrafts, setCommandArgumentDrafts] = useState<Record<string, CommandArgumentDraftValue>>({});
    const [commandConfirm, setCommandConfirm] = useState(false);
    const [submittingCommand, setSubmittingCommand] = useState(false);
    const [assessmentOpen, setAssessmentOpen] = useState(false);
    const [assessmentDraft, setAssessmentDraft] = useState<ReleaseAssessmentDraft>({
        sessionId: selectedSessionId || '',
        projectKey: '',
        environment: 'staging',
        requiredTestsPassed: true,
        changeSummary: '',
    });
    const [submittingAssessment, setSubmittingAssessment] = useState(false);
    const [releaseDeployOpen, setReleaseDeployOpen] = useState(false);
    const [releaseDeployDraft, setReleaseDeployDraft] = useState<ReleaseDeployDraft>({
        assessmentId: '',
        projectKey: '',
        environment: 'staging',
        targetType: 'repo',
        repoId: '',
        branch: '',
        comment: '',
    });
    const [submittingReleaseDeploy, setSubmittingReleaseDeploy] = useState(false);

    const commandMap = useMemo(
        () => commands.reduce<Record<string, CommandDefinition>>((acc, item) => {
            acc[item.command_id] = item;
            return acc;
        }, {}),
        [commands],
    );
    const allowedCommands = useMemo(
        () => commands.filter((item) => item.allowed),
        [commands],
    );
    const selectedLaunchCommand = useMemo(
        () => allowedCommands.find((item) => item.command_id === selectedCommandIdForLaunch) || allowedCommands[0] || null,
        [allowedCommands, selectedCommandIdForLaunch],
    );
    const selectedContextSession = useMemo(
        () => sessions.find((item) => item.session_id === selectedSessionId) || null,
        [selectedSessionId, sessions],
    );
    const launcherDraftContext = useMemo<CommandArgumentDraftContext>(() => ({
        projectKey: selectedContextSession?.project_key || commandRunFilters.projectKey || runDetail?.project_key || profile.project_ids[0] || '',
        sessionId: selectedContextSession?.session_id || selectedSessionId || '',
        assessmentId: selectedAssessmentId || '',
        targetUrl: selectedContextSession?.target_url || '',
    }), [
        commandRunFilters.projectKey,
        profile.project_ids,
        runDetail?.project_key,
        selectedAssessmentId,
        selectedContextSession?.project_key,
        selectedContextSession?.session_id,
        selectedContextSession?.target_url,
        selectedSessionId,
    ]);

    const refresh = async () => {
        setLoading(true);
        setError('');
        try {
            const [commandDefs, runPayload, assessmentPayload, sessionPayload, bindingPayload] = await Promise.all([
                listCommands(),
                listCommandRuns({
                    status: commandRunFilters.status,
                    approval_status: commandRunFilters.approvalStatus,
                    command_id: commandRunFilters.commandId,
                    project_key: commandRunFilters.projectKey,
                    source: commandRunFilters.source,
                    limit: 30,
                }),
                listReleaseRiskAssessments({
                    project_key: commandRunFilters.projectKey,
                    limit: 20,
                }),
                listExplorationSessions({
                    project_key: commandRunFilters.projectKey,
                    limit: 50,
                }),
                getNotificationPlatformBindingMe(),
            ]);
            setCommands(commandDefs);
            setRuns(runPayload.runs);
            setAssessments(assessmentPayload.assessments);
            setSessions(sessionPayload.sessions);
            setBinding(bindingPayload.binding);
            setPendingBindingCode(bindingPayload.pending_code);
            markRefreshed();
        } catch (err) {
            setError(err instanceof Error ? err.message : '控制中心加载失败');
        } finally {
            setLoading(false);
        }
    };

    const refreshBinding = async () => {
        setBindingLoading(true);
        try {
            const payload = await getNotificationPlatformBindingMe();
            setBinding(payload.binding);
            setPendingBindingCode(payload.pending_code);
        } catch (err) {
            setError(err instanceof Error ? err.message : '通知平台绑定信息加载失败');
        } finally {
            setBindingLoading(false);
        }
    };

    useEffect(() => {
        void refresh();
    }, [
        commandRunFilters.approvalStatus,
        commandRunFilters.commandId,
        commandRunFilters.projectKey,
        commandRunFilters.source,
        commandRunFilters.status,
    ]);

    useEffect(() => {
        if (!selectedRunId) {
            setRunDetail(null);
            return;
        }
        setDetailLoading(true);
        getCommandRun(selectedRunId)
            .then((payload) => {
                setRunDetail(payload);
            })
            .catch((err) => {
                setError(err instanceof Error ? err.message : '命令详情加载失败');
            })
            .finally(() => setDetailLoading(false));
    }, [selectedRunId]);

    useEffect(() => {
        if (!selectedAssessmentId) {
            setAssessmentDetail(null);
            return;
        }
        getReleaseRiskAssessment(selectedAssessmentId)
            .then((payload) => setAssessmentDetail(payload))
            .catch((err) => setError(err instanceof Error ? err.message : '风险评估详情加载失败'));
    }, [selectedAssessmentId]);

    useEffect(() => {
        const linkedSessionId = extractSessionIdFromRun(runDetail);
        const linkedAssessmentId = extractAssessmentIdFromRun(runDetail);
        if (!runDetail || (!linkedSessionId && !linkedAssessmentId)) {
            setLinkedRunFindings([]);
            setLinkedRunAssessment(null);
            setLinkedEvidenceLoading(false);
            return;
        }

        let cancelled = false;
        setLinkedEvidenceLoading(true);
        Promise.all([
            linkedSessionId
                ? listExplorationFindings(linkedSessionId, {})
                : Promise.resolve({ session_id: '', findings: [], count: 0 }),
            linkedAssessmentId
                ? getReleaseRiskAssessment(linkedAssessmentId)
                : Promise.resolve(null),
        ])
            .then(([findingsPayload, assessmentPayload]) => {
                if (cancelled) return;
                setLinkedRunFindings(findingsPayload.findings || []);
                setLinkedRunAssessment(assessmentPayload);
            })
            .catch((err) => {
                if (cancelled) return;
                setError(err instanceof Error ? err.message : '关联证据加载失败');
                setLinkedRunFindings([]);
                setLinkedRunAssessment(null);
            })
            .finally(() => {
                if (!cancelled) {
                    setLinkedEvidenceLoading(false);
                }
            });

        return () => {
            cancelled = true;
        };
    }, [runDetail]);

    useEffect(() => {
        const matched = sessions.find((item) => item.session_id === (selectedSessionId || assessmentDraft.sessionId));
        if (!matched) return;
        setAssessmentDraft((prev) => ({
            ...prev,
            sessionId: matched.session_id,
            projectKey: prev.projectKey || matched.project_key,
        }));
    }, [assessmentDraft.sessionId, selectedSessionId, sessions]);

    useEffect(() => {
        if (!commandOpen) return;
        if (!selectedLaunchCommand) {
            setSelectedCommandIdForLaunch('');
            setCommandArgumentDrafts({});
            setCommandConfirm(false);
            return;
        }
        setSelectedCommandIdForLaunch(selectedLaunchCommand.command_id);
        setCommandArgumentDrafts(buildCommandArgumentDrafts(selectedLaunchCommand, launcherDraftContext));
        setCommandConfirm(false);
    }, [commandOpen, launcherDraftContext, selectedLaunchCommand?.command_id]);

    const summary = useMemo(() => ({
        pending: runs.filter((item) => item.approval_status === 'pending').length,
        running: runs.filter((item) => item.status === 'running').length,
        failed: runs.filter((item) => item.status === 'failed').length,
        assessments: assessments.length,
        autoRelease: assessments.filter((item) => item.auto_release_eligible).length,
        notification_platformRuns: runs.filter((item) => item.source === 'notification_platform').length,
    }), [assessments, runs]);
    const primaryLinkedFinding = useMemo(
        () => linkedRunFindings.find((item) => item.requires_human_review && item.review_status === 'pending')
            || linkedRunFindings.find((item) => item.requires_human_review && item.review_status === 'confirmed')
            || linkedRunFindings.find((item) => item.review_status !== 'dismissed')
            || linkedRunFindings[0]
            || null,
        [linkedRunFindings],
    );
    const linkedAssessmentReviewImpact = useMemo(
        () => getReviewImpact(linkedRunAssessment),
        [linkedRunAssessment],
    );
    const linkedAssessmentReviewSummary = useMemo(
        () => getReviewSummary(linkedRunAssessment),
        [linkedRunAssessment],
    );
    const assessmentDetailReviewSummary = useMemo(
        () => getReviewSummary(assessmentDetail),
        [assessmentDetail],
    );
    const linkedReleaseDeployResult = useMemo(
        () => extractReleaseDeployResult(runDetail?.result),
        [runDetail?.result],
    );
    const releaseDeployAssessment = useMemo(() => {
        if (!releaseDeployDraft.assessmentId) return null;
        if (assessmentDetail?.assessment_id === releaseDeployDraft.assessmentId) {
            return assessmentDetail;
        }
        if (linkedRunAssessment?.assessment_id === releaseDeployDraft.assessmentId) {
            return linkedRunAssessment;
        }
        return assessments.find((item) => item.assessment_id === releaseDeployDraft.assessmentId) || null;
    }, [
        assessmentDetail,
        assessments,
        linkedRunAssessment,
        releaseDeployDraft.assessmentId,
    ]);

    const applySelectionPatch = (patch: {
        tab?: LegionTabId;
        runId?: string | null;
        sessionId?: string | null;
        assessmentId?: string | null;
        findingId?: string | null;
    }) => {
        if (onUpdateSelection) {
            onUpdateSelection(patch);
            return;
        }
        if ('runId' in patch) onSelectRun(patch.runId ?? null);
        if ('sessionId' in patch) onSelectSession(patch.sessionId ?? null);
        if ('assessmentId' in patch) onSelectAssessment(patch.assessmentId ?? null);
    };

    const handleIssueBindingCode = async () => {
        setBindingMutating('issue');
        setError('');
        try {
            const payload = await issueNotificationPlatformBindingCode();
            setBinding(payload.binding);
            setPendingBindingCode(payload.pending_code);
        } catch (err) {
            setError(err instanceof Error ? err.message : '生成绑定码失败');
        } finally {
            setBindingMutating('');
        }
    };

    const openReleaseDeployDialog = (assessment?: ReleaseRiskAssessment | null) => {
        if (!assessment) {
            setError('请先选择一条发布风险评估。');
            return;
        }
        setReleaseDeployDraft({
            assessmentId: assessment.assessment_id,
            projectKey: assessment.project_key || assessment.input?.project_key || '',
            environment: assessment.environment || assessment.input?.environment || 'staging',
            targetType: 'repo',
            repoId: '',
            branch: '',
            comment: '',
        });
        setReleaseDeployOpen(true);
    };

    const handleRevokeBinding = async () => {
        setBindingMutating('revoke');
        setError('');
        try {
            const payload = await revokeNotificationPlatformBinding();
            setBinding(null);
            setPendingBindingCode(payload.pending_code);
        } catch (err) {
            setError(err instanceof Error ? err.message : '撤销通知平台绑定失败');
        } finally {
            setBindingMutating('');
        }
    };

    const runColumns: DataTableColumn<CommandRun>[] = [
        {
            key: 'command_id',
            title: '命令',
            render: (_, record) => (
                <div>
                    <div className="font-medium text-slate-900 dark:text-white">{record.command_id}</div>
                    <div className="text-xs text-slate-400">{commandMap[record.command_id]?.summary || record.command_summary}</div>
                </div>
            ),
        },
        {
            key: 'project_key',
            title: '项目',
            render: (value) => <span>{String(value || '平台级')}</span>,
        },
        {
            key: 'source',
            title: '来源',
            render: (value) => (
                <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                    {String(value || '-')}
                </span>
            ),
        },
        {
            key: 'status',
            title: '运行状态',
            render: (value) => (
                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${toneClass(String(value || ''), STATUS_BADGE)}`}>
                    {String(value || '-')}
                </span>
            ),
        },
        {
            key: 'approval_status',
            title: '审批',
            render: (value) => (
                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${toneClass(String(value || ''), STATUS_BADGE)}`}>
                    {String(value || '-')}
                </span>
            ),
        },
        {
            key: 'risk_level',
            title: '风险',
            render: (value) => (
                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${toneClass(String(value || ''), RISK_BADGE)}`}>
                    {String(value || '-')}
                </span>
            ),
        },
        {
            key: 'created_at',
            title: '创建时间',
            render: (value) => formatDateTime(String(value || '')),
        },
    ];

    const assessmentColumns: DataTableColumn<ReleaseRiskAssessment>[] = [
        { key: 'project_key', title: '项目' },
        { key: 'environment', title: '环境' },
        {
            key: 'release_risk',
            title: '发布风险',
            render: (value) => (
                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${toneClass(String(value || ''), RISK_BADGE)}`}>
                    {String(value || '-')}
                </span>
            ),
        },
        {
            key: 'auto_release_eligible',
            title: '自动发布资格',
            render: (value) => Boolean(value)
                ? <span className="inline-flex rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200">可自动发布</span>
                : <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-200">需人工放行</span>,
        },
        {
            key: 'review_summary',
            title: '复核摘要',
            render: (_, record) => {
                const summary = getReviewSummary(record);
                if (!summary) {
                    return <span className="text-xs text-slate-400">历史记录</span>;
                }
                return (
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                        待 {summary.pending} / 确 {summary.confirmed} / 驳 {summary.dismissed}
                    </span>
                );
            },
        },
        {
            key: 'created_at',
            title: '评估时间',
            render: (value) => formatDateTime(String(value || '')),
        },
    ];

    const handleReview = async (decision: 'approve' | 'reject') => {
        if (!runDetail?.run_id) return;
        setReviewing(decision);
        setError('');
        try {
            if (decision === 'approve') {
                const payload = await approveRun(runDetail.run_id, reviewComment || '批准执行', true);
                setRunDetail(payload.run);
                onSelectRun(payload.run.run_id);
            } else {
                const payload = await rejectRun(runDetail.run_id, reviewComment || '人工驳回');
                setRunDetail(payload.run);
                onSelectRun(payload.run.run_id);
            }
            setReviewComment('');
            await refresh();
        } catch (err) {
            setError(err instanceof Error ? err.message : '审批操作失败');
        } finally {
            setReviewing('');
        }
    };

    const handleCreateAssessment = async () => {
        if (!assessmentDraft.sessionId) {
            setError('请先选择一个探索会话，再生成发布风险评估。');
            return;
        }
        if (!assessmentDraft.projectKey.trim()) {
            setError('请先补充项目标识。');
            return;
        }
        setSubmittingAssessment(true);
        setError('');
        try {
            const payload = await executeCommand(
                'release.risk.assess',
                {
                    project_key: assessmentDraft.projectKey.trim(),
                    environment: assessmentDraft.environment,
                    exploration_session_ids: [assessmentDraft.sessionId],
                    required_tests_passed: assessmentDraft.requiredTestsPassed,
                    change_summary: assessmentDraft.changeSummary,
                },
            );
            const result = payload.result as { assessment?: ReleaseRiskAssessment } | null;
            applySelectionPatch({
                runId: payload.run.run_id,
                assessmentId: result?.assessment?.assessment_id || null,
            });
            setAssessmentOpen(false);
            await refresh();
        } catch (err) {
            setError(err instanceof Error ? err.message : '生成风险评估失败');
        } finally {
            setSubmittingAssessment(false);
        }
    };

    const handleCreateReleaseDeploy = async () => {
        if (!releaseDeployDraft.assessmentId) {
            setError('请先选择一条发布风险评估。');
            return;
        }
        if (!releaseDeployDraft.projectKey.trim()) {
            setError('当前评估缺少项目标识，无法发起发布。');
            return;
        }
        if (releaseDeployDraft.targetType === 'repo' && !releaseDeployDraft.repoId.trim()) {
            setError('仓库发布需要填写 repo_id。');
            return;
        }

        setSubmittingReleaseDeploy(true);
        setError('');
        try {
            const payload = await executeCommand(
                'release.deploy.request',
                {
                    assessment_id: releaseDeployDraft.assessmentId,
                    target_type: releaseDeployDraft.targetType,
                    repo_id: releaseDeployDraft.targetType === 'repo' ? releaseDeployDraft.repoId.trim() : '',
                    branch: releaseDeployDraft.targetType === 'repo' ? releaseDeployDraft.branch.trim() : '',
                    comment: releaseDeployDraft.comment.trim(),
                },
                true,
            );
            const result = extractReleaseDeployResult(payload.result);
            applySelectionPatch({
                runId: payload.run.run_id,
                assessmentId: result?.assessment_id || releaseDeployDraft.assessmentId,
            });
            setReleaseDeployOpen(false);
            await refresh();
        } catch (err) {
            setError(err instanceof Error ? err.message : '发起受控发布失败');
        } finally {
            setSubmittingReleaseDeploy(false);
        }
    };

    const handleExecuteControlledCommand = async () => {
        if (!selectedLaunchCommand) {
            setError('当前没有可执行的受控命令。');
            return;
        }
        if (selectedLaunchCommand.requires_confirmation && !commandConfirm) {
            setError(`命令 ${selectedLaunchCommand.command_id} 为高风险动作，请先勾选显式确认。`);
            return;
        }

        setSubmittingCommand(true);
        setError('');
        try {
            const payload = await executeCommand(
                selectedLaunchCommand.command_id,
                normalizeCommandArguments(selectedLaunchCommand, commandArgumentDrafts),
                commandConfirm,
            );
            const nextSessionId = extractSessionIdFromRun(payload.run) || extractNestedEntityId(payload.result, 'session', 'session_id');
            const nextAssessmentId = extractAssessmentIdFromRun(payload.run) || extractNestedEntityId(payload.result, 'assessment', 'assessment_id');
            applySelectionPatch({
                runId: payload.run.run_id,
                sessionId: nextSessionId || undefined,
                assessmentId: nextAssessmentId || undefined,
            });

            setCommandOpen(false);
            await refresh();
        } catch (err) {
            setError(err instanceof Error ? err.message : '发起受控命令失败');
        } finally {
            setSubmittingCommand(false);
        }
    };

    return (
        <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
                <SummaryCard label="待审批命令" value={String(summary.pending)} hint="需要人工批准后才能继续执行的写动作" icon={<Clock className="h-5 w-5" />} />
                <SummaryCard label="运行中命令" value={String(summary.running)} hint="正在执行中的受控命令运行" icon={<Loader2 className="h-5 w-5" />} />
                <SummaryCard label="失败命令" value={String(summary.failed)} hint="需要排查或重新决策的运行记录" icon={<XCircle className="h-5 w-5" />} />
                <SummaryCard label="最近评估" value={String(summary.assessments)} hint="最近生成的发布风险评估数量" icon={<Shield className="h-5 w-5" />} />
                <SummaryCard label="可自动发布" value={String(summary.autoRelease)} hint="满足低风险非生产自动发布条件的评估" icon={<Sparkles className="h-5 w-5" />} />
                <SummaryCard label="通知平台命令" value={String(summary.notification_platformRuns)} hint="当前列表里由通知平台入口触发的命令运行数量" icon={<CheckCircle2 className="h-5 w-5" />} />
            </div>

            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <div className="text-lg font-semibold text-slate-900 dark:text-white">我的通知平台绑定</div>
                        <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">在 Legion 里生成一次性绑定码，再去通知平台发送“绑定 &lt;code&gt;”，后续通知平台命令就会归因到当前平台账号。</div>
                    </div>
                    <button
                        type="button"
                        onClick={() => void refreshBinding()}
                        className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                    >
                        <Loader2 className={`h-4 w-4 ${bindingLoading ? 'animate-spin' : ''}`} />
                        刷新绑定状态
                    </button>
                </div>

                <div className="mt-4 grid gap-4 xl:grid-cols-[1.2fr_1fr]">
                    <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4 dark:border-slate-700 dark:bg-slate-950/50">
                        <div className="flex flex-wrap items-center gap-2">
                            <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${binding ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200' : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200'}`}>
                                {binding ? '已绑定' : '未绑定'}
                            </span>
                            <span className="text-sm text-slate-500 dark:text-slate-400">
                                {binding ? `通知平台身份 ${binding.notification_platform_open_id}` : '当前通知平台身份尚未绑定到平台账号'}
                            </span>
                        </div>
                        <div className="mt-4 space-y-2 text-sm text-slate-600 dark:text-slate-300">
                            <div>平台账号：{binding?.username || profile.username}</div>
                            <div>当前聊天：{binding?.chat_id || '尚未记录'}</div>
                            <div>最近触达：{formatDateTime(binding?.last_seen_at || '')}</div>
                            <div>绑定时间：{formatDateTime(binding?.bound_at || '')}</div>
                        </div>
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4 dark:border-slate-700 dark:bg-slate-950/50">
                        <div className="text-sm font-medium text-slate-900 dark:text-white">一次性绑定码</div>
                        {!pendingBindingCode ? (
                            <div className="mt-3 text-sm text-slate-500 dark:text-slate-400">当前没有待使用绑定码，可直接生成新的 10 分钟有效绑定码。</div>
                        ) : (
                            <div className="mt-3 space-y-2 text-sm text-slate-600 dark:text-slate-300">
                                <div className="rounded-xl bg-slate-900 px-3 py-2 font-mono text-slate-100">{pendingBindingCode.code}</div>
                                <div>状态：{pendingBindingCode.status}</div>
                                <div>有效期至：{formatDateTime(pendingBindingCode.expires_at)}</div>
                            </div>
                        )}
                        <div className="mt-4 flex flex-wrap gap-2">
                            <button
                                type="button"
                                onClick={() => void handleIssueBindingCode()}
                                disabled={bindingMutating !== ''}
                                className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                            >
                                {bindingMutating === 'issue' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Shield className="h-4 w-4" />}
                                生成绑定码
                            </button>
                            <button
                                type="button"
                                onClick={() => void handleRevokeBinding()}
                                disabled={bindingMutating !== '' || (!binding && !pendingBindingCode)}
                                className="inline-flex items-center gap-2 rounded-xl border border-rose-200 px-3 py-2 text-sm text-rose-700 transition hover:bg-rose-50 disabled:opacity-50 dark:border-rose-900/40 dark:text-rose-200 dark:hover:bg-rose-950/20"
                            >
                                {bindingMutating === 'revoke' ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
                                撤销绑定
                            </button>
                        </div>
                    </div>
                </div>
            </section>

            {error && (
                <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-200">
                    {error}
                </div>
            )}

            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <div className="text-lg font-semibold text-slate-900 dark:text-white">命令运行与审批</div>
                        <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">所有 Web 写动作都统一落到命令运行记录，再由审批与审计驱动后续执行。</div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <button
                            type="button"
                            onClick={() => setCommandOpen(true)}
                            className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                        >
                            <PlayCircle className="h-4 w-4" />
                            发起受控命令
                        </button>
                        <button
                            type="button"
                            onClick={() => void refresh()}
                            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                        >
                            <Loader2 className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                            刷新控制中心
                        </button>
                    </div>
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-5">
                    <label className="text-sm text-slate-600 dark:text-slate-300">
                        命令筛选
                        <select
                            value={commandRunFilters.commandId}
                            onChange={(event) => setCommandRunFilters({ commandId: event.target.value })}
                            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                        >
                            <option value="">全部命令</option>
                            {commands.map((item) => (
                                <option key={item.command_id} value={item.command_id}>{item.command_id}</option>
                            ))}
                        </select>
                    </label>
                    <label className="text-sm text-slate-600 dark:text-slate-300">
                        项目筛选
                        <input
                            value={commandRunFilters.projectKey}
                            onChange={(event) => setCommandRunFilters({ projectKey: event.target.value })}
                            placeholder="demo"
                            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                        />
                    </label>
                    <label className="text-sm text-slate-600 dark:text-slate-300">
                        运行状态
                        <select
                            value={commandRunFilters.status}
                            onChange={(event) => setCommandRunFilters({ status: event.target.value })}
                            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                        >
                            <option value="">全部状态</option>
                            {['created', 'running', 'approval_pending', 'approved_pending_execution', 'succeeded', 'failed', 'rejected'].map((status) => (
                                <option key={status} value={status}>{status}</option>
                            ))}
                        </select>
                    </label>
                    <label className="text-sm text-slate-600 dark:text-slate-300">
                        审批状态
                        <select
                            value={commandRunFilters.approvalStatus}
                            onChange={(event) => setCommandRunFilters({ approvalStatus: event.target.value })}
                            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                        >
                            <option value="">全部审批</option>
                            {['not_required', 'pending', 'approved', 'rejected'].map((status) => (
                                <option key={status} value={status}>{status}</option>
                            ))}
                        </select>
                    </label>
                    <label className="text-sm text-slate-600 dark:text-slate-300">
                        来源筛选
                        <select
                            value={commandRunFilters.source}
                            onChange={(event) => setCommandRunFilters({ source: event.target.value })}
                            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                        >
                            <option value="">全部来源</option>
                            {['web', 'notification_platform', 'simulation'].map((source) => (
                                <option key={source} value={source}>{source}</option>
                            ))}
                        </select>
                    </label>
                </div>

                <div className="mt-5 grid gap-5 xl:grid-cols-[1.45fr_1fr]">
                    <DataTable
                        columns={runColumns}
                        data={runs}
                        rowKey="run_id"
                        loading={loading}
                        emptyText="暂无命令运行记录"
                        activeRowKey={selectedRunId}
                        onRowClick={(record) => onSelectRun(record.run_id)}
                    />

                    <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4 dark:border-slate-700 dark:bg-slate-950/50">
                        <div className="flex items-center justify-between">
                            <div className="text-base font-semibold text-slate-900 dark:text-white">命令详情</div>
                            {detailLoading && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
                        </div>
                        {!runDetail ? (
                            <div className="mt-4 text-sm text-slate-500 dark:text-slate-400">选择一条命令运行后，这里会展示参数、审批状态、结果与错误详情。</div>
                        ) : (
                            <div className="mt-4 space-y-4">
                                <div className="space-y-2 text-sm text-slate-600 dark:text-slate-300">
                                    <div className="font-medium text-slate-900 dark:text-white">{runDetail.command_id}</div>
                                    <div>项目：{runDetail.project_key || '平台级'}</div>
                                    <div>请求人：{runDetail.requester_id || '-'}</div>
                                    <div>发起渠道：{runDetail.source || '-'}</div>
                                    <div>创建时间：{formatDateTime(runDetail.created_at)}</div>
                                    <div>风险：<span className={`rounded-full px-2 py-0.5 text-xs font-medium ${toneClass(runDetail.risk_level, RISK_BADGE)}`}>{runDetail.risk_level}</span></div>
                                    <div>审批：<span className={`rounded-full px-2 py-0.5 text-xs font-medium ${toneClass(runDetail.approval_status, STATUS_BADGE)}`}>{runDetail.approval_status}</span></div>
                                </div>

                                {runDetail.source_context && Object.keys(runDetail.source_context).length > 0 && (
                                    <div>
                                        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">来源上下文</div>
                                        <div className="mt-2 grid gap-3 md:grid-cols-2">
                                            <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-950">
                                                <div>渠道：{String(runDetail.source_context.channel || runDetail.source || '-')}</div>
                                                <div>通知平台用户：{String(runDetail.source_context.from_user || '-')}</div>
                                                <div>chat_id：{String(runDetail.source_context.chat_id || '-')}</div>
                                                <div>绑定状态：{String(runDetail.source_context.binding_status || '-')}</div>
                                            </div>
                                            <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-950">
                                                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">原始消息摘要</div>
                                                <div className="mt-2 whitespace-pre-wrap break-all text-slate-700 dark:text-slate-200">
                                                    {String(runDetail.source_context.raw_message || '-')}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                <div>
                                    <div className="text-xs uppercase tracking-[0.18em] text-slate-400">参数</div>
                                    <pre className="mt-2 overflow-auto rounded-xl bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(runDetail.arguments, null, 2)}</pre>
                                </div>

                                {Boolean(runDetail.result) && (
                                    <div>
                                        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">结果</div>
                                        <pre className="mt-2 overflow-auto rounded-xl bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(runDetail.result, null, 2)}</pre>
                                    </div>
                                )}
                                {Boolean(runDetail.error) && (
                                    <div>
                                        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">错误</div>
                                        <pre className="mt-2 overflow-auto rounded-xl bg-slate-900 p-3 text-xs text-red-200">{JSON.stringify(runDetail.error, null, 2)}</pre>
                                    </div>
                                )}

                                {(linkedEvidenceLoading || linkedRunFindings.length > 0 || linkedRunAssessment) && (
                                    <div>
                                        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">关联证据摘要</div>
                                        {linkedEvidenceLoading ? (
                                            <div className="mt-2 inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400">
                                                <Loader2 className="h-4 w-4 animate-spin" />
                                                正在加载关联探索发现与风险结论...
                                            </div>
                                        ) : (
                                            <div className="mt-2 space-y-3">
                                                {linkedRunFindings.length > 0 && (
                                                    <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950">
                                                        <div className="flex flex-wrap items-center justify-between gap-2">
                                                            <div>
                                                                <div className="text-sm font-medium text-slate-900 dark:text-white">探索发现</div>
                                                                <div className="mt-1 text-xs text-slate-400">共 {linkedRunFindings.length} 条关联发现，优先展示最需要人工关注的证据。</div>
                                                            </div>
                                                            <div className="flex flex-wrap items-center gap-2">
                                                                {extractSessionIdFromRun(runDetail) && (
                                                                    <button
                                                                        type="button"
                                                                        onClick={() => applySelectionPatch({
                                                                            sessionId: extractSessionIdFromRun(runDetail),
                                                                            ...(selectedFindingId ? { findingId: selectedFindingId } : {}),
                                                                        })}
                                                                        className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                                                                    >
                                                                        <PlayCircle className="h-4 w-4" />
                                                                        查看探索发现
                                                                    </button>
                                                                )}
                                                                {extractSessionIdFromRun(runDetail) && primaryLinkedFinding && (
                                                                    <button
                                                                        type="button"
                                                                        onClick={() => applySelectionPatch({
                                                                            tab: 'exploration',
                                                                            sessionId: extractSessionIdFromRun(runDetail),
                                                                            findingId: primaryLinkedFinding.finding_id,
                                                                        })}
                                                                        className="inline-flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 transition hover:bg-amber-100 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200 dark:hover:bg-amber-950/30"
                                                                    >
                                                                        <AlertTriangle className="h-4 w-4" />
                                                                        进入人工复核
                                                                    </button>
                                                                )}
                                                            </div>
                                                        </div>
                                                        <div className="mt-3 space-y-2">
                                                            {linkedRunFindings.slice(0, 3).map((finding) => (
                                                                <div key={finding.finding_id} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm dark:border-slate-800 dark:bg-slate-900">
                                                                    <div className="flex flex-wrap items-center gap-2">
                                                                        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${toneClass(finding.severity, RISK_BADGE)}`}>
                                                                            {finding.severity}
                                                                        </span>
                                                                        <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                                                                            {finding.finding_type}
                                                                        </span>
                                                                        {finding.requires_human_review && (
                                                                            <span className="inline-flex rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-700 dark:bg-amber-500/10 dark:text-amber-200">
                                                                                需人工复核
                                                                            </span>
                                                                        )}
                                                                        <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                                                                            复核 {finding.review_status || 'pending'}
                                                                        </span>
                                                                    </div>
                                                                    <div className="mt-2 font-medium text-slate-900 dark:text-white">{finding.title}</div>
                                                                    <div className="mt-1 text-slate-600 dark:text-slate-300">{finding.summary}</div>
                                                                    <div className="mt-2 text-xs text-slate-400">
                                                                        置信度 {Math.round((finding.confidence || 0) * 100)}%
                                                                    </div>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}

                                                {linkedRunAssessment && (
                                                    <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950">
                                                        <div className="flex flex-wrap items-center justify-between gap-2">
                                                            <div>
                                                                <div className="text-sm font-medium text-slate-900 dark:text-white">发布风险结论</div>
                                                                <div className="mt-1 text-xs text-slate-400">结合探索发现与策略命中结果给出当前命令关联的发布判断。</div>
                                                            </div>
                                                            <div className="flex flex-wrap items-center gap-2">
                                                                <button
                                                                    type="button"
                                                                    onClick={() => openReleaseDeployDialog(linkedRunAssessment)}
                                                                    className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-3 py-2 text-xs font-medium text-white transition hover:bg-slate-700 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                                                                >
                                                                    <PlayCircle className="h-4 w-4" />
                                                                    按当前评估发起发布
                                                                </button>
                                                                <button
                                                                    type="button"
                                                                    onClick={() => applySelectionPatch({
                                                                        assessmentId: linkedRunAssessment.assessment_id,
                                                                        sessionId: String(linkedRunAssessment.input?.exploration_session_ids?.[0] || '') || undefined,
                                                                    })}
                                                                    className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                                                                >
                                                                    <Shield className="h-4 w-4" />
                                                                    查看风险评估
                                                                </button>
                                                            </div>
                                                        </div>
                                                        <div className="mt-3 flex flex-wrap items-center gap-2">
                                                            <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${toneClass(linkedRunAssessment.release_risk, RISK_BADGE)}`}>
                                                                发布风险 {linkedRunAssessment.release_risk}
                                                            </span>
                                                            <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${linkedRunAssessment.auto_release_eligible ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200' : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200'}`}>
                                                                {formatAutoReleaseLabel(linkedRunAssessment)}
                                                            </span>
                                                            {linkedAssessmentReviewImpact && (
                                                                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${linkedAssessmentReviewImpact === 'pending' ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200' : 'bg-rose-100 text-rose-700 dark:bg-rose-500/10 dark:text-rose-200'}`}>
                                                                    {linkedAssessmentReviewImpact === 'pending' ? '待复核阻断' : '已确认问题阻断'}
                                                                </span>
                                                            )}
                                                            <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                                                                blockers {linkedRunAssessment.blockers.length}
                                                            </span>
                                                        </div>
                                                        {linkedAssessmentReviewSummary && (
                                                            <div className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                                                                复核摘要：
                                                                {' '}待 {linkedAssessmentReviewSummary.pending}
                                                                {' '}/ 确 {linkedAssessmentReviewSummary.confirmed}
                                                                {' '}/ 驳 {linkedAssessmentReviewSummary.dismissed}
                                                                {' '}/ 生效 {linkedAssessmentReviewSummary.effective}
                                                            </div>
                                                        )}
                                                        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-300">
                                                            当前发布策略：{formatDeployActionHint(linkedRunAssessment)}
                                                        </div>
                                                        {linkedRunAssessment.blockers.length > 0 && (
                                                            <div className="mt-3 space-y-2">
                                                                {linkedRunAssessment.blockers.slice(0, 2).map((item, index) => (
                                                                    <div key={`${linkedRunAssessment.assessment_id}-linked-blocker-${index}`} className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200">
                                                                        {formatBlockerLabel(item)}
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        )}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                )}

                                {linkedReleaseDeployResult && (
                                    <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4 dark:border-slate-700 dark:bg-slate-950/50">
                                        <div className="flex flex-wrap items-center justify-between gap-2">
                                            <div>
                                                <div className="text-sm font-medium text-slate-900 dark:text-white">受控发布结果</div>
                                                <div className="mt-1 text-xs text-slate-400">当前命令已把发布风险评估衔接到了 Deploy 审批与作业链路。</div>
                                            </div>
                                            <a
                                                href="/deploy"
                                                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                                            >
                                                <Shield className="h-4 w-4" />
                                                前往部署控制台
                                            </a>
                                        </div>
                                        <div className="mt-3 flex flex-wrap items-center gap-2">
                                            <span className="inline-flex rounded-full bg-indigo-100 px-2.5 py-1 text-xs font-medium text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-200">
                                                {formatReleaseDecisionLabel(linkedReleaseDeployResult.release_decision)}
                                            </span>
                                            <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                                                {linkedReleaseDeployResult.deploy_target.target_type === 'repo' ? '仓库发布' : '项目全量发布'}
                                            </span>
                                        </div>
                                        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                                            <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-950">
                                                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Assessment</div>
                                                <div className="mt-2 font-medium text-slate-900 dark:text-white">{linkedReleaseDeployResult.assessment_id || '-'}</div>
                                            </div>
                                            <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-950">
                                                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Approval</div>
                                                <div className="mt-2 font-medium text-slate-900 dark:text-white">{linkedReleaseDeployResult.approval_id || '-'}</div>
                                            </div>
                                            <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-950">
                                                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Job</div>
                                                <div className="mt-2 font-medium text-slate-900 dark:text-white">{linkedReleaseDeployResult.job_id || '-'}</div>
                                            </div>
                                            <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-950">
                                                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">目标</div>
                                                <div className="mt-2 font-medium text-slate-900 dark:text-white">
                                                    {linkedReleaseDeployResult.deploy_target.repo_id || linkedReleaseDeployResult.deploy_target.project_key || '-'}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {extractSessionIdFromRun(runDetail) && (
                                    <button
                                        type="button"
                                        onClick={() => onSelectSession(extractSessionIdFromRun(runDetail))}
                                        className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                                    >
                                        <PlayCircle className="h-4 w-4" />
                                        打开关联探索会话
                                    </button>
                                )}

                                {runDetail.approval_status === 'pending' && (
                                    <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-900/40 dark:bg-amber-950/20">
                                        <div className="flex items-center gap-2 text-sm font-medium text-amber-800 dark:text-amber-200">
                                            <Filter className="h-4 w-4" />
                                            当前命令正在等待审批
                                        </div>
                                        <textarea
                                            value={reviewComment}
                                            onChange={(event) => setReviewComment(event.target.value)}
                                            placeholder="填写审批备注或驳回原因"
                                            className="mt-3 min-h-[84px] w-full rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm dark:border-amber-800 dark:bg-slate-950"
                                        />
                                        <div className="mt-3 flex flex-wrap gap-2">
                                            <button
                                                type="button"
                                                onClick={() => void handleReview('approve')}
                                                disabled={reviewing !== ''}
                                                className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:opacity-50"
                                            >
                                                {reviewing === 'approve' ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                                                批准执行
                                            </button>
                                            <button
                                                type="button"
                                                onClick={() => void handleReview('reject')}
                                                disabled={reviewing !== ''}
                                                className="inline-flex items-center gap-2 rounded-xl bg-rose-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-rose-700 disabled:opacity-50"
                                            >
                                                {reviewing === 'reject' ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
                                                驳回命令
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                        <div className="text-lg font-semibold text-slate-900 dark:text-white">发布风险评估</div>
                        <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">基于探索性测试发现生成业务风险、体验风险和自动发布资格结论。</div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        {assessmentDetail && (
                            <button
                                type="button"
                                onClick={() => openReleaseDeployDialog(assessmentDetail)}
                                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                            >
                                <Sparkles className="h-4 w-4" />
                                按当前评估发起发布
                            </button>
                        )}
                        <button
                            type="button"
                            onClick={() => {
                                setAssessmentDraft((prev) => ({
                                    ...prev,
                                    sessionId: selectedSessionId || prev.sessionId,
                                    projectKey: prev.projectKey || profile.project_ids[0] || '',
                                }));
                                setAssessmentOpen(true);
                            }}
                            className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                        >
                            <PlayCircle className="h-4 w-4" />
                            生成发布风险评估
                        </button>
                    </div>
                </div>

                <div className="mt-5 grid gap-5 xl:grid-cols-[1.2fr_1fr]">
                    <DataTable
                        columns={assessmentColumns}
                        data={assessments}
                        rowKey="assessment_id"
                        loading={loading}
                        emptyText="暂无发布风险评估"
                        activeRowKey={selectedAssessmentId}
                        onRowClick={(record) => {
                            const relatedSessionId = record.input?.exploration_session_ids?.[0] || '';
                            applySelectionPatch({
                                assessmentId: record.assessment_id,
                                sessionId: relatedSessionId || undefined,
                            });
                        }}
                    />

                    <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4 dark:border-slate-700 dark:bg-slate-950/50">
                        <div className="text-base font-semibold text-slate-900 dark:text-white">评估详情</div>
                        {!assessmentDetail ? (
                            <div className="mt-4 text-sm text-slate-500 dark:text-slate-400">选择一条评估记录后，这里会显示 blockers、证据和自动发布资格。</div>
                        ) : (
                            <div className="mt-4 space-y-4">
                                <div className="flex flex-wrap items-center gap-2">
                                    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${toneClass(assessmentDetail.release_risk, RISK_BADGE)}`}>
                                        发布风险 {assessmentDetail.release_risk}
                                    </span>
                                    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${assessmentDetail.auto_release_eligible ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200' : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200'}`}>
                                        {formatAutoReleaseLabel(assessmentDetail)}
                                    </span>
                                    {getReviewImpact(assessmentDetail) && (
                                        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${getReviewImpact(assessmentDetail) === 'pending' ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200' : 'bg-rose-100 text-rose-700 dark:bg-rose-500/10 dark:text-rose-200'}`}>
                                            {getReviewImpact(assessmentDetail) === 'pending' ? '待复核阻断' : '已确认问题阻断'}
                                        </span>
                                    )}
                                </div>

                                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                                    <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-950">
                                        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">业务风险</div>
                                        <div className="mt-2 font-medium text-slate-900 dark:text-white">{assessmentDetail.business_risk}</div>
                                    </div>
                                    <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-950">
                                        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">体验风险</div>
                                        <div className="mt-2 font-medium text-slate-900 dark:text-white">{assessmentDetail.ux_risk}</div>
                                    </div>
                                    <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-950">
                                        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">待复核 / 已确认</div>
                                        <div className="mt-2 font-medium text-slate-900 dark:text-white">
                                            {assessmentDetailReviewSummary ? `${assessmentDetailReviewSummary.pending} / ${assessmentDetailReviewSummary.confirmed}` : '-'}
                                        </div>
                                    </div>
                                    <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-950">
                                        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">已驳回 / 生效</div>
                                        <div className="mt-2 font-medium text-slate-900 dark:text-white">
                                            {assessmentDetailReviewSummary ? `${assessmentDetailReviewSummary.dismissed} / ${assessmentDetailReviewSummary.effective}` : '-'}
                                        </div>
                                    </div>
                                </div>

                                <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
                                    当前发布策略：{formatDeployActionHint(assessmentDetail)}
                                </div>

                                <div>
                                    <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Blockers</div>
                                    {assessmentDetail.blockers.length === 0 ? (
                                        <div className="mt-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-200">
                                            当前评估没有命中阻断项。
                                        </div>
                                    ) : (
                                        <div className="mt-2 space-y-2">
                                            {assessmentDetail.blockers.map((item, index) => (
                                                <div key={`${assessmentDetail.assessment_id}-blocker-${index}`} className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200">
                                                    {formatBlockerLabel(item)}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>

                                <div>
                                    <div className="text-xs uppercase tracking-[0.18em] text-slate-400">证据摘要</div>
                                    <pre className="mt-2 overflow-auto rounded-xl bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(assessmentDetail.evidence, null, 2)}</pre>
                                </div>

                                <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-950">
                                    <div className="text-sm text-slate-600 dark:text-slate-300">
                                        受控发布会复用 Deploy 审批与作业链路，并保留完整命令运行、审批和审计痕迹。
                                    </div>
                                    <div className="flex flex-wrap items-center gap-2">
                                        <button
                                            type="button"
                                            onClick={() => openReleaseDeployDialog(assessmentDetail)}
                                            className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                                        >
                                            <PlayCircle className="h-4 w-4" />
                                            按当前评估发起发布
                                        </button>
                                        <a
                                            href="/deploy"
                                            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                                        >
                                            <Shield className="h-4 w-4" />
                                            打开部署控制台
                                        </a>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </section>

            {commandOpen && (
                <div
                    role="dialog"
                    aria-modal="true"
                    aria-label="受控命令发起器"
                    className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/50 px-4"
                >
                    <div className="w-full max-w-3xl rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-700 dark:bg-slate-900">
                        <div className="flex items-center justify-between">
                            <div>
                                <div className="text-lg font-semibold text-slate-900 dark:text-white">发起受控命令</div>
                                <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">按命令网关元数据发起 Web 侧受控命令，所有动作都会生成对应的 command run。</div>
                            </div>
                            <button
                                type="button"
                                onClick={() => setCommandOpen(false)}
                                className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                            >
                                关闭
                            </button>
                        </div>

                        {!selectedLaunchCommand ? (
                            <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200">
                                当前账号没有可执行的受控命令。
                            </div>
                        ) : (
                            <>
                                <div className="mt-5 grid gap-4 md:grid-cols-2">
                                    <label className="text-sm text-slate-600 dark:text-slate-300">
                                        命令
                                        <select
                                            value={selectedLaunchCommand.command_id}
                                            onChange={(event) => setSelectedCommandIdForLaunch(event.target.value)}
                                            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                        >
                                            {allowedCommands.map((item) => (
                                                <option key={item.command_id} value={item.command_id}>{item.command_id}</option>
                                            ))}
                                        </select>
                                    </label>
                                    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-300">
                                        <div>风险：<span className={`rounded-full px-2 py-0.5 text-xs font-medium ${toneClass(selectedLaunchCommand.risk_level, RISK_BADGE)}`}>{selectedLaunchCommand.risk_level}</span></div>
                                        <div className="mt-1">权限：{selectedLaunchCommand.permission}</div>
                                        <div className="mt-1">环境：{selectedLaunchCommand.env_scope} · 项目域：{selectedLaunchCommand.project_scope}</div>
                                        <div className="mt-1">审批：{selectedLaunchCommand.approval_required ? '需要审批' : '无需审批'} · 确认：{selectedLaunchCommand.requires_confirmation ? '显式确认' : '无需确认'}</div>
                                    </div>
                                </div>

                                <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50/80 p-4 dark:border-slate-700 dark:bg-slate-950/50">
                                    <div className="text-sm font-medium text-slate-900 dark:text-white">{selectedLaunchCommand.summary}</div>
                                    <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">{selectedLaunchCommand.description}</div>
                                </div>

                                <div className="mt-5 grid gap-4 md:grid-cols-2">
                                    {selectedLaunchCommand.arguments.length === 0 ? (
                                        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-400 md:col-span-2">
                                            当前命令不需要额外参数，可直接提交。
                                        </div>
                                    ) : selectedLaunchCommand.arguments.map((argument) => {
                                        const rawValue = commandArgumentDrafts[argument.name];
                                        const longText = ['user_input', 'charter', 'change_summary', 'diff_text'].includes(argument.name);
                                        if (argument.type === 'boolean') {
                                            return (
                                                <label
                                                    key={argument.name}
                                                    className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-300"
                                                >
                                                    <input
                                                        type="checkbox"
                                                        aria-label={`${argument.name}${argument.required ? ' *' : ''}`}
                                                        checked={Boolean(rawValue)}
                                                        onChange={(event) => setCommandArgumentDrafts((prev) => ({ ...prev, [argument.name]: event.target.checked }))}
                                                    />
                                                    <span>{argument.name}{argument.required ? ' *' : ''}</span>
                                                    <span className="text-xs text-slate-400">{argument.description || argument.type}</span>
                                                </label>
                                            );
                                        }
                                        return (
                                            <label key={argument.name} className={`text-sm text-slate-600 dark:text-slate-300 ${longText ? 'md:col-span-2' : ''}`}>
                                                {argument.name}{argument.required ? ' *' : ''}
                                                {longText ? (
                                                    <textarea
                                                        aria-label={`${argument.name}${argument.required ? ' *' : ''}`}
                                                        value={String(rawValue ?? '')}
                                                        onChange={(event) => setCommandArgumentDrafts((prev) => ({ ...prev, [argument.name]: event.target.value }))}
                                                        placeholder={argument.description || argument.name}
                                                        rows={4}
                                                        className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                                    />
                                                ) : (
                                                    <input
                                                        type={argument.type === 'integer' ? 'number' : 'text'}
                                                        aria-label={`${argument.name}${argument.required ? ' *' : ''}`}
                                                        value={String(rawValue ?? '')}
                                                        onChange={(event) => setCommandArgumentDrafts((prev) => ({ ...prev, [argument.name]: event.target.value }))}
                                                        placeholder={argument.description || argument.name}
                                                        className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                                    />
                                                )}
                                                <div className="mt-1 text-xs text-slate-400">
                                                    {argument.description || '未提供说明'} · 类型 {argument.type}
                                                </div>
                                            </label>
                                        );
                                    })}
                                </div>

                                {selectedLaunchCommand.requires_confirmation && (
                                    <label className="mt-4 flex items-center gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200">
                                        <input
                                            type="checkbox"
                                            checked={commandConfirm}
                                            onChange={(event) => setCommandConfirm(event.target.checked)}
                                        />
                                        我已确认这是高风险动作，允许通过命令网关继续执行
                                    </label>
                                )}

                                <div className="mt-6 flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-300">
                                    <div>
                                        提交后会生成新的 command run。
                                        {selectedLaunchCommand.approval_required ? ' 如果命中审批策略，会先进入待审批状态。' : ''}
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => void handleExecuteControlledCommand()}
                                        disabled={submittingCommand}
                                        className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                                    >
                                        {submittingCommand ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
                                        提交命令
                                    </button>
                                </div>
                            </>
                        )}
                    </div>
                </div>
            )}

            {assessmentOpen && (
                <div
                    role="dialog"
                    aria-modal="true"
                    aria-label="发布风险评估对话框"
                    className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/50 px-4"
                >
                    <div className="w-full max-w-2xl rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-700 dark:bg-slate-900">
                        <div className="flex items-center justify-between">
                            <div>
                                <div className="text-lg font-semibold text-slate-900 dark:text-white">生成发布风险评估</div>
                                <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">写动作会统一走命令网关并生成对应的 command run。</div>
                            </div>
                            <button
                                type="button"
                                onClick={() => setAssessmentOpen(false)}
                                className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                            >
                                关闭
                            </button>
                        </div>
                        <div className="mt-5 grid gap-4 md:grid-cols-2">
                            <label className="text-sm text-slate-600 dark:text-slate-300">
                                关联探索会话
                                <select
                                    value={assessmentDraft.sessionId}
                                    onChange={(event) => {
                                        const nextSessionId = event.target.value;
                                        const matched = sessions.find((item) => item.session_id === nextSessionId);
                                        setAssessmentDraft((prev) => ({
                                            ...prev,
                                            sessionId: nextSessionId,
                                            projectKey: matched?.project_key || prev.projectKey,
                                        }));
                                    }}
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                >
                                    <option value="">请选择探索会话</option>
                                    {sessions.map((item) => (
                                        <option key={item.session_id} value={item.session_id}>
                                            {item.project_key || 'platform'} · {item.target_url}
                                        </option>
                                    ))}
                                </select>
                            </label>
                            <label className="text-sm text-slate-600 dark:text-slate-300">
                                项目标识
                                <input
                                    value={assessmentDraft.projectKey}
                                    onChange={(event) => setAssessmentDraft((prev) => ({ ...prev, projectKey: event.target.value }))}
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                />
                            </label>
                            <label className="text-sm text-slate-600 dark:text-slate-300">
                                目标环境
                                <select
                                    value={assessmentDraft.environment}
                                    onChange={(event) => setAssessmentDraft((prev) => ({ ...prev, environment: event.target.value }))}
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                >
                                    {['test', 'staging', 'preprod', 'production'].map((item) => (
                                        <option key={item} value={item}>{item}</option>
                                    ))}
                                </select>
                            </label>
                            <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-300">
                                <input
                                    type="checkbox"
                                    checked={assessmentDraft.requiredTestsPassed}
                                    onChange={(event) => setAssessmentDraft((prev) => ({ ...prev, requiredTestsPassed: event.target.checked }))}
                                />
                                所需测试已全部通过
                            </label>
                            <label className="md:col-span-2 text-sm text-slate-600 dark:text-slate-300">
                                变更摘要
                                <textarea
                                    value={assessmentDraft.changeSummary}
                                    onChange={(event) => setAssessmentDraft((prev) => ({ ...prev, changeSummary: event.target.value }))}
                                    rows={4}
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                />
                            </label>
                        </div>
                        <div className="mt-6 flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-300">
                            <div className="flex items-center gap-2">
                                <AlertTriangle className="h-4 w-4 text-amber-500" />
                                当前阶段只生成风险结论，不会真的执行自动发布。
                            </div>
                            <button
                                type="button"
                                onClick={() => void handleCreateAssessment()}
                                disabled={submittingAssessment}
                                className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                            >
                                {submittingAssessment ? <Loader2 className="h-4 w-4 animate-spin" /> : <Shield className="h-4 w-4" />}
                                提交命令并评估
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {releaseDeployOpen && (
                <div
                    role="dialog"
                    aria-modal="true"
                    aria-label="受控发布对话框"
                    className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/50 px-4"
                >
                    <div className="w-full max-w-2xl rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-700 dark:bg-slate-900">
                        <div className="flex items-center justify-between">
                            <div>
                                <div className="text-lg font-semibold text-slate-900 dark:text-white">按当前评估发起发布</div>
                                <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">写动作会统一走命令网关，再复用现有 Deploy 审批与作业调度链路。</div>
                            </div>
                            <button
                                type="button"
                                onClick={() => setReleaseDeployOpen(false)}
                                className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                            >
                                关闭
                            </button>
                        </div>
                        <div className="mt-5 grid gap-4 md:grid-cols-2">
                            <label className="text-sm text-slate-600 dark:text-slate-300">
                                assessment_id
                                <input
                                    value={releaseDeployDraft.assessmentId}
                                    readOnly
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300"
                                />
                            </label>
                            <label className="text-sm text-slate-600 dark:text-slate-300">
                                项目标识
                                <input
                                    value={releaseDeployDraft.projectKey}
                                    readOnly
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300"
                                />
                            </label>
                            <label className="text-sm text-slate-600 dark:text-slate-300">
                                目标环境
                                <input
                                    value={releaseDeployDraft.environment}
                                    readOnly
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300"
                                />
                            </label>
                            <label className="text-sm text-slate-600 dark:text-slate-300">
                                发布目标
                                <select
                                    value={releaseDeployDraft.targetType}
                                    onChange={(event) => setReleaseDeployDraft((prev) => ({
                                        ...prev,
                                        targetType: event.target.value === 'project' ? 'project' : 'repo',
                                    }))}
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                >
                                    <option value="repo">仓库发布</option>
                                    <option value="project">项目全量发布</option>
                                </select>
                            </label>
                            {releaseDeployDraft.targetType === 'repo' && (
                                <>
                                    <label className="text-sm text-slate-600 dark:text-slate-300">
                                        repo_id
                                        <input
                                            aria-label="repo_id"
                                            value={releaseDeployDraft.repoId}
                                            onChange={(event) => setReleaseDeployDraft((prev) => ({ ...prev, repoId: event.target.value }))}
                                            placeholder="例如 frontend-web"
                                            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                        />
                                    </label>
                                    <label className="text-sm text-slate-600 dark:text-slate-300">
                                        branch
                                        <input
                                            aria-label="branch"
                                            value={releaseDeployDraft.branch}
                                            onChange={(event) => setReleaseDeployDraft((prev) => ({ ...prev, branch: event.target.value }))}
                                            placeholder="可选，例如 main"
                                            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                        />
                                    </label>
                                </>
                            )}
                            <label className="md:col-span-2 text-sm text-slate-600 dark:text-slate-300">
                                发布备注
                                <textarea
                                    aria-label="发布备注"
                                    value={releaseDeployDraft.comment}
                                    onChange={(event) => setReleaseDeployDraft((prev) => ({ ...prev, comment: event.target.value }))}
                                    rows={4}
                                    placeholder="可选：补充发布背景、策略依据或人工说明"
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                />
                            </label>
                        </div>
                        <div className="mt-6 flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-300">
                            <div className="flex items-center gap-2">
                                <AlertTriangle className="h-4 w-4 text-amber-500" />
                                当前发布策略：{formatDeployActionHint(releaseDeployAssessment)}
                            </div>
                            <button
                                type="button"
                                onClick={() => void handleCreateReleaseDeploy()}
                                disabled={submittingReleaseDeploy}
                                className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                            >
                                {submittingReleaseDeploy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                                提交受控发布
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
