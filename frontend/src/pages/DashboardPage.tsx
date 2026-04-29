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

// ── 统计卡片 ──
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

// ── 空状态 ──
const EmptyChart: React.FC<{ message: string }> = ({ message }) => (
    <div className="flex h-52 items-center justify-center text-sm text-slate-400 dark:text-slate-500">
        {message}
    </div>
);

// ── 自定义 Tooltip ──
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
                    {p.name}: <span className="font-bold">{p.value}{p.name === '成功率' ? '%' : ''}</span>
                </p>
            ))}
        </div>
    );
};

// ── 深度分析面板 ──
const REASON_COLORS: Record<string, string> = {
    '超时': '#f59e0b', '元素定位': '#ef4444', '断言失败': '#8b5cf6',
    '网络错误': '#3b82f6', '权限/认证': '#ec4899', '其他': '#94a3b8',
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
                深度分析
            </h3>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* 失败 Top N 热图 */}
                {failures.length > 0 && (
                    <div className="rounded-2xl card-hover-lift border border-slate-200/60 bg-white/80 backdrop-blur-sm p-5 dark:border-slate-700/60 dark:bg-slate-800/60">
                        <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3 flex items-center gap-2">
                            <Bug className="w-4 h-4 text-red-500" />
                            失败热图 Top {failures.length}
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
                                <Bar dataKey="failCount" name="失败次数" fill="#ef4444" radius={[0, 6, 6, 0]} barSize={20} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                )}

                {/* 失败原因分布 */}
                {reasons.length > 0 && (
                    <div className="rounded-2xl card-hover-lift border border-slate-200/60 bg-white/80 backdrop-blur-sm p-5 dark:border-slate-700/60 dark:bg-slate-800/60">
                        <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3 flex items-center gap-2">
                            <AlertTriangle className="w-4 h-4 text-amber-500" />
                            失败原因分类
                        </h4>
                        <div className="space-y-3">
                            {reasons.map((r) => (
                                <div key={r.reason}>
                                    <div className="flex justify-between text-xs mb-1">
                                        <span className="text-slate-600 dark:text-slate-400 font-medium">{r.reason}</span>
                                        <span className="text-slate-500">{r.count} 次 ({r.percentage}%)</span>
                                    </div>
                                    <div className="h-2.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                                        <div
                                            className="h-full rounded-full transition-all duration-500"
                                            style={{
                                                width: `${r.percentage}%`,
                                                backgroundColor: REASON_COLORS[r.reason] || '#94a3b8',
                                            }}
                                        />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {/* Flaky 检测 */}
            {flakyTests.length > 0 && (
                <div className="rounded-2xl border border-amber-200 bg-amber-50/50 p-5 shadow-sm dark:border-amber-500/30 dark:bg-amber-500/5">
                    <h4 className="text-sm font-semibold text-amber-700 dark:text-amber-400 mb-3 flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4" />
                        Flaky 用例检测 ({flakyTests.length})
                        <span className="ml-auto text-xs font-normal text-amber-600/60 dark:text-amber-400/60">
                            通过率在 20-80% 之间视为 Flaky
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
                                        {t.severity === 'high' ? '高' : '中'}
                                    </span>
                                    <span className="text-xs text-slate-700 dark:text-slate-300 font-medium truncate" title={t.name}>
                                        {t.name}
                                    </span>
                                </div>
                                <div className="flex items-center gap-3 text-[11px] text-slate-500">
                                    <span>共 {t.total} 次</span>
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

    // 初始加载
    useEffect(() => { load(); }, [load]);

    // 每 30s 自动刷新
    const { start } = usePolling(async () => { await load(); }, { interval: 30_000, immediate: false });
    useEffect(() => { start(); }, [start]);

    const formatDuration = (ms: number) => {
        if (ms < 1000) return `${ms}ms`;
        if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
        return `${(ms / 60_000).toFixed(1)}m`;
    };

    const formatTimestamp = (value?: string) => {
        if (!value) return '未执行';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return `${date.getMonth() + 1}/${date.getDate()} ${date.toLocaleTimeString('zh-CN', {
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
                    ? `已归档 ${result.archived_count} 条可疑维护记录，剩余 ${result.remaining} 条待处理`
                    : '当前没有可归档的可疑维护记录'
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
                    ? `已导出 ${result.count} 条归档记录到 ${result.file_path}`
                    : `已生成空归档文件 ${result.file_path}`
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
                    ? `保留策略检查完成：待清理归档记录 ${result.candidate_runs} 条，待清理导出文件 ${result.candidate_exports} 个`
                    : `归档清理完成：删除归档记录 ${result.deleted_runs} 条，删除导出文件 ${result.deleted_exports} 个`
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
                    ? `已隔离 ${result.moved_count} 个影子业务库，当前风险等级 ${result.observability.risk_level}`
                    : `未隔离新的影子业务库，跳过 ${result.skipped_count} 个`
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
    const businessDbPath = platformInfo?.operations?.business_db_path || '未识别';
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
    const notificationSummary = platformInfo?.operations?.notification_summary || maintenanceCurrent?.notification?.summary || '尚未配置启用中的生产告警 Webhook';
    const notificationBadgeText = notificationReady
        ? `健康 ${notificationHealthyCount}/${notificationWebhookCount}`
        : notificationWebhookCount === 0
            ? '未配置'
            : notificationTestedCount === 0
                ? `待验证 ${notificationUntestedCount}`
                : `健康 ${notificationHealthyCount}/${notificationWebhookCount}`;
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
            ? '对外建议使用当前项目专属的同一个通知平台应用机器人承接命令与回复，Webhook 仅保留兜底通知。'
            : '当前仍主要依赖 Webhook 机器人发通知，尚未形成“一个机器人”对外体验。'
    );
    const chatopsSubscriptionVerified = platformInfo?.operations?.commander_chatops_subscription_endpoint_verified ?? false;
    const chatopsTokenConfigured = platformInfo?.operations?.commander_chatops_verification_token_configured ?? false;
    const chatopsTokenMasked = platformInfo?.operations?.commander_chatops_verification_token_masked || '';
    const chatopsCallbackUrl = platformInfo?.operations?.commander_chatops_callback_url || '';
    const chatopsCallbackUrlPublic = platformInfo?.operations?.commander_chatops_callback_url_public ?? false;
    const chatopsCallbackProviderLabel = platformInfo?.operations?.commander_chatops_callback_provider?.label || (chatopsCallbackUrlPublic ? '自定义公网地址' : '本地地址');
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
    const chatopsSummary = platformInfo?.operations?.commander_chatops_summary || '通知平台双向指令状态暂不可用';
    const chatopsLatestVerifiedAt = chatopsLatestExternalSuccessAt || chatopsLatestExternalSelfCheckAt || chatopsRecentSuccessAt || '';
    const chatopsLatestVerifiedLabel = chatopsLatestExternalSuccessAt
        ? '最近真实通知平台回流'
        : chatopsLatestExternalSelfCheckAt
            ? '最近公网自测'
            : chatopsRecentSuccessAt
                ? '最近成功事件'
                : '尚未验证';
    const chatopsCurrentEntryLabel = chatopsDirectChatReady
        ? '单聊 AI Test Platform'
        : chatopsExternalConnectionStale
            ? '历史已打通，当前待恢复'
            : chatopsPlatformReady
                ? '去通知配置页继续联调'
                : '先补平台配置';
    const chatopsBadgeText = chatopsDirectChatReady
        ? '已联通'
        : !chatopsPlatformReady
            ? '平台侧待完成'
            : !chatopsCallbackUrlPublic
                ? '本地回调'
                : chatopsExternalConnectionStale
                    ? '外部已退化'
                : chatopsCallbackProbeAttempted && !chatopsCallbackProbeSuccess
                    ? '公网回探失败'
                : !chatopsAppBotConfigured
                    ? '缺专属机器人'
                    : !chatopsExternalConnected
                        ? '待真实群测'
                        : '待确认';
    const chatopsBadgeClass = chatopsDirectChatReady
        ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
        : chatopsPlatformReady && !(chatopsCallbackProbeAttempted && !chatopsCallbackProbeSuccess)
            ? 'bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
            : chatopsExternalConnectionStale || (chatopsCallbackProbeAttempted && !chatopsCallbackProbeSuccess)
                ? 'bg-rose-50 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300'
                : 'bg-violet-50 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300';
    const chatopsActionHint = !chatopsPlatformReady
        ? '先补齐公网回调、Token 和 challenge 自检'
        : !chatopsCallbackUrlPublic
            ? '先去通知配置页保存公网回调地址'
            : chatopsExternalSelfCheckRecentSuccess && !chatopsDirectChatReady
                ? '公网自测已通过，下一步在目标群里发一条真实消息完成最终联调'
            : chatopsExternalConnectionStale
                ? '平台历史上已打通过，但当前公网入口已退化；先修复公网地址/隧道，再重新做群测'
            : chatopsCallbackProbeAttempted && !chatopsCallbackProbeSuccess
                ? '先修复当前公网回调地址或隧道，再去通知平台后台联调'
                : !chatopsAppBotConfigured
                    ? '先补当前项目专属通知平台应用机器人，再把它加入目标群'
                    : !chatopsExternalConnected
                        ? '去通知平台后台完成事件订阅并发一条测试消息'
                        : '双向指令链路已完成联调';
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
    const maintenanceHistorySummary = platformInfo?.operations?.maintenance_history_summary || maintenanceCurrent?.data_quality?.summary || '维护历史正常';
    const readiness = platformReadiness;
    const readinessStage = readiness?.stage || platformInfo?.operations?.readiness_stage || 'beta';
    const readinessScore = readiness?.score ?? platformInfo?.operations?.readiness_score ?? 0;
    const readinessSummary = readiness?.summary || platformInfo?.operations?.readiness_summary || '就绪度评估暂不可用';
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
            {/* ── 标题 ── */}
            <div className="mb-2">
                <h2 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
                    <div className="p-2 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 text-white">
                        <LayoutDashboard className="w-5 h-5" />
                    </div>
                    控制中心
                </h2>
                <p className="text-slate-500 mt-2 text-sm">智能体状态总览与系统监控</p>
            </div>

            {/* ── 统计卡片组 ── */}
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 stagger-enter">
                <StatCard
                    label="今日执行"
                    value={loading ? '—' : stats?.todayExecutions ?? 0}
                    sub="测试任务执行次数"
                    icon={<Activity className="w-5 h-5" />}
                    gradient="bg-gradient-to-br from-indigo-500 to-indigo-700"
                />
                <StatCard
                    label="成功率"
                    value={loading ? '—' : `${stats?.todaySuccessRate ?? 0}%`}
                    sub="今日通过率"
                    icon={<CheckCircle2 className="w-5 h-5" />}
                    gradient="bg-gradient-to-br from-emerald-500 to-emerald-700"
                />
                <StatCard
                    label="平均耗时"
                    value={loading ? '—' : formatDuration(stats?.avgDurationMs ?? 0)}
                    sub="全部任务平均"
                    icon={<Clock className="w-5 h-5" />}
                    gradient="bg-gradient-to-br from-amber-500 to-orange-600"
                />
                <StatCard
                    label="发现缺陷"
                    value={loading ? '—' : stats?.todayDefects ?? 0}
                    sub="今日错误计数"
                    icon={<Bug className="w-5 h-5" />}
                    gradient="bg-gradient-to-br from-rose-500 to-rose-700"
                />
            </div>

            {/* ── 快速开始 ── */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {[
                    {
                        title: '快速测试',
                        desc: '输入 URL 和需求，AI 自动生成计划并执行',
                        path: '/orchestrator',
                        icon: Play,
                        gradient: 'from-indigo-500 to-blue-500',
                        shadow: 'shadow-indigo-500/20',
                    },
                    {
                        title: '全面测试',
                        desc: '一句话启动多类型测试，Commander 智能调度',
                        path: '/commander',
                        icon: Swords,
                        gradient: 'from-purple-500 to-pink-500',
                        shadow: 'shadow-purple-500/20',
                    },
                    {
                        title: '探索发现',
                        desc: '让 AI 自主浏览网站，自动发现异常和 Bug',
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
                                开始使用 <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                            </div>
                        </div>
                    </button>
                ))}
            </div>

            {/* ── 图表行 ── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {/* 7 天趋势 — 占 2/3 */}
                <div className="lg:col-span-2 card-hover-lift rounded-2xl border border-slate-200/60 bg-white/80 backdrop-blur-sm p-5 dark:border-slate-700/60 dark:bg-slate-800/60">
                    <h3 className="mb-4 text-base font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                        <BarChart3 className="w-4 h-4 text-indigo-500" />
                        最近 7 天趋势
                    </h3>
                    {!stats?.trend7Days?.some(d => d.executions > 0) ? (
                        <EmptyChart message="暂无执行数据" />
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
                                <Area yAxisId="left" type="monotone" dataKey="executions" name="执行数" stroke="#6366f1" fill="url(#colorExec)" strokeWidth={2} />
                                <Area yAxisId="right" type="monotone" dataKey="successRate" name="成功率" stroke="#22c55e" fill="url(#colorRate)" strokeWidth={2} />
                            </AreaChart>
                        </ResponsiveContainer>
                    )}
                </div>

                {/* 测试类型分布 — 占 1/3 */}
                <div className="rounded-2xl card-hover-lift border border-slate-200/60 bg-white/80 backdrop-blur-sm p-5 dark:border-slate-700/60 dark:bg-slate-800/60">
                    <h3 className="mb-4 text-base font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                        <PieChartLucide className="w-4 h-4 text-violet-500" />
                        测试类型分布
                    </h3>
                    {!stats?.typeDistribution?.length ? (
                        <EmptyChart message="暂无数据" />
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
                            生产推进视角
                        </h3>
                        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                            同时从局部模块和全局架构两个层面，衡量平台距离生产级还有多远。
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="text-right">
                            <div className="text-xs text-slate-400">总体就绪度</div>
                            <div className="text-2xl font-bold text-slate-900 dark:text-white">{readinessScore}</div>
                        </div>
                        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${readinessBadgeClass}`}>
                            {readinessStage === 'production-ready' ? '生产级' : readinessStage === 'pre-production' ? '准生产' : 'Beta'}
                        </span>
                    </div>
                </div>
                <div className="mt-4 rounded-xl border border-slate-200/70 bg-slate-50/70 px-4 py-3 text-sm text-slate-600 dark:border-slate-700/60 dark:bg-slate-900/30 dark:text-slate-300">
                    {readinessSummary}
                </div>
                <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
                    <div className="rounded-2xl border border-slate-200/70 bg-slate-50/70 p-4 dark:border-slate-700/60 dark:bg-slate-900/30">
                        <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">局部视角</div>
                        <div className="mt-3 space-y-3">
                            {(readiness?.local || []).map(section => (
                                <div key={section.key} className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 dark:border-slate-700/60 dark:bg-slate-800">
                                    <div className="flex items-center justify-between gap-3">
                                        <div className="text-sm font-medium text-slate-800 dark:text-slate-100">{section.name}</div>
                                        <div className="flex items-center gap-2">
                                            <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${readinessStatusClass(section.status)}`}>
                                                {section.status === 'good' ? '稳定' : section.status === 'warning' ? '关注' : '阻塞'}
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
                        <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">全局视角</div>
                        <div className="mt-3 space-y-3">
                            {(readiness?.global || []).map(section => (
                                <div key={section.key} className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 dark:border-slate-700/60 dark:bg-slate-800">
                                    <div className="flex items-center justify-between gap-3">
                                        <div className="text-sm font-medium text-slate-800 dark:text-slate-100">{section.name}</div>
                                        <div className="flex items-center gap-2">
                                            <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${readinessStatusClass(section.status)}`}>
                                                {section.status === 'good' ? '稳定' : section.status === 'warning' ? '关注' : '阻塞'}
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
                        <div className="text-sm font-semibold text-indigo-700 dark:text-indigo-300">下一步推进建议</div>
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
                                <div className="text-sm font-semibold text-rose-700 dark:text-rose-300">关键行动项</div>
                                <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                                    当前共 {remediation.counts.total} 项，其中阻塞项 {remediation.counts.blocking} 项。
                                </div>
                            </div>
                            <div className="flex items-center gap-2 text-xs">
                                <span className="rounded-full bg-white/80 px-2 py-1 text-slate-700 dark:bg-slate-900/40 dark:text-slate-200">
                                    局部 {remediation.counts.local}
                                </span>
                                <span className="rounded-full bg-white/80 px-2 py-1 text-slate-700 dark:bg-slate-900/40 dark:text-slate-200">
                                    全局 {remediation.counts.global}
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
                                                    {item.scope === 'local' ? '局部' : '全局'}
                                                </span>
                                            </div>
                                            <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">{item.summary}</div>
                                            <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">影响：{item.impact}</div>
                                            <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">下一步：{item.next_step}</div>
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
                                                立即处理
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
                            平台维护
                        </h3>
                        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                            启动自维护、历史修复和报告修复的当前状态与最近执行记录
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
                                {shadowQuarantineRunning ? '隔离中...' : '隔离影子库'}
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
                                {archiveCleanupRunning ? '检查中...' : '检查归档保留'}
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
                                {archiveCleanupRunning ? '清理中...' : '清理过期归档'}
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
                                {archiveExportRunning ? '导出中...' : '导出归档记录'}
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
                                {archiveRunning ? '归档中...' : '归档可疑记录'}
                            </button>
                        )}
                        <button
                            type="button"
                            onClick={() => { void triggerMaintenance(); }}
                            disabled={maintenanceRunning}
                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-cyan-200 bg-cyan-50 px-4 py-2 text-sm font-medium text-cyan-700 transition hover:bg-cyan-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-cyan-500/30 dark:bg-cyan-500/10 dark:text-cyan-300 dark:hover:bg-cyan-500/20"
                        >
                            <RefreshCw className={`w-4 h-4 ${maintenanceRunning ? 'animate-spin' : ''}`} />
                            {maintenanceRunning ? '执行中...' : '立即维护'}
                        </button>
                    </div>
                </div>

                <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[1.1fr_0.9fr]">
                    <div className="rounded-2xl border border-slate-200/70 bg-slate-50/70 p-4 dark:border-slate-700/60 dark:bg-slate-900/30">
                        <div className="flex items-center justify-between">
                            <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">当前维护状态</div>
                            <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${maintenanceBadgeClass}`}>
                                {maintenanceCurrent?.status === 'failed'
                                    ? '失败'
                                    : maintenanceCurrent?.skipped
                                        ? '节流跳过'
                                        : maintenanceCurrent?.status === 'success'
                                            ? '正常'
                                            : '未执行'}
                            </span>
                        </div>
                        <div className="mt-4 grid grid-cols-2 gap-3">
                            <div className="rounded-xl bg-white px-3 py-3 text-sm dark:bg-slate-800">
                                <div className="text-xs text-slate-400">最近执行</div>
                                <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{formatTimestamp(maintenanceCurrent?.timestamp)}</div>
                            </div>
                            <div className="rounded-xl bg-white px-3 py-3 text-sm dark:bg-slate-800">
                                <div className="text-xs text-slate-400">耗时</div>
                                <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{formatDuration(maintenanceCurrent?.duration_ms || 0)}</div>
                            </div>
                            <div className="rounded-xl bg-white px-3 py-3 text-sm dark:bg-slate-800">
                                <div className="text-xs text-slate-400">触发原因</div>
                                <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{maintenanceCurrent?.reason || '未执行'}</div>
                            </div>
                            <div className="rounded-xl bg-white px-3 py-3 text-sm dark:bg-slate-800">
                                <div className="text-xs text-slate-400">报告历史</div>
                                <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">
                                    {maintenanceCurrent?.report_history?.history_entries ?? 0} 条 / 修复 {maintenanceCurrent?.report_history?.updated_entries ?? 0} 条
                                </div>
                            </div>
                        </div>
                        <div className="mt-3 grid grid-cols-3 gap-3">
                            <div className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 text-sm dark:border-slate-700/60 dark:bg-slate-800">
                                <div className="text-xs text-slate-400">性能导入</div>
                                <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{maintenanceCurrent?.sync?.performance ?? 0}</div>
                            </div>
                            <div className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 text-sm dark:border-slate-700/60 dark:bg-slate-800">
                                <div className="text-xs text-slate-400">安全导入</div>
                                <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{maintenanceCurrent?.sync?.security ?? 0}</div>
                            </div>
                            <div className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 text-sm dark:border-slate-700/60 dark:bg-slate-800">
                                <div className="text-xs text-slate-400">文本修复</div>
                                <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">
                                    {(maintenanceCurrent?.repair?.group_updates ?? 0) + (maintenanceCurrent?.repair?.record_updates ?? 0)}
                                </div>
                            </div>
                        </div>
                        <div className="mt-3 grid grid-cols-2 gap-3">
                            <div className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 text-sm dark:border-slate-700/60 dark:bg-slate-800">
                                <div className="text-xs text-slate-400">最近活动</div>
                                <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{latestActivity?.reason || '未记录'}</div>
                                <div className="mt-1 text-xs text-slate-400">{formatTimestamp(latestActivity?.timestamp)}</div>
                            </div>
                            <div className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 text-sm dark:border-slate-700/60 dark:bg-slate-800">
                                <div className="text-xs text-slate-400">业务库风险</div>
                                <div className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${
                                    businessDbRiskLevel === 'warning'
                                        ? 'bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
                                        : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
                                }`}>
                                    {businessDbRiskLevel === 'warning' ? `存在 ${shadowBusinessDbCount} 个影子库` : '正常'}
                                </div>
                                <div className="mt-1 text-xs text-slate-400">{maintenanceRisk?.summary || '最新扰动不会覆盖关键维护主状态'}</div>
                                {businessDbRiskLevel === 'warning' && (
                                    <div className="mt-1 text-xs text-slate-400">
                                        预警状态 {maintenanceCurrent?.risk_alert_sent ? '已发送' : '未发送'}
                                    </div>
                                )}
                            </div>
                        </div>
                        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
                            <div className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 text-sm dark:border-slate-700/60 dark:bg-slate-800">
                                <div className="text-xs text-slate-400">告警接出</div>
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
                                        启用 {notificationWebhookCount} 个，已测试 {notificationTestedCount} 个，未验证 {notificationUntestedCount} 个
                                    </div>
                                )}
                            </div>
                    <div className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 text-sm dark:border-slate-700/60 dark:bg-slate-800">
                                <div className="flex items-start justify-between gap-2">
                                    <div>
                                        <div className="text-xs text-slate-400">通知平台双向指令</div>
                                        <div className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${chatopsBadgeClass}`}>
                                            {chatopsBadgeText}
                                        </div>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => navigate('/notifications')}
                                        className="inline-flex items-center justify-center rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-[11px] font-medium text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900/50 dark:text-slate-200 dark:hover:bg-slate-700"
                                    >
                                        去处理
                                    </button>
                                </div>
                                    <div className="mt-1 text-xs text-slate-400">{chatopsSummary}</div>
                                    <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
                                        <div className="rounded-xl border border-slate-200/70 bg-slate-50/80 px-3 py-2 dark:border-slate-700/60 dark:bg-slate-900/40">
                                            <div className="text-[11px] text-slate-400">当前入口</div>
                                            <div className="mt-1 text-xs font-semibold text-slate-700 dark:text-slate-100">{chatopsCurrentEntryLabel}</div>
                                        </div>
                                        <div className="rounded-xl border border-slate-200/70 bg-slate-50/80 px-3 py-2 dark:border-slate-700/60 dark:bg-slate-900/40">
                                            <div className="text-[11px] text-slate-400">{chatopsLatestVerifiedLabel}</div>
                                            <div className="mt-1 text-xs font-semibold text-slate-700 dark:text-slate-100">
                                                {chatopsLatestVerifiedAt ? formatTimestamp(chatopsLatestVerifiedAt) : '暂无'}
                                            </div>
                                        </div>
                                        <div className="rounded-xl border border-slate-200/70 bg-slate-50/80 px-3 py-2 dark:border-slate-700/60 dark:bg-slate-900/40">
                                            <div className="text-[11px] text-slate-400">团队通知入口</div>
                                            <div className="mt-1 text-xs font-semibold text-slate-700 dark:text-slate-100">测试平台群</div>
                                        </div>
                                    </div>
                                    <div className="mt-1 space-y-1 text-xs text-slate-400">
                                        <div>平台侧 {chatopsPlatformReady ? '已就绪' : '未就绪'} · 公网入口 {chatopsExternalCallbackReady ? '已打通' : '未打通'} · 群聊直连 {chatopsDirectChatReady ? '已联通' : '未联通'}</div>
                                        <div>
                                            对外机器人 {chatopsUnifiedRobotReady ? '已完成单机器人' : chatopsUnifiedRobotPlatformReady ? '单机器人待群测' : chatopsUnifiedRobotTarget ? '单机器人建设中' : '仍为多入口'}
                                            {' · '}
                                            {chatopsDeliveryStrategy === 'single_robot_with_webhook_fallback'
                                                ? '应用机器人主通道 + Webhook 兜底'
                                                : chatopsDeliveryStrategy === 'app_bot_only'
                                                    ? '仅应用机器人'
                                                    : chatopsDeliveryStrategy === 'webhook_only'
                                                        ? '仅 Webhook 机器人'
                                                        : '未配置'}
                                        </div>
                                        <div>{chatopsDeliveryStrategySummary}</div>
                                        <div>回调地址 {chatopsCallbackUrlPublic ? '公网可达' : '本地/内网'}{chatopsCallbackUrl ? ` · ${chatopsCallbackUrl}` : ''}</div>
                                        <div>
                                            公网回探 {chatopsCallbackProbeSuccess ? '已通过' : chatopsCallbackProbeAttempted ? '未通过' : '未执行'}
                                            {chatopsCallbackProbeIssue ? ` · ${chatopsCallbackProbeIssue}` : ''}
                                            {typeof chatopsCallbackProbeStatusCode === 'number' ? ` · HTTP ${chatopsCallbackProbeStatusCode}` : ''}
                                        </div>
                                        <div>公网入口 {chatopsCallbackProviderLabel}{chatopsCallbackProviderHost ? ` · ${chatopsCallbackProviderHost}` : ''}</div>
                                        {chatopsCallbackProbeSummary && (
                                            <div>{chatopsCallbackProbeSummary}</div>
                                        )}
                                        {chatopsCallbackRecommendation && (
                                            <div>建议动作 {chatopsCallbackRecommendation}</div>
                                        )}
                                        <div>
                                            历史回流 {chatopsExternalHistoryObserved ? '已观察到' : '未观察到'}
                                            {chatopsLatestExternalSuccessAt ? ` · ${formatTimestamp(chatopsLatestExternalSuccessAt)}` : ''}
                                            {chatopsExternalConnectionStale ? ' · 当前已退化' : ''}
                                        </div>
                                        <div>
                                            最近公网自测 {chatopsExternalSelfCheckRecentSuccess ? '已通过' : '未通过'}
                                            {chatopsLatestExternalSelfCheckAt ? ` · ${formatTimestamp(chatopsLatestExternalSelfCheckAt)}` : ''}
                                        </div>
                                        <div>应用机器人 {chatopsAppBotConfigured ? '已配置' : '未配置'}{chatopsAppBotIdMasked ? ` · ${chatopsAppBotIdMasked}` : ''}</div>
                                        <div>Token {chatopsTokenConfigured ? '已配置' : '未配置'}{chatopsTokenMasked ? ` · ${chatopsTokenMasked}` : ''}</div>
                                        <div>challenge 自检 {chatopsSubscriptionVerified ? '已通过' : '未通过'}</div>
                                        {(chatopsRecentEventAt || chatopsRecentSuccessAt) && (
                                            <div>最近事件 {formatTimestamp(chatopsRecentEventAt || chatopsRecentSuccessAt)}</div>
                                        )}
                                        {chatopsCallbackProbeProbedAt && (
                                            <div>最近回探 {formatTimestamp(chatopsCallbackProbeProbedAt)}</div>
                                        )}
                                        <div>{chatopsActionHint}</div>
                                    </div>
                                </div>
                            <div className="rounded-xl border border-slate-200/70 bg-white px-3 py-3 text-sm dark:border-slate-700/60 dark:bg-slate-800">
                                <div className="text-xs text-slate-400">历史洁净度</div>
                                <div className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${
                                    maintenanceHistoryClean
                                        ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
                                        : 'bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
                                }`}>
                                    {maintenanceHistoryClean ? '正常' : `隐藏 ${maintenanceSuspectHistoryCount} 条可疑记录`}
                                </div>
                                <div className="mt-1 text-xs text-slate-400">{maintenanceHistorySummary}</div>
                                {maintenanceArchivedHistoryCount > 0 && (
                                    <div className="mt-1 space-y-1 text-xs text-slate-400">
                                        <div>已归档 {maintenanceArchivedHistoryCount} 条历史记录</div>
                                        <div>
                                            归档导出 {maintenanceArchiveExportFresh ? '已更新' : '待更新'}
                                            {maintenanceArchiveExportCount > 0 ? ` · 共 ${maintenanceArchiveExportCount} 次` : ''}
                                        </div>
                                        <div>
                                            保留策略 {maintenanceArchiveRetentionDays} 天
                                            {maintenanceArchiveCleanupNeeded
                                                ? ` · 待清理 ${maintenanceArchiveCleanupCandidateCount} 项`
                                                : ' · 当前无待清理项'}
                                        </div>
                                        <div>
                                            清理拆分：记录 {maintenanceArchiveRunCleanupCandidates} 条
                                            {' · '}
                                            导出文件 {maintenanceArchiveExportCleanupCandidates} 个
                                        </div>
                                        {maintenanceLastArchiveExportAt && (
                                            <div>
                                                最近导出 {formatTimestamp(maintenanceLastArchiveExportAt)}
                                                {maintenanceLastArchiveExportFormat ? ` · ${maintenanceLastArchiveExportFormat.toUpperCase()}` : ''}
                                            </div>
                                        )}
                                        {maintenanceLastArchiveExportReason && (
                                            <div>导出原因 {maintenanceLastArchiveExportReason}</div>
                                        )}
                                        {maintenanceLastArchiveCleanupAt && (
                                            <div>
                                                最近清理 {formatTimestamp(maintenanceLastArchiveCleanupAt)}
                                                {maintenanceLastArchiveCleanupDryRun ? ' · Dry Run' : ` · 删除记录 ${maintenanceLastArchiveCleanupDeletedRuns} 条 / 文件 ${maintenanceLastArchiveCleanupDeletedExports} 个`}
                                            </div>
                                        )}
                                        {maintenanceLastArchiveCleanupReason && (
                                            <div>清理原因 {maintenanceLastArchiveCleanupReason}</div>
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
                            <div className="text-xs text-slate-400">当前业务库</div>
                            <div className="mt-1 break-all font-mono text-xs text-slate-700 dark:text-slate-200">{businessDbPath}</div>
                            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-400">
                                <span>大小 {formatBytes(businessDbSizeBytes)}</span>
                                <span>最近修改 {formatTimestamp(businessDbUpdatedAt)}</span>
                            </div>
                        </div>
                        {maintenanceLastArchiveExportPath && (
                            <div className="mt-3 rounded-xl border border-slate-200/70 bg-white px-3 py-3 text-sm dark:border-slate-700/60 dark:bg-slate-800">
                                <div className="text-xs text-slate-400">最近归档导出文件</div>
                                <div className="mt-1 break-all font-mono text-[11px] text-slate-700 dark:text-slate-200">{maintenanceLastArchiveExportPath}</div>
                            </div>
                        )}
                        {shadowBusinessDbs.length > 0 && (
                            <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
                                <div className="flex items-center gap-2 font-semibold">
                                    <AlertTriangle className="h-4 w-4" />
                                    检测到影子业务库
                                </div>
                                <div className="mt-2 text-xs leading-5">
                                    当前服务已统一写入上方业务库；以下旧库路径仍存在，后续请避免从错误目录启动旧实例：
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
                        <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">最近维护记录</div>
                        {!!maintenance?.history.suspect_count && (
                            <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
                                已自动隐藏 {maintenance.history.suspect_count} 条可疑测试污染记录，避免影响生产运维主视图判断。
                            </div>
                        )}
                        <div className="mt-3 space-y-2">
                            {!maintenance?.history.items?.length ? (
                                <div className="rounded-xl border border-dashed border-slate-200 px-3 py-6 text-center text-sm text-slate-400 dark:border-slate-700 dark:text-slate-500">
                                    暂无维护记录
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
                                                    风险
                                                </span>
                                            )}
                                            {item.risk_alert_sent && (
                                                <span className="rounded-full bg-sky-50 px-2 py-0.5 text-[11px] font-semibold text-sky-700 dark:bg-sky-500/15 dark:text-sky-300">
                                                    已预警
                                                </span>
                                            )}
                                            {item.status === 'failed' && item.alert_sent && (
                                                <span className="rounded-full bg-rose-50 px-2 py-0.5 text-[11px] font-semibold text-rose-700 dark:bg-rose-500/15 dark:text-rose-300">
                                                    已告警
                                                </span>
                                            )}
                                            <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${item.status === 'failed'
                                                ? 'bg-rose-50 text-rose-600 dark:bg-rose-500/15 dark:text-rose-300'
                                                : 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300'
                                                }`}>
                                                {item.status === 'failed' ? '失败' : '成功'}
                                            </span>
                                        </div>
                                    </div>
                                    <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-slate-500 dark:text-slate-400">
                                        <span>耗时 {formatDuration(item.duration_ms)}</span>
                                        <span>修复 {item.repair.group_updates + item.repair.record_updates}</span>
                                        <span>报告 {item.report_history.updated_entries}</span>
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

            {/* ── 军团概览 ── */}
            <div
                onClick={() => navigate('/legion')}
                className="group rounded-2xl border border-slate-200 bg-gradient-to-r from-indigo-50/50 via-purple-50/50 to-pink-50/50 dark:from-indigo-500/5 dark:via-purple-500/5 dark:to-pink-500/5 dark:border-slate-700 p-5 shadow-sm hover:shadow-md hover:border-indigo-300/80 dark:hover:border-indigo-500/50 transition-all duration-200 cursor-pointer"
            >
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                        <Swords className="w-4 h-4 text-indigo-500" />
                        军团概览
                    </h3>
                    <span className="flex items-center gap-1 text-xs text-indigo-500 font-medium group-hover:text-indigo-600 transition-colors">
                        进入军团中心 <ChevronRight className="w-3.5 h-3.5" />
                    </span>
                </div>
                <div className="grid grid-cols-3 gap-4">
                    <div className="text-center p-3 rounded-xl bg-white dark:bg-slate-800 border border-slate-200/50 dark:border-slate-700/50">
                        <Users className="w-5 h-5 text-emerald-500 mx-auto mb-1" />
                        <div className="text-2xl font-bold text-slate-800 dark:text-slate-100">{onlineCount}<span className="text-sm text-slate-400 font-normal">/{legionHealth.length}</span></div>
                        <div className="text-xs text-slate-500">Agent 在线</div>
                    </div>
                    <div className="text-center p-3 rounded-xl bg-white dark:bg-slate-800 border border-slate-200/50 dark:border-slate-700/50">
                        <Swords className="w-5 h-5 text-indigo-500 mx-auto mb-1" />
                        <div className="text-2xl font-bold text-slate-800 dark:text-slate-100">{squadCount}</div>
                        <div className="text-xs text-slate-500">测试班</div>
                    </div>
                    <div className="text-center p-3 rounded-xl bg-white dark:bg-slate-800 border border-slate-200/50 dark:border-slate-700/50">
                        <Wrench className="w-5 h-5 text-purple-500 mx-auto mb-1" />
                        <div className="text-2xl font-bold text-slate-800 dark:text-slate-100">{skillCount}</div>
                        <div className="text-xs text-slate-500">技能包</div>
                    </div>
                </div>
            </div>

            {/* ── 深度分析面板 ── */}
            <AnalyticsPanel />
        </div>
    );
};

export default DashboardPage;
