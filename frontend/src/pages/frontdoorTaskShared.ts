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
        title: '通用编排',
        description: '一句话发起综合测试编排，适合快速验证一条真实任务目标。',
        targetLabel: '目标 URL（可选）',
        placeholder: '比如：检查登录、下单和支付主链路',
    },
    {
        kind: 'prototype',
        title: '原型测试',
        description: '输入 URL、文件或目录，统一生成证据、Findings 和门禁结论。',
        targetLabel: '原型来源',
        placeholder: '比如：D:\\prototype 或 https://example.com',
    },
    {
        kind: 'exploration',
        title: '探索测试',
        description: '围绕目标页面进行探索发现，适合找断链、异常和未知问题。',
        targetLabel: '目标 URL',
        placeholder: '比如：探索订单异常、发现关键风险',
    },
];

export function getTaskKindMeta(taskKind: FrontdoorTaskKind | string): FrontdoorTaskKindOption {
    return TASK_KIND_OPTIONS.find((item) => item.kind === taskKind) ?? TASK_KIND_OPTIONS[0];
}

export function statusMeta(status: string): { label: string; variant: 'success' | 'warning' | 'error' | 'info' | 'neutral' } {
    const normalized = String(status || '').toLowerCase();
    if (['completed', 'success'].includes(normalized)) return { label: '已完成', variant: 'success' };
    if (['failed', 'error'].includes(normalized)) return { label: '失败', variant: 'error' };
    if (['cancelled', 'stopped'].includes(normalized)) return { label: '已停止', variant: 'neutral' };
    if (['parsing', 'planning', 'dispatching', 'executing', 'reporting', 'pending'].includes(normalized)) {
        return { label: '执行中', variant: 'warning' };
    }
    return { label: '未知', variant: 'info' };
}

export function gateMeta(status: string): { label: string; variant: 'success' | 'warning' | 'error' | 'info' } {
    const normalized = String(status || '').toLowerCase();
    if (normalized === 'failed') return { label: '有明确问题', variant: 'error' };
    if (normalized === 'warning') return { label: '需人工确认', variant: 'warning' };
    if (normalized === 'passed') return { label: '已验证通过', variant: 'success' };
    return { label: '待判定', variant: 'info' };
}

export function isRunningStatus(status: string): boolean {
    return ['pending', 'parsing', 'planning', 'dispatching', 'executing', 'reporting'].includes(String(status || '').toLowerCase());
}

export function formatTimestamp(value?: string | null): string {
    if (!value) return '--';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString('zh-CN', { hour12: false });
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
            label: verificationState?.label || '已验证通过',
            variant: 'success',
            summary: verificationState?.summary || '当前任务在现有上下文下已验证通过。',
        };
    }
    if (normalized === 'context_unprovable') {
        return {
            label: verificationState?.label || '当前上下文无法证明',
            variant: 'warning',
            summary: verificationState?.summary || '当前仍存在静态原型或当前环境无法证明的点。',
        };
    }
    if (normalized === 'issues_found') {
        return {
            label: verificationState?.label || '有明确问题',
            variant: 'error',
            summary: verificationState?.summary || '当前任务已发现明确问题。',
        };
    }
    return {
        label: verificationState?.label || '待判定',
        variant: 'info',
        summary: verificationState?.summary || '当前任务还没有形成稳定结论。',
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
    if (summary.pending_confirmation > 0) parts.push(`待确认 ${summary.pending_confirmation}`);
    if (summary.other > 0) parts.push(`其他 ${summary.other}`);
    return parts.length > 0 ? parts.join(' / ') : '无 Findings';
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
