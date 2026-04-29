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
            setError(`加载任务详情失败：${err}`);
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
            setError(`停止任务失败：${err}`);
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
            setError(`重新运行失败：${err}`);
        } finally {
            setActionLoading('');
        }
    }, [navigate, setCurrentTask, setCurrentTaskId, taskId]);

    if (loading && !selectedTask) {
        return (
            <div className="mx-auto flex min-h-[60vh] max-w-4xl items-center justify-center">
                <div className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900">
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    正在加载任务结果…
                </div>
            </div>
        );
    }

    if (!selectedTask) {
        return (
            <div className="mx-auto max-w-4xl space-y-4">
                <PageHeader
                    icon={<Sparkles className="h-5 w-5" />}
                    title="统一任务结果"
                    description="任务不存在、尚未加载完成，或者当前页面已失去上下文。"
                    accent="violet"
                />
                <div className="rounded-3xl border border-dashed border-slate-200 bg-white px-6 py-12 text-center text-sm text-slate-400 dark:border-slate-700 dark:bg-slate-900">
                    {error || '没有找到对应任务，请从统一测试前门重新进入。'}
                </div>
            </div>
        );
    }

    return (
        <div className="mx-auto max-w-7xl space-y-6">
            <PageHeader
                icon={<Sparkles className="h-5 w-5" />}
                title={`${taskMeta.title}结果`}
                description="统一结果页固定展示任务意图、执行状态、证据、Findings、Gate 和下一步建议。"
                accent="violet"
                actions={(
                    <>
                        <button
                            type="button"
                            onClick={() => void loadTask(selectedTask.task_id)}
                            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-500 transition-colors hover:text-violet-500 dark:border-slate-700"
                        >
                            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                            刷新
                        </button>
                        {running && (
                            <button
                                type="button"
                                onClick={() => void handleCancel()}
                                disabled={actionLoading === 'cancel'}
                                className="inline-flex items-center gap-2 rounded-lg border border-amber-200 px-3 py-2 text-sm text-amber-600 transition-colors hover:bg-amber-50 disabled:opacity-50 dark:border-amber-500/30 dark:hover:bg-amber-500/10"
                            >
                                {actionLoading === 'cancel' ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Pause className="h-4 w-4" />}
                                停止任务
                            </button>
                        )}
                        <button
                            type="button"
                            onClick={() => void handleRerun()}
                            disabled={actionLoading === 'rerun'}
                            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-500 transition-colors hover:text-violet-500 disabled:opacity-50 dark:border-slate-700"
                        >
                            {actionLoading === 'rerun' ? <RefreshCw className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
                            重新运行
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
                            <div className="font-semibold">当前上下文无法证明</div>
                            <div className="mt-1 leading-6">
                                本任务包含 `static_unprovable` 指标，说明仍有静态原型、当前环境或当前会话无法直接证明的点，它不等于“通过”。
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
                                    <span>执行组：{selectedTask.execution_group_id || '-'}</span>
                                    <span>复跑链：{selectedTask.lineage_root_id || '-'}</span>
                                    {selectedTask.rerun_from_task_id && (
                                        <span>来自复跑：{selectedTask.rerun_from_task_id}</span>
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
                                    执行中心
                                </button>
                                <button
                                    type="button"
                                    onClick={() => navigate(selectedTask.quality_gate_path)}
                                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-500 transition-colors hover:text-violet-500 dark:border-slate-700"
                                >
                                    <ShieldAlert className="h-4 w-4" />
                                    质量门禁
                                </button>
                                <button
                                    type="button"
                                    onClick={() => navigate(selectedTask.expert_path)}
                                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-500 transition-colors hover:text-violet-500 dark:border-slate-700"
                                >
                                    <ExternalLink className="h-4 w-4" />
                                    专家深挖
                                </button>
                            </div>
                        </div>
                    </section>

                    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                        <div className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-200">1. 任务意图与输入上下文</div>
                        <div className="grid gap-4 md:grid-cols-2">
                            <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
                                <div className="text-xs uppercase tracking-wider text-slate-400">任务意图</div>
                                <div className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">{selectedTask.user_goal}</div>
                            </div>
                            <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
                                <div className="text-xs uppercase tracking-wider text-slate-400">输入上下文</div>
                                <div className="mt-3 space-y-2">
                                    {Object.entries(selectedTask.source_context || {}).length === 0 ? (
                                        <div className="text-sm text-slate-400">当前任务没有额外上下文字段</div>
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
                        <div className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-200">2. 执行策略与当前状态</div>
                        <div className="grid gap-4 lg:grid-cols-[0.9fr,1.1fr]">
                            <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
                                <div className="grid grid-cols-2 gap-3 text-sm">
                                    <div>
                                        <div className="text-xs uppercase tracking-wider text-slate-400">创建时间</div>
                                        <div className="mt-1 text-slate-700 dark:text-slate-200">{formatTimestamp(selectedTask.created_at)}</div>
                                    </div>
                                    <div>
                                        <div className="text-xs uppercase tracking-wider text-slate-400">开始时间</div>
                                        <div className="mt-1 text-slate-700 dark:text-slate-200">{formatTimestamp(selectedTask.started_at)}</div>
                                    </div>
                                    <div>
                                        <div className="text-xs uppercase tracking-wider text-slate-400">结束时间</div>
                                        <div className="mt-1 text-slate-700 dark:text-slate-200">{formatTimestamp(selectedTask.completed_at)}</div>
                                    </div>
                                    <div>
                                        <div className="text-xs uppercase tracking-wider text-slate-400">日志流</div>
                                        <div className="mt-1 text-slate-700 dark:text-slate-200">{streamConnected ? '已连接' : '未连接'}</div>
                                    </div>
                                </div>
                            </div>
                            <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
                                <div className="text-xs uppercase tracking-wider text-slate-400">执行策略 / Agent 状态</div>
                                <div className="mt-3 grid gap-3 md:grid-cols-2">
                                    <div className="rounded-xl bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                        <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">策略</div>
                                        <div className="mt-2 space-y-1.5">
                                            {Object.entries(selectedTask.strategy || {}).length === 0 ? (
                                                <div className="text-sm text-slate-400">未设置额外策略</div>
                                            ) : Object.entries(selectedTask.strategy || {}).map(([key, value]) => (
                                                <div key={key} className="flex items-start justify-between gap-3 text-sm">
                                                    <span className="text-slate-400">{key}</span>
                                                    <span className="break-all text-right text-slate-700 dark:text-slate-200">{formatMetricValue(value)}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="rounded-xl bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                        <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">Agent 状态</div>
                                        <div className="mt-2 space-y-2">
                                            {Object.entries(selectedTask.agent_states || {}).length === 0 ? (
                                                <div className="text-sm text-slate-400">当前没有 agent 状态</div>
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
                        <div className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-200">3. 实时 / 历史日志时间线</div>
                        <div className="overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-700">
                            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 dark:border-slate-700">
                                <div className="text-sm text-slate-600 dark:text-slate-300">统一日志流</div>
                                {running && <Badge variant="warning" dot>持续更新中</Badge>}
                            </div>
                            <div className="max-h-[360px] overflow-y-auto bg-slate-950 px-4 py-3 font-mono text-xs text-slate-300">
                                {(selectedTask.logs || []).length === 0 ? (
                                    <div className="py-8 text-center text-slate-500">当前任务还没有日志</div>
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
                        <div className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-200">4. 关键证据与 Findings</div>
                        <div className="grid gap-4 lg:grid-cols-[0.8fr,1.2fr]">
                            <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
                                <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
                                    <Activity className="h-4 w-4 text-sky-500" />
                                    证据摘要
                                </div>
                                <div className="mt-4 grid grid-cols-2 gap-3">
                                    <div className="rounded-xl bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                        <div className="text-xs uppercase tracking-wider text-slate-400">日志</div>
                                        <div className="mt-1 text-lg font-semibold text-slate-800 dark:text-white">{selectedTask.evidence_summary.log_count}</div>
                                    </div>
                                    <div className="rounded-xl bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                        <div className="text-xs uppercase tracking-wider text-slate-400">Findings</div>
                                        <div className="mt-1 text-lg font-semibold text-slate-800 dark:text-white">{selectedTask.evidence_summary.finding_count}</div>
                                    </div>
                                    <div className="rounded-xl bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                        <div className="text-xs uppercase tracking-wider text-slate-400">报告</div>
                                        <div className="mt-1 text-lg font-semibold text-slate-800 dark:text-white">{selectedTask.evidence_summary.has_report ? '已生成' : '暂无'}</div>
                                    </div>
                                    <div className="rounded-xl bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                        <div className="text-xs uppercase tracking-wider text-slate-400">执行组</div>
                                        <div className="mt-1 text-sm font-semibold text-slate-800 dark:text-white">{selectedTask.execution_group_id}</div>
                                    </div>
                                </div>
                                <div className="mt-4 space-y-2 text-xs text-slate-400">
                                    <div>摘要字段：{(selectedTask.evidence_summary.summary_keys || []).join('、') || '无'}</div>
                                    <div>证据标识：{(selectedTask.evidence_summary.evidence_ids || []).join('、') || '无'}</div>
                                    <div>最新日志：{formatTimestamp(selectedTask.evidence_summary.latest_log_at || '')}</div>
                                    <div>静态无法证明项：{selectedTask.evidence_summary.static_unprovable_count ?? 0}</div>
                                </div>
                            </div>
                            <div className="space-y-3">
                                {(selectedTask.findings || []).length === 0 ? (
                                    <div className="rounded-2xl border border-dashed border-slate-200 px-4 py-10 text-center text-sm text-slate-400 dark:border-slate-700">
                                        当前任务没有 Findings
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
                                                <div>证据：{finding.evidence_id || '无'}</div>
                                                <div>来源：{finding.source_type || '未知'}</div>
                                                <div>定位：{finding.locator || '无'}</div>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    </section>

                    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                        <div className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-200">5. Gate 结论与核心指标</div>
                        <div className="grid gap-4 lg:grid-cols-[0.85fr,1.15fr]">
                            <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
                                <div className="flex items-center gap-2">
                                    <ShieldAlert className="h-4 w-4 text-amber-500" />
                                    <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">Gate 结论</div>
                                    <Badge variant={gateInfo.variant}>{selectedTask.gate_summary.status}</Badge>
                                </div>
                                <div className="mt-3 text-sm leading-6 text-slate-500 dark:text-slate-400">{selectedTask.gate_summary.summary}</div>
                                <div className="mt-3 rounded-xl bg-slate-50 px-3 py-3 text-xs leading-6 text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
                                    结论原因：{selectedTask.gate_summary.decision_reason || '当前没有结构化决策原因。'}
                                </div>
                            </div>
                            <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
                                <div className="text-xs uppercase tracking-wider text-slate-400">核心 Metrics</div>
                                <div className="mt-3 grid gap-2 md:grid-cols-2">
                                    {Object.entries(selectedTask.gate_summary.metrics || {}).length === 0 ? (
                                        <div className="text-sm text-slate-400">当前没有可展示的 metrics</div>
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
                        <div className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-200">6. 下一步建议与深挖入口</div>
                        <div className="grid gap-4 lg:grid-cols-[1fr,0.9fr]">
                            <div className="space-y-3">
                                {(selectedTask.recommendations || []).length === 0 ? (
                                    <div className="rounded-2xl border border-dashed border-slate-200 px-4 py-8 text-sm text-slate-400 dark:border-slate-700">
                                        当前任务没有额外建议
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
                                        <div className="text-sm font-semibold text-slate-700 dark:text-slate-100">进入执行中心</div>
                                        <div className="mt-1 text-xs text-slate-400">查看同执行组记录、历史与回放</div>
                                    </div>
                                    <History className="h-4 w-4 text-slate-400" />
                                </button>
                                <button
                                    type="button"
                                    onClick={() => navigate(selectedTask.quality_gate_path)}
                                    className="flex w-full items-center justify-between rounded-2xl border border-slate-200 px-4 py-4 text-left transition-colors hover:border-violet-300 hover:bg-violet-50/40 dark:border-slate-700 dark:hover:border-violet-500/40 dark:hover:bg-violet-500/10"
                                >
                                    <div>
                                        <div className="text-sm font-semibold text-slate-700 dark:text-slate-100">进入质量门禁</div>
                                        <div className="mt-1 text-xs text-slate-400">按当前任务上下文查看门禁结论与历史</div>
                                    </div>
                                    <ShieldAlert className="h-4 w-4 text-slate-400" />
                                </button>
                                <button
                                    type="button"
                                    onClick={() => navigate(selectedTask.expert_path)}
                                    className="flex w-full items-center justify-between rounded-2xl border border-slate-200 px-4 py-4 text-left transition-colors hover:border-violet-300 hover:bg-violet-50/40 dark:border-slate-700 dark:hover:border-violet-500/40 dark:hover:bg-violet-500/10"
                                >
                                    <div>
                                        <div className="text-sm font-semibold text-slate-700 dark:text-slate-100">进入专家深挖页</div>
                                        <div className="mt-1 text-xs text-slate-400">在保持主链语境的前提下，进入对应专项页继续深挖</div>
                                    </div>
                                    <ExternalLink className="h-4 w-4 text-slate-400" />
                                </button>

                                <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
                                    <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
                                        <Compass className="h-4 w-4 text-teal-500" />
                                        同类任务参考
                                    </div>
                                    <div className="mt-3 space-y-2">
                                        {sameTaskKindReferences.length === 0 ? (
                                            <div className="text-sm text-slate-400">当前没有可参考的同类任务</div>
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
                                        复跑链摘要
                                    </div>
                                    <div className="mt-3 space-y-2 text-xs text-slate-400">
                                        <div>链根任务：{selectedTask.lineage_root_id || '无'}</div>
                                        <div>当前来源：{selectedTask.rerun_from_task_id || '首次运行'}</div>
                                    </div>
                                    <div className="mt-3 space-y-2">
                                        {lineageContext.sortedTasks.length === 0 ? (
                                            <div className="text-sm text-slate-400">当前没有同链路任务</div>
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
                                                        {task.rerun_from_task_id ? ` · 来自 ${task.rerun_from_task_id}` : ' · 首次运行'}
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
                                        最近复跑对比
                                    </div>
                                    {!comparableTask || !comparisonSummary ? (
                                        <div className="mt-3 text-sm text-slate-400">当前还没有可比的历史复跑任务。</div>
                                    ) : (
                                        <div className="mt-3 space-y-3">
                                            <div className="rounded-xl bg-slate-50 px-3 py-3 text-xs text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
                                                对比对象：{comparableTask.task_id} · {statusMeta(comparableTask.status).label} · {formatTimestamp(comparableTask.completed_at || comparableTask.created_at)}
                                            </div>
                                            <div className="grid gap-2">
                                                <div className="flex items-start justify-between gap-3 rounded-xl bg-slate-50 px-3 py-3 text-sm dark:bg-slate-800/60">
                                                    <span className="text-slate-400">Findings 数量</span>
                                                    <span className="text-right text-slate-700 dark:text-slate-200">
                                                        本次 {comparisonSummary.currentFindingCount} / 上次 {comparisonSummary.comparableFindingCount}
                                                        {comparisonSummary.findingDelta !== 0 && ` (${comparisonSummary.findingDelta > 0 ? '+' : ''}${comparisonSummary.findingDelta})`}
                                                    </span>
                                                </div>
                                                <div className="flex items-start justify-between gap-3 rounded-xl bg-slate-50 px-3 py-3 text-sm dark:bg-slate-800/60">
                                                    <span className="text-slate-400">高风险 Findings</span>
                                                    <span className="text-right text-slate-700 dark:text-slate-200">
                                                        本次 {comparisonSummary.currentSeveritySummary.blocking + comparisonSummary.currentSeveritySummary.major} / 上次 {comparisonSummary.comparableSeveritySummary.blocking + comparisonSummary.comparableSeveritySummary.major}
                                                        {comparisonSummary.highRiskDelta !== 0 && ` (${comparisonSummary.highRiskDelta > 0 ? '+' : ''}${comparisonSummary.highRiskDelta})`}
                                                    </span>
                                                </div>
                                                <div className="rounded-xl bg-slate-50 px-3 py-3 text-sm dark:bg-slate-800/60">
                                                    <div className="text-slate-400">严重级别变化</div>
                                                    <div className="mt-2 text-slate-700 dark:text-slate-200">本次：{formatFindingSeveritySummary(comparisonSummary.currentSeveritySummary)}</div>
                                                    <div className="mt-1 text-slate-500 dark:text-slate-400">上次：{formatFindingSeveritySummary(comparisonSummary.comparableSeveritySummary)}</div>
                                                </div>
                                                <div className="flex items-start justify-between gap-3 rounded-xl bg-slate-50 px-3 py-3 text-sm dark:bg-slate-800/60">
                                                    <span className="text-slate-400">Gate 状态</span>
                                                    <span className="text-right text-slate-700 dark:text-slate-200">
                                                        本次 {selectedTask.gate_summary.status} / 上次 {comparableTask.gate_summary.status}
                                                    </span>
                                                </div>
                                                <div className="flex items-start justify-between gap-3 rounded-xl bg-slate-50 px-3 py-3 text-sm dark:bg-slate-800/60">
                                                    <span className="text-slate-400">验证态</span>
                                                    <span className="text-right text-slate-700 dark:text-slate-200">
                                                        本次 {verificationInfo.label} / 上次 {verificationStateMeta(comparableTask.verification_state).label}
                                                    </span>
                                                </div>
                                                <div className="rounded-xl bg-slate-50 px-3 py-3 text-sm dark:bg-slate-800/60">
                                                    <div className="text-slate-400">判定原因变化</div>
                                                    <div className="mt-2 text-slate-700 dark:text-slate-200">本次：{selectedTask.gate_summary.decision_reason || '当前没有结构化决策原因。'}</div>
                                                    <div className="mt-1 text-slate-500 dark:text-slate-400">上次：{comparableTask.gate_summary.decision_reason || '上次没有结构化决策原因。'}</div>
                                                    {!comparisonSummary.decisionReasonChanged && (
                                                        <div className="mt-2 text-xs text-slate-400">本次与上次的结构化判定原因一致。</div>
                                                    )}
                                                </div>
                                                <div className="rounded-xl bg-slate-50 px-3 py-3 text-sm dark:bg-slate-800/60">
                                                    <div className="flex items-center justify-between gap-3">
                                                        <div className="text-slate-400">关键 Metrics 变化</div>
                                                        <div className="text-xs text-slate-400">
                                                            {comparisonSummary.changedMetricCount > 0
                                                                ? `${comparisonSummary.changedMetricCount} 项变化`
                                                                : '与上次一致'}
                                                        </div>
                                                    </div>
                                                    <div className="mt-2 space-y-2">
                                                        {comparisonSummary.metricChanges.length === 0 ? (
                                                            <div className="text-xs text-slate-400">当前没有可对比的 metrics。</div>
                                                        ) : comparisonSummary.metricChanges.slice(0, 6).map((metric) => (
                                                            <div key={metric.key} className="rounded-lg border border-slate-200/70 bg-white px-3 py-3 dark:border-slate-700/70 dark:bg-slate-900/40">
                                                                <div className="flex items-center justify-between gap-3">
                                                                    <div className="text-xs text-slate-400">{metric.key}</div>
                                                                    {metric.changed ? (
                                                                        <Badge variant="warning" size="sm">已变化</Badge>
                                                                    ) : (
                                                                        <Badge variant="neutral" size="sm">一致</Badge>
                                                                    )}
                                                                </div>
                                                                <div className="mt-2 text-slate-700 dark:text-slate-200">
                                                                    本次：{formatMetricValue(metric.currentValue)}
                                                                </div>
                                                                <div className="mt-1 text-slate-500 dark:text-slate-400">
                                                                    上次：{formatMetricValue(metric.comparableValue)}
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
                        <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">结果摘要</div>
                        <div className="mt-4 space-y-2">
                            {Object.entries(selectedTask.result_summary || {}).length === 0 ? (
                                <div className="text-sm text-slate-400">当前没有结构化结果摘要</div>
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
