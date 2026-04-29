import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
    Activity, CheckCircle2, XCircle, Clock, Trash2, ChevronDown, ChevronRight,
    Globe, Cpu, Filter, Timer, AlertTriangle, FileText, Shield,
    Search, ChevronLeft as PageLeft, ChevronRight as PageRight, CalendarDays,
    ExternalLink, Camera, Layers, RotateCcw
} from './icons';
import { API_BASE_URL, API_ENDPOINTS } from '../config';
import { getExecutionDetail } from '../services/backendService';
import { getFrontdoorTask, listFrontdoorTasks, type FrontdoorTask } from '../services/frontdoorTaskService';
import { useConfirmDialog, ConfirmDialog } from './ui/ConfirmDialog';
import GalleryPanel from './GalleryPanel';
import ReportDropdown from './ReportDropdown';
import {
    buildFrontdoorDeepView,
    gateMeta,
    resolveExecutionGroupTagSummary,
    statusMeta,
} from '../pages/frontdoorTaskShared';

interface HistoryRecord {
    task_id: string;
    requirement: string;
    requirement_display?: string;
    status: string;
    log_count: number;
    error_count: number;
    duration_ms: number;
    target_url: string;
    mode: string;
    created_at: string;
    execution_group_id: string;
    record_kind: 'root' | 'child';
    requirement_raw_present?: number;
    task_text_state?: string;
}

interface HistoryGroup {
    group_id: string;
    title: string;
    requirement: string;
    requirement_display?: string;
    status: string;
    target_url: string;
    mode: string;
    created_at: string;
    updated_at: string;
    record_count: number;
    log_count: number;
    error_count: number;
    duration_ms: number;
    root_task_id: string;
    records: HistoryRecord[];
    requirement_raw_present?: number;
    task_text_state?: string;
}

interface DetailRecord extends HistoryRecord {
    logs: Array<{ type?: string; content?: string }>;
}

interface ReportSummary {
    id?: string;
    task_id?: string;
    timestamp: string;
    report_scope?: 'record' | 'summary' | 'batch';
    report_url?: string;
    allure_url?: string;
}

type FilterStatus = 'all' | 'success' | 'healed' | 'failed';
type DateRange = 'all' | 'today' | '3d' | '7d' | '30d';
type ModeFilter = 'all' | 'smart' | 'quick' | 'special';
type DetailTab = 'log' | 'gallery';

const MODE_LABELS: Record<string, string> = {
    commander: '军团中心',
    smart: 'Smart Agent',
    quick: 'Quick Plan',
    api_rest: 'API 测试',
    api_graphql: 'GraphQL 测试',
    performance: '性能测试',
    security: '安全扫描',
    accessibility: '无障碍测试',
    i18n: 'i18n 测试',
    compliance: '合规审计',
    database: '数据库测试',
    api_workbench: 'API 工作台',
    graphql: 'GraphQL 测试',
    grpc: 'gRPC 测试',
    websocket: 'WebSocket 测试',
    chaos: '混沌测试',
    mobile: '移动端测试',
};

export function resolveFocusedGroupPage(groups: Array<{ group_id: string }>, groupId: string, pageSize: number): number | null {
    const normalized = (groupId || '').trim();
    if (!normalized) return null;
    const index = groups.findIndex(group => group.group_id === normalized);
    if (index < 0) return null;
    return Math.floor(index / pageSize) + 1;
}

export function resolveFocusedRecordId(
    groups: Array<{ group_id: string; records: Array<{ task_id: string }> }>,
    groupId: string,
    recordId: string,
): string | null {
    const normalizedGroupId = (groupId || '').trim();
    const normalizedRecordId = (recordId || '').trim();
    if (!normalizedGroupId || !normalizedRecordId) return null;
    const targetGroup = groups.find(group => group.group_id === normalizedGroupId);
    if (!targetGroup) return null;
    return targetGroup.records.some(record => record.task_id === normalizedRecordId) ? normalizedRecordId : null;
}

function formatDuration(ms: number): string {
    if (!ms || ms <= 0) return '-';
    if (ms < 1000) return `${ms}ms`;
    const s = Math.floor(ms / 1000);
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    const remainS = s % 60;
    return remainS > 0 ? `${m}m ${remainS}s` : `${m}m`;
}

function formatTime(dateStr: string): string {
    if (!dateStr) return '未知时间';
    try {
        return new Date(dateStr.replace(' ', 'T')).toLocaleString('zh-CN', {
            month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
    } catch {
        return dateStr;
    }
}

function isRecoveredStatus(status: string): boolean {
    return status === 'healed' || status === 'recovered';
}

function isPureSuccessStatus(status: string): boolean {
    return status === 'success';
}

function isSuccessfulStatus(status: string): boolean {
    return isPureSuccessStatus(status) || isRecoveredStatus(status);
}

function buildReportUrl(report?: ReportSummary | null): string | null {
    const rawUrl = report?.allure_url || report?.report_url;
    if (!rawUrl) return null;
    if (rawUrl.startsWith('http://') || rawUrl.startsWith('https://')) return rawUrl;
    return `${API_BASE_URL}${rawUrl.startsWith('/') ? rawUrl : `/${rawUrl}`}`;
}

const SummaryCards: React.FC<{ groups: HistoryGroup[] }> = ({ groups }) => {
    const total = groups.length;
    const successCount = groups.filter(group => isSuccessfulStatus(group.status)).length;
    const rate = total > 0 ? Math.round((successCount / total) * 100) : 0;
    const avgDuration = total > 0 ? Math.round(groups.reduce((sum, group) => sum + (group.duration_ms || 0), 0) / total) : 0;
    const cards = [
        { label: '总测试批次', value: `${total}`, icon: <Layers className="w-4 h-4" />, color: 'text-indigo-600 dark:text-indigo-400', bg: 'bg-indigo-50 dark:bg-indigo-500/10' },
        { label: '批次成功率', value: `${rate}%`, icon: <CheckCircle2 className="w-4 h-4" />, color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-500/10' },
        { label: '平均批次时长', value: formatDuration(avgDuration), icon: <Timer className="w-4 h-4" />, color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-500/10' },
    ];
    return <div className="grid grid-cols-3 gap-4 mb-6">{cards.map(card => <div key={card.label} className={`${card.bg} rounded-xl p-4 border border-transparent`}><div className={`flex items-center gap-2 ${card.color} mb-1`}>{card.icon}<span className="text-xs font-medium uppercase tracking-wider">{card.label}</span></div><div className="text-2xl font-bold text-slate-900 dark:text-white">{card.value}</div></div>)}</div>;
};

const StatusFilter: React.FC<{ filter: FilterStatus; onChange: (value: FilterStatus) => void; counts: { all: number; success: number; healed: number; failed: number } }> = ({ filter, onChange, counts }) => {
    const tabs: { key: FilterStatus; label: string; count: number }[] = [
        { key: 'all', label: '全部', count: counts.all },
        { key: 'success', label: '✓ 成功', count: counts.success },
        { key: 'healed', label: '♡ 自愈', count: counts.healed },
        { key: 'failed', label: '✗ 失败', count: counts.failed },
    ];
    return <div className="flex gap-1 bg-slate-100 dark:bg-slate-800 rounded-lg p-1">{tabs.map(tab => <button key={tab.key} onClick={() => onChange(tab.key)} className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${filter === tab.key ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm' : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300'}`}>{tab.label} ({tab.count})</button>)}</div>;
};

const LogPanel: React.FC<{ taskId: string; isOpen: boolean }> = ({ taskId, isOpen }) => {
    const [detail, setDetail] = useState<DetailRecord | null>(null);
    const [loading, setLoading] = useState(false);
    useEffect(() => {
        if (!isOpen) return;
        setLoading(true);
        getExecutionDetail(taskId)
            .then(data => setDetail(data as unknown as DetailRecord))
            .catch(() => setDetail(null))
            .finally(() => setLoading(false));
    }, [isOpen, taskId]);
    if (!isOpen) return null;
    if (loading) return <div className="text-xs text-slate-400 p-3">加载日志中...</div>;
    if (!detail?.logs?.length) return <div className="text-xs text-slate-500 p-3 bg-slate-100 dark:bg-slate-800/50 rounded-lg">暂无日志数据</div>;
    return (
        <div className="bg-slate-950 rounded-lg p-3 max-h-64 overflow-y-auto custom-scrollbar border border-slate-800">
            <div className="flex items-center gap-2 mb-2 pb-2 border-b border-slate-800">
                <FileText className="w-3 h-3 text-slate-500" />
                <span className="text-[10px] text-slate-500 uppercase tracking-wider">执行日志 · {detail.logs.length} 条 · {detail.error_count} 错误</span>
                {detail.task_text_state === 'broken_fallback' && (
                    <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-300">
                        <AlertTriangle className="w-3 h-3" />
                        编码已回退显示
                    </span>
                )}
            </div>
            {detail.logs.map((log, index) => {
                const isError = log.type === 'error';
                const content = log.content || JSON.stringify(log);
                return <div key={`${taskId}_${index}`} className={`text-xs font-mono py-0.5 leading-relaxed ${isError ? 'text-red-400' : 'text-slate-400'}`}><span className="text-slate-600 select-none mr-2">{String(index + 1).padStart(3, ' ')}</span>{content}</div>;
            })}
        </div>
    );
};

const ExecutionHistory: React.FC = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [groups, setGroups] = useState<HistoryGroup[]>([]);
    const [reportMap, setReportMap] = useState<Record<string, ReportSummary>>({});
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState<FilterStatus>('all');
    const [keyword, setKeyword] = useState('');
    const [urlFilter, setUrlFilter] = useState('');
    const [dateRange, setDateRange] = useState<DateRange>('all');
    const [modeFilter, setModeFilter] = useState<ModeFilter>('all');
    const [page, setPage] = useState(1);
    const [expandedGroupId, setExpandedGroupId] = useState<string | null>(null);
    const [expandedRecordId, setExpandedRecordId] = useState<string | null>(null);
    const [detailTab, setDetailTab] = useState<DetailTab>('log');
    const [taskContext, setTaskContext] = useState<FrontdoorTask | null>(null);
    const [taskContextLoading, setTaskContextLoading] = useState(false);
    const [lineageTasks, setLineageTasks] = useState<FrontdoorTask[]>([]);
    const [relatedTasks, setRelatedTasks] = useState<FrontdoorTask[]>([]);
    const { confirm, dialogProps } = useConfirmDialog();
    const focusedGroupId = (searchParams.get('group') || '').trim();
    const focusedRecordId = (searchParams.get('record') || '').trim();
    const focusedTaskId = (searchParams.get('task_id') || '').trim();
    const focusedLineageRootId = (searchParams.get('lineage_root_id') || '').trim();

    const loadHistory = useCallback(async () => {
        try {
            const res = await fetch(`${API_ENDPOINTS.history.list}?view=groups&limit=200`);
            if (!res.ok) return;
            const data = await res.json();
            setGroups(Array.isArray(data?.items) ? data.items : []);
        } finally {
            setLoading(false);
        }
    }, []);

    const loadReportMap = useCallback(async () => {
        try {
            const res = await fetch(`${API_ENDPOINTS.report.history}?limit=200`);
            if (!res.ok) return;
            const data = await res.json();
            const items = Array.isArray(data?.history) ? data.history as ReportSummary[] : [];
            const nextMap: Record<string, ReportSummary> = {};
            for (const item of items) {
                if (!item?.task_id || nextMap[item.task_id]) continue;
                nextMap[item.task_id] = item;
            }
            setReportMap(nextMap);
        } catch {
            // silent
        }
    }, []);

    useEffect(() => {
        loadHistory();
        loadReportMap();
        const timer = setInterval(() => {
            loadHistory();
            loadReportMap();
        }, 10000);
        return () => clearInterval(timer);
    }, [loadHistory, loadReportMap]);

    useEffect(() => {
        let active = true;
        if (!focusedTaskId) {
            setTaskContext(null);
            if (!focusedLineageRootId) setLineageTasks([]);
            setRelatedTasks([]);
            setTaskContextLoading(false);
            return () => {
                active = false;
            };
        }
        setTaskContextLoading(true);
        void getFrontdoorTask(focusedTaskId)
            .then(async (task) => {
                if (!active) return;
                setTaskContext(task);
                const lineageRoot = task.lineage_root_id || focusedLineageRootId;
                if (!lineageRoot) {
                    setLineageTasks([]);
                } else {
                    try {
                        const tasks = await listFrontdoorTasks({ limit: 10, lineageRootId: lineageRoot });
                        if (!active) return;
                        setLineageTasks(tasks);
                    } catch {
                        if (!active) return;
                        setLineageTasks([]);
                    }
                }
                try {
                    const tasks = await listFrontdoorTasks({ limit: 8, taskKind: task.task_kind });
                    if (!active) return;
                    setRelatedTasks(tasks);
                } catch {
                    if (!active) return;
                    setRelatedTasks([]);
                }
            })
            .catch(() => {
                if (!active) return;
                setTaskContext(null);
                setLineageTasks([]);
                setRelatedTasks([]);
            })
            .finally(() => {
                if (!active) return;
                setTaskContextLoading(false);
            });
        return () => {
            active = false;
        };
    }, [focusedLineageRootId, focusedTaskId]);

    const deepView = useMemo(
        () => buildFrontdoorDeepView({
            currentTask: taskContext,
            currentTaskId: focusedTaskId,
            lineageTasks,
            sameTaskKindTasks: relatedTasks,
            maxSameTaskKindReferences: 4,
        }),
        [focusedTaskId, lineageTasks, relatedTasks, taskContext],
    );
    const { lineageContext, sameTaskKindReferences } = deepView;

    const handleGenerateReport = async (event: React.MouseEvent, id: string, hasExistingReport: boolean) => {
        event.stopPropagation();
        const res = await fetch(API_ENDPOINTS.report.generate, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_id: id })
        });
        const data = await res.json();
        if (!res.ok || data.status === 'error') {
            alert(`生成失败: ${data.message || '未知错误'}`);
            return;
        }
        await loadReportMap();
        const reportUrl = buildReportUrl({ report_url: data.report_url, allure_url: data.allure_url, timestamp: new Date().toISOString() });
        if (reportUrl) window.open(reportUrl, '_blank', 'noopener,noreferrer');
        alert(`${hasExistingReport ? '重新生成' : '生成'}成功。${reportUrl ? '\n已自动打开最新测试报告。' : ''}`);
    };

    const handleDelete = async (id: string, label: string) => {
        const ok = await confirm('删除记录', `确定要删除这条${label}吗？`);
        if (!ok) return;
        await fetch(API_ENDPOINTS.history.delete(id), { method: 'DELETE' });
        await loadHistory();
        await loadReportMap();
        if (expandedGroupId === id) setExpandedGroupId(null);
        if (expandedRecordId === id) setExpandedRecordId(null);
    };

    const handleClearAll = async () => {
        const ok = await confirm('清空全部', `确定要清空全部 ${groups.length} 个测试批次吗？此操作不可恢复。`);
        if (!ok) return;
        await fetch(API_ENDPOINTS.history.clear, { method: 'DELETE' });
        setGroups([]);
        setExpandedGroupId(null);
        setExpandedRecordId(null);
    };

    const filtered = useMemo(() => {
        const now = Date.now();
        const dayMs = 86400000;
        return groups.filter(group => {
            if (filter === 'success' && !isPureSuccessStatus(group.status)) return false;
            if (filter === 'healed' && !isRecoveredStatus(group.status)) return false;
            if (filter === 'failed' && isSuccessfulStatus(group.status)) return false;
            if (keyword) {
                const kw = keyword.toLowerCase();
                const matched = [
                    group.title,
                    group.requirement,
                    group.requirement_display,
                    ...group.records.flatMap(record => [record.requirement, record.requirement_display]),
                ].some(value => (value || '').toLowerCase().includes(kw));
                if (!matched) return false;
            }
            if (urlFilter) {
                const matched = [group.target_url, ...group.records.map(record => record.target_url)].some(value => (value || '').toLowerCase().includes(urlFilter.toLowerCase()));
                if (!matched) return false;
            }
            const timeValue = group.updated_at || group.created_at;
            if (dateRange !== 'all' && timeValue) {
                const ts = new Date(timeValue.replace(' ', 'T')).getTime();
                const cutoff = dateRange === 'today' ? now - dayMs : dateRange === '3d' ? now - 3 * dayMs : dateRange === '7d' ? now - 7 * dayMs : now - 30 * dayMs;
                if (ts < cutoff) return false;
            }
            if (modeFilter !== 'all') {
                const values = [group.mode, ...group.records.map(record => record.mode)];
                const matched = modeFilter === 'special' ? values.some(mode => mode !== 'smart' && mode !== 'quick') : values.includes(modeFilter);
                if (!matched) return false;
            }
            return true;
        });
    }, [groups, filter, keyword, urlFilter, dateRange, modeFilter]);

    const PAGE_SIZE = 12;
    const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
    const safePage = Math.min(page, totalPages);
    const paged = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
    if (page !== safePage) setPage(safePage);

    useEffect(() => {
        const targetPage = resolveFocusedGroupPage(filtered, focusedGroupId, PAGE_SIZE);
        if (!focusedGroupId || !targetPage) return;
        let detailChanged = false;
        if (page !== targetPage) {
            setPage(targetPage);
        }
        if (expandedGroupId !== focusedGroupId) {
            setExpandedGroupId(focusedGroupId);
            detailChanged = true;
            if (!focusedRecordId) {
                setExpandedRecordId(null);
            }
        }
        if (focusedRecordId) {
            const targetRecordId = resolveFocusedRecordId(filtered, focusedGroupId, focusedRecordId);
            if (targetRecordId && expandedRecordId !== targetRecordId) {
                setExpandedRecordId(targetRecordId);
                detailChanged = true;
            }
        }
        if (detailChanged) {
            setDetailTab('log');
        }
    }, [filtered, focusedGroupId, focusedRecordId, page, expandedGroupId, expandedRecordId]);

    const counts = {
        all: groups.length,
        success: groups.filter(group => isPureSuccessStatus(group.status)).length,
        healed: groups.filter(group => isRecoveredStatus(group.status)).length,
        failed: groups.filter(group => !isSuccessfulStatus(group.status)).length,
    };

    if (loading) return <div className="flex items-center justify-center h-full"><div className="text-center text-slate-500"><Activity className="w-10 h-10 mx-auto mb-3 opacity-30 animate-spin" /><p className="text-sm">加载执行中心...</p></div></div>;
    if (groups.length === 0) return <div className="flex items-center justify-center h-full text-slate-500"><div className="text-center"><Activity className="w-12 h-12 mx-auto mb-4 opacity-15" /><p className="font-medium">暂无执行记录</p><p className="text-sm text-slate-400 mt-2">执行测试后，这里会按“测试批次 / 单条记录”结构展示</p></div></div>;

    return (
        <div className="space-y-4 h-full flex flex-col animate-in fade-in duration-500">
            <ConfirmDialog {...dialogProps} />
            <SummaryCards groups={groups} />
            {(taskContextLoading || taskContext) && (
                <div className="rounded-2xl border border-violet-200/70 bg-violet-50/70 p-4 shadow-sm dark:border-violet-500/20 dark:bg-violet-500/10">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                        <div className="space-y-2">
                            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-violet-500">
                                <RotateCcw className="w-3.5 h-3.5" />
                                当前任务上下文
                            </div>
                            {taskContextLoading && !taskContext ? (
                                <div className="text-sm text-slate-500 dark:text-slate-300">正在从统一任务链恢复当前上下文…</div>
                            ) : taskContext ? (
                                <>
                                    <div className="text-sm font-semibold text-slate-900 dark:text-white">{taskContext.user_goal}</div>
                                    <div className="flex flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-300">
                                        <span>任务 ID：{taskContext.task_id}</span>
                                        <span>执行组：{taskContext.execution_group_id || '-'}</span>
                                        <span>复跑链：{taskContext.lineage_root_id || focusedLineageRootId || '-'}</span>
                                        <span>{taskContext.rerun_from_task_id ? `来自复跑：${taskContext.rerun_from_task_id}` : '当前为首轮任务'}</span>
                                    </div>
                                    <div className="flex flex-wrap gap-3 text-xs text-slate-500 dark:text-slate-300">
                                        <span>任务状态：{statusMeta(taskContext.status).label}</span>
                                        <span>门禁结论：{gateMeta(taskContext.gate_summary?.status || '').label}</span>
                                        {lineageContext.currentIndex >= 0 && (
                                            <span>当前位于复跑链第 {lineageContext.currentIndex + 1} / {lineageContext.sortedTasks.length} 个任务</span>
                                        )}
                                    </div>
                                    {(lineageContext.olderTask || lineageContext.newerTask || lineageContext.comparableTask) && (
                                        <div className="rounded-xl border border-violet-200/60 bg-white/80 px-3 py-3 text-xs text-slate-600 dark:border-violet-500/20 dark:bg-slate-900/60 dark:text-slate-300">
                                            <div className="font-semibold text-slate-700 dark:text-slate-100">复跑链摘要</div>
                                            <div className="mt-2 flex flex-wrap gap-3">
                                                {lineageContext.olderTask && <span>前一次：{lineageContext.olderTask.task_id}</span>}
                                                {lineageContext.newerTask && <span>后一次：{lineageContext.newerTask.task_id}</span>}
                                                {lineageContext.comparableTask && <span>最近一次可比任务：{lineageContext.comparableTask.task_id}</span>}
                                            </div>
                                        </div>
                                    )}
                                    {lineageContext.sortedTasks.length > 0 && (
                                        <div className="rounded-xl border border-violet-200/60 bg-white/80 px-3 py-3 text-xs text-slate-600 dark:border-violet-500/20 dark:bg-slate-900/60 dark:text-slate-300">
                                            <div className="font-semibold text-slate-700 dark:text-slate-100">链路时间线</div>
                                            <div className="mt-2 space-y-2">
                                                {lineageContext.sortedTasks.map((task, index) => {
                                                    const isCurrent = task.task_id === (taskContext?.task_id || focusedTaskId);
                                                    return (
                                                        <button
                                                            key={task.task_id}
                                                            type="button"
                                                            onClick={() => navigate(`/tasks/${task.task_id}`)}
                                                            className={`flex w-full items-start justify-between gap-3 rounded-xl border px-3 py-3 text-left transition-colors ${
                                                                isCurrent
                                                                    ? 'border-violet-300 bg-violet-50 dark:border-violet-500/40 dark:bg-violet-500/10'
                                                                    : 'border-transparent bg-slate-50 hover:bg-violet-50 dark:bg-slate-800/60 dark:hover:bg-violet-500/10'
                                                            }`}
                                                        >
                                                            <div className="min-w-0">
                                                                <div className="flex flex-wrap items-center gap-2">
                                                                    <span className="font-medium text-slate-700 dark:text-slate-100">
                                                                        第 {lineageContext.sortedTasks.length - index} 次
                                                                    </span>
                                                                    {isCurrent && (
                                                                        <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[10px] text-violet-700 dark:bg-violet-500/20 dark:text-violet-300">
                                                                            当前任务
                                                                        </span>
                                                                    )}
                                                                </div>
                                                                <div className="mt-1 truncate text-slate-600 dark:text-slate-300">{task.user_goal}</div>
                                                                <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-slate-400">
                                                                    <span>{task.task_id}</span>
                                                                    <span>{task.execution_group_id || '-'}</span>
                                                                    <span>{formatTime(task.completed_at || task.created_at || '')}</span>
                                                                </div>
                                                            </div>
                                                            <div className="shrink-0 text-right">
                                                                <div className="text-[11px] text-slate-500 dark:text-slate-400">{statusMeta(task.status).label}</div>
                                                                <div className="mt-1 text-[11px] text-slate-400">{gateMeta(task.gate_summary?.status || '').label}</div>
                                                            </div>
                                                        </button>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    )}
                                    {sameTaskKindReferences.length > 0 && (
                                        <div className="rounded-xl border border-violet-200/60 bg-white/80 px-3 py-3 text-xs text-slate-600 dark:border-violet-500/20 dark:bg-slate-900/60 dark:text-slate-300">
                                            <div className="font-semibold text-slate-700 dark:text-slate-100">同任务类型参考</div>
                                            <div className="mt-2 space-y-2">
                                                {sameTaskKindReferences.map((task) => (
                                                    <button
                                                        key={task.task_id}
                                                        type="button"
                                                        onClick={() => navigate(`/tasks/${task.task_id}`)}
                                                        className="flex w-full items-start justify-between gap-3 rounded-xl bg-slate-50 px-3 py-3 text-left transition-colors hover:bg-violet-50 dark:bg-slate-800/60 dark:hover:bg-violet-500/10"
                                                    >
                                                        <div className="min-w-0">
                                                            <div className="truncate font-medium text-slate-700 dark:text-slate-100">{task.user_goal}</div>
                                                            <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-slate-400">
                                                                <span>{task.task_id}</span>
                                                                <span>{task.execution_group_id || '-'}</span>
                                                                <span>{formatTime(task.completed_at || task.created_at || '')}</span>
                                                            </div>
                                                        </div>
                                                        <div className="shrink-0 text-right">
                                                            <div className="text-[11px] text-slate-500 dark:text-slate-400">{statusMeta(task.status).label}</div>
                                                            <div className="mt-1 text-[11px] text-slate-400">{gateMeta(task.gate_summary?.status || '').label}</div>
                                                        </div>
                                                    </button>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </>
                            ) : (
                                <div className="text-sm text-slate-500 dark:text-slate-300">当前没有可恢复的统一任务上下文。</div>
                            )}
                        </div>
                        {taskContext && (
                            <div className="flex flex-wrap gap-2">
                                <button
                                    type="button"
                                    onClick={() => navigate(`/tasks/${taskContext.task_id}`)}
                                    className="rounded-lg border border-violet-200 bg-white px-3 py-2 text-sm text-violet-700 transition-colors hover:bg-violet-50 dark:border-violet-500/30 dark:bg-slate-900 dark:text-violet-300 dark:hover:bg-violet-500/10"
                                >
                                    返回任务结果
                                </button>
                                <button
                                    type="button"
                                    onClick={() => navigate(taskContext.quality_gate_path)}
                                    className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 transition-colors hover:text-violet-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                                >
                                    查看质量门禁
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            )}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div>
                        <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2"><div className="p-2 rounded-lg bg-indigo-500/10"><Layers className="w-5 h-5 text-indigo-500" /></div>执行中心</h2>
                        <div className="mt-1 text-xs text-slate-400">统一查看当前任务、复跑链、执行组与同任务类型参考</div>
                    </div>
                    <StatusFilter filter={filter} onChange={(value) => { setFilter(value); setPage(1); }} counts={counts} />
                </div>
                <div className="flex items-center gap-2"><ReportDropdown /><button onClick={handleClearAll} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors"><Trash2 className="w-3.5 h-3.5" />清空全部</button></div>
            </div>

            <div className="flex items-center gap-3 flex-wrap">
                <div className="relative flex-1 min-w-[200px] max-w-[300px]"><Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" /><input type="text" placeholder="搜索批次或单条记录..." value={keyword} onChange={(e) => { setKeyword(e.target.value); setPage(1); }} className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 outline-none transition-all" /></div>
                <div className="relative min-w-[180px] max-w-[250px]"><Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" /><input type="text" placeholder="筛选目标 URL..." value={urlFilter} onChange={(e) => { setUrlFilter(e.target.value); setPage(1); }} className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 outline-none transition-all" /></div>
                <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 rounded-lg p-0.5"><CalendarDays className="w-3.5 h-3.5 text-slate-400 ml-2" />{([['all', '全部'], ['today', '今天'], ['3d', '3天'], ['7d', '7天'], ['30d', '30天']] as [DateRange, string][]).map(([key, label]) => <button key={key} onClick={() => { setDateRange(key); setPage(1); }} className={`px-2 py-1 rounded-md text-[11px] font-medium transition-all ${dateRange === key ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm' : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'}`}>{label}</button>)}</div>
                <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 rounded-lg p-0.5"><Cpu className="w-3.5 h-3.5 text-slate-400 ml-2" />{([['all', '全部'], ['smart', 'Smart'], ['quick', 'Quick'], ['special', '专项']] as [ModeFilter, string][]).map(([key, label]) => <button key={key} onClick={() => { setModeFilter(key); setPage(1); }} className={`px-2 py-1 rounded-md text-[11px] font-medium transition-all ${modeFilter === key ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm' : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'}`}>{label}</button>)}</div>
                {(keyword || urlFilter || dateRange !== 'all' || modeFilter !== 'all') && <button onClick={() => { setKeyword(''); setUrlFilter(''); setDateRange('all'); setModeFilter('all'); setPage(1); }} className="text-xs text-slate-500 hover:text-indigo-500 transition-colors">清除筛选</button>}
                <span className="text-[10px] text-slate-400 ml-auto">共 {filtered.length} 个测试批次</span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-1 custom-scrollbar">
                {paged.map(group => {
                    const groupExpanded = expandedGroupId === group.group_id;
                    const groupSuccess = isPureSuccessStatus(group.status);
                    const groupHealed = isRecoveredStatus(group.status);
                    const groupReport = reportMap[group.group_id];
                    const groupReportUrl = buildReportUrl(groupReport);
                    const groupTagSummary = resolveExecutionGroupTagSummary(group.group_id, deepView);
                    return (
                        <div key={group.group_id} className={`rounded-xl border transition-all duration-200 ${groupSuccess ? 'border-emerald-200/50 dark:border-emerald-500/20' : groupHealed ? 'border-teal-200/50 dark:border-teal-500/20' : 'border-red-200/50 dark:border-red-500/20'} bg-white dark:bg-slate-800/50`}>
                            <div className="flex items-center gap-4 p-4 cursor-pointer select-none" onClick={() => { setExpandedGroupId(groupExpanded ? null : group.group_id); setExpandedRecordId(null); setDetailTab('log'); }}>
                                <div className="text-slate-400 shrink-0">{groupExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}</div>
                                <div className="shrink-0">{groupSuccess ? <CheckCircle2 className="w-5 h-5 text-emerald-500" /> : groupHealed ? <Shield className="w-5 h-5 text-teal-500" /> : <XCircle className="w-5 h-5 text-red-500" />}</div>
                                <div className="flex-1 min-w-0"><h3 className="text-sm font-semibold text-slate-900 dark:text-white truncate">{group.title || group.requirement_display || '未命名测试批次'}</h3><div className="flex items-center gap-3 mt-1 text-xs text-slate-400"><span className="flex items-center gap-1"><Layers className="w-3 h-3" />单次记录</span><span className="flex items-center gap-1"><Cpu className="w-3 h-3" />{MODE_LABELS[group.mode || 'smart'] || group.mode || 'Smart Agent'}</span>{group.target_url && <span className="flex items-center gap-1 truncate max-w-[220px]" title={group.target_url}><Globe className="w-3 h-3" />{group.target_url.replace(/^https?:\/\//, '')}</span>}</div></div>
                                <div className="shrink-0 flex items-center gap-2">
                                    {groupTagSummary.isCurrentTaskGroup && <span className="flex items-center gap-1 text-xs text-violet-600 dark:text-violet-300 bg-violet-50 dark:bg-violet-500/10 px-2 py-0.5 rounded-full">当前任务执行组</span>}
                                    {groupTagSummary.isSameLineageGroup && <span className="flex items-center gap-1 text-xs text-sky-600 dark:text-sky-300 bg-sky-50 dark:bg-sky-500/10 px-2 py-0.5 rounded-full">同复跑链</span>}
                                    {groupTagSummary.isSameTaskKindReferenceGroup && <span className="flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-500/10 px-2 py-0.5 rounded-full">同任务类型参考</span>}
                                    {groupReport && <span className="flex items-center gap-1 text-xs text-indigo-600 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-500/10 px-2 py-0.5 rounded-full"><FileText className="w-3 h-3" />测试报告</span>}
                                    <span className="text-xs text-slate-500 bg-slate-100 dark:bg-slate-700/50 px-2 py-0.5 rounded-full">{group.record_count} 条单条记录</span>
                                    {group.error_count > 0 && <span className="flex items-center gap-1 text-xs text-red-500 bg-red-50 dark:bg-red-900/20 px-2 py-0.5 rounded-full"><AlertTriangle className="w-3 h-3" />{group.error_count}</span>}
                                </div>
                                <div className="shrink-0 text-right text-xs text-slate-400"><div className="flex items-center gap-1"><Timer className="w-3 h-3" />{formatDuration(group.duration_ms)}</div><div className="flex items-center gap-1 mt-1"><Clock className="w-3 h-3" />{formatTime(group.updated_at || group.created_at)}</div></div>
                                {groupReportUrl && <a href={groupReportUrl} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} className="shrink-0 p-1.5 rounded-lg hover:bg-indigo-50 dark:hover:bg-indigo-900/20 text-indigo-500 hover:text-indigo-600 transition-colors" title="查看该测试批次报告"><ExternalLink className="w-3.5 h-3.5" /></a>}
                                <button onClick={(e) => handleGenerateReport(e, group.group_id, Boolean(groupReport))} className="shrink-0 p-1.5 rounded-lg hover:bg-indigo-50 dark:hover:bg-indigo-900/20 text-indigo-400 hover:text-indigo-600 transition-colors" title="为该测试批次生成专属报告"><FileText className="w-3.5 h-3.5" /></button>
                                <button onClick={(e) => { e.stopPropagation(); handleDelete(group.group_id, '测试批次'); }} className="shrink-0 p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-slate-300 hover:text-red-500 transition-colors" title="删除测试批次"><Trash2 className="w-3.5 h-3.5" /></button>
                            </div>
                            {groupExpanded && <div className="px-4 pb-4 space-y-3"><div className="text-xs text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-900/30 rounded-lg px-3 py-2">该测试批次共包含 {group.record_count} 条单条记录。下面每条记录对应一次具体测试动作，例如 Smart Agent 执行、性能测试、安全扫描、数据库验证等。</div>{group.records.map(record => {
                                const recordExpanded = expandedRecordId === record.task_id;
                                const recordSuccess = isPureSuccessStatus(record.status);
                                const recordHealed = isRecoveredStatus(record.status);
                                const recordReport = reportMap[record.task_id];
                                const recordReportUrl = buildReportUrl(recordReport);
                                return <div key={record.task_id} className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/70 dark:bg-slate-900/30 overflow-hidden"><div className="flex items-center gap-3 px-4 py-3 cursor-pointer" onClick={() => { setExpandedRecordId(recordExpanded ? null : record.task_id); setDetailTab('log'); }}><div className="text-slate-400 shrink-0">{recordExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}</div><div className="shrink-0">{recordSuccess ? <CheckCircle2 className="w-4 h-4 text-emerald-500" /> : recordHealed ? <Shield className="w-4 h-4 text-teal-500" /> : <XCircle className="w-4 h-4 text-red-500" />}</div><div className="flex-1 min-w-0"><div className="text-sm text-slate-900 dark:text-white truncate">{record.requirement_display || record.requirement || '未命名单条记录'}</div><div className="flex items-center gap-3 mt-1 text-xs text-slate-400"><span className="flex items-center gap-1"><FileText className="w-3 h-3" />单条记录</span><span className="flex items-center gap-1"><Cpu className="w-3 h-3" />{MODE_LABELS[record.mode || 'smart'] || record.mode || 'Smart Agent'}</span>{record.target_url && <span className="flex items-center gap-1 truncate max-w-[220px]" title={record.target_url}><Globe className="w-3 h-3" />{record.target_url.replace(/^https?:\/\//, '')}</span>}</div></div><span className="text-xs text-slate-400 whitespace-nowrap">{formatDuration(record.duration_ms)}</span>{recordReport && <span className="flex items-center gap-1 text-xs text-indigo-600 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-500/10 px-2 py-0.5 rounded-full"><FileText className="w-3 h-3" />测试报告</span>}{recordReportUrl && <a href={recordReportUrl} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} className="shrink-0 p-1.5 rounded-lg hover:bg-indigo-50 dark:hover:bg-indigo-900/20 text-indigo-500 hover:text-indigo-600 transition-colors" title="查看该单条记录报告"><ExternalLink className="w-3.5 h-3.5" /></a>}<button onClick={(e) => handleGenerateReport(e, record.task_id, Boolean(recordReport))} className="shrink-0 p-1.5 rounded-lg hover:bg-indigo-50 dark:hover:bg-indigo-900/20 text-indigo-400 hover:text-indigo-600 transition-colors" title="生成该单条记录报告"><FileText className="w-3.5 h-3.5" /></button><button onClick={(e) => { e.stopPropagation(); handleDelete(record.task_id, '单条记录'); }} className="shrink-0 p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-slate-300 hover:text-red-500 transition-colors" title="删除单条记录"><Trash2 className="w-3.5 h-3.5" /></button></div>{recordExpanded && <div className="px-4 pb-4"><div className="flex items-center gap-1 mb-3 bg-slate-100 dark:bg-slate-800 rounded-lg p-0.5 w-fit"><button onClick={(e) => { e.stopPropagation(); setDetailTab('log'); }} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${detailTab === 'log' ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm' : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300'}`}><FileText className="w-3 h-3" />执行日志</button><button onClick={(e) => { e.stopPropagation(); setDetailTab('gallery'); }} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${detailTab === 'gallery' ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm' : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300'}`}><Camera className="w-3 h-3" />步骤截图</button></div>{detailTab === 'log' ? <LogPanel taskId={record.task_id} isOpen={recordExpanded} /> : <GalleryPanel taskId={record.task_id} isOpen={recordExpanded} />}</div>}</div>;
                            })}</div>}
                        </div>
                    );
                })}
                {filtered.length === 0 && <div className="text-center text-slate-400 py-8"><Filter className="w-8 h-8 mx-auto mb-2 opacity-30" /><p className="text-sm">当前筛选无匹配测试批次</p></div>}
            </div>

            {totalPages > 1 && <div className="flex items-center justify-center gap-2 pt-2 border-t border-slate-200 dark:border-slate-800"><button onClick={() => setPage(current => Math.max(1, current - 1))} disabled={safePage <= 1} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"><PageLeft className="w-4 h-4" /></button>{Array.from({ length: totalPages }, (_, index) => index + 1).filter(current => current === 1 || current === totalPages || Math.abs(current - safePage) <= 2).map((current, index, array) => <React.Fragment key={current}>{index > 0 && array[index - 1] !== current - 1 && <span className="text-[10px] text-slate-400">...</span>}<button onClick={() => setPage(current)} className={`w-7 h-7 rounded-lg text-xs font-medium transition-all ${current === safePage ? 'bg-indigo-500 text-white shadow-lg shadow-indigo-500/20' : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'}`}>{current}</button></React.Fragment>)}<button onClick={() => setPage(current => Math.min(totalPages, current + 1))} disabled={safePage >= totalPages} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"><PageRight className="w-4 h-4" /></button></div>}
        </div>
    );
};

export default ExecutionHistory;
