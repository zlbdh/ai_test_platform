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
        return "Pending human review; automatic release is prohibited";
    case 'confirmed_issue_requires_manual_release':
        return "Confirmed issue; human authorization is required";
    case 'human_review_required':
        return "Blocked by a historical human review; human judgment is required";
    case 'required_tests_failed':
        return "Required tests have not all passed; automatic release is prohibited";
    case 'production_requires_manual_approval':
        return "Production releases must retain human approval";
    default:
        return String(blocker.message || blocker.title || blocker.type || "Unknown blocker");
    }
}

function formatAutoReleaseLabel(assessment?: ReleaseRiskAssessment | null): string {
    if (assessment?.auto_release_eligible) {
        return "Review passed; automatic release is allowed";
    }
    const impact = getReviewImpact(assessment);
    if (impact === 'pending') {
        return "Pending review; automatic release is prohibited";
    }
    if (impact === 'confirmed') {
        return "Confirmed issue; human authorization is required";
    }
    return "Human approval required";
}

function isProductionEnvironment(environment?: string): boolean {
    return ['prod', 'production', 'online'].includes(String(environment || '').trim().toLowerCase());
}

function formatDeployActionHint(assessment?: ReleaseRiskAssessment | null): string {
    if (!assessment) return "Select a release risk assessment first.";
    if (isProductionEnvironment(assessment.environment || assessment.input?.environment)) {
        return "Only a release request pending approval may be created";
    }
    if (getReviewImpact(assessment)) {
        return "Only manually approved releases are currently allowed";
    }
    if (assessment.auto_release_eligible) {
        return "Automatic release allowed";
    }
    return "A release request pending approval will be created";
}

function formatReleaseDecisionLabel(decision?: string): string {
    if (decision === 'auto_executed') {
        return "Controlled release created and executed automatically";
    }
    if (decision === 'approval_created') {
        return "Release request created and awaiting approval";
    }
    return "Controlled release submitted";
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
            setError(err instanceof Error ? err.message : "Failed to load control center");
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
            setError(err instanceof Error ? err.message : "Failed to load notification platform bindings");
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
                setError(err instanceof Error ? err.message : "Failed to load command details");
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
            .catch((err) => setError(err instanceof Error ? err.message : "Failed to load risk assessment details"));
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
                setError(err instanceof Error ? err.message : "Failed to load linked evidence");
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
            setError(err instanceof Error ? err.message : "Failed to generate binding code");
        } finally {
            setBindingMutating('');
        }
    };

    const openReleaseDeployDialog = (assessment?: ReleaseRiskAssessment | null) => {
        if (!assessment) {
            setError("Select a release risk assessment first.");
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
            setError(err instanceof Error ? err.message : "Failed to revoke notification platform binding");
        } finally {
            setBindingMutating('');
        }
    };

    const runColumns: DataTableColumn<CommandRun>[] = [
        {
            key: 'command_id',
            title: "Command",
            render: (_, record) => (
                <div>
                    <div className="font-medium text-slate-900 dark:text-white">{record.command_id}</div>
                    <div className="text-xs text-slate-400">{commandMap[record.command_id]?.summary || record.command_summary}</div>
                </div>
            ),
        },
        {
            key: 'project_key',
            title: "Project",
            render: (value) => <span>{String(value || "Platform-wide")}</span>,
        },
        {
            key: 'source',
            title: "Source",
            render: (value) => (
                <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                    {String(value || '-')}
                </span>
            ),
        },
        {
            key: 'status',
            title: "Runtime status",
            render: (value) => (
                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${toneClass(String(value || ''), STATUS_BADGE)}`}>
                    {String(value || '-')}
                </span>
            ),
        },
        {
            key: 'approval_status',
            title: "Approval",
            render: (value) => (
                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${toneClass(String(value || ''), STATUS_BADGE)}`}>
                    {String(value || '-')}
                </span>
            ),
        },
        {
            key: 'risk_level',
            title: "Risk",
            render: (value) => (
                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${toneClass(String(value || ''), RISK_BADGE)}`}>
                    {String(value || '-')}
                </span>
            ),
        },
        {
            key: 'created_at',
            title: "Created at",
            render: (value) => formatDateTime(String(value || '')),
        },
    ];

    const assessmentColumns: DataTableColumn<ReleaseRiskAssessment>[] = [
        { key: 'project_key', title: "Project" },
        { key: 'environment', title: "Environment" },
        {
            key: 'release_risk',
            title: "Release risk",
            render: (value) => (
                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${toneClass(String(value || ''), RISK_BADGE)}`}>
                    {String(value || '-')}
                </span>
            ),
        },
        {
            key: 'auto_release_eligible',
            title: "Automatic release eligibility",
            render: (value) => Boolean(value)
                ? <span className="inline-flex rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200">Eligible for automatic release</span>
                : <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-200">Human authorization required</span>,
        },
        {
            key: 'review_summary',
            title: "Review summary",
            render: (_, record) => {
                const summary = getReviewSummary(record);
                if (!summary) {
                    return <span className="text-xs text-slate-400">History</span>;
                }
                return (
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                        Pending {summary.pending} / Confirmed {summary.confirmed} / Rejected {summary.dismissed}
                    </span>
                );
            },
        },
        {
            key: 'created_at',
            title: "Assessment time",
            render: (value) => formatDateTime(String(value || '')),
        },
    ];

    const handleReview = async (decision: 'approve' | 'reject') => {
        if (!runDetail?.run_id) return;
        setReviewing(decision);
        setError('');
        try {
            if (decision === 'approve') {
                const payload = await approveRun(runDetail.run_id, reviewComment || "Approve execution", true);
                setRunDetail(payload.run);
                onSelectRun(payload.run.run_id);
            } else {
                const payload = await rejectRun(runDetail.run_id, reviewComment || "Reject manually");
                setRunDetail(payload.run);
                onSelectRun(payload.run.run_id);
            }
            setReviewComment('');
            await refresh();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Approval action failed");
        } finally {
            setReviewing('');
        }
    };

    const handleCreateAssessment = async () => {
        if (!assessmentDraft.sessionId) {
            setError("Select an exploration session before generating a release risk assessment.");
            return;
        }
        if (!assessmentDraft.projectKey.trim()) {
            setError("Enter a project identifier first.");
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
            setError(err instanceof Error ? err.message : "Failed to generate risk assessment");
        } finally {
            setSubmittingAssessment(false);
        }
    };

    const handleCreateReleaseDeploy = async () => {
        if (!releaseDeployDraft.assessmentId) {
            setError("Select a release risk assessment first.");
            return;
        }
        if (!releaseDeployDraft.projectKey.trim()) {
            setError("This assessment has no project identifier, so a release cannot be started.");
            return;
        }
        if (releaseDeployDraft.targetType === 'repo' && !releaseDeployDraft.repoId.trim()) {
            setError("A repository release requires repo_id.");
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
            setError(err instanceof Error ? err.message : "Failed to start controlled release");
        } finally {
            setSubmittingReleaseDeploy(false);
        }
    };

    const handleExecuteControlledCommand = async () => {
        if (!selectedLaunchCommand) {
            setError("No controlled commands are currently executable.");
            return;
        }
        if (selectedLaunchCommand.requires_confirmation && !commandConfirm) {
            setError(`Command ${selectedLaunchCommand.command_id} is a high-risk action. Select the explicit confirmation checkbox first.`);
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
            setError(err instanceof Error ? err.message : "Failed to start controlled command");
        } finally {
            setSubmittingCommand(false);
        }
    };

    return (
        <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
                <SummaryCard label={"Commands awaiting approval"} value={String(summary.pending)} hint={"Write actions that require human approval before execution can continue"} icon={<Clock className="h-5 w-5" />} />
                <SummaryCard label={"Running commands"} value={String(summary.running)} hint={"Controlled command runs currently in progress"} icon={<Loader2 className="h-5 w-5" />} />
                <SummaryCard label={"Failed commands"} value={String(summary.failed)} hint={"Runs that require investigation or a new decision"} icon={<XCircle className="h-5 w-5" />} />
                <SummaryCard label={"Recent assessments"} value={String(summary.assessments)} hint={"Number of recently generated release risk assessments"} icon={<Shield className="h-5 w-5" />} />
                <SummaryCard label={"Eligible for automatic release"} value={String(summary.autoRelease)} hint={"Assessments eligible for low-risk, nonproduction automatic release"} icon={<Sparkles className="h-5 w-5" />} />
                <SummaryCard label={"Notification platform commands"} value={String(summary.notification_platformRuns)} hint={"Command runs in this list initiated from the notification platform"} icon={<CheckCircle2 className="h-5 w-5" />} />
            </div>

            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <div className="text-lg font-semibold text-slate-900 dark:text-white">My notification platform bindings</div>
                        <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">Generate a one-time binding code in Legion, then send "bind &lt;code&gt;" on the notification platform. Subsequent commands will be attributed to your current platform account.</div>
                    </div>
                    <button
                        type="button"
                        onClick={() => void refreshBinding()}
                        className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                    >
                        <Loader2 className={`h-4 w-4 ${bindingLoading ? 'animate-spin' : ''}`} />
                        Refresh binding status
                    </button>
                </div>

                <div className="mt-4 grid gap-4 xl:grid-cols-[1.2fr_1fr]">
                    <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4 dark:border-slate-700 dark:bg-slate-950/50">
                        <div className="flex flex-wrap items-center gap-2">
                            <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${binding ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200' : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200'}`}>
                                {binding ? "Bound" : "Not bound"}
                            </span>
                            <span className="text-sm text-slate-500 dark:text-slate-400">
                                {binding ? `Notification platform identity ${binding.notification_platform_open_id}` : "This notification platform identity is not bound to a platform account"}
                            </span>
                        </div>
                        <div className="mt-4 space-y-2 text-sm text-slate-600 dark:text-slate-300">
                            <div>Platform account: {binding?.username || profile.username}</div>
                            <div>Current chat: {binding?.chat_id || "Not recorded"}</div>
                            <div>Last contact: {formatDateTime(binding?.last_seen_at || '')}</div>
                            <div>Bound at: {formatDateTime(binding?.bound_at || '')}</div>
                        </div>
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4 dark:border-slate-700 dark:bg-slate-950/50">
                        <div className="text-sm font-medium text-slate-900 dark:text-white">One-time binding code</div>
                        {!pendingBindingCode ? (
                            <div className="mt-3 text-sm text-slate-500 dark:text-slate-400">No unused binding code is available. Generate a new code valid for 10 minutes.</div>
                        ) : (
                            <div className="mt-3 space-y-2 text-sm text-slate-600 dark:text-slate-300">
                                <div className="rounded-xl bg-slate-900 px-3 py-2 font-mono text-slate-100">{pendingBindingCode.code}</div>
                                <div>Status: {pendingBindingCode.status}</div>
                                <div>Expires at: {formatDateTime(pendingBindingCode.expires_at)}</div>
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
                                Generate binding code
                            </button>
                            <button
                                type="button"
                                onClick={() => void handleRevokeBinding()}
                                disabled={bindingMutating !== '' || (!binding && !pendingBindingCode)}
                                className="inline-flex items-center gap-2 rounded-xl border border-rose-200 px-3 py-2 text-sm text-rose-700 transition hover:bg-rose-50 disabled:opacity-50 dark:border-rose-900/40 dark:text-rose-200 dark:hover:bg-rose-950/20"
                            >
                                {bindingMutating === 'revoke' ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
                                Revoke binding
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
                        <div className="text-lg font-semibold text-slate-900 dark:text-white">Command runs and approvals</div>
                        <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">All web write actions create command run records. Approval and auditing determine subsequent execution.</div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <button
                            type="button"
                            onClick={() => setCommandOpen(true)}
                            className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                        >
                            <PlayCircle className="h-4 w-4" />
                            Start controlled command
                        </button>
                        <button
                            type="button"
                            onClick={() => void refresh()}
                            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                        >
                            <Loader2 className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                            Refresh control center
                        </button>
                    </div>
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-5">
                    <label className="text-sm text-slate-600 dark:text-slate-300">
                        Filter commands
                        <select
                            value={commandRunFilters.commandId}
                            onChange={(event) => setCommandRunFilters({ commandId: event.target.value })}
                            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                        >
                            <option value="">All commands</option>
                            {commands.map((item) => (
                                <option key={item.command_id} value={item.command_id}>{item.command_id}</option>
                            ))}
                        </select>
                    </label>
                    <label className="text-sm text-slate-600 dark:text-slate-300">
                        Filter projects
                        <input
                            value={commandRunFilters.projectKey}
                            onChange={(event) => setCommandRunFilters({ projectKey: event.target.value })}
                            placeholder="demo"
                            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                        />
                    </label>
                    <label className="text-sm text-slate-600 dark:text-slate-300">
                        Runtime status
                        <select
                            value={commandRunFilters.status}
                            onChange={(event) => setCommandRunFilters({ status: event.target.value })}
                            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                        >
                            <option value="">All statuses</option>
                            {['created', 'running', 'approval_pending', 'approved_pending_execution', 'succeeded', 'failed', 'rejected'].map((status) => (
                                <option key={status} value={status}>{status}</option>
                            ))}
                        </select>
                    </label>
                    <label className="text-sm text-slate-600 dark:text-slate-300">
                        Approval status
                        <select
                            value={commandRunFilters.approvalStatus}
                            onChange={(event) => setCommandRunFilters({ approvalStatus: event.target.value })}
                            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                        >
                            <option value="">All approvals</option>
                            {['not_required', 'pending', 'approved', 'rejected'].map((status) => (
                                <option key={status} value={status}>{status}</option>
                            ))}
                        </select>
                    </label>
                    <label className="text-sm text-slate-600 dark:text-slate-300">
                        Filter sources
                        <select
                            value={commandRunFilters.source}
                            onChange={(event) => setCommandRunFilters({ source: event.target.value })}
                            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                        >
                            <option value="">All sources</option>
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
                        emptyText={"No command runs yet"}
                        activeRowKey={selectedRunId}
                        onRowClick={(record) => onSelectRun(record.run_id)}
                    />

                    <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4 dark:border-slate-700 dark:bg-slate-950/50">
                        <div className="flex items-center justify-between">
                            <div className="text-base font-semibold text-slate-900 dark:text-white">Command details</div>
                            {detailLoading && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
                        </div>
                        {!runDetail ? (
                            <div className="mt-4 text-sm text-slate-500 dark:text-slate-400">Select a command run to view its parameters, approval status, results, and error details.</div>
                        ) : (
                            <div className="mt-4 space-y-4">
                                <div className="space-y-2 text-sm text-slate-600 dark:text-slate-300">
                                    <div className="font-medium text-slate-900 dark:text-white">{runDetail.command_id}</div>
                                    <div>Project: {runDetail.project_key || "Platform-wide"}</div>
                                    <div>Requested by: {runDetail.requester_id || '-'}</div>
                                    <div>Request channel: {runDetail.source || '-'}</div>
                                    <div>Created at: {formatDateTime(runDetail.created_at)}</div>
                                    <div>Risk:<span className={`rounded-full px-2 py-0.5 text-xs font-medium ${toneClass(runDetail.risk_level, RISK_BADGE)}`}>{runDetail.risk_level}</span></div>
                                    <div>Approval:<span className={`rounded-full px-2 py-0.5 text-xs font-medium ${toneClass(runDetail.approval_status, STATUS_BADGE)}`}>{runDetail.approval_status}</span></div>
                                </div>

                                {runDetail.source_context && Object.keys(runDetail.source_context).length > 0 && (
                                    <div>
                                        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Source context</div>
                                        <div className="mt-2 grid gap-3 md:grid-cols-2">
                                            <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-950">
                                                <div>Channel: {String(runDetail.source_context.channel || runDetail.source || '-')}</div>
                                                <div>Notification platform user: {String(runDetail.source_context.from_user || '-')}</div>
                                                <div>chat_id: {String(runDetail.source_context.chat_id || '-')}</div>
                                                <div>Binding status: {String(runDetail.source_context.binding_status || '-')}</div>
                                            </div>
                                            <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-950">
                                                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Original message summary</div>
                                                <div className="mt-2 whitespace-pre-wrap break-all text-slate-700 dark:text-slate-200">
                                                    {String(runDetail.source_context.raw_message || '-')}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                <div>
                                    <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Parameters</div>
                                    <pre className="mt-2 overflow-auto rounded-xl bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(runDetail.arguments, null, 2)}</pre>
                                </div>

                                {Boolean(runDetail.result) && (
                                    <div>
                                        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Result</div>
                                        <pre className="mt-2 overflow-auto rounded-xl bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(runDetail.result, null, 2)}</pre>
                                    </div>
                                )}
                                {Boolean(runDetail.error) && (
                                    <div>
                                        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Error</div>
                                        <pre className="mt-2 overflow-auto rounded-xl bg-slate-900 p-3 text-xs text-red-200">{JSON.stringify(runDetail.error, null, 2)}</pre>
                                    </div>
                                )}

                                {(linkedEvidenceLoading || linkedRunFindings.length > 0 || linkedRunAssessment) && (
                                    <div>
                                        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Linked evidence summary</div>
                                        {linkedEvidenceLoading ? (
                                            <div className="mt-2 inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400">
                                                <Loader2 className="h-4 w-4 animate-spin" />
                                                Loading linked exploration findings and risk conclusions...
                                            </div>
                                        ) : (
                                            <div className="mt-2 space-y-3">
                                                {linkedRunFindings.length > 0 && (
                                                    <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950">
                                                        <div className="flex flex-wrap items-center justify-between gap-2">
                                                            <div>
                                                                <div className="text-sm font-medium text-slate-900 dark:text-white">Exploration findings</div>
                                                                <div className="mt-1 text-xs text-slate-400">Total: {linkedRunFindings.length} linked findings, with evidence requiring human attention shown first.</div>
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
                                                                        View exploration findings
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
                                                                        Open human review
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
                                                                                Human review required
                                                                            </span>
                                                                        )}
                                                                        <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                                                                            Review {finding.review_status || 'pending'}
                                                                        </span>
                                                                    </div>
                                                                    <div className="mt-2 font-medium text-slate-900 dark:text-white">{finding.title}</div>
                                                                    <div className="mt-1 text-slate-600 dark:text-slate-300">{finding.summary}</div>
                                                                    <div className="mt-2 text-xs text-slate-400">
                                                                        Confidence {Math.round((finding.confidence || 0) * 100)}%
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
                                                                <div className="text-sm font-medium text-slate-900 dark:text-white">Release risk conclusion</div>
                                                                <div className="mt-1 text-xs text-slate-400">The release decision associated with this command combines exploration findings with policy matches.</div>
                                                            </div>
                                                            <div className="flex flex-wrap items-center gap-2">
                                                                <button
                                                                    type="button"
                                                                    onClick={() => openReleaseDeployDialog(linkedRunAssessment)}
                                                                    className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-3 py-2 text-xs font-medium text-white transition hover:bg-slate-700 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                                                                >
                                                                    <PlayCircle className="h-4 w-4" />
                                                                    Start release using this assessment
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
                                                                    View risk assessment
                                                                </button>
                                                            </div>
                                                        </div>
                                                        <div className="mt-3 flex flex-wrap items-center gap-2">
                                                            <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${toneClass(linkedRunAssessment.release_risk, RISK_BADGE)}`}>
                                                                Release risk {linkedRunAssessment.release_risk}
                                                            </span>
                                                            <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${linkedRunAssessment.auto_release_eligible ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200' : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200'}`}>
                                                                {formatAutoReleaseLabel(linkedRunAssessment)}
                                                            </span>
                                                            {linkedAssessmentReviewImpact && (
                                                                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${linkedAssessmentReviewImpact === 'pending' ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200' : 'bg-rose-100 text-rose-700 dark:bg-rose-500/10 dark:text-rose-200'}`}>
                                                                    {linkedAssessmentReviewImpact === 'pending' ? "Blocked pending review" : "Blocked by confirmed issues"}
                                                                </span>
                                                            )}
                                                            <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                                                                blockers {linkedRunAssessment.blockers.length}
                                                            </span>
                                                        </div>
                                                        {linkedAssessmentReviewSummary && (
                                                            <div className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                                                                Review summary:
                                                                {' '} Pending {linkedAssessmentReviewSummary.pending}
                                                                {' '} / Confirmed {linkedAssessmentReviewSummary.confirmed}
                                                                {' '} / Rejected {linkedAssessmentReviewSummary.dismissed}
                                                                {' '} / Effective {linkedAssessmentReviewSummary.effective}
                                                            </div>
                                                        )}
                                                        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-300">
                                                            Current release policy: {formatDeployActionHint(linkedRunAssessment)}
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
                                                <div className="text-sm font-medium text-slate-900 dark:text-white">Controlled release result</div>
                                                <div className="mt-1 text-xs text-slate-400">This command has connected the release risk assessment to Deploy approvals and jobs.</div>
                                            </div>
                                            <a
                                                href="/deploy"
                                                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                                            >
                                                <Shield className="h-4 w-4" />
                                                Open deployment console
                                            </a>
                                        </div>
                                        <div className="mt-3 flex flex-wrap items-center gap-2">
                                            <span className="inline-flex rounded-full bg-indigo-100 px-2.5 py-1 text-xs font-medium text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-200">
                                                {formatReleaseDecisionLabel(linkedReleaseDeployResult.release_decision)}
                                            </span>
                                            <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                                                {linkedReleaseDeployResult.deploy_target.target_type === 'repo' ? "Repository release" : "Full project release"}
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
                                                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Target</div>
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
                                        Open linked exploration session
                                    </button>
                                )}

                                {runDetail.approval_status === 'pending' && (
                                    <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-900/40 dark:bg-amber-950/20">
                                        <div className="flex items-center gap-2 text-sm font-medium text-amber-800 dark:text-amber-200">
                                            <Filter className="h-4 w-4" />
                                            This command is awaiting approval
                                        </div>
                                        <textarea
                                            value={reviewComment}
                                            onChange={(event) => setReviewComment(event.target.value)}
                                            placeholder={"Enter an approval note or rejection reason"}
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
                                                Approve execution
                                            </button>
                                            <button
                                                type="button"
                                                onClick={() => void handleReview('reject')}
                                                disabled={reviewing !== ''}
                                                className="inline-flex items-center gap-2 rounded-xl bg-rose-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-rose-700 disabled:opacity-50"
                                            >
                                                {reviewing === 'reject' ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
                                                Reject command
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
                        <div className="text-lg font-semibold text-slate-900 dark:text-white">Release risk assessment</div>
                        <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">Assess business risk, experience risk, and automatic release eligibility from exploratory testing findings.</div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        {assessmentDetail && (
                            <button
                                type="button"
                                onClick={() => openReleaseDeployDialog(assessmentDetail)}
                                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                            >
                                <Sparkles className="h-4 w-4" />
                                Start release using this assessment
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
                            Generate release risk assessment
                        </button>
                    </div>
                </div>

                <div className="mt-5 grid gap-5 xl:grid-cols-[1.2fr_1fr]">
                    <DataTable
                        columns={assessmentColumns}
                        data={assessments}
                        rowKey="assessment_id"
                        loading={loading}
                        emptyText={"No release risk assessments yet"}
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
                        <div className="text-base font-semibold text-slate-900 dark:text-white">Assessment details</div>
                        {!assessmentDetail ? (
                            <div className="mt-4 text-sm text-slate-500 dark:text-slate-400">Select an assessment to view blockers, evidence, and automatic release eligibility.</div>
                        ) : (
                            <div className="mt-4 space-y-4">
                                <div className="flex flex-wrap items-center gap-2">
                                    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${toneClass(assessmentDetail.release_risk, RISK_BADGE)}`}>
                                        Release risk {assessmentDetail.release_risk}
                                    </span>
                                    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${assessmentDetail.auto_release_eligible ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200' : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200'}`}>
                                        {formatAutoReleaseLabel(assessmentDetail)}
                                    </span>
                                    {getReviewImpact(assessmentDetail) && (
                                        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${getReviewImpact(assessmentDetail) === 'pending' ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200' : 'bg-rose-100 text-rose-700 dark:bg-rose-500/10 dark:text-rose-200'}`}>
                                            {getReviewImpact(assessmentDetail) === 'pending' ? "Blocked pending review" : "Blocked by confirmed issues"}
                                        </span>
                                    )}
                                </div>

                                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                                    <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-950">
                                        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Business risk</div>
                                        <div className="mt-2 font-medium text-slate-900 dark:text-white">{assessmentDetail.business_risk}</div>
                                    </div>
                                    <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-950">
                                        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Experience risk</div>
                                        <div className="mt-2 font-medium text-slate-900 dark:text-white">{assessmentDetail.ux_risk}</div>
                                    </div>
                                    <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-950">
                                        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Pending review / Confirmed</div>
                                        <div className="mt-2 font-medium text-slate-900 dark:text-white">
                                            {assessmentDetailReviewSummary ? `${assessmentDetailReviewSummary.pending} / ${assessmentDetailReviewSummary.confirmed}` : '-'}
                                        </div>
                                    </div>
                                    <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-950">
                                        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Rejected / Effective</div>
                                        <div className="mt-2 font-medium text-slate-900 dark:text-white">
                                            {assessmentDetailReviewSummary ? `${assessmentDetailReviewSummary.dismissed} / ${assessmentDetailReviewSummary.effective}` : '-'}
                                        </div>
                                    </div>
                                </div>

                                <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
                                    Current release policy: {formatDeployActionHint(assessmentDetail)}
                                </div>

                                <div>
                                    <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Blockers</div>
                                    {assessmentDetail.blockers.length === 0 ? (
                                        <div className="mt-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-200">
                                            This assessment has no matching blockers.
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
                                    <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Evidence summary</div>
                                    <pre className="mt-2 overflow-auto rounded-xl bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(assessmentDetail.evidence, null, 2)}</pre>
                                </div>

                                <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-950">
                                    <div className="text-sm text-slate-600 dark:text-slate-300">
                                        Controlled releases reuse Deploy approvals and jobs while retaining complete command run, approval, and audit records.
                                    </div>
                                    <div className="flex flex-wrap items-center gap-2">
                                        <button
                                            type="button"
                                            onClick={() => openReleaseDeployDialog(assessmentDetail)}
                                            className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                                        >
                                            <PlayCircle className="h-4 w-4" />
                                            Start release using this assessment
                                        </button>
                                        <a
                                            href="/deploy"
                                            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                                        >
                                            <Shield className="h-4 w-4" />
                                            Open deployment console
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
                    aria-label={"Controlled command launcher"}
                    className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/50 px-4"
                >
                    <div className="w-full max-w-3xl rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-700 dark:bg-slate-900">
                        <div className="flex items-center justify-between">
                            <div>
                                <div className="text-lg font-semibold text-slate-900 dark:text-white">Start controlled command</div>
                                <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">Launch controlled web commands using command gateway metadata. Each action creates a corresponding command run.</div>
                            </div>
                            <button
                                type="button"
                                onClick={() => setCommandOpen(false)}
                                className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                            >
                                Close
                            </button>
                        </div>

                        {!selectedLaunchCommand ? (
                            <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200">
                                This account has no executable controlled commands.
                            </div>
                        ) : (
                            <>
                                <div className="mt-5 grid gap-4 md:grid-cols-2">
                                    <label className="text-sm text-slate-600 dark:text-slate-300">
                                        Command
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
                                        <div>Risk:<span className={`rounded-full px-2 py-0.5 text-xs font-medium ${toneClass(selectedLaunchCommand.risk_level, RISK_BADGE)}`}>{selectedLaunchCommand.risk_level}</span></div>
                                        <div className="mt-1">Permission: {selectedLaunchCommand.permission}</div>
                                        <div className="mt-1">Environment: {selectedLaunchCommand.env_scope} · Project scope: {selectedLaunchCommand.project_scope}</div>
                                        <div className="mt-1">Approval: {selectedLaunchCommand.approval_required ? "Approval required" : "No approval required"} · Confirmation: {selectedLaunchCommand.requires_confirmation ? "Explicit confirmation" : "No confirmation required"}</div>
                                    </div>
                                </div>

                                <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50/80 p-4 dark:border-slate-700 dark:bg-slate-950/50">
                                    <div className="text-sm font-medium text-slate-900 dark:text-white">{selectedLaunchCommand.summary}</div>
                                    <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">{selectedLaunchCommand.description}</div>
                                </div>

                                <div className="mt-5 grid gap-4 md:grid-cols-2">
                                    {selectedLaunchCommand.arguments.length === 0 ? (
                                        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-400 md:col-span-2">
                                            This command requires no additional parameters and can be submitted directly.
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
                                                    {argument.description || "No description provided"} · Type {argument.type}
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
                                        I confirm this is a high-risk action and authorize execution through the command gateway
                                    </label>
                                )}

                                <div className="mt-6 flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-300">
                                    <div>
                                        Submitting creates a new command run.
                                        {selectedLaunchCommand.approval_required ? " If an approval policy applies, the run first enters the pending approval state." : ''}
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => void handleExecuteControlledCommand()}
                                        disabled={submittingCommand}
                                        className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                                    >
                                        {submittingCommand ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
                                        Submit command
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
                    aria-label={"Release risk assessment dialog"}
                    className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/50 px-4"
                >
                    <div className="w-full max-w-2xl rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-700 dark:bg-slate-900">
                        <div className="flex items-center justify-between">
                            <div>
                                <div className="text-lg font-semibold text-slate-900 dark:text-white">Generate release risk assessment</div>
                                <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">Write actions go through the command gateway and create corresponding command runs.</div>
                            </div>
                            <button
                                type="button"
                                onClick={() => setAssessmentOpen(false)}
                                className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                            >
                                Close
                            </button>
                        </div>
                        <div className="mt-5 grid gap-4 md:grid-cols-2">
                            <label className="text-sm text-slate-600 dark:text-slate-300">
                                Linked exploration session
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
                                    <option value="">Select an exploration session</option>
                                    {sessions.map((item) => (
                                        <option key={item.session_id} value={item.session_id}>
                                            {item.project_key || 'platform'} · {item.target_url}
                                        </option>
                                    ))}
                                </select>
                            </label>
                            <label className="text-sm text-slate-600 dark:text-slate-300">
                                Project identifier
                                <input
                                    value={assessmentDraft.projectKey}
                                    onChange={(event) => setAssessmentDraft((prev) => ({ ...prev, projectKey: event.target.value }))}
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                />
                            </label>
                            <label className="text-sm text-slate-600 dark:text-slate-300">
                                Target environment
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
                                All required tests have passed
                            </label>
                            <label className="md:col-span-2 text-sm text-slate-600 dark:text-slate-300">
                                Change summary
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
                                This step only generates a risk conclusion. It does not execute an automatic release.
                            </div>
                            <button
                                type="button"
                                onClick={() => void handleCreateAssessment()}
                                disabled={submittingAssessment}
                                className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                            >
                                {submittingAssessment ? <Loader2 className="h-4 w-4 animate-spin" /> : <Shield className="h-4 w-4" />}
                                Submit command and assess
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {releaseDeployOpen && (
                <div
                    role="dialog"
                    aria-modal="true"
                    aria-label={"Controlled release dialog"}
                    className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/50 px-4"
                >
                    <div className="w-full max-w-2xl rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-700 dark:bg-slate-900">
                        <div className="flex items-center justify-between">
                            <div>
                                <div className="text-lg font-semibold text-slate-900 dark:text-white">Start release using this assessment</div>
                                <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">Write actions go through the command gateway and reuse the existing Deploy approval and job scheduling flow.</div>
                            </div>
                            <button
                                type="button"
                                onClick={() => setReleaseDeployOpen(false)}
                                className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                            >
                                Close
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
                                Project identifier
                                <input
                                    value={releaseDeployDraft.projectKey}
                                    readOnly
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300"
                                />
                            </label>
                            <label className="text-sm text-slate-600 dark:text-slate-300">
                                Target environment
                                <input
                                    value={releaseDeployDraft.environment}
                                    readOnly
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300"
                                />
                            </label>
                            <label className="text-sm text-slate-600 dark:text-slate-300">
                                Release target
                                <select
                                    value={releaseDeployDraft.targetType}
                                    onChange={(event) => setReleaseDeployDraft((prev) => ({
                                        ...prev,
                                        targetType: event.target.value === 'project' ? 'project' : 'repo',
                                    }))}
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                >
                                    <option value="repo">Repository release</option>
                                    <option value="project">Full project release</option>
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
                                            placeholder={"Example: frontend-web"}
                                            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                        />
                                    </label>
                                    <label className="text-sm text-slate-600 dark:text-slate-300">
                                        branch
                                        <input
                                            aria-label="branch"
                                            value={releaseDeployDraft.branch}
                                            onChange={(event) => setReleaseDeployDraft((prev) => ({ ...prev, branch: event.target.value }))}
                                            placeholder={"Optional, for example: main"}
                                            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                        />
                                    </label>
                                </>
                            )}
                            <label className="md:col-span-2 text-sm text-slate-600 dark:text-slate-300">
                                Release notes
                                <textarea
                                    aria-label={"Release notes"}
                                    value={releaseDeployDraft.comment}
                                    onChange={(event) => setReleaseDeployDraft((prev) => ({ ...prev, comment: event.target.value }))}
                                    rows={4}
                                    placeholder={"Optional: add release context, policy rationale, or reviewer notes"}
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                />
                            </label>
                        </div>
                        <div className="mt-6 flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-300">
                            <div className="flex items-center gap-2">
                                <AlertTriangle className="h-4 w-4 text-amber-500" />
                                Current release policy: {formatDeployActionHint(releaseDeployAssessment)}
                            </div>
                            <button
                                type="button"
                                onClick={() => void handleCreateReleaseDeploy()}
                                disabled={submittingReleaseDeploy}
                                className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                            >
                                {submittingReleaseDeploy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                                Submit controlled release
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
