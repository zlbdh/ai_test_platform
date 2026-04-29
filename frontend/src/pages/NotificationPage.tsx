import { useState, useEffect, useCallback } from 'react';
import {
    Bell, Plus, Trash2, CheckCircle2, XCircle, Loader2,
    TestTubes, X, RefreshCw, Copy, Check,
} from '../components/icons';
import {
    configureCommanderChatOpsAppBot,
    unbindCommanderChatOpsAppBot,
    selfCheckCommanderChatOpsAppBot,
    getCommanderChatOpsOverview,
    configureCommanderChatOpsCallbackUrl,
    runCommanderChatOpsExternalSelfCheck,
    refreshCommanderChatOpsProbe,
    restartCommanderChatOpsLocalTunnel,
    configureCommanderChatOpsToken,
    createNotificationWebhook,
    deleteNotificationWebhook,
    drillNotificationWebhooks,
    selfCheckCommanderChatOpsSubscription,
    simulateCommanderChatOps,
    type CommanderChatOpsOverview,
    type CommanderChatOpsCallbackConfigResponse,
    type CommanderChatOpsProbeRefreshResponse,
    type CommanderChatOpsLocalTunnelRestartResponse,
    type CommanderChatOpsAppBotConfigResponse,
    type CommanderChatOpsAppBotUnbindResponse,
    type CommanderChatOpsAppBotSelfCheckResponse,
    type CommanderChatOpsExternalSelfCheckResponse,
    type CommanderChatOpsSimulateResponse,
    type CommanderChatOpsSubscriptionSelfCheckResponse,
    type CommanderChatOpsTokenConfigResponse,
    getNotificationOverview,
    type NotificationOverview,
    type NotificationDrillResponse,
    type NotificationWebhook,
    testNotificationWebhook,
    updateNotificationWebhook,
} from '../services/notificationService';
import { API_BASE_URL } from '../config';

const TYPE_LABELS: Record<string, string> = {
    dingtalk: '钉钉',
    wecom: '企业微信',
    notification_platform: '通知平台',
    custom: '自定义',
};

export default function NotificationPage() {
    const [webhooks, setWebhooks] = useState<NotificationWebhook[]>([]);
    const [overview, setOverview] = useState<NotificationOverview | null>(null);
    const [chatopsOverview, setChatopsOverview] = useState<CommanderChatOpsOverview | null>(null);
    const [showAdd, setShowAdd] = useState(false);
    const [name, setName] = useState('');
    const [url, setUrl] = useState('');
    const [type, setType] = useState('dingtalk');
    const [enabled, setEnabled] = useState(true);
    const [testAfterCreate, setTestAfterCreate] = useState(true);
    const [testing, setTesting] = useState<string | null>(null);
    const [toggling, setToggling] = useState<string | null>(null);
    const [drilling, setDrilling] = useState(false);
    const [testResult, setTestResult] = useState<{ id: string; ok: boolean; msg: string } | null>(null);
    const [drillResult, setDrillResult] = useState<NotificationDrillResponse | null>(null);
    const [simulateMessage, setSimulateMessage] = useState('状态');
    const [simulating, setSimulating] = useState(false);
    const [simulateResult, setSimulateResult] = useState<CommanderChatOpsSimulateResponse | null>(null);
    const [publicApiBaseUrlInput, setPublicApiBaseUrlInput] = useState('');
    const [lastAutoFilledBaseUrl, setLastAutoFilledBaseUrl] = useState('');
    const [configuringCallbackUrl, setConfiguringCallbackUrl] = useState(false);
    const [callbackConfigResult, setCallbackConfigResult] = useState<CommanderChatOpsCallbackConfigResponse | null>(null);
    const [refreshingProbe, setRefreshingProbe] = useState(false);
    const [probeRefreshResult, setProbeRefreshResult] = useState<CommanderChatOpsProbeRefreshResponse | null>(null);
    const [restartingLocalTunnel, setRestartingLocalTunnel] = useState(false);
    const [localTunnelRestartResult, setLocalTunnelRestartResult] = useState<CommanderChatOpsLocalTunnelRestartResponse | null>(null);
    const [externallyChecking, setExternallyChecking] = useState(false);
    const [externalCheckResult, setExternalCheckResult] = useState<CommanderChatOpsExternalSelfCheckResponse | null>(null);
    const [appBotAppIdInput, setAppBotAppIdInput] = useState('');
    const [appBotSecretInput, setAppBotSecretInput] = useState('');
    const [configuringAppBot, setConfiguringAppBot] = useState(false);
    const [appBotConfigResult, setAppBotConfigResult] = useState<CommanderChatOpsAppBotConfigResponse | null>(null);
    const [unbindingAppBot, setUnbindingAppBot] = useState(false);
    const [appBotUnbindResult, setAppBotUnbindResult] = useState<CommanderChatOpsAppBotUnbindResponse | null>(null);
    const [checkingAppBot, setCheckingAppBot] = useState(false);
    const [appBotSelfCheckResult, setAppBotSelfCheckResult] = useState<CommanderChatOpsAppBotSelfCheckResponse | null>(null);
    const [configuringToken, setConfiguringToken] = useState(false);
    const [tokenConfigResult, setTokenConfigResult] = useState<CommanderChatOpsTokenConfigResponse | null>(null);
    const [selfCheckingSubscription, setSelfCheckingSubscription] = useState(false);
    const [subscriptionCheckResult, setSubscriptionCheckResult] = useState<CommanderChatOpsSubscriptionSelfCheckResponse | null>(null);
    const [copyFeedback, setCopyFeedback] = useState<{ key: string; message: string } | null>(null);

    const load = useCallback(async () => {
        try {
            const [notificationData, chatopsData] = await Promise.all([
                getNotificationOverview(),
                getCommanderChatOpsOverview(),
            ]);
            setOverview(notificationData.overview);
            setWebhooks(notificationData.webhooks || []);
            setChatopsOverview(chatopsData);
            setSimulateResult(prev => prev ? { ...prev, overview: chatopsData } : prev);
        } catch { /* ignore */ }
    }, []);

    useEffect(() => {
        const timer = window.setTimeout(() => {
            void load();
        }, 0);
        return () => window.clearTimeout(timer);
    }, [load]);

    useEffect(() => {
        const callbackUrl = chatopsOverview?.callback_url || '';
        const suffix = '/api/commander/notification_platform/events';
        if (callbackUrl.endsWith(suffix)) {
            const nextBaseUrl = callbackUrl.slice(0, -suffix.length);
            if (!publicApiBaseUrlInput || publicApiBaseUrlInput === lastAutoFilledBaseUrl) {
                setPublicApiBaseUrlInput(nextBaseUrl);
                setLastAutoFilledBaseUrl(nextBaseUrl);
            }
        }
    }, [chatopsOverview?.callback_url, publicApiBaseUrlInput, lastAutoFilledBaseUrl]);

    const handleAdd = async () => {
        if (!name.trim() || !url.trim()) return;
        const created = await createNotificationWebhook({ name, url, type, enabled });
        if (enabled && testAfterCreate) {
            setTesting(created.id);
            try {
                const data = await testNotificationWebhook(created.id);
                setTestResult({
                    id: created.id,
                    ok: data.success,
                    msg: data.success ? (data.message || '发送成功') : (data.error || data.message || `HTTP ${data.status_code}`),
                });
            } finally {
                setTesting(null);
            }
        }
        setShowAdd(false);
        setName('');
        setUrl('');
        setEnabled(true);
        setTestAfterCreate(true);
        load();
    };

    const handleDelete = async (id: string) => {
        await deleteNotificationWebhook(id);
        load();
    };

    const handleTest = async (id: string) => {
        setTesting(id);
        setTestResult(null);
        try {
            const data = await testNotificationWebhook(id);
            setTestResult({ id, ok: data.success, msg: data.success ? (data.message || '发送成功') : (data.error || data.message || `HTTP ${data.status_code}`) });
            await load();
        } catch (e) {
            setTestResult({ id, ok: false, msg: '请求失败' });
        }
        setTesting(null);
    };

    const handleDrill = async () => {
        setDrilling(true);
        setDrillResult(null);
        try {
            const data = await drillNotificationWebhooks();
            setDrillResult(data);
            await load();
        } finally {
            setDrilling(false);
        }
    };

    const handleToggleEnabled = async (wh: NotificationWebhook) => {
        setToggling(wh.id);
        try {
            await updateNotificationWebhook(wh.id, { enabled: !wh.enabled });
            await load();
        } finally {
            setToggling(null);
        }
    };

    const handleSimulate = async (message: string = simulateMessage) => {
        const normalizedMessage = message.trim();
        if (!normalizedMessage) return;
        setSimulating(true);
        try {
            const data = await simulateCommanderChatOps({
                message: normalizedMessage,
                from_user: 'notification_debug',
                chat_id: 'notification_debug_chat',
                deliver: true,
            });
            setSimulateMessage(normalizedMessage);
            setSimulateResult(data);
            setChatopsOverview(data.overview);
        } finally {
            setSimulating(false);
        }
    };

    const handleConfigureToken = async () => {
        setConfiguringToken(true);
        try {
            const data = await configureCommanderChatOpsToken({ regenerate: true });
            setTokenConfigResult(data);
            setChatopsOverview(data.overview);
        } finally {
            setConfiguringToken(false);
        }
    };

    const handleConfigureCallbackUrl = async () => {
        setConfiguringCallbackUrl(true);
        try {
            const data = await configureCommanderChatOpsCallbackUrl({
                public_api_base_url: publicApiBaseUrlInput.trim(),
            });
            setCallbackConfigResult(data);
            setChatopsOverview(data.overview);
        } finally {
            setConfiguringCallbackUrl(false);
        }
    };

    const handleConfigureAppBot = async () => {
        if (!appBotAppIdInput.trim() || !appBotSecretInput.trim()) return;
        setConfiguringAppBot(true);
        try {
            setAppBotUnbindResult(null);
            const data = await configureCommanderChatOpsAppBot({
                app_id: appBotAppIdInput.trim(),
                app_secret: appBotSecretInput.trim(),
            });
            setAppBotConfigResult(data);
            setChatopsOverview(data.overview);
            setAppBotSecretInput('');
        } finally {
            setConfiguringAppBot(false);
        }
    };

    const handleUnbindAppBot = async () => {
        setUnbindingAppBot(true);
        try {
            const data = await unbindCommanderChatOpsAppBot({ purge_history: true });
            setAppBotUnbindResult(data);
            setAppBotConfigResult(null);
            setAppBotSelfCheckResult(null);
            setAppBotAppIdInput('');
            setAppBotSecretInput('');
            setChatopsOverview(data.overview);
        } finally {
            setUnbindingAppBot(false);
        }
    };

    const handleSelfCheckAppBot = async () => {
        setCheckingAppBot(true);
        try {
            const data = await selfCheckCommanderChatOpsAppBot();
            setAppBotSelfCheckResult(data);
            setChatopsOverview(data.overview);
        } finally {
            setCheckingAppBot(false);
        }
    };

    const handleRefreshProbe = async () => {
        setRefreshingProbe(true);
        try {
            const data = await refreshCommanderChatOpsProbe();
            setProbeRefreshResult(data);
            setChatopsOverview(data.overview);
        } finally {
            setRefreshingProbe(false);
        }
    };

    const handleRestartLocalTunnel = async () => {
        setRestartingLocalTunnel(true);
        try {
            const data = await restartCommanderChatOpsLocalTunnel();
            setLocalTunnelRestartResult(data);
            setChatopsOverview(data.overview);
        } finally {
            setRestartingLocalTunnel(false);
        }
    };

    const handleSubscriptionSelfCheck = async () => {
        setSelfCheckingSubscription(true);
        try {
            const data = await selfCheckCommanderChatOpsSubscription({ challenge: 'codex-self-check' });
            setSubscriptionCheckResult(data);
            setChatopsOverview(data.overview);
        } finally {
            setSelfCheckingSubscription(false);
        }
    };

    const handleExternalSelfCheck = async () => {
        setExternallyChecking(true);
        try {
            const data = await runCommanderChatOpsExternalSelfCheck();
            setExternalCheckResult(data);
            setChatopsOverview(data.overview);
        } finally {
            setExternallyChecking(false);
        }
    };

    const handleCopy = useCallback(async (key: string, text: string, message: string) => {
        if (!text.trim()) return;
        try {
            await navigator.clipboard.writeText(text);
            setCopyFeedback({ key, message });
        } catch {
            setCopyFeedback({ key, message: '复制失败，请检查浏览器剪贴板权限。' });
        }
    }, []);

    const formatTimestamp = (value?: string) => {
        if (!value) return '未测试';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return `${date.getMonth() + 1}/${date.getDate()} ${date.toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false,
        })}`;
    };

    const formatReplyMode = (value?: string) => {
        switch (value) {
            case 'app_bot':
                return '应用机器人';
            case 'app_bot_fallback_webhook':
                return '应用机器人失败，已走 Webhook 兜底';
            case 'webhook_only':
                return 'Webhook 机器人';
            default:
                return value || '未知';
        }
    };

    const formatBindingSource = (value?: string) => {
        switch (value) {
            case 'event_subscription':
                return '通知平台事件订阅';
            case 'simulate':
                return '平台模拟';
            case 'external_self_check':
                return '公网自测';
            default:
                return value || '未知来源';
        }
    };

    const productionReady = overview?.production_ready ?? false;
    const notification_platformCallbackUrl = chatopsOverview?.callback_url || `${API_BASE_URL}/api/commander/notification_platform/events`;
    const chatopsReady = chatopsOverview?.ready ?? false;
    const chatopsWebhookReady = chatopsOverview?.webhook_ready ?? false;
    const chatopsPlatformReady = chatopsOverview?.platform_ready ?? false;
    const chatopsExternalConnectedCurrent = chatopsOverview?.external_connected_current ?? chatopsOverview?.external_connected ?? false;
    const chatopsExternalHistoryObserved = chatopsOverview?.external_connected_history_observed ?? !!chatopsOverview?.latest_external_successful_event;
    const chatopsExternalConnectionStale = chatopsOverview?.external_connection_stale ?? (chatopsExternalHistoryObserved && !chatopsExternalConnectedCurrent);
    const chatopsExternalCallbackReady = chatopsOverview?.external_callback_ready ?? false;
    const chatopsDirectChatReady = chatopsOverview?.direct_chat_ready ?? chatopsReady;
    const chatopsAppBotConfigured = chatopsOverview?.app_bot_configured ?? false;
    const chatopsAppBotReady = chatopsOverview?.app_bot_ready ?? false;
    const chatopsAppBotIdMasked = chatopsOverview?.app_bot_id_masked || '';
    const latestAppBotCheck = chatopsOverview?.app_bot_check ?? null;
    const unifiedRobotTarget = chatopsOverview?.unified_robot_target ?? chatopsAppBotConfigured;
    const unifiedRobotPlatformReady = chatopsOverview?.unified_robot_platform_ready ?? (chatopsAppBotConfigured && chatopsExternalCallbackReady);
    const unifiedRobotReady = chatopsOverview?.unified_robot_ready ?? chatopsDirectChatReady;
    const deliveryStrategy = chatopsOverview?.delivery_strategy || (chatopsAppBotConfigured ? 'single_robot_with_webhook_fallback' : 'webhook_only');
    const deliveryStrategySummary = chatopsOverview?.delivery_strategy_summary || (
        chatopsAppBotConfigured
            ? '对外建议使用当前项目专属的同一个通知平台应用机器人承接命令与回复，Webhook 仅保留兜底通知。'
            : '当前仍主要依赖 Webhook 机器人发通知，尚未形成对外单机器人体验。'
    );
    const chatopsCallbackProviderLabel = chatopsOverview?.callback_provider?.label || (chatopsOverview?.callback_url_public ? '自定义公网地址' : '本地地址');
    const chatopsCallbackProviderHost = chatopsOverview?.callback_provider?.host || '';
    const chatopsCallbackRecommendation = chatopsOverview?.callback_recommendation || '';
    const callbackProbe = chatopsOverview?.callback_probe ?? null;
    const callbackProbeHistory = chatopsOverview?.callback_probe_history ?? [];
    const localTunnel = chatopsOverview?.local_tunnel ?? null;
    const recentChatBindings = chatopsOverview?.recent_chat_bindings ?? [];
    const latestChatopsEvent = chatopsOverview?.latest_event ?? null;
    const latestSuccessfulChatopsEvent = chatopsOverview?.latest_successful_event ?? null;
    const latestExternalSuccessAt = chatopsOverview?.latest_external_success_at || chatopsOverview?.latest_external_successful_event?.created_at || '';
    const latestExternalSelfCheckEvent = chatopsOverview?.latest_external_self_check_event ?? null;
    const latestExternalSelfCheckAt = chatopsOverview?.latest_external_self_check_at || latestExternalSelfCheckEvent?.created_at || '';
    const externalSelfCheckRecentSuccess = chatopsOverview?.external_self_check_recent_success ?? false;
    const latestSubscriptionCheckEvent = chatopsOverview?.latest_subscription_check_event ?? null;
    const chatopsDirectChatRecoveredHistory = chatopsExternalHistoryObserved && !!latestExternalSuccessAt;
    const chatopsDirectChatDegraded = !chatopsDirectChatReady && chatopsDirectChatRecoveredHistory;
    const directChatStatusLabel = chatopsDirectChatReady
        ? '单聊可用'
        : chatopsDirectChatDegraded
            ? '历史已联通'
            : '单聊待联通';
    const directChatStatusClass = chatopsDirectChatReady
        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
        : chatopsDirectChatDegraded
            ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
            : chatopsPlatformReady
                ? 'bg-cyan-100 text-cyan-700 dark:bg-cyan-500/15 dark:text-cyan-300'
                : 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300';
    const directChatDescription = chatopsDirectChatDegraded
        ? `用于个人单聊发指令并即时拿回复；最近一次真实单聊已成功${latestExternalSuccessAt ? `（${formatTimestamp(latestExternalSuccessAt)}）` : ''}，但当前公网入口退化，恢复后可继续直接对话。`
        : '用于个人单聊发指令并即时拿回复，当前推荐在单聊里发送状态 / 报告 / 测试。';
    const commandEntryLabel = chatopsDirectChatReady
        ? '单聊 AI Test Platform 机器人'
        : chatopsDirectChatDegraded
            ? '单聊历史已联通，当前公网入口退化'
            : '先完成应用机器人联调';
    const unifiedRobotBadgeLabel = unifiedRobotReady
        ? '单机器人已完成'
        : chatopsDirectChatDegraded
            ? '单机器人入口退化'
            : unifiedRobotPlatformReady
                ? '单机器人待群测'
                : '单机器人建设中';
    const unifiedRobotBadgeClass = unifiedRobotReady
        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
        : chatopsDirectChatDegraded
            ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
            : unifiedRobotPlatformReady
                ? 'bg-cyan-100 text-cyan-700 dark:bg-cyan-500/15 dark:text-cyan-300'
                : 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300';
    const chatopsCurrentStatusLabel = chatopsDirectChatReady
        ? '当前可直接使用'
        : chatopsDirectChatDegraded
            ? '历史可用，当前需恢复入口'
            : chatopsPlatformReady
                ? '平台侧已就绪，待完成最终联调'
                : '平台侧建设中';
    const chatopsCurrentStatusClass = chatopsDirectChatReady
        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
        : chatopsDirectChatDegraded
            ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
            : chatopsPlatformReady
                ? 'bg-cyan-100 text-cyan-700 dark:bg-cyan-500/15 dark:text-cyan-300'
                : 'bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300';
    const chatopsLatestVerifiedAt = latestExternalSuccessAt || latestExternalSelfCheckAt || latestSuccessfulChatopsEvent?.created_at || '';
    const chatopsLatestVerifiedLabel = latestExternalSuccessAt
        ? '最近真实通知平台回流'
        : latestExternalSelfCheckAt
            ? '最近公网链路自测'
            : latestSuccessfulChatopsEvent?.created_at
                ? '最近平台成功事件'
                : '尚未验证';
    const chatopsCurrentStatusDescription = chatopsDirectChatReady
        ? `当前推荐直接单聊 AI Test Platform 机器人；最近一次真实通知平台回流${chatopsLatestVerifiedAt ? `在 ${formatTimestamp(chatopsLatestVerifiedAt)}` : '已验证'}，可以继续发送状态 / 报告 / 测试。`
        : chatopsDirectChatDegraded
            ? `历史上已经打通过真实通知平台回流${chatopsLatestVerifiedAt ? `（最近一次 ${formatTimestamp(chatopsLatestVerifiedAt)}）` : ''}，但当前公网入口暂时退化；建议先执行“立即重试回探”或“跑公网链路自测”后再继续单聊使用。`
            : chatopsPlatformReady
                ? '平台内部和应用机器人已就绪，下一步重点是完成公网回调联调并做一次真实消息验收。'
                : '当前仍在补齐通知平台双向指令的基础配置，先完成 token、应用机器人或公网回调配置。';
    const chatopsOverviewCards = [
        {
            key: 'status',
            title: '当前状态',
            value: chatopsCurrentStatusLabel,
            detail: chatopsDirectChatReady
                ? '可以直接对话'
                : chatopsDirectChatDegraded
                    ? '先恢复公网入口'
                    : '还需继续联调',
        },
        {
            key: 'entry',
            title: '当前命令入口',
            value: commandEntryLabel,
            detail: '推荐在这里发状态 / 报告 / 测试',
        },
        {
            key: 'verified',
            title: chatopsLatestVerifiedLabel,
            value: chatopsLatestVerifiedAt ? formatTimestamp(chatopsLatestVerifiedAt) : '暂无',
            detail: chatopsLatestVerifiedAt ? '这是最近一次成功验证时间' : '还没有成功记录',
        },
        {
            key: 'notify',
            title: '团队通知入口',
            value: '测试平台群',
            detail: '群里继续负责接收结果与告警',
        },
    ];
    const localTunnelStatusLabel = !localTunnel?.supported
        ? '当前环境不支持'
        : !localTunnel?.script_exists
            ? '脚本缺失'
            : localTunnel?.running
                ? '运行中'
                : '未运行';
    const localTunnelStatusClass = !localTunnel?.supported
        ? 'text-slate-600 dark:text-slate-300'
        : localTunnel?.running
            ? 'text-emerald-600 dark:text-emerald-300'
            : 'text-amber-600 dark:text-amber-300';
    const currentTokenValue = tokenConfigResult?.token || '';
    const currentTokenHint = currentTokenValue
        ? currentTokenValue
        : chatopsOverview?.verification_token_configured
            ? `当前页面未缓存明文 token，请点击“${chatopsOverview.verification_token_configured ? '重新生成 Token' : '生成 Token'}”后再复制。当前摘要：${chatopsOverview?.verification_token_masked || '未生成'}`
            : '当前尚未生成 verification token。';
    const notification_platformRoleCards = [
        {
            key: 'group-notify',
            title: '测试平台群',
            status: productionReady ? '通知可用' : '通知待补齐',
            statusClass: productionReady
                ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
                : 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
            flow: '平台 -> 群',
            description: '用于团队统一接收测试结果、报告提醒、军团状态和平台告警，不承担命令解析。',
            hints: [
                '适合团队同步看结果',
                '保留 Webhook 作为稳定通知通道',
            ],
        },
        {
            key: 'bot-command',
            title: 'AI Test Platform 机器人',
            status: directChatStatusLabel,
            statusClass: directChatStatusClass,
            flow: '你 -> 平台 -> 你',
            description: directChatDescription,
            hints: [
                '状态',
                '报告 <任务ID>',
                '测试 <URL>',
            ],
        },
    ];
    const chatopsGuideText = [
        '通知平台事件订阅配置清单',
        `1. 事件回调 URL：${notification_platformCallbackUrl}`,
        `2. Verification Token：${currentTokenValue || currentTokenHint}`,
        `3. 当前项目专属通知平台应用机器人：${chatopsAppBotConfigured ? `已配置 ${chatopsAppBotIdMasked || ''}` : '仍未配置，请在平台内补 App ID / Secret。'}`,
        `4. 当前公网入口：${chatopsCallbackProviderLabel}${chatopsCallbackProviderHost ? ` (${chatopsCallbackProviderHost})` : ''}`,
        `5. 公网回调回探：${callbackProbe?.summary || '尚未执行回探，保存公网地址后平台会自动诊断。'}`,
        `6. 推荐动作：${chatopsCallbackRecommendation || '先保证公网回调 challenge 回探成功，再去通知平台后台联调。'}`,
        '7. 在通知平台开发者后台开启事件订阅，并订阅消息接收相关事件。',
        '8. 把当前项目专属通知平台应用机器人加入目标群，保存配置后，在群里发送一条文本消息，例如：状态。',
        '9. 若平台仍显示“通知平台侧回流未验证”，请先根据“公网回调回探”提示修复外部入口。',
    ].join('\n');
    const chatopsSetupSteps = [
        {
            key: 'unified-robot',
            title: '单机器人模式',
            done: unifiedRobotTarget,
            detail: unifiedRobotTarget
                ? unifiedRobotReady
                    ? '应用机器人、回调与真实群聊都已打通，对外可以只保留这一个机器人。'
                    : unifiedRobotPlatformReady
                        ? '应用机器人和公网回调都已具备，Webhook 只需保留兜底；再做一次真实群聊联调即可完成。'
                        : deliveryStrategySummary
                : '当前仍主要依赖 Webhook 自定义机器人发通知，还没有形成“一个机器人对外”的体验。',
        },
        {
            key: 'public-url',
            title: '公网回调地址',
            done: !!chatopsOverview?.callback_url_public,
            detail: chatopsOverview?.callback_url_public
                ? '已配置公网基地址，通知平台云端可以访问回调入口。'
                : '当前仍是本地或内网地址，需要先保存一个公网基地址或隧道地址。',
        },
        {
            key: 'callback-probe',
            title: '公网回调回探',
            done: !!callbackProbe?.success,
            detail: !chatopsOverview?.callback_url_public
                ? '当前还是本地或内网地址，平台暂不执行公网回探。'
                : callbackProbe?.summary || '保存公网地址后，平台会自动做一次 challenge 回探诊断。',
        },
        {
            key: 'verification-token',
            title: 'Verification Token',
            done: !!chatopsOverview?.verification_token_configured,
            detail: chatopsOverview?.verification_token_configured
                ? `已配置，当前摘要 ${chatopsOverview?.verification_token_masked || '已生成'}。`
                : '平台里还未生成 verification token。',
        },
        {
            key: 'app-bot',
            title: '通知平台应用机器人',
            done: chatopsAppBotConfigured,
            detail: chatopsAppBotConfigured
                ? `已配置应用机器人，当前摘要 ${chatopsAppBotIdMasked || '已保存'}。`
                : '当前群里仍只是自定义 Webhook 机器人；要让群成员直接发消息回流到平台，还需要在这里补 App ID / Secret。',
        },
        {
            key: 'subscription-self-check',
            title: '平台侧自检',
            done: !!chatopsOverview?.subscription_endpoint_verified,
            detail: chatopsOverview?.subscription_endpoint_verified
                ? 'challenge 自检已通过，平台回调入口格式正确。'
                : '请先执行一次“验证回调入口”，确认 challenge 正常返回。',
        },
        {
            key: 'external-self-check',
            title: '公网链路自测',
            done: externalSelfCheckRecentSuccess,
            detail: !chatopsOverview?.callback_url_public
                ? '需要先配置公网回调地址，平台才能从外部跑 challenge + 文本消息双验证。'
                : externalSelfCheckRecentSuccess
                    ? `最近一次平台公网自测已通过${latestExternalSelfCheckAt ? `（${formatTimestamp(latestExternalSelfCheckAt)}）` : ''}。`
                    : '建议执行一次“跑公网链路自测”，确认 challenge 与文本消息能从公网入口打到平台。',
        },
        {
            key: 'notification_platform-console',
            title: '通知平台后台联调',
            done: chatopsDirectChatReady,
            detail: chatopsDirectChatReady
                ? '最近已经收到通知平台真实文本消息回流。'
                : chatopsExternalConnectionStale
                    ? '平台历史上曾收到真实群消息回流，但当前公网入口已经退化，请先修复外部入口再联调。'
                : !chatopsAppBotConfigured
                    ? '先补齐通知平台应用机器人，再去通知平台后台完成事件订阅和群内联调。'
                    : '还需要在通知平台开发者后台完成事件订阅，并发一条真实群消息做最终联调。',
        },
    ];
    const typePlaceholder = type === 'wecom'
        ? 'https://example.com/webhook?key=...'
        : type === 'notification_platform'
            ? 'https://open.notification_platform.cn/open-apis/bot/v2/hook/...'
            : type === 'custom'
                ? 'https://example.com/webhook'
                : 'https://example.com/robot/send?access_token=...';
    const legionControlHref = '/legion?tab=control';
    const latestEventRunHref = latestChatopsEvent?.run_id
        ? `/legion?tab=control&run=${encodeURIComponent(latestChatopsEvent.run_id)}`
        : '';
    const simulateRunId = simulateResult?.result && typeof simulateResult.result === 'object' && 'run' in simulateResult.result
        ? String(((simulateResult.result as { run?: { run_id?: string } }).run?.run_id) || '')
        : '';
    const simulateRunHref = simulateRunId ? `/legion?tab=control&run=${encodeURIComponent(simulateRunId)}` : '';

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
                        <div className="p-2 rounded-xl bg-gradient-to-br from-pink-500 to-rose-500 text-white">
                            <Bell className="w-5 h-5" />
                        </div>
                        通知配置
                    </h2>
                    <p className="text-slate-500 mt-2 text-sm">测试完成后自动发送通知到钉钉 / 企微 / 通知平台</p>
                </div>
                <div className="flex gap-2">
                    <a
                        href={legionControlHref}
                        className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 text-white rounded-xl text-sm font-medium transition-all hover:bg-slate-700 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                    >
                        前往 Legion 控制中心
                    </a>
                    <button onClick={load} className="p-2.5 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-500 hover:text-indigo-500 transition-colors">
                        <RefreshCw className="w-4 h-4" />
                    </button>
                    <button
                        onClick={() => { void handleDrill(); }}
                        disabled={drilling}
                        className="flex items-center gap-2 px-4 py-2.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 rounded-xl text-sm font-medium transition-all hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-60"
                    >
                        {drilling ? <Loader2 className="w-4 h-4 animate-spin" /> : <TestTubes className="w-4 h-4" />}
                        {drilling ? '演练中...' : '演练启用通道'}
                    </button>
                    <button onClick={() => setShowAdd(true)}
                        className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-pink-500 to-rose-500 text-white rounded-xl text-sm font-medium shadow-lg shadow-pink-500/25 transition-all hover:shadow-xl">
                        <Plus className="w-4 h-4" /> 添加 Webhook
                    </button>
                </div>
            </div>

            <div className={`rounded-2xl border p-5 shadow-sm ${
                productionReady
                    ? 'border-emerald-200 bg-emerald-50/70 dark:border-emerald-500/30 dark:bg-emerald-500/10'
                    : 'border-amber-200 bg-amber-50/70 dark:border-amber-500/30 dark:bg-amber-500/10'
            }`}>
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <div className="flex items-center gap-2 text-sm font-semibold">
                            <Bell className={`w-4 h-4 ${productionReady ? 'text-emerald-600 dark:text-emerald-300' : 'text-amber-600 dark:text-amber-300'}`} />
                            <span className={productionReady ? 'text-emerald-700 dark:text-emerald-300' : 'text-amber-700 dark:text-amber-300'}>
                                {productionReady ? '生产告警已接出' : '生产告警尚未就绪'}
                            </span>
                        </div>
                        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
                            {overview?.summary || '正在加载通知配置概览...'}
                        </p>
                    </div>
                    <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                        <div className="rounded-xl bg-white/85 px-3 py-3 dark:bg-slate-900/40">
                            <div className="text-xs text-slate-400">总数</div>
                            <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{overview?.total ?? 0}</div>
                        </div>
                        <div className="rounded-xl bg-white/85 px-3 py-3 dark:bg-slate-900/40">
                            <div className="text-xs text-slate-400">启用中</div>
                            <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{overview?.enabled ?? 0}</div>
                        </div>
                        <div className="rounded-xl bg-white/85 px-3 py-3 dark:bg-slate-900/40">
                            <div className="text-xs text-slate-400">已验证</div>
                            <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{overview?.healthy_enabled ?? 0}</div>
                        </div>
                        <div className="rounded-xl bg-white/85 px-3 py-3 dark:bg-slate-900/40">
                            <div className="text-xs text-slate-400">未测试</div>
                            <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{overview?.untested_enabled ?? 0}</div>
                        </div>
                    </div>
                </div>
                {!productionReady && (
                    <div className="mt-3 rounded-xl border border-amber-200 bg-white/85 px-4 py-3 text-sm text-slate-700 dark:border-amber-500/20 dark:bg-slate-900/40 dark:text-slate-200">
                        建议先添加 1 个生产可达 Webhook，并立即执行一次测试通知，确认返回 200 后再依赖平台做维护失败和风险预警。
                    </div>
                )}
                {drillResult && (
                    <div className={`mt-3 rounded-xl border px-4 py-3 text-sm ${
                        drillResult.failed === 0
                            ? 'border-emerald-200 bg-white/85 text-slate-700 dark:border-emerald-500/20 dark:bg-slate-900/40 dark:text-slate-200'
                            : 'border-amber-200 bg-white/85 text-slate-700 dark:border-amber-500/20 dark:bg-slate-900/40 dark:text-slate-200'
                    }`}>
                        <div className="font-medium">{drillResult.summary}</div>
                        {drillResult.results.length > 0 && (
                            <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400">
                                {drillResult.results.map(item => (
                                    <span
                                        key={item.id}
                                        className={`rounded-full px-2 py-1 ${
                                            item.success
                                                ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300'
                                                : 'bg-rose-50 text-rose-600 dark:bg-rose-500/15 dark:text-rose-300'
                                        }`}
                                    >
                                        {item.name}: {item.message}
                                    </span>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>

            <div className="rounded-2xl border border-sky-200 bg-sky-50/70 p-5 text-sm text-slate-700 shadow-sm dark:border-sky-500/20 dark:bg-sky-500/10 dark:text-slate-200">
                <div className="font-semibold text-sky-700 dark:text-sky-300">通知平台接入说明</div>
                <div className="mt-2 space-y-2">
                    <p>当前这里配置的是“自定义 Webhook 机器人”，它只能接收平台推送，不能监听群成员发言，所以在群里直接发“你好 / 帮我部署”不会自动回复。</p>
                    <p>如果你要做“在通知平台群里发命令，平台自动执行并回消息”，需要在通知平台开发者后台配置事件订阅，并把消息回调地址指向：</p>
                    <div className="rounded-xl bg-white/90 px-3 py-2 font-mono text-xs text-slate-700 dark:bg-slate-900/40 dark:text-slate-100">
                        {notification_platformCallbackUrl}
                    </div>
                    <p>平台已经内置支持这条入口，支持的文本指令包括：`状态`、`报告 mission_id`、`测试 https://目标地址`。</p>
                </div>
            </div>

            <div
                className={`rounded-2xl border p-5 shadow-sm ${
                    chatopsDirectChatReady
                        ? 'border-emerald-200 bg-emerald-50/70 dark:border-emerald-500/20 dark:bg-emerald-500/10'
                        : chatopsDirectChatDegraded
                            ? 'border-amber-200 bg-amber-50/70 dark:border-amber-500/20 dark:bg-amber-500/10'
                            : 'border-violet-200 bg-violet-50/70 dark:border-violet-500/20 dark:bg-violet-500/10'
                }`}
                data-testid="chatops-current-usage"
            >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <div className="font-semibold text-slate-800 dark:text-slate-100">当前通知平台使用方式</div>
                        <div className="mt-2 text-sm text-slate-600 dark:text-slate-300">
                            {chatopsCurrentStatusDescription}
                        </div>
                    </div>
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${chatopsCurrentStatusClass}`}>
                        {chatopsCurrentStatusLabel}
                    </span>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    {chatopsOverviewCards.map(item => (
                        <div
                            key={item.key}
                            className="rounded-2xl border border-slate-200 bg-white/85 px-4 py-3 dark:border-slate-700 dark:bg-slate-900/40"
                            data-testid={`chatops-overview-card-${item.key}`}
                        >
                            <div className="text-xs text-slate-400">{item.title}</div>
                            <div className="mt-1 text-sm font-semibold text-slate-800 dark:text-slate-100">{item.value}</div>
                            <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{item.detail}</div>
                        </div>
                    ))}
                </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white/80 p-5 shadow-sm dark:border-slate-700/60 dark:bg-slate-800/60">
                <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <div className="font-semibold text-slate-800 dark:text-slate-100">通知平台入口分工</div>
                        <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                            当前项目建议保留“一个群负责通知、一个机器人负责指令”的清晰分工；对外机器人策略是 {deliveryStrategySummary}
                        </div>
                    </div>
                    <div className="rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:bg-slate-900/40 dark:text-slate-300">
                        当前命令入口：{commandEntryLabel}
                    </div>
                </div>
                <div className="mt-4 grid gap-3 lg:grid-cols-2">
                    {notification_platformRoleCards.map(card => (
                        <div
                            key={card.key}
                            className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-4 dark:border-slate-700 dark:bg-slate-900/40"
                            data-testid={`notification_platform-role-card-${card.key}`}
                        >
                            <div className="flex items-center justify-between gap-3">
                                <div className="font-semibold text-slate-800 dark:text-slate-100">{card.title}</div>
                                <span className={`rounded-full px-2 py-1 text-xs ${card.statusClass}`}>{card.status}</span>
                            </div>
                            <div className="mt-2 text-xs text-slate-400">链路：{card.flow}</div>
                            <div className="mt-3 text-sm text-slate-600 dark:text-slate-300">{card.description}</div>
                            <div className="mt-3 flex flex-wrap gap-2">
                                {card.hints.map(hint => (
                                    <span
                                        key={hint}
                                        className="rounded-full bg-white px-2.5 py-1 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-200"
                                    >
                                        {hint}
                                    </span>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <div className={`rounded-2xl border p-5 text-sm shadow-sm ${
                chatopsDirectChatReady
                    ? 'border-emerald-200 bg-emerald-50/70 dark:border-emerald-500/20 dark:bg-emerald-500/10'
                    : chatopsDirectChatDegraded
                        ? 'border-amber-200 bg-amber-50/70 dark:border-amber-500/20 dark:bg-amber-500/10'
                        : 'border-violet-200 bg-violet-50/70 dark:border-violet-500/20 dark:bg-violet-500/10'
            }`}>
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <div className={`font-semibold ${
                            chatopsDirectChatReady
                                ? 'text-emerald-700 dark:text-emerald-300'
                                : chatopsDirectChatDegraded
                                    ? 'text-amber-700 dark:text-amber-300'
                                    : 'text-violet-700 dark:text-violet-300'
                        }`}>
                            通知平台双向指令
                        </div>
                        <div className="mt-2 text-slate-600 dark:text-slate-300">
                            {chatopsOverview?.summary || '正在加载双向指令状态...'}
                        </div>
                        <div className="mt-3 rounded-xl bg-white/90 px-3 py-2 font-mono text-xs text-slate-700 dark:bg-slate-900/40 dark:text-slate-100">
                            {notification_platformCallbackUrl}
                        </div>
                        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-3 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-200">
                            <div className="flex flex-wrap items-center gap-2">
                                <span className="font-semibold">对外机器人方案</span>
                                <span className={`rounded-full px-2 py-0.5 ${unifiedRobotBadgeClass}`}>
                                    {unifiedRobotBadgeLabel}
                                </span>
                                <span className="rounded-full bg-slate-200 px-2 py-0.5 text-slate-700 dark:bg-slate-700 dark:text-slate-200">
                                    {deliveryStrategy === 'single_robot_with_webhook_fallback'
                                        ? '应用机器人主通道 + Webhook 兜底'
                                        : deliveryStrategy === 'app_bot_only'
                                            ? '仅应用机器人'
                                            : deliveryStrategy === 'webhook_only'
                                                ? '仅 Webhook 机器人'
                                                : '未配置'}
                                </span>
                            </div>
                            <div className="mt-2 leading-5">
                                {deliveryStrategySummary}
                            </div>
                        </div>
                        {!chatopsOverview?.callback_url_public && (
                            <div className="mt-2 rounded-xl border border-amber-200 bg-amber-50/80 px-3 py-2 text-xs text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200">
                                当前回调地址还是本地/内网地址，通知平台云端无法直接访问。要做真实双向指令，还需要配置公网域名或隧道地址。
                            </div>
                        )}
                        {chatopsExternalConnectionStale && (
                            <div className="mt-2 rounded-xl border border-amber-200 bg-amber-50/80 px-3 py-2 text-xs text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200">
                                平台历史上曾收到真实通知平台群消息回流{latestExternalSuccessAt ? `（最近一次 ${formatTimestamp(latestExternalSuccessAt)}）` : ''}，但当前公网回探失败，说明现在是公网入口退化，不是平台从未打通过。
                            </div>
                        )}
                    </div>
                    <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                        <div className="rounded-xl bg-white/85 px-3 py-3 dark:bg-slate-900/40">
                            <div className="text-xs text-slate-400">通知平台通道</div>
                            <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{chatopsOverview?.healthy_notification_platform_webhook_count ?? 0}</div>
                        </div>
                        <div className="rounded-xl bg-white/85 px-3 py-3 dark:bg-slate-900/40">
                            <div className="text-xs text-slate-400">验证 Token</div>
                            <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{chatopsOverview?.verification_token_configured ? '已配置' : '未配置'}</div>
                        </div>
                        <div className="rounded-xl bg-white/85 px-3 py-3 dark:bg-slate-900/40">
                            <div className="text-xs text-slate-400">最近事件</div>
                            <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{latestChatopsEvent ? formatTimestamp(latestChatopsEvent.created_at) : '暂无'}</div>
                        </div>
                        <div className="rounded-xl bg-white/85 px-3 py-3 dark:bg-slate-900/40">
                            <div className="text-xs text-slate-400">最近回推</div>
                            <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">
                                {latestChatopsEvent ? `${latestChatopsEvent.delivery_delivered}/${latestChatopsEvent.delivery_configured}` : '暂无'}
                            </div>
                        </div>
                    </div>
                </div>

                <div className="mt-4 grid gap-3 sm:grid-cols-5">
                    <div className="rounded-xl border border-slate-200 bg-white/85 px-4 py-3 dark:border-slate-700 dark:bg-slate-900/40">
                        <div className="text-xs text-slate-400">平台侧就绪</div>
                        <div className={`mt-1 text-sm font-semibold ${chatopsPlatformReady ? 'text-emerald-600 dark:text-emerald-300' : 'text-violet-600 dark:text-violet-300'}`}>
                            {chatopsPlatformReady ? '已就绪' : '待完成'}
                        </div>
                        <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                            Webhook、token 与 challenge 自检全部完成后才会就绪
                        </div>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-white/85 px-4 py-3 dark:border-slate-700 dark:bg-slate-900/40">
                        <div className="text-xs text-slate-400">公网回调入口</div>
                        <div className={`mt-1 text-sm font-semibold ${chatopsExternalCallbackReady ? 'text-emerald-600 dark:text-emerald-300' : 'text-amber-600 dark:text-amber-300'}`}>
                            {chatopsExternalCallbackReady ? '已打通' : '待验证'}
                        </div>
                        <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                            {chatopsExternalConnectionStale
                                ? '历史上曾打通过，但当前 challenge 回探失败，公网入口已退化。'
                                : chatopsOverview?.callback_url_public
                                    ? 'challenge 回探通过后，公网入口才算当前稳定可用。'
                                    : '先把回调地址换成通知平台可访问的公网地址'}
                        </div>
                        <div className="mt-1 text-[11px] text-slate-400 dark:text-slate-500">
                            {chatopsCallbackProviderLabel}{chatopsCallbackProviderHost ? ` · ${chatopsCallbackProviderHost}` : ''}
                        </div>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-white/85 px-4 py-3 dark:border-slate-700 dark:bg-slate-900/40">
                        <div className="text-xs text-slate-400">应用机器人</div>
                        <div className={`mt-1 text-sm font-semibold ${chatopsAppBotConfigured ? 'text-emerald-600 dark:text-emerald-300' : 'text-amber-600 dark:text-amber-300'}`}>
                            {chatopsAppBotConfigured ? '已配置' : '未配置'}
                        </div>
                        <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                            {chatopsAppBotConfigured ? `当前摘要 ${chatopsAppBotIdMasked || '已保存'}` : '仅有自定义 Webhook 机器人时，群成员直接发消息不会回流到平台。'}
                        </div>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-white/85 px-4 py-3 dark:border-slate-700 dark:bg-slate-900/40">
                        <div className="text-xs text-slate-400">公网回探</div>
                        <div className={`mt-1 text-sm font-semibold ${
                            callbackProbe?.success
                                ? 'text-emerald-600 dark:text-emerald-300'
                                : callbackProbe?.attempted
                                    ? 'text-amber-600 dark:text-amber-300'
                                    : 'text-slate-600 dark:text-slate-300'
                        }`}>
                            {callbackProbe?.success ? '已通过' : callbackProbe?.attempted ? '未通过' : '未执行'}
                        </div>
                        <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                            {callbackProbe?.summary || '保存公网地址后，平台会自动做一次 challenge 回探。'}
                        </div>
                        {chatopsCallbackRecommendation && (
                            <div className="mt-1 text-[11px] text-slate-400 dark:text-slate-500">
                                建议：{chatopsCallbackRecommendation}
                            </div>
                        )}
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-white/85 px-4 py-3 dark:border-slate-700 dark:bg-slate-900/40">
                        <div className="text-xs text-slate-400">历史真实回流</div>
                        <div className={`mt-1 text-sm font-semibold ${
                            chatopsExternalConnectedCurrent
                                ? 'text-emerald-600 dark:text-emerald-300'
                                : chatopsExternalConnectionStale
                                    ? 'text-amber-600 dark:text-amber-300'
                                    : 'text-slate-600 dark:text-slate-300'
                        }`}>
                            {chatopsExternalConnectedCurrent ? '当前有效' : chatopsExternalConnectionStale ? '历史曾成功' : chatopsExternalHistoryObserved ? '已观察到' : '未观察到'}
                        </div>
                        <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                            {chatopsExternalHistoryObserved
                                ? `最近一次真实群消息回流 ${latestExternalSuccessAt ? formatTimestamp(latestExternalSuccessAt) : '时间未知'}${chatopsExternalConnectionStale ? '，但当前公网入口已退化。' : '。'}`
                                : '平台还没收到过真实通知平台群消息回流。'}
                        </div>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-white/85 px-4 py-3 dark:border-slate-700 dark:bg-slate-900/40">
                        <div className="text-xs text-slate-400">Token 摘要</div>
                        <div className="mt-1 font-mono text-xs text-slate-700 dark:text-slate-100">
                            {chatopsOverview?.verification_token_masked || '未生成'}
                        </div>
                        <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                            {chatopsOverview?.verification_token_updated_at ? `更新于 ${formatTimestamp(chatopsOverview.verification_token_updated_at)}` : '生成后可复制到通知平台开发者后台'}
                        </div>
                    </div>
                </div>

                <div className="mt-4 rounded-xl border border-slate-200 bg-white/85 px-4 py-4 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
                    <div className="font-medium text-slate-700 dark:text-slate-100">当前项目专属通知平台应用机器人配置</div>
                    <div className="mt-1">
                        自定义 Webhook 机器人只能接收平台主动推送；如果要让群成员直接发“状态 / 报告 / 测试 URL”触发平台，还需要为当前项目单独配置一个专属通知平台应用机器人。
                    </div>
                    <div className="mt-3 grid gap-3 lg:grid-cols-[1fr_1.2fr_auto_auto_auto]">
                        <input
                            value={appBotAppIdInput}
                            onChange={(e) => setAppBotAppIdInput(e.target.value)}
                            placeholder="当前项目专属通知平台 App ID"
                            className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 outline-none focus:border-violet-300 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100"
                        />
                        <input
                            value={appBotSecretInput}
                            onChange={(e) => setAppBotSecretInput(e.target.value)}
                            placeholder="当前项目专属通知平台 App Secret"
                            type="password"
                            className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 outline-none focus:border-violet-300 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100"
                        />
                        <button
                            onClick={() => { void handleConfigureAppBot(); }}
                            disabled={configuringAppBot || !appBotAppIdInput.trim() || !appBotSecretInput.trim()}
                            className="inline-flex items-center justify-center gap-2 rounded-xl bg-violet-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-600 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {configuringAppBot ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                            {configuringAppBot ? '保存中...' : '保存应用机器人'}
                        </button>
                        <button
                            onClick={() => { void handleUnbindAppBot(); }}
                            disabled={unbindingAppBot || !chatopsAppBotConfigured}
                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-medium text-rose-700 transition-colors hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-rose-800/60 dark:bg-rose-500/10 dark:text-rose-200 dark:hover:bg-rose-500/20"
                        >
                            {unbindingAppBot ? <Loader2 className="h-4 w-4 animate-spin" /> : <X className="h-4 w-4" />}
                            {unbindingAppBot ? '解绑中...' : '解绑当前应用机器人'}
                        </button>
                        <button
                            onClick={() => { void handleSelfCheckAppBot(); }}
                            disabled={checkingAppBot || !chatopsAppBotConfigured}
                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100 dark:hover:bg-slate-700"
                        >
                            {checkingAppBot ? <Loader2 className="h-4 w-4 animate-spin" /> : <TestTubes className="h-4 w-4" />}
                            {checkingAppBot ? '校验中...' : '验证应用机器人'}
                        </button>
                    </div>
                    <div className="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-slate-700 dark:bg-slate-800/60 dark:text-slate-100">
                        {chatopsAppBotConfigured
                            ? `当前项目已配置专属应用机器人：${chatopsAppBotIdMasked || '已保存'}`
                            : '当前项目尚未配置专属应用机器人，群成员直接发消息不会自动回流到平台。'}
                    </div>
                    {chatopsAppBotConfigured && (
                        <div className={`mt-3 rounded-xl px-3 py-3 ${
                            chatopsAppBotReady
                                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200'
                                : 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200'
                        }`}>
                            <div className="font-medium">应用机器人凭据校验</div>
                            <div className="mt-1">
                                状态：{chatopsAppBotReady ? '已通过' : '未通过'}
                                {latestAppBotCheck?.created_at ? ` · ${formatTimestamp(latestAppBotCheck.created_at)}` : ''}
                            </div>
                            <div className="mt-1 text-xs opacity-80">
                                {latestAppBotCheck?.message || '保存后平台会尝试获取 tenant_access_token；你也可以手动再验一次。'}
                            </div>
                            {latestAppBotCheck?.status_code ? (
                                <div className="mt-1 text-[11px] opacity-80">
                                    HTTP {latestAppBotCheck.status_code}
                                    {latestAppBotCheck.app_id_masked ? ` · ${latestAppBotCheck.app_id_masked}` : ''}
                                    {latestAppBotCheck.source ? ` · ${latestAppBotCheck.source === 'config_save' ? '保存后自动校验' : '手动校验'}` : ''}
                                </div>
                            ) : (
                                latestAppBotCheck?.app_id_masked ? (
                                    <div className="mt-1 text-[11px] opacity-80">
                                        {latestAppBotCheck.app_id_masked}
                                        {latestAppBotCheck.source ? ` · ${latestAppBotCheck.source === 'config_save' ? '保存后自动校验' : '手动校验'}` : ''}
                                    </div>
                                ) : null
                            )}
                        </div>
                    )}
                    {appBotUnbindResult && (
                        <div className="mt-3 rounded-xl bg-emerald-50 px-3 py-3 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200">
                            <div className="font-medium">已解绑当前项目应用机器人</div>
                            <div className="mt-1">{appBotUnbindResult.message}</div>
                            <div className="mt-1 text-xs opacity-80">
                                已清理：应用校验 {appBotUnbindResult.purged?.checks_removed ?? 0} 条
                                · 会话绑定 {appBotUnbindResult.purged?.bindings_removed ?? 0} 条
                                · 联调事件 {appBotUnbindResult.purged?.events_removed ?? 0} 条
                            </div>
                        </div>
                    )}
                    {appBotConfigResult && (
                        <div className={`mt-3 rounded-xl px-3 py-3 ${
                            appBotConfigResult.validation?.ok
                                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200'
                                : 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200'
                        }`}>
                            <div>已保存应用机器人配置，当前摘要 {appBotConfigResult.app_id_masked || '已保存'}。</div>
                            <div className="mt-1 text-xs opacity-80">
                                {appBotConfigResult.validation?.message || '平台已保存凭据，尚未返回校验结果。'}
                            </div>
                        </div>
                    )}
                    {appBotSelfCheckResult && (
                        <div className={`mt-3 rounded-xl px-3 py-3 ${
                            appBotSelfCheckResult.validation?.ok
                                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200'
                                : 'bg-slate-50 text-slate-700 dark:bg-slate-800/60 dark:text-slate-100'
                        }`}>
                            <div className="font-medium">最近一次手动校验</div>
                            <div className="mt-1">{appBotSelfCheckResult.validation?.message || '已完成应用机器人校验。'}</div>
                            <div className="mt-1 text-xs opacity-80">
                                {appBotSelfCheckResult.validation?.status_code ? `HTTP ${appBotSelfCheckResult.validation.status_code}` : '未返回 HTTP 状态'}
                                {appBotSelfCheckResult.validation?.app_id_masked ? ` · ${appBotSelfCheckResult.validation.app_id_masked}` : ''}
                            </div>
                        </div>
                    )}
                </div>

                <div className="mt-4 rounded-xl border border-slate-200 bg-white/85 px-4 py-4 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
                    <div className="font-medium text-slate-700 dark:text-slate-100">公网回调地址配置</div>
                    <div className="mt-1">
                        这里只填写公网基地址，平台会自动拼接通知平台事件订阅回调路径。
                    </div>
                    <div className="mt-3 flex flex-col gap-3 lg:flex-row">
                        <input
                            value={publicApiBaseUrlInput}
                            onChange={(e) => setPublicApiBaseUrlInput(e.target.value)}
                            placeholder="https://ops.example.com"
                            className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 outline-none focus:border-violet-300 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100"
                        />
                        <button
                            onClick={() => { void handleConfigureCallbackUrl(); }}
                            disabled={configuringCallbackUrl}
                            className="inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-violet-500 dark:hover:bg-violet-600"
                        >
                            {configuringCallbackUrl ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                            {configuringCallbackUrl ? '保存中...' : '保存公网地址'}
                        </button>
                        <button
                            onClick={() => { void handleRefreshProbe(); }}
                            disabled={refreshingProbe}
                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100 dark:hover:bg-slate-700"
                        >
                            {refreshingProbe ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                            {refreshingProbe ? '回探中...' : '立即重试回探'}
                        </button>
                    </div>
                    <div className="mt-2 rounded-lg bg-slate-50 px-3 py-2 font-mono text-[11px] text-slate-700 dark:bg-slate-800/60 dark:text-slate-100">
                        {chatopsOverview?.callback_url || `${publicApiBaseUrlInput || 'https://ops.example.com'}/api/commander/notification_platform/events`}
                    </div>
                    <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-3 dark:border-slate-700 dark:bg-slate-800/40">
                        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                            <div>
                                <div className="font-medium text-slate-700 dark:text-slate-100">本机反向隧道</div>
                                <div className={`mt-1 text-sm font-semibold ${localTunnelStatusClass}`}>
                                    {localTunnelStatusLabel}
                                    {localTunnel?.pid ? ` · PID ${localTunnel.pid}` : ''}
                                </div>
                                <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                                    {localTunnel?.summary || '正在检测本机反向隧道状态...'}
                                </div>
                                {localTunnel?.checked_at ? (
                                    <div className="mt-1 text-[11px] text-slate-400 dark:text-slate-500">
                                        最近检测：{formatTimestamp(localTunnel.checked_at)}
                                    </div>
                                ) : null}
                            </div>
                            <button
                                onClick={() => { void handleRestartLocalTunnel(); }}
                                disabled={restartingLocalTunnel || !localTunnel?.supported || !localTunnel?.script_exists}
                                className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100 dark:hover:bg-slate-700"
                            >
                                {restartingLocalTunnel ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                                {restartingLocalTunnel ? '重启中...' : '重启本机隧道'}
                            </button>
                        </div>
                        {(localTunnel?.stderr_tail || localTunnel?.stdout_tail) ? (
                            <div className="mt-3 rounded-lg bg-white px-3 py-2 text-[11px] text-slate-600 dark:bg-slate-900/40 dark:text-slate-300">
                                <div className="font-medium text-slate-700 dark:text-slate-100">最近日志</div>
                                <div className="mt-1 whitespace-pre-wrap break-all">
                                    {localTunnel.stderr_tail || localTunnel.stdout_tail}
                                </div>
                            </div>
                        ) : null}
                        {localTunnelRestartResult ? (
                            <div className={`mt-3 rounded-lg px-3 py-2 text-xs ${
                                localTunnelRestartResult.ok
                                    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200'
                                    : 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200'
                            }`}>
                                <div className="font-medium">最近一次隧道重启</div>
                                <div className="mt-1">{localTunnelRestartResult.message}</div>
                            </div>
                        ) : null}
                    </div>
                    {callbackProbe?.attempted && (
                        <div className={`mt-3 rounded-xl px-3 py-3 ${
                            callbackProbe.success
                                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200'
                                : 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200'
                        }`}>
                            <div className="font-medium">公网回调回探</div>
                            <div className="mt-1">{callbackProbe.summary}</div>
                            <div className="mt-1 text-xs opacity-80">
                                {callbackProbe.probed_at ? `最近回探：${formatTimestamp(callbackProbe.probed_at)}` : '最近回探时间未知'}
                                {callbackProbe.status_code ? ` · HTTP ${callbackProbe.status_code}` : ''}
                                {callbackProbe.issue ? ` · ${callbackProbe.issue}` : ''}
                            </div>
                            <div className="mt-1 text-xs opacity-80">
                                当前入口：{chatopsCallbackProviderLabel}{chatopsCallbackProviderHost ? ` · ${chatopsCallbackProviderHost}` : ''}
                            </div>
                            {chatopsCallbackRecommendation && (
                                <div className="mt-2 text-xs opacity-90">
                                    建议动作：{chatopsCallbackRecommendation}
                                </div>
                            )}
                        </div>
                    )}
                    {probeRefreshResult && (
                        <div className={`mt-3 rounded-xl px-3 py-3 ${
                            probeRefreshResult.probe?.success
                                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200'
                                : 'bg-slate-50 text-slate-700 dark:bg-slate-800/60 dark:text-slate-100'
                        }`}>
                            <div className="font-medium">最近一次手动重试</div>
                            <div className="mt-1">{probeRefreshResult.probe?.summary || '已完成回探重试。'}</div>
                            <div className="mt-1 text-xs opacity-80">
                                {probeRefreshResult.probe?.probed_at ? `时间：${formatTimestamp(probeRefreshResult.probe.probed_at)}` : '时间未知'}
                                {probeRefreshResult.probe?.status_code ? ` · HTTP ${probeRefreshResult.probe.status_code}` : ''}
                                {probeRefreshResult.probe?.issue ? ` · ${probeRefreshResult.probe.issue}` : ''}
                            </div>
                        </div>
                    )}
                    {callbackConfigResult && (
                        <div className={`mt-3 rounded-xl px-3 py-3 ${
                            callbackConfigResult.status === 'success'
                                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200'
                                : 'bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-200'
                        }`}>
                            {callbackConfigResult.status === 'success'
                                ? `已保存公网基地址，当前回调为 ${callbackConfigResult.callback_url}`
                                : (callbackConfigResult.message || '保存失败')}
                        </div>
                    )}
                    <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-3 dark:border-slate-700 dark:bg-slate-800/40">
                        <div className="flex items-center justify-between gap-3">
                            <div className="font-medium text-slate-700 dark:text-slate-100">最近回探记录</div>
                            <div className="text-[11px] text-slate-500 dark:text-slate-400">
                                {callbackProbeHistory.length ? `最近 ${callbackProbeHistory.length} 次` : '暂无历史'}
                            </div>
                        </div>
                        {callbackProbeHistory.length ? (
                            <div className="mt-3 space-y-2">
                                {callbackProbeHistory.map(item => (
                                    <div
                                        key={item.id}
                                        className={`rounded-lg border px-3 py-3 ${
                                            item.success
                                                ? 'border-emerald-200 bg-emerald-50/80 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-200'
                                                : 'border-slate-200 bg-white text-slate-700 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-100'
                                        }`}
                                    >
                                        <div className="flex flex-wrap items-center gap-2 text-[11px] opacity-80">
                                            <span>{item.created_at ? formatTimestamp(item.created_at) : '时间未知'}</span>
                                            <span>·</span>
                                            <span>{item.success ? '通过' : item.attempted ? '失败' : '未执行'}</span>
                                            <span>·</span>
                                            <span>{item.source === 'manual_refresh' ? '手动重试' : '自动诊断'}</span>
                                            {item.force_refresh && (
                                                <>
                                                    <span>·</span>
                                                    <span>强制刷新</span>
                                                </>
                                            )}
                                            {item.status_code ? (
                                                <>
                                                    <span>·</span>
                                                    <span>HTTP {item.status_code}</span>
                                                </>
                                            ) : null}
                                            {item.issue ? (
                                                <>
                                                    <span>·</span>
                                                    <span>{item.issue}</span>
                                                </>
                                            ) : null}
                                        </div>
                                        <div className="mt-1">{item.summary}</div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                                还没有历史回探记录。保存公网地址后，平台会自动诊断；也可以点上面的“立即重试回探”主动刷新。
                            </div>
                        )}
                    </div>
                </div>

                <div className="mt-4 rounded-xl border border-slate-200 bg-white/85 px-4 py-4 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
                    <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                        <div>
                            <div className="font-medium text-slate-700 dark:text-slate-100">通知平台开发者后台配置清单</div>
                            <div className="mt-1">
                                下面这 5 步全部完成后，群里发“状态 / 报告 mission_id / 测试 URL”才会真正回流到平台。
                            </div>
                        </div>
                        <div className="rounded-lg bg-slate-50 px-3 py-2 text-slate-600 dark:bg-slate-800/60 dark:text-slate-200">
                            {chatopsDirectChatReady ? '端到端联调已完成' : !chatopsAppBotConfigured ? '仍差应用机器人配置' : '仍差通知平台后台最后一步'}
                        </div>
                    </div>
                    <div className="mt-4 grid gap-3 lg:grid-cols-2">
                        {chatopsSetupSteps.map(step => (
                            <div
                                key={step.key}
                                className={`rounded-xl border px-3 py-3 ${
                                    step.done
                                        ? 'border-emerald-200 bg-emerald-50/80 dark:border-emerald-500/20 dark:bg-emerald-500/10'
                                        : 'border-amber-200 bg-amber-50/80 dark:border-amber-500/20 dark:bg-amber-500/10'
                                }`}
                            >
                                <div className="flex items-center gap-2 font-medium">
                                    {step.done ? <Check className="h-4 w-4 text-emerald-600 dark:text-emerald-300" /> : <Copy className="h-4 w-4 text-amber-600 dark:text-amber-300" />}
                                    <span>{step.title}</span>
                                </div>
                                <div className="mt-2 leading-5 opacity-90">{step.detail}</div>
                            </div>
                        ))}
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                        <button
                            onClick={() => { void handleCopy('callback-url', notification_platformCallbackUrl, '回调地址已复制，可直接粘贴到通知平台开发者后台。'); }}
                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100 dark:hover:bg-slate-700"
                        >
                            <Copy className="h-4 w-4" />
                            复制回调地址
                        </button>
                        <button
                            onClick={() => { void handleCopy('setup-guide', chatopsGuideText, '配置清单已复制，可直接发给运维或粘贴到通知平台后台对照。'); }}
                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100 dark:hover:bg-slate-700"
                        >
                            <Copy className="h-4 w-4" />
                            复制配置清单
                        </button>
                        <button
                            onClick={() => { void handleCopy('token', currentTokenValue, '当前会话里的 verification token 已复制。'); }}
                            disabled={!currentTokenValue}
                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100 dark:hover:bg-slate-700"
                        >
                            <Copy className="h-4 w-4" />
                            复制当前 Token
                        </button>
                    </div>
                    {copyFeedback && (
                        <div
                            data-testid="chatops-copy-feedback"
                            className="mt-3 rounded-xl bg-slate-50 px-3 py-3 text-slate-700 dark:bg-slate-800/60 dark:text-slate-100"
                        >
                            {copyFeedback.message}
                        </div>
                    )}
                    {!currentTokenValue && (
                        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 leading-5 dark:border-slate-700 dark:bg-slate-800/60">
                            <div className="font-medium text-slate-700 dark:text-slate-100">Verification Token 当前可见性</div>
                            <div className="mt-1">{currentTokenHint}</div>
                        </div>
                    )}
                </div>

                <div className="mt-4 rounded-xl border border-slate-200 bg-white/85 px-4 py-4 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
                    <div className="flex items-center justify-between gap-3">
                        <div className="font-medium text-slate-700 dark:text-slate-100">最近群聊路由</div>
                        <div className="text-[11px] text-slate-500 dark:text-slate-400">
                            {recentChatBindings.length ? `最近 ${recentChatBindings.length} 个会话` : '暂无会话'}
                        </div>
                    </div>
                    {recentChatBindings.length ? (
                        <div className="mt-3 space-y-2" data-testid="chatops-binding-list">
                            {recentChatBindings.map(item => (
                                <div
                                    key={item.chat_id}
                                    data-testid="chatops-binding-item"
                                    className={`rounded-lg border px-3 py-3 ${
                                        item.last_delivery_ok
                                            ? 'border-emerald-200 bg-emerald-50/80 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-200'
                                            : 'border-slate-200 bg-white text-slate-700 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-100'
                                    }`}
                                >
                                    <div className="flex flex-wrap items-center gap-2 text-[11px] opacity-80">
                                        <span className="font-mono">{item.chat_id || '未知群会话'}</span>
                                        <span>·</span>
                                        <span>{formatBindingSource(item.source)}</span>
                                        <span>·</span>
                                        <span>{formatReplyMode(item.last_reply_mode)}</span>
                                        <span>·</span>
                                        <span>{item.last_delivery_ok ? '最近回推成功' : '最近回推失败'}</span>
                                        <span>·</span>
                                        <span>{item.last_seen_at ? formatTimestamp(item.last_seen_at) : '时间未知'}</span>
                                    </div>
                                    <div className="mt-1">
                                        <span className="font-medium">最近消息：</span>
                                        <span>{item.last_message || '暂无内容'}</span>
                                    </div>
                                    <div className="mt-1 text-[11px] opacity-80">
                                        最近发起人：{item.last_from_user || '未知用户'}
                                    </div>
                                    <div className="mt-1 text-[11px] opacity-80">
                                        绑定状态：{item.binding_status || '未知'} · run_id：{item.last_run_id || '未关联'}
                                    </div>
                                    {item.last_run_id && (
                                        <div className="mt-2">
                                            <a
                                                href={`/legion?tab=control&run=${encodeURIComponent(item.last_run_id)}`}
                                                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-100 dark:hover:bg-slate-800"
                                            >
                                                查看关联命令
                                            </a>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                            还没有最近群聊路由记录。等通知平台真实群消息回流或平台侧模拟执行一次后，这里会显示最近会话到底是走应用机器人回复，还是走 Webhook 兜底。
                        </div>
                    )}
                </div>

                {latestChatopsEvent && (
                    <div className="mt-4 rounded-xl border border-slate-200 bg-white/85 px-4 py-3 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
                        <div className="font-medium text-slate-700 dark:text-slate-100">最近一条指令</div>
                        <div className="mt-2">消息：{latestChatopsEvent.message || '-'}</div>
                        <div className="mt-1">回复：{latestChatopsEvent.response || '-'}</div>
                        <div className="mt-1">状态：{latestChatopsEvent.status} · 回推 {latestChatopsEvent.delivery_delivered}/{latestChatopsEvent.delivery_configured}</div>
                        <div className="mt-1">命令：{latestChatopsEvent.command_id || '-'} · run_id：{latestChatopsEvent.run_id || '未关联'} · 绑定：{latestChatopsEvent.binding_status || '未知'}</div>
                        {latestEventRunHref && (
                            <div className="mt-2">
                                <a
                                    href={latestEventRunHref}
                                    className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100 dark:hover:bg-slate-700"
                                >
                                    打开这条命令的 Legion 详情
                                </a>
                            </div>
                        )}
                        {latestChatopsEvent.status === 'ignored' && latestSuccessfulChatopsEvent && (
                            <div className="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-slate-600 dark:bg-slate-800/60 dark:text-slate-200">
                                最近成功指令：{latestSuccessfulChatopsEvent.message} → {latestSuccessfulChatopsEvent.response}
                            </div>
                        )}
                    </div>
                )}

                <div className="mt-4 rounded-xl border border-slate-200 bg-white/85 px-4 py-4 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div>
                            <div className="font-medium text-slate-700 dark:text-slate-100">事件订阅配置</div>
                            <div className="mt-1">
                                平台现在支持直接生成 verification token，并在本地先做一次 challenge 自检，减少通知平台后台接入前的不确定性。
                            </div>
                        </div>
                        <div className="rounded-lg bg-slate-50 px-3 py-2 text-slate-600 dark:bg-slate-800/60 dark:text-slate-200">
                            {chatopsOverview?.verification_token_configured ? 'Token 已配置' : '还未生成 Token'}
                        </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                        <button
                            onClick={() => { void handleConfigureToken(); }}
                            disabled={configuringToken}
                            className="inline-flex items-center justify-center gap-2 rounded-xl bg-sky-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {configuringToken ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                            {configuringToken ? '生成中...' : (chatopsOverview?.verification_token_configured ? '重新生成 Token' : '生成 Token')}
                        </button>
                        <button
                            onClick={() => { void handleSubscriptionSelfCheck(); }}
                            disabled={selfCheckingSubscription || !chatopsOverview?.verification_token_configured}
                            className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-600 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {selfCheckingSubscription ? <Loader2 className="h-4 w-4 animate-spin" /> : <TestTubes className="h-4 w-4" />}
                            {selfCheckingSubscription ? '验证中...' : '验证回调入口'}
                        </button>
                    </div>
                    {tokenConfigResult && (
                        <div className="mt-3 rounded-xl bg-slate-50 px-3 py-3 text-slate-700 dark:bg-slate-800/60 dark:text-slate-100">
                            <div className="font-medium">最近生成的 verification token</div>
                            <div className="mt-2 break-all rounded-lg bg-white/90 px-3 py-2 font-mono text-xs dark:bg-slate-900/60">
                                {tokenConfigResult.token}
                            </div>
                            <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                                请把这串 token 配到通知平台开发者后台的事件订阅配置里；平台内已同时持久化保存。
                            </div>
                        </div>
                    )}
                    {subscriptionCheckResult && (
                        <div className={`mt-3 rounded-xl px-3 py-3 ${
                            subscriptionCheckResult.status === 'success'
                                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200'
                                : 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200'
                        }`}>
                            <div className="font-medium">平台侧 challenge 自检</div>
                            <div className="mt-2">
                                {subscriptionCheckResult.status === 'success'
                                    ? `验证成功，challenge=${subscriptionCheckResult.result?.challenge || 'codex-self-check'}`
                                    : subscriptionCheckResult.message || '验证未通过'}
                            </div>
                            <div className="mt-1 text-xs opacity-80">
                                {latestSubscriptionCheckEvent
                                    ? `最近一次自检：${formatTimestamp(latestSubscriptionCheckEvent.created_at)}`
                                    : '自检完成后，这里会显示最近验证时间。'}
                            </div>
                        </div>
                    )}
                    {externalCheckResult && (
                        <div className={`mt-3 rounded-xl px-3 py-3 ${
                            externalCheckResult.status === 'success'
                                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200'
                                : 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200'
                        }`}>
                            <div className="font-medium">公网链路自测</div>
                            <div className="mt-2 break-all">
                                地址：{externalCheckResult.callback_url}
                            </div>
                            <div className="mt-1">
                                challenge：{externalCheckResult.challenge_check.ok && externalCheckResult.challenge_check.challenge_matched ? '通过' : '未通过'}
                                {typeof externalCheckResult.challenge_check.status_code === 'number'
                                    ? ` · HTTP ${externalCheckResult.challenge_check.status_code}`
                                    : ''}
                            </div>
                            <div className="mt-1">
                                文本消息：{externalCheckResult.message_check.ok ? '通过' : '未通过'}
                                {typeof externalCheckResult.message_check.status_code === 'number'
                                    ? ` · HTTP ${externalCheckResult.message_check.status_code}`
                                    : ''}
                                {externalCheckResult.message_check.delivery
                                    ? ` · 回推 ${externalCheckResult.message_check.delivery.delivered || 0}/${externalCheckResult.message_check.delivery.configured || 0}`
                                    : ''}
                            </div>
                            {!!externalCheckResult.message_check.command_response && (
                                <div className="mt-1 line-clamp-3">
                                    回复：{externalCheckResult.message_check.command_response}
                                </div>
                            )}
                            {(externalCheckResult.challenge_check.error || externalCheckResult.message_check.error) && (
                                <div className="mt-1 text-xs opacity-80">
                                    {externalCheckResult.challenge_check.error || externalCheckResult.message_check.error}
                                </div>
                            )}
                        </div>
                    )}
                    {!externalCheckResult && latestExternalSelfCheckAt && (
                        <div className={`mt-3 rounded-xl px-3 py-3 ${
                            externalSelfCheckRecentSuccess
                                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200'
                                : 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200'
                        }`}>
                            <div className="font-medium">最近公网链路自测</div>
                            <div className="mt-1">
                                状态：{externalSelfCheckRecentSuccess ? '已通过' : '未通过'}
                                {latestExternalSelfCheckAt ? ` · ${formatTimestamp(latestExternalSelfCheckAt)}` : ''}
                            </div>
                            <div className="mt-1 text-xs opacity-80">
                                这代表平台最近一次从公网入口跑通了 challenge 与文本消息双验证；
                                {chatopsDirectChatReady ? ' 当前真实通知平台群聊也已经联通。' : ' 但这还不等同于真实通知平台群消息已经完成联调。'}
                            </div>
                            {latestExternalSelfCheckEvent?.response && (
                                <div className="mt-1 line-clamp-3 text-xs opacity-80">
                                    最近回复：{latestExternalSelfCheckEvent.response}
                                </div>
                            )}
                        </div>
                    )}
                </div>

                <div className="mt-4 rounded-xl border border-slate-200 bg-white/85 px-4 py-4 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                        <div className="flex-1">
                            <div className="font-medium text-slate-700 dark:text-slate-100">平台侧自检</div>
                            <div className="mt-1">
                                不进入通知平台开发者后台，也可以先在平台内模拟一条通知平台文本指令，验证“收消息 → 解析 → 回推”链路。
                            </div>
                        </div>
                        <div className="rounded-lg bg-slate-50 px-3 py-2 text-slate-600 dark:bg-slate-800/60 dark:text-slate-200">
                            {chatopsDirectChatReady
                                ? '双向链路已就绪'
                                : !chatopsOverview?.callback_url_public
                                    ? '当前还是本地回调地址'
                                : !chatopsAppBotConfigured
                                    ? '还缺通知平台应用机器人'
                                : chatopsPlatformReady
                                    ? '平台侧已就绪，待通知平台侧发一条真实群消息'
                                    : chatopsWebhookReady
                                        ? '还缺 token 或 challenge 自检'
                                        : '还缺健康的通知平台回推通道'}
                        </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                        {['状态', '报告 125c69cd', '测试 https://example.com'].map(command => (
                            <button
                                key={command}
                                onClick={() => {
                                    setSimulateMessage(command);
                                    void handleSimulate(command);
                                }}
                                disabled={simulating}
                                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-600 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-200 dark:hover:bg-slate-700"
                            >
                                {command}
                            </button>
                        ))}
                    </div>
                    <div className="mt-3 flex flex-col gap-3 lg:flex-row">
                        <input
                            value={simulateMessage}
                            onChange={e => setSimulateMessage(e.target.value)}
                            placeholder="输入要模拟的通知平台文本指令，例如：状态"
                            className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 outline-none focus:border-violet-300 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100"
                        />
                        <button
                            onClick={() => { void handleSimulate(); }}
                            disabled={simulating || !simulateMessage.trim()}
                            className="inline-flex items-center justify-center gap-2 rounded-xl bg-violet-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-600 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {simulating ? <Loader2 className="h-4 w-4 animate-spin" /> : <TestTubes className="h-4 w-4" />}
                            {simulating ? '模拟中...' : '模拟通知平台指令'}
                        </button>
                        <button
                            onClick={() => { void handleExternalSelfCheck(); }}
                            disabled={externallyChecking || !chatopsOverview?.callback_url_public || !chatopsOverview?.verification_token_configured}
                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-700 transition-colors hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200 dark:hover:bg-emerald-500/20"
                        >
                            {externallyChecking ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                            {externallyChecking ? '公网自测中...' : '跑公网链路自测'}
                        </button>
                    </div>
                    {simulateResult && (
                        <div className="mt-3 rounded-xl bg-slate-50 px-3 py-3 text-slate-700 dark:bg-slate-800/60 dark:text-slate-100">
                            <div className="font-medium">最近一次模拟</div>
                            <div className="mt-2">回复：{simulateResult.result.response || '-'}</div>
                            <div className="mt-1">
                                回推：{simulateResult.delivery.delivered}/{simulateResult.delivery.configured}
                                {simulateResult.delivery.message ? ` · ${simulateResult.delivery.message}` : ''}
                            </div>
                            <div className="mt-1">当前状态：{simulateResult.overview.summary}</div>
                            {simulateRunId && (
                                <div className="mt-1">关联 run_id：{simulateRunId}</div>
                            )}
                            <div className="mt-3 flex flex-wrap gap-2">
                                <a
                                    href={legionControlHref}
                                    className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-100 dark:hover:bg-slate-800"
                                >
                                    去 Legion 控制中心
                                </a>
                                {simulateRunHref && (
                                    <a
                                        href={simulateRunHref}
                                        className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-100 dark:hover:bg-slate-800"
                                    >
                                        打开关联命令
                                    </a>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Webhook List */}
            <div className="bg-white/80 dark:bg-slate-800/60 rounded-2xl border border-slate-200/60 dark:border-slate-700/60 backdrop-blur-sm overflow-hidden card-hover-lift">
                {webhooks.length === 0 ? (
                    <div className="py-20 text-center">
                        <Bell className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
                        <p className="text-slate-400 text-sm">暂无通知配置</p>
                        <p className="text-slate-400 text-xs mt-1">添加 Webhook 后测试完成会自动发送通知</p>
                    </div>
                ) : (
                    <div className="divide-y divide-slate-100 dark:divide-slate-700/50">
                        {webhooks.map(wh => (
                            <div key={wh.id} className="flex items-center gap-4 px-5 py-4 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
                                <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0
                                    ${wh.type === 'dingtalk' ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-500'
                                        : wh.type === 'wecom' ? 'bg-green-50 dark:bg-green-500/10 text-green-500'
                                            : wh.type === 'notification_platform' ? 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-500'
                                                : 'bg-slate-100 dark:bg-slate-700 text-slate-500'}`}>
                                    <Bell className="w-5 h-5" />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium text-slate-700 dark:text-slate-200">{wh.name}</p>
                                    <div className="flex gap-2 mt-0.5 text-xs text-slate-400">
                                        <span className="px-1.5 py-0.5 bg-slate-100 dark:bg-slate-700 rounded text-slate-500">{TYPE_LABELS[wh.type] || wh.type}</span>
                                        <span className="truncate max-w-[240px] font-mono">{wh.url}</span>
                                    </div>
                                    <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
                                        <span className={`rounded-full px-2 py-0.5 ${
                                            wh.enabled
                                                ? 'bg-sky-50 text-sky-600 dark:bg-sky-500/15 dark:text-sky-300'
                                                : 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-300'
                                        }`}>
                                            {wh.enabled ? '已启用' : '已停用'}
                                        </span>
                                        <span className={`rounded-full px-2 py-0.5 ${
                                            wh.last_test_at
                                                ? wh.last_test_success
                                                    ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300'
                                                    : 'bg-rose-50 text-rose-600 dark:bg-rose-500/15 dark:text-rose-300'
                                                : 'bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-300'
                                        }`}>
                                            {!wh.last_test_at ? '未测试' : wh.last_test_success ? '最近测试通过' : '最近测试失败'}
                                        </span>
                                        <span>{formatTimestamp(wh.last_test_at)}</span>
                                        {!!wh.last_test_message && <span className="truncate max-w-[320px]">{wh.last_test_message}</span>}
                                    </div>
                                </div>

                                {testResult?.id === wh.id && (
                                    <span className={`text-xs px-2 py-1 rounded-lg ${testResult.ok ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-600'}`}>
                                        {testResult.ok ? <CheckCircle2 className="w-3 h-3 inline mr-1" /> : <XCircle className="w-3 h-3 inline mr-1" />}
                                        {testResult.msg}
                                    </span>
                                )}

                                <div className="flex gap-1 shrink-0">
                                    <button
                                        onClick={() => { void handleToggleEnabled(wh); }}
                                        disabled={toggling === wh.id}
                                        className="rounded-lg px-2.5 py-2 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-700 dark:hover:text-slate-200 transition-colors disabled:opacity-60"
                                        title={wh.enabled ? '停用' : '启用'}
                                    >
                                        {toggling === wh.id ? '处理中...' : wh.enabled ? '停用' : '启用'}
                                    </button>
                                    <button onClick={() => handleTest(wh.id)} disabled={testing === wh.id}
                                        className="p-2 rounded-lg text-slate-400 hover:text-indigo-500 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 transition-colors" title="测试">
                                        {testing === wh.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <TestTubes className="w-4 h-4" />}
                                    </button>
                                    <button onClick={() => handleDelete(wh.id)}
                                        className="p-2 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors" title="删除">
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Add Modal */}
            {showAdd && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md animate-in fade-in duration-300">
                    <div className="bg-white/95 dark:bg-slate-800/95 backdrop-blur-xl rounded-2xl shadow-2xl shadow-black/20 dark:shadow-black/50 border border-slate-200/80 dark:border-slate-700/80 w-full max-w-md p-6 relative animate-in zoom-in-95 duration-300">
                        <button onClick={() => setShowAdd(false)} className="absolute top-4 right-4 text-slate-400 hover:text-slate-600">
                            <X className="w-5 h-5" />
                        </button>
                        <h3 className="text-lg font-bold text-slate-800 dark:text-white mb-4 flex items-center gap-2">
                            <Bell className="w-5 h-5 text-pink-500" /> 添加 Webhook
                        </h3>
                        <div className="space-y-3">
                            <div>
                                <label className="text-xs font-medium text-slate-500">名称</label>
                                <input type="text" value={name} onChange={e => setName(e.target.value)}
                                    placeholder="如：钉钉测试群" className="w-full mt-1 px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600 text-sm outline-none" />
                            </div>
                            <div>
                                <label className="text-xs font-medium text-slate-500">类型</label>
                                <select value={type} onChange={e => setType(e.target.value)}
                                    className="w-full mt-1 px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600 text-sm outline-none">
                                    <option value="dingtalk">钉钉</option>
                                    <option value="wecom">企业微信</option>
                                    <option value="notification_platform">通知平台</option>
                                    <option value="custom">自定义</option>
                                </select>
                            </div>
                            <div>
                                <label className="text-xs font-medium text-slate-500">Webhook URL</label>
                                <input type="text" value={url} onChange={e => setUrl(e.target.value)}
                                    placeholder={typePlaceholder}
                                    className="w-full mt-1 px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600 text-sm font-mono outline-none" />
                            </div>
                            <label className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-700/40 dark:text-slate-200">
                                <span>添加后立即启用</span>
                                <input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />
                            </label>
                            <label className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-700/40 dark:text-slate-200">
                                <span>添加后立即测试</span>
                                <input
                                    type="checkbox"
                                    checked={testAfterCreate}
                                    disabled={!enabled}
                                    onChange={e => setTestAfterCreate(e.target.checked)}
                                />
                            </label>
                            <button onClick={handleAdd} disabled={!name.trim() || !url.trim()}
                                className="w-full mt-2 px-4 py-2.5 bg-gradient-to-r from-pink-500 to-rose-500 text-white rounded-xl text-sm font-medium disabled:opacity-50 transition-all">
                                {enabled && testAfterCreate ? '添加并测试' : '添加'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
