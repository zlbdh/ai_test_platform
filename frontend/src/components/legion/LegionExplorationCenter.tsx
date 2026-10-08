import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    AlertTriangle,
    CheckCircle2,
    Compass,
    Eye,
    Loader2,
    Sparkles,
    XCircle,
} from '../icons';
import DataTable, { type DataTableColumn } from '../ui/DataTable';
import {
    executeCommand,
    getExplorationFinding,
    getExplorationSession,
    listExplorationFindings,
    listExplorationReviewQueue,
    listExplorationSessions,
    type ExperienceFinding,
    type ExplorationSession,
} from '../../services/legionControlService';
import type { ControlAuthProfile } from '../../services/controlAuthService';
import { useLegionControlStore } from '../../stores';
import type { LegionTabId } from '../../stores/legionControlStore';

interface LegionExplorationCenterProps {
    profile: ControlAuthProfile;
    selectedSessionId: string | null;
    selectedFindingId: string | null;
    onSelectSession: (sessionId: string | null) => void;
    onSelectFinding: (findingId: string | null) => void;
    onSelectRun: (runId: string | null) => void;
    onSelectRunAndSession?: (payload: { runId: string | null; sessionId: string | null; findingId?: string | null }) => void;
    onUpdateSelection?: (patch: {
        tab?: LegionTabId;
        runId?: string | null;
        sessionId?: string | null;
        assessmentId?: string | null;
        findingId?: string | null;
    }) => void;
}

interface LaunchSessionDraft {
    projectKey: string;
    groupId: string;
    targetUrl: string;
    charter: string;
}

const SEVERITY_BADGE: Record<string, string> = {
    low: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200',
    medium: 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200',
    high: 'bg-orange-100 text-orange-700 dark:bg-orange-500/10 dark:text-orange-200',
    critical: 'bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-200',
};

const REVIEW_BADGE: Record<string, string> = {
    pending: 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200',
    confirmed: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200',
    dismissed: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200',
};

interface ReviewQueueSummary {
    pending: number;
    confirmed: number;
    dismissed: number;
}

function formatDateTime(value?: string): string {
    if (!value) return '-';
    return value.replace('T', ' ');
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

export default function LegionExplorationCenter({
    profile,
    selectedSessionId,
    selectedFindingId,
    onSelectSession,
    onSelectFinding,
    onSelectRun,
    onSelectRunAndSession,
    onUpdateSelection,
}: LegionExplorationCenterProps) {
    const { explorationFilters, setExplorationFilters, markRefreshed } = useLegionControlStore();
    const [sessions, setSessions] = useState<ExplorationSession[]>([]);
    const [sessionDetail, setSessionDetail] = useState<ExplorationSession | null>(null);
    const [findings, setFindings] = useState<ExperienceFinding[]>([]);
    const [deepLinkedFinding, setDeepLinkedFinding] = useState<ExperienceFinding | null>(null);
    const [reviewQueueFindings, setReviewQueueFindings] = useState<ExperienceFinding[]>([]);
    const [reviewQueueSummary, setReviewQueueSummary] = useState<ReviewQueueSummary>({
        pending: 0,
        confirmed: 0,
        dismissed: 0,
    });
    const [loading, setLoading] = useState(true);
    const [detailLoading, setDetailLoading] = useState(false);
    const [queueLoading, setQueueLoading] = useState(false);
    const [error, setError] = useState('');
    const [launchOpen, setLaunchOpen] = useState(false);
    const [launching, setLaunching] = useState(false);
    const [reviewComment, setReviewComment] = useState('');
    const [reviewing, setReviewing] = useState<'confirmed' | 'dismissed' | ''>('');
    const [draft, setDraft] = useState<LaunchSessionDraft>({
        projectKey: profile.project_ids[0] || '',
        groupId: '',
        targetUrl: '',
        charter: '',
    });

    const selectedFinding = useMemo(
        () => findings.find((item) => item.finding_id === selectedFindingId)
            || (deepLinkedFinding?.finding_id === selectedFindingId ? deepLinkedFinding : null)
            || null,
        [deepLinkedFinding, findings, selectedFindingId],
    );

    const refreshSessions = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            const payload = await listExplorationSessions({
                project_key: explorationFilters.projectKey,
                status: explorationFilters.status,
                limit: 30,
            });
            setSessions(payload.sessions);
            markRefreshed();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load exploration sessions");
        } finally {
            setLoading(false);
        }
    }, [explorationFilters.projectKey, explorationFilters.status, markRefreshed]);

    const refreshReviewQueue = useCallback(async () => {
        setQueueLoading(true);
        try {
            const [pendingPayload, confirmedPayload, dismissedPayload] = await Promise.all([
                listExplorationReviewQueue({
                    project_key: explorationFilters.projectKey,
                    severity: explorationFilters.severity,
                    review_status: 'pending',
                    limit: 20,
                }),
                listExplorationReviewQueue({
                    project_key: explorationFilters.projectKey,
                    severity: explorationFilters.severity,
                    review_status: 'confirmed',
                    limit: 20,
                }),
                listExplorationReviewQueue({
                    project_key: explorationFilters.projectKey,
                    severity: explorationFilters.severity,
                    review_status: 'dismissed',
                    limit: 20,
                }),
            ]);
            setReviewQueueFindings(pendingPayload.findings);
            setReviewQueueSummary({
                pending: pendingPayload.count,
                confirmed: confirmedPayload.count,
                dismissed: dismissedPayload.count,
            });
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load human review queue");
        } finally {
            setQueueLoading(false);
        }
    }, [explorationFilters.projectKey, explorationFilters.severity]);

    const refreshSessionDetail = useCallback(async (sessionId: string) => {
        setDetailLoading(true);
        try {
            const [sessionPayload, findingPayload] = await Promise.all([
                getExplorationSession(sessionId),
                listExplorationFindings(sessionId, {
                    severity: explorationFilters.severity,
                    review_only: explorationFilters.reviewOnly,
                    review_status: explorationFilters.reviewStatus,
                }),
            ]);
            setSessionDetail(sessionPayload);
            setFindings(findingPayload.findings);

            const hasSelectedFinding = Boolean(
                selectedFindingId && findingPayload.findings.some((item) => item.finding_id === selectedFindingId),
            );
            if (hasSelectedFinding) {
                setDeepLinkedFinding(null);
            } else if (!selectedFindingId && findingPayload.findings[0]) {
                onSelectFinding(findingPayload.findings[0].finding_id);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load exploration details");
        } finally {
            setDetailLoading(false);
        }
    }, [
        explorationFilters.reviewOnly,
        explorationFilters.reviewStatus,
        explorationFilters.severity,
        onSelectFinding,
        selectedFindingId,
    ]);

    useEffect(() => {
        void refreshSessions();
    }, [refreshSessions]);

    useEffect(() => {
        void refreshReviewQueue();
    }, [refreshReviewQueue]);

    useEffect(() => {
        if (!selectedSessionId) {
            setSessionDetail(null);
            setFindings([]);
            return;
        }
        void refreshSessionDetail(selectedSessionId);
    }, [refreshSessionDetail, selectedSessionId]);

    useEffect(() => {
        if (!selectedFindingId) {
            setDeepLinkedFinding(null);
            setReviewComment('');
            return;
        }
        if (findings.some((item) => item.finding_id === selectedFindingId)) {
            setDeepLinkedFinding(null);
            return;
        }
        let cancelled = false;
        getExplorationFinding(selectedFindingId)
            .then((finding) => {
                if (cancelled) return;
                setDeepLinkedFinding(finding);
                if (!selectedSessionId || selectedSessionId !== finding.session_id) {
                    onSelectSession(finding.session_id);
                }
            })
            .catch((err) => {
                if (cancelled) return;
                setError(err instanceof Error ? err.message : "Failed to load exploration finding details");
            });
        return () => {
            cancelled = true;
        };
    }, [findings, onSelectSession, selectedFindingId, selectedSessionId]);

    useEffect(() => {
        setReviewComment(selectedFinding?.review_comment || '');
    }, [selectedFinding?.finding_id, selectedFinding?.review_comment]);

    const summary = useMemo(() => ({
        totalSessions: sessions.length,
        highRisk: sessions.filter((item) => item.risk_score >= 0.8).length,
        pending: reviewQueueSummary.pending,
        confirmed: reviewQueueSummary.confirmed,
        dismissed: reviewQueueSummary.dismissed,
    }), [reviewQueueSummary, sessions]);

    const sessionColumns: DataTableColumn<ExplorationSession>[] = [
        {
            key: 'project_key',
            title: "Project",
            render: (_, record) => (
                <div>
                    <div className="font-medium text-slate-900 dark:text-white">{record.project_key || 'platform'}</div>
                    <div className="text-xs text-slate-400">{record.target_url}</div>
                </div>
            ),
        },
        { key: 'status', title: "Status" },
        {
            key: 'risk_score',
            title: "Risk score",
            render: (value) => Number(value || 0).toFixed(2),
        },
        {
            key: 'finding_count',
            title: "Findings",
            render: (value) => String(value || 0),
        },
        {
            key: 'human_review_count',
            title: "Human review",
            render: (value) => String(value || 0),
        },
        {
            key: 'created_at',
            title: "Created at",
            render: (value) => formatDateTime(String(value || '')),
        },
    ];

    const findingColumns: DataTableColumn<ExperienceFinding>[] = [
        {
            key: 'severity',
            title: "Severity",
            render: (value) => (
                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${SEVERITY_BADGE[String(value || 'low')] || SEVERITY_BADGE.low}`}>
                    {String(value || 'low')}
                </span>
            ),
        },
        { key: 'finding_type', title: "Type" },
        {
            key: 'review_status',
            title: "Review status",
            render: (value) => (
                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${REVIEW_BADGE[String(value || 'pending')] || REVIEW_BADGE.pending}`}>
                    {String(value || 'pending')}
                </span>
            ),
        },
        {
            key: 'title',
            title: "Finding",
            render: (_, record) => (
                <div>
                    <div className="font-medium text-slate-900 dark:text-white">{record.title}</div>
                    <div className="text-xs text-slate-400">{record.summary}</div>
                </div>
            ),
        },
    ];

    const handleLaunch = async () => {
        if (!draft.targetUrl.trim() || !draft.charter.trim()) {
            setError("Enter a target URL and exploration charter first.");
            return;
        }
        setLaunching(true);
        setError('');
        try {
            const payload = await executeCommand(
                'exploration.session.create',
                {
                    project_key: draft.projectKey.trim(),
                    group_id: draft.groupId.trim(),
                    target_url: draft.targetUrl.trim(),
                    charter: draft.charter.trim(),
                },
            );
            const result = payload.result as { session?: ExplorationSession } | null;
            const nextSessionId = result?.session?.session_id || null;
            const nextRunId = payload.run.run_id || null;
            if (onSelectRunAndSession) {
                onSelectRunAndSession({
                    runId: nextRunId,
                    sessionId: nextSessionId,
                    findingId: null,
                });
            } else {
                if (nextSessionId) {
                    onSelectSession(nextSessionId);
                }
                onSelectRun(nextRunId);
            }
            setLaunchOpen(false);
            setDraft((prev) => ({
                ...prev,
                groupId: '',
                targetUrl: '',
                charter: '',
            }));
            await Promise.all([refreshSessions(), refreshReviewQueue()]);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to start exploration session");
        } finally {
            setLaunching(false);
        }
    };

    const handleReview = async (decision: 'confirmed' | 'dismissed') => {
        if (!selectedFinding) {
            setError("Select an exploration finding to process first.");
            return;
        }
        setReviewing(decision);
        setError('');
        try {
            const payload = await executeCommand(
                'exploration.finding.review',
                {
                    finding_id: selectedFinding.finding_id,
                    decision,
                    comment: reviewComment.trim(),
                },
            );
            const result = payload.result as { finding?: ExperienceFinding } | null;
            const updatedFinding = result?.finding;
            if (updatedFinding) {
                setFindings((prev) => prev.map((item) => (
                    item.finding_id === updatedFinding.finding_id ? updatedFinding : item
                )));
                setDeepLinkedFinding(updatedFinding);
                onSelectFinding(updatedFinding.finding_id);
                setReviewComment(updatedFinding.review_comment || '');
            }
            await Promise.all([
                refreshReviewQueue(),
                selectedSessionId ? refreshSessionDetail(selectedSessionId) : Promise.resolve(),
            ]);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to submit human review");
        } finally {
            setReviewing('');
        }
    };

    const handleReturnToControl = () => {
        if (!selectedFinding) return;
        if (onUpdateSelection) {
            onUpdateSelection({
                tab: 'control',
                sessionId: selectedFinding.session_id,
                findingId: selectedFinding.finding_id,
            });
            return;
        }
        onSelectSession(selectedFinding.session_id);
        onSelectFinding(selectedFinding.finding_id);
    };

    return (
        <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <SummaryCard label={"Exploration sessions"} value={String(summary.totalSessions)} hint={"Number of exploratory testing sessions in the current query scope"} icon={<Compass className="h-5 w-5" />} />
                <SummaryCard label={"High-risk sessions"} value={String(summary.highRisk)} hint={"Priority exploration sessions with a risk score of at least 0.8"} icon={<AlertTriangle className="h-5 w-5" />} />
                <SummaryCard label={"Pending review"} value={String(summary.pending)} hint={"Exploration findings that require human attention and remain pending"} icon={<Eye className="h-5 w-5" />} />
                <SummaryCard label={"Confirmed / Rejected"} value={`${summary.confirmed} / ${summary.dismissed}`} hint={"Latest conclusions for findings reviewed by a person"} icon={<CheckCircle2 className="h-5 w-5" />} />
            </div>

            {error && (
                <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-200">
                    {error}
                </div>
            )}

            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <div className="text-lg font-semibold text-slate-900 dark:text-white">Exploration sessions</div>
                        <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">Start an exploratory testing session from a test charter to produce structured findings and evidence packages.</div>
                    </div>
                    <button
                        type="button"
                        onClick={() => setLaunchOpen(true)}
                        className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                    >
                        <Sparkles className="h-4 w-4" />
                        Start exploration session
                    </button>
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-5">
                    <label className="text-sm text-slate-600 dark:text-slate-300">
                        Filter projects
                        <input
                            value={explorationFilters.projectKey}
                            onChange={(event) => setExplorationFilters({ projectKey: event.target.value })}
                            placeholder="demo"
                            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                        />
                    </label>
                    <label className="text-sm text-slate-600 dark:text-slate-300">
                        Session status
                        <select
                            value={explorationFilters.status}
                            onChange={(event) => setExplorationFilters({ status: event.target.value })}
                            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                        >
                            <option value="">All statuses</option>
                            {['completed', 'stopped'].map((status) => (
                                <option key={status} value={status}>{status}</option>
                            ))}
                        </select>
                    </label>
                    <label className="text-sm text-slate-600 dark:text-slate-300">
                        Severity
                        <select
                            value={explorationFilters.severity}
                            onChange={(event) => setExplorationFilters({ severity: event.target.value })}
                            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                        >
                            <option value="">All levels</option>
                            {['low', 'medium', 'high', 'critical'].map((severity) => (
                                <option key={severity} value={severity}>{severity}</option>
                            ))}
                        </select>
                    </label>
                    <label className="text-sm text-slate-600 dark:text-slate-300">
                        Review status
                        <select
                            value={explorationFilters.reviewStatus}
                            onChange={(event) => setExplorationFilters({ reviewStatus: event.target.value })}
                            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                        >
                            <option value="">All statuses</option>
                            {['pending', 'confirmed', 'dismissed'].map((status) => (
                                <option key={status} value={status}>{status}</option>
                            ))}
                        </select>
                    </label>
                    <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-300">
                        <input
                            type="checkbox"
                            checked={explorationFilters.reviewOnly}
                            onChange={(event) => setExplorationFilters({ reviewOnly: event.target.checked })}
                        />
                        Human review only
                    </label>
                </div>

                <div className="mt-5 grid gap-5 xl:grid-cols-[1.1fr_1fr]">
                    <DataTable
                        columns={sessionColumns}
                        data={sessions}
                        rowKey="session_id"
                        loading={loading}
                        emptyText={"No exploration sessions yet"}
                        activeRowKey={selectedSessionId}
                        onRowClick={(record) => onSelectSession(record.session_id)}
                    />

                    <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4 dark:border-slate-700 dark:bg-slate-950/50">
                        <div className="flex items-center justify-between">
                            <div className="text-base font-semibold text-slate-900 dark:text-white">Session details</div>
                            {detailLoading && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
                        </div>
                        {!sessionDetail ? (
                            <div className="mt-4 text-sm text-slate-500 dark:text-slate-400">Select an exploration session to view its charter, risk summary, and current findings.</div>
                        ) : (
                            <div className="mt-4 space-y-4 text-sm text-slate-600 dark:text-slate-300">
                                <div className="space-y-2">
                                    <div className="font-medium text-slate-900 dark:text-white">{sessionDetail.target_url}</div>
                                    <div>Project: {sessionDetail.project_key || 'platform'}</div>
                                    <div>Charter: {sessionDetail.charter}</div>
                                    <div>Risk score: {sessionDetail.risk_score.toFixed(2)}</div>
                                    <div>Created at: {formatDateTime(sessionDetail.created_at)}</div>
                                </div>
                                <div>
                                    <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Summary</div>
                                    <pre className="mt-2 overflow-auto rounded-xl bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(sessionDetail.summary, null, 2)}</pre>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                        <div className="text-lg font-semibold text-slate-900 dark:text-white">Exploration findings and human review</div>
                        <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">Each finding includes evidence, impact scope, and AI confidence. Review it to record a final conclusion.</div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        {selectedSessionId && (
                            <div className="rounded-xl bg-slate-100 px-3 py-2 text-sm text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                                Current session: {selectedSessionId}
                            </div>
                        )}
                        {selectedFindingId && (
                            <div className="rounded-xl bg-slate-100 px-3 py-2 text-sm text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                                Current finding: {selectedFindingId}
                            </div>
                        )}
                    </div>
                </div>

                <div className="mt-4 grid gap-4 md:grid-cols-3">
                    <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 dark:border-amber-900/40 dark:bg-amber-950/20">
                        <div className="text-xs uppercase tracking-[0.18em] text-amber-700/70 dark:text-amber-200/70">Pending review queue</div>
                        <div className="mt-2 text-2xl font-semibold text-amber-800 dark:text-amber-100">{summary.pending}</div>
                        <div className="mt-2 text-sm text-amber-800/80 dark:text-amber-200/80">Findings that require human confirmation before a final judgment is recorded.</div>
                    </div>
                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 dark:border-emerald-900/40 dark:bg-emerald-950/20">
                        <div className="text-xs uppercase tracking-[0.18em] text-emerald-700/70 dark:text-emerald-200/70">Confirmed</div>
                        <div className="mt-2 text-2xl font-semibold text-emerald-800 dark:text-emerald-100">{summary.confirmed}</div>
                        <div className="mt-2 text-sm text-emerald-800/80 dark:text-emerald-200/80">Issues and risks retained after human confirmation.</div>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 dark:border-slate-700 dark:bg-slate-950/60">
                        <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Rejected</div>
                        <div className="mt-2 text-2xl font-semibold text-slate-900 dark:text-white">{summary.dismissed}</div>
                        <div className="mt-2 text-sm text-slate-500 dark:text-slate-400">Findings that a reviewer determined need no further action.</div>
                    </div>
                </div>

                <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50/80 p-4 dark:border-slate-700 dark:bg-slate-950/50">
                    <div className="flex items-center justify-between">
                        <div className="text-sm font-medium text-slate-900 dark:text-white">Pending review queue</div>
                        {queueLoading && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
                    </div>
                    <div className="mt-3 space-y-2">
                        {reviewQueueFindings.length === 0 ? (
                            <div className="text-sm text-slate-500 dark:text-slate-400">No exploration findings await review in the current scope.</div>
                        ) : reviewQueueFindings.slice(0, 5).map((finding) => (
                            <button
                                key={finding.finding_id}
                                type="button"
                                onClick={() => {
                                    onSelectSession(finding.session_id);
                                    onSelectFinding(finding.finding_id);
                                }}
                                className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-left transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:hover:bg-slate-800"
                            >
                                <div className="flex flex-wrap items-center gap-2">
                                    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${SEVERITY_BADGE[finding.severity] || SEVERITY_BADGE.low}`}>
                                        {finding.severity}
                                    </span>
                                    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${REVIEW_BADGE[finding.review_status] || REVIEW_BADGE.pending}`}>
                                        {finding.review_status}
                                    </span>
                                    <span className="text-xs text-slate-400">{finding.session_id}</span>
                                </div>
                                <div className="mt-2 font-medium text-slate-900 dark:text-white">{finding.title}</div>
                                <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">{finding.summary}</div>
                            </button>
                        ))}
                    </div>
                </div>

                <div className="mt-5 grid gap-5 xl:grid-cols-[1.2fr_1fr]">
                    <DataTable
                        columns={findingColumns}
                        data={findings}
                        rowKey="finding_id"
                        loading={detailLoading}
                        emptyText={"No exploration findings yet"}
                        activeRowKey={selectedFindingId}
                        onRowClick={(record) => onSelectFinding(record.finding_id)}
                    />

                    <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4 dark:border-slate-700 dark:bg-slate-950/50">
                        <div className="text-base font-semibold text-slate-900 dark:text-white">Finding details</div>
                        {!selectedFinding ? (
                            <div className="mt-4 text-sm text-slate-500 dark:text-slate-400">Select a finding to view evidence, reproduction steps, impact scope, and review actions.</div>
                        ) : (
                            <div className="mt-4 space-y-4">
                                <div className="space-y-2 text-sm text-slate-600 dark:text-slate-300">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${SEVERITY_BADGE[selectedFinding.severity] || SEVERITY_BADGE.low}`}>
                                            {selectedFinding.severity}
                                        </span>
                                        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${REVIEW_BADGE[selectedFinding.review_status] || REVIEW_BADGE.pending}`}>
                                            {selectedFinding.review_status}
                                        </span>
                                        {selectedFinding.requires_human_review && (
                                            <span className="inline-flex rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-700 dark:bg-amber-500/10 dark:text-amber-200">
                                                Human review required
                                            </span>
                                        )}
                                    </div>
                                    <div className="font-medium text-slate-900 dark:text-white">{selectedFinding.title}</div>
                                    <div>{selectedFinding.summary}</div>
                                    <div>Type: {selectedFinding.finding_type}</div>
                                    <div>Confidence: {selectedFinding.confidence.toFixed(2)}</div>
                                    <div>Reviewer: {selectedFinding.reviewed_by || '-'}</div>
                                    <div>Reviewed at: {formatDateTime(selectedFinding.reviewed_at)}</div>
                                    <div>Review notes: {selectedFinding.review_comment || '-'}</div>
                                </div>
                                <div>
                                    <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Reproduction steps</div>
                                    <div className="mt-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
                                        {Array.isArray(selectedFinding.evidence?.reproduction_steps)
                                            ? (selectedFinding.evidence.reproduction_steps as unknown[]).map((item, index) => (
                                                <div key={`${selectedFinding.finding_id}-step-${index}`}>{index + 1}. {String(item)}</div>
                                            ))
                                            : "No reproduction steps"}
                                    </div>
                                </div>
                                <div className="grid gap-4 md:grid-cols-2">
                                    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
                                        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Impact scope</div>
                                        <div className="mt-2">{String(selectedFinding.evidence?.impact_scope || '-')}</div>
                                    </div>
                                    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
                                        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">AI confidence</div>
                                        <div className="mt-2">{String(selectedFinding.evidence?.ai_confidence ?? selectedFinding.confidence)}</div>
                                    </div>
                                </div>
                                <div>
                                    <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Evidence package</div>
                                    <pre className="mt-2 overflow-auto rounded-xl bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(selectedFinding.evidence, null, 2)}</pre>
                                </div>
                                <label className="block text-sm text-slate-600 dark:text-slate-300">
                                    Review notes
                                    <textarea
                                        value={reviewComment}
                                        onChange={(event) => setReviewComment(event.target.value)}
                                        rows={4}
                                        placeholder={"Optional: add confirmation evidence, rejection reasons, or follow-up suggestions"}
                                        className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                    />
                                </label>
                                <div className="flex flex-wrap items-center gap-3">
                                    <button
                                        type="button"
                                        onClick={() => void handleReview('confirmed')}
                                        disabled={reviewing !== ''}
                                        className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-emerald-500 disabled:opacity-50"
                                    >
                                        {reviewing === 'confirmed' ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                                        Confirm issue
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => void handleReview('dismissed')}
                                        disabled={reviewing !== ''}
                                        className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                                    >
                                        {reviewing === 'dismissed' ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
                                        Reject issue
                                    </button>
                                    {selectedFinding.review_status !== 'pending' && (
                                        <button
                                            type="button"
                                            onClick={handleReturnToControl}
                                            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                                        >
                                            <AlertTriangle className="h-4 w-4" />
                                            Return to the control center to regenerate the release risk assessment
                                        </button>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </section>

            {launchOpen && (
                <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/50 px-4">
                    <div className="w-full max-w-2xl rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-700 dark:bg-slate-900">
                        <div className="flex items-center justify-between">
                            <div>
                                <div className="text-lg font-semibold text-slate-900 dark:text-white">Start exploration session</div>
                                <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">Submitting creates a new exploration command run through the command gateway and automatically adds structured findings.</div>
                            </div>
                            <button
                                type="button"
                                onClick={() => setLaunchOpen(false)}
                                className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                            >
                                Close
                            </button>
                        </div>
                        <div className="mt-5 grid gap-4">
                            <label className="text-sm text-slate-600 dark:text-slate-300">
                                Project identifier
                                <input
                                    value={draft.projectKey}
                                    onChange={(event) => setDraft((prev) => ({ ...prev, projectKey: event.target.value }))}
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                />
                            </label>
                            <label className="text-sm text-slate-600 dark:text-slate-300">
                                Execution group
                                <input
                                    value={draft.groupId}
                                    onChange={(event) => setDraft((prev) => ({ ...prev, groupId: event.target.value }))}
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                />
                            </label>
                            <label className="text-sm text-slate-600 dark:text-slate-300">
                                Target URL
                                <input
                                    value={draft.targetUrl}
                                    onChange={(event) => setDraft((prev) => ({ ...prev, targetUrl: event.target.value }))}
                                    placeholder="https://demo.example.com/login"
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                />
                            </label>
                            <label className="text-sm text-slate-600 dark:text-slate-300">
                                Exploration charter
                                <textarea
                                    value={draft.charter}
                                    onChange={(event) => setDraft((prev) => ({ ...prev, charter: event.target.value }))}
                                    rows={5}
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                                />
                            </label>
                        </div>
                        <div className="mt-6 flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-300">
                            <div className="flex items-center gap-2">
                                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                                Exploration results are automatically saved as structured evidence and added to the human review queue.
                            </div>
                            <button
                                type="button"
                                onClick={() => void handleLaunch()}
                                disabled={launching}
                                className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                            >
                                {launching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                                Submit exploration command
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
