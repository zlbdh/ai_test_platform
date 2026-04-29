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
    goal_achievement: '目标达成率',
    step_accuracy: '步骤准确率',
    hallucination_score: '幻觉抑制分',
    healing_success_rate: '自愈成功率',
    token_efficiency: 'Token 效率',
    login_success_rate: '登录成功率',
    core_flow_pass_rate: '核心流程通过率',
    blocking_bug_count: '阻断缺陷数',
    unexplained_5xx_count: '未解释 5xx 数',
    critical_ui_error_count: '关键 UI 异常数',
    module_coverage_rate: '模块覆盖率',
    page_mapping_rate: '页面映射率',
    critical_page_missing_count: '关键页面缺失数',
    blocking_prototype_gap_count: '阻断级原型差异数',
    critical_field_missing_count: '关键字段缺失数',
    critical_state_transition_gap_count: '关键状态流转缺失数',
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
            title: pack?.playbook_title || '示例项目大平台原型测试包',
            description: '规则覆盖模块覆盖率、页面映射率、关键页面缺失、阻断级原型差异、关键字段缺失和关键状态流转缺失。',
        };
    }
    if (pack?.playbook_id === 'sample-first-regression' || rules.some(rule => rule.name.startsWith('sample_platform_'))) {
        return {
            title: pack?.playbook_title || '示例项目企业平台端首轮真实回归',
            description: '规则覆盖登录成功率、核心流程通过率、阻断缺陷数、未解释 5xx、关键页面异常数。',
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
                        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">质量门禁</h2>
                        <p className="text-sm text-slate-500 dark:text-slate-400">统一任务的深读结论页与业务准入检查点</p>
                    </div>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={() => void importRules('sample-first-regression')}
                        disabled={importingRules}
                        className="flex items-center gap-1.5 px-3 py-2 border border-emerald-200 bg-emerald-50 hover:bg-emerald-100 rounded-lg text-sm text-emerald-700 transition-colors shadow-sm disabled:opacity-50 dark:bg-emerald-900/20 dark:border-emerald-800/60 dark:text-emerald-300 dark:hover:bg-emerald-900/30"
                    >
                        {importingRules ? <RefreshCw className="w-4 h-4 animate-spin" /> : <BookOpen className="w-4 h-4" />}
                        {importingRules ? '导入中...' : '导入示例项目规则'}
                    </button>
                    <button
                        onClick={() => void importRules('sample-platform-prototype')}
                        disabled={importingRules}
                        className="flex items-center gap-1.5 px-3 py-2 border border-blue-200 bg-blue-50 hover:bg-blue-100 rounded-lg text-sm text-blue-700 transition-colors shadow-sm disabled:opacity-50 dark:bg-blue-900/20 dark:border-blue-800/60 dark:text-blue-300 dark:hover:bg-blue-900/30"
                    >
                        {importingRules ? <RefreshCw className="w-4 h-4 animate-spin" /> : <BookOpen className="w-4 h-4" />}
                        {importingRules ? '导入中...' : '导入大平台原型规则'}
                    </button>
                    <button onClick={() => setShowAddModal(true)} className="flex items-center gap-1.5 px-3 py-2 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg text-sm text-slate-700 transition-colors shadow-sm dark:bg-slate-800 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-700">
                        <Plus className="w-4 h-4" /> 添加规则
                    </button>
                    <button onClick={runCheck} disabled={checking || currentMetrics.length === 0} className="flex items-center gap-1.5 px-3 py-2 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 rounded-lg text-sm text-white transition-all disabled:opacity-50 shadow-sm">
                        {checking ? <RefreshCw className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />} 执行检查
                    </button>
                </div>
            </div>

            {(taskContextLoading || taskContext) && (
                <div className="rounded-2xl border border-violet-200 bg-violet-50/70 p-5 dark:border-violet-800/50 dark:bg-violet-900/10">
                    {taskContextLoading ? (
                        <div className="flex items-center gap-2 text-sm text-violet-600 dark:text-violet-300">
                            <RefreshCw className="h-4 w-4 animate-spin" />
                            正在加载统一任务上下文...
                        </div>
                    ) : taskContext ? (
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                            <div>
                                <p className="text-xs uppercase tracking-wide text-violet-500">来自统一测试任务</p>
                                <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">{taskContext.user_goal}</h3>
                                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                                    {taskContext.task_kind} · {taskContext.task_id} · 当前状态 {taskContext.status}
                                </p>
                                <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500 dark:text-slate-400">
                                    <span>执行组：{taskContext.execution_group_id || '-'}</span>
                                    <span>复跑链：{taskContext.lineage_root_id || '-'}</span>
                                    <span>run_id：{runIdParam || taskContext.task_id || '-'}</span>
                                    <span>{taskContext.rerun_from_task_id ? `来自复跑：${taskContext.rerun_from_task_id}` : '当前为首轮任务'}</span>
                                    <span>任务态：{statusMeta(taskContext.status).label}</span>
                                </div>
                                <div className="mt-3 flex flex-wrap items-center gap-2">
                                    <span className={`rounded-full px-3 py-1 text-xs font-medium ${taskGateColor}`}>
                                        当前 Gate：{taskContext.gate_summary?.status || 'pending'}
                                    </span>
                                    <span className="text-sm text-slate-600 dark:text-slate-300">
                                        {taskContext.gate_summary?.summary || '当前任务暂无门禁摘要。'}
                                    </span>
                                </div>
                                {taskContext.gate_summary?.decision_reason && (
                                    <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                                        判定原因：{taskContext.gate_summary.decision_reason}
                                    </div>
                                )}
                                {runIdParam && (
                                    <div className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                                        当前已聚焦 run_id = {runIdParam} 的门禁历史，并把任务指标带入“业务指标录入”区域。
                                        {historyStatusParam ? ` 同时过滤状态 = ${historyStatusParam}。` : ''}
                                    </div>
                                )}
                                {comparableTask && (
                                    <div className="mt-3 rounded-xl border border-violet-200/60 bg-white/80 px-3 py-3 text-xs text-slate-600 dark:border-violet-500/20 dark:bg-slate-900/50 dark:text-slate-300">
                                        <div className="font-semibold text-slate-700 dark:text-slate-100">最近一次可比复跑</div>
                                        <div className="mt-2 flex flex-wrap gap-3">
                                            <span>任务：{comparableTask.task_id}</span>
                                            <span>状态：{statusMeta(comparableTask.status).label}</span>
                                            <span>Gate：{comparableTask.gate_summary?.status || 'pending'}</span>
                                        </div>
                                        <div className="mt-2 text-slate-500 dark:text-slate-400">
                                            {comparableTask.gate_summary?.summary || '当前可比任务暂无门禁摘要。'}
                                        </div>
                                    </div>
                                )}
                                {comparableTask && comparisonSummary && (
                                    <div className="mt-3 rounded-xl border border-violet-200/60 bg-white/80 px-3 py-3 text-xs text-slate-600 dark:border-violet-500/20 dark:bg-slate-900/50 dark:text-slate-300">
                                        <div className="font-semibold text-slate-700 dark:text-slate-100">本次 vs 最近一次复跑</div>
                                        <div className="mt-2 grid gap-2 md:grid-cols-2">
                                            <div className="rounded-lg bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                                <div className="text-slate-400">Findings 数量</div>
                                                <div className="mt-1 text-slate-700 dark:text-slate-200">
                                                    本次 {comparisonSummary.currentFindingCount} / 上次 {comparisonSummary.comparableFindingCount}
                                                </div>
                                            </div>
                                            <div className="rounded-lg bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                                <div className="text-slate-400">高风险 Findings</div>
                                                <div className="mt-1 text-slate-700 dark:text-slate-200">
                                                    本次 {comparisonSummary.currentSeveritySummary.blocking + comparisonSummary.currentSeveritySummary.major}
                                                    {' / '}
                                                    上次 {comparisonSummary.comparableSeveritySummary.blocking + comparisonSummary.comparableSeveritySummary.major}
                                                </div>
                                            </div>
                                            <div className="rounded-lg bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                                <div className="text-slate-400">Gate 状态</div>
                                                <div className="mt-1 text-slate-700 dark:text-slate-200">
                                                    本次 {taskContext.gate_summary?.status || 'pending'} / 上次 {comparableTask.gate_summary?.status || 'pending'}
                                                </div>
                                            </div>
                                            <div className="rounded-lg bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                                <div className="text-slate-400">验证态</div>
                                                <div className="mt-1 text-slate-700 dark:text-slate-200">
                                                    本次 {verificationStateMeta(taskContext.verification_state).label}
                                                    {' / '}
                                                    上次 {verificationStateMeta(comparableTask.verification_state).label}
                                                </div>
                                            </div>
                                        </div>
                                        <div className="mt-2 rounded-lg bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                            <div className="text-slate-400">严重级别变化</div>
                                            <div className="mt-1 text-slate-700 dark:text-slate-200">
                                                本次：{formatFindingSeveritySummary(comparisonSummary.currentSeveritySummary)}
                                            </div>
                                            <div className="mt-1 text-slate-500 dark:text-slate-400">
                                                上次：{formatFindingSeveritySummary(comparisonSummary.comparableSeveritySummary)}
                                            </div>
                                        </div>
                                        <div className="mt-2 rounded-lg bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                            <div className="text-slate-400">判定原因变化</div>
                                            <div className="mt-1 text-slate-700 dark:text-slate-200">
                                                本次：{taskContext.gate_summary?.decision_reason || '当前没有结构化决策原因。'}
                                            </div>
                                            <div className="mt-1 text-slate-500 dark:text-slate-400">
                                                上次：{comparableTask.gate_summary?.decision_reason || '上次没有结构化决策原因。'}
                                            </div>
                                        </div>
                                        <div className="mt-2 rounded-lg bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                            <div className="flex items-center justify-between gap-3">
                                                <div className="text-slate-400">关键 Metrics 变化</div>
                                                <div className="text-[11px] text-slate-400">
                                                    {comparisonSummary.changedMetricCount > 0 ? `${comparisonSummary.changedMetricCount} 项变化` : '与上次一致'}
                                                </div>
                                            </div>
                                            <div className="mt-2 space-y-2">
                                                {comparisonSummary.metricChanges.length === 0 ? (
                                                    <div className="text-slate-400">当前没有可对比的 metrics。</div>
                                                ) : comparisonSummary.metricChanges.slice(0, 6).map((metric) => (
                                                    <div key={metric.key} className="rounded-lg border border-slate-200/70 bg-white px-3 py-3 dark:border-slate-700/70 dark:bg-slate-900/40">
                                                        <div className="flex items-center justify-between gap-3">
                                                            <div className="text-slate-400">{metric.key}</div>
                                                            <span className={`rounded-full px-2 py-0.5 text-[10px] ${metric.changed ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300' : 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-300'}`}>
                                                                {metric.changed ? '已变化' : '一致'}
                                                            </span>
                                                        </div>
                                                        <div className="mt-1 text-slate-700 dark:text-slate-200">本次：{formatMetricValue(metric.currentValue)}</div>
                                                        <div className="mt-1 text-slate-500 dark:text-slate-400">上次：{formatMetricValue(metric.comparableValue)}</div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                        <div className="mt-2 rounded-lg bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
                                            <div className="flex items-center justify-between gap-3">
                                                <div className="text-slate-400">Checks 变化</div>
                                                <div className="text-[11px] text-slate-400">
                                                    {changedGateChecks.length > 0 ? `${changedGateChecks.length} 条规则变化` : '与上次一致'}
                                                </div>
                                            </div>
                                            {!currentGateHistory ? (
                                                <div className="mt-2 text-slate-400">当前任务还没有可用的门禁历史 checks。</div>
                                            ) : !comparableGateHistory ? (
                                                <div className="mt-2 text-slate-400">最近一次复跑还没有可对比的门禁历史。</div>
                                            ) : (
                                                <div className="mt-2 space-y-2">
                                                    <div className="text-slate-500 dark:text-slate-400">
                                                        本次 {currentGateHistory.verdict?.failed_checks ?? 0}/{currentGateHistory.verdict?.total_checks ?? 0} 失败，
                                                        上次 {comparableGateHistory.verdict?.failed_checks ?? 0}/{comparableGateHistory.verdict?.total_checks ?? 0} 失败。
                                                    </div>
                                                    {(changedGateChecks.length > 0 ? changedGateChecks : gateCheckDiff).slice(0, 4).map((item) => (
                                                        <div key={item.ruleName} className="rounded-lg border border-slate-200/70 bg-white px-3 py-3 dark:border-slate-700/70 dark:bg-slate-900/40">
                                                            <div className="text-slate-700 dark:text-slate-200">{item.ruleName}</div>
                                                            <div className="mt-1 text-slate-500 dark:text-slate-400">
                                                                本次：{item.currentStatus} / 上次：{item.comparableStatus}
                                                            </div>
                                                            {(item.currentMessage || item.comparableMessage) && (
                                                                <div className="mt-1 text-[11px] text-slate-400">
                                                                    本次说明：{item.currentMessage || '无'}；上次说明：{item.comparableMessage || '无'}
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
                                    带入指标复核
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setTab('history')}
                                    className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 transition-colors hover:text-violet-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
                                >
                                    聚焦门禁历史
                                </button>
                                <button
                                    type="button"
                                    onClick={() => navigate(taskContext.execution_center_path)}
                                    className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 transition-colors hover:text-violet-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
                                >
                                    返回执行中心
                                </button>
                                <button
                                    type="button"
                                    onClick={() => navigate('/quality-gate')}
                                    className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 transition-colors hover:text-violet-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
                                >
                                    清除任务上下文
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
                            <p className="text-xs uppercase tracking-wide text-emerald-500">项目门禁</p>
                            <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">{rulePackSummary.title}</h3>
                            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                                {rulePackSummary.description}
                            </p>
                        </div>
                        {lastImportedCount > 0 && (
                            <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-emerald-700 shadow-sm dark:bg-slate-800 dark:text-emerald-300">
                                已导入 {lastImportedCount} 条规则
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
                        {{ rules: '门禁规则', check: '检查结果', history: '历史记录' }[t]}
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
                    {rules.length === 0 && !loading && <div className="text-center text-slate-400 dark:text-slate-500 py-8">暂无门禁规则</div>}
                </div>
            )}

            {tab === 'check' && (
                <div className="space-y-4">
                    <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm dark:border-slate-700/80 dark:bg-slate-800/60">
                        <div className="flex items-center justify-between gap-3 mb-4">
                            <div>
                                <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">业务指标录入</h3>
                                <p className="text-sm text-slate-500 dark:text-slate-400">按本次回归结果填写指标，执行准入检查。</p>
                            </div>
                            <button
                                onClick={runCheck}
                                disabled={checking || currentMetrics.length === 0}
                                className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-500 text-sm text-white hover:bg-emerald-600 disabled:opacity-50"
                            >
                                {checking ? <RefreshCw className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />} 运行门禁
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
                            <div className="text-center text-slate-400 dark:text-slate-500 py-6">暂无可录入指标，请先添加或导入规则。</div>
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
                                通过: {checkResult.passed_checks}/{checkResult.total_checks} | 失败: {checkResult.failed_checks}
                            </div>
                        </div>
                    ) : (
                        <div className="text-center text-slate-400 dark:text-slate-500 py-8">录入指标后点击“运行门禁”查看结果</div>
                    )}
                </div>
            )}

            {tab === 'history' && (
                <div className="space-y-3">
                    {comparableTask && (
                        <div className="rounded-2xl border border-violet-200/60 bg-violet-50/70 p-4 dark:border-violet-500/20 dark:bg-violet-500/10">
                            <div className="text-sm font-semibold text-slate-800 dark:text-slate-100">最近一次对比对象</div>
                            <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500 dark:text-slate-300">
                                <span>任务：{comparableTask.task_id}</span>
                                <span>复跑链：{comparableTask.lineage_root_id || '-'}</span>
                                <span>Gate：{comparableTask.gate_summary?.status || 'pending'}</span>
                                {comparableGateHistory && <span>历史 verdict：{comparableGateHistory.verdict?.status || 'pending'}</span>}
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
                                    <span className="text-xs text-slate-500 dark:text-slate-400">{new Date(h.timestamp * 1000).toLocaleString('zh-CN')}</span>
                                </div>
                            </div>
                        );
                    })}
                    {filteredHistory.length === 0 && !loading && (
                        <div className="text-center text-slate-400 dark:text-slate-500 py-8">
                            {runIdParam ? '当前任务还没有对应的门禁历史。' : '暂无检查历史'}
                        </div>
                    )}
                </div>
            )}

            {showAddModal && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-md flex items-center justify-center z-50 animate-in fade-in duration-300">
                    <div className="bg-white/95 dark:bg-slate-800/95 backdrop-blur-xl border border-slate-200/80 dark:border-slate-700/80 rounded-2xl p-6 w-96 space-y-4 shadow-2xl shadow-black/20 dark:shadow-black/50 animate-in zoom-in-95 duration-300">
                        <h3 className="text-lg font-bold text-slate-900 dark:text-white">添加门禁规则</h3>
                        {[
                            { label: '规则名称', key: 'name' },
                            { label: '描述', key: 'description' },
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
                                <label className="text-sm font-medium text-slate-600 dark:text-slate-400">指标</label>
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
                                <label className="text-sm font-medium text-slate-600 dark:text-slate-400">阈值</label>
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
                                <label className="text-sm font-medium text-slate-600 dark:text-slate-400">操作符</label>
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
                                <label className="text-sm font-medium text-slate-600 dark:text-slate-400">级别</label>
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
                            <button onClick={() => setShowAddModal(false)} className="flex-1 py-2 rounded-lg border border-slate-200 bg-white text-slate-600 text-sm hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600">取消</button>
                            <button onClick={addRule} disabled={!newRule.name} className="flex-1 py-2 rounded-lg bg-gradient-to-r from-emerald-500 to-emerald-600 text-white text-sm hover:from-emerald-600 hover:to-emerald-700 disabled:opacity-50">添加</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
