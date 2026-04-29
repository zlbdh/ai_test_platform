
import { TestStep } from '../types';
import { API_BASE_URL, API_ENDPOINTS } from '../config';

export interface SystemStatusResponse {
    status: string;
    logs: string[];
    task?: string;
    task_display?: string;
    task_text_state?: string;
    execution_mode?: string;
    interaction_policy?: string;
    step_budget?: number | null;
    signal?: string;
    is_running?: boolean;
}

export interface ExecutionDetailResponse {
    task_id: string;
    requirement: string;
    requirement_display?: string;
    status: string;
    log_count: number;
    error_count: number;
    duration_ms: number;
    target_url: string;
    mode: string;
    requirement_raw_present?: number;
    task_text_state?: string;
    logs: Record<string, unknown>[];
    created_at: string;
}

export interface PlanStep {
    action: string;
    target: string;
    value: string;
    description: string;
}

export interface HistoryRecord {
    task_id?: string;
    id?: string;
    requirement?: string;
    requirement_display?: string;
    goal?: string;
    status: string;
    requirement_raw_present?: number;
    task_text_state?: string;
    created_at?: string;
    timestamp?: string;
    [key: string]: unknown;
}

export interface HealingStats {
    [key: string]: unknown;
}

export interface MaintenanceSnapshot {
    status: string;
    reason: string;
    timestamp: string;
    duration_ms: number;
    skipped: boolean;
    sync: { performance: number; security: number };
    repair: { group_updates: number; record_updates: number; legacy_groups: number };
    report_history: { history_entries: number; updated_entries: number };
    risk?: {
        level: string;
        shadow_count: number;
        summary: string;
        current_db_path?: string;
        current_db_size_bytes?: number;
        current_db_updated_at?: string;
        shadow_paths?: string[];
    };
    notification?: {
        webhook_count: number;
        tested_enabled?: number;
        healthy_enabled?: number;
        untested_enabled?: number;
        ready: boolean;
        summary: string;
    };
    data_quality?: {
        suspect_history_count: number;
        raw_history_count?: number;
        archived_history_count?: number;
        visible_history_count?: number;
        archive_export_count?: number;
        last_archive_export_at?: string;
        last_archive_export_reason?: string;
        last_archive_export_path?: string;
        last_archive_export_format?: string;
        archive_export_fresh?: boolean;
        archive_retention_days?: number;
        archive_cleanup_needed?: boolean;
        archive_cleanup_candidate_count?: number;
        archive_run_cleanup_candidates?: number;
        archive_export_cleanup_candidates?: number;
        last_archive_cleanup_at?: string;
        last_archive_cleanup_reason?: string;
        last_archive_cleanup_dry_run?: boolean;
        last_archive_cleanup_deleted_runs?: number;
        last_archive_cleanup_deleted_exports?: number;
        clean: boolean;
        summary: string;
    };
    alert_sent?: boolean;
    risk_alert_sent?: boolean;
    warning_detected?: boolean;
    error?: string;
    requested_at?: string;
    skip_reason?: string;
}

export interface MaintenanceHistoryItem extends MaintenanceSnapshot {
    id: number;
}

export interface PlatformMaintenanceResponse {
    status: string;
    current: MaintenanceSnapshot;
    latest_activity?: MaintenanceSnapshot;
    history: {
        items: MaintenanceHistoryItem[];
        total: number;
        raw_total?: number;
        suspect_count?: number;
        filtered?: boolean;
        include_suspect?: boolean;
        archived_count?: number;
        include_archived?: boolean;
    };
}

export interface PlatformInfoResponse {
    name: string;
    version: string;
    operations?: {
        auto_maintenance?: boolean;
        maintenance_status?: string;
        last_maintenance_reason?: string;
        business_db_path?: string;
        business_db_exists?: boolean;
        business_db_size_bytes?: number;
        business_db_updated_at?: string;
        shadow_business_dbs?: string[];
        shadow_business_db_count?: number;
        business_db_risk_level?: string;
        notification_webhook_count?: number;
        notification_tested_webhook_count?: number;
        notification_healthy_webhook_count?: number;
        notification_untested_webhook_count?: number;
        notification_ready?: boolean;
        notification_summary?: string;
        commander_chatops_ready?: boolean;
        commander_chatops_platform_ready?: boolean;
        commander_chatops_webhook_ready?: boolean;
        commander_chatops_external_connected?: boolean;
        commander_chatops_external_connected_current?: boolean;
        commander_chatops_external_connected_history_observed?: boolean;
        commander_chatops_external_connection_stale?: boolean;
        commander_chatops_external_callback_ready?: boolean;
        commander_chatops_external_self_check_recent_success?: boolean;
        commander_chatops_direct_chat_ready?: boolean;
        commander_chatops_app_bot_configured?: boolean;
        commander_chatops_app_bot_id_masked?: string;
        commander_chatops_app_bot_updated_at?: string;
        commander_chatops_unified_robot_target?: boolean;
        commander_chatops_unified_robot_platform_ready?: boolean;
        commander_chatops_unified_robot_ready?: boolean;
        commander_chatops_delivery_strategy?: string;
        commander_chatops_delivery_strategy_summary?: string;
        commander_chatops_subscription_endpoint_verified?: boolean;
        commander_chatops_verification_token_configured?: boolean;
        commander_chatops_verification_token_masked?: string;
        commander_chatops_verification_token_updated_at?: string;
        commander_chatops_callback_url?: string;
        commander_chatops_callback_url_public?: boolean;
        commander_chatops_callback_provider?: {
            key?: string;
            label?: string;
            host?: string;
        };
        commander_chatops_callback_recommendation?: string;
        commander_chatops_callback_probe_attempted?: boolean;
        commander_chatops_callback_probe_success?: boolean;
        commander_chatops_callback_probe_issue?: string;
        commander_chatops_callback_probe_summary?: string;
        commander_chatops_callback_probe_status_code?: number | null;
        commander_chatops_callback_probe_content_type?: string;
        commander_chatops_callback_probe_probed_at?: string;
        commander_chatops_summary?: string;
        commander_chatops_recent_event_at?: string;
        commander_chatops_recent_success_at?: string;
        commander_chatops_latest_external_success_at?: string;
        commander_chatops_latest_external_self_check_at?: string;
        commander_chatops_recent_delivery_count?: number;
        maintenance_suspect_history_count?: number;
        maintenance_archived_history_count?: number;
        maintenance_archive_export_count?: number;
        maintenance_last_archive_export_at?: string;
        maintenance_last_archive_export_reason?: string;
        maintenance_last_archive_export_path?: string;
        maintenance_last_archive_export_format?: string;
        maintenance_archive_export_fresh?: boolean;
        maintenance_archive_retention_days?: number;
        maintenance_archive_cleanup_needed?: boolean;
        maintenance_archive_cleanup_candidate_count?: number;
        maintenance_archive_run_cleanup_candidates?: number;
        maintenance_archive_export_cleanup_candidates?: number;
        maintenance_last_archive_cleanup_at?: string;
        maintenance_last_archive_cleanup_reason?: string;
        maintenance_last_archive_cleanup_dry_run?: boolean;
        maintenance_last_archive_cleanup_deleted_runs?: number;
        maintenance_last_archive_cleanup_deleted_exports?: number;
        maintenance_history_clean?: boolean;
        maintenance_history_summary?: string;
        readiness_stage?: string;
        readiness_score?: number;
        readiness_summary?: string;
    };
}

export interface MaintenanceArchiveResult {
    archived_count: number;
    archived_ids: number[];
    reason: string;
    archived_at: string;
    remaining: number;
    data_quality: {
        suspect_history_count: number;
        raw_history_count: number;
        archived_history_count?: number;
        visible_history_count: number;
        clean: boolean;
        summary: string;
    };
}

export interface MaintenanceArchiveExportResult {
    reason: string;
    format: string;
    exported_at: string;
    file_path: string;
    count: number;
    bytes_written: number;
    data_quality: {
        suspect_history_count: number;
        raw_history_count: number;
        archived_history_count?: number;
        visible_history_count: number;
        archive_export_count?: number;
        last_archive_export_at?: string;
        last_archive_export_reason?: string;
        last_archive_export_path?: string;
        last_archive_export_format?: string;
        archive_export_fresh?: boolean;
        archive_retention_days?: number;
        archive_cleanup_needed?: boolean;
        archive_cleanup_candidate_count?: number;
        archive_run_cleanup_candidates?: number;
        archive_export_cleanup_candidates?: number;
        last_archive_cleanup_at?: string;
        last_archive_cleanup_reason?: string;
        last_archive_cleanup_dry_run?: boolean;
        last_archive_cleanup_deleted_runs?: number;
        last_archive_cleanup_deleted_exports?: number;
        clean: boolean;
        summary: string;
    };
}

export interface MaintenanceArchiveCleanupResult {
    reason: string;
    retention_days: number;
    dry_run: boolean;
    cutoff: string;
    candidate_runs: number;
    candidate_exports: number;
    deleted_runs: number;
    deleted_exports: number;
    deleted_export_files: string[];
    data_quality: {
        suspect_history_count: number;
        raw_history_count: number;
        archived_history_count?: number;
        visible_history_count: number;
        archive_export_count?: number;
        last_archive_export_at?: string;
        last_archive_export_reason?: string;
        last_archive_export_path?: string;
        last_archive_export_format?: string;
        archive_export_fresh?: boolean;
        archive_retention_days?: number;
        archive_cleanup_needed?: boolean;
        archive_cleanup_candidate_count?: number;
        archive_run_cleanup_candidates?: number;
        archive_export_cleanup_candidates?: number;
        last_archive_cleanup_at?: string;
        last_archive_cleanup_reason?: string;
        last_archive_cleanup_dry_run?: boolean;
        last_archive_cleanup_deleted_runs?: number;
        last_archive_cleanup_deleted_exports?: number;
        clean: boolean;
        summary: string;
    };
}

export interface ShadowDbQuarantineResult {
    reason: string;
    archive_dir: string;
    moved_count: number;
    moved: Array<{
        source_path: string;
        archived_path: string;
        size_bytes?: number;
    }>;
    skipped_count: number;
    skipped: Array<{
        path: string;
        reason: string;
    }>;
    observability: {
        path: string;
        shadow_paths: string[];
        shadow_count: number;
        risk_level: string;
        current_db?: {
            exists?: boolean;
            size_bytes?: number;
            updated_at?: string;
        };
    };
}

export interface ReadinessSection {
    key: string;
    name: string;
    score: number;
    status: string;
    summary: string;
}

export interface PlatformReadiness {
    stage: string;
    score: number;
    local_score: number;
    global_score: number;
    summary: string;
    computed_at: string;
    local: ReadinessSection[];
    global: ReadinessSection[];
    recommendations: string[];
}

export interface PlatformReadinessResponse {
    status: string;
    readiness: PlatformReadiness;
}

export interface PlatformRemediationItem {
    key: string;
    title: string;
    scope: string;
    priority: string;
    blocking: boolean;
    status: string;
    route?: string;
    summary: string;
    impact: string;
    next_step: string;
    evidence: Record<string, unknown>;
}

export interface PlatformRemediation {
    computed_at: string;
    status: string;
    summary: string;
    counts: {
        total: number;
        blocking: number;
        local: number;
        global: number;
        p0: number;
        p1: number;
    };
    items: PlatformRemediationItem[];
    risk: {
        shadow_count: number;
        notification_ready: boolean;
        readiness_stage: string;
    };
}

export interface PlatformRemediationResponse {
    status: string;
    remediation: PlatformRemediation;
}

// ============================================================================
// 统一请求工具 — 内置超时控制与错误格式化
// ============================================================================
const DEFAULT_TIMEOUT_MS = 30_000;

async function fetchWithTimeout(
    url: string,
    options: RequestInit = {},
    timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<Response> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const response = await fetch(url, { ...options, signal: controller.signal });
        if (!response.ok) {
            const errorText = await response.text().catch(() => response.statusText);
            throw new Error(`API 请求失败 [${response.status}]: ${errorText}`);
        }
        return response;
    } catch (error: unknown) {
        if (error instanceof DOMException && error.name === 'AbortError') {
            throw new Error(`请求超时 (${timeoutMs / 1000}s): ${url}`);
        }
        throw error;
    } finally {
        clearTimeout(timer);
    }
}

/**
 * 启动执行
 */
export const startExecution = async (
    task: string,
    useMultiAgent: boolean = true,
    enableVision: boolean = true,
    targetUrl: string = '',
    sessionId: string = 'default_session',
    browserMode: string = 'chromium',
    executionGroupId: string = '',
    executionMode: 'default' | 'probe' = 'default',
    interactionPolicy: 'default' | 'read_only' = 'default',
): Promise<{ task_id: string }> => {
    void enableVision;
    try {
        const response = await fetchWithTimeout(API_ENDPOINTS.start, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                requirement: task,
                mode: 'CLOUD',
                planner_mode: useMultiAgent ? 'smart' : 'quick',
                target_url: targetUrl,
                session_id: sessionId,
                browser_mode: browserMode,
                execution_group_id: executionGroupId || undefined,
                execution_mode: executionMode,
                interaction_policy: interactionPolicy,
            }),
        });
        return await response.json();
    } catch (e) {
        console.error("Start Execution Failed", e);
        throw e;
    }
};

/**
 * 获取单条执行记录详情（含完整日志）
 */
export const getExecutionDetail = async (taskId: string): Promise<ExecutionDetailResponse> => {
    const response = await fetchWithTimeout(`${API_ENDPOINTS.history.list}/${taskId}`);
    return await response.json();
};

/**
 * 停止执行
 */
export const stopExecution = async (sessionId: string = 'default_session'): Promise<{ status: string }> => {
    await fetchWithTimeout(API_ENDPOINTS.stop(sessionId), { method: 'POST' });
    return { status: 'stopped' };
};

export const pauseExecution = async (sessionId: string = 'default_session'): Promise<{ status: string }> => {
    await fetchWithTimeout(API_ENDPOINTS.control.pause(sessionId), { method: 'POST' });
    return { status: 'paused' };
};

export const resumeExecution = async (sessionId: string = 'default_session'): Promise<{ status: string }> => {
    await fetchWithTimeout(API_ENDPOINTS.control.resume(sessionId), { method: 'POST' });
    return { status: 'running' };
};

export const suspendExecution = async (sessionId: string = 'default_session', reason: string = 'User Intervention'): Promise<{ status: string }> => {
    await fetchWithTimeout(API_ENDPOINTS.control.suspend, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, reason })
    });
    return { status: 'paused' };
};

/**
 * 健康检查
 */
export const checkBackendHealth = async (): Promise<boolean> => {
    try {
        const response = await fetch(`${API_BASE_URL}/`);
        return response.ok;
    } catch {
        return false;
    }
};

// --- Deprecated / Mapped for Compatibility ---

export const generateTestPlan = async (requirement: string, url?: string): Promise<TestStep[]> => {
    const result = await generateTestPlanWithCoverage(requirement, url);
    return result.steps;
};

export interface CoverageSummary {
    total_scenarios: number;
    by_priority: { P0: number; P1: number; P2: number };
    dimensions_covered: string[];
}

export interface PlanResult {
    steps: TestStep[];
    coverage_summary: CoverageSummary | null;
}

export const generateTestPlanWithCoverage = async (
    requirement: string,
    url?: string,
    executionMode: 'default' | 'probe' = 'default',
    interactionPolicy: 'default' | 'read_only' = 'default',
): Promise<PlanResult> => {
    try {
        const response = await fetchWithTimeout(`${API_BASE_URL}/api/plan/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                requirement,
                target_url: url,
                enable_rag: true,
                execution_mode: executionMode,
                interaction_policy: interactionPolicy,
            })
        }, 360_000); // LLM 计划生成可能较慢（长上下文规划场景），放宽到 360s

        const data = await response.json();

        if (data.status === 'error') {
            throw new Error(data.message || 'Plan generation failed');
        }

        // 将后端格式转换为前端 TestStep 格式
        const steps = (data.steps || []).map((step: PlanStep, index: number) => ({
            id: `step-${index + 1}`,
            agent: 'PLANNER' as const,
            action: step.action || '',
            target: step.target || '',
            value: step.value || '',
            description: step.description || `Step ${index + 1}`,
            priority: (step as unknown as Record<string, unknown>).priority || 'P1',
            scenario: (step as unknown as Record<string, unknown>).scenario || '',
            status: 'pending' as const,
            logs: []
        }));

        return {
            steps,
            coverage_summary: data.coverage_summary || null
        };
    } catch (error) {
        console.error('Plan generation error:', error);
        throw error;
    }
};


export const getSystemStatus = async (): Promise<SystemStatusResponse> => {
    try {
        const response = await fetch(API_ENDPOINTS.status('default_session'));
        if (!response.ok) return { status: 'UNKNOWN', logs: [] };
        const data = await response.json();
        return {
            status: data.status || 'UNKNOWN',
            logs: data.logs || [],
            task: data.task,
            task_display: data.task_display,
            task_text_state: data.task_text_state,
            execution_mode: data.execution_mode,
            interaction_policy: data.interaction_policy,
            step_budget: data.step_budget,
            signal: data.signal,
            is_running: data.is_running,
        };
    } catch {
        return { status: 'UNKNOWN', logs: [] };
    }
};

export const getExecutionHistory = async (limit: number = 100): Promise<HistoryRecord[]> => {
    void limit;
    try {
        const response = await fetch(API_ENDPOINTS.history.list);
        if (!response.ok) return [];
        const data = await response.json();
        // 兼容新旧格式
        return Array.isArray(data) ? data : (data.items || []);
    } catch {
        return [];
    }
};

export const getAgentStats = async (): Promise<HealingStats> => {
    try {
        const response = await fetch(`${API_BASE_URL}/api/ai/healing/stats`);
        if (!response.ok) return {};
        const data = await response.json();
        return data.stats || {};
    } catch {
        return {};
    }
};

export const getPlatformMaintenance = async (
    limit: number = 10,
    includeSuspect: boolean = false,
    includeArchived: boolean = false
): Promise<PlatformMaintenanceResponse> => {
    const response = await fetchWithTimeout(
        `${API_BASE_URL}/api/platform/maintenance?limit=${limit}&include_suspect=${includeSuspect}&include_archived=${includeArchived}`
    );
    return await response.json();
};

export const getPlatformInfo = async (): Promise<PlatformInfoResponse> => {
    const response = await fetchWithTimeout(`${API_BASE_URL}/api/platform/info`);
    return await response.json();
};

export const getPlatformReadiness = async (): Promise<PlatformReadinessResponse> => {
    const response = await fetchWithTimeout(`${API_BASE_URL}/api/platform/readiness`);
    return await response.json();
};

export const getPlatformRemediation = async (): Promise<PlatformRemediationResponse> => {
    const response = await fetchWithTimeout(`${API_BASE_URL}/api/platform/remediation`);
    return await response.json();
};

export const runPlatformMaintenance = async (
    force: boolean = true,
    reason: string = 'dashboard_manual'
): Promise<MaintenanceSnapshot> => {
    const response = await fetchWithTimeout(`${API_BASE_URL}/api/platform/maintenance/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force, reason }),
    });
    const data = await response.json();
    return data.result;
};

export const archivePlatformMaintenanceSuspects = async (
    reason: string = 'dashboard_archive_suspect',
    limit: number = 0
): Promise<MaintenanceArchiveResult> => {
    const response = await fetchWithTimeout(`${API_BASE_URL}/api/platform/maintenance/archive-suspect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason, limit }),
    });
    const data = await response.json();
    return data.result;
};

export const exportPlatformMaintenanceArchive = async (
    reason: string = 'dashboard_export_archive',
    format: string = 'json'
): Promise<MaintenanceArchiveExportResult> => {
    const response = await fetchWithTimeout(`${API_BASE_URL}/api/platform/maintenance/export-archive`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason, format }),
    });
    const data = await response.json();
    return data.result;
};

export const cleanupPlatformMaintenanceArchive = async (
    reason: string = 'dashboard_cleanup_archive',
    retentionDays: number = 30,
    dryRun: boolean = true
): Promise<MaintenanceArchiveCleanupResult> => {
    const response = await fetchWithTimeout(`${API_BASE_URL}/api/platform/maintenance/cleanup-archive`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason, retention_days: retentionDays, dry_run: dryRun }),
    });
    const data = await response.json();
    return data.result;
};

export const quarantinePlatformShadowDbs = async (
    reason: string = 'dashboard_shadow_db_quarantine'
): Promise<ShadowDbQuarantineResult> => {
    const response = await fetchWithTimeout(`${API_BASE_URL}/api/platform/shadow-db/quarantine`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason }),
    });
    const data = await response.json();
    return data.result;
};

// ============================================================================
// Dashboard 统计聚合 — 基于 history 数据在前端计算
// ============================================================================
export interface DashboardStats {
    todayExecutions: number;
    todaySuccessRate: number;
    avgDurationMs: number;
    todayDefects: number;
    trend7Days: { date: string; executions: number; successRate: number }[];
    typeDistribution: { name: string; value: number; fill: string }[];
}

const TYPE_COLORS: Record<string, string> = {
    smart: '#6366f1',
    quick: '#22c55e',
    CLOUD: '#3b82f6',
    LOCAL: '#f59e0b',
    other: '#94a3b8',
};

export const getDashboardStats = async (): Promise<DashboardStats> => {
    const records = await getExecutionHistory(200);
    const now = new Date();
    const todayStr = now.toISOString().slice(0, 10);

    // 今日记录
    const todayRecords = records.filter(r => {
        const d = r.created_at || r.timestamp || '';
        return d.slice(0, 10) === todayStr;
    });
    const todayExecutions = todayRecords.length;
    const todaySuccessCount = todayRecords.filter(r => r.status === 'completed' || r.status === 'success').length;
    const todaySuccessRate = todayExecutions > 0 ? Math.round((todaySuccessCount / todayExecutions) * 100) : 0;
    const todayDefects = todayRecords.filter(r => (r as Record<string, unknown>).error_count && ((r as Record<string, unknown>).error_count as number) > 0).reduce((s, r) => s + (((r as Record<string, unknown>).error_count as number) || 0), 0);

    // 平均耗时
    const durations = records.filter(r => (r as Record<string, unknown>).duration_ms && ((r as Record<string, unknown>).duration_ms as number) > 0).map(r => (r as Record<string, unknown>).duration_ms as number);
    const avgDurationMs = durations.length > 0 ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length) : 0;

    // 7 天趋势
    const trend7Days: DashboardStats['trend7Days'] = [];
    for (let i = 6; i >= 0; i--) {
        const d = new Date(now);
        d.setDate(d.getDate() - i);
        const ds = d.toISOString().slice(0, 10);
        const dayRecs = records.filter(r => (r.created_at || r.timestamp || '').slice(0, 10) === ds);
        const daySuccess = dayRecs.filter(r => r.status === 'completed' || r.status === 'success').length;
        trend7Days.push({
            date: `${d.getMonth() + 1}/${d.getDate()}`,
            executions: dayRecs.length,
            successRate: dayRecs.length > 0 ? Math.round((daySuccess / dayRecs.length) * 100) : 0,
        });
    }

    // 类型分布
    const typeCounts: Record<string, number> = {};
    for (const r of records) {
        const mode = ((r as Record<string, unknown>).mode as string) || 'other';
        typeCounts[mode] = (typeCounts[mode] || 0) + 1;
    }
    const typeDistribution = Object.entries(typeCounts).map(([name, value]) => ({
        name,
        value,
        fill: TYPE_COLORS[name] || TYPE_COLORS.other,
    }));

    return { todayExecutions, todaySuccessRate, avgDurationMs, todayDefects, trend7Days, typeDistribution };
};
