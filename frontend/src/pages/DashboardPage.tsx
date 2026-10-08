import { failureReasonLabel } from '../utils/failureReasonLabel';
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    getDashboardStats,
    archivePlatformMaintenanceSuspects,
    cleanupPlatformMaintenanceArchive,
    exportPlatformMaintenanceArchive,
    getPlatformInfo,
    getPlatformMaintenance,
    getPlatformReadiness,
    getPlatformRemediation,
    quarantinePlatformShadowDbs,
    runPlatformMaintenance,
    DashboardStats,
    PlatformInfoResponse,
    PlatformMaintenanceResponse,
    PlatformReadiness,
    PlatformRemediation,
} from '../services/backendService';
import { commanderHealth, type AgentHealth } from '../services/commanderService';
import {
    LayoutDashboard, Activity, CheckCircle2, Clock, Bug,
    TrendingUp, TrendingDown, Minus, ChevronRight, AlertTriangle,
    BarChart3, Users, Wrench, Play, Swords, Compass, ArrowRight,
    PieChart as PieChartLucide,
    RefreshCw,
    Server,
} from '../components/icons';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
    ResponsiveContainer, PieChart, Pie, Cell, Legend,
    BarChart, Bar,
} from 'recharts';
import { API_BASE_URL } from '../config';
import { useAsync, usePolling } from '../hooks';

// Statistics cards
interface StatCardProps {
    label: string;
    value: string | number;
    sub?: string;
    icon: React.ReactNode;
    gradient: string;
    trend?: number;
}

const StatCard: React.FC<StatCardProps> = ({ label, value, sub, icon, gradient, trend }) => {
    const iconBg = gradient.includes('indigo') ? 'bg-gradient-to-br from-indigo-100 to-indigo-50 text-indigo-600 dark:from-indigo-500/20 dark:to-indigo-500/10 dark:text-indigo-400'
        : gradient.includes('emerald') ? 'bg-gradient-to-br from-emerald-100 to-emerald-50 text-emerald-600 dark:from-emerald-500/20 dark:to-emerald-500/10 dark:text-emerald-400'
            : gradient.includes('amber') || gradient.includes('orange') ? 'bg-gradient-to-br from-amber-100 to-amber-50 text-amber-600 dark:from-amber-500/20 dark:to-amber-500/10 dark:text-amber-400'
                : gradient.includes('rose') || gradient.includes('red') ? 'bg-gradient-to-br from-rose-100 to-rose-50 text-rose-600 dark:from-rose-500/20 dark:to-rose-500/10 dark:text-rose-400'
                    : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-400';

    return (
        <div className="card-hover-lift group rounded-2xl border border-slate-200/60 bg-white/80 backdrop-blur-sm p-5 dark:border-slate-700/60 dark:bg-slate-800/60">
            <div className="flex items-center justify-between">
                <div className={`rounded-xl p-2.5 ${iconBg} shadow-sm transition-transform duration-200 group-hover:scale-110`}>{icon}</div>
                {trend !== undefined && (
                    <span className={`flex items-center gap-0.5 text-[11px] font-semibold rounded-full px-2 py-0.5 ${trend > 0 ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400'
                        : trend < 0 ? 'bg-rose-50 text-rose-600 dark:bg-rose-500/15 dark:text-rose-400'
                            : 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400'
                        }`}>
                        {trend > 0 ? <TrendingUp className="w-3 h-3" /> : trend < 0 ? <TrendingDown className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
                        {Math.abs(trend)}%
                    </span>
                )}
            </div>
            <div className="mt-4">
                <p className="text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">{value}</p>
                <p className="mt-1 text-sm font-medium text-slate-500 dark:text-slate-400">{label}</p>
                {sub && <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">{sub}</p>}
            </div>
        </div>
    );
};

// Empty state
const EmptyChart: React.FC<{ message: string }> = ({ message }) => (
    <div className="flex h-52 items-center justify-center text-sm text-slate-400 dark:text-slate-500">
        {message}
    </div>
);

// Custom tooltip
interface TooltipPayload {
    name: string;
    value: number;
    color: string;
}
interface ChartTooltipProps {
    active?: boolean;
    payload?: TooltipPayload[];
    label?: string;
}
const ChartTooltip: React.FC<ChartTooltipProps> = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
        <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-xl dark:border-slate-700 dark:bg-slate-800">
            <p className="mb-1 text-xs font-semibold text-slate-500 dark:text-slate-400">{label}</p>
            {payload.map((p, i) => (
                <p key={i} className="text-sm" style={{ color: p.color }}>
                    {p.name}: <span className="font-bold">{p.value}{p.name === "Success rate" ? '%' : ''}</span>
                </p>
            ))}
        </div>
    );
};

// Detailed analysis panel
const REASON_COLORS: Record<string, string> = {
    "Timeout": '#f59e0b', "Element location": '#ef4444', "Assertion failure": '#8b5cf6',
    "Network error": '#3b82f6', "Permissions/authentication": '#ec4899', "Other": '#94a3b8',
};

interface FailureItem { name: string; failCount: number; lastFailure: string }
interface FlakyItem { name: string; total: number; passed: number; failed: number; passRate: number; severity: string }
interface ReasonItem { reason: string; count: number; percentage: number }

const AnalyticsPanel: React.FC = () => {
    const [failures, setFailures] = useState<FailureItem[]>([]);
    const [flakyTests, setFlakyTests] = useState<FlakyItem[]>([]);
    const [reasons, setReasons] = useState<ReasonItem[]>([]);
    const [loaded, setLoaded] = useState(false);

    useEffect(() => {
        const load = async () => {
            try {
                const [failResp, flakyResp, reasonResp] = await Promise.all([
                    fetch(`${API_BASE_URL}/api/analytics/failures`).then(r => r.json()).catch(() => ({ top: [] })),
                    fetch(`${API_BASE_URL}/api/analytics/flaky`).then(r => r.json()).catch(() => ({ tests: [] })),
                    fetch(`${API_BASE_URL}/api/analytics/failure-reasons`).then(r => r.json()).catch(() => ({ reasons: [] })),
                ]);
                setFailures(failResp.top || []);
                setFlakyTests(flakyResp.tests || []);
                setReasons(reasonResp.reasons || []);
            } catch { /* ignore */ }
            setLoaded(true);
        };
        load();
    }, []);

    if (!loaded) return (
        <div className="rounded-2xl card-hover-lift border border-slate-200/60 bg-white/80 backdrop-blur-sm p-5 dark:border-slate-700/60 dark:bg-slate-800/60 animate-pulse h-40" />
    );

    const hasData = failures.length > 0 || flakyTests.length > 0 || reasons.length > 0;
    if (!hasData) return null;

    return (
        <div className="space-y-4">
            <h3 className="text-lg font-bold text-slate-800 dark:text-white flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-indigo-500" />
                Detailed analysis
            </h3>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Top N failure heatmap*/}
                {failures.length > 0 && (
                    <div className="rounded-2xl card-hover-lift border border-slate-200/60 bg-white/80 backdrop-blur-sm p-5 dark:border-slate-700/60 dark:bg-slate-800/60">
                        <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3 flex items-center gap-2">
                            <Bug className="w-4 h-4 text-red-500" />
                            Failure heatmap: top {failures.length}
                        </h4>
                        <ResponsiveContainer width="100%" height={Math.max(120, failures.length * 36)}>
                            <BarChart data={failures} layout="vertical" margin={{ left: 0, right: 20 }}>
                                <XAxis type="number" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                                <YAxis
                                    type="category" dataKey="name" width={160}
                                    tick={{ fontSize: 11 }} stroke="#94a3b8"
                                    tickFormatter={(v: string) => v.length > 20 ? v.slice(0, 20) + '…' : v}
                                />
                                <Tooltip />
                                <Bar dataKey="failCount" name={"Failure count"} fill="#ef4444" radius={[0, 6, 6, 0]} barSize={20} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                )}

                {/* Failure cause distribution*/}
                {reasons.length > 0 && (
                    <div className="rounded-2xl card-hover-lift border border-slate-200/60 bg-white/80 backdrop-blur-sm p-5 dark:border-slate-700/60 dark:bg-slate-800/60">
                        <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3 flex items-center gap-2">
                            <AlertTriangle className="w-4 h-4 text-amber-500" />
                            Failure causes
                        </h4>
                        <div className="space-y-3">
                            {reasons.map((r) => (
                                <div key={r.reason}>
                                    <div className="flex justify-between text-xs mb-1">
                                        <span className="text-slate-600 dark:text-slate-400 font-medium">{failureReasonLabel(r.reason)}</span>
                                        <span className="text-slate-500">{r.count} occurrences ( {r.percentage}%)</span>
                                    </div>
                                    <div className="h-2.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                                        <div
                                            className="h-full rounded-full transition-all duration-500"
                                            style={{
                                                width: `${r.percentage}%`,
                                                backgroundColor: REASON_COLORS[failureReasonLabel(r.reason)] || '#94a3b8',
                                            }}
                                        />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {/* Flaky test detection*/}
            {flakyTests.length > 0 && (
                <div className="rounded-2xl border border-amber-200 bg-amber-50/50 p-5 shadow-sm dark:border-amber-500/30 dark:bg-amber-500/5">
                    <h4 className="text-sm font-semibold text-amber-700 dark:text-amber-400 mb-3 flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4" />
                        Flaky test detection ( {flakyTests.length})
                        <span className="ml-auto text-xs font-normal text-amber-600/60 dark:text-amber-400/60">
                            Tests with a pass rate between 20% and 80% are considered flaky
                        </span>
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        {flakyTests.map((t, i) => (
                            <div key={i} className="bg-white dark:bg-slate-800 rounded-xl border border-amber-200/60 dark:border-amber-500/20 p-3">
                                <div className="flex items-start gap-2 mb-2">
                                    <span className={`mt-0.5 shrink-0 px-1.5 py-0.5 text-[10px] rounded font-bold ${t.severity === 'high'
                                        ? 'bg-red-100 text-red-600 dark:bg-red-500/20 dark:text-red-400'
                                        : 'bg-amber-100 text-amber-600 dark:bg-amber-500/20 dark:text-amber-400'
                                        }`}>
                                        {t.severity === 'high' ? "High" : "Medium"}
                                    </span>
                                    <span className="text-xs text-slate-700 dark:text-slate-300 font-medium truncate" title={t.name}>
                                        {t.name}
                                    </span>
                                </div>
                                <div className="flex items-center gap-3 text-[11px] text-slate-500">
                                    <span>Total: {t.total} occurrences</span>
                                    <span className="text-emerald-600">✓{t.passed}</span>
                                    <span className="text-red-500">✗{t.failed}</span>
                                    <span className="ml-auto font-bold text-amber-600">{t.passRate}%</span>
                                </div>
                                <div className="mt-1.5 h-1.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden flex">
                                    <div className="h-full bg-emerald-500" style={{ width: `${t.passRate}%` }} />
                                    <div className="h-full bg-red-500" style={{ width: `${100 - t.passRate}%` }} />
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

// ============================================================================
// Dashboard Page
// ============================================================================
const DashboardPage: React.FC = () => {
    const navigate = useNavigate();
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [maintenance, setMaintenance] = useState<PlatformMaintenanceResponse | null>(null);
    const [platformInfo, setPlatformInfo] = useState<PlatformInfoResponse | null>(null);
    const [platformReadiness, setPlatformReadiness] = useState<PlatformReadiness | null>(null);
    const [platformRemediation, setPlatformRemediation] = useState<PlatformRemediation | null>(null);
    const [maintenanceRunning, setMaintenanceRunning] = useState(false);
    const [archiveRunning, setArchiveRunning] = useState(false);
    const [archiveExportRunning, setArchiveExportRunning] = useState(false);
    const [archiveCleanupRunning, setArchiveCleanupRunning] = useState(false);
    const [shadowQuarantineRunning, setShadowQuarantineRunning] = useState(false);
    const [archiveSummary, setArchiveSummary] = useState('');
    const [archiveExportSummary, setArchiveExportSummary] = useState('');
    const [archiveCleanupSummary, setArchiveCleanupSummary] = useState('');
    const [shadowDbSummary, setShadowDbSummary] = useState('');
    const { loading, run } = useAsync({ initialLoading: true });
    const [legionHealth, setLegionHealth] = useState<AgentHealth[]>([]);
    const [skillCount, setSkillCount] = useState(0);

    const load = useCallback(() => run(async () => {
        const [data, health, skillsResp, maintenanceResp, platformInfoResp, readinessResp, remediationResp] = await Promise.all([
            getDashboardStats(),
            commanderHealth().catch(() => ({ agents: [] })),
            fetch(`${API_BASE_URL}/api/commander/skills`).then(r => r.json()).catch(() => ({ total: 0 })),
            getPlatformMaintenance(5).catch(() => null),
            getPlatformInfo().catch(() => null),
            getPlatformReadiness().catch(() => null),
            getPlatformRemediation().catch(() => null),
        ]);
        setStats(data);
        setLegionHealth(health.agents);
        setSkillCount(skillsResp.total || 0);
        setMaintenance(maintenanceResp);
        setPlatformInfo(platformInfoResp);
        setPlatformReadiness(readinessResp?.readiness || null);
        setPlatformRemediation(remediationResp?.remediation || null);
    }), [run]);

    // Initial load
    useEffect(() => { load(); }, [load]);

    // Refresh automatically every 30 seconds.
    const { start } = usePolling(async () => { await load(); }, { interval: 30_000, immediate: false });
    useEffect(() => { start(); }, [start]);

    const formatDuration = (ms: number) => {
        if (ms < 1000) return `${ms}ms`;
        if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
        return `${(ms / 60_000).toFixed(1)}m`;
    };

    const formatTimestamp = (value?: string) => {
        if (!value) return "Not run";
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return `${date.getMonth() + 1}/${date.getDate()} ${date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false,
        })}`;
    };

    const formatBytes = (value?: number) => {
        const bytes = Number(value || 0);
        if (bytes <= 0) return '0 B';
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
    };

    const triggerMaintenance = async () => {
        setMaintenanceRunning(true);
        try {
            const result = await runPlatformMaintenance(true, 'dashboard_manual');
            setMaintenance(prev => ({
                status: 'success',
                current: result,
                latest_activity: result,
                history: {
                    total: (prev?.history.total || 0) + (result.skipped ? 0 : 1),
                    items: result.skipped
                        ? (prev?.history.items || [])
                        : [{ id: Date.now(), ...result }, ...(prev?.history.items || [])].slice(0, 5),
                },
            }));
            await load();
        } finally {
            setMaintenanceRunning(false);
        }
    };

    const triggerArchiveSuspects = async () => {
        setArchiveRunning(true);
        setArchiveSummary('');
        try {
            const result = await archivePlatformMaintenanceSuspects('dashboard_archive_suspect');
            setArchiveSummary(
                result.archived_count > 0
                    ? `Archived ${result.archived_count} suspicious maintenance records; ${result.remaining} remain pending`
                    : "No suspicious maintenance records are available to archive"
            );
            await load();
        } finally {
            setArchiveRunning(false);
        }
    };

    const triggerArchiveExport = async () => {
        setArchiveExportRunning(true);
        setArchiveExportSummary('');
        try {
            const result = await exportPlatformMaintenanceArchive('dashboard_export_archive', 'json');
            setArchiveExportSummary(
                result.count > 0
                    ? `Exported ${result.count} archived records to ${result.file_path}`
                    : `Created empty archive file ${result.file_path}`
            );
            await load();
        } finally {
            setArchiveExportRunning(false);
        }
    };

    const triggerArchiveCleanup = async (dryRun: boolean) => {
        setArchiveCleanupRunning(true);
        setArchiveCleanupSummary('');
        try {
            const result = await cleanupPlatformMaintenanceArchive(
                dryRun ? 'dashboard_cleanup_archive_dry_run' : 'dashboard_cleanup_archive',
                maintenanceArchiveRetentionDays,
                dryRun
            );
            setArchiveCleanupSummary(
                dryRun
                    ? `Retention check completed: archive records to clean up ${result.candidate_runs}; export files to clean up ${result.candidate_exports} files`
                    : `Archive cleanup completed: deleted archive records ${result.deleted_runs}; deleted export files ${result.deleted_exports} files`
            );
            await load();
        } finally {
            setArchiveCleanupRunning(false);
        }
    };

    const triggerShadowDbQuarantine = async () => {
        setShadowQuarantineRunning(true);
        setShadowDbSummary('');
        try {
            const result = await quarantinePlatformShadowDbs('dashboard_shadow_db_quarantine');
            setShadowDbSummary(
                result.moved_count > 0
                    ? `Isolated ${result.moved_count} shadow business databases; current risk level ${result.observability.risk_level}`
                    : `No new shadow business databases isolated; skipped ${result.skipped_count} files`
            );
            await load();
        } finally {
            setShadowQuarantineRunning(false);
        }
    };

    const onlineCount = legionHealth.filter(a => a.healthy).length;
    const squadCount = legionHealth.filter(a => a.type === 'squad').length;
    const maintenanceCurrent = maintenance?.current;
    const latestActivity = maintenance?.latest_activity;
    const maintenanceRisk = maintenanceCurrent?.risk;
    const businessDbPath = platformInfo?.operations?.business_db_path || "Unrecognized";
    const shadowBusinessDbs = platformInfo?.operations?.shadow_business_dbs || [];
    const shadowBusinessDbCount = platformInfo?.operations?.shadow_business_db_count || shadowBusinessDbs.length;
    const businessDbUpdatedAt = platformInfo?.operations?.business_db_updated_at || '';
    const businessDbSizeBytes = platformInfo?.operations?.business_db_size_bytes || 0;
    const businessDbRiskLevel = platformInfo?.operations?.business_db_risk_level || 'normal';
    const notificationWebhookCount = platformInfo?.operations?.notification_webhook_count ?? maintenanceCurrent?.notification?.webhook_count ?? 0;
    const notificationTestedCount = platformInfo?.operations?.notification_tested_webhook_count ?? maintenanceCurrent?.notification?.tested_enabled ?? 0;
    const notificationHealthyCount = platformInfo?.operations?.notification_healthy_webhook_count ?? maintenanceCurrent?.notification?.healthy_enabled ?? 0;
    const notificationUntestedCount = platformInfo?.operations?.notification_untested_webhook_count ?? maintenanceCurrent?.notification?.untested_enabled ?? Math.max(notificationWebhookCount - notificationTestedCount, 0);
    const notificationReady = platformInfo?.operations?.notification_ready ?? maintenanceCurrent?.notification?.ready ?? false;
    const notificationSummary = platformInfo?.operations?.notification_summary || maintenanceCurrent?.notification?.summary || "No enabled production alert webhook is configured";
    const notificationBadgeText = notificationReady
        ? `Healthy ${notificationHealthyCount}/${notificationWebhookCount}`
        : notificationWebhookCount === 0
            ? "Not configured"
            : notificationTestedCount === 0
                ? `Pending verification ${notificationUntestedCount}`
                : `Healthy ${notificationHealthyCount}/${notificationWebhookCount}`;
    const chatopsReady = platformInfo?.operations?.commander_chatops_ready ?? false;
    const chatopsPlatformReady = platformInfo?.operations?.commander_chatops_platform_ready ?? false;
    const chatopsExternalConnected = platformInfo?.operations?.commander_chatops_external_connected ?? false;
    const chatopsExternalConnectedCurrent = platformInfo?.operations?.commander_chatops_external_connected_current ?? chatopsExternalConnected;
    const chatopsExternalHistoryObserved = platformInfo?.operations?.commander_chatops_external_connected_history_observed ?? false;
    const chatopsExternalConnectionStale = platformInfo?.operations?.commander_chatops_external_connection_stale ?? (chatopsExternalHistoryObserved && !chatopsExternalConnectedCurrent);
    const chatopsExternalCallbackReady = platformInfo?.operations?.commander_chatops_external_callback_ready ?? false;
    const chatopsExternalSelfCheckRecentSuccess = platformInfo?.operations?.commander_chatops_external_self_check_recent_success ?? false;
    const chatopsDirectChatReady = platformInfo?.operations?.commander_chatops_direct_chat_ready ?? chatopsReady;
    const chatopsAppBotConfigured = platformInfo?.operations?.commander_chatops_app_bot_configured ?? false;
    const chatopsAppBotIdMasked = platformInfo?.operations?.commander_chatops_app_bot_id_masked || '';
    const chatopsUnifiedRobotTarget = platformInfo?.operations?.commander_chatops_unified_robot_target ?? chatopsAppBotConfigured;
    const chatopsUnifiedRobotPlatformReady = platformInfo?.operations?.commander_chatops_unified_robot_platform_ready ?? (chatopsAppBotConfigured && chatopsExternalCallbackReady);
    const chatopsUnifiedRobotReady = platformInfo?.operations?.commander_chatops_unified_robot_ready ?? chatopsDirectChatReady;
    const chatopsDeliveryStrategy = platformInfo?.operations?.commander_chatops_delivery_strategy || (chatopsAppBotConfigured ? 'single_robot_with_webhook_fallback' : 'webhook_only');
    const chatopsDeliveryStrategySummary = platformInfo?.operations?.commander_chatops_delivery_strategy_summary || (
        chatopsAppBotConfigured
            ? "Use the same project-specific notification app bot for commands and replies. Keep webhooks as a notification fallback."
            : "Notifications still rely mainly on a webhook bot; a unified bot experience is not yet in place."
    );
    const chatopsSubscriptionVerified = platformInfo?.operations?.commander_chatops_subscription_endpoint_verified ?? false;
    const chatopsTokenConfigured = platformInfo?.operations?.commander_chatops_verification_token_configured ?? false;
    const chatopsTokenMasked = platformInfo?.operations?.commander_chatops_verification_token_masked || '';
    const chatopsCallbackUrl = platformInfo?.operations?.commander_chatops_callback_url || '';
    const chatopsCallbackUrlPublic = platformInfo?.operations?.commander_chatops_callback_url_public ?? false;
    const chatopsCallbackProviderLabel = platformInfo?.operations?.commander_chatops_callback_provider?.label || (chatopsCallbackUrlPublic ? "Custom public URL" : "Local URL");
    const chatopsCallbackProviderHost = platformInfo?.operations?.commander_chatops_callback_provider?.host || '';
    const chatopsCallbackRecommendation = platformInfo?.operations?.commander_chatops_callback_recommendation || '';
    const chatopsCallbackProbeAttempted = platformInfo?.operations?.commander_chatops_callback_probe_attempted ?? false;
    const chatopsCallbackProbeSuccess = platformInfo?.operations?.commander_chatops_callback_probe_success ?? false;
    const chatopsCallbackProbeIssue = platformInfo?.operations?.commander_chatops_callback_probe_issue || '';
    const chatopsCallbackProbeSummary = platformInfo?.operations?.commander_chatops_callback_probe_summary || '';
    const chatopsCallbackProbeStatusCode = platformInfo?.operations?.commander_chatops_callback_probe_status_code;
    const chatopsCallbackProbeProbedAt = platformInfo?.operations?.commander_chatops_callback_probe_probed_at || '';
    const chatopsRecentEventAt = platformInfo?.operations?.commander_chatops_recent_event_at || '';
    const chatopsRecentSuccessAt = platformInfo?.operations?.commander_chatops_recent_success_at || '';
    const chatopsLatestExternalSuccessAt = platformInfo?.operations?.commander_chatops_latest_external_success_at || '';
    const chatopsLatestExternalSelfCheckAt = platformInfo?.operations?.commander_chatops_latest_external_self_check_at || '';
    const chatopsSummary = platformInfo?.operations?.commander_chatops_summary || "Two-way notification command status is temporarily unavailable";
    const chatopsLatestVerifiedAt = chatopsLatestExternalSuccessAt || chatopsLatestExternalSelfCheckAt || chatopsRecentSuccessAt || '';
    const chatopsLatestVerifiedLabel = chatopsLatestExternalSuccessAt
        ? "Latest actual inbound notification event"
        : chatopsLatestExternalSelfCheckAt
            ? "Latest public endpoint self-test"
            : chatopsRecentSuccessAt
                ? "Latest successful event"
                : "Not verified yet";
    const chatopsCurrentEntryLabel = chatopsDirectChatReady
        ? "Direct message AI Test Platform"
        : chatopsExternalConnectionStale
            ? "Previously connected; restoration pending"
            : chatopsPlatformReady
                ? "Continue integration testing in notification settings"
                : "Complete platform configuration first";
    const chatopsBadgeText = chatopsDirectChatReady
        ? "Connected"
        : !chatopsPlatformReady
            ? "Platform setup pending"
            : !chatopsCallbackUrlPublic
                ? "Local callback"
                : chatopsExternalConnectionStale
                    ? "External connection degraded"
                : chatopsCallbackProbeAttempted && !chatopsCallbackProbeSuccess
                    ? "Public endpoint probe failed"
                : !chatopsAppBotConfigured
                    ? "Project-specific bot missing"
                    : !chatopsExternalConnected
                        ? "Real group test pending"
                        : "Pending confirmation";
    const chatopsBadgeClass = chatopsDirectChatReady
        ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
        : chatopsPlatformReady && !(chatopsCallbackProbeAttempted && !chatopsCallbackProbeSuccess)
            ? 'bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
            : chatopsExternalConnectionStale || (chatopsCallbackProbeAttempted && !chatopsCallbackProbeSuccess)
                ? 'bg-rose-50 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300'
                : 'bg-violet-50 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300';
    const chatopsActionHint = !chatopsPlatformReady
        ? "Complete the public callback, token, and challenge self-check first"
        : !chatopsCallbackUrlPublic
            ? "Save the public callback URL in notification settings first"
            : chatopsExternalSelfCheckRecentSuccess && !chatopsDirectChatReady
                ? "The public self-test passed. Send a real message in the target group to finish integration testing."
            : chatopsExternalConnectionStale
                ? "The platform was connected previously, but the public endpoint has degraded. Fix the public URL or tunnel, then repeat the group test."
            : chatopsCallbackProbeAttempted && !chatopsCallbackProbeSuccess
                ? "Fix the current public callback URL or tunnel, then test integration in the notification platform console"
                : !chatopsAppBotConfigured
                    ? "Add a notification app bot dedicated to this project, then invite it to the target group"
                    : !chatopsExternalConnected
                        ? "Configure event subscriptions in the notification platform console and send a test message"
                        : "Two-way command integration testing completed";
    const maintenanceSuspectHistoryCount = platformInfo?.operations?.maintenance_suspect_history_count ?? maintenanceCurrent?.data_quality?.suspect_history_count ?? 0;
    const maintenanceArchivedHistoryCount = platformInfo?.operations?.maintenance_archived_history_count ?? maintenanceCurrent?.data_quality?.archived_history_count ?? 0;
    const maintenanceArchiveExportCount = platformInfo?.operations?.maintenance_archive_export_count ?? maintenanceCurrent?.data_quality?.archive_export_count ?? 0;
    const maintenanceArchiveExportFresh = platformInfo?.operations?.maintenance_archive_export_fresh ?? maintenanceCurrent?.data_quality?.archive_export_fresh ?? (maintenanceArchivedHistoryCount === 0);
    const maintenanceLastArchiveExportAt = platformInfo?.operations?.maintenance_last_archive_export_at || maintenanceCurrent?.data_quality?.last_archive_export_at || '';
    const maintenanceLastArchiveExportReason = platformInfo?.operations?.maintenance_last_archive_export_reason || maintenanceCurrent?.data_quality?.last_archive_export_reason || '';
    const maintenanceLastArchiveExportPath = platformInfo?.operations?.maintenance_last_archive_export_path || maintenanceCurrent?.data_quality?.last_archive_export_path || '';
    const maintenanceLastArchiveExportFormat = platformInfo?.operations?.maintenance_last_archive_export_format || maintenanceCurrent?.data_quality?.last_archive_export_format || '';
    const maintenanceArchiveRetentionDays = platformInfo?.operations?.maintenance_archive_retention_days ?? maintenanceCurrent?.data_quality?.archive_retention_days ?? 30;
    const maintenanceArchiveCleanupNeeded = platformInfo?.operations?.maintenance_archive_cleanup_needed ?? maintenanceCurrent?.data_quality?.archive_cleanup_needed ?? false;
    const maintenanceArchiveCleanupCandidateCount = platformInfo?.operations?.maintenance_archive_cleanup_candidate_count ?? maintenanceCurrent?.data_quality?.archive_cleanup_candidate_count ?? 0;
    const maintenanceArchiveRunCleanupCandidates = platformInfo?.operations?.maintenance_archive_run_cleanup_candidates ?? maintenanceCurrent?.data_quality?.archive_run_cleanup_candidates ?? 0;
    const maintenanceArchiveExportCleanupCandidates = platformInfo?.operations?.maintenance_archive_export_cleanup_candidates ?? maintenanceCurrent?.data_quality?.archive_export_cleanup_candidates ?? 0;
    const maintenanceLastArchiveCleanupAt = platformInfo?.operations?.maintenance_last_archive_cleanup_at || maintenanceCurrent?.data_quality?.last_archive_cleanup_at || '';
    const maintenanceLastArchiveCleanupReason = platformInfo?.operations?.maintenance_last_archive_cleanup_reason || maintenanceCurrent?.data_quality?.last_archive_cleanup_reason || '';
    const maintenanceLastArchiveCleanupDryRun = platformInfo?.operations?.maintenance_last_archive_cleanup_dry_run ?? maintenanceCurrent?.data_quality?.last_archive_cleanup_dry_run ?? true;
    const maintenanceLastArchiveCleanupDeletedRuns = platformInfo?.operations?.maintenance_last_archive_cleanup_deleted_runs ?? maintenanceCurrent?.data_quality?.last_archive_cleanup_deleted_runs ?? 0;
    const maintenanceLastArchiveCleanupDeletedExports = platformInfo?.operations?.maintenance_last_archive_cleanup_deleted_exports ?? maintenanceCurrent?.data_quality?.last_archive_cleanup_deleted_exports ?? 0;
    const maintenanceHistoryClean = platformInfo?.operations?.maintenance_history_clean ?? maintenanceCurrent?.data_quality?.clean ?? true;
    const maintenanceHistorySummary = platformInfo?.operations?.maintenance_history_summary || maintenanceCurrent?.data_quality?.summary || "Maintenance history is normal";
    const readiness = platformReadiness;
    const readinessStage = readiness?.stage || platformInfo?.operations?.readiness_stage || 'beta';
    const readinessScore = readiness?.score ?? platformInfo?.operations?.readiness_score ?? 0;
    const readinessSummary = readiness?.summary || platformInfo?.operations?.readiness_summary || "Readiness assessment is temporarily unavailable";
    const maintenanceBadgeClass = maintenanceCurrent?.status === 'failed'
        ? 'bg-rose-50 text-rose-600 dark:bg-rose-500/15 dark:text-rose-300'
        : maintenanceCurrent?.skipped
            ? 'bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-300'
            : 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300';
    const readinessBadgeClass = readinessStage === 'production-ready'
        ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
        : readinessStage === 'pre-production'
            ? 'bg-cyan-50 text-cyan-700 dark:bg-cyan-500/15 dark:text-cyan-300'
            : 'bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300';
    const readinessStatusClass = (status?: string) => status === 'good'
        ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
        : status === 'warning'
            ? 'bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
            : 'bg-rose-50 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300';
    const remediation = platformRemediation;
    const remediationPriorityClass = (priority?: string) => priority === 'P0'
        ? 'bg-rose-50 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300'
        : 'bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300';
    const remediationScopeClass = (scope?: string) => scope === 'local'
        ? 'bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300'
        : 'bg-indigo-50 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300';

    return (
        <div className="space-y-6">
            {/* Title*/}
            <div className="mb-2">
                <h2 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
                    <div className="p-2 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 text-white">
                        <LayoutDashboard className="w-5 h-5" />
                    </div>
                    Control center
                </h2>
                <p className="text-slate-500 mt-2 text-sm">Agent status and system monitoring</p>
            </div>

            {/* Statistics cards*/}
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 stagger-enter">
                <StatCard
                    label={"Runs today"}
                    value={loading ? '—' : stats?.todayExecutions ?? 0}
                    sub={"Test task execution count"}
                    icon={<Activity className="w-5 h-5" />}
                    gradient="bg-gradient-to-br from-indigo-500 to-indigo-700"
                />
                <StatCard
                    label={"Success rate"}
                    value={loading ? '—' : `${stats?.todaySuccessRate ?? 0}%`}
                    sub={"Today's pass rate"}
                    icon={<CheckCircle2 className="w-5 h-5" />}
                    gradient="bg-gradient-to-br from-emerald-500 to-emerald-700"
                />
                <StatCard
                    label={"Average duration"}
                    value={loading ? '—' : formatDuration(stats?.avgDurationMs ?? 0)}
                    sub={"Average across all tasks"}
                    icon={<Clock className="w-5 h-5" />}
                    gradient="bg-gradient-to-br from-amber-500 to-orange-600"
                />
                <StatCard
                    label={"Defects found"}
                    value={loading ? '—' : stats?.todayDefects ?? 0}
                    sub={"Today's error count"}
                    icon={<Bug className="w-5 h-5" />}
                    gradient="bg-gradient-to-br from-rose-500 to-rose-700"
                />
            </div>

            {/* Quick start*/}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {[
                    {
                        title: "Quick test",
                        desc: "Enter a URL and requirements; AI generates and executes a plan",
                        path: '/orchestrator',
                        icon: Play,
                        gradient: 'from-indigo-500 to-blue-500',
                        shadow: 'shadow-indigo-500/20',
                    },
                    {
                        title: "Comprehensive testing",
                        desc: "Start multiple test types with one instruction and Commander scheduling",
                        path: '/commander',
                        icon: Swords,
                        gradient: 'from-purple-500 to-pink-500',
                        shadow: 'shadow-purple-500/20',
                    },
                    {
                        title: "Exploration findings",
                        desc: "Let AI explore the website and discover anomalies and bugs",
                        path: '/exploratory',
                        icon: Compass,
                        gradient: 'from-teal-500 to-emerald-500',
                        shadow: 'shadow-teal-500/20',
                    },
                ].map((g) => (
                    <button
                        key={g.path}
                        onClick={() => navigate(g.path)}
                        className={`group relative overflow-hidden rounded-2xl bg-gradient-to-br ${g.gradient} p-5 text-left text-white shadow-lg ${g.shadow} hover:scale-[1.02] active:scale-[0.98] transition-all duration-200`}
                    >
                        <div className="absolute -right-6 -top-6 h-28 w-28 rounded-full bg-white/10 blur-2xl group-hover:bg-white/20 group-hover:scale-110 transition-all duration-500" />
                        <div className="relative z-10">
                            <g.icon className="w-7 h-7 mb-3 opacity-90" />
                            <h3 className="text-lg font-bold mb-1">{g.title}</h3>
                            <p className="text-sm text-white/80 leading-relaxed">{g.desc}</p>
                            <div className="mt-3 flex items-center gap-1 text-xs font-medium text-white/70 group-hover:text-white transition-colors">
                                Get started <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                            </div>
                        </div>
                    </button>
                ))}
            </div>

            {/* Charts row*/}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {/* Seven-day trend: two-thirds width*/}
                <div className="lg:col-span-2 card-hover-lift rounded-2xl border border-slate-200/60 bg-white/80 backdrop-blur-sm p-5 dark:border-slate-700/60 dark:bg-slate-800/60">
                    <h3 className="mb-4 text-base font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                        <BarChart3 className="w-4 h-4 text-indigo-500" />
                        Last 7 days
                    </h3>
                    {!stats?.trend7Days?.some(d => d.executions > 0) ? (
                        <EmptyChart message={"No execution data yet"} />
                    ) : (
                        <ResponsiveContainer width="100%" height={240}>
                            <AreaChart data={stats?.trend7Days} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                                <defs>
                                    <linearGradient id="colorExec" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                                    </linearGradient>
                                    <linearGradient id="colorRate" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                                <XAxis dataKey="date" tick={{ fontSize: 12 }} stroke="#94a3b8" />
                                <YAxis yAxisId="left" tick={{ fontSize: 12 }} stroke="#94a3b8" />
                                <YAxis yAxisId="right" orientation="right" domain={[0, 100]} tick={{ fontSize: 12 }} stroke="#94a3b8" />
                                <Tooltip content={<ChartTooltip />} />
                                <Area yAxisId="left" type="monotone" dataKey="executions" name={"Executions"} stroke="#6366f1" fill="url(#colorExec)" strokeWidth={2} />
                                <Area yAxisId="right" type="monotone" dataKey="successRate" name={"Success rate"} stroke="#22c55e" fill="url(#colorRate)" strokeWidth={2} />
                            </AreaChart>
                        </ResponsiveContainer>
                    )}
                </div>

                {/* Test type distribution: one-third width*/}
                <div className="rounded-2xl card-hover-lift border border-slate-200/60 bg-white/80 backdrop-blur-sm p-5 dark:border-slate-700/60 dark:bg-slate-800/60">
                    <h3 className="mb-4 text-base font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                        <PieChartLucide className="w-4 h-4 text-violet-500" />
                        Test type distribution
                    </h3>
                    {!stats?.typeDistribution?.length ? (
                        <EmptyChart message={"No data yet"} />
                    ) : (
                        <ResponsiveContainer width="100%" height={240}>
                            <PieChart>
                                <Pie
                                    data={stats.typeDistribution}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={50}
                                    outerRadius={80}
                                    paddingAngle={4}
                                    dataKey="value"
                                    label={false}
                                    labelLine={false}
                                >
                                    {stats.typeDistribution.map((entry, index) => (
                                        <Cell key={index} fill={entry.fill} />
                                    ))}
                                </Pie>
                                <Legend verticalAlign="bottom" height={36} />
                                <Tooltip />
                            </PieChart>
                        </ResponsiveContainer>
                    )}
                </div>
            </div>

            <div className="rounded-2xl border border-slate-200/70 bg-white/85 p-5 shadow-sm backdrop-blur-sm dark:border-slate-700/60 dark:bg-slate-800/65">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 flex items-center gap-2">
                            <BarChart3 className="w-4 h-4 text-indigo-500" />
                            Production readiness
                        </h3>
                        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                            Measure progress toward production readiness at both the module and overall architecture levels.
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="text-right">
                            <div className="text-xs text-slate-400">Overall readiness</div>
                            <div className="text-2xl font-bold text-slate-900 dark:text-white">{readinessScore}</div>
                        </div>
                        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${readinessBadgeClass}`}>
                            {readinessStage === 'production-ready' ? "Production-ready" : readinessStage === 'pre-production' ? "Near production" : 'Beta'}
                        </span>
                    </div>
                </div>
                <div className="mt-4 rounded-xl border border-slate-200/70 bg-slate-50/70 px-4 py-3 text-sm text-slate-600 dark:border-slate-700/60 dark:bg-slate-900/30 dark:text-slate-300">
                    {readinessSummary}
                </div>
                <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
                    <div className="rounded-2xl border border-slate-200/70 bg-slate-50/70 p-4 dark:border-slate-700/60 dark:bg-slate-900/30">
                        <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">Module view</div>
                        <div className="mt-3 space-y-3">
                            {(readiness?.local || []).map(section => (
                                <div key={section.key} className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 dark:border-slate-700/60 dark:bg-slate-800">
                                    <div className="flex items-center justify-between gap-3">
                                        <div className="text-sm font-medium text-slate-800 dark:text-slate-100">{section.name}</div>
                                        <div className="flex items-center gap-2">
                                            <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${readinessStatusClass(section.status)}`}>
                                                {section.status === 'good' ? "Stable" : section.status === 'warning' ? "Needs attention" : "Blocked"}
                                            </span>
                                            <span className="text-sm font-bold text-slate-800 dark:text-slate-100">{section.score}</span>
                                        </div>
                                    </div>
                                    <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">{section.summary}</div>
                                </div>
                            ))}
                        </div>
                    </div>
                    <div className="rounded-2xl border border-slate-200/70 bg-slate-50/70 p-4 dark:border-slate-700/60 dark:bg-slate-900/30">
                        <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">Architecture view</div>
                        <div className="mt-3 space-y-3">
                            {(readiness?.global || []).map(section => (
                                <div key={section.key} className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 dark:border-slate-700/60 dark:bg-slate-800">
                                    <div className="flex items-center justify-between gap-3">
                                        <div className="text-sm font-medium text-slate-800 dark:text-slate-100">{section.name}</div>
                                        <div className="flex items-center gap-2">
                                            <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${readinessStatusClass(section.status)}`}>
                                                {section.status === 'good' ? "Stable" : section.status === 'warning' ? "Needs attention" : "Blocked"}
                                            </span>
                                            <span className="text-sm font-bold text-slate-800 dark:text-slate-100">{section.score}</span>
                                        </div>
                                    </div>
                                    <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">{section.summary}</div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
                {!!readiness?.recommendations?.length && (
                    <div className="mt-4 rounded-2xl border border-indigo-200/70 bg-indigo-50/70 p-4 dark:border-indigo-500/30 dark:bg-indigo-500/10">
                        <div className="text-sm font-semibold text-indigo-700 dark:text-indigo-300">Suggested next steps</div>
                        <div className="mt-3 grid grid-cols-1 gap-2">
                            {readiness.recommendations.slice(0, 3).map((item, index) => (
                                <div key={`${index}-${item}`} className="rounded-xl bg-white/80 px-3 py-2 text-sm text-slate-700 dark:bg-slate-900/40 dark:text-slate-200">
                                    {item}
                                </div>
                            ))}
                        </div>
                    </div>
                )}
                {!!remediation?.items?.length && (
                    <div className="mt-4 rounded-2xl border border-rose-200/70 bg-rose-50/70 p-4 dark:border-rose-500/30 dark:bg-rose-500/10">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                            <div>
                                <div className="text-sm font-semibold text-rose-700 dark:text-rose-300">Key action items</div>
                                <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                                    Currently {remediation.counts.total} items, including {remediation.counts.blocking} blockers.
                                </div>
                            </div>
                            <div className="flex items-center gap-2 text-xs">
                                <span className="rounded-full bg-white/80 px-2 py-1 text-slate-700 dark:bg-slate-900/40 dark:text-slate-200">
                                    Module {remediation.counts.local}
                                </span>
                                <span className="rounded-full bg-white/80 px-2 py-1 text-slate-700 dark:bg-slate-900/40 dark:text-slate-200">
                                    Overall {remediation.counts.global}
                                </span>
                            </div>
                        </div>
                        <div className="mt-3 grid grid-cols-1 gap-3">
                            {remediation.items.slice(0, 4).map(item => (
                                <div key={item.key} className="rounded-xl border border-rose-200/70 bg-white/85 px-4 py-3 dark:border-rose-500/20 dark:bg-slate-900/40">
                                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                                        <div className="min-w-0">
                                            <div className="flex flex-wrap items-center gap-2">
                                                <div className="text-sm font-semibold text-slate-800 dark:text-slate-100">{item.title}</div>
                                                <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${remediationPriorityClass(item.priority)}`}>
                                                    {item.priority}
                                                </span>
                                                <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${remediationScopeClass(item.scope)}`}>
                                                    {item.scope === 'local' ? "Module" : "Overall"}
                                                </span>
                                            </div>
                                            <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">{item.summary}</div>
                                            <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">Impact: {item.impact}</div>
                                            <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">Next step: {item.next_step}</div>
                                            {Array.isArray(item.evidence?.shadow_paths) && item.evidence.shadow_paths.length > 0 && (
                                                <div className="mt-2 rounded-lg bg-slate-50 px-2 py-2 font-mono text-[11px] text-slate-600 dark:bg-slate-800/80 dark:text-slate-300">
                                                    {(item.evidence.shadow_paths as string[]).join('\n')}
                                                </div>
                                            )}
                                        </div>
                                        {!!item.route && item.route !== '/' && (
                                            <button
                                                type="button"
                                                onClick={() => navigate(item.route!)}
                                                className="inline-flex shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                                            >
                                                Resolve now
                                            </button>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            <div className="rounded-2xl border border-slate-200/70 bg-white/85 p-5 shadow-sm backdrop-blur-sm dark:border-slate-700/60 dark:bg-slate-800/65">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                        <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 flex items-center gap-2">
                            <Server className="w-4 h-4 text-cyan-500" />
                            Platform maintenance
                        </h3>
                        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                            Current status and recent runs for startup self-maintenance, history repair, and report repair
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        {shadowBusinessDbCount > 0 && (
                            <button
                                type="button"
                                onClick={() => { void triggerShadowDbQuarantine(); }}
                                disabled={shadowQuarantineRunning}
                                className="inline-flex items-center justify-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-medium text-rose-700 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300 dark:hover:bg-rose-500/20"
                            >
                                <Wrench className={`w-4 h-4 ${shadowQuarantineRunning ? 'animate-spin' : ''}`} />
                                {shadowQuarantineRunning ? "Isolating..." : "Isolate shadow databases"}
                            </button>
                        )}
                        {maintenanceArchivedHistoryCount > 0 && (
                            <button
                                type="button"
                                onClick={() => { void triggerArchiveCleanup(true); }}
                                disabled={archiveCleanupRunning}
                                className="inline-flex items-center justify-center gap-2 rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-2 text-sm font-medium text-indigo-700 transition hover:bg-indigo-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-indigo-500/30 dark:bg-indigo-500/10 dark:text-indigo-300 dark:hover:bg-indigo-500/20"
                            >
                                <Wrench className={`w-4 h-4 ${archiveCleanupRunning ? 'animate-spin' : ''}`} />
                                {archiveCleanupRunning ? "Checking..." : "Check archive retention"}
                            </button>
                        )}
                        {maintenanceArchiveCleanupNeeded && (
                            <button
                                type="button"
                                onClick={() => { void triggerArchiveCleanup(false); }}
                                disabled={archiveCleanupRunning}
                                className="inline-flex items-center justify-center gap-2 rounded-xl border border-violet-200 bg-violet-50 px-4 py-2 text-sm font-medium text-violet-700 transition hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-violet-500/30 dark:bg-violet-500/10 dark:text-violet-300 dark:hover:bg-violet-500/20"
                            >
                                <Wrench className={`w-4 h-4 ${archiveCleanupRunning ? 'animate-spin' : ''}`} />
                                {archiveCleanupRunning ? "Cleaning up..." : "Clean up expired archives"}
                            </button>
                        )}
                        {maintenanceArchivedHistoryCount > 0 && (
                            <button
                                type="button"
                                onClick={() => { void triggerArchiveExport(); }}
                                disabled={archiveExportRunning}
                                className="inline-flex items-center justify-center gap-2 rounded-xl border border-sky-200 bg-sky-50 px-4 py-2 text-sm font-medium text-sky-700 transition hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300 dark:hover:bg-sky-500/20"
                            >
                                <Wrench className={`w-4 h-4 ${archiveExportRunning ? 'animate-spin' : ''}`} />
                                {archiveExportRunning ? "Exporting..." : "Export archived records"}
                            </button>
                        )}
                        {maintenanceSuspectHistoryCount > 0 && (
                            <button
                                type="button"
                                onClick={() => { void triggerArchiveSuspects(); }}
                                disabled={archiveRunning}
                                className="inline-flex items-center justify-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-700 transition hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300 dark:hover:bg-amber-500/20"
                            >
                                <Wrench className={`w-4 h-4 ${archiveRunning ? 'animate-spin' : ''}`} />
                                {archiveRunning ? "Archiving..." : "Archive suspicious records"}
                            </button>
                        )}
                        <button
                            type="button"
                            onClick={() => { void triggerMaintenance(); }}
                            disabled={maintenanceRunning}
                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-cyan-200 bg-cyan-50 px-4 py-2 text-sm font-medium text-cyan-700 transition hover:bg-cyan-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-cyan-500/30 dark:bg-cyan-500/10 dark:text-cyan-300 dark:hover:bg-cyan-500/20"
                        >
                            <RefreshCw className={`w-4 h-4 ${maintenanceRunning ? 'animate-spin' : ''}`} />
                            {maintenanceRunning ? "Running..." : "Run maintenance now"}
                        </button>
                    </div>
                </div>

                <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[1.1fr_0.9fr]">
                    <div className="rounded-2xl border border-slate-200/70 bg-slate-50/70 p-4 dark:border-slate-700/60 dark:bg-slate-900/30">
                        <div className="flex items-center justify-between">
                            <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">Current maintenance status</div>
                            <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${maintenanceBadgeClass}`}>
                                {maintenanceCurrent?.status === 'failed'
                                    ? "Failed"
                                    : maintenanceCurrent?.skipped
                                        ? "Skipped due to throttling"
                                        : maintenanceCurrent?.status === 'success'
                                            ? "Normal"
                                            : "Not run"}
                            </span>
                        </div>
                        <div className="mt-4 grid grid-cols-2 gap-3">
                            <div className="rounded-xl bg-white px-3 py-3 text-sm dark:bg-slate-800">
                                <div className="text-xs text-slate-400">Latest run</div>
                                <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{formatTimestamp(maintenanceCurrent?.timestamp)}</div>
                            </div>
                            <div className="rounded-xl bg-white px-3 py-3 text-sm dark:bg-slate-800">
                                <div className="text-xs text-slate-400">Duration</div>
                                <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{formatDuration(maintenanceCurrent?.duration_ms || 0)}</div>
                            </div>
                            <div className="rounded-xl bg-white px-3 py-3 text-sm dark:bg-slate-800">
                                <div className="text-xs text-slate-400">Trigger reason</div>
                                <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{maintenanceCurrent?.reason || "Not run"}</div>
                            </div>
                            <div className="rounded-xl bg-white px-3 py-3 text-sm dark:bg-slate-800">
                                <div className="text-xs text-slate-400">Report history</div>
                                <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">
                                    {maintenanceCurrent?.report_history?.history_entries ?? 0} entries / Repaired {maintenanceCurrent?.report_history?.updated_entries ?? 0} tasks
                                </div>
                            </div>
                        </div>
                        <div className="mt-3 grid grid-cols-3 gap-3">
                            <div className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 text-sm dark:border-slate-700/60 dark:bg-slate-800">
                                <div className="text-xs text-slate-400">Performance import</div>
                                <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{maintenanceCurrent?.sync?.performance ?? 0}</div>
                            </div>
                            <div className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 text-sm dark:border-slate-700/60 dark:bg-slate-800">
                                <div className="text-xs text-slate-400">Security import</div>
                                <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{maintenanceCurrent?.sync?.security ?? 0}</div>
                            </div>
                            <div className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 text-sm dark:border-slate-700/60 dark:bg-slate-800">
                                <div className="text-xs text-slate-400">Text repair</div>
                                <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">
                                    {(maintenanceCurrent?.repair?.group_updates ?? 0) + (maintenanceCurrent?.repair?.record_updates ?? 0)}
                                </div>
                            </div>
                        </div>
                        <div className="mt-3 grid grid-cols-2 gap-3">
                            <div className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 text-sm dark:border-slate-700/60 dark:bg-slate-800">
                                <div className="text-xs text-slate-400">Recent activity</div>
                                <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{latestActivity?.reason || "Not recorded"}</div>
                                <div className="mt-1 text-xs text-slate-400">{formatTimestamp(latestActivity?.timestamp)}</div>
                            </div>
                            <div className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 text-sm dark:border-slate-700/60 dark:bg-slate-800">
                                <div className="text-xs text-slate-400">Business database risk</div>
                                <div className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${
                                    businessDbRiskLevel === 'warning'
                                        ? 'bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
                                        : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
                                }`}>
                                    {businessDbRiskLevel === 'warning' ? `Found ${shadowBusinessDbCount} shadow databases` : "Normal"}
                                </div>
                                <div className="mt-1 text-xs text-slate-400">{maintenanceRisk?.summary || "Recent disruptions do not overwrite the primary maintenance status"}</div>
                                {businessDbRiskLevel === 'warning' && (
                                    <div className="mt-1 text-xs text-slate-400">
                                        Warning status {maintenanceCurrent?.risk_alert_sent ? "Sent" : "Not sent"}
                                    </div>
                                )}
                            </div>
                        </div>
                        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
                            <div className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 text-sm dark:border-slate-700/60 dark:bg-slate-800">
                                <div className="text-xs text-slate-400">Alert delivery</div>
                                <div className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${
                                    notificationReady
                                        ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
                                        : 'bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
                                }`}>
                                    {notificationBadgeText}
                                </div>
                                <div className="mt-1 text-xs text-slate-400">{notificationSummary}</div>
                                {notificationWebhookCount > 0 && (
                                    <div className="mt-1 text-xs text-slate-400">
                                        Enabled {notificationWebhookCount} , tested {notificationTestedCount} , unverified {notificationUntestedCount} endpoints
                                    </div>
                                )}
                            </div>
                    <div className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 text-sm dark:border-slate-700/60 dark:bg-slate-800">
                                <div className="flex items-start justify-between gap-2">
                                    <div>
                                        <div className="text-xs text-slate-400">Two-way notification commands</div>
                                        <div className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${chatopsBadgeClass}`}>
                                            {chatopsBadgeText}
                                        </div>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => navigate('/notifications')}
                                        className="inline-flex items-center justify-center rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-[11px] font-medium text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900/50 dark:text-slate-200 dark:hover:bg-slate-700"
                                    >
                                        Resolve
                                    </button>
                                </div>
                                    <div className="mt-1 text-xs text-slate-400">{chatopsSummary}</div>
                                    <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
                                        <div className="rounded-xl border border-slate-200/70 bg-slate-50/80 px-3 py-2 dark:border-slate-700/60 dark:bg-slate-900/40">
                                            <div className="text-[11px] text-slate-400">Current entry point</div>
                                            <div className="mt-1 text-xs font-semibold text-slate-700 dark:text-slate-100">{chatopsCurrentEntryLabel}</div>
                                        </div>
                                        <div className="rounded-xl border border-slate-200/70 bg-slate-50/80 px-3 py-2 dark:border-slate-700/60 dark:bg-slate-900/40">
                                            <div className="text-[11px] text-slate-400">{chatopsLatestVerifiedLabel}</div>
                                            <div className="mt-1 text-xs font-semibold text-slate-700 dark:text-slate-100">
                                                {chatopsLatestVerifiedAt ? formatTimestamp(chatopsLatestVerifiedAt) : "None"}
                                            </div>
                                        </div>
                                        <div className="rounded-xl border border-slate-200/70 bg-slate-50/80 px-3 py-2 dark:border-slate-700/60 dark:bg-slate-900/40">
                                            <div className="text-[11px] text-slate-400">Team notification entry point</div>
                                            <div className="mt-1 text-xs font-semibold text-slate-700 dark:text-slate-100">Testing platform group</div>
                                        </div>
                                    </div>
                                    <div className="mt-1 space-y-1 text-xs text-slate-400">
                                        <div>Platform {chatopsPlatformReady ? "Ready" : "Not ready"} · Public endpoint {chatopsExternalCallbackReady ? "Connected" : "Not connected"} · Direct group connection {chatopsDirectChatReady ? "Connected" : "Not connected"}</div>
                                        <div>
                                            External bot {chatopsUnifiedRobotReady ? "Unified bot ready" : chatopsUnifiedRobotPlatformReady ? "Unified bot awaiting group test" : chatopsUnifiedRobotTarget ? "Unified bot setup in progress" : "Multiple entry points remain"}
                                            {' · '}
                                            {chatopsDeliveryStrategy === 'single_robot_with_webhook_fallback'
                                                ? "App bot primary channel with webhook fallback"
                                                : chatopsDeliveryStrategy === 'app_bot_only'
                                                    ? "App bot only"
                                                    : chatopsDeliveryStrategy === 'webhook_only'
                                                        ? "Webhook bot only"
                                                        : "Not configured"}
                                        </div>
                                        <div>{chatopsDeliveryStrategySummary}</div>
                                        <div>Callback URL {chatopsCallbackUrlPublic ? "Publicly reachable" : "Local/private network"}{chatopsCallbackUrl ? ` · ${chatopsCallbackUrl}` : ''}</div>
                                        <div>
                                            Public endpoint probe {chatopsCallbackProbeSuccess ? "Passed" : chatopsCallbackProbeAttempted ? "Failed" : "Not run"}
                                            {chatopsCallbackProbeIssue ? ` · ${chatopsCallbackProbeIssue}` : ''}
                                            {typeof chatopsCallbackProbeStatusCode === 'number' ? ` · HTTP ${chatopsCallbackProbeStatusCode}` : ''}
                                        </div>
                                        <div>Public endpoint {chatopsCallbackProviderLabel}{chatopsCallbackProviderHost ? ` · ${chatopsCallbackProviderHost}` : ''}</div>
                                        {chatopsCallbackProbeSummary && (
                                            <div>{chatopsCallbackProbeSummary}</div>
                                        )}
                                        {chatopsCallbackRecommendation && (
                                            <div>Suggested action {chatopsCallbackRecommendation}</div>
                                        )}
                                        <div>
                                            Historical inbound events {chatopsExternalHistoryObserved ? "Observed" : "Not observed"}
                                            {chatopsLatestExternalSuccessAt ? ` · ${formatTimestamp(chatopsLatestExternalSuccessAt)}` : ''}
                                            {chatopsExternalConnectionStale ? " · Currently degraded" : ''}
                                        </div>
                                        <div>
                                            Latest public self-test {chatopsExternalSelfCheckRecentSuccess ? "Passed" : "Failed"}
                                            {chatopsLatestExternalSelfCheckAt ? ` · ${formatTimestamp(chatopsLatestExternalSelfCheckAt)}` : ''}
                                        </div>
                                        <div>App bot {chatopsAppBotConfigured ? "Configured" : "Not configured"}{chatopsAppBotIdMasked ? ` · ${chatopsAppBotIdMasked}` : ''}</div>
                                        <div>Token {chatopsTokenConfigured ? "Configured" : "Not configured"}{chatopsTokenMasked ? ` · ${chatopsTokenMasked}` : ''}</div>
                                        <div>Challenge self-check {chatopsSubscriptionVerified ? "Passed" : "Failed"}</div>
                                        {(chatopsRecentEventAt || chatopsRecentSuccessAt) && (
                                            <div>Latest event {formatTimestamp(chatopsRecentEventAt || chatopsRecentSuccessAt)}</div>
                                        )}
                                        {chatopsCallbackProbeProbedAt && (
                                            <div>Latest probe {formatTimestamp(chatopsCallbackProbeProbedAt)}</div>
                                        )}
                                        <div>{chatopsActionHint}</div>
                                    </div>
                                </div>
                            <div className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 text-sm dark:border-slate-700/60 dark:bg-slate-800">
                                <div className="text-xs text-slate-400">History integrity</div>
                                <div className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${
                                    maintenanceHistoryClean
                                        ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
                                        : 'bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
                                }`}>
                                    {maintenanceHistoryClean ? "Normal" : `Hidden ${maintenanceSuspectHistoryCount} suspicious records`}
                                </div>
                                <div className="mt-1 text-xs text-slate-400">{maintenanceHistorySummary}</div>
                                {maintenanceArchivedHistoryCount > 0 && (
                                    <div className="mt-1 space-y-1 text-xs text-slate-400">
                                        <div>Archived {maintenanceArchivedHistoryCount} history records</div>
                                        <div>
                                            Archive export {maintenanceArchiveExportFresh ? "Updated" : "Update pending"}
                                            {maintenanceArchiveExportCount > 0 ? ` · Total ${maintenanceArchiveExportCount} occurrences` : ''}
                                        </div>
                                        <div>
                                            Retention policy {maintenanceArchiveRetentionDays} days
                                            {maintenanceArchiveCleanupNeeded
                                                ? ` · Pending cleanup ${maintenanceArchiveCleanupCandidateCount} items`
                                                : " · No pending cleanup"}
                                        </div>
                                        <div>
                                            Cleanup breakdown: records {maintenanceArchiveRunCleanupCandidates} entries
                                            {' · '}
                                            Export files {maintenanceArchiveExportCleanupCandidates} files
                                        </div>
                                        {maintenanceLastArchiveExportAt && (
                                            <div>
                                                Latest export {formatTimestamp(maintenanceLastArchiveExportAt)}
                                                {maintenanceLastArchiveExportFormat ? ` · ${maintenanceLastArchiveExportFormat.toUpperCase()}` : ''}
                                            </div>
                                        )}
                                        {maintenanceLastArchiveExportReason && (
                                            <div>Export reason {maintenanceLastArchiveExportReason}</div>
                                        )}
                                        {maintenanceLastArchiveCleanupAt && (
                                            <div>
                                                Latest cleanup {formatTimestamp(maintenanceLastArchiveCleanupAt)}
                                                {maintenanceLastArchiveCleanupDryRun ? ' · Dry Run' : ` · Records deleted ${maintenanceLastArchiveCleanupDeletedRuns} / Files ${maintenanceLastArchiveCleanupDeletedExports} files`}
                                            </div>
                                        )}
                                        {maintenanceLastArchiveCleanupReason && (
                                            <div>Cleanup reason {maintenanceLastArchiveCleanupReason}</div>
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>
                        {archiveSummary && (
                            <div className="mt-3 rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300">
                                {archiveSummary}
                            </div>
                        )}
                        {shadowDbSummary && (
                            <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300">
                                {shadowDbSummary}
                            </div>
                        )}
                        {archiveExportSummary && (
                            <div className="mt-3 rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300">
                                {archiveExportSummary}
                            </div>
                        )}
                        {archiveCleanupSummary && (
                            <div className="mt-3 rounded-xl border border-indigo-200 bg-indigo-50 px-3 py-2 text-sm text-indigo-700 dark:border-indigo-500/30 dark:bg-indigo-500/10 dark:text-indigo-300">
                                {archiveCleanupSummary}
                            </div>
                        )}
                        <div className="mt-3 rounded-xl border border-slate-200/70 bg-white px-3 py-3 text-sm dark:border-slate-700/60 dark:bg-slate-800">
                            <div className="text-xs text-slate-400">Current business database</div>
                            <div className="mt-1 break-all font-mono text-xs text-slate-700 dark:text-slate-200">{businessDbPath}</div>
                            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-400">
                                <span>Size {formatBytes(businessDbSizeBytes)}</span>
                                <span>Last modified {formatTimestamp(businessDbUpdatedAt)}</span>
                            </div>
                        </div>
                        {maintenanceLastArchiveExportPath && (
                            <div className="mt-3 rounded-xl border border-slate-200/70 bg-white px-3 py-3 text-sm dark:border-slate-700/60 dark:bg-slate-800">
                                <div className="text-xs text-slate-400">Latest archive export file</div>
                                <div className="mt-1 break-all font-mono text-[11px] text-slate-700 dark:text-slate-200">{maintenanceLastArchiveExportPath}</div>
                            </div>
                        )}
                        {shadowBusinessDbs.length > 0 && (
                            <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
                                <div className="flex items-center gap-2 font-semibold">
                                    <AlertTriangle className="h-4 w-4" />
                                    Shadow business databases detected
                                </div>
                                <div className="mt-2 text-xs leading-5">
                                    The current service writes to the business database shown above. These older database paths still exist; avoid starting old instances from the wrong directory:
                                </div>
                                <div className="mt-2 space-y-1">
                                    {shadowBusinessDbs.map(path => (
                                        <div key={path} className="break-all rounded-lg bg-white/70 px-2 py-1 font-mono text-[11px] dark:bg-slate-900/30">
                                            {path}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                        {maintenanceCurrent?.error && (
                            <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300">
                                {maintenanceCurrent.error}
                            </div>
                        )}
                    </div>

                    <div className="rounded-2xl border border-slate-200/70 bg-slate-50/70 p-4 dark:border-slate-700/60 dark:bg-slate-900/30">
                        <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">Recent maintenance records</div>
                        {!!maintenance?.history.suspect_count && (
                            <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
                                Automatically hidden {maintenance.history.suspect_count} suspicious test-contamination records to keep the primary production operations view accurate.
                            </div>
                        )}
                        <div className="mt-3 space-y-2">
                            {!maintenance?.history.items?.length ? (
                                <div className="rounded-xl border border-dashed border-slate-200 px-3 py-6 text-center text-sm text-slate-400 dark:border-slate-700 dark:text-slate-500">
                                    No maintenance records yet
                                </div>
                            ) : maintenance.history.items.slice(0, 5).map(item => (
                                <div key={item.id} className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 dark:border-slate-700/60 dark:bg-slate-800">
                                    <div className="flex items-center justify-between gap-3">
                                        <div className="min-w-0">
                                            <div className="truncate text-sm font-medium text-slate-800 dark:text-slate-100">{item.reason}</div>
                                            <div className="mt-1 text-xs text-slate-400">{formatTimestamp(item.timestamp)}</div>
                                        </div>
                                        <div className="flex shrink-0 items-center gap-2">
                                            {item.warning_detected && (
                                                <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">
                                                    Risk
                                                </span>
                                            )}
                                            {item.risk_alert_sent && (
                                                <span className="rounded-full bg-sky-50 px-2 py-0.5 text-[11px] font-semibold text-sky-700 dark:bg-sky-500/15 dark:text-sky-300">
                                                    Warning sent
                                                </span>
                                            )}
                                            {item.status === 'failed' && item.alert_sent && (
                                                <span className="rounded-full bg-rose-50 px-2 py-0.5 text-[11px] font-semibold text-rose-700 dark:bg-rose-500/15 dark:text-rose-300">
                                                    Alert sent
                                                </span>
                                            )}
                                            <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${item.status === 'failed'
                                                ? 'bg-rose-50 text-rose-600 dark:bg-rose-500/15 dark:text-rose-300'
                                                : 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300'
                                                }`}>
                                                {item.status === 'failed' ? "Failed" : "Success"}
                                            </span>
                                        </div>
                                    </div>
                                    <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-slate-500 dark:text-slate-400">
                                        <span>Duration {formatDuration(item.duration_ms)}</span>
                                        <span>Repaired {item.repair.group_updates + item.repair.record_updates}</span>
                                        <span>Report {item.report_history.updated_entries}</span>
                                    </div>
                                    {item.risk?.summary && (
                                        <div className="mt-2 text-xs text-slate-400">
                                            {item.risk.summary}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {/* Agent fleet overview*/}
            <div
                onClick={() => navigate('/legion')}
                className="group rounded-2xl border border-slate-200 bg-gradient-to-r from-indigo-50/50 via-purple-50/50 to-pink-50/50 dark:from-indigo-500/5 dark:via-purple-500/5 dark:to-pink-500/5 dark:border-slate-700 p-5 shadow-sm hover:shadow-md hover:border-indigo-300/80 dark:hover:border-indigo-500/50 transition-all duration-200 cursor-pointer"
            >
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                        <Swords className="w-4 h-4 text-indigo-500" />
                        Agent fleet overview
                    </h3>
                    <span className="flex items-center gap-1 text-xs text-indigo-500 font-medium group-hover:text-indigo-600 transition-colors">
                        Open agent hub <ChevronRight className="w-3.5 h-3.5" />
                    </span>
                </div>
                <div className="grid grid-cols-3 gap-4">
                    <div className="text-center p-3 rounded-xl bg-white dark:bg-slate-800 border border-slate-200/50 dark:border-slate-700/50">
                        <Users className="w-5 h-5 text-emerald-500 mx-auto mb-1" />
                        <div className="text-2xl font-bold text-slate-800 dark:text-slate-100">{onlineCount}<span className="text-sm text-slate-400 font-normal">/{legionHealth.length}</span></div>
                        <div className="text-xs text-slate-500">Agents online</div>
                    </div>
                    <div className="text-center p-3 rounded-xl bg-white dark:bg-slate-800 border border-slate-200/50 dark:border-slate-700/50">
                        <Swords className="w-5 h-5 text-indigo-500 mx-auto mb-1" />
                        <div className="text-2xl font-bold text-slate-800 dark:text-slate-100">{squadCount}</div>
                        <div className="text-xs text-slate-500">Test squads</div>
                    </div>
                    <div className="text-center p-3 rounded-xl bg-white dark:bg-slate-800 border border-slate-200/50 dark:border-slate-700/50">
                        <Wrench className="w-5 h-5 text-purple-500 mx-auto mb-1" />
                        <div className="text-2xl font-bold text-slate-800 dark:text-slate-100">{skillCount}</div>
                        <div className="text-xs text-slate-500">Skill packages</div>
                    </div>
                </div>
            </div>

            {/* Detailed analysis panel*/}
            <AnalyticsPanel />
        </div>
    );
};

export default DashboardPage;
