import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
    Accessibility,
    Activity,
    AlertTriangle,
    CheckCircle2,
    ChevronRight,
    Clock,
    Eye,
    FileText,
    FlaskConical,
    Gauge,
    GitCompareArrows,
    Layers,
    Loader2,
    Pause,
    PlayCircle,
    RefreshCw,
    Sparkles,
    XCircle,
} from '../components/icons';
import {
    commanderCancel,
    commanderPrototypeMissions,
    commanderPrototypeRun,
    commanderPrototypeStatus,
    commanderPrototypeStream,
    type MissionLog,
    type PrototypeFinding,
    type PrototypeMissionResult,
    type PrototypeRunRequest,
    type PrototypeWorkerResult,
} from '../services/commanderService';

const DEFAULT_SWITCHES = {
    visual: true,
    flow: true,
    ab: true,
    a11y: true,
    perf: true,
};

const DEFAULT_FORM: PrototypeRunRequest = {
    source_type: 'url',
    source: '',
    compare_source: '',
    playbook_id: '',
    worker_switches: DEFAULT_SWITCHES,
    providers: {
        visual: 'local-visual-regression',
        flow: 'playwright-flow',
        ab: 'mock-chromatic',
        a11y: 'local-a11y-audit',
        perf: 'mock-lighthouse',
    },
    wcag_level: 'AA',
};

export const PROTOTYPE_AGENT_ORDER = [
    'orchestrator',
    'visual',
    'flow',
    'ab',
    'a11y',
    'perf',
    'reporter',
] as const;

type PrototypeAgentId = typeof PROTOTYPE_AGENT_ORDER[number];

const AGENT_META: Record<PrototypeAgentId, { title: string; role: string; icon: React.ReactNode }> = {
    orchestrator: {
        title: 'Orchestrator',
        role: "Task decomposition, state coordination, and worker broadcasts",
        icon: <FlaskConical className="w-4 h-4" />,
    },
    visual: {
        title: 'Visual',
        role: "Screenshots, baselines, and pixel differences",
        icon: <Eye className="w-4 h-4" />,
    },
    flow: {
        title: 'Flow',
        role: "Flow connectivity and page navigation",
        icon: <Layers className="w-4 h-4" />,
    },
    ab: {
        title: 'A/B',
        role: "Version structure differences and component changes",
        icon: <GitCompareArrows className="w-4 h-4" />,
    },
    a11y: {
        title: 'A11y',
        role: "WCAG accessibility scan",
        icon: <Accessibility className="w-4 h-4" />,
    },
    perf: {
        title: 'Perf',
        role: "Mock Lighthouse performance warnings",
        icon: <Gauge className="w-4 h-4" />,
    },
    reporter: {
        title: 'Reporter',
        role: "Severity ranking, recommendations, and gate metrics",
        icon: <FileText className="w-4 h-4" />,
    },
};

const AGENT_STATE_CLASS: Record<string, string> = {
    idle: 'border-slate-200 bg-white text-slate-500',
    running: 'border-sky-300 bg-sky-50 text-sky-700',
    success: 'border-emerald-300 bg-emerald-50 text-emerald-700',
    error: 'border-rose-300 bg-rose-50 text-rose-700',
    skipped: 'border-amber-300 bg-amber-50 text-amber-700',
};

const FINDING_TONE_CLASS: Record<string, string> = {
    blocking: 'border-rose-200 bg-rose-50 text-rose-700',
    high: 'border-orange-200 bg-orange-50 text-orange-700',
    medium: 'border-amber-200 bg-amber-50 text-amber-700',
    low: 'border-sky-200 bg-sky-50 text-sky-700',
    info: 'border-slate-200 bg-slate-100 text-slate-600',
};

function formatStatusLabel(status: string): string {
    const normalized = String(status || 'idle').toLowerCase();
    return {
        pending: "Waiting",
        parsing: "Parsing",
        dispatching: "Dispatching",
        executing: "Running",
        reporting: "Summarizing",
        completed: "Completed",
        failed: "Failed",
        cancelled: "Canceled",
        idle: "Idle",
        running: "Running",
        success: "Complete",
        error: "Error",
        skipped: "Skipped",
    }[normalized] || normalized;
}

function getStatusIcon(status: string) {
    const normalized = String(status || 'idle').toLowerCase();
    if (normalized === 'running' || normalized === 'executing' || normalized === 'reporting' || normalized === 'dispatching' || normalized === 'parsing') {
        return <Loader2 className="w-4 h-4 animate-spin" />;
    }
    if (normalized === 'success' || normalized === 'completed') {
        return <CheckCircle2 className="w-4 h-4" />;
    }
    if (normalized === 'error' || normalized === 'failed') {
        return <XCircle className="w-4 h-4" />;
    }
    if (normalized === 'skipped' || normalized === 'cancelled') {
        return <Pause className="w-4 h-4" />;
    }
    return <Clock className="w-4 h-4" />;
}

export function getPrototypeAgentNodes(mission?: PrototypeMissionResult | null) {
    const states = mission?.agent_states || {};
    return PROTOTYPE_AGENT_ORDER.map((agentId) => ({
        id: agentId,
        title: AGENT_META[agentId].title,
        role: AGENT_META[agentId].role,
        status: states[agentId] || 'idle',
    }));
}

function mergeMissionList(previous: PrototypeMissionResult[], nextMission: PrototypeMissionResult): PrototypeMissionResult[] {
    const next = [nextMission, ...previous.filter((item) => item.mission_id !== nextMission.mission_id)];
    return next.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
}

function summarizeWorkerPayload(worker: PrototypeWorkerResult): string {
    const payload = worker.payload || {};
    if (worker.agent_id === 'visual') return `diff ${String(payload.diffPercentage ?? '0')}%`;
    if (worker.agent_id === 'flow') return `${Array.isArray(payload.steps) ? payload.steps.length : 0} steps`;
    if (worker.agent_id === 'ab') return `${Array.isArray(payload.changedComponents) ? payload.changedComponents.length : 0} changed`;
    if (worker.agent_id === 'a11y') return `${Array.isArray(payload.violations) ? payload.violations.length : 0} violations`;
    if (worker.agent_id === 'perf') return `score ${String(payload.score ?? '-')}`;
    return worker.status;
}

export function buildSeveritySummary(findings: PrototypeFinding[]): string {
    if (!findings.length) return "No issues found";
    const counts = findings.reduce<Record<string, number>>((acc, item) => {
        const key = item.severity || 'info';
        acc[key] = (acc[key] || 0) + 1;
        return acc;
    }, {});
    return Object.entries(counts).map(([key, value]) => `${key}:${value}`).join(' / ');
}

function formatDateTime(value?: string | null): string {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString('en-US');
}

function isRunningMission(status?: string | null): boolean {
    return ['pending', 'parsing', 'dispatching', 'executing', 'reporting'].includes(String(status || '').toLowerCase());
}

const SOURCE_TYPE_OPTIONS: Array<{ value: PrototypeRunRequest['source_type']; label: string; helper: string }> = [
    { value: 'url', label: 'URL', helper: "Online prototype URL" },
    { value: 'file', label: "File", helper: "Local HTML file path" },
    { value: 'directory', label: "Directory", helper: "Local prototype directory" },
];

const PLAYBOOK_OPTIONS = [
    { value: '', label: "Do not inject a project package" },
    { value: 'sample-platform-prototype', label: 'sample-platform-prototype' },
];

const WCAG_OPTIONS = ['A', 'AA', 'AAA'] as const;

const PrototypeAgentsPage: React.FC = () => {
    const [form, setForm] = useState<PrototypeRunRequest>(DEFAULT_FORM);
    const [missions, setMissions] = useState<PrototypeMissionResult[]>([]);
    const [activeMissionId, setActiveMissionId] = useState<string>('');
    const [logs, setLogs] = useState<MissionLog[]>([]);
    const [rawTab, setRawTab] = useState<'report' | 'json'>('report');
    const [loadingHistory, setLoadingHistory] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const streamCleanupRef = useRef<(() => void) | null>(null);

    const activeMission = useMemo(
        () => missions.find((item) => item.mission_id === activeMissionId) || null,
        [missions, activeMissionId],
    );
    const running = ['pending', 'parsing', 'dispatching', 'executing', 'reporting'].includes(String(activeMission?.status || '').toLowerCase());
    const agentNodes = useMemo(() => getPrototypeAgentNodes(activeMission), [activeMission]);
    const findings = (activeMission?.report?.findings || []) as PrototypeFinding[];
    const workerResults = activeMission?.worker_results || [];
    const missionSummary = activeMission?.report?.summary || {};
    const qualityMetrics = activeMission?.report?.quality_gate_metrics || {};
    const sourceContext = activeMission?.source_context || {};
    const discoveredPages = Array.isArray(sourceContext.discovered_pages) ? sourceContext.discovered_pages : [];
    const playbookContext = (sourceContext.playbook_context || {}) as Record<string, unknown>;
    const criticalPages = Array.isArray(playbookContext.critical_pages) ? playbookContext.critical_pages as Array<Record<string, unknown>> : [];
    const severitySummary = buildSeveritySummary(findings);
    const missionStatusLabel = formatStatusLabel(activeMission?.status || 'idle');
    const highlightStats = [
        {
            label: "Issues found",
            value: String(missionSummary.finding_count ?? findings.length ?? 0),
            helper: severitySummary,
            icon: <AlertTriangle className="w-4 h-4" />,
        },
        {
            label: "Successful workers",
            value: `${String(missionSummary.success_workers ?? workerResults.filter(item => item.status === 'success').length)}/${String(missionSummary.total_workers ?? workerResults.length)}`,
            helper: `Skipped ${String(missionSummary.skipped_workers ?? workerResults.filter(item => item.status === 'skipped').length)}`,
            icon: <CheckCircle2 className="w-4 h-4" />,
        },
        {
            label: "Discovered pages",
            value: String(discoveredPages.length || 0),
            helper: activeMission?.source_type === 'directory' ? "Directory normalization complete" : "Entry page parsed",
            icon: <Layers className="w-4 h-4" />,
        },
        {
            label: "Gate coverage",
            value: `${Math.round(Number(qualityMetrics.module_coverage_rate || 0) * 100)}%`,
            helper: `page mapping ${Math.round(Number(qualityMetrics.page_mapping_rate || 0) * 100)}%`,
            icon: <Gauge className="w-4 h-4" />,
        },
    ];

    const cleanupStream = () => {
        streamCleanupRef.current?.();
        streamCleanupRef.current = null;
    };

    const upsertMission = (mission: PrototypeMissionResult) => {
        setMissions((previous) => mergeMissionList(previous, mission));
    };

    const loadHistory = async () => {
        setLoadingHistory(true);
        try {
            const data = await commanderPrototypeMissions(12);
            setMissions(data);
            if (!activeMissionId && data[0]?.mission_id) {
                setActiveMissionId(data[0].mission_id);
                setLogs(data[0].logs || []);
            }
        } finally {
            setLoadingHistory(false);
        }
    };

    const loadMission = async (missionId: string, attachStream = false) => {
        const mission = await commanderPrototypeStatus(missionId);
        upsertMission(mission);
        setActiveMissionId(missionId);
        setLogs(mission.logs || []);
        if (attachStream) {
            cleanupStream();
            streamCleanupRef.current = commanderPrototypeStream(
                missionId,
                (entry) => {
                    setLogs((previous) => [...previous, entry]);
                    void commanderPrototypeStatus(missionId).then((latest) => upsertMission(latest)).catch(() => {});
                },
                () => {
                    void commanderPrototypeStatus(missionId).then((latest) => upsertMission(latest)).catch(() => {});
                },
            );
        }
    };

    useEffect(() => {
        void loadHistory();
        return () => cleanupStream();
    }, []);

    useEffect(() => {
        if (!activeMissionId) return;
        if (!running) {
            cleanupStream();
            return;
        }

        const timer = window.setInterval(() => {
            void commanderPrototypeStatus(activeMissionId).then((latest) => upsertMission(latest)).catch(() => {});
        }, 4000);
        return () => window.clearInterval(timer);
    }, [activeMissionId, running]);

    const handleSubmit = async () => {
        if (!form.source.trim()) return;
        setSubmitting(true);
        try {
            const mission = await commanderPrototypeRun({
                ...form,
                source: form.source.trim(),
                compare_source: form.compare_source?.trim() || '',
            });
            upsertMission(mission);
            setActiveMissionId(mission.mission_id);
            setLogs(mission.logs || []);
            cleanupStream();
            streamCleanupRef.current = commanderPrototypeStream(
                mission.mission_id,
                (entry) => {
                    setLogs((previous) => [...previous, entry]);
                    void commanderPrototypeStatus(mission.mission_id).then((latest) => upsertMission(latest)).catch(() => {});
                },
                () => {
                    void commanderPrototypeStatus(mission.mission_id).then((latest) => upsertMission(latest)).catch(() => {});
                },
            );
        } finally {
            setSubmitting(false);
        }
    };

    const handleStop = async () => {
        if (!activeMissionId) return;
        await commanderCancel(activeMissionId);
        await loadMission(activeMissionId, false);
    };

    return (
        <div className="space-y-5">
            <section className="rounded-3xl border border-slate-200 bg-gradient-to-br from-cyan-50 via-white to-slate-50 p-5 shadow-sm">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-3">
                        <div className="inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-white/90 px-3 py-1 text-xs font-medium text-cyan-700">
                            <Sparkles className="w-4 h-4" />
                            Prototype Agents
                        </div>
                        <div>
                            <h1 className="text-2xl font-semibold text-slate-900">Seven-agent prototype testing workspace</h1>
                            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                                Enter a prototype URL, local HTML file, or directory. The orchestrator runs Visual, Flow, A/B, A11y, and Perf test workers in parallel, then Reporter combines their results into a structured report ordered by severity.
                            </p>
                        </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3 sm:min-w-[320px]">
                        {highlightStats.map((item) => (
                            <div key={item.label} className="rounded-2xl border border-white bg-white/90 p-4 shadow-sm">
                                <div className="flex items-center justify-between text-slate-500">
                                    <span className="text-xs font-medium">{item.label}</span>
                                    <span>{item.icon}</span>
                                </div>
                                <div className="mt-3 text-2xl font-semibold text-slate-900">{item.value}</div>
                                <div className="mt-1 text-xs text-slate-500">{item.helper}</div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            <section className="grid gap-5 xl:grid-cols-[1.6fr_1fr]">
                <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <h2 className="text-lg font-semibold text-slate-900">Runtime configuration</h2>
                            <p className="mt-1 text-sm text-slate-500">The first release supports URLs, local files, and directories. A/B and Perf providers remain replaceable.</p>
                        </div>
                        <div className="flex items-center gap-2">
                            <button
                                type="button"
                                onClick={() => void loadHistory()}
                                disabled={loadingHistory}
                                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                <RefreshCw className={`w-4 h-4 ${loadingHistory ? 'animate-spin' : ''}`} />
                                Refresh history
                            </button>
                            <button
                                type="button"
                                onClick={handleStop}
                                disabled={!running}
                                className="inline-flex items-center gap-2 rounded-xl border border-rose-200 px-3 py-2 text-sm text-rose-600 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                <Pause className="w-4 h-4" />
                                Stop
                            </button>
                            <button
                                type="button"
                                onClick={() => void handleSubmit()}
                                disabled={submitting || !form.source.trim()}
                                className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <PlayCircle className="w-4 h-4" />}
                                Start execution
                            </button>
                        </div>
                    </div>

                    <div className="mt-5 space-y-5">
                        <div className="flex flex-wrap gap-2">
                            {SOURCE_TYPE_OPTIONS.map((option) => {
                                const active = form.source_type === option.value;
                                return (
                                    <button
                                        key={option.value}
                                        type="button"
                                        onClick={() => setForm((previous) => ({ ...previous, source_type: option.value }))}
                                        className={`rounded-2xl border px-4 py-3 text-left transition ${active
                                            ? 'border-slate-900 bg-slate-900 text-white'
                                            : 'border-slate-200 bg-slate-50 text-slate-600 hover:border-slate-300 hover:bg-white'
                                            }`}
                                    >
                                        <div className="text-sm font-medium">{option.label}</div>
                                        <div className={`mt-1 text-xs ${active ? 'text-slate-200' : 'text-slate-500'}`}>{option.helper}</div>
                                    </button>
                                );
                            })}
                        </div>

                        <div className="grid gap-4 md:grid-cols-2">
                            <label className="space-y-2">
                                <span className="text-sm font-medium text-slate-700">Prototype source</span>
                                <input
                                    value={form.source}
                                    onChange={(event) => setForm((previous) => ({ ...previous, source: event.target.value }))}
                                    placeholder={form.source_type === 'url'
                                        ? 'https://prototype.example.com'
                                        : form.source_type === 'file'
                                            ? 'D:\\prototype\\index.html'
                                            : 'D:\\prototype\\dist'}
                                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800 outline-none transition focus:border-slate-400 focus:bg-white"
                                />
                            </label>
                            <label className="space-y-2">
                                <span className="text-sm font-medium text-slate-700">Comparison version source</span>
                                <input
                                    value={form.compare_source || ''}
                                    onChange={(event) => setForm((previous) => ({ ...previous, compare_source: event.target.value }))}
                                    placeholder={"Optional; used by the A/B worker for structural comparison"}
                                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800 outline-none transition focus:border-slate-400 focus:bg-white"
                                />
                            </label>
                            <label className="space-y-2">
                                <span className="text-sm font-medium text-slate-700">Project package</span>
                                <select
                                    value={form.playbook_id || ''}
                                    onChange={(event) => setForm((previous) => ({ ...previous, playbook_id: event.target.value }))}
                                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800 outline-none transition focus:border-slate-400 focus:bg-white"
                                >
                                    {PLAYBOOK_OPTIONS.map((option) => (
                                        <option key={option.value || 'default'} value={option.value}>{option.label}</option>
                                    ))}
                                </select>
                            </label>
                            <label className="space-y-2">
                                <span className="text-sm font-medium text-slate-700">Target WCAG level</span>
                                <select
                                    value={form.wcag_level || 'AA'}
                                    onChange={(event) => setForm((previous) => ({ ...previous, wcag_level: event.target.value as PrototypeRunRequest['wcag_level'] }))}
                                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800 outline-none transition focus:border-slate-400 focus:bg-white"
                                >
                                    {WCAG_OPTIONS.map((level) => (
                                        <option key={level} value={level}>{level}</option>
                                    ))}
                                </select>
                            </label>
                        </div>

                        <div className="grid gap-4 lg:grid-cols-2">
                            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                                <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                                    <Activity className="w-4 h-4" />
                                    Worker toggles
                                </div>
                                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                                    {PROTOTYPE_AGENT_ORDER.filter((item) => item !== 'orchestrator' && item !== 'reporter').map((workerId) => (
                                        <label key={workerId} className="flex items-center justify-between rounded-xl border border-white bg-white px-3 py-2 text-sm text-slate-700">
                                            <span>{AGENT_META[workerId].title}</span>
                                            <input
                                                type="checkbox"
                                                checked={Boolean(form.worker_switches?.[workerId as keyof typeof DEFAULT_SWITCHES])}
                                                onChange={(event) => setForm((previous) => ({
                                                    ...previous,
                                                    worker_switches: {
                                                        ...previous.worker_switches,
                                                        [workerId]: event.target.checked,
                                                    },
                                                }))}
                                                className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-300"
                                            />
                                        </label>
                                    ))}
                                </div>
                            </div>

                            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                                <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                                    <Sparkles className="w-4 h-4" />
                                    Provider mapping
                                </div>
                                <div className="mt-3 grid gap-3">
                                    {PROTOTYPE_AGENT_ORDER.filter((item) => item !== 'orchestrator' && item !== 'reporter').map((workerId) => (
                                        <label key={workerId} className="grid gap-1">
                                            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{AGENT_META[workerId].title}</span>
                                            <input
                                                value={form.providers?.[workerId as keyof NonNullable<typeof form.providers>] || ''}
                                                onChange={(event) => setForm((previous) => ({
                                                    ...previous,
                                                    providers: {
                                                        ...previous.providers,
                                                        [workerId]: event.target.value,
                                                    },
                                                }))}
                                                className="w-full rounded-xl border border-white bg-white px-3 py-2 text-sm text-slate-700 outline-none transition focus:border-slate-300"
                                            />
                                        </label>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <h2 className="text-lg font-semibold text-slate-900">Task status</h2>
                            <p className="mt-1 text-sm text-slate-500">Runtime status, source context, and gate summary for the selected task.</p>
                        </div>
                        <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600">
                            {missionStatusLabel}
                        </div>
                    </div>

                    {activeMission ? (
                        <div className="mt-5 space-y-4">
                            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                                <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Mission</div>
                                <div className="mt-2 text-sm font-semibold text-slate-900">#{activeMission.mission_id}</div>
                                <div className="mt-1 text-sm text-slate-600">{activeMission.source || activeMission.user_input}</div>
                                <div className="mt-3 grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
                                    <div>Created at: {formatDateTime(activeMission.created_at)}</div>
                                    <div>Completed at: {formatDateTime(activeMission.completed_at)}</div>
                                    <div>Source type: {String(activeMission.source_type || '—').toUpperCase()}</div>
                                    <div>Playbook: {activeMission.playbook_id || "Not injected"}</div>
                                </div>
                            </div>

                            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                                <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                                    <Layers className="w-4 h-4" />
                                    Context summary
                                </div>
                                <div className="mt-3 grid gap-3 text-sm text-slate-600">
                                    <div>
                                        <span className="font-medium text-slate-800">Entry page:</span>
                                        {String(sourceContext.entry_url || '—')}
                                    </div>
                                    <div>
                                        <span className="font-medium text-slate-800">Discovered pages:</span>
                                        {discoveredPages.length ? discoveredPages.slice(0, 4).map((page) => String(page.relative_path || page.title || '')).join(' / ') : '—'}
                                    </div>
                                    <div>
                                        <span className="font-medium text-slate-800">Critical pages:</span>
                                        {criticalPages.length ? criticalPages.slice(0, 3).map((page) => String(page.page_name || page.route || "Unnamed")).join(' / ') : "Not injected"}
                                    </div>
                                </div>
                            </div>

                            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                                <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                                    <Gauge className="w-4 h-4" />
                                    Quality gate
                                </div>
                                <div className="mt-3 grid grid-cols-2 gap-3">
                                    {[
                                        ['module_coverage_rate', `${Math.round(Number(qualityMetrics.module_coverage_rate || 0) * 100)}%`],
                                        ['page_mapping_rate', `${Math.round(Number(qualityMetrics.page_mapping_rate || 0) * 100)}%`],
                                        ['blocking_gap', String(qualityMetrics.blocking_prototype_gap_count ?? 0)],
                                        ['critical_transition_gap', String(qualityMetrics.critical_state_transition_gap_count ?? 0)],
                                    ].map(([label, value]) => (
                                        <div key={label} className="rounded-xl border border-white bg-white px-3 py-3">
                                            <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
                                            <div className="mt-2 text-lg font-semibold text-slate-900">{value}</div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="mt-8 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
                            No task selected. Submit a prototype test or open a task from the history list at the bottom right.
                        </div>
                    )}
                </div>
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                    <div>
                        <h2 className="text-lg font-semibold text-slate-900">Agent status graph</h2>
                        <p className="mt-1 text-sm text-slate-500">Hub-and-spoke orchestration. SSE logs update node status in real time.</p>
                    </div>
                    <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600">
                        {activeMission ? `Current task ${activeMission.mission_id}` : "Waiting for task"}
                    </div>
                </div>

                <div className="mt-5 flex flex-wrap items-center gap-3">
                    {agentNodes.map((node, index) => {
                        const stateClass = AGENT_STATE_CLASS[node.status] || AGENT_STATE_CLASS.idle;
                        return (
                            <React.Fragment key={node.id}>
                                <div className={`min-w-[170px] flex-1 rounded-2xl border px-4 py-4 ${stateClass}`}>
                                    <div className="flex items-center justify-between gap-2">
                                        <div className="flex items-center gap-2 text-sm font-semibold">
                                            {AGENT_META[node.id as PrototypeAgentId].icon}
                                            {node.title}
                                        </div>
                                        <div>{getStatusIcon(node.status)}</div>
                                    </div>
                                    <div className="mt-2 text-xs leading-5 opacity-80">{node.role}</div>
                                    <div className="mt-3 inline-flex items-center rounded-full bg-white/70 px-2.5 py-1 text-xs font-medium">
                                        {formatStatusLabel(node.status)}
                                    </div>
                                </div>
                                {index < agentNodes.length - 1 && (
                                    <div className="hidden text-slate-300 lg:block">
                                        <ChevronRight className="w-5 h-5" />
                                    </div>
                                )}
                            </React.Fragment>
                        );
                    })}
                </div>
            </section>

            <section className="grid gap-5 2xl:grid-cols-[1.3fr_1fr]">
                <div className="space-y-5">
                    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                        <div className="flex items-start justify-between gap-3">
                            <div>
                                <h2 className="text-lg font-semibold text-slate-900">Worker results</h2>
                                <p className="mt-1 text-sm text-slate-500">Unified output from five specialized workers for comparison with the final report.</p>
                            </div>
                            <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600">
                                {workerResults.length} / 5
                            </div>
                        </div>

                        {workerResults.length ? (
                            <div className="mt-5 grid gap-4 xl:grid-cols-2">
                                {workerResults.map((worker) => {
                                    const stateClass = AGENT_STATE_CLASS[worker.status] || AGENT_STATE_CLASS.idle;
                                    const findingsPreview = worker.normalized_findings || [];
                                    return (
                                        <div key={worker.agent_id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                                            <div className="flex items-start justify-between gap-3">
                                                <div>
                                                    <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                                                        {AGENT_META[worker.agent_id as PrototypeAgentId]?.icon}
                                                        {AGENT_META[worker.agent_id as PrototypeAgentId]?.title || worker.agent_id}
                                                    </div>
                                                    <div className="mt-1 text-xs text-slate-500">{AGENT_META[worker.agent_id as PrototypeAgentId]?.role}</div>
                                                </div>
                                                <div className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-medium ${stateClass}`}>
                                                    {getStatusIcon(worker.status)}
                                                    {formatStatusLabel(worker.status)}
                                                </div>
                                            </div>

                                            <div className="mt-4 grid gap-3 sm:grid-cols-3">
                                                <div className="rounded-xl border border-white bg-white px-3 py-3">
                                                    <div className="text-[11px] uppercase tracking-wide text-slate-400">provider</div>
                                                    <div className="mt-2 text-sm font-medium text-slate-800">{worker.provider}</div>
                                                </div>
                                                <div className="rounded-xl border border-white bg-white px-3 py-3">
                                                    <div className="text-[11px] uppercase tracking-wide text-slate-400">Summary</div>
                                                    <div className="mt-2 text-sm font-medium text-slate-800">{summarizeWorkerPayload(worker)}</div>
                                                </div>
                                                <div className="rounded-xl border border-white bg-white px-3 py-3">
                                                    <div className="text-[11px] uppercase tracking-wide text-slate-400">Findings</div>
                                                    <div className="mt-2 text-sm font-medium text-slate-800">{findingsPreview.length}</div>
                                                </div>
                                            </div>

                                            <div className="mt-4 space-y-2">
                                                {findingsPreview.length ? findingsPreview.slice(0, 3).map((finding) => (
                                                    <div key={finding.finding_id || `${worker.agent_id}_${finding.title}`} className={`rounded-xl border px-3 py-3 ${FINDING_TONE_CLASS[finding.severity] || FINDING_TONE_CLASS.info}`}>
                                                        <div className="flex items-center justify-between gap-3">
                                                            <div className="text-sm font-medium">{finding.title}</div>
                                                            <div className="text-[11px] uppercase tracking-wide">{finding.severity}</div>
                                                        </div>
                                                        <div className="mt-1 text-sm leading-5">{finding.summary}</div>
                                                    </div>
                                                )) : (
                                                    <div className="rounded-xl border border-dashed border-slate-200 bg-white px-3 py-5 text-center text-sm text-slate-500">
                                                        This worker did not produce a standardized finding.
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        ) : (
                            <div className="mt-5 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
                                Worker results appear here in real time during execution.
                            </div>
                        )}
                    </div>

                    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                        <div className="flex items-center justify-between gap-3">
                            <div>
                                <h2 className="text-lg font-semibold text-slate-900">Final report</h2>
                                <p className="mt-1 text-sm text-slate-500">Reporter merges five JSON results and produces severity rankings and recommended fixes.</p>
                            </div>
                            <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 p-1 text-xs">
                                <button
                                    type="button"
                                    onClick={() => setRawTab('report')}
                                    className={`rounded-full px-3 py-1.5 transition ${rawTab === 'report' ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-white'}`}
                                >
                                    Report view
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setRawTab('json')}
                                    className={`rounded-full px-3 py-1.5 transition ${rawTab === 'json' ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-white'}`}
                                >
                                    Raw JSON
                                </button>
                            </div>
                        </div>

                        {rawTab === 'report' ? (
                            <div className="mt-5 space-y-5">
                                <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
                                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                                        <div className="text-sm font-semibold text-slate-900">Severity overview</div>
                                        <div className="mt-3 text-sm text-slate-600">{severitySummary}</div>
                                        <div className="mt-4 space-y-2">
                                            {findings.length ? findings.slice(0, 6).map((finding) => (
                                                <div key={finding.finding_id || `${finding.agent_id}_${finding.title}`} className={`rounded-xl border px-3 py-3 ${FINDING_TONE_CLASS[finding.severity] || FINDING_TONE_CLASS.info}`}>
                                                    <div className="flex items-center justify-between gap-3">
                                                        <div className="text-sm font-semibold">{finding.title}</div>
                                                        <div className="text-[11px] uppercase tracking-wide">{finding.severity}</div>
                                                    </div>
                                                    <div className="mt-1 text-sm leading-5">{finding.summary}</div>
                                                    <div className="mt-2 text-[11px] uppercase tracking-wide opacity-80">
                                                        {finding.agent_id} · {finding.provider}
                                                    </div>
                                                </div>
                                            )) : (
                                                <div className="rounded-xl border border-dashed border-slate-200 bg-white px-3 py-8 text-center text-sm text-slate-500">
                                                    No standardized findings yet.
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                                        <div className="text-sm font-semibold text-slate-900">Recommended fixes</div>
                                        <div className="mt-4 space-y-3">
                                            {(activeMission?.report?.recommendations || []).length ? (activeMission?.report?.recommendations || []).map((item, index) => (
                                                <div key={`${index}_${item}`} className="rounded-xl border border-white bg-white px-3 py-3 text-sm leading-6 text-slate-700">
                                                    <span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-slate-900 text-[11px] font-medium text-white">{index + 1}</span>
                                                    {item}
                                                </div>
                                            )) : (
                                                <div className="rounded-xl border border-dashed border-slate-200 bg-white px-3 py-8 text-center text-sm text-slate-500">
                                                    Reporter has not provided recommendations yet.
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <pre className="mt-5 max-h-[560px] overflow-auto rounded-2xl border border-slate-200 bg-slate-950 p-4 text-xs leading-6 text-slate-100">
                                {activeMission ? JSON.stringify(activeMission, null, 2) : "{\n  \"message\": \"No task\"\n}"}
                            </pre>
                        )}
                    </div>
                </div>

                <div className="space-y-5">
                    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                        <div className="flex items-start justify-between gap-3">
                            <div>
                                <h2 className="text-lg font-semibold text-slate-900">Timeline</h2>
                                <p className="mt-1 text-sm text-slate-500">Consume the SSE stream to record state changes from Orchestrator, workers, and Reporter.</p>
                            </div>
                            <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600">
                                {logs.length} entries
                            </div>
                        </div>

                        {logs.length ? (
                            <div className="mt-5 max-h-[560px] space-y-3 overflow-auto pr-1">
                                {logs.map((entry, index) => {
                                    const agentId = String(entry.data?.agent_id || '');
                                    const status = String(entry.data?.agent_status || entry.level || 'info');
                                    const stateClass = AGENT_STATE_CLASS[status] || AGENT_STATE_CLASS.idle;
                                    return (
                                        <div key={`${entry.timestamp}_${index}`} className="relative rounded-2xl border border-slate-200 bg-slate-50 p-4">
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="space-y-1">
                                                    <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                                                        {agentId && AGENT_META[agentId as PrototypeAgentId]?.icon}
                                                        <span>{entry.message}</span>
                                                    </div>
                                                    <div className="text-xs text-slate-500">
                                                        {formatDateTime(entry.timestamp)}
                                                        {agentId ? ` · ${agentId}` : ''}
                                                    </div>
                                                </div>
                                                <div className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-medium ${stateClass}`}>
                                                    {getStatusIcon(status)}
                                                    {formatStatusLabel(status)}
                                                </div>
                                            </div>
                                            {Object.keys(entry.data || {}).length > 0 && (
                                                <pre className="mt-3 overflow-auto rounded-xl border border-white bg-white p-3 text-[11px] leading-5 text-slate-600">
                                                    {JSON.stringify(entry.data, null, 2)}
                                                </pre>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        ) : (
                            <div className="mt-5 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
                                Broadcasts and response logs appear here continuously after a task starts.
                            </div>
                        )}
                    </div>

                    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                        <div className="flex items-start justify-between gap-3">
                            <div>
                                <h2 className="text-lg font-semibold text-slate-900">Recent tasks</h2>
                                <p className="mt-1 text-sm text-slate-500">Reopen historical tasks. Running tasks automatically resume listening to SSE.</p>
                            </div>
                            <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600">
                                {missions.length} entries
                            </div>
                        </div>

                        {missions.length ? (
                            <div className="mt-5 space-y-3">
                                {missions.slice(0, 8).map((mission) => {
                                    const selected = mission.mission_id === activeMissionId;
                                    const missionFindings = (mission.report?.findings || []) as PrototypeFinding[];
                                    return (
                                        <button
                                            key={mission.mission_id}
                                            type="button"
                                            onClick={() => void loadMission(mission.mission_id, isRunningMission(mission.status))}
                                            className={`w-full rounded-2xl border p-4 text-left transition ${selected
                                                ? 'border-slate-900 bg-slate-900 text-white'
                                                : 'border-slate-200 bg-slate-50 text-slate-800 hover:border-slate-300 hover:bg-white'
                                                }`}
                                        >
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="min-w-0">
                                                    <div className="truncate text-sm font-semibold">#{mission.mission_id}</div>
                                                    <div className={`mt-1 truncate text-xs ${selected ? 'text-slate-300' : 'text-slate-500'}`}>
                                                        {mission.source || mission.user_input}
                                                    </div>
                                                </div>
                                                <div className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-medium ${selected
                                                    ? 'border-white/20 bg-white/10 text-white'
                                                    : (AGENT_STATE_CLASS[mission.status] || AGENT_STATE_CLASS.idle)
                                                    }`}>
                                                    {getStatusIcon(mission.status)}
                                                    {formatStatusLabel(mission.status)}
                                                </div>
                                            </div>
                                            <div className={`mt-3 grid grid-cols-3 gap-2 text-xs ${selected ? 'text-slate-300' : 'text-slate-500'}`}>
                                                <div>
                                                    <div className="uppercase tracking-wide">Create</div>
                                                    <div className="mt-1">{formatDateTime(mission.created_at)}</div>
                                                </div>
                                                <div>
                                                    <div className="uppercase tracking-wide">Issues</div>
                                                    <div className="mt-1">{missionFindings.length}</div>
                                                </div>
                                                <div>
                                                    <div className="uppercase tracking-wide">Worker</div>
                                                    <div className="mt-1">{mission.worker_results?.length || 0}</div>
                                                </div>
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        ) : (
                            <div className="mt-5 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
                                No task history yet. Run a prototype test to begin.
                            </div>
                        )}
                    </div>
                </div>
            </section>
        </div>
    );
};

export default PrototypeAgentsPage;
