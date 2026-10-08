import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import PageHeader from '../components/ui/PageHeader';
import Badge from '../components/ui/Badge';
import {
    Activity,
    AlertTriangle,
    Compass,
    ExternalLink,
    History,
    Pause,
    RefreshCw,
    RotateCcw,
    ShieldAlert,
    Sparkles,
} from '../components/icons';
import {
    cancelFrontdoorTask,
    getFrontdoorTask,
    listFrontdoorTasks,
    rerunFrontdoorTask,
    streamFrontdoorTask,
    type FrontdoorTask,
} from '../services/frontdoorTaskService';
import type { MissionLog } from '../services/commanderService';
import { useFrontdoorTaskStore } from '../stores';
import {
    buildFrontdoorDeepView,
    formatFindingSeveritySummary,
    formatMetricValue,
    formatTimestamp,
    gateMeta,
    getTaskKindMeta,
    hasStaticUnprovable,
    isRunningStatus,
    statusMeta,
    verificationStateMeta,
} from './frontdoorTaskShared';

function mergeLogs(base: MissionLog[], incoming: MissionLog[]): MissionLog[] {
    const merged = [...base];
    incoming.forEach((item) => {
        const exists = merged.some((log) => (
            log.timestamp === item.timestamp
            && log.message === item.message
            && log.level === item.level
        ));
        if (!exists) merged.push(item);
    });
    return merged.sort((a, b) => String(a.timestamp).localeCompare(String(b.timestamp)));
}

function logLevelStyle(level: string): string {
    const normalized = String(level || '').toLowerCase();
    if (normalized === 'error') return 'text-red-400';
    if (normalized === 'warn' || normalized === 'warning') return 'text-amber-400';
    return 'text-sky-400';
}

const TaskResultPage: React.FC = () => {
    const { taskId = '' } = useParams();
    const navigate = useNavigate();
    const {
        currentTask,
        setCurrentTask,
        setCurrentTaskId,
        setStreamConnected,
        streamConnected,
    } = useFrontdoorTaskStore();
    const [loading, setLoading] = useState(Boolean(taskId));
    const [actionLoading, setActionLoading] = useState<'cancel' | 'rerun' | ''>('');
    const [error, setError] = useState('');
    const [actionMessage, setActionMessage] = useState('');
    const [relatedTasks, setRelatedTasks] = useState<FrontdoorTask[]>([]);
    const [lineageTasks, setLineageTasks] = useState<FrontdoorTask[]>([]);

    const selectedTask = currentTask?.task_id === taskId ? currentTask : null;
    const running = isRunningStatus(selectedTask?.status || '');
    const taskMeta = useMemo(() => getTaskKindMeta(selectedTask?.task_kind || 'general'), [selectedTask?.task_kind]);
    const statusInfo = useMemo(() => statusMeta(selectedTask?.status || ''), [selectedTask?.status]);
    const gateInfo = useMemo(() => gateMeta(selectedTask?.gate_summary?.status || ''), [selectedTask?.gate_summary?.status]);
    const verificationInfo = useMemo(() => verificationStateMeta(selectedTask?.verification_state), [selectedTask?.verification_state]);
    const staticUnprovable = useMemo(() => hasStaticUnprovable(selectedTask?.gate_summary), [selectedTask?.gate_summary]);
    const deepView = useMemo(
        () => buildFrontdoorDeepView({
            currentTask: selectedTask,
            currentTaskId: taskId,
            lineageTasks,
            sameTaskKindTasks: relatedTasks,
            maxSameTaskKindReferences: 4,
        }),
        [lineageTasks, relatedTasks, selectedTask, taskId],
    );
    const { lineageContext, comparableTask, comparisonSummary, sameTaskKindReferences } = deepView;

    const loadTask = useCallback(async (id: string) => {
        if (!id) return;
        setLoading(true);
        setError('');
        try {
            const detail = await getFrontdoorTask(id);
            setCurrentTask(detail);
            setCurrentTaskId(detail.task_id);
        } catch (err) {
            setError(`Failed to load task details: ${err}`);
        } finally {
            setLoading(false);
        }
    }, [setCurrentTask, setCurrentTaskId]);

    const loadRelatedTasks = useCallback(async (task?: FrontdoorTask | null) => {
        if (!task?.task_kind) {
            setRelatedTasks([]);
            return;
        }
        try {
            const related = await listFrontdoorTasks({
                limit: 6,
                taskKind: task.task_kind,
            });
            setRelatedTasks(related);
        } catch {
            setRelatedTasks([]);
        }
    }, []);

    const loadLineageTasks = useCallback(async (task?: FrontdoorTask | null) => {
        if (!task?.lineage_root_id) {
            setLineageTasks([]);
            return;
        }
        try {
            const related = await listFrontdoorTasks({
                limit: 10,
                lineageRootId: task.lineage_root_id,
            });
            setLineageTasks(related);
        } catch {
            setLineageTasks([]);
        }
    }, []);

    useEffect(() => {
        if (!taskId) return;
        void loadTask(taskId);
    }, [loadTask, taskId]);

    useEffect(() => {
        if (!selectedTask) return;
        void loadRelatedTasks(selectedTask);
        void loadLineageTasks(selectedTask);
    }, [loadLineageTasks, loadRelatedTasks, selectedTask]);

    useEffect(() => {
        if (!taskId || !running) return undefined;
        const timer = window.setInterval(() => {
            void loadTask(taskId);
        }, 3000);
        return () => window.clearInterval(timer);
    }, [loadTask, running, taskId]);

    useEffect(() => {
        if (!taskId || !running) {
            setStreamConnected(false);
            return undefined;
        }
        setStreamConnected(true);
        const close = streamFrontdoorTask(
            taskId,
            (log) => {
                setCurrentTask((prev) => {
                    if (!prev || prev.task_id !== taskId) return prev;
                    return { ...prev, logs: mergeLogs(prev.logs || [], [log]) };
                });
            },
            () => {
                setStreamConnected(false);
                void loadTask(taskId);
            },
        );
        return () => {
            setStreamConnected(false);
            close();
        };
    }, [loadTask, running, setCurrentTask, setStreamConnected, taskId]);

    const handleCancel = useCallback(async () => {
        if (!taskId) return;
        setActionLoading('cancel');
        setActionMessage('');
        setError('');
        try {
            const result = await cancelFrontdoorTask(taskId);
            setActionMessage(result.message);
            await loadTask(taskId);
        } catch (err) {
            setError(`Failed to stop task: ${err}`);
        } finally {
            setActionLoading('');
        }
    }, [loadTask, taskId]);

    const handleRerun = useCallback(async () => {
        if (!taskId) return;
        setActionLoading('rerun');
        setActionMessage('');
        setError('');
        try {
            const rerunTask = await rerunFrontdoorTask(taskId);
            setCurrentTask(rerunTask);
            setCurrentTaskId(rerunTask.task_id);
            navigate(`/tasks/${rerunTask.task_id}`);
        } catch (err) {
            setError(`Failed to rerun task: ${err}`);
        } finally {
            setActionLoading('');
        }
    }, [navigate, setCurrentTask, setCurrentTaskId, taskId]);

    if (loading && !selectedTask) {
        return (
            <div className="mx-auto flex min-h-[60vh] max-w-4xl items-center justify-center">
                <div className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900">
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    Loading task results…
                </div>
            </div>
        );
    }

    if (!selectedTask) {
        return (
            <div className="mx-auto max-w-4xl space-y-4">
                <PageHeader
                    icon={<Sparkles className="h-5 w-5" />}
                    title={"Unified task results"}
                    description={"The task does not exist, has not finished loading, or the page context is no longer available."}
                    accent="violet"
                />
                <div className="rounded-3xl border border-dashed border-slate-200 bg-white px-6 py-12 text-center text-sm text-slate-400 dark:border-slate-700 dark:bg-slate-900">
                    {error || "No matching task was found. Return to the unified testing entry point."}
                </div>
            </div>
        );
    }

    return (
        <div className="mx-auto max-w-7xl space-y-6">
            <PageHeader
                icon={<Sparkles className="h-5 w-5" />}
                title={`${taskMeta.title}Result`}
                description={"The unified results page always shows task intent, execution status, evidence, findings, gate decisions, and next steps."}
                accent="violet"
                actions={(
                    <>
                        <button
                            type="button"
                            onClick={() => void loadTask(selectedTask.task_id)}
                            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-500 transition-colors hover:text-violet-500 dark:border-slate-700"
                        >
                            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                            Refresh
                        </button>
                        {running && (
                            <button
                                type="button"
                                onClick={() => void handleCancel()}
                                disabled={actionLoading === 'cancel'}
                                className="inline-flex items-center gap-2 rounded-lg border border-amber-200 px-3 py-2 text-sm text-amber-600 transition-colors hover:bg-amber-50 disabled:opacity-50 dark:border-amber-500/30 dark:hover:bg-amber-500/10"
                            >
                                {actionLoading === 'cancel' ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Pause className="h-4 w-4" />}
                                Stop task
                            </button>
                        )}
                        <button
                            type="button"
                            onClick={() => void handleRerun()}
                            disabled={actionLoading === 'rerun'}
                            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-500 transition-colors hover:text-violet-500 disabled:opacity-50 dark:border-slate-700"
                        >
                            {actionLoading === 'rerun' ? <RefreshCw className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
                            Rerun
                        </button>
                    </>
                )}
            />

            {error && (
                <div className="rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-600 dark:bg-red-500/10 dark:text-red-400">
                    {error}
                </div>
            )}

            {actionMessage && (
                <div className="rounded-2xl bg-slate-100 px-4 py-3 text-sm text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                    {actionMessage}
                </div>
            )}

            {staticUnprovable && (
                <div className="rounded-2xl border border-amber-200 bg-amber-50/80 px-4 py-4 text-sm text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300">
                    <div className="flex items-start gap-3">
                        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                        <div>
                            <div className="font-semibold">Not provable in the current context</div>
                            <div className="mt-1 leading-6">
                                This task includes `static_unprovable` metrics: some points cannot be proven directly from a static prototype, the current environment, or the current session. This does not mean they passed.
                            </div>
                        </div>
                    </div>
                </div>
            )}

            <div className={`rounded-2xl px-4 py-4 text-sm ${
                verificationInfo.variant === 'success'
                    ? 'border border-emerald-200 bg-emerald-50/80 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300'
                    : verificationInfo.variant === 'error'
                        ? 'border border-rose-200 bg-rose-50/80 text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300'
                        : verificationInfo.variant === 'warning'
                            ? 'border border-amber-200 bg-amber-50/80 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300'
                            : 'border border-slate-200 bg-slate-50/80 text-slate-700 dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-300'
            }`}>
                <div className="font-semibold">{verificationInfo.label}</div>
                <div className="mt-1 leading-6">{verificationInfo.summary}</div>
            </div>

            <div className="grid gap-6 xl:grid-cols-[1.3fr,0.7fr]">
                <div className="space-y-6">
                    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                        <div className="flex flex-wrap items-start justify-between gap-4">
                            <div>
                                <div className="flex items-center gap-2">
                                    <div className="text-xl font-semibold text-slate-800 dark:text-white">{selectedTask.user_goal}</div>
                                    <Badge variant={statusInfo.variant} dot>{statusInfo.label}</Badge>
                                    <Badge variant={gateInfo.variant}>{gateInfo.label}</Badge>
                                </div>
                                <div className="mt-2 text-xs text-slate-400">{selectedTask.task_kind} · {selectedTask.task_id}</div>
                                <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-400">
                                    <span>Execution group: {selectedTask.execution_group_id || '-'}</span>
                                    <span>Rerun chain: {selectedTask.lineage_root_id || '-'}</span>
                                    {selectedTask.rerun_from_task_id && (
                                        <span>Rerun of: {selectedTask.rerun_from_task_id}</span>
                                    )}
                                </div>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                <button
                                    type="button"
                                    onClick={() => navigate(selectedTask.execution_center_path)}
                                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-500 transition-colors hover:text-violet-500 dark:border-slate-700"
                                >
                                    <History className="h-4 w-4" />
                                    Execution center
                                </button>
                                <button
                                    type="button"
                                    onClick={() => navigate(selectedTask.quality_gate_path)}
                                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-500 transition-colors hover:text-violet-500 dark:border-slate-700"
                                >
                                    <ShieldAlert className="h-4 w-4" />
                                    Quality gate
                                </button>
                                <button
                                    type="button"
                                    onClick={() => navigate(selectedTask.expert_path)}
                                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-500 transition-colors hover:text-violet-500 dark:border-slate-700"
                                >
                                    <ExternalLink className="h-4 w-4" />
                                    Expert investigation
                                </button>
                            </div>
                        </div>
                    </section>

                    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                        <div className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-200">1. Task intent and input context</div>
                        <div className="grid gap-4 md:grid-cols-2">
                            <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
                                <div className="text-xs uppercase tracking-wider text-slate-400">Task intent</div>
                                <div className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">{selectedTask.user_goal}</div>
                            </div>
                            <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
                                <div className="text-xs uppercase tracking-wider text-slate-400">Input context</div>
                                <div className="mt-3 space-y-2">
                                    {Object.entries(selectedTask.source_context || {}).length === 0 ? (
                                        <div className="text-sm text-slate-400">This task has no additional context fields</div>
                                    ) : Object.entries(selectedTask.source_context || {}).map(([key, value]) => (
                                        <div key={key} className="flex items-start justify-between gap-3 text-sm">
                                            <span className="text-slate-400">{key}</span>
                                            <span className="break-all text-right text-slate-700 dark:text-slate-200">{formatMetricValue(value)}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </section>

                    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                        <div className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-200">2. Execution strategy and current status</div>
                        <div className="grid gap-4 lg:grid-cols-[0.9fr,1.1fr]">
                            <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
                                <div className="grid grid-cols-2 gap-3 text-sm">
                                    <div>
                                        <div className="text-xs uppercase tracking-wider text-slate-400">Created at</div>
                                        <div className="mt-1 text-slate-700 dark:text-slate-200">{formatTimestamp(selectedTask.created_at)}</div>
                                    </div>
                                    <div>
                                        <div className="text-xs uppercase tracking-wider text-slate-400">Start time</div>
                                        <div className="mt-1 text-slate-700 dark:text-slate-200">{formatTimestamp(selectedTask.started_at)}</div>
                                    </div>
                                    <div>
                                        <div className="text-xs uppercase tracking-wider text-slate-400">End time</div>
                                        <div className="mt-1 text-slate-700 dark:text-slate-200">{formatTimestamp(selectedTask.completed_at)}</div>
                                    </div>
                                    <div>
                                        <div className="text-xs uppercase tracking-wider text-slate-400">Log stream</div>
                                        <div className="mt-1 text-slate-700 dark:text-slate-200">{streamConnected ? "Connected" : "Disconnected"}</div>
                                    </div>
                                </div>
                            </div>
                            <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
                                <div className="text-xs uppercase tracking-wider text-slate-400">Execution strategy / agent status</div>
                                <div className="mt-3 grid gap-3 md:grid-cols-2">
                                    <div className="rounded-xl bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                        <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">Strategy</div>
                                        <div className="mt-2 space-y-1.5">
                                            {Object.entries(selectedTask.strategy || {}).length === 0 ? (
                                                <div className="text-sm text-slate-400">No additional strategy configured</div>
                                            ) : Object.entries(selectedTask.strategy || {}).map(([key, value]) => (
                                                <div key={key} className="flex items-start justify-between gap-3 text-sm">
                                                    <span className="text-slate-400">{key}</span>
                                                    <span className="break-all text-right text-slate-700 dark:text-slate-200">{formatMetricValue(value)}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="rounded-xl bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                        <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">Agent status</div>
                                        <div className="mt-2 space-y-2">
                                            {Object.entries(selectedTask.agent_states || {}).length === 0 ? (
                                                <div className="text-sm text-slate-400">No agent status available</div>
                                            ) : Object.entries(selectedTask.agent_states || {}).map(([key, value]) => (
                                                <div key={key} className="flex items-center justify-between gap-3">
                                                    <span className="text-sm text-slate-500 dark:text-slate-400">{key}</span>
                                                    <Badge variant={statusMeta(String(value)).variant} size="sm">{String(value)}</Badge>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </section>

                    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                        <div className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-200">3. Live and historical log timeline</div>
                        <div className="overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-700">
                            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 dark:border-slate-700">
                                <div className="text-sm text-slate-600 dark:text-slate-300">Unified log stream</div>
                                {running && <Badge variant="warning" dot>Updating continuously</Badge>}
                            </div>
                            <div className="max-h-[360px] overflow-y-auto bg-slate-950 px-4 py-3 font-mono text-xs text-slate-300">
                                {(selectedTask.logs || []).length === 0 ? (
                                    <div className="py-8 text-center text-slate-500">This task has no logs yet</div>
                                ) : (
                                    <div className="space-y-1.5">
                                        {(selectedTask.logs || []).map((log, index) => (
                                            <div key={`${log.timestamp}-${index}`} className="grid grid-cols-[160px,64px,1fr] gap-3">
                                                <span className="text-slate-500">{formatTimestamp(log.timestamp)}</span>
                                                <span className={logLevelStyle(log.level)}>{log.level}</span>
                                                <span>{log.message}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    </section>

                    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                        <div className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-200">4. Key evidence and findings</div>
                        <div className="grid gap-4 lg:grid-cols-[0.8fr,1.2fr]">
                            <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
                                <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
                                    <Activity className="h-4 w-4 text-sky-500" />
                                    Evidence summary
                                </div>
                                <div className="mt-4 grid grid-cols-2 gap-3">
                                    <div className="rounded-xl bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                        <div className="text-xs uppercase tracking-wider text-slate-400">Logs</div>
                                        <div className="mt-1 text-lg font-semibold text-slate-800 dark:text-white">{selectedTask.evidence_summary.log_count}</div>
                                    </div>
                                    <div className="rounded-xl bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                        <div className="text-xs uppercase tracking-wider text-slate-400">Findings</div>
                                        <div className="mt-1 text-lg font-semibold text-slate-800 dark:text-white">{selectedTask.evidence_summary.finding_count}</div>
                                    </div>
                                    <div className="rounded-xl bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                        <div className="text-xs uppercase tracking-wider text-slate-400">Report</div>
                                        <div className="mt-1 text-lg font-semibold text-slate-800 dark:text-white">{selectedTask.evidence_summary.has_report ? "Generated" : "None"}</div>
                                    </div>
                                    <div className="rounded-xl bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                        <div className="text-xs uppercase tracking-wider text-slate-400">Execution group</div>
                                        <div className="mt-1 text-sm font-semibold text-slate-800 dark:text-white">{selectedTask.execution_group_id}</div>
                                    </div>
                                </div>
                                <div className="mt-4 space-y-2 text-xs text-slate-400">
                                    <div>Summary fields: {(selectedTask.evidence_summary.summary_keys || []).join('、') || "None"}</div>
                                    <div>Evidence identifiers: {(selectedTask.evidence_summary.evidence_ids || []).join('、') || "None"}</div>
                                    <div>Latest log: {formatTimestamp(selectedTask.evidence_summary.latest_log_at || '')}</div>
                                    <div>Statically unprovable items: {selectedTask.evidence_summary.static_unprovable_count ?? 0}</div>
                                </div>
                            </div>
                            <div className="space-y-3">
                                {(selectedTask.findings || []).length === 0 ? (
                                    <div className="rounded-2xl border border-dashed border-slate-200 px-4 py-10 text-center text-sm text-slate-400 dark:border-slate-700">
                                        This task has no findings
                                    </div>
                                ) : (
                                    (selectedTask.findings || []).map((finding) => (
                                        <div key={finding.finding_id || `${finding.title}-${finding.summary}`} className="rounded-2xl border border-slate-200 px-4 py-4 dark:border-slate-700">
                                            <div className="flex items-start justify-between gap-3">
                                                <div>
                                                    <div className="text-sm font-semibold text-slate-700 dark:text-slate-100">{finding.title}</div>
                                                    <div className="mt-1 text-xs text-slate-400">{finding.category} · {finding.agent_id}</div>
                                                </div>
                                                <Badge variant={finding.severity === 'blocking' ? 'error' : finding.severity === 'major' ? 'warning' : 'info'} size="sm">
                                                    {finding.severity}
                                                </Badge>
                                            </div>
                                            <div className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">{finding.summary}</div>
                                            <div className="mt-3 grid gap-2 text-xs text-slate-400 md:grid-cols-3">
                                                <div>Evidence: {finding.evidence_id || "None"}</div>
                                                <div>Source: {finding.source_type || "Unknown"}</div>
                                                <div>Location: {finding.locator || "None"}</div>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    </section>

                    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                        <div className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-200">5. Gate decision and core metrics</div>
                        <div className="grid gap-4 lg:grid-cols-[0.85fr,1.15fr]">
                            <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
                                <div className="flex items-center gap-2">
                                    <ShieldAlert className="h-4 w-4 text-amber-500" />
                                    <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">Gate decision</div>
                                    <Badge variant={gateInfo.variant}>{selectedTask.gate_summary.status}</Badge>
                                </div>
                                <div className="mt-3 text-sm leading-6 text-slate-500 dark:text-slate-400">{selectedTask.gate_summary.summary}</div>
                                <div className="mt-3 rounded-xl bg-slate-50 px-3 py-3 text-xs leading-6 text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
                                    Decision reason: {selectedTask.gate_summary.decision_reason || "No structured decision reasons for this run."}
                                </div>
                            </div>
                            <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
                                <div className="text-xs uppercase tracking-wider text-slate-400">Core metrics</div>
                                <div className="mt-3 grid gap-2 md:grid-cols-2">
                                    {Object.entries(selectedTask.gate_summary.metrics || {}).length === 0 ? (
                                        <div className="text-sm text-slate-400">No metrics available</div>
                                    ) : Object.entries(selectedTask.gate_summary.metrics || {}).map(([key, value]) => (
                                        <div key={key} className="flex items-start justify-between gap-3 rounded-xl bg-slate-50 px-3 py-3 text-sm dark:bg-slate-800/60">
                                            <span className="text-slate-400">{key}</span>
                                            <span className="break-all text-right text-slate-700 dark:text-slate-200">{formatMetricValue(value)}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </section>

                    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                        <div className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-200">6. Recommended next steps and investigation tools</div>
                        <div className="grid gap-4 lg:grid-cols-[1fr,0.9fr]">
                            <div className="space-y-3">
                                {(selectedTask.recommendations || []).length === 0 ? (
                                    <div className="rounded-2xl border border-dashed border-slate-200 px-4 py-8 text-sm text-slate-400 dark:border-slate-700">
                                        This task has no additional recommendations
                                    </div>
                                ) : (
                                    (selectedTask.recommendations || []).map((item, index) => (
                                        <div key={`${item}-${index}`} className="rounded-2xl border border-slate-200 px-4 py-4 text-sm leading-6 text-slate-600 dark:border-slate-700 dark:text-slate-300">
                                            {item}
                                        </div>
                                    ))
                                )}
                            </div>
                            <div className="space-y-3">
                                <button
                                    type="button"
                                    onClick={() => navigate(selectedTask.execution_center_path)}
                                    className="flex w-full items-center justify-between rounded-2xl border border-slate-200 px-4 py-4 text-left transition-colors hover:border-violet-300 hover:bg-violet-50/40 dark:border-slate-700 dark:hover:border-violet-500/40 dark:hover:bg-violet-500/10"
                                >
                                    <div>
                                        <div className="text-sm font-semibold text-slate-700 dark:text-slate-100">Open execution center</div>
                                        <div className="mt-1 text-xs text-slate-400">View records, history, and replays from the same execution group</div>
                                    </div>
                                    <History className="h-4 w-4 text-slate-400" />
                                </button>
                                <button
                                    type="button"
                                    onClick={() => navigate(selectedTask.quality_gate_path)}
                                    className="flex w-full items-center justify-between rounded-2xl border border-slate-200 px-4 py-4 text-left transition-colors hover:border-violet-300 hover:bg-violet-50/40 dark:border-slate-700 dark:hover:border-violet-500/40 dark:hover:bg-violet-500/10"
                                >
                                    <div>
                                        <div className="text-sm font-semibold text-slate-700 dark:text-slate-100">Open quality gates</div>
                                        <div className="mt-1 text-xs text-slate-400">View gate decisions and history in the current task context</div>
                                    </div>
                                    <ShieldAlert className="h-4 w-4 text-slate-400" />
                                </button>
                                <button
                                    type="button"
                                    onClick={() => navigate(selectedTask.expert_path)}
                                    className="flex w-full items-center justify-between rounded-2xl border border-slate-200 px-4 py-4 text-left transition-colors hover:border-violet-300 hover:bg-violet-50/40 dark:border-slate-700 dark:hover:border-violet-500/40 dark:hover:bg-violet-500/10"
                                >
                                    <div>
                                        <div className="text-sm font-semibold text-slate-700 dark:text-slate-100">Open expert investigation</div>
                                        <div className="mt-1 text-xs text-slate-400">Continue in a specialized view while preserving the main workflow context</div>
                                    </div>
                                    <ExternalLink className="h-4 w-4 text-slate-400" />
                                </button>

                                <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
                                    <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
                                        <Compass className="h-4 w-4 text-teal-500" />
                                        Similar tasks
                                    </div>
                                    <div className="mt-3 space-y-2">
                                        {sameTaskKindReferences.length === 0 ? (
                                            <div className="text-sm text-slate-400">No similar tasks available</div>
                                        ) : sameTaskKindReferences.map((task) => (
                                            <button
                                                key={task.task_id}
                                                type="button"
                                                onClick={() => navigate(`/tasks/${task.task_id}`)}
                                                className="flex w-full items-center justify-between rounded-xl bg-slate-50 px-3 py-3 text-left transition-colors hover:bg-violet-50 dark:bg-slate-800/60 dark:hover:bg-violet-500/10"
                                            >
                                                <div className="min-w-0">
                                                    <div className="truncate text-sm font-medium text-slate-700 dark:text-slate-100">{task.user_goal}</div>
                                                    <div className="mt-1 text-xs text-slate-400">{task.task_id}</div>
                                                </div>
                                                <Badge variant={statusMeta(task.status).variant} size="sm">{task.status}</Badge>
                                    </button>
                                        ))}
                                    </div>
                                </div>

                                <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
                                    <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
                                        <RotateCcw className="h-4 w-4 text-violet-500" />
                                        Rerun chain summary
                                    </div>
                                    <div className="mt-3 space-y-2 text-xs text-slate-400">
                                        <div>Root task: {selectedTask.lineage_root_id || "None"}</div>
                                        <div>Current source: {selectedTask.rerun_from_task_id || "First run"}</div>
                                    </div>
                                    <div className="mt-3 space-y-2">
                                        {lineageContext.sortedTasks.length === 0 ? (
                                            <div className="text-sm text-slate-400">No tasks in the same chain</div>
                                        ) : lineageContext.sortedTasks.slice(0, 5).map((task) => (
                                            <button
                                                key={task.task_id}
                                                type="button"
                                                onClick={() => navigate(`/tasks/${task.task_id}`)}
                                                className="flex w-full items-center justify-between rounded-xl bg-slate-50 px-3 py-3 text-left transition-colors hover:bg-violet-50 dark:bg-slate-800/60 dark:hover:bg-violet-500/10"
                                            >
                                                <div className="min-w-0">
                                                    <div className="truncate text-sm font-medium text-slate-700 dark:text-slate-100">{task.user_goal}</div>
                                                    <div className="mt-1 text-xs text-slate-400">
                                                        {task.task_id}
                                                        {task.rerun_from_task_id ? ` · From ${task.rerun_from_task_id}` : " · First run"}
                                                    </div>
                                                </div>
                                                <Badge variant={statusMeta(task.status).variant} size="sm">{task.status}</Badge>
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
                                    <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
                                        <RotateCcw className="h-4 w-4 text-amber-500" />
                                        Latest rerun comparison
                                    </div>
                                    {!comparableTask || !comparisonSummary ? (
                                        <div className="mt-3 text-sm text-slate-400">No comparable historical rerun is available yet.</div>
                                    ) : (
                                        <div className="mt-3 space-y-3">
                                            <div className="rounded-xl bg-slate-50 px-3 py-3 text-xs text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
                                                Compared with: {comparableTask.task_id} · {statusMeta(comparableTask.status).label} · {formatTimestamp(comparableTask.completed_at || comparableTask.created_at)}
                                            </div>
                                            <div className="grid gap-2">
                                                <div className="flex items-start justify-between gap-3 rounded-xl bg-slate-50 px-3 py-3 text-sm dark:bg-slate-800/60">
                                                    <span className="text-slate-400">Finding count</span>
                                                    <span className="text-right text-slate-700 dark:text-slate-200">
                                                        Current {comparisonSummary.currentFindingCount} / Previous {comparisonSummary.comparableFindingCount}
                                                        {comparisonSummary.findingDelta !== 0 && ` (${comparisonSummary.findingDelta > 0 ? '+' : ''}${comparisonSummary.findingDelta})`}
                                                    </span>
                                                </div>
                                                <div className="flex items-start justify-between gap-3 rounded-xl bg-slate-50 px-3 py-3 text-sm dark:bg-slate-800/60">
                                                    <span className="text-slate-400">High-risk findings</span>
                                                    <span className="text-right text-slate-700 dark:text-slate-200">
                                                        Current {comparisonSummary.currentSeveritySummary.blocking + comparisonSummary.currentSeveritySummary.major} / Previous {comparisonSummary.comparableSeveritySummary.blocking + comparisonSummary.comparableSeveritySummary.major}
                                                        {comparisonSummary.highRiskDelta !== 0 && ` (${comparisonSummary.highRiskDelta > 0 ? '+' : ''}${comparisonSummary.highRiskDelta})`}
                                                    </span>
                                                </div>
                                                <div className="rounded-xl bg-slate-50 px-3 py-3 text-sm dark:bg-slate-800/60">
                                                    <div className="text-slate-400">Severity changes</div>
                                                    <div className="mt-2 text-slate-700 dark:text-slate-200">Current: {formatFindingSeveritySummary(comparisonSummary.currentSeveritySummary)}</div>
                                                    <div className="mt-1 text-slate-500 dark:text-slate-400">Previous: {formatFindingSeveritySummary(comparisonSummary.comparableSeveritySummary)}</div>
                                                </div>
                                                <div className="flex items-start justify-between gap-3 rounded-xl bg-slate-50 px-3 py-3 text-sm dark:bg-slate-800/60">
                                                    <span className="text-slate-400">Gate status</span>
                                                    <span className="text-right text-slate-700 dark:text-slate-200">
                                                        Current {selectedTask.gate_summary.status} / Previous {comparableTask.gate_summary.status}
                                                    </span>
                                                </div>
                                                <div className="flex items-start justify-between gap-3 rounded-xl bg-slate-50 px-3 py-3 text-sm dark:bg-slate-800/60">
                                                    <span className="text-slate-400">Verification state</span>
                                                    <span className="text-right text-slate-700 dark:text-slate-200">
                                                        Current {verificationInfo.label} / Previous {verificationStateMeta(comparableTask.verification_state).label}
                                                    </span>
                                                </div>
                                                <div className="rounded-xl bg-slate-50 px-3 py-3 text-sm dark:bg-slate-800/60">
                                                    <div className="text-slate-400">Decision reason changes</div>
                                                    <div className="mt-2 text-slate-700 dark:text-slate-200">Current: {selectedTask.gate_summary.decision_reason || "No structured decision reasons for this run."}</div>
                                                    <div className="mt-1 text-slate-500 dark:text-slate-400">Previous: {comparableTask.gate_summary.decision_reason || "No structured decision reasons for the previous run."}</div>
                                                    {!comparisonSummary.decisionReasonChanged && (
                                                        <div className="mt-2 text-xs text-slate-400">The structured decision reason is unchanged from the previous run.</div>
                                                    )}
                                                </div>
                                                <div className="rounded-xl bg-slate-50 px-3 py-3 text-sm dark:bg-slate-800/60">
                                                    <div className="flex items-center justify-between gap-3">
                                                        <div className="text-slate-400">Key metric changes</div>
                                                        <div className="text-xs text-slate-400">
                                                            {comparisonSummary.changedMetricCount > 0
                                                                ? `${comparisonSummary.changedMetricCount} changes`
                                                                : "Unchanged from previous run"}
                                                        </div>
                                                    </div>
                                                    <div className="mt-2 space-y-2">
                                                        {comparisonSummary.metricChanges.length === 0 ? (
                                                            <div className="text-xs text-slate-400">No comparable metrics are available.</div>
                                                        ) : comparisonSummary.metricChanges.slice(0, 6).map((metric) => (
                                                            <div key={metric.key} className="rounded-lg border border-slate-200/70 bg-white px-3 py-3 dark:border-slate-700/70 dark:bg-slate-900/40">
                                                                <div className="flex items-center justify-between gap-3">
                                                                    <div className="text-xs text-slate-400">{metric.key}</div>
                                                                    {metric.changed ? (
                                                                        <Badge variant="warning" size="sm">Changed</Badge>
                                                                    ) : (
                                                                        <Badge variant="neutral" size="sm">Unchanged</Badge>
                                                                    )}
                                                                </div>
                                                                <div className="mt-2 text-slate-700 dark:text-slate-200">
                                                                    Current: {formatMetricValue(metric.currentValue)}
                                                                </div>
                                                                <div className="mt-1 text-slate-500 dark:text-slate-400">
                                                                    Previous: {formatMetricValue(metric.comparableValue)}
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </section>
                </div>

                <aside className="space-y-4">
                    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                        <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">Results summary</div>
                        <div className="mt-4 space-y-2">
                            {Object.entries(selectedTask.result_summary || {}).length === 0 ? (
                                <div className="text-sm text-slate-400">No structured results summary available</div>
                            ) : Object.entries(selectedTask.result_summary || {}).map(([key, value]) => (
                                <div key={key} className="flex items-start justify-between gap-3 rounded-xl bg-slate-50 px-3 py-3 text-sm dark:bg-slate-800/60">
                                    <span className="text-slate-400">{key}</span>
                                    <span className="break-all text-right text-slate-700 dark:text-slate-200">{formatMetricValue(value)}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </aside>
            </div>
        </div>
    );
};

export default TaskResultPage;
