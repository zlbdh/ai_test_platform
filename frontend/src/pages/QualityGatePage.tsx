import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ShieldCheck, Plus, Settings, CheckCircle, XCircle, AlertTriangle, RefreshCw, BookOpen } from '../components/icons';
import { API_ENDPOINTS } from '../config';
import { getFrontdoorTask, listFrontdoorTasks, type FrontdoorTask } from '../services/frontdoorTaskService';
import {
    buildFrontdoorDeepView,
    formatFindingSeveritySummary,
    formatMetricValue,
    statusMeta,
    verificationStateMeta,
} from './frontdoorTaskShared';

interface GateRule {
    name: string;
    description: string;
    metric: string;
    operator: string;
    threshold: number;
    severity: string;
    enabled: boolean;
}

interface GateCheck {
    rule_name: string;
    status: string;
    actual_value: number;
    threshold: number;
    message: string;
}

interface GateVerdict {
    status: string;
    summary: string;
    checks: GateCheck[];
    total_checks: number;
    passed_checks: number;
    failed_checks: number;
}

interface HistoryEntry {
    run_id: string;
    status: string;
    verdict: GateVerdict;
    timestamp: number;
}

interface ApiEnvelope<T> {
    status?: string;
    data?: T;
    [key: string]: unknown;
}

interface ImportedRulePack {
    playbook_id: string;
    playbook_name?: string;
    playbook_title?: string;
    project_name?: string;
    imported_count: number;
}

const statusIcon: Record<string, any> = {
    passed: CheckCircle,
    failed: XCircle,
    warning: AlertTriangle,
    pending: RefreshCw,
};

const statusColor: Record<string, string> = {
    passed: 'text-emerald-600 dark:text-emerald-400',
    failed: 'text-rose-600 dark:text-rose-400',
    warning: 'text-amber-600 dark:text-amber-400',
    pending: 'text-slate-500 dark:text-slate-400',
};

const severityBadge: Record<string, string> = {
    blocking: 'bg-rose-50 text-rose-700 dark:bg-rose-500/15 dark:text-rose-400',
    warning: 'bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400',
    info: 'bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400',
};

const metricLabels: Record<string, string> = {
    goal_achievement: "Goal achievement rate",
    step_accuracy: "Step accuracy",
    hallucination_score: "Hallucination suppression score",
    healing_success_rate: "Self-healing success rate",
    token_efficiency: "Token efficiency",
    login_success_rate: "Login success rate",
    core_flow_pass_rate: "Core flow pass rate",
    blocking_bug_count: "Blocking defects",
    unexplained_5xx_count: "Unexplained 5xx responses",
    critical_ui_error_count: "Critical UI anomalies",
    module_coverage_rate: "Module coverage",
    page_mapping_rate: "Page mapping rate",
    critical_page_missing_count: "Missing critical pages",
    blocking_prototype_gap_count: "Blocking prototype differences",
    critical_field_missing_count: "Missing critical fields",
    critical_state_transition_gap_count: "Missing critical state transitions",
};

const defaultMetricSamples: Record<string, number> = {
    goal_achievement: 0.85,
    step_accuracy: 0.75,
    hallucination_score: 0.9,
    healing_success_rate: 0.7,
    token_efficiency: 0.6,
    login_success_rate: 1,
    core_flow_pass_rate: 0.95,
    blocking_bug_count: 0,
    unexplained_5xx_count: 0,
    critical_ui_error_count: 0,
    module_coverage_rate: 1,
    page_mapping_rate: 0.95,
    critical_page_missing_count: 0,
    blocking_prototype_gap_count: 0,
    critical_field_missing_count: 0,
    critical_state_transition_gap_count: 0,
};

const getRulePackSummary = (pack: ImportedRulePack | null, rules: GateRule[]) => {
    if (pack?.playbook_id === 'sample-platform-prototype' || rules.some(rule => rule.name.startsWith('sample_platform_platform_'))) {
        return {
            title: pack?.playbook_title || "Sample project platform prototype test package",
            description: "Rules cover module coverage, page mapping, missing critical pages, blocking prototype differences, missing critical fields, and missing critical state transitions.",
        };
    }
    if (pack?.playbook_id === 'sample-first-regression' || rules.some(rule => rule.name.startsWith('sample_platform_'))) {
        return {
            title: pack?.playbook_title || "Sample enterprise platform initial live regression",
            description: "Rules cover login success rate, core flow pass rate, blocking defects, unexplained 5xx responses, and critical page anomalies.",
        };
    }
    return null;
};

const getPayload = <T,>(value: ApiEnvelope<T> | T): T => {
    if (value && typeof value === 'object' && 'data' in (value as ApiEnvelope<T>)) {
        const envelope = value as ApiEnvelope<T>;
        if (envelope.data !== undefined) {
            return envelope.data;
        }
    }
    return value as T;
};

const buildMetricDrafts = (rules: GateRule[], previous: Record<string, string>) => {
    const next: Record<string, string> = {};
    const metrics = Array.from(new Set(rules.map(rule => rule.metric)));
    metrics.forEach(metric => {
        const previousValue = previous[metric];
        if (previousValue !== undefined) {
            next[metric] = previousValue;
            return;
        }
        const sample = defaultMetricSamples[metric];
        next[metric] = sample !== undefined ? String(sample) : '0';
    });
    return next;
};

const mergeTaskMetricsIntoDrafts = (
    base: Record<string, string>,
    metrics: Record<string, unknown>,
) => {
    const next = { ...base };
    Object.entries(metrics || {}).forEach(([metric, value]) => {
        if (value === undefined || value === null) return;
        if (typeof value === 'object') return;
        const normalized = String(value);
        if (!(metric in next) || next[metric] === '') {
            next[metric] = normalized;
        }
    });
    return next;
};

export default function QualityGatePage() {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [rules, setRules] = useState<GateRule[]>([]);
    const [history, setHistory] = useState<HistoryEntry[]>([]);
    const [tab, setTab] = useState<'rules' | 'check' | 'history'>('rules');
    const [loading, setLoading] = useState(false);
    const [checking, setChecking] = useState(false);
    const [importingRules, setImportingRules] = useState(false);
    const [checkResult, setCheckResult] = useState<GateVerdict | null>(null);
    const [showAddModal, setShowAddModal] = useState(false);
    const [metricDrafts, setMetricDrafts] = useState<Record<string, string>>({});
    const [lastImportedCount, setLastImportedCount] = useState(0);
    const [lastImportedPack, setLastImportedPack] = useState<ImportedRulePack | null>(null);
    const [taskContext, setTaskContext] = useState<FrontdoorTask | null>(null);
    const [taskContextLoading, setTaskContextLoading] = useState(false);
    const [lineageTasks, setLineageTasks] = useState<FrontdoorTask[]>([]);
    const [comparableHistoryEntry, setComparableHistoryEntry] = useState<HistoryEntry | null>(null);
    const [newRule, setNewRule] = useState({
        name: '',
        description: '',
        metric: 'goal_achievement',
        operator: '>=',
        threshold: 0.8,
        severity: 'blocking',
    });
    const taskIdParam = (searchParams.get('task_id') || '').trim();
    const runIdParam = (searchParams.get('run_id') || '').trim();
    const historyStatusParam = (searchParams.get('status') || '').trim();
    const focusParam = (searchParams.get('focus') || '').trim();

    const applyRules = useCallback((nextRules: GateRule[]) => {
        setRules(nextRules);
        setMetricDrafts(previous => buildMetricDrafts(nextRules, previous));
    }, []);

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const historyParams = new URLSearchParams();
            historyParams.set('limit', '20');
            if (runIdParam) historyParams.set('run_id', runIdParam);
            if (historyStatusParam) historyParams.set('status', historyStatusParam);
            const [rulesEnvelope, historyEnvelope] = await Promise.all([
                fetch(API_ENDPOINTS.qualityGate.rules).then(r => r.json()),
                fetch(`${API_ENDPOINTS.qualityGate.history}?${historyParams.toString()}`).then(r => r.json()),
            ]);
            const rulesData = getPayload<{ rules?: GateRule[] }>(rulesEnvelope);
            const historyData = getPayload<{ history?: HistoryEntry[] }>(historyEnvelope);
            applyRules(rulesData.rules || []);
            setHistory(historyData.history || []);
        } catch (e) {
            console.error(e);
        }
        setLoading(false);
    }, [applyRules, historyStatusParam, runIdParam]);

    useEffect(() => {
        const timer = window.setTimeout(() => {
            void fetchData();
        }, 0);
        return () => window.clearTimeout(timer);
    }, [fetchData]);

    useEffect(() => {
        if (focusParam === 'rules' || focusParam === 'check' || focusParam === 'history') {
            setTab(focusParam);
        }
    }, [focusParam]);

    useEffect(() => {
        let active = true;
        if (!taskIdParam) {
            setTaskContext(null);
            setLineageTasks([]);
            setComparableHistoryEntry(null);
            setTaskContextLoading(false);
            return () => {
                active = false;
            };
        }
        setTaskContextLoading(true);
        void getFrontdoorTask(taskIdParam)
            .then(async (task) => {
                if (!active) return;
                setTaskContext(task);
                setMetricDrafts(previous => mergeTaskMetricsIntoDrafts(buildMetricDrafts(rules, previous), task.gate_summary?.metrics || {}));
                if (!task.lineage_root_id) {
                    setLineageTasks([]);
                    return;
                }
                try {
                    const tasks = await listFrontdoorTasks({ limit: 10, lineageRootId: task.lineage_root_id });
                    if (!active) return;
                    setLineageTasks(tasks);
                } catch {
                    if (!active) return;
                    setLineageTasks([]);
                }
            })
            .catch(() => {
                if (!active) return;
                setTaskContext(null);
                setLineageTasks([]);
                setComparableHistoryEntry(null);
            })
            .finally(() => {
                if (!active) return;
                setTaskContextLoading(false);
            });
        return () => {
            active = false;
        };
    }, [rules, taskIdParam]);

    const runCheck = async () => {
        setChecking(true);
        try {
            const metric_scores = Object.entries(metricDrafts).reduce<Record<string, number>>((acc, [metric, value]) => {
                const parsed = Number(value);
                acc[metric] = Number.isFinite(parsed) ? parsed : 0;
                return acc;
            }, {});

            const res = await fetch(API_ENDPOINTS.qualityGate.check, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ metric_scores, run_id: `manual_${Date.now()}` }),
            });
            const data = await res.json();
            const payload = getPayload<{ verdict?: GateVerdict }>(data);
            setCheckResult(payload.verdict || null);
            setTab('check');
            await fetchData();
        } catch (e) {
            console.error(e);
        }
        setChecking(false);
    };

    const addRule = async () => {
        try {
            await fetch(API_ENDPOINTS.qualityGate.rules, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newRule),
            });
            setShowAddModal(false);
            setNewRule({ name: '', description: '', metric: 'goal_achievement', operator: '>=', threshold: 0.8, severity: 'blocking' });
            await fetchData();
        } catch (e) {
            console.error(e);
        }
    };

    const importRules = async (playbookId: string) => {
        setImportingRules(true);
        try {
            const res = await fetch(API_ENDPOINTS.qualityGate.importRules(playbookId), {
                method: 'POST',
            });
            const data = await res.json();
            const payload = getPayload<ImportedRulePack>(data);
            setLastImportedCount(payload.imported_count || 0);
            setLastImportedPack({
                playbook_id: payload.playbook_id,
                playbook_name: payload.playbook_name,
                playbook_title: payload.playbook_title,
                project_name: payload.project_name,
                imported_count: payload.imported_count || 0,
            });
            await fetchData();
            setTab('rules');
        } catch (e) {
            console.error(e);
        }
        setImportingRules(false);
    };

    const currentMetrics = Object.keys(metricDrafts);
    const rulePackSummary = getRulePackSummary(lastImportedPack, rules);
    const filteredHistory = useMemo(() => history, [history]);
    const currentHistoryEntry = useMemo(
        () => (runIdParam ? filteredHistory.find((entry) => entry.run_id === runIdParam) || filteredHistory[0] || null : null),
        [filteredHistory, runIdParam],
    );
    const deepView = useMemo(
        () => buildFrontdoorDeepView({
            currentTask: taskContext,
            currentTaskId: taskIdParam,
            lineageTasks,
            currentGateHistory: currentHistoryEntry,
            comparableGateHistory: comparableHistoryEntry,
        }),
        [comparableHistoryEntry, currentHistoryEntry, lineageTasks, taskContext, taskIdParam],
    );
    const { comparableTask, comparisonSummary, gateDeepRead } = deepView;
    const taskGateStatus = taskContext?.gate_summary?.status || 'pending';
    const taskGateColor = statusColor[taskGateStatus] || statusColor.pending;
    const currentGateHistory = gateDeepRead.currentHistory;
    const comparableGateHistory = gateDeepRead.comparableHistory;
    const gateCheckDiff = gateDeepRead.gateCheckDiff;
    const changedGateChecks = gateDeepRead.changedGateChecks;

    useEffect(() => {
        let active = true;
        if (!comparableTask?.task_id) {
            setComparableHistoryEntry(null);
            return () => {
                active = false;
            };
        }
        void fetch(`${API_ENDPOINTS.qualityGate.history}?limit=1&run_id=${encodeURIComponent(comparableTask.task_id)}`)
            .then((response) => response.json())
            .then((data) => {
                if (!active) return;
                const payload = getPayload<{ history?: HistoryEntry[] }>(data);
                setComparableHistoryEntry(payload.history?.[0] || null);
            })
            .catch(() => {
                if (!active) return;
                setComparableHistoryEntry(null);
            });
        return () => {
            active = false;
        };
    }, [comparableTask?.task_id]);

    return (
        <div className="space-y-6 pb-8">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 text-white">
                        <ShieldCheck className="w-5 h-5" />
                    </div>
                    <div>
                        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Quality gate</h2>
                        <p className="text-sm text-slate-500 dark:text-slate-400">Detailed unified task conclusions and business acceptance checks</p>
                    </div>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={() => void importRules('sample-first-regression')}
                        disabled={importingRules}
                        className="flex items-center gap-1.5 px-3 py-2 border border-emerald-200 bg-emerald-50 hover:bg-emerald-100 rounded-lg text-sm text-emerald-700 transition-colors shadow-sm disabled:opacity-50 dark:bg-emerald-900/20 dark:border-emerald-800/60 dark:text-emerald-300 dark:hover:bg-emerald-900/30"
                    >
                        {importingRules ? <RefreshCw className="w-4 h-4 animate-spin" /> : <BookOpen className="w-4 h-4" />}
                        {importingRules ? "Importing..." : "Import sample project rules"}
                    </button>
                    <button
                        onClick={() => void importRules('sample-platform-prototype')}
                        disabled={importingRules}
                        className="flex items-center gap-1.5 px-3 py-2 border border-blue-200 bg-blue-50 hover:bg-blue-100 rounded-lg text-sm text-blue-700 transition-colors shadow-sm disabled:opacity-50 dark:bg-blue-900/20 dark:border-blue-800/60 dark:text-blue-300 dark:hover:bg-blue-900/30"
                    >
                        {importingRules ? <RefreshCw className="w-4 h-4 animate-spin" /> : <BookOpen className="w-4 h-4" />}
                        {importingRules ? "Importing..." : "Import platform prototype rules"}
                    </button>
                    <button onClick={() => setShowAddModal(true)} className="flex items-center gap-1.5 px-3 py-2 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg text-sm text-slate-700 transition-colors shadow-sm dark:bg-slate-800 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-700">
                        <Plus className="w-4 h-4" /> Add rule
                    </button>
                    <button onClick={runCheck} disabled={checking || currentMetrics.length === 0} className="flex items-center gap-1.5 px-3 py-2 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 rounded-lg text-sm text-white transition-all disabled:opacity-50 shadow-sm">
                        {checking ? <RefreshCw className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />} Run checks
                    </button>
                </div>
            </div>

            {(taskContextLoading || taskContext) && (
                <div className="rounded-2xl border border-violet-200 bg-violet-50/70 p-5 dark:border-violet-800/50 dark:bg-violet-900/10">
                    {taskContextLoading ? (
                        <div className="flex items-center gap-2 text-sm text-violet-600 dark:text-violet-300">
                            <RefreshCw className="h-4 w-4 animate-spin" />
                            Loading unified task context...
                        </div>
                    ) : taskContext ? (
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                            <div>
                                <p className="text-xs uppercase tracking-wide text-violet-500">From unified testing task</p>
                                <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">{taskContext.user_goal}</h3>
                                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                                    {taskContext.task_kind} · {taskContext.task_id} · Current status {taskContext.status}
                                </p>
                                <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500 dark:text-slate-400">
                                    <span>Execution group: {taskContext.execution_group_id || '-'}</span>
                                    <span>Rerun chain: {taskContext.lineage_root_id || '-'}</span>
                                    <span>run_id: {runIdParam || taskContext.task_id || '-'}</span>
                                    <span>{taskContext.rerun_from_task_id ? `Rerun of: ${taskContext.rerun_from_task_id}` : "This is the initial task"}</span>
                                    <span>Task state: {statusMeta(taskContext.status).label}</span>
                                </div>
                                <div className="mt-3 flex flex-wrap items-center gap-2">
                                    <span className={`rounded-full px-3 py-1 text-xs font-medium ${taskGateColor}`}>
                                        Current gate: {taskContext.gate_summary?.status || 'pending'}
                                    </span>
                                    <span className="text-sm text-slate-600 dark:text-slate-300">
                                        {taskContext.gate_summary?.summary || "No gate summary is available for this task."}
                                    </span>
                                </div>
                                {taskContext.gate_summary?.decision_reason && (
                                    <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                                        Decision reason: {taskContext.gate_summary.decision_reason}
                                    </div>
                                )}
                                {runIdParam && (
                                    <div className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                                        Focused on gate history for run_id = {runIdParam} , with task metrics loaded into Business metrics input.
                                        {historyStatusParam ? ` Also filtering status = ${historyStatusParam}.` : ''}
                                    </div>
                                )}
                                {comparableTask && (
                                    <div className="mt-3 rounded-xl border border-violet-200/60 bg-white/80 px-3 py-3 text-xs text-slate-600 dark:border-violet-500/20 dark:bg-slate-900/50 dark:text-slate-300">
                                        <div className="font-semibold text-slate-700 dark:text-slate-100">Most recent comparable rerun</div>
                                        <div className="mt-2 flex flex-wrap gap-3">
                                            <span>Task: {comparableTask.task_id}</span>
                                            <span>Status: {statusMeta(comparableTask.status).label}</span>
                                            <span>Gate: {comparableTask.gate_summary?.status || 'pending'}</span>
                                        </div>
                                        <div className="mt-2 text-slate-500 dark:text-slate-400">
                                            {comparableTask.gate_summary?.summary || "No gate summary is available for the comparable task."}
                                        </div>
                                    </div>
                                )}
                                {comparableTask && comparisonSummary && (
                                    <div className="mt-3 rounded-xl border border-violet-200/60 bg-white/80 px-3 py-3 text-xs text-slate-600 dark:border-violet-500/20 dark:bg-slate-900/50 dark:text-slate-300">
                                        <div className="font-semibold text-slate-700 dark:text-slate-100">Current run vs. most recent rerun</div>
                                        <div className="mt-2 grid gap-2 md:grid-cols-2">
                                            <div className="rounded-lg bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                                <div className="text-slate-400">Finding count</div>
                                                <div className="mt-1 text-slate-700 dark:text-slate-200">
                                                    Current {comparisonSummary.currentFindingCount} / Previous {comparisonSummary.comparableFindingCount}
                                                </div>
                                            </div>
                                            <div className="rounded-lg bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                                <div className="text-slate-400">High-risk findings</div>
                                                <div className="mt-1 text-slate-700 dark:text-slate-200">
                                                    Current {comparisonSummary.currentSeveritySummary.blocking + comparisonSummary.currentSeveritySummary.major}
                                                    {' / '}
                                                    Previous {comparisonSummary.comparableSeveritySummary.blocking + comparisonSummary.comparableSeveritySummary.major}
                                                </div>
                                            </div>
                                            <div className="rounded-lg bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                                <div className="text-slate-400">Gate status</div>
                                                <div className="mt-1 text-slate-700 dark:text-slate-200">
                                                    Current {taskContext.gate_summary?.status || 'pending'} / Previous {comparableTask.gate_summary?.status || 'pending'}
                                                </div>
                                            </div>
                                            <div className="rounded-lg bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                                <div className="text-slate-400">Verification state</div>
                                                <div className="mt-1 text-slate-700 dark:text-slate-200">
                                                    Current {verificationStateMeta(taskContext.verification_state).label}
                                                    {' / '}
                                                    Previous {verificationStateMeta(comparableTask.verification_state).label}
                                                </div>
                                            </div>
                                        </div>
                                        <div className="mt-2 rounded-lg bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                            <div className="text-slate-400">Severity changes</div>
                                            <div className="mt-1 text-slate-700 dark:text-slate-200">
                                                Current: {formatFindingSeveritySummary(comparisonSummary.currentSeveritySummary)}
                                            </div>
                                            <div className="mt-1 text-slate-500 dark:text-slate-400">
                                                Previous: {formatFindingSeveritySummary(comparisonSummary.comparableSeveritySummary)}
                                            </div>
                                        </div>
                                        <div className="mt-2 rounded-lg bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                            <div className="text-slate-400">Decision reason changes</div>
                                            <div className="mt-1 text-slate-700 dark:text-slate-200">
                                                Current: {taskContext.gate_summary?.decision_reason || "No structured decision reasons for this run."}
                                            </div>
                                            <div className="mt-1 text-slate-500 dark:text-slate-400">
                                                Previous: {comparableTask.gate_summary?.decision_reason || "No structured decision reasons for the previous run."}
                                            </div>
                                        </div>
                                        <div className="mt-2 rounded-lg bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                            <div className="flex items-center justify-between gap-3">
                                                <div className="text-slate-400">Key metric changes</div>
                                                <div className="text-[11px] text-slate-400">
                                                    {comparisonSummary.changedMetricCount > 0 ? `${comparisonSummary.changedMetricCount} changes` : "Unchanged from previous run"}
                                                </div>
                                            </div>
                                            <div className="mt-2 space-y-2">
                                                {comparisonSummary.metricChanges.length === 0 ? (
                                                    <div className="text-slate-400">No comparable metrics are available.</div>
                                                ) : comparisonSummary.metricChanges.slice(0, 6).map((metric) => (
                                                    <div key={metric.key} className="rounded-lg border border-slate-200/70 bg-white px-3 py-3 dark:border-slate-700/70 dark:bg-slate-900/40">
                                                        <div className="flex items-center justify-between gap-3">
                                                            <div className="text-slate-400">{metric.key}</div>
                                                            <span className={`rounded-full px-2 py-0.5 text-[10px] ${metric.changed ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300' : 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-300'}`}>
                                                                {metric.changed ? "Changed" : "Unchanged"}
                                                            </span>
                                                        </div>
                                                        <div className="mt-1 text-slate-700 dark:text-slate-200">Current: {formatMetricValue(metric.currentValue)}</div>
                                                        <div className="mt-1 text-slate-500 dark:text-slate-400">Previous: {formatMetricValue(metric.comparableValue)}</div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                        <div className="mt-2 rounded-lg bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                            <div className="flex items-center justify-between gap-3">
                                                <div className="text-slate-400">Check changes</div>
                                                <div className="text-[11px] text-slate-400">
                                                    {changedGateChecks.length > 0 ? `${changedGateChecks.length} ${changedGateChecks.length === 1 ? 'rule change' : 'rule changes'}` : "Unchanged from previous run"}
                                                </div>
                                            </div>
                                            {!currentGateHistory ? (
                                                <div className="mt-2 text-slate-400">No gate history checks are available for this task yet.</div>
                                            ) : !comparableGateHistory ? (
                                                <div className="mt-2 text-slate-400">No comparable gate history is available for the most recent rerun yet.</div>
                                            ) : (
                                                <div className="mt-2 space-y-2">
                                                    <div className="text-slate-500 dark:text-slate-400">
                                                        Current {currentGateHistory.verdict?.failed_checks ?? 0}/{currentGateHistory.verdict?.total_checks ?? 0} failed, previous {comparableGateHistory.verdict?.failed_checks ?? 0}/{comparableGateHistory.verdict?.total_checks ?? 0} failed.
                                                    </div>
                                                    {(changedGateChecks.length > 0 ? changedGateChecks : gateCheckDiff).slice(0, 4).map((item) => (
                                                        <div key={item.ruleName} className="rounded-lg border border-slate-200/70 bg-white px-3 py-3 dark:border-slate-700/70 dark:bg-slate-900/40">
                                                            <div className="text-slate-700 dark:text-slate-200">{item.ruleName}</div>
                                                            <div className="mt-1 text-slate-500 dark:text-slate-400">
                                                                Current: {item.currentStatus} / Previous: {item.comparableStatus}
                                                            </div>
                                                            {(item.currentMessage || item.comparableMessage) && (
                                                                <div className="mt-1 text-[11px] text-slate-400">
                                                                    Current explanation: {item.currentMessage || "None"} ; previous explanation: {item.comparableMessage || "None"}
                                                                </div>
                                                            )}
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>
                            <div className="flex flex-wrap gap-2">
                                <button
                                    type="button"
                                    onClick={() => setTab('check')}
                                    className="rounded-lg border border-violet-200 bg-white px-3 py-2 text-sm text-violet-700 transition-colors hover:bg-violet-50 dark:border-violet-700/50 dark:bg-slate-800 dark:text-violet-300 dark:hover:bg-violet-500/10"
                                >
                                    Load metrics for review
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setTab('history')}
                                    className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 transition-colors hover:text-violet-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
                                >
                                    Focus gate history
                                </button>
                                <button
                                    type="button"
                                    onClick={() => navigate(taskContext.execution_center_path)}
                                    className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 transition-colors hover:text-violet-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
                                >
                                    Return to execution center
                                </button>
                                <button
                                    type="button"
                                    onClick={() => navigate('/quality-gate')}
                                    className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 transition-colors hover:text-violet-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
                                >
                                    Clear task context
                                </button>
                            </div>
                        </div>
                    ) : null}
                </div>
            )}

            {rulePackSummary && (
                <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-5 dark:border-emerald-800/50 dark:bg-emerald-900/10">
                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <p className="text-xs uppercase tracking-wide text-emerald-500">Project gate</p>
                            <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">{rulePackSummary.title}</h3>
                            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                                {rulePackSummary.description}
                            </p>
                        </div>
                        {lastImportedCount > 0 && (
                            <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-emerald-700 shadow-sm dark:bg-slate-800 dark:text-emerald-300">
                                Imported {lastImportedCount} rules
                            </span>
                        )}
                    </div>
                </div>
            )}

            <div className="flex gap-1 p-1 bg-slate-100 rounded-lg w-fit dark:bg-slate-800/60">
                {(['rules', 'check', 'history'] as const).map(t => (
                    <button
                        key={t}
                        onClick={() => setTab(t)}
                        className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${tab === t
                            ? 'bg-white text-indigo-600 shadow-sm dark:bg-slate-700 dark:text-indigo-400'
                            : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'
                            }`}
                    >
                        {{ rules: "Gate rules", check: "Check results", history: "History" }[t]}
                    </button>
                ))}
            </div>

            {tab === 'rules' && (
                <div className="space-y-3">
                    {rules.map(r => (
                        <div key={r.name} className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm hover:shadow-md hover:border-emerald-200 transition-all dark:border-slate-700/80 dark:bg-slate-800/60 dark:hover:border-emerald-500/30">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <Settings className="w-4 h-4 text-slate-400 dark:text-slate-500" />
                                    <span className="font-semibold text-slate-800 dark:text-slate-200">{r.name}</span>
                                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${severityBadge[r.severity] || severityBadge.info}`}>{r.severity}</span>
                                </div>
                                <code className="text-xs text-slate-500 bg-slate-100 dark:bg-slate-700 dark:text-slate-400 px-2 py-0.5 rounded">{r.metric} {r.operator} {r.threshold}</code>
                            </div>
                            {r.description && <p className="text-sm text-slate-500 dark:text-slate-400 mt-2 ml-7">{r.description}</p>}
                        </div>
                    ))}
                    {rules.length === 0 && !loading && <div className="text-center text-slate-400 dark:text-slate-500 py-8">No gate rules yet</div>}
                </div>
            )}

            {tab === 'check' && (
                <div className="space-y-4">
                    <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm dark:border-slate-700/80 dark:bg-slate-800/60">
                        <div className="flex items-center justify-between gap-3 mb-4">
                            <div>
                                <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">Business metrics input</h3>
                                <p className="text-sm text-slate-500 dark:text-slate-400">Enter metrics from this regression run to check acceptance criteria.</p>
                            </div>
                            <button
                                onClick={runCheck}
                                disabled={checking || currentMetrics.length === 0}
                                className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-500 text-sm text-white hover:bg-emerald-600 disabled:opacity-50"
                            >
                                {checking ? <RefreshCw className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />} Run gate
                            </button>
                        </div>
                        {currentMetrics.length > 0 ? (
                            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                                {currentMetrics.map(metric => (
                                    <label key={metric} className="rounded-xl border border-slate-200 bg-slate-50/70 p-3 dark:border-slate-700 dark:bg-slate-900/30">
                                        <span className="text-sm font-medium text-slate-700 dark:text-slate-200">
                                            {metricLabels[metric] || metric}
                                        </span>
                                        <span className="block text-xs text-slate-400 mt-1">{metric}</span>
                                        <input
                                            type="number"
                                            step="0.01"
                                            value={metricDrafts[metric] ?? ''}
                                            onChange={e => setMetricDrafts(prev => ({ ...prev, [metric]: e.target.value }))}
                                            className="mt-3 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-emerald-500/30 dark:border-slate-600 dark:bg-slate-700 dark:text-white"
                                        />
                                    </label>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center text-slate-400 dark:text-slate-500 py-6">No metrics are available for input. Add or import rules first.</div>
                        )}
                    </div>

                    {checkResult ? (
                        <div className="card-hover-lift rounded-2xl border border-slate-200/60 bg-white/80 backdrop-blur-sm p-6 dark:border-slate-700/60 dark:bg-slate-800/60">
                            <div className="flex items-center gap-3 mb-4">
                                {(() => {
                                    const Icon = statusIcon[checkResult.status] || RefreshCw;
                                    return <Icon className={`w-6 h-6 ${statusColor[checkResult.status]}`} />;
                                })()}
                                <span className={`text-lg font-bold ${statusColor[checkResult.status]}`}>{checkResult.summary}</span>
                            </div>
                            <div className="space-y-2">
                                {(checkResult.checks || []).map(c => {
                                    const Icon = statusIcon[c.status] || RefreshCw;
                                    return (
                                        <div key={c.rule_name} className="flex items-center justify-between gap-4 py-2 px-3 rounded-xl bg-slate-50 dark:bg-slate-700/40">
                                            <div className="flex items-center gap-2">
                                                <Icon className={`w-4 h-4 ${statusColor[c.status]}`} />
                                                <span className="text-sm text-slate-800 dark:text-slate-200">{c.rule_name}</span>
                                            </div>
                                            <span className="text-sm text-slate-500 dark:text-slate-400">{c.message}</span>
                                        </div>
                                    );
                                })}
                            </div>
                            <div className="mt-4 text-xs text-slate-500 dark:text-slate-400">
                                Passed: {checkResult.passed_checks}/{checkResult.total_checks} | Failed: {checkResult.failed_checks}
                            </div>
                        </div>
                    ) : (
                        <div className="text-center text-slate-400 dark:text-slate-500 py-8">Enter metrics and click Run gate to view results</div>
                    )}
                </div>
            )}

            {tab === 'history' && (
                <div className="space-y-3">
                    {comparableTask && (
                        <div className="rounded-2xl border border-violet-200/60 bg-violet-50/70 p-4 dark:border-violet-500/20 dark:bg-violet-500/10">
                            <div className="text-sm font-semibold text-slate-800 dark:text-slate-100">Most recent comparison target</div>
                            <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500 dark:text-slate-300">
                                <span>Task: {comparableTask.task_id}</span>
                                <span>Rerun chain: {comparableTask.lineage_root_id || '-'}</span>
                                <span>Gate: {comparableTask.gate_summary?.status || 'pending'}</span>
                                {comparableGateHistory && <span>Historical verdict: {comparableGateHistory.verdict?.status || 'pending'}</span>}
                            </div>
                        </div>
                    )}
                    {filteredHistory.map((h, i) => {
                        const Icon = statusIcon[h.status] || RefreshCw;
                        return (
                            <div key={i} className="card-hover-lift rounded-2xl border border-slate-200/60 bg-white/80 backdrop-blur-sm p-4 dark:border-slate-700/60 dark:bg-slate-800/60">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <Icon className={`w-4 h-4 ${statusColor[h.status]}`} />
                                        <span className={`font-medium ${statusColor[h.status]}`}>{h.status.toUpperCase()}</span>
                                        <span className="text-xs text-slate-500 dark:text-slate-400">{h.run_id}</span>
                                    </div>
                                    <span className="text-xs text-slate-500 dark:text-slate-400">{new Date(h.timestamp * 1000).toLocaleString('en-US')}</span>
                                </div>
                            </div>
                        );
                    })}
                    {filteredHistory.length === 0 && !loading && (
                        <div className="text-center text-slate-400 dark:text-slate-500 py-8">
                            {runIdParam ? "No corresponding gate history exists for this task yet." : "No check history yet"}
                        </div>
                    )}
                </div>
            )}

            {showAddModal && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-md flex items-center justify-center z-50 animate-in fade-in duration-300">
                    <div className="bg-white/95 dark:bg-slate-800/95 backdrop-blur-xl border border-slate-200/80 dark:border-slate-700/80 rounded-2xl p-6 w-96 space-y-4 shadow-2xl shadow-black/20 dark:shadow-black/50 animate-in zoom-in-95 duration-300">
                        <h3 className="text-lg font-bold text-slate-900 dark:text-white">Add gate rule</h3>
                        {[
                            { label: "Rule name", key: 'name' },
                            { label: "Description", key: 'description' },
                        ].map(field => (
                            <div key={field.key}>
                                <label className="text-sm font-medium text-slate-600 dark:text-slate-400">{field.label}</label>
                                <input
                                    value={field.key === 'name' ? newRule.name : newRule.description}
                                    onChange={e => setNewRule(prev => ({ ...prev, [field.key]: e.target.value }))}
                                    className="w-full mt-1 px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-400 dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                                />
                            </div>
                        ))}
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="text-sm font-medium text-slate-600 dark:text-slate-400">Metrics</label>
                                <select
                                    value={newRule.metric}
                                    onChange={e => setNewRule(prev => ({ ...prev, metric: e.target.value }))}
                                    className="w-full mt-1 px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-900 text-sm dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                                >
                                    {Object.keys(metricLabels).map(metric => (
                                        <option key={metric} value={metric}>{metric}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="text-sm font-medium text-slate-600 dark:text-slate-400">Threshold</label>
                                <input
                                    type="number"
                                    step="0.01"
                                    value={newRule.threshold}
                                    onChange={e => setNewRule(prev => ({ ...prev, threshold: parseFloat(e.target.value) }))}
                                    className="w-full mt-1 px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-900 text-sm dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                                />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="text-sm font-medium text-slate-600 dark:text-slate-400">Operator</label>
                                <select
                                    value={newRule.operator}
                                    onChange={e => setNewRule(prev => ({ ...prev, operator: e.target.value }))}
                                    className="w-full mt-1 px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-900 text-sm dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                                >
                                    {['>=', '<=', '>', '<', '==', '!='].map(operator => (
                                        <option key={operator} value={operator}>{operator}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="text-sm font-medium text-slate-600 dark:text-slate-400">Level</label>
                                <select
                                    value={newRule.severity}
                                    onChange={e => setNewRule(prev => ({ ...prev, severity: e.target.value }))}
                                    className="w-full mt-1 px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-900 text-sm dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                                >
                                    {['blocking', 'warning', 'info'].map(severity => (
                                        <option key={severity} value={severity}>{severity}</option>
                                    ))}
                                </select>
                            </div>
                        </div>
                        <div className="flex gap-3 pt-2">
                            <button onClick={() => setShowAddModal(false)} className="flex-1 py-2 rounded-lg border border-slate-200 bg-white text-slate-600 text-sm hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600">Cancel</button>
                            <button onClick={addRule} disabled={!newRule.name} className="flex-1 py-2 rounded-lg bg-gradient-to-r from-emerald-500 to-emerald-600 text-white text-sm hover:from-emerald-600 hover:to-emerald-700 disabled:opacity-50">Add</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
