import type {
    FrontdoorFinding,
    FrontdoorGateSummary,
    FrontdoorTask,
    FrontdoorTaskKind,
    FrontdoorVerificationState,
} from '../services/frontdoorTaskService';

export interface FrontdoorTaskKindOption {
    kind: FrontdoorTaskKind;
    title: string;
    description: string;
    targetLabel: string;
    placeholder: string;
}

export const TASK_KIND_OPTIONS: FrontdoorTaskKindOption[] = [
    {
        kind: 'general',
        title: "General orchestration",
        description: "Start comprehensive test orchestration with one sentence to quickly validate a real task objective.",
        targetLabel: "Target URL (optional)",
        placeholder: "Example: Check the login, ordering, and payment workflows",
    },
    {
        kind: 'prototype',
        title: "Prototype testing",
        description: "Provide a URL, file, or directory to generate evidence, findings, and a gate decision.",
        targetLabel: "Prototype source",
        placeholder: "Example: D:\\prototype or https://example.com",
    },
    {
        kind: 'exploration',
        title: "Exploratory testing",
        description: "Explore a target page to discover broken links, errors, and unknown issues.",
        targetLabel: "Target URL",
        placeholder: "Example: Explore order errors and identify critical risks",
    },
];

export function getTaskKindMeta(taskKind: FrontdoorTaskKind | string): FrontdoorTaskKindOption {
    return TASK_KIND_OPTIONS.find((item) => item.kind === taskKind) ?? TASK_KIND_OPTIONS[0];
}

export function statusMeta(status: string): { label: string; variant: 'success' | 'warning' | 'error' | 'info' | 'neutral' } {
    const normalized = String(status || '').toLowerCase();
    if (['completed', 'success'].includes(normalized)) return { label: "Completed", variant: 'success' };
    if (['failed', 'error'].includes(normalized)) return { label: "Failed", variant: 'error' };
    if (['cancelled', 'stopped'].includes(normalized)) return { label: "Stopped", variant: 'neutral' };
    if (['parsing', 'planning', 'dispatching', 'executing', 'reporting', 'pending'].includes(normalized)) {
        return { label: "Running", variant: 'warning' };
    }
    return { label: "Unknown", variant: 'info' };
}

export function gateMeta(status: string): { label: string; variant: 'success' | 'warning' | 'error' | 'info' } {
    const normalized = String(status || '').toLowerCase();
    if (normalized === 'failed') return { label: "Confirmed issues", variant: 'error' };
    if (normalized === 'warning') return { label: "Human confirmation required", variant: 'warning' };
    if (normalized === 'passed') return { label: "Verified", variant: 'success' };
    return { label: "Pending decision", variant: 'info' };
}

export function isRunningStatus(status: string): boolean {
    return ['pending', 'parsing', 'planning', 'dispatching', 'executing', 'reporting'].includes(String(status || '').toLowerCase());
}

export function formatTimestamp(value?: string | null): string {
    if (!value) return '--';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString('en-US', { hour12: false });
}

export function hasStaticUnprovable(gateSummary?: FrontdoorGateSummary | null): boolean {
    const count = Number(gateSummary?.metrics?.static_unprovable_count ?? 0);
    return Number.isFinite(count) && count > 0;
}

export function formatMetricValue(value: unknown): string {
    if (Array.isArray(value)) return value.join(', ');
    if (value && typeof value === 'object') return JSON.stringify(value);
    return String(value ?? '--');
}

export function verificationStateMeta(
    verificationState?: FrontdoorVerificationState | null,
): { label: string; variant: 'success' | 'warning' | 'error' | 'info'; summary: string } {
    const normalized = String(verificationState?.status || '').toLowerCase();
    if (normalized === 'verified_passed') {
        return {
            label: verificationState?.label || "Verified",
            variant: 'success',
            summary: verificationState?.summary || "This task has been verified in the available context.",
        };
    }
    if (normalized === 'context_unprovable') {
        return {
            label: verificationState?.label || "Not provable in the current context",
            variant: 'warning',
            summary: verificationState?.summary || "Some points remain unprovable from the static prototype or current environment.",
        };
    }
    if (normalized === 'issues_found') {
        return {
            label: verificationState?.label || "Confirmed issues",
            variant: 'error',
            summary: verificationState?.summary || "This task has identified confirmed issues.",
        };
    }
    return {
        label: verificationState?.label || "Pending decision",
        variant: 'info',
        summary: verificationState?.summary || "This task does not yet have a stable conclusion.",
    };
}

function parseTaskTime(task: FrontdoorTask): number {
    const candidate = task.completed_at || task.started_at || task.created_at || '';
    const ts = Date.parse(candidate);
    return Number.isFinite(ts) ? ts : 0;
}

export interface FrontdoorLineageContext {
    sortedTasks: FrontdoorTask[];
    currentTask: FrontdoorTask | null;
    currentIndex: number;
    olderTask: FrontdoorTask | null;
    newerTask: FrontdoorTask | null;
    comparableTask: FrontdoorTask | null;
}

export function sortLineageTasks(tasks: FrontdoorTask[]): FrontdoorTask[] {
    return [...tasks].sort((left, right) => {
        const timeDiff = parseTaskTime(right) - parseTaskTime(left);
        if (timeDiff !== 0) return timeDiff;
        return String(right.task_id || '').localeCompare(String(left.task_id || ''));
    });
}

export function buildLineageContext(tasks: FrontdoorTask[], currentTaskId: string): FrontdoorLineageContext {
    const sortedTasks = sortLineageTasks(tasks);
    const currentIndex = sortedTasks.findIndex((task) => task.task_id === currentTaskId);
    const currentTask = currentIndex >= 0 ? sortedTasks[currentIndex] : null;
    const olderTask = currentIndex >= 0 ? sortedTasks[currentIndex + 1] || null : null;
    const newerTask = currentIndex > 0 ? sortedTasks[currentIndex - 1] || null : null;
    return {
        sortedTasks,
        currentTask,
        currentIndex,
        olderTask,
        newerTask,
        comparableTask: olderTask || newerTask || null,
    };
}

export interface FrontdoorFindingSeveritySummary {
    blocking: number;
    major: number;
    normal: number;
    pending_confirmation: number;
    other: number;
    total: number;
}

export interface FrontdoorTaskComparisonSummary {
    currentFindingCount: number;
    comparableFindingCount: number;
    findingDelta: number;
    currentSeveritySummary: FrontdoorFindingSeveritySummary;
    comparableSeveritySummary: FrontdoorFindingSeveritySummary;
    highRiskDelta: number;
    gateChanged: boolean;
    verificationChanged: boolean;
    decisionReasonChanged: boolean;
    metricChanges: FrontdoorMetricComparisonItem[];
    changedMetricCount: number;
}

export interface FrontdoorExecutionGroupTagSummary {
    isCurrentTaskGroup: boolean;
    isSameLineageGroup: boolean;
    isSameTaskKindReferenceGroup: boolean;
}

export interface FrontdoorGateHistoryLike {
    run_id?: string;
    status?: string;
    verdict?: {
        status?: string;
        summary?: string;
        checks?: FrontdoorGateCheckLike[];
        total_checks?: number;
        passed_checks?: number;
        failed_checks?: number;
    };
}

export interface FrontdoorGateDeepReadView {
    currentHistory: FrontdoorGateHistoryLike | null;
    comparableHistory: FrontdoorGateHistoryLike | null;
    gateCheckDiff: FrontdoorGateCheckDiffItem[];
    changedGateChecks: FrontdoorGateCheckDiffItem[];
}

export interface FrontdoorDeepView {
    currentTask: FrontdoorTask | null;
    lineageContext: FrontdoorLineageContext;
    comparableTask: FrontdoorTask | null;
    comparisonSummary: FrontdoorTaskComparisonSummary | null;
    sameTaskKindReferences: FrontdoorTask[];
    currentLineageGroupIds: Set<string>;
    sameTaskKindGroupIds: Set<string>;
    gateDeepRead: FrontdoorGateDeepReadView;
}

export interface FrontdoorMetricComparisonItem {
    key: string;
    currentValue: unknown;
    comparableValue: unknown;
    changed: boolean;
}

export interface FrontdoorGateCheckLike {
    rule_name: string;
    status?: string;
    message?: string;
}

export interface FrontdoorGateCheckDiffItem {
    ruleName: string;
    currentStatus: string;
    comparableStatus: string;
    currentMessage: string;
    comparableMessage: string;
    changed: boolean;
}

function normalizeFindingSeverity(severity: string): keyof Omit<FrontdoorFindingSeveritySummary, 'total'> {
    const normalized = String(severity || '').trim().toLowerCase();
    if (normalized === 'blocking') return 'blocking';
    if (normalized === 'major') return 'major';
    if (normalized === 'normal') return 'normal';
    if (normalized === 'pending_confirmation') return 'pending_confirmation';
    return 'other';
}

export function summarizeFindingSeverities(findings: FrontdoorFinding[] = []): FrontdoorFindingSeveritySummary {
    return findings.reduce<FrontdoorFindingSeveritySummary>((acc, finding) => {
        const key = normalizeFindingSeverity(finding.severity);
        acc[key] += 1;
        acc.total += 1;
        return acc;
    }, {
        blocking: 0,
        major: 0,
        normal: 0,
        pending_confirmation: 0,
        other: 0,
        total: 0,
    });
}

export function formatFindingSeveritySummary(summary: FrontdoorFindingSeveritySummary): string {
    const parts: string[] = [];
    if (summary.blocking > 0) parts.push(`blocking ${summary.blocking}`);
    if (summary.major > 0) parts.push(`major ${summary.major}`);
    if (summary.normal > 0) parts.push(`normal ${summary.normal}`);
    if (summary.pending_confirmation > 0) parts.push(`Pending confirmation ${summary.pending_confirmation}`);
    if (summary.other > 0) parts.push(`Other ${summary.other}`);
    return parts.length > 0 ? parts.join(' / ') : "No findings";
}

export function buildMetricComparisonItems(
    currentMetrics: Record<string, unknown> = {},
    comparableMetrics: Record<string, unknown> = {},
): FrontdoorMetricComparisonItem[] {
    const keys = Array.from(new Set([
        ...Object.keys(currentMetrics || {}),
        ...Object.keys(comparableMetrics || {}),
    ]));

    return keys.map((key) => {
        const currentValue = currentMetrics?.[key];
        const comparableValue = comparableMetrics?.[key];
        return {
            key,
            currentValue,
            comparableValue,
            changed: JSON.stringify(currentValue ?? null) !== JSON.stringify(comparableValue ?? null),
        };
    });
}

export function buildGateCheckDiff(
    currentChecks: FrontdoorGateCheckLike[] = [],
    comparableChecks: FrontdoorGateCheckLike[] = [],
): FrontdoorGateCheckDiffItem[] {
    const currentMap = new Map(currentChecks.map((item) => [item.rule_name, item]));
    const comparableMap = new Map(comparableChecks.map((item) => [item.rule_name, item]));
    const ruleNames = Array.from(new Set([
        ...currentMap.keys(),
        ...comparableMap.keys(),
    ]));

    return ruleNames.map((ruleName) => {
        const current = currentMap.get(ruleName);
        const comparable = comparableMap.get(ruleName);
        const currentStatus = String(current?.status || 'missing');
        const comparableStatus = String(comparable?.status || 'missing');
        const currentMessage = String(current?.message || '');
        const comparableMessage = String(comparable?.message || '');
        return {
            ruleName,
            currentStatus,
            comparableStatus,
            currentMessage,
            comparableMessage,
            changed: currentStatus !== comparableStatus || currentMessage !== comparableMessage,
        };
    });
}

function getTaskFindingCount(task: FrontdoorTask): number {
    const reportedCount = Number(task.evidence_summary?.finding_count ?? Number.NaN);
    if (Number.isFinite(reportedCount)) return reportedCount;
    return Array.isArray(task.findings) ? task.findings.length : 0;
}

export function buildTaskComparisonSummary(
    currentTask?: FrontdoorTask | null,
    comparableTask?: FrontdoorTask | null,
): FrontdoorTaskComparisonSummary | null {
    if (!currentTask || !comparableTask) return null;
    const currentSeveritySummary = summarizeFindingSeverities(currentTask.findings || []);
    const comparableSeveritySummary = summarizeFindingSeverities(comparableTask.findings || []);
    const currentFindingCount = getTaskFindingCount(currentTask);
    const comparableFindingCount = getTaskFindingCount(comparableTask);
    const currentHighRisk = currentSeveritySummary.blocking + currentSeveritySummary.major;
    const comparableHighRisk = comparableSeveritySummary.blocking + comparableSeveritySummary.major;
    const metricChanges = buildMetricComparisonItems(
        currentTask.gate_summary?.metrics || {},
        comparableTask.gate_summary?.metrics || {},
    );
    return {
        currentFindingCount,
        comparableFindingCount,
        findingDelta: currentFindingCount - comparableFindingCount,
        currentSeveritySummary,
        comparableSeveritySummary,
        highRiskDelta: currentHighRisk - comparableHighRisk,
        gateChanged: String(currentTask.gate_summary?.status || '') !== String(comparableTask.gate_summary?.status || ''),
        verificationChanged: String(currentTask.verification_state?.status || '') !== String(comparableTask.verification_state?.status || ''),
        decisionReasonChanged: String(currentTask.gate_summary?.decision_reason || '') !== String(comparableTask.gate_summary?.decision_reason || ''),
        metricChanges,
        changedMetricCount: metricChanges.filter((item) => item.changed).length,
    };
}

interface BuildFrontdoorDeepViewParams {
    currentTask?: FrontdoorTask | null;
    currentTaskId?: string;
    lineageTasks?: FrontdoorTask[];
    sameTaskKindTasks?: FrontdoorTask[];
    maxSameTaskKindReferences?: number;
    currentGateHistory?: FrontdoorGateHistoryLike | null;
    comparableGateHistory?: FrontdoorGateHistoryLike | null;
}

export function buildFrontdoorDeepView({
    currentTask,
    currentTaskId,
    lineageTasks = [],
    sameTaskKindTasks = [],
    maxSameTaskKindReferences = 4,
    currentGateHistory = null,
    comparableGateHistory = null,
}: BuildFrontdoorDeepViewParams): FrontdoorDeepView {
    const lineageContext = buildLineageContext(lineageTasks, currentTask?.task_id || currentTaskId || '');
    const resolvedCurrentTask = currentTask || lineageContext.currentTask || null;
    const comparableTask = lineageContext.comparableTask;
    const comparisonSummary = buildTaskComparisonSummary(resolvedCurrentTask, comparableTask);

    const sameTaskKindReferences = sameTaskKindTasks.filter((task) => {
        if (!resolvedCurrentTask) return true;
        if (task.task_id === resolvedCurrentTask.task_id) return false;
        if (resolvedCurrentTask.lineage_root_id && task.lineage_root_id === resolvedCurrentTask.lineage_root_id) return false;
        return true;
    }).slice(0, maxSameTaskKindReferences);

    const gateCheckDiff = buildGateCheckDiff(
        currentGateHistory?.verdict?.checks || [],
        comparableGateHistory?.verdict?.checks || [],
    );
    const changedGateChecks = gateCheckDiff.filter((item) => item.changed);

    return {
        currentTask: resolvedCurrentTask,
        lineageContext,
        comparableTask,
        comparisonSummary,
        sameTaskKindReferences,
        currentLineageGroupIds: new Set(lineageContext.sortedTasks.map((task) => task.execution_group_id || task.task_id)),
        sameTaskKindGroupIds: new Set(sameTaskKindReferences.map((task) => task.execution_group_id || task.task_id)),
        gateDeepRead: {
            currentHistory: currentGateHistory,
            comparableHistory: comparableGateHistory,
            gateCheckDiff,
            changedGateChecks,
        },
    };
}

export function resolveExecutionGroupTagSummary(
    groupId: string,
    deepView: Pick<FrontdoorDeepView, 'currentTask' | 'currentLineageGroupIds' | 'sameTaskKindGroupIds'>,
): FrontdoorExecutionGroupTagSummary {
    const normalizedGroupId = String(groupId || '').trim();
    const currentGroupId = String(deepView.currentTask?.execution_group_id || deepView.currentTask?.task_id || '').trim();
    const isCurrentTaskGroup = Boolean(normalizedGroupId && currentGroupId && normalizedGroupId === currentGroupId);
    const isSameLineageGroup = Boolean(
        normalizedGroupId
        && !isCurrentTaskGroup
        && deepView.currentLineageGroupIds.has(normalizedGroupId),
    );
    const isSameTaskKindReferenceGroup = Boolean(
        normalizedGroupId
        && !isCurrentTaskGroup
        && !isSameLineageGroup
        && deepView.sameTaskKindGroupIds.has(normalizedGroupId),
    );

    return {
        isCurrentTaskGroup,
        isSameLineageGroup,
        isSameTaskKindReferenceGroup,
    };
}
