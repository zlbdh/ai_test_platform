import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Sword, Send, Target, Loader2, CheckCircle2, XCircle, Clock,
    Zap, Shield, Gauge, Database, Eye, Globe, Accessibility,
    ChevronDown, ChevronUp, Ban, RotateCcw, Users, Activity, Heart, Trash2, AlertTriangle, ExternalLink, FileText, Search,
} from '../components/icons';
import { API_BASE_URL, API_ENDPOINTS } from '../config';
import {
    commanderRun, commanderStream, commanderMissions, commanderStatus,
    commanderHealth, commanderDeleteMission, commanderClearMissions,
    type AgentHealth, type MissionResult, type MissionBugSummaryItem,
} from '../services/commanderService';
import { ConfirmDialog, useConfirmDialog } from '../components/ui/ConfirmDialog';
import { useToast } from '../components/ui/Toast';
import { useCommanderStore } from '../stores';

// Status icon mapping

const STATUS_CONFIG: Record<string, { icon: React.ReactNode; color: string; bg: string; label: string }> = {
    pending: {
        icon: <Clock className="w-4 h-4" />,
        color: 'text-slate-400',
        bg: 'bg-slate-100 dark:bg-slate-800',
        label: "Waiting",
    },
    parsing: {
        icon: <Loader2 className="w-4 h-4 animate-spin" />,
        color: 'text-blue-500',
        bg: 'bg-blue-50 dark:bg-blue-500/10',
        label: "Parse requirements",
    },
    planning: {
        icon: <Loader2 className="w-4 h-4 animate-spin" />,
        color: 'text-indigo-500',
        bg: 'bg-indigo-50 dark:bg-indigo-500/10',
        label: "Select strategy",
    },
    dispatching: {
        icon: <Loader2 className="w-4 h-4 animate-spin" />,
        color: 'text-amber-500',
        bg: 'bg-amber-50 dark:bg-amber-500/10',
        label: "Dispatch tasks",
    },
    executing: {
        icon: <Loader2 className="w-4 h-4 animate-spin" />,
        color: 'text-purple-500',
        bg: 'bg-purple-50 dark:bg-purple-500/10',
        label: "Run tests",
    },
    reporting: {
        icon: <Loader2 className="w-4 h-4 animate-spin" />,
        color: 'text-cyan-500',
        bg: 'bg-cyan-50 dark:bg-cyan-500/10',
        label: "Generate report",
    },
    completed: {
        icon: <CheckCircle2 className="w-4 h-4" />,
        color: 'text-emerald-500',
        bg: 'bg-emerald-50 dark:bg-emerald-500/10',
        label: "Complete",
    },
    failed: {
        icon: <XCircle className="w-4 h-4" />,
        color: 'text-red-500',
        bg: 'bg-red-50 dark:bg-red-500/10',
        label: "Failed",
    },
    cancelled: {
        icon: <Ban className="w-4 h-4" />,
        color: 'text-gray-500',
        bg: 'bg-gray-50 dark:bg-gray-500/10',
        label: "Canceled",
    },
};

const TEST_TYPE_ICON: Record<string, React.ReactNode> = {
    ui_e2e: <Eye className="w-4 h-4" />,
    api_rest: <Globe className="w-4 h-4" />,
    api_graphql: <Globe className="w-4 h-4" />,
    security: <Shield className="w-4 h-4" />,
    performance: <Gauge className="w-4 h-4" />,
    database: <Database className="w-4 h-4" />,
    accessibility: <Accessibility className="w-4 h-4" />,
    visual_regression: <Eye className="w-4 h-4" />,
};

const TEST_TYPE_LABELS: Record<string, string> = {
    ui_e2e: "UI automation",
    api_rest: "API testing",
    api_graphql: "GraphQL testing",
    security: "Security scanning",
    performance: "Performance testing",
    database: "Database testing",
    accessibility: "Accessibility testing",
    visual_regression: "Visual regression",
};

interface CommanderReportSummary {
    id?: string;
    task_id?: string;
    timestamp: string;
    report_scope?: 'record' | 'summary' | 'batch';
    report_url?: string;
    allure_url?: string;
}

function buildCommanderReportUrl(report?: CommanderReportSummary | null): string | null {
    const rawUrl = report?.allure_url || report?.report_url;
    if (!rawUrl) return null;
    if (rawUrl.startsWith('http://') || rawUrl.startsWith('https://')) return rawUrl;
    return `${API_BASE_URL}${rawUrl.startsWith('/') ? rawUrl : `/${rawUrl}`}`;
}

type MissionMetaTone = 'neutral' | 'indigo' | 'red' | 'amber';
type MissionHistoryFilter = 'all' | 'has_bugs' | 'has_report' | 'pending_report';
type MissionHistorySort = 'latest' | 'bugs_first' | 'pending_report_first' | 'report_ready_first';
type MissionStatusFilter = 'all' | 'completed' | 'failed' | 'running';
type MissionSelectionScope = 'all' | 'selected';
type CommanderBugBoardSeverityFilter = 'all' | 'error' | 'warning' | 'recovered';

interface MissionMetaBadge {
    key: string;
    label: string;
    tone: MissionMetaTone;
}

const MISSION_META_TONE_CLASS: Record<MissionMetaTone, string> = {
    neutral: 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400',
    indigo: 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-300',
    red: 'bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-300',
    amber: 'bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-300',
};

interface CommanderMissionExecutionMetrics {
    totalTests: number;
    passedTests: number;
    failedTests: number;
    successRate: number | null;
}

interface CommanderHistoryOverview {
    missionCount: number;
    completedCount: number;
    runningCount: number;
    bugMissionCount: number;
    bugItemCount: number;
    reportReadyCount: number;
    pendingReportCount: number;
    totalTestLines: number;
    failedTestLines: number;
    averageSuccessRate: number | null;
    averageSuccessRateSamples: number;
}

interface CommanderSelectedMissionSummary {
    total: number;
    withBugs: number;
    reportReady: number;
    pendingReport: number;
}

type CommanderBatchActionTone = 'success' | 'warning' | 'info';
type CommanderBatchActionKind = 'restore_selected' | 'focus_selected';

interface CommanderBatchActionFeedback {
    tone: CommanderBatchActionTone;
    message: string;
    timestamp: number;
    missionIds?: string[];
    actionKind?: CommanderBatchActionKind;
}

interface CommanderBugHotspot {
    key: string;
    testType: string;
    title: string;
    summary: string;
    status: string;
    count: number;
    missionIds: string[];
    primaryMissionId: string | null;
    primaryExecutionRecordId: string | null;
}

interface CommanderBugBoardItem {
    key: string;
    missionId: string;
    missionInput: string;
    missionCreatedAt: string;
    missionStatus: string;
    executionGroupId: string;
    executionRecordId: string | null;
    testType: string;
    title: string;
    summary: string;
    status: string;
    severityKey: Exclude<CommanderBugBoardSeverityFilter, 'all'> | 'info';
    hasReport: boolean;
}

function toSafeNumber(value: unknown): number | null {
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    if (typeof value === 'string' && value.trim()) {
        const parsed = Number(value);
        if (Number.isFinite(parsed)) return parsed;
    }
    return null;
}

function toSafeInteger(value: unknown): number {
    const normalized = toSafeNumber(value);
    return normalized === null ? 0 : Math.max(0, Math.round(normalized));
}

function toSummaryRecord(mission: Pick<MissionResult, 'report'> | null | undefined): Record<string, unknown> | null {
    if (!mission?.report || typeof mission.report !== 'object') return null;
    const summary = (mission.report as Record<string, unknown>).summary;
    return summary && typeof summary === 'object' ? summary as Record<string, unknown> : null;
}

function getBugSeverityRank(status: string): number {
    const normalized = String(status || '').toLowerCase();
    if (normalized === 'error' || normalized === 'failed') return 3;
    if (normalized === 'warning' || normalized === 'warn') return 2;
    if (normalized === 'recovered' || normalized === 'healed') return 1;
    return 0;
}

function getBugSeverityTone(status: string): string {
    const normalized = String(status || '').toLowerCase();
    if (normalized === 'error' || normalized === 'failed') return "Error";
    if (normalized === 'warning' || normalized === 'warn') return "Warning";
    if (normalized === 'recovered' || normalized === 'healed') return "Recovered";
    return "Notice";
}

function normalizeCommanderBugSeverity(status: string): CommanderBugBoardItem['severityKey'] {
    const normalized = String(status || '').toLowerCase();
    if (normalized === 'error' || normalized === 'failed') return 'error';
    if (normalized === 'warning' || normalized === 'warn') return 'warning';
    if (normalized === 'recovered' || normalized === 'healed') return 'recovered';
    return 'info';
}

export function buildCommanderBugHotspotKey(
    bug: Pick<MissionBugSummaryItem, 'test_type' | 'title' | 'summary'>,
): string {
    const testType = String(bug.test_type || 'unknown');
    const title = String(bug.title || TEST_TYPE_LABELS[testType] || "Unnamed issue");
    const summary = String(bug.summary || "Failures found").trim();
    return `${testType}::${title}::${summary}`;
}

export function getCommanderMissionExecutionMetrics(
    mission: Pick<MissionResult, 'report' | 'test_results_count'> | null | undefined,
): CommanderMissionExecutionMetrics {
    const summary = toSummaryRecord(mission);
    const totalTests = toSafeInteger(summary?.total_tests ?? mission?.test_results_count ?? 0);
    const failedTests = summary ? toSafeInteger(summary?.failed ?? 0) : 0;
    const passedFromSummary = summary ? toSafeInteger(summary?.completed ?? 0) : 0;
    const passedTests = summary
        ? (passedFromSummary > 0 ? passedFromSummary : Math.max(totalTests - failedTests, 0))
        : 0;
    const successRateFromSummary = toSafeNumber(summary?.success_rate);
    const successRate = successRateFromSummary !== null
        ? Number(successRateFromSummary.toFixed(1))
        : summary && totalTests > 0
            ? Number(((passedTests / totalTests) * 100).toFixed(1))
            : null;
    return {
        totalTests,
        passedTests,
        failedTests,
        successRate,
    };
}

export function buildCommanderHistoryOverview(
    missions: MissionResult[],
    reportMap: Record<string, CommanderReportSummary>,
): CommanderHistoryOverview {
    let completedCount = 0;
    let runningCount = 0;
    let bugMissionCount = 0;
    let bugItemCount = 0;
    let reportReadyCount = 0;
    let totalTestLines = 0;
    let failedTestLines = 0;
    let successRateTotal = 0;
    let successRateSamples = 0;

    for (const mission of missions) {
        if (mission.status === 'completed') completedCount += 1;
        if (!['completed', 'failed', 'cancelled'].includes(mission.status)) runningCount += 1;

        const bugCount = getMissionBugSummaryItems(mission).length;
        if (bugCount > 0) bugMissionCount += 1;
        bugItemCount += bugCount;

        if (buildCommanderReportUrl(reportMap[mission.execution_group_id || ''])) {
            reportReadyCount += 1;
        }

        const metrics = getCommanderMissionExecutionMetrics(mission);
        totalTestLines += metrics.totalTests;
        failedTestLines += metrics.failedTests;
        if (metrics.successRate !== null) {
            successRateTotal += metrics.successRate;
            successRateSamples += 1;
        }
    }

    return {
        missionCount: missions.length,
        completedCount,
        runningCount,
        bugMissionCount,
        bugItemCount,
        reportReadyCount,
        pendingReportCount: Math.max(missions.length - reportReadyCount, 0),
        totalTestLines,
        failedTestLines,
        averageSuccessRate: successRateSamples > 0
            ? Number((successRateTotal / successRateSamples).toFixed(1))
            : null,
        averageSuccessRateSamples: successRateSamples,
    };
}

export function buildCommanderBugHotspots(
    missions: MissionResult[],
    limit = 3,
): CommanderBugHotspot[] {
    const hotspotMap = new Map<string, CommanderBugHotspot>();

    for (const mission of missions) {
        for (const bug of getMissionBugSummaryItems(mission)) {
            const title = String(bug.title || TEST_TYPE_LABELS[bug.test_type] || "Unnamed issue");
            const key = buildCommanderBugHotspotKey(bug);
            const existing = hotspotMap.get(key);
            if (existing) {
                existing.count += 1;
                if (getBugSeverityRank(bug.status) > getBugSeverityRank(existing.status)) {
                    existing.status = String(bug.status || existing.status || 'unknown');
                }
                if (!existing.missionIds.includes(mission.mission_id)) {
                    existing.missionIds.push(mission.mission_id);
                }
                continue;
            }
            hotspotMap.set(key, {
                key,
                testType: String(bug.test_type || 'unknown'),
                title,
                summary: String(bug.summary || "Failures found"),
                status: String(bug.status || 'unknown'),
                count: 1,
                missionIds: [mission.mission_id],
                primaryMissionId: mission.mission_id,
                primaryExecutionRecordId: bug.execution_record_id || null,
            });
        }
    }

    return Array.from(hotspotMap.values())
        .sort((left, right) => {
            if (right.count !== left.count) return right.count - left.count;
            if (getBugSeverityRank(right.status) !== getBugSeverityRank(left.status)) {
                return getBugSeverityRank(right.status) - getBugSeverityRank(left.status);
            }
            return left.title.localeCompare(right.title, 'en-US');
        })
        .slice(0, Math.max(limit, 0));
}

export function buildCommanderBugBoardItems(
    missions: MissionResult[],
    reportMap: Record<string, CommanderReportSummary>,
    severityFilter: CommanderBugBoardSeverityFilter = 'all',
    limit = 8,
): CommanderBugBoardItem[] {
    const items: CommanderBugBoardItem[] = [];

    for (const mission of missions) {
        const hasReport = Boolean(buildCommanderReportUrl(reportMap[mission.execution_group_id || '']));
        for (const bug of getMissionBugSummaryItems(mission)) {
            const severityKey = normalizeCommanderBugSeverity(bug.status);
            if (severityFilter !== 'all' && severityKey !== severityFilter) {
                continue;
            }
            items.push({
                key: `${mission.mission_id}::${buildCommanderBugHotspotKey(bug)}::${bug.execution_record_id || 'inline'}`,
                missionId: mission.mission_id,
                missionInput: String(mission.user_input || ''),
                missionCreatedAt: String(mission.created_at || ''),
                missionStatus: String(mission.status || 'unknown'),
                executionGroupId: String(mission.execution_group_id || ''),
                executionRecordId: bug.execution_record_id || null,
                testType: String(bug.test_type || 'unknown'),
                title: String(bug.title || TEST_TYPE_LABELS[String(bug.test_type || '')] || "Unnamed issue"),
                summary: String(bug.summary || "Failures found"),
                status: String(bug.status || 'unknown'),
                severityKey,
                hasReport,
            });
        }
    }

    return items
        .sort((left, right) => {
            if (getBugSeverityRank(right.status) !== getBugSeverityRank(left.status)) {
                return getBugSeverityRank(right.status) - getBugSeverityRank(left.status);
            }
            const rightTime = new Date(right.missionCreatedAt || 0).getTime();
            const leftTime = new Date(left.missionCreatedAt || 0).getTime();
            if (rightTime !== leftTime) return rightTime - leftTime;
            return left.summary.localeCompare(right.summary, 'en-US');
        })
        .slice(0, Math.max(limit, 0));
}

export function collectCommanderBugBoardMissionIds(items: CommanderBugBoardItem[]): string[] {
    const seen = new Set<string>();
    const missionIds: string[] = [];
    for (const item of items) {
        if (!item.missionId || seen.has(item.missionId)) continue;
        seen.add(item.missionId);
        missionIds.push(item.missionId);
    }
    return missionIds;
}

export function collectCommanderPendingReportMissionIds(
    missions: MissionResult[],
    reportMap: Record<string, CommanderReportSummary>,
    missionIds: string[],
): string[] {
    const pending: string[] = [];
    const seen = new Set<string>();
    const missionMap = new Map(missions.map(mission => [mission.mission_id, mission]));

    for (const missionId of missionIds) {
        if (!missionId || seen.has(missionId)) continue;
        seen.add(missionId);
        const mission = missionMap.get(missionId);
        if (!mission) continue;
        const hasReport = Boolean(buildCommanderReportUrl(reportMap[mission.execution_group_id || '']));
        if (!hasReport) {
            pending.push(missionId);
        }
    }
    return pending;
}

export function buildCommanderSelectedMissionSummary(
    missions: MissionResult[],
    reportMap: Record<string, CommanderReportSummary>,
    selectedMissionIds: string[],
): CommanderSelectedMissionSummary {
    const selected = new Set(selectedMissionIds.filter(Boolean));
    let total = 0;
    let withBugs = 0;
    let reportReady = 0;

    for (const mission of missions) {
        if (!selected.has(mission.mission_id)) continue;
        total += 1;
        if (getMissionBugSummaryItems(mission).length > 0) {
            withBugs += 1;
        }
        if (buildCommanderReportUrl(reportMap[mission.execution_group_id || ''])) {
            reportReady += 1;
        }
    }

    return {
        total,
        withBugs,
        reportReady,
        pendingReport: Math.max(total - reportReady, 0),
    };
}

export function buildCommanderBatchActionFeedback(
    type: 'bulk_report' | 'bug_board_report' | 'delete' | 'clear' | 'empty',
    payload: {
        generated?: number;
        skipped?: number;
        failed?: number;
        total?: number;
        count?: number;
        missionIds?: string[];
    },
): CommanderBatchActionFeedback {
    if (type === 'empty') {
        return {
            tone: 'info',
            message: "No tasks in the current issue scope need reports.",
            timestamp: Date.now(),
        };
    }
    if (type === 'delete') {
        return {
            tone: 'success',
            message: `Deleted ${payload.count ?? 0} task records.`,
            timestamp: Date.now(),
        };
    }
    if (type === 'clear') {
        return {
            tone: 'info',
            message: `Cleared ${payload.count ?? 0} selected tasks.`,
            timestamp: Date.now(),
            missionIds: payload.missionIds ?? [],
            actionKind: (payload.missionIds?.length ?? 0) > 0 ? 'restore_selected' : undefined,
        };
    }
    const prefix = type === 'bug_board_report' ? "Issue list processing completed" : "Batch processing completed";
    const failed = payload.failed ?? 0;
    return {
        tone: failed > 0 ? 'warning' : 'success',
        message: `${prefix}: generated ${payload.generated ?? 0}, already existed ${payload.skipped ?? 0}, failed ${failed}.`,
        timestamp: Date.now(),
        missionIds: payload.missionIds ?? [],
        actionKind: (payload.missionIds?.length ?? 0) > 0 ? 'focus_selected' : undefined,
    };
}

export function filterCommanderMissionsByBugHotspot(
    missions: MissionResult[],
    hotspotKey: string | null | undefined,
): MissionResult[] {
    const normalized = String(hotspotKey || '').trim();
    if (!normalized) return missions;
    return missions.filter(mission =>
        getMissionBugSummaryItems(mission).some(bug => buildCommanderBugHotspotKey(bug) === normalized),
    );
}

export function getMissionBugSummaryItems(mission: Pick<MissionResult, 'bug_summary' | 'report'> | null | undefined): MissionBugSummaryItem[] {
    if (!mission) return [];
    const reportSummary = mission.report && Array.isArray((mission.report as Record<string, unknown>).bug_summary)
        ? (mission.report as Record<string, unknown>).bug_summary as MissionBugSummaryItem[]
        : [];
    const directSummary = Array.isArray(mission.bug_summary) ? mission.bug_summary : [];
    return (reportSummary.length ? reportSummary : directSummary).map(item => ({
        test_type: String(item.test_type || ''),
        title: String(item.title || TEST_TYPE_LABELS[String(item.test_type || '')] || "Unnamed issue"),
        status: String(item.status || 'unknown'),
        summary: String(item.summary || "Failures found"),
        execution_record_id: item.execution_record_id || null,
    }));
}

export function buildCommanderExecutionHistoryPath(
    mission: Pick<MissionResult, 'execution_group_id'> | null | undefined,
    executionRecordId?: string | null,
): string | null {
    const groupId = (mission?.execution_group_id || '').trim();
    if (!groupId) return null;
    const params = new URLSearchParams({ group: groupId });
    const recordId = (executionRecordId || '').trim();
    if (recordId) params.set('record', recordId);
    return `/history?${params.toString()}`;
}

export function getCommanderMissionMetaBadges(
    mission: Pick<MissionResult, 'test_results_count' | 'bug_summary' | 'report'> | null | undefined,
    hasReport: boolean,
): MissionMetaBadge[] {
    if (!mission) return [];
    const badges: MissionMetaBadge[] = [];
    const metrics = getCommanderMissionExecutionMetrics(mission);
    if (metrics.totalTests > 0) {
        badges.push({
            key: 'lanes',
            label: `${metrics.totalTests} test tracks`,
            tone: 'neutral',
        });
    }
    if (metrics.passedTests > 0) {
        badges.push({
            key: 'passed',
            label: `Passed ${metrics.passedTests}`,
            tone: 'indigo',
        });
    }
    if (metrics.failedTests > 0) {
        badges.push({
            key: 'failed',
            label: `Failed ${metrics.failedTests}`,
            tone: 'red',
        });
    }
    if (metrics.successRate !== null && metrics.totalTests > 0) {
        badges.push({
            key: 'success_rate',
            label: `${metrics.successRate}% pass rate`,
            tone: metrics.failedTests > 0 ? 'amber' : 'indigo',
        });
    }
    const bugCount = getMissionBugSummaryItems(mission).length;
    badges.push({
        key: 'report',
        label: hasReport ? "Report generated" : "Report pending",
        tone: hasReport ? 'indigo' : 'amber',
    });
    if (bugCount > 0) {
        badges.push({
            key: 'bugs',
            label: `${bugCount} ${bugCount === 1 ? 'issue' : 'issues'}`,
            tone: 'red',
        });
    }
    return badges;
}

export function filterCommanderMissions(
    missions: MissionResult[],
    reportMap: Record<string, CommanderReportSummary>,
    filter: MissionHistoryFilter,
): MissionResult[] {
    if (filter === 'all') return missions;
    return missions.filter(mission => {
        const hasReport = Boolean(buildCommanderReportUrl(reportMap[mission.execution_group_id || '']));
        const hasBugs = getMissionBugSummaryItems(mission).length > 0;
        if (filter === 'has_bugs') return hasBugs;
        if (filter === 'has_report') return hasReport;
        if (filter === 'pending_report') return !hasReport;
        return true;
    });
}

export function searchCommanderMissions(missions: MissionResult[], keyword: string): MissionResult[] {
    const normalized = (keyword || '').trim().toLowerCase();
    if (!normalized) return missions;
    return missions.filter(mission =>
        [
            mission.mission_id,
            mission.user_input,
            mission.target_url,
            mission.execution_group_id,
        ].some(value => String(value || '').toLowerCase().includes(normalized)),
    );
}

export function sortCommanderMissions(
    missions: MissionResult[],
    reportMap: Record<string, CommanderReportSummary>,
    sort: MissionHistorySort,
): MissionResult[] {
    const withMeta = missions.map(mission => {
        const hasReport = Boolean(buildCommanderReportUrl(reportMap[mission.execution_group_id || '']));
        const bugCount = getMissionBugSummaryItems(mission).length;
        const createdAt = new Date(mission.created_at || 0).getTime();
        return { mission, hasReport, bugCount, createdAt };
    });

    withMeta.sort((left, right) => {
        if (sort === 'bugs_first' && right.bugCount !== left.bugCount) {
            return right.bugCount - left.bugCount;
        }
        if (sort === 'pending_report_first' && left.hasReport !== right.hasReport) {
            return left.hasReport ? 1 : -1;
        }
        if (sort === 'report_ready_first' && left.hasReport !== right.hasReport) {
            return left.hasReport ? -1 : 1;
        }
        return right.createdAt - left.createdAt;
    });

    return withMeta.map(item => item.mission);
}

export function filterCommanderMissionsByStatus(
    missions: MissionResult[],
    statusFilter: MissionStatusFilter,
): MissionResult[] {
    if (statusFilter === 'all') return missions;
    return missions.filter(mission => {
        if (statusFilter === 'completed') return mission.status === 'completed';
        if (statusFilter === 'failed') return mission.status === 'failed' || mission.status === 'cancelled';
        if (statusFilter === 'running') return !['completed', 'failed', 'cancelled'].includes(mission.status);
        return true;
    });
}

export function filterCommanderMissionsBySelection(
    missions: MissionResult[],
    selectedMissionIds: string[],
    scope: MissionSelectionScope,
): MissionResult[] {
    if (scope === 'all') return missions;
    const selected = new Set(selectedMissionIds.filter(Boolean));
    if (selected.size === 0) return [];
    return missions.filter(mission => selected.has(mission.mission_id));
}

// Main page

const CommanderPage: React.FC = () => {
    const navigate = useNavigate();
    const [input, setInput] = useState('');
    const [targetUrl, setTargetUrl] = useState('');
    const [showUrlInput, setShowUrlInput] = useState(false);
    const [expandedMission, setExpandedMission] = useState<string | null>(null);
    const [agentHealth, setAgentHealth] = useState<AgentHealth[]>([]);
    const [showAgents, setShowAgents] = useState(false);
    const [reportMap, setReportMap] = useState<Record<string, CommanderReportSummary>>({});
    const [reportLoadingId, setReportLoadingId] = useState<string | null>(null);
    const [historyFilter, setHistoryFilter] = useState<MissionHistoryFilter>('all');
    const [historyKeyword, setHistoryKeyword] = useState('');
    const [historySort, setHistorySort] = useState<MissionHistorySort>('latest');
    const [historyStatusFilter, setHistoryStatusFilter] = useState<MissionStatusFilter>('all');
    const [historySelectionScope, setHistorySelectionScope] = useState<MissionSelectionScope>('all');
    const [activeBugHotspotKey, setActiveBugHotspotKey] = useState<string | null>(null);
    const [bugBoardSeverityFilter, setBugBoardSeverityFilter] = useState<CommanderBugBoardSeverityFilter>('all');
    const [bugBoardActionFeedback, setBugBoardActionFeedback] = useState<CommanderBatchActionFeedback | null>(null);
    const [selectedMissionIds, setSelectedMissionIds] = useState<string[]>([]);
    const { showToast } = useToast();
    const { confirm, dialogProps } = useConfirmDialog();

    // Read execution state from the global store to persist across pages.
    const {
        isRunning, activeMission, streamLogs, missions,
        startMission, appendStreamLog, finishMission,
        setActiveMission, setMissions, setIsRunning, setSseCleanup,
    } = useCommanderStore();

    const logEndRef = useRef<HTMLDivElement>(null);
    const activeMissionReport = activeMission?.execution_group_id
        ? reportMap[activeMission.execution_group_id]
        : undefined;
    const activeMissionReportUrl = buildCommanderReportUrl(activeMissionReport);
    const searchedMissions = useMemo(
        () => searchCommanderMissions(missions, historyKeyword),
        [missions, historyKeyword],
    );
    const statusFilteredMissions = useMemo(
        () => filterCommanderMissionsByStatus(searchedMissions, historyStatusFilter),
        [searchedMissions, historyStatusFilter],
    );
    const filteredMissions = useMemo(
        () => filterCommanderMissions(statusFilteredMissions, reportMap, historyFilter),
        [statusFilteredMissions, reportMap, historyFilter],
    );
    const selectionScopedMissions = useMemo(
        () => filterCommanderMissionsBySelection(filteredMissions, selectedMissionIds, historySelectionScope),
        [filteredMissions, selectedMissionIds, historySelectionScope],
    );
    const bugHotspots = useMemo(
        () => buildCommanderBugHotspots(selectionScopedMissions, 4),
        [selectionScopedMissions],
    );
    const hotspotFilteredMissions = useMemo(
        () => filterCommanderMissionsByBugHotspot(selectionScopedMissions, activeBugHotspotKey),
        [selectionScopedMissions, activeBugHotspotKey],
    );
    const visibleMissions = useMemo(
        () => sortCommanderMissions(hotspotFilteredMissions, reportMap, historySort),
        [hotspotFilteredMissions, reportMap, historySort],
    );
    const missionMapById = useMemo(
        () => new Map(missions.map(mission => [mission.mission_id, mission])),
        [missions],
    );
    const historyCounts = useMemo(() => ({
        all: statusFilteredMissions.length,
        has_bugs: filterCommanderMissions(statusFilteredMissions, reportMap, 'has_bugs').length,
        has_report: filterCommanderMissions(statusFilteredMissions, reportMap, 'has_report').length,
        pending_report: filterCommanderMissions(statusFilteredMissions, reportMap, 'pending_report').length,
    }), [statusFilteredMissions, reportMap]);
    const statusCounts = useMemo(() => ({
        all: searchedMissions.length,
        completed: filterCommanderMissionsByStatus(searchedMissions, 'completed').length,
        failed: filterCommanderMissionsByStatus(searchedMissions, 'failed').length,
        running: filterCommanderMissionsByStatus(searchedMissions, 'running').length,
    }), [searchedMissions]);
    const historyOverview = useMemo(
        () => buildCommanderHistoryOverview(visibleMissions, reportMap),
        [visibleMissions, reportMap],
    );
    const bugBoardItems = useMemo(
        () => buildCommanderBugBoardItems(visibleMissions, reportMap, bugBoardSeverityFilter, 8),
        [visibleMissions, reportMap, bugBoardSeverityFilter],
    );
    const bugBoardMissionIds = useMemo(
        () => collectCommanderBugBoardMissionIds(bugBoardItems),
        [bugBoardItems],
    );
    const bugBoardPendingReportMissionIds = useMemo(
        () => collectCommanderPendingReportMissionIds(missions, reportMap, bugBoardMissionIds),
        [missions, reportMap, bugBoardMissionIds],
    );
    const selectedBugBoardPendingReportMissionIds = useMemo(
        () => collectCommanderPendingReportMissionIds(
            missions,
            reportMap,
            bugBoardMissionIds.filter(id => selectedMissionIds.includes(id)),
        ),
        [missions, reportMap, bugBoardMissionIds, selectedMissionIds],
    );
    const selectedBugBoardMissionCount = useMemo(
        () => bugBoardMissionIds.filter(id => selectedMissionIds.includes(id)).length,
        [bugBoardMissionIds, selectedMissionIds],
    );
    const selectedMissionSummary = useMemo(
        () => buildCommanderSelectedMissionSummary(missions, reportMap, selectedMissionIds),
        [missions, reportMap, selectedMissionIds],
    );
    const visibleMissionIds = useMemo(() => visibleMissions.map(mission => mission.mission_id), [visibleMissions]);
    const allVisibleSelected = visibleMissionIds.length > 0 && visibleMissionIds.every(id => selectedMissionIds.includes(id));
    const allBugBoardSelected = bugBoardMissionIds.length > 0 && bugBoardMissionIds.every(id => selectedMissionIds.includes(id));

    const loadReportMap = useCallback(async () => {
        try {
            const res = await fetch(`${API_ENDPOINTS.report.history}?limit=200`);
            if (!res.ok) return;
            const data = await res.json();
            const items = Array.isArray(data?.history) ? data.history as CommanderReportSummary[] : [];
            const nextMap: Record<string, CommanderReportSummary> = {};
            for (const item of items) {
                if (!item?.task_id || nextMap[item.task_id]) continue;
                nextMap[item.task_id] = item;
            }
            setReportMap(nextMap);
        } catch {
            // silent
        }
    }, []);

    const openExecutionCenter = useCallback((mission: MissionResult, executionRecordId?: string | null) => {
        const targetPath = buildCommanderExecutionHistoryPath(mission, executionRecordId);
        if (!targetPath) return;
        navigate(targetPath);
    }, [navigate]);

    const focusMission = useCallback((missionId: string) => {
        setExpandedMission(missionId);
        const mission = missionMapById.get(missionId);
        if (mission) {
            setActiveMission(mission);
        }
    }, [missionMapById, setActiveMission]);

    const focusHotspotMission = useCallback((missionId: string, hotspotKey: string) => {
        setActiveBugHotspotKey(hotspotKey);
        focusMission(missionId);
    }, [focusMission]);

    const ensureMissionReport = useCallback(async (
        mission: MissionResult,
        options?: { openExisting?: boolean; openGenerated?: boolean; silent?: boolean },
    ) => {
        const groupId = (mission.execution_group_id || '').trim();
        if (!groupId) return { ok: false, existed: false };
        const config = {
            openExisting: options?.openExisting ?? true,
            openGenerated: options?.openGenerated ?? true,
            silent: options?.silent ?? false,
        };
        const existingReport = reportMap[groupId];
        const existingReportUrl = buildCommanderReportUrl(existingReport);
        if (existingReportUrl) {
            if (config.openExisting) {
                window.open(existingReportUrl, '_blank', 'noopener,noreferrer');
            }
            return { ok: true, existed: true, url: existingReportUrl };
        }

        setReportLoadingId(groupId);
        try {
            const res = await fetch(API_ENDPOINTS.report.generate, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ execution_group_id: groupId }),
            });
            const data = await res.json();
            if (!res.ok || data.status === 'error') {
                if (!config.silent) {
                    showToast('error', `Failed to generate report: ${data.message || "Unknown error"}`);
                }
                return { ok: false, existed: false };
            }
            await loadReportMap();
            const reportUrl = buildCommanderReportUrl({
                timestamp: new Date().toISOString(),
                report_scope: data.report_scope,
                report_url: data.report_url,
                allure_url: data.allure_url,
            });
            if (reportUrl && config.openGenerated) {
                window.open(reportUrl, '_blank', 'noopener,noreferrer');
                return { ok: true, existed: false, url: reportUrl };
            }
            if (!config.silent) {
                showToast('success', "Batch report generated. View it in the execution center or test report history.");
            }
            return { ok: true, existed: false, url: reportUrl || null };
        } catch (err) {
            if (!config.silent) {
                showToast('error', `Failed to generate report: ${err instanceof Error ? err.message : "Network error"}`);
            }
            return { ok: false, existed: false };
        } finally {
            setReportLoadingId(null);
        }
    }, [loadReportMap, reportMap, showToast]);

    const openMissionReport = useCallback(async (mission: MissionResult) => {
        await ensureMissionReport(mission);
    }, [ensureMissionReport]);

    const toggleMissionSelection = useCallback((missionId: string) => {
        setSelectedMissionIds(prev => prev.includes(missionId)
            ? prev.filter(id => id !== missionId)
            : [...prev, missionId]);
    }, []);

    const toggleSelectVisibleMissions = useCallback(() => {
        setSelectedMissionIds(prev => {
            if (allVisibleSelected) {
                return prev.filter(id => !visibleMissionIds.includes(id));
            }
            return Array.from(new Set([...prev, ...visibleMissionIds]));
        });
    }, [allVisibleSelected, visibleMissionIds]);

    const toggleSelectBugBoardMissions = useCallback(() => {
        setSelectedMissionIds(prev => {
            if (allBugBoardSelected) {
                return prev.filter(id => !bugBoardMissionIds.includes(id));
            }
            return Array.from(new Set([...prev, ...bugBoardMissionIds]));
        });
    }, [allBugBoardSelected, bugBoardMissionIds]);

    const clearSelectedMissions = useCallback(() => {
        if (selectedMissionIds.length === 0) return;
        setBugBoardActionFeedback(buildCommanderBatchActionFeedback('clear', {
            count: selectedMissionIds.length,
            missionIds: selectedMissionIds,
        }));
        setHistorySelectionScope('all');
        setSelectedMissionIds([]);
    }, [selectedMissionIds]);

    const generateReportsForMissionIds = useCallback(async (missionIds: string[]) => {
        const targetIds = Array.from(new Set(missionIds.filter(Boolean)));
        const selectedMissions = missions.filter(mission => targetIds.includes(mission.mission_id));
        if (selectedMissions.length === 0) {
            return { generated: 0, skipped: 0, failed: 0, total: 0 };
        }
        let generated = 0;
        let skipped = 0;
        let failed = 0;
        for (const mission of selectedMissions) {
            const result = await ensureMissionReport(mission, {
                openExisting: false,
                openGenerated: false,
                silent: true,
            });
            if (!result?.ok) failed += 1;
            else if (result.existed) skipped += 1;
            else generated += 1;
        }
        await loadReportMap();
        return {
            generated,
            skipped,
            failed,
            total: selectedMissions.length,
        };
    }, [missions, ensureMissionReport, loadReportMap]);

    const handleBulkGenerateReports = useCallback(async () => {
        const result = await generateReportsForMissionIds(selectedMissionIds);
        if (result.total === 0) return;
        const feedback = buildCommanderBatchActionFeedback('bulk_report', {
            ...result,
            missionIds: selectedMissionIds,
        });
        setBugBoardActionFeedback(feedback);
        showToast(
            feedback.tone,
            feedback.message,
            5000,
        );
    }, [selectedMissionIds, generateReportsForMissionIds, showToast]);

    const handleBugBoardGenerateReports = useCallback(async () => {
        const targetMissionIds = selectedBugBoardMissionCount > 0
            ? selectedBugBoardPendingReportMissionIds
            : bugBoardPendingReportMissionIds;
        const result = await generateReportsForMissionIds(targetMissionIds);
        if (result.total === 0) {
            const feedback = buildCommanderBatchActionFeedback('empty', {});
            setBugBoardActionFeedback(feedback);
            showToast(feedback.tone, feedback.message);
            return;
        }
        const feedback = buildCommanderBatchActionFeedback('bug_board_report', {
            ...result,
            missionIds: targetMissionIds,
        });
        setBugBoardActionFeedback(feedback);
        showToast(
            feedback.tone,
            feedback.message,
            5000,
        );
    }, [
        selectedBugBoardMissionCount,
        selectedBugBoardPendingReportMissionIds,
        bugBoardPendingReportMissionIds,
        generateReportsForMissionIds,
        showToast,
    ]);

    const handleFeedbackAction = useCallback(() => {
        if (!bugBoardActionFeedback?.missionIds?.length) return;
        const nextMissionIds = Array.from(new Set(bugBoardActionFeedback.missionIds.filter(Boolean)));
        if (nextMissionIds.length === 0) return;
        setSelectedMissionIds(nextMissionIds);
        setHistorySelectionScope('selected');
        focusMission(nextMissionIds[0]);
    }, [bugBoardActionFeedback, focusMission]);

    const handleBulkDelete = useCallback(async () => {
        if (selectedMissionIds.length === 0) return;
        const ok = await confirm("Delete tasks in bulk", `Delete the selected ${selectedMissionIds.length} task records?`);
        if (!ok) return;
        const deleteCount = selectedMissionIds.length;
        for (const missionId of selectedMissionIds) {
            await commanderDeleteMission(missionId);
        }
        setMissions(prev => prev.filter(mission => !selectedMissionIds.includes(mission.mission_id)));
        if (activeMission && selectedMissionIds.includes(activeMission.mission_id)) {
            setActiveMission(null);
        }
        setHistorySelectionScope('all');
        setSelectedMissionIds([]);
        const feedback = buildCommanderBatchActionFeedback('delete', { count: deleteCount });
        setBugBoardActionFeedback(feedback);
        showToast(feedback.tone, feedback.message);
    }, [selectedMissionIds, setMissions, activeMission, setActiveMission, confirm, showToast]);

    useEffect(() => {
        setSelectedMissionIds(prev => prev.filter(id => missions.some(mission => mission.mission_id === id)));
    }, [missions]);

    useEffect(() => {
        if (historySelectionScope === 'selected' && selectedMissionIds.length === 0) {
            setHistorySelectionScope('all');
        }
    }, [historySelectionScope, selectedMissionIds]);

    useEffect(() => {
        if (!activeBugHotspotKey) return;
        if (!bugHotspots.some(item => item.key === activeBugHotspotKey)) {
            setActiveBugHotspotKey(null);
        }
    }, [bugHotspots, activeBugHotspotKey]);

    useEffect(() => {
        if (!activeBugHotspotKey || visibleMissions.length === 0) return;
        if (!expandedMission || !visibleMissions.some(mission => mission.mission_id === expandedMission)) {
            setExpandedMission(visibleMissions[0].mission_id);
        }
    }, [activeBugHotspotKey, visibleMissions, expandedMission]);

    // Load task history and agent health only when the store has no data.
    useEffect(() => {
        if (missions.length === 0) {
            commanderMissions(10).then(setMissions).catch(() => { });
        }
        commanderHealth().then(d => setAgentHealth(d.agents)).catch(() => { });
        loadReportMap();
    }, [missions.length, setMissions, loadReportMap]);

    // Scroll logs automatically.
    useEffect(() => {
        logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [streamLogs]);

    const handleRun = useCallback(async () => {
        if (!input.trim() || isRunning) return;

        try {
            // 1. Start the task without blocking; return mission_id immediately.
            const result = await commanderRun(input, targetUrl, true);
            startMission(result);

            // 2. Open SSE logs; the store manages their lifecycle.
            const cleanup = commanderStream(
                result.mission_id,
                (log) => {
                    appendStreamLog(log);
                },
                async () => {
                    // Refresh final status and history when SSE ends.
                    let final: typeof result | null = null;
                    try {
                        final = await commanderStatus(result.mission_id);
                    } catch { /* ignore */ }
                    const updated = await commanderMissions(10);
                    finishMission(final, updated);
                    void loadReportMap();
                },
            );
            setSseCleanup(cleanup);

            // 3. Poll task status for fields that SSE may miss.
            const pollInterval = setInterval(async () => {
                try {
                    const status = await commanderStatus(result.mission_id);
                    setActiveMission(status);
                    if (['completed', 'failed', 'cancelled'].includes(status.status)) {
                        clearInterval(pollInterval);
                        const updated = await commanderMissions(10);
                        finishMission(status, updated);
                        void loadReportMap();
                    }
                } catch { /* ignore */ }
            }, 3000);

            setInput('');
            setTargetUrl('');
        } catch (err) {
            appendStreamLog({
                timestamp: new Date().toISOString(),
                level: 'error',
                message: `❌ Failed to start: ${err instanceof Error ? err.message : String(err)}`,
                data: {},
            });
            setIsRunning(false);
        }
    }, [input, targetUrl, isRunning, startMission, appendStreamLog, finishMission, setActiveMission, setIsRunning, setSseCleanup, loadReportMap]);


    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleRun();
        }
    };

    return (
        <div className="flex flex-col gap-6 h-full">
            <ConfirmDialog {...dialogProps} />
            {/* Hero Input */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-600 p-[1px]">
                <div className="bg-white dark:bg-slate-900 rounded-2xl p-6">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center text-white shadow-lg shadow-indigo-500/25">
                            <Sword className="w-5 h-5" />
                        </div>
                        <div>
                            <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">Commander</h2>
                            <p className="text-sm text-slate-500 dark:text-slate-400">Start comprehensive testing with one instruction: automatic parsing, intelligent scheduling, and parallel execution</p>
                        </div>
                    </div>

                    <div className="flex gap-3">
                        <div className="flex-1 relative">
                            <textarea
                                id="commander-input"
                                value={input}
                                onChange={e => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder={"Enter test requirements, for example: Fully test the store login flow, including valid credentials, incorrect passwords, and verification codes..."}
                                className="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500 transition-all min-h-[56px] max-h-[120px]"
                                rows={2}
                                disabled={isRunning}
                            />

                            {/* URL Toggle */}
                            <button
                                onClick={() => setShowUrlInput(!showUrlInput)}
                                className="absolute right-2 bottom-2 p-1.5 text-slate-400 hover:text-indigo-500 rounded-lg hover:bg-indigo-50 dark:hover:bg-indigo-500/10 transition-colors"
                                title={"Add target URL"}
                            >
                                <Target className="w-4 h-4" />
                            </button>
                        </div>

                        <button
                            id="commander-run-btn"
                            onClick={handleRun}
                            disabled={isRunning || !input.trim()}
                            className="px-6 py-3 bg-gradient-to-r from-indigo-500 to-purple-500 hover:from-indigo-600 hover:to-purple-600 disabled:from-slate-300 disabled:to-slate-400 dark:disabled:from-slate-700 dark:disabled:to-slate-600 text-white rounded-xl font-medium text-sm transition-all shadow-lg shadow-indigo-500/25 disabled:shadow-none flex items-center gap-2 shrink-0"
                        >
                            {isRunning ? (
                                <><Loader2 className="w-4 h-4 animate-spin" /> Running...</>
                            ) : (
                                <><Send className="w-4 h-4" /> Launch</>
                            )}
                        </button>
                    </div>

                    {showUrlInput && (
                        <div className="mt-3 animate-in slide-in-from-top-2 duration-200">
                            <input
                                id="commander-url-input"
                                type="text"
                                value={targetUrl}
                                onChange={e => setTargetUrl(e.target.value)}
                                placeholder="https://example.com"
                                className="w-full px-4 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/40 transition-all"
                            />
                        </div>
                    )}

                    {/* Quick Actions */}
                    <div className="flex items-center gap-2 mt-3 flex-wrap">
                        <span className="text-xs text-slate-400 dark:text-slate-500">Quick start:</span>
                        {[
                            "Comprehensive login testing",
                            "API regression testing",
                            "Security vulnerability scan",
                            "Load-test the home page",
                        ].map(q => (
                            <button
                                key={q}
                                onClick={() => setInput(q)}
                                className="px-3 py-1 text-xs bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 rounded-lg hover:bg-indigo-50 dark:hover:bg-indigo-500/10 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
                            >
                                {q}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Active Mission + Logs */}
            {activeMission && (
                <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
                    <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            {(() => {
                                const cfg = STATUS_CONFIG[activeMission.status] || STATUS_CONFIG.pending;
                                return (
                                    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${cfg.bg} ${cfg.color}`}>
                                        {cfg.icon}
                                        <span className="text-sm font-medium">{cfg.label}</span>
                                    </div>
                                );
                            })()}
                            <span className="text-sm text-slate-500 dark:text-slate-400 font-mono">
                                #{activeMission.mission_id}
                            </span>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-slate-400">
                            {!!activeMission.report?.summary && (
                                <span className="px-2 py-1 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded-md font-medium">
                                    Success rate {String((activeMission.report.summary as Record<string, unknown>)?.success_rate ?? '–')}%
                                </span>
                            )}
                            {activeMission.execution_group_id && (
                                <button
                                    onClick={() => openExecutionCenter(activeMission)}
                                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-indigo-200 dark:border-indigo-500/30 text-indigo-600 dark:text-indigo-300 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 transition-colors"
                                >
                                    <ExternalLink className="w-3.5 h-3.5" />
                                    View execution center
                                </button>
                            )}
                            {activeMission.execution_group_id && (
                                <button
                                    onClick={() => openMissionReport(activeMission)}
                                    disabled={reportLoadingId === activeMission.execution_group_id}
                                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-emerald-200 dark:border-emerald-500/30 text-emerald-600 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                                >
                                    {reportLoadingId === activeMission.execution_group_id ? (
                                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                    ) : (
                                        <FileText className="w-3.5 h-3.5" />
                                    )}
                                    {activeMissionReportUrl ? "View batch report" : "Generate batch report"}
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Test Results */}
                    {!!activeMission.report?.results && (
                        <div className="px-5 py-3 border-b border-slate-100 dark:border-slate-700/50">
                            <div className="flex flex-wrap gap-2">
                                {(activeMission.report.results as Array<Record<string, unknown>>).map((r, i) => {
                                    const type = String(r.test_type || '');
                                    const status = String(r.status || '');
                                    const isOk = status === 'completed';
                                    return (
                                        <div
                                            key={i}
                                            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm ${isOk
                                                ? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                                                : 'bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-300'
                                                }`}
                                        >
                                            {TEST_TYPE_ICON[type] || <Zap className="w-4 h-4" />}
                                            <span>{String(type).replace('_', ' ')}</span>
                                            {isOk ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    )}

                    {getMissionBugSummaryItems(activeMission).length > 0 && (
                        <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-700/50 bg-red-50/40 dark:bg-red-500/5">
                            <div className="flex items-center justify-between gap-3 mb-3">
                                <div className="flex items-center gap-2 text-sm font-semibold text-red-700 dark:text-red-300">
                                    <AlertTriangle className="w-4 h-4" />
                                    Found {getMissionBugSummaryItems(activeMission).length} priority issues
                                </div>
                                {activeMission.execution_group_id && (
                                    <button
                                        onClick={() => openExecutionCenter(activeMission)}
                                        className="text-xs text-indigo-600 dark:text-indigo-300 hover:text-indigo-700 transition-colors"
                                    >
                                        View complete logs in the execution center
                                    </button>
                                )}
                            </div>
                            <div className="space-y-2">
                                {getMissionBugSummaryItems(activeMission).slice(0, 5).map((bug, index) => (
                                    <div key={`${bug.test_type}_${index}`} className="rounded-lg border border-red-100 dark:border-red-500/20 bg-white/80 dark:bg-slate-900/40 px-3 py-2">
                                        <div className="flex items-start justify-between gap-3">
                                            <div className="flex items-center gap-2 text-xs font-medium text-red-600 dark:text-red-300">
                                                {TEST_TYPE_ICON[bug.test_type] || <Zap className="w-3.5 h-3.5" />}
                                                <span>{bug.title}</span>
                                            </div>
                                            {bug.execution_record_id && activeMission.execution_group_id && (
                                                <button
                                                    onClick={() => openExecutionCenter(activeMission, bug.execution_record_id)}
                                                    className="shrink-0 inline-flex items-center gap-1 text-[11px] text-indigo-600 dark:text-indigo-300 hover:text-indigo-700 transition-colors"
                                                >
                                                    <ExternalLink className="w-3 h-3" />
                                                    Locate record
                                                </button>
                                            )}
                                        </div>
                                        <div className="mt-1 text-sm text-slate-700 dark:text-slate-200">{bug.summary}</div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Logs */}
                    <div className="max-h-72 overflow-y-auto p-4 space-y-1.5 bg-slate-50 dark:bg-slate-900/80 font-mono text-[13px] leading-relaxed">
                        {(activeMission.logs || []).map((log, i) => (
                            <div key={i} className={`flex gap-3 items-start py-1 px-2 rounded-lg transition-colors hover:bg-white dark:hover:bg-slate-800 ${log.level === 'error' ? 'text-red-600 dark:text-red-400 bg-red-50/50 dark:bg-red-500/5' :
                                log.level === 'warn' ? 'text-amber-600 dark:text-amber-400 bg-amber-50/50 dark:bg-amber-500/5' :
                                    'text-slate-700 dark:text-slate-300'
                                }`}>
                                <span className="text-slate-400 dark:text-slate-500 shrink-0 select-none text-xs mt-0.5">
                                    {new Date(log.timestamp).toLocaleTimeString('en-US')}
                                </span>
                                <span className="break-all">{log.message}</span>
                            </div>
                        ))}
                        {streamLogs.map((log, i) => (
                            <div key={`s${i}`} className={`flex gap-3 items-start py-1 px-2 rounded-lg transition-colors hover:bg-white dark:hover:bg-slate-800 ${log.level === 'error' ? 'text-red-600 dark:text-red-400 bg-red-50/50 dark:bg-red-500/5' :
                                log.level === 'warn' ? 'text-amber-600 dark:text-amber-400 bg-amber-50/50 dark:bg-amber-500/5' :
                                    'text-slate-700 dark:text-slate-300'
                                }`}>
                                <span className="text-slate-400 dark:text-slate-500 shrink-0 select-none text-xs mt-0.5">
                                    {new Date(log.timestamp).toLocaleTimeString('en-US')}
                                </span>
                                <span className="break-all">{log.message}</span>
                            </div>
                        ))}
                        <div ref={logEndRef} />
                    </div>
                </div>
            )}

            {/* Agent Status Panel */}
            <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
                <div
                    className="px-5 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors"
                    onClick={() => {
                        setShowAgents(!showAgents);
                        if (!showAgents) commanderHealth().then(d => setAgentHealth(d.agents)).catch(() => { });
                    }}
                >
                    <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                        <Users className="w-4 h-4 text-indigo-500" />
                        Agent fleet status
                        <span className="px-2 py-0.5 text-xs bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded-full font-medium">
                            {agentHealth.filter(a => a.healthy).length}/{agentHealth.length} Ready
                        </span>
                    </h3>
                    <div className="text-slate-400">
                        {showAgents ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </div>
                </div>

                {showAgents && (
                    <div className="p-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                        {agentHealth.map(agent => {
                            const isSquad = agent.type === 'squad';
                            const isCommander = agent.type === 'commander';
                            return (
                                <div
                                    key={agent.name}
                                    className={`relative p-3 rounded-xl border transition-all ${agent.healthy
                                        ? 'border-emerald-200 dark:border-emerald-500/30 bg-emerald-50/50 dark:bg-emerald-500/5'
                                        : 'border-red-200 dark:border-red-500/30 bg-red-50/50 dark:bg-red-500/5'
                                        }`}
                                >
                                    <div className="flex items-center gap-2 mb-2">
                                        <div className={`w-2 h-2 rounded-full ${agent.healthy ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`} />
                                        <span className="text-xs font-semibold text-slate-700 dark:text-slate-200 truncate">
                                            {agent.profile_id || agent.name}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-1">
                                        {isCommander && <Sword className="w-3 h-3 text-indigo-500" />}
                                        {isSquad && <Activity className="w-3 h-3 text-purple-500" />}
                                        {!isSquad && !isCommander && <Heart className="w-3 h-3 text-slate-400" />}
                                        <span className="text-[10px] text-slate-400 dark:text-slate-500">
                                            {agent.type}
                                        </span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Mission History */}
            <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
                <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                            <Clock className="w-4 h-4 text-slate-400" />
                            Task history
                        </h3>
                        <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 rounded-lg p-1">
                            {([
                                ['all', "All"],
                                ['has_bugs', "Has issues"],
                                ['has_report', "Report available"],
                                ['pending_report', "Report pending"],
                            ] as [MissionHistoryFilter, string][]).map(([key, label]) => (
                                <button
                                    key={key}
                                    onClick={() => setHistoryFilter(key)}
                                    className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${historyFilter === key
                                        ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm'
                                        : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300'
                                        }`}
                                >
                                    {label} ({historyCounts[key]})
                                </button>
                            ))}
                        </div>
                    </div>
                    <div className="flex items-center gap-1">
                        <button
                            onClick={() => commanderMissions(10).then(setMissions)}
                            className="p-1.5 text-slate-400 hover:text-indigo-500 rounded-lg hover:bg-indigo-50 dark:hover:bg-indigo-500/10 transition-colors"
                            title={"Refresh"}
                        >
                            <RotateCcw className="w-4 h-4" />
                        </button>
                        {missions.length > 0 && (
                            <button
                                onClick={async () => {
                                    const ok = await confirm("Clear all tasks", `Clear all ${missions.length} task records? This cannot be undone.`);
                                    if (!ok) return;
                                    await commanderClearMissions();
                                    setMissions([]);
                                    setSelectedMissionIds([]);
                                    showToast('success', "All agent fleet task records cleared.");
                                }}
                                className="flex items-center gap-1 px-2 py-1 text-xs text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-lg transition-colors"
                                title={"Clear all"}
                            >
                                <Trash2 className="w-3.5 h-3.5" />
                                Clear all
                            </button>
                        )}
                    </div>
                </div>
                <div className="px-5 py-3 border-b border-slate-100 dark:border-slate-700/50 flex items-center gap-3 flex-wrap bg-slate-50/60 dark:bg-slate-900/30">
                    <div className="relative flex-1 min-w-[220px] max-w-[360px]">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                        <input
                            type="text"
                            value={historyKeyword}
                            onChange={e => setHistoryKeyword(e.target.value)}
                            placeholder={"Search task ID, test requirements, or target URL"}
                            className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 outline-none transition-all"
                        />
                    </div>
                    <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 rounded-lg p-1">
                        {([
                            ['all', "All statuses"],
                            ['completed', "Completed"],
                            ['failed', "Failed/canceled"],
                            ['running', "Running"],
                        ] as [MissionStatusFilter, string][]).map(([key, label]) => (
                            <button
                                key={key}
                                onClick={() => setHistoryStatusFilter(key)}
                                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${historyStatusFilter === key
                                    ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm'
                                    : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300'
                                    }`}
                            >
                                {label} ({statusCounts[key]})
                            </button>
                        ))}
                    </div>
                    <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 rounded-lg p-1">
                        {([
                            ['latest', "Newest first"],
                            ['bugs_first', "Issues first"],
                            ['pending_report_first', "Pending reports first"],
                            ['report_ready_first', "Available reports first"],
                        ] as [MissionHistorySort, string][]).map(([key, label]) => (
                            <button
                                key={key}
                                onClick={() => setHistorySort(key)}
                                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${historySort === key
                                    ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm'
                                    : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300'
                                    }`}
                            >
                                {label}
                            </button>
                        ))}
                    </div>
                    <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 rounded-lg p-1">
                        {([
                            ['all', `All tasks (${filteredMissions.length})`],
                            ['selected', `Selected for batch only (${selectedMissionIds.length})`],
                        ] as [MissionSelectionScope, string][]).map(([key, label]) => (
                            <button
                                key={key}
                                onClick={() => setHistorySelectionScope(key)}
                                disabled={key === 'selected' && selectedMissionIds.length === 0}
                                data-testid={`commander-history-selection-scope-${key}`}
                                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${
                                    historySelectionScope === key
                                        ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm'
                                        : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300'
                                } disabled:opacity-40 disabled:cursor-not-allowed`}
                            >
                                {label}
                            </button>
                        ))}
                    </div>
                    <div className="flex items-center gap-2 ml-auto">
                        <button
                            onClick={toggleSelectVisibleMissions}
                            className="px-2.5 py-1 text-[11px] font-medium rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                        >
                            {allVisibleSelected ? "Deselect current list" : "Select current list"}
                        </button>
                        {selectedMissionIds.length > 0 && (
                            <>
                                <span className="text-[11px] text-slate-500 dark:text-slate-400">
                                    Selected {selectedMissionIds.length} tasks
                                </span>
                                <button
                                    onClick={() => void handleBulkGenerateReports()}
                                    className="px-2.5 py-1 text-[11px] font-medium rounded-lg border border-emerald-200 dark:border-emerald-500/30 text-emerald-600 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 transition-colors"
                                >
                                    Generate reports in bulk
                                </button>
                                <button
                                    onClick={() => void handleBulkDelete()}
                                    className="px-2.5 py-1 text-[11px] font-medium rounded-lg border border-red-200 dark:border-red-500/30 text-red-600 dark:text-red-300 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors"
                                >
                                    Delete in bulk
                                </button>
                            </>
                        )}
                    </div>
                    <span className="text-[11px] text-slate-400">
                        <span data-testid="commander-history-visible-count">
                        Showing {visibleMissions.length} / {missions.length} tasks
                        </span>
                    </span>
                </div>
                {visibleMissions.length > 0 && (
                    <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-700/50 bg-white/80 dark:bg-slate-900/20 space-y-3">
                        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3">
                            {[
                                {
                                    key: 'mission_scope',
                                    icon: <Activity className="w-4 h-4 text-indigo-500" />,
                                    title: "Current view",
                                    value: `${historyOverview.missionCount} entries`,
                                    detail: `Running ${historyOverview.runningCount} · Completed ${historyOverview.completedCount}`,
                                },
                                {
                                    key: 'bug_scope',
                                    icon: <AlertTriangle className="w-4 h-4 text-red-500" />,
                                    title: "Issue overview",
                                    value: `${historyOverview.bugMissionCount} tasks`,
                                    detail: `Total ${historyOverview.bugItemCount} issues`,
                                },
                                {
                                    key: 'test_lines',
                                    icon: <XCircle className="w-4 h-4 text-amber-500" />,
                                    title: "Failed test tracks",
                                    value: `${historyOverview.failedTestLines} entries`,
                                    detail: `Total test tracks ${historyOverview.totalTestLines} entries`,
                                },
                                {
                                    key: 'report_coverage',
                                    icon: <FileText className="w-4 h-4 text-emerald-500" />,
                                    title: "Report coverage",
                                    value: `${historyOverview.reportReadyCount} available`,
                                    detail: `Pending ${historyOverview.pendingReportCount} entries`,
                                },
                                {
                                    key: 'success_rate',
                                    icon: <Gauge className="w-4 h-4 text-cyan-500" />,
                                    title: "Average success rate",
                                    value: historyOverview.averageSuccessRate === null
                                        ? '—'
                                        : `${historyOverview.averageSuccessRate}%`,
                                    detail: historyOverview.averageSuccessRateSamples > 0
                                        ? `Based on ${historyOverview.averageSuccessRateSamples} summarized tasks`
                                        : "No results available to calculate",
                                },
                            ].map(card => (
                                <div
                                    key={card.key}
                                    className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/80 dark:bg-slate-800/70 px-4 py-3"
                                >
                                    <div className="flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400">
                                        {card.icon}
                                        {card.title}
                                    </div>
                                    <div className="mt-2 text-lg font-semibold text-slate-900 dark:text-white">
                                        {card.value}
                                    </div>
                                    <div className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                                        {card.detail}
                                    </div>
                                </div>
                            ))}
                        </div>
                        {bugHotspots.length > 0 && (
                            <div
                                data-testid="commander-bug-hotspots"
                                className="rounded-xl border border-red-100 dark:border-red-500/20 bg-red-50/50 dark:bg-red-500/5 px-4 py-3"
                            >
                                <div className="flex items-center justify-between gap-3">
                                    <div className="flex items-center gap-2 text-xs font-medium text-red-600 dark:text-red-300">
                                        <AlertTriangle className="w-4 h-4" />
                                        Frequent issue hotspots
                                        {activeBugHotspotKey && (
                                            <span className="rounded-full bg-red-100 dark:bg-red-500/20 px-2 py-0.5 text-[10px] font-medium">
                                                Filtered by hotspot
                                            </span>
                                        )}
                                    </div>
                                    {activeBugHotspotKey && (
                                        <button
                                            onClick={() => setActiveBugHotspotKey(null)}
                                            className="text-[11px] font-medium text-red-600 dark:text-red-300 hover:text-red-700 transition-colors"
                                        >
                                            Clear hotspot filter
                                        </button>
                                    )}
                                </div>
                                <div className="mt-3 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
                                    {bugHotspots.map(hotspot => {
                                        const primaryMission = hotspot.primaryMissionId
                                            ? missionMapById.get(hotspot.primaryMissionId)
                                            : undefined;
                                        const primaryMissionReportUrl = primaryMission?.execution_group_id
                                            ? buildCommanderReportUrl(reportMap[primaryMission.execution_group_id])
                                            : null;
                                        const reportedMissionCount = hotspot.missionIds.filter(missionId => {
                                            const mission = missionMapById.get(missionId);
                                            if (!mission?.execution_group_id) return false;
                                            return Boolean(buildCommanderReportUrl(reportMap[mission.execution_group_id]));
                                        }).length;
                                        return (
                                            <div
                                                key={hotspot.key}
                                                data-testid="commander-bug-hotspot-card"
                                                className={`rounded-lg border px-3 py-2 text-left transition-all ${
                                                    activeBugHotspotKey === hotspot.key
                                                        ? 'border-red-300 dark:border-red-400/50 bg-red-100/80 dark:bg-red-500/15 shadow-sm'
                                                        : 'border-red-100 dark:border-red-500/20 bg-white/80 dark:bg-slate-900/40 hover:bg-red-50 dark:hover:bg-red-500/10'
                                                }`}
                                            >
                                                <div className="flex items-center justify-between gap-2">
                                                    <div className="flex items-center gap-2 text-xs font-semibold text-slate-700 dark:text-slate-100">
                                                        {TEST_TYPE_ICON[hotspot.testType] || <Zap className="w-3.5 h-3.5" />}
                                                        <span className="truncate">{hotspot.title}</span>
                                                    </div>
                                                    <div className="flex items-center gap-1">
                                                        <span className={`shrink-0 inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${
                                                            getBugSeverityRank(hotspot.status) >= 3
                                                                ? 'bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-300'
                                                                : getBugSeverityRank(hotspot.status) === 2
                                                                    ? 'bg-amber-100 dark:bg-amber-500/20 text-amber-600 dark:text-amber-300'
                                                                    : 'bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-300'
                                                        }`}>
                                                            {getBugSeverityTone(hotspot.status)}
                                                        </span>
                                                        <span className="shrink-0 inline-flex items-center rounded-full bg-red-100 dark:bg-red-500/20 px-2 py-0.5 text-[10px] font-medium text-red-600 dark:text-red-300">
                                                            {hotspot.count} occurrences
                                                        </span>
                                                    </div>
                                                </div>
                                                <div className="mt-1 text-xs text-slate-500 dark:text-slate-400 line-clamp-2">
                                                    {hotspot.summary}
                                                </div>
                                                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                                                    {hotspot.missionIds.slice(0, 2).map(missionId => (
                                                        <button
                                                            key={`${hotspot.key}_${missionId}`}
                                                            onClick={() => focusHotspotMission(missionId, hotspot.key)}
                                                            className="inline-flex items-center gap-1 rounded-md border border-slate-200 dark:border-slate-700 bg-white/80 dark:bg-slate-900/40 px-2 py-1 text-[10px] text-slate-500 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-300 transition-colors"
                                                        >
                                                            #{missionId}
                                                        </button>
                                                    ))}
                                                    {hotspot.missionIds.length > 2 && (
                                                        <span className="text-[10px] text-slate-400 dark:text-slate-500">
                                                            +{hotspot.missionIds.length - 2} entries
                                                        </span>
                                                    )}
                                                </div>
                                                <div className="mt-3 flex items-center justify-between gap-3">
                                                    <span className="text-[10px] text-slate-500 dark:text-slate-400">
                                                        Affects {hotspot.missionIds.length} tasks · Reports {reportedMissionCount}/{hotspot.missionIds.length}
                                                    </span>
                                                    <div className="flex items-center gap-2">
                                                        {primaryMission && (
                                                            <button
                                                                onClick={() => void openMissionReport(primaryMission)}
                                                                className="inline-flex items-center gap-1 text-[10px] font-medium text-emerald-600 dark:text-emerald-300 hover:text-emerald-700 transition-colors"
                                                            >
                                                                <FileText className="w-3 h-3" />
                                                                {primaryMissionReportUrl ? "View first report" : "Generate first report"}
                                                            </button>
                                                        )}
                                                        {primaryMission && (
                                                            <button
                                                                onClick={() => openExecutionCenter(primaryMission, hotspot.primaryExecutionRecordId)}
                                                                className="inline-flex items-center gap-1 text-[10px] font-medium text-indigo-600 dark:text-indigo-300 hover:text-indigo-700 transition-colors"
                                                            >
                                                                <ExternalLink className="w-3 h-3" />
                                                                Locate first issue
                                                            </button>
                                                        )}
                                                        <button
                                                            onClick={() => setActiveBugHotspotKey(prev => prev === hotspot.key ? null : hotspot.key)}
                                                            className="text-[10px] font-medium text-red-600 dark:text-red-300 hover:text-red-700 transition-colors"
                                                        >
                                                            {activeBugHotspotKey === hotspot.key ? "Clear filter" : "Related tasks only"}
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        )}
                        {historyOverview.bugItemCount > 0 && (
                            <div
                                data-testid="commander-bug-board"
                                className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white/90 dark:bg-slate-900/40 px-4 py-3"
                            >
                                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                                    <div>
                                        <div className="flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-300">
                                            <AlertTriangle className="w-4 h-4 text-red-500" />
                                            Issue list
                                        </div>
                                        <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                                            View issues, associated tasks, report status, and troubleshooting links immediately. Current filter: {bugBoardItems.length} issues affecting {bugBoardMissionIds.length} tasks.
                                        </div>
                                        {bugBoardMissionIds.length > 0 && (
                                            <div
                                                data-testid="commander-bug-board-selection-summary"
                                                className="mt-2 text-[11px] text-slate-500 dark:text-slate-400"
                                            >
                                                Added to batch: {selectedBugBoardMissionCount} / {bugBoardMissionIds.length} tasks · Pending reports: {bugBoardPendingReportMissionIds.length} entries
                                                {historySelectionScope === 'selected' && (
                                                    <span
                                                        data-testid="commander-bug-board-selected-scope-badge"
                                                        className="ml-2 inline-flex items-center rounded-full bg-indigo-50 dark:bg-indigo-500/10 px-2 py-0.5 text-[10px] text-indigo-600 dark:text-indigo-300"
                                                    >
                                                        Showing only tasks added to the batch
                                                    </span>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                    <div className="flex flex-wrap items-center gap-2">
                                        {([
                                            ['all', `All issues (${historyOverview.bugItemCount})`],
                                            ['error', "Error"],
                                            ['warning', "Warning"],
                                            ['recovered', "Recovered"],
                                        ] as [CommanderBugBoardSeverityFilter, string][]).map(([key, label]) => (
                                            <button
                                                key={key}
                                                onClick={() => setBugBoardSeverityFilter(key)}
                                                data-testid={`commander-bug-board-filter-${key}`}
                                                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${
                                                    bugBoardSeverityFilter === key
                                                        ? 'bg-slate-900 dark:bg-white text-white dark:text-slate-900 shadow-sm'
                                                        : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'
                                                }`}
                                            >
                                                {label}
                                            </button>
                                        ))}
                                        {bugBoardMissionIds.length > 0 && (
                                            <button
                                                onClick={toggleSelectBugBoardMissions}
                                                data-testid="commander-bug-board-bulk-toggle"
                                                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${
                                                    allBugBoardSelected
                                                        ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                                                        : 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-500/20'
                                                }`}
                                            >
                                                {allBugBoardSelected ? `Deselect related tasks (${bugBoardMissionIds.length})` : `Select related tasks (${bugBoardMissionIds.length})`}
                                            </button>
                                        )}
                                        <button
                                                onClick={() => void handleBugBoardGenerateReports()}
                                                data-testid="commander-bug-board-generate-reports"
                                            disabled={selectedBugBoardMissionCount > 0
                                                ? selectedBugBoardPendingReportMissionIds.length === 0
                                                : bugBoardPendingReportMissionIds.length === 0}
                                            className="px-2.5 py-1 rounded-md text-[11px] font-medium bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-300 hover:bg-emerald-100 dark:hover:bg-emerald-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                            {selectedBugBoardMissionCount > 0
                                                ? selectedBugBoardPendingReportMissionIds.length > 0
                                                    ? `Generate missing reports for selected tasks (${selectedBugBoardPendingReportMissionIds.length})`
                                                    : `All selected tasks have reports (${selectedBugBoardMissionCount})`
                                                : `Generate missing reports for current issues (${bugBoardPendingReportMissionIds.length})`}
                                        </button>
                                        {selectedMissionIds.length > 0 && (
                                            <button
                                                onClick={() => setHistorySelectionScope(prev => prev === 'selected' ? 'all' : 'selected')}
                                                data-testid="commander-bug-board-toggle-selected-view"
                                                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${
                                                    historySelectionScope === 'selected'
                                                        ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                                                        : 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-500/20'
                                                }`}
                                            >
                                                {historySelectionScope === 'selected'
                                                    ? `Return to all tasks (${filteredMissions.length})`
                                                    : `Selected for batch only (${selectedMissionIds.length})`}
                                            </button>
                                        )}
                                    </div>
                                </div>
                                {selectedMissionSummary.total > 0 && (
                                    <div
                                        data-testid="commander-bug-board-batch-actions"
                                        className="mt-3 rounded-lg border border-indigo-100 dark:border-indigo-500/20 bg-indigo-50/60 dark:bg-indigo-500/5 px-3 py-3"
                                    >
                                        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                                            <div className="text-[11px] text-slate-600 dark:text-slate-300">
                                                Processing selected tasks: {selectedMissionSummary.total} entries
                                                <span className="mx-2 text-slate-300 dark:text-slate-600">|</span>
                                                With issues {selectedMissionSummary.withBugs} entries
                                                <span className="mx-2 text-slate-300 dark:text-slate-600">|</span>
                                                Reports available {selectedMissionSummary.reportReady} entries
                                                <span className="mx-2 text-slate-300 dark:text-slate-600">|</span>
                                                Reports pending {selectedMissionSummary.pendingReport} entries
                                            </div>
                                            <div className="flex flex-wrap items-center gap-2">
                                                <button
                                                    onClick={() => void handleBulkGenerateReports()}
                                                    data-testid="commander-bug-board-batch-generate"
                                                    disabled={selectedMissionSummary.pendingReport === 0}
                                                    className="px-2.5 py-1 rounded-md text-[11px] font-medium bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-300 hover:bg-emerald-100 dark:hover:bg-emerald-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                                                >
                                                    {selectedMissionSummary.pendingReport > 0
                                                        ? `Generate reports in bulk (${selectedMissionSummary.pendingReport})`
                                                        : `All reports available (${selectedMissionSummary.total})`}
                                                </button>
                                                <button
                                                    onClick={() => void handleBulkDelete()}
                                                    data-testid="commander-bug-board-batch-delete"
                                                    className="px-2.5 py-1 rounded-md text-[11px] font-medium bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-500/20 transition-all"
                                                >
                                                    Delete in bulk ( {selectedMissionSummary.total})
                                                </button>
                                                <button
                                                    onClick={clearSelectedMissions}
                                                    data-testid="commander-bug-board-batch-clear"
                                                    className="px-2.5 py-1 rounded-md text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-all"
                                                >
                                                    Clear selection
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                )}
                                {bugBoardActionFeedback && (
                                    <div
                                        data-testid="commander-bug-board-feedback"
                                        className={`mt-3 rounded-lg border px-3 py-2 text-[11px] ${
                                            bugBoardActionFeedback.tone === 'success'
                                                ? 'border-emerald-100 dark:border-emerald-500/20 bg-emerald-50/70 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                                                : bugBoardActionFeedback.tone === 'warning'
                                                    ? 'border-amber-100 dark:border-amber-500/20 bg-amber-50/70 dark:bg-amber-500/10 text-amber-700 dark:text-amber-300'
                                                    : 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/70 text-slate-600 dark:text-slate-300'
                                        }`}
                                    >
                                        <div className="flex flex-col gap-2">
                                            <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                                                <span>{bugBoardActionFeedback.message}</span>
                                                <span className="text-[10px] opacity-70">
                                                    Recent action {new Date(bugBoardActionFeedback.timestamp).toLocaleTimeString('en-US')}
                                                </span>
                                            </div>
                                            <div className="flex flex-wrap items-center gap-2">
                                                {bugBoardActionFeedback.actionKind && bugBoardActionFeedback.missionIds?.length ? (
                                                    <button
                                                        onClick={handleFeedbackAction}
                                                        data-testid="commander-bug-board-feedback-action"
                                                        className="px-2.5 py-1 rounded-md text-[11px] font-medium bg-white/80 dark:bg-slate-900/40 text-slate-700 dark:text-slate-200 hover:bg-white dark:hover:bg-slate-900 transition-all"
                                                    >
                                                        {bugBoardActionFeedback.actionKind === 'restore_selected' ? "Restore selection" : `Show only this batch (${bugBoardActionFeedback.missionIds.length})`}
                                                    </button>
                                                ) : null}
                                                <button
                                                    onClick={() => setBugBoardActionFeedback(null)}
                                                    data-testid="commander-bug-board-feedback-dismiss"
                                                    className="px-2.5 py-1 rounded-md text-[11px] font-medium bg-transparent text-slate-500 dark:text-slate-300 hover:text-slate-700 dark:hover:text-white transition-all"
                                                >
                                                    Hide feedback
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                )}
                                {bugBoardItems.length === 0 ? (
                                    <div className="mt-4 rounded-lg border border-dashed border-slate-200 dark:border-slate-700 px-4 py-5 text-center text-xs text-slate-400 dark:text-slate-500">
                                        No issues match the current filters. Switch to All issues or choose another hotspot.
                                    </div>
                                ) : (
                                    <div className="mt-4 space-y-3">
                                        {bugBoardItems.map(item => {
                                            const mission = missionMapById.get(item.missionId);
                                            const missionSelected = selectedMissionIds.includes(item.missionId);
                                            return (
                                            <div
                                                key={item.key}
                                                data-testid="commander-bug-board-item"
                                                className="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50/80 dark:bg-slate-800/60 px-4 py-3"
                                            >
                                                    <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                                                        <div className="min-w-0 flex-1">
                                                            <div className="flex flex-wrap items-center gap-2">
                                                                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${
                                                                    item.severityKey === 'error'
                                                                        ? 'bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-300'
                                                                        : item.severityKey === 'warning'
                                                                            ? 'bg-amber-100 dark:bg-amber-500/20 text-amber-600 dark:text-amber-300'
                                                                            : item.severityKey === 'recovered'
                                                                                ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-300'
                                                                                : 'bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-300'
                                                                }`}>
                                                                    {getBugSeverityTone(item.status)}
                                                                </span>
                                                                <span className="inline-flex items-center gap-1 text-xs font-semibold text-slate-700 dark:text-slate-100">
                                                                    {TEST_TYPE_ICON[item.testType] || <Zap className="w-3.5 h-3.5" />}
                                                                    {item.title}
                                                                </span>
                                                                <span className="inline-flex items-center rounded-full bg-slate-100 dark:bg-slate-700 px-2 py-0.5 text-[10px] text-slate-500 dark:text-slate-300">
                                                                    #{item.missionId}
                                                                </span>
                                                                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] ${
                                                                    item.hasReport
                                                                        ? 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-300'
                                                                        : 'bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-300'
                                                                }`}>
                                                                    {item.hasReport ? "Report available" : "Report pending"}
                                                                </span>
                                                            </div>
                                                            <div className="mt-2 text-sm text-slate-700 dark:text-slate-200">
                                                                {item.summary}
                                                            </div>
                                                            <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-400 dark:text-slate-500">
                                                                <span className="truncate max-w-[360px]">Task: {item.missionInput || "Unnamed task"}</span>
                                                                <span>Status: {STATUS_CONFIG[item.missionStatus]?.label || item.missionStatus}</span>
                                                                <span>{item.missionCreatedAt ? new Date(item.missionCreatedAt).toLocaleString('en-US') : "Unknown time"}</span>
                                                            </div>
                                                        </div>
                                                        <div className="flex flex-wrap items-center gap-2 xl:justify-end">
                                                            <button
                                                                onClick={() => toggleMissionSelection(item.missionId)}
                                                                data-testid="commander-bug-board-item-select"
                                                                className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-[11px] font-medium transition-colors ${
                                                                    missionSelected
                                                                        ? 'border-indigo-200 dark:border-indigo-500/30 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-300'
                                                                        : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700'
                                                                }`}
                                                            >
                                                                {missionSelected ? "Added to batch" : "Add to batch"}
                                                            </button>
                                                            <button
                                                                onClick={() => focusMission(item.missionId)}
                                                                className="inline-flex items-center gap-1 rounded-md border border-slate-200 dark:border-slate-700 px-2.5 py-1 text-[11px] font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                                                            >
                                                                Focus task
                                                            </button>
                                                            {mission && (
                                                                <button
                                                                    onClick={() => void openMissionReport(mission)}
                                                                    className="inline-flex items-center gap-1 rounded-md border border-emerald-200 dark:border-emerald-500/30 px-2.5 py-1 text-[11px] font-medium text-emerald-600 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 transition-colors"
                                                                >
                                                                    <FileText className="w-3.5 h-3.5" />
                                                                    {item.hasReport ? "View report" : "Generate report"}
                                                                </button>
                                                            )}
                                                            {mission && item.executionRecordId && item.executionGroupId && (
                                                                <button
                                                                    onClick={() => openExecutionCenter(mission, item.executionRecordId)}
                                                                    className="inline-flex items-center gap-1 rounded-md border border-indigo-200 dark:border-indigo-500/30 px-2.5 py-1 text-[11px] font-medium text-indigo-600 dark:text-indigo-300 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 transition-colors"
                                                                >
                                                                    <ExternalLink className="w-3.5 h-3.5" />
                                                                    Locate record
                                                                </button>
                                                            )}
                                                        </div>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}

                {missions.length === 0 ? (
                    <div className="px-5 py-10 text-center text-sm text-slate-400 dark:text-slate-500">
                        No task records yet. Enter requirements and click Launch to start your first test.
                    </div>
                ) : filteredMissions.length === 0 ? (
                    <div className="px-5 py-10 text-center text-sm text-slate-400 dark:text-slate-500">
                        No tasks match the current filters. Try changing the filters.
                    </div>
                ) : (
                    <div className="divide-y divide-slate-100 dark:divide-slate-700/50">
                        {visibleMissions.map(m => {
                            const cfg = STATUS_CONFIG[m.status] || STATUS_CONFIG.pending;
                            const isExpanded = expandedMission === m.mission_id;
                            const missionBugs = getMissionBugSummaryItems(m);
                            const missionBugPreview = missionBugs.slice(0, 2);
                            const missionReport = m.execution_group_id ? reportMap[m.execution_group_id] : undefined;
                            const missionReportUrl = buildCommanderReportUrl(missionReport);
                            const missionMetaBadges = getCommanderMissionMetaBadges(m, Boolean(missionReportUrl));
                            const isSelected = selectedMissionIds.includes(m.mission_id);

                            return (
                                <div key={m.mission_id}>
                                    <div
                                        onClick={() => {
                                            setExpandedMission(isExpanded ? null : m.mission_id);
                                            if (!isExpanded) setActiveMission(m);
                                        }}
                                        className="group flex items-center gap-3 px-5 py-3 hover:bg-slate-50 dark:hover:bg-slate-700/30 cursor-pointer transition-colors"
                                    >
                                        <input
                                            type="checkbox"
                                            checked={isSelected}
                                            onClick={(e) => e.stopPropagation()}
                                            onChange={() => toggleMissionSelection(m.mission_id)}
                                            className="w-4 h-4 rounded border-slate-300 text-indigo-500 focus:ring-indigo-500/30"
                                        />
                                        <div className={`shrink-0 ${cfg.color}`}>{cfg.icon}</div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm text-slate-700 dark:text-slate-200 truncate">
                                                {m.user_input}
                                            </p>
                                            <p className="text-xs text-slate-400 mt-0.5">
                                                #{m.mission_id} · {new Date(m.created_at).toLocaleString('en-US')}
                                            </p>
                                            <div className="flex flex-wrap items-center gap-1.5 mt-1">
                                                {missionMetaBadges.map(badge => (
                                                    <span
                                                        key={`${m.mission_id}_${badge.key}`}
                                                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium ${MISSION_META_TONE_CLASS[badge.tone]}`}
                                                    >
                                                        {badge.label}
                                                    </span>
                                                ))}
                                            </div>
                                            {missionBugPreview.length > 0 && (
                                                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                                                    {missionBugPreview.map((bug, index) => (
                                                        <span
                                                            key={`${m.mission_id}_preview_${bug.test_type}_${index}`}
                                                            className="inline-flex max-w-full items-center gap-1 rounded-md border border-red-100 dark:border-red-500/20 bg-red-50/70 dark:bg-red-500/10 px-2 py-1 text-[10px] text-red-600 dark:text-red-300"
                                                        >
                                                            {TEST_TYPE_ICON[bug.test_type] || <Zap className="w-3 h-3" />}
                                                            <span className="truncate max-w-[280px]">{bug.summary}</span>
                                                        </span>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                        {missionBugs.length > 0 && (
                                            <span className="shrink-0 inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-300">
                                                <AlertTriangle className="w-3.5 h-3.5" />
                                                Bug
                                            </span>
                                        )}
                                        {missionReportUrl && (
                                            <span className="shrink-0 inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-300">
                                                <FileText className="w-3.5 h-3.5" />
                                                Report
                                            </span>
                                        )}
                                        <div className={`shrink-0 px-2 py-1 rounded text-xs font-medium ${cfg.bg} ${cfg.color}`}>
                                            {cfg.label}
                                        </div>
                                        {m.execution_group_id && (
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    void openMissionReport(m);
                                                }}
                                                disabled={reportLoadingId === m.execution_group_id}
                                                className="shrink-0 px-2 py-1 text-xs text-indigo-600 dark:text-indigo-300 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 rounded-lg transition-colors disabled:opacity-60 disabled:cursor-not-allowed opacity-0 group-hover:opacity-100"
                                                title={missionReportUrl ? "View batch report" : "Generate batch report"}
                                            >
                                                {reportLoadingId === m.execution_group_id
                                                    ? "Generating..."
                                                    : missionReportUrl
                                                        ? "View report"
                                                        : "Generate report"}
                                            </button>
                                        )}
                                        <button
                                            onClick={async (e) => {
                                                e.stopPropagation();
                                                const ok = await confirm("Delete task", "Delete this task record?");
                                                if (!ok) return;
                                                await commanderDeleteMission(m.mission_id);
                                                setMissions(prev => prev.filter(x => x.mission_id !== m.mission_id));
                                                setSelectedMissionIds(prev => prev.filter(id => id !== m.mission_id));
                                                if (activeMission?.mission_id === m.mission_id) {
                                                    setActiveMission(null);
                                                }
                                                showToast('success', "Task record deleted.");
                                            }}
                                            className="shrink-0 p-1 text-slate-300 hover:text-red-500 rounded hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors opacity-0 group-hover:opacity-100"
                                            title={"Delete"}
                                        >
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                        <div className="shrink-0 text-slate-400">
                                            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                                        </div>
                                    </div>

                                    {isExpanded && (
                                        <div className="px-5 py-3 bg-slate-50 dark:bg-slate-800/50 border-t border-slate-100 dark:border-slate-700/50">
                                            <div className="flex flex-wrap items-center gap-2 mb-3">
                                                {m.execution_group_id && (
                                                    <button
                                                        onClick={() => openExecutionCenter(m)}
                                                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-indigo-200 dark:border-indigo-500/30 text-indigo-600 dark:text-indigo-300 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 transition-colors text-xs"
                                                    >
                                                        <ExternalLink className="w-3.5 h-3.5" />
                                                        View execution center
                                                    </button>
                                                )}
                                                {m.execution_group_id && (
                                                    <button
                                                        onClick={() => openMissionReport(m)}
                                                        disabled={reportLoadingId === m.execution_group_id}
                                                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-emerald-200 dark:border-emerald-500/30 text-emerald-600 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 transition-colors text-xs disabled:opacity-60 disabled:cursor-not-allowed"
                                                    >
                                                        {reportLoadingId === m.execution_group_id ? (
                                                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                                        ) : (
                                                            <FileText className="w-3.5 h-3.5" />
                                                        )}
                                                        {missionReportUrl ? "View batch report" : "Generate batch report"}
                                                    </button>
                                                )}
                                            </div>
                                            {m.report && (
                                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
                                                    {[
                                                        { label: "Total tests", value: (m.report.summary as Record<string, unknown>)?.total_tests ?? '–' },
                                                        { label: "Passed", value: (m.report.summary as Record<string, unknown>)?.completed ?? '–' },
                                                        { label: "Failed", value: (m.report.summary as Record<string, unknown>)?.failed ?? '–' },
                                                        { label: "Success rate", value: `${(m.report.summary as Record<string, unknown>)?.success_rate ?? '–'}%` },
                                                    ].map(s => (
                                                        <div key={s.label} className="text-center py-2 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                                                            <div className="text-lg font-bold text-slate-700 dark:text-slate-200">{String(s.value)}</div>
                                                            <div className="text-xs text-slate-400">{s.label}</div>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                            {missionBugs.length > 0 && (
                                                <div className="rounded-xl border border-red-100 dark:border-red-500/20 bg-white dark:bg-slate-900/40 p-4">
                                                    <div className="flex items-center justify-between gap-3 mb-3">
                                                        <div className="flex items-center gap-2 text-sm font-semibold text-red-700 dark:text-red-300">
                                                            <AlertTriangle className="w-4 h-4" />
                                                            Issues found by this agent fleet task
                                                        </div>
                                                        {m.execution_group_id && (
                                                            <button
                                                                onClick={() => openExecutionCenter(m)}
                                                                className="inline-flex items-center gap-1 text-xs text-indigo-600 dark:text-indigo-300 hover:text-indigo-700 transition-colors"
                                                            >
                                                                <ExternalLink className="w-3.5 h-3.5" />
                                                                Open execution center
                                                            </button>
                                                        )}
                                                    </div>
                                                    <div className="space-y-2">
                                                        {missionBugs.slice(0, 6).map((bug, index) => (
                                                            <div key={`${m.mission_id}_${bug.test_type}_${index}`} className="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50/80 dark:bg-slate-800/60 px-3 py-2">
                                                                <div className="flex items-start justify-between gap-3">
                                                                    <div className="flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-300">
                                                                        {TEST_TYPE_ICON[bug.test_type] || <Zap className="w-3.5 h-3.5" />}
                                                                        <span>{bug.title}</span>
                                                                    </div>
                                                                    {bug.execution_record_id && m.execution_group_id && (
                                                                        <button
                                                                            onClick={() => openExecutionCenter(m, bug.execution_record_id)}
                                                                            className="shrink-0 inline-flex items-center gap-1 text-[11px] text-indigo-600 dark:text-indigo-300 hover:text-indigo-700 transition-colors"
                                                                        >
                                                                            <ExternalLink className="w-3 h-3" />
                                                                            Locate record
                                                                        </button>
                                                                    )}
                                                                </div>
                                                                <div className="mt-1 text-sm text-slate-700 dark:text-slate-200">{bug.summary}</div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};

export default CommanderPage;
