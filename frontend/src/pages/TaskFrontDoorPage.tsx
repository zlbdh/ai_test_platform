import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PageHeader from '../components/ui/PageHeader';
import Badge from '../components/ui/Badge';
import {
    Compass,
    History,
    Play,
    RefreshCw,
    Sparkles,
} from '../components/icons';
import { createFrontdoorTask, listFrontdoorTasks, type FrontdoorTaskKind } from '../services/frontdoorTaskService';
import { useFrontdoorTaskStore } from '../stores';
import { getTaskKindMeta, statusMeta, TASK_KIND_OPTIONS } from './frontdoorTaskShared';

function buildTaskPayload(draft: ReturnType<typeof useFrontdoorTaskStore.getState>['draft']) {
    if (draft.taskKind === 'prototype') {
        return {
            task_kind: draft.taskKind,
            user_goal: draft.userGoal,
            source_context: {
                source_type: draft.sourceType,
                source: draft.source,
                compare_source: draft.compareSource,
                playbook_id: draft.playbookId,
            },
            strategy: { wcag_level: 'AA' },
        };
    }

    if (draft.taskKind === 'exploration') {
        return {
            task_kind: draft.taskKind,
            user_goal: draft.userGoal,
            source_context: { target_url: draft.targetUrl },
            strategy: { max_steps: 20, planner_mode: 'smart' },
        };
    }

    return {
        task_kind: draft.taskKind,
        user_goal: draft.userGoal,
        source_context: { target_url: draft.targetUrl },
        strategy: { parallel: true },
    };
}

const TaskFrontDoorPage: React.FC = () => {
    const navigate = useNavigate();
    const {
        draft,
        tasks,
        filters,
        setDraft,
        setTasks,
        setCurrentTask,
        setCurrentTaskId,
        setFilters,
    } = useFrontdoorTaskStore();
    const [loading, setLoading] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    const currentKindMeta = useMemo(() => getTaskKindMeta(draft.taskKind), [draft.taskKind]);

    const loadTasks = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            const next = await listFrontdoorTasks({
                limit: 12,
                taskKind: filters.taskKind,
                status: filters.status,
            });
            setTasks(next);
        } catch (err) {
            setError(`Failed to load recent tasks: ${err}`);
        } finally {
            setLoading(false);
        }
    }, [filters.status, filters.taskKind, setTasks]);

    useEffect(() => {
        void loadTasks();
    }, [loadTasks]);

    const handleSubmit = useCallback(async () => {
        setError('');
        if (!draft.userGoal.trim()) {
            setError("Enter a task objective first.");
            return;
        }
        if (draft.taskKind === 'prototype' && !draft.source.trim()) {
            setError("Prototype testing requires a prototype source.");
            return;
        }
        if (draft.taskKind === 'exploration' && !draft.targetUrl.trim()) {
            setError("Exploratory testing requires a target URL.");
            return;
        }

        setSubmitting(true);
        try {
            const created = await createFrontdoorTask(buildTaskPayload(draft));
            setCurrentTask(created);
            setCurrentTaskId(created.task_id);
            await loadTasks();
            navigate(`/tasks/${created.task_id}`);
        } catch (err) {
            setError(`Failed to create task: ${err}`);
        } finally {
            setSubmitting(false);
        }
    }, [draft, loadTasks, navigate, setCurrentTask, setCurrentTaskId]);

    const openTask = useCallback((taskId: string) => {
        const selected = tasks.find((task) => task.task_id === taskId) ?? null;
        if (selected) setCurrentTask(selected);
        setCurrentTaskId(taskId);
        navigate(`/tasks/${taskId}`);
    }, [navigate, setCurrentTask, setCurrentTaskId, tasks]);

    return (
        <div className="mx-auto max-w-6xl space-y-6">
            <PageHeader
                icon={<Sparkles className="h-5 w-5" />}
                title={"Unified testing entry point"}
                description={"Start general orchestration, prototype testing, or exploratory testing here, then open the unified results page or a specialized workbench for further investigation."}
                accent="violet"
                actions={(
                    <button
                        type="button"
                        onClick={() => void loadTasks()}
                        className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-500 transition-colors hover:text-violet-500 dark:border-slate-700"
                    >
                        <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                        Refresh recent tasks
                    </button>
                )}
            />

            <section className="grid gap-6 xl:grid-cols-[1.15fr,0.85fr]">
                <div className="space-y-4 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                    <div className="grid gap-3 md:grid-cols-3">
                        {TASK_KIND_OPTIONS.map((option) => {
                            const active = option.kind === draft.taskKind;
                            return (
                                <button
                                    key={option.kind}
                                    type="button"
                                    onClick={() => setDraft({ taskKind: option.kind })}
                                    className={`rounded-2xl border px-4 py-4 text-left transition-colors ${
                                        active
                                            ? 'border-violet-300 bg-violet-50/60 dark:border-violet-500/40 dark:bg-violet-500/10'
                                            : 'border-slate-200 dark:border-slate-700'
                                    }`}
                                >
                                    <div className="flex items-center justify-between gap-3">
                                        <div className="text-sm font-semibold text-slate-700 dark:text-slate-100">{option.title}</div>
                                        {active && <Badge variant="info" size="sm">Current</Badge>}
                                    </div>
                                    <div className="mt-2 text-xs leading-5 text-slate-500 dark:text-slate-400">{option.description}</div>
                                </button>
                            );
                        })}
                    </div>

                    <div className="grid gap-4 lg:grid-cols-[1.2fr,0.8fr]">
                        <div className="space-y-4">
                            <div className="space-y-2">
                                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">Task objective</label>
                                <textarea
                                    value={draft.userGoal}
                                    onChange={(event) => setDraft({ userGoal: event.target.value })}
                                    rows={5}
                                    placeholder={currentKindMeta.placeholder}
                                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:ring-2 focus:ring-violet-500/30 dark:border-slate-700 dark:bg-slate-800"
                                />
                            </div>

                            {(draft.taskKind === 'general' || draft.taskKind === 'exploration') && (
                                <div className="space-y-2">
                                    <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">{currentKindMeta.targetLabel}</label>
                                    <input
                                        value={draft.targetUrl}
                                        onChange={(event) => setDraft({ targetUrl: event.target.value })}
                                        placeholder="https://example.com/path"
                                        className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:ring-2 focus:ring-violet-500/30 dark:border-slate-700 dark:bg-slate-800"
                                    />
                                </div>
                            )}

                            {draft.taskKind === 'prototype' && (
                                <div className="space-y-3">
                                    <div className="grid gap-3 md:grid-cols-2">
                                        <select
                                            value={draft.sourceType}
                                            onChange={(event) => setDraft({ sourceType: event.target.value as 'url' | 'file' | 'directory' })}
                                            className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:ring-2 focus:ring-violet-500/30 dark:border-slate-700 dark:bg-slate-800"
                                        >
                                            <option value="url">URL</option>
                                            <option value="file">File</option>
                                            <option value="directory">Directory</option>
                                        </select>
                                        <input
                                            value={draft.playbookId}
                                            onChange={(event) => setDraft({ playbookId: event.target.value })}
                                            placeholder={"Project package ID"}
                                            className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:ring-2 focus:ring-violet-500/30 dark:border-slate-700 dark:bg-slate-800"
                                        />
                                    </div>
                                    <input
                                        value={draft.source}
                                        onChange={(event) => setDraft({ source: event.target.value })}
                                        placeholder={draft.sourceType === 'directory' ? 'D:\\path\\to\\prototype' : draft.sourceType === 'file' ? 'D:\\path\\to\\index.html' : 'https://example.com'}
                                        className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:ring-2 focus:ring-violet-500/30 dark:border-slate-700 dark:bg-slate-800"
                                    />
                                    <input
                                        value={draft.compareSource}
                                        onChange={(event) => setDraft({ compareSource: event.target.value })}
                                        placeholder={"Comparison source (optional)"}
                                        className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:ring-2 focus:ring-violet-500/30 dark:border-slate-700 dark:bg-slate-800"
                                    />
                                </div>
                            )}

                            {error && (
                                <div className="rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-600 dark:bg-red-500/10 dark:text-red-400">
                                    {error}
                                </div>
                            )}

                            <button
                                type="button"
                                onClick={() => void handleSubmit()}
                                disabled={submitting}
                                className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-violet-500 to-indigo-500 px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
                            >
                                {submitting ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                                Start task and open results
                            </button>
                        </div>

                        <div className="space-y-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 p-4 dark:border-slate-700 dark:bg-slate-800/40">
                            <div>
                                <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">Current task type</div>
                                <div className="mt-2 text-lg font-semibold text-slate-800 dark:text-white">{currentKindMeta.title}</div>
                                <div className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">{currentKindMeta.description}</div>
                            </div>

                            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4 dark:border-slate-700 dark:bg-slate-900">
                                <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
                                    <Compass className="h-4 w-4 text-teal-500" />
                                    The results page always includes
                                </div>
                                <ul className="mt-3 space-y-2 text-sm text-slate-500 dark:text-slate-400">
                                    <li>Task intent and input context</li>
                                    <li>Execution strategy and current status</li>
                                    <li>Live logs and key evidence</li>
                                    <li>Findings and gate decision</li>
                                    <li>Recommended next steps and expert tools</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="space-y-4 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
                            <History className="h-4 w-4 text-slate-400" />
                            Recent tasks
                        </div>
                        <div className="flex gap-2">
                            <select
                                value={filters.taskKind}
                                onChange={(event) => setFilters({ taskKind: event.target.value as FrontdoorTaskKind | '' })}
                                className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs outline-none transition focus:ring-2 focus:ring-violet-500/30 dark:border-slate-700 dark:bg-slate-800"
                            >
                                <option value="">All types</option>
                                {TASK_KIND_OPTIONS.map((option) => (
                                    <option key={option.kind} value={option.kind}>{option.title}</option>
                                ))}
                            </select>
                            <select
                                value={filters.status}
                                onChange={(event) => setFilters({ status: event.target.value })}
                                className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs outline-none transition focus:ring-2 focus:ring-violet-500/30 dark:border-slate-700 dark:bg-slate-800"
                            >
                                <option value="">All statuses</option>
                                <option value="pending">Running</option>
                                <option value="completed">Completed</option>
                                <option value="failed">Failed</option>
                                <option value="cancelled">Stopped</option>
                            </select>
                        </div>
                    </div>

                    <div className="space-y-3">
                        {tasks.length === 0 ? (
                            <div className="rounded-2xl border border-dashed border-slate-200 px-4 py-10 text-center text-sm text-slate-400 dark:border-slate-700">
                                No unified tasks match the current filters
                            </div>
                        ) : tasks.map((task) => {
                            const taskMeta = getTaskKindMeta(task.task_kind);
                            const meta = statusMeta(task.status);
                            return (
                                <button
                                    key={task.task_id}
                                    type="button"
                                    onClick={() => openTask(task.task_id)}
                                    className="w-full rounded-2xl border border-slate-200 px-4 py-4 text-left transition-colors hover:border-violet-300 hover:bg-violet-50/40 dark:border-slate-700 dark:hover:border-violet-500/40 dark:hover:bg-violet-500/10"
                                >
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="min-w-0">
                                            <div className="truncate text-sm font-semibold text-slate-700 dark:text-slate-100">{task.user_goal}</div>
                                            <div className="mt-1 text-xs text-slate-400">{taskMeta.title} · {task.task_id}</div>
                                        </div>
                                        <Badge variant={meta.variant} size="sm" dot>{meta.label}</Badge>
                                    </div>
                                    <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-slate-500 dark:text-slate-400">
                                        <div>
                                            <div className="text-[10px] uppercase tracking-wider text-slate-400">Findings</div>
                                            <div className="mt-1 font-medium text-slate-700 dark:text-slate-200">{task.evidence_summary.finding_count}</div>
                                        </div>
                                        <div>
                                            <div className="text-[10px] uppercase tracking-wider text-slate-400">Gate</div>
                                            <div className="mt-1 font-medium text-slate-700 dark:text-slate-200">{task.gate_summary.status}</div>
                                        </div>
                                        <div>
                                            <div className="text-[10px] uppercase tracking-wider text-slate-400">Logs</div>
                                            <div className="mt-1 font-medium text-slate-700 dark:text-slate-200">{task.evidence_summary.log_count}</div>
                                        </div>
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                </div>
            </section>
        </div>
    );
};

export default TaskFrontDoorPage;
