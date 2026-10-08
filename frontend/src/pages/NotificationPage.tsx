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
    dingtalk: "DingTalk",
    wecom: "WeCom",
    notification_platform: "Notification platform",
    custom: "Custom",
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
    const [simulateMessage, setSimulateMessage] = useState("Status");
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
                    msg: data.success ? (data.message || "Sent successfully") : (data.error || data.message || `HTTP ${data.status_code}`),
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
            setTestResult({ id, ok: data.success, msg: data.success ? (data.message || "Sent successfully") : (data.error || data.message || `HTTP ${data.status_code}`) });
            await load();
        } catch (e) {
            setTestResult({ id, ok: false, msg: "Request failed" });
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
            setCopyFeedback({ key, message: "Copy failed. Check browser clipboard permissions." });
        }
    }, []);

    const formatTimestamp = (value?: string) => {
        if (!value) return "Not tested";
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return `${date.getMonth() + 1}/${date.getDate()} ${date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false,
        })}`;
    };

    const formatReplyMode = (value?: string) => {
        switch (value) {
            case 'app_bot':
                return "App bot";
            case 'app_bot_fallback_webhook':
                return "App bot failed; webhook fallback used";
            case 'webhook_only':
                return "Webhook bot";
            default:
                return value || "Unknown";
        }
    };

    const formatBindingSource = (value?: string) => {
        switch (value) {
            case 'event_subscription':
                return "Notification platform event subscription";
            case 'simulate':
                return "Platform simulation";
            case 'external_self_check':
                return "Public endpoint self-test";
            default:
                return value || "Unknown source";
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
            ? "Use the same project-specific notification app bot for commands and replies. Keep webhooks as a notification fallback."
            : "Notifications still rely mainly on a webhook bot; a unified external bot experience is not yet in place."
    );
    const chatopsCallbackProviderLabel = chatopsOverview?.callback_provider?.label || (chatopsOverview?.callback_url_public ? "Custom public URL" : "Local URL");
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
        ? "Direct messages available"
        : chatopsDirectChatDegraded
            ? "Previously connected"
            : "Direct message connection pending";
    const directChatStatusClass = chatopsDirectChatReady
        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
        : chatopsDirectChatDegraded
            ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
            : chatopsPlatformReady
                ? 'bg-cyan-100 text-cyan-700 dark:bg-cyan-500/15 dark:text-cyan-300'
                : 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300';
    const directChatDescription = chatopsDirectChatDegraded
        ? `Send commands in a direct message and receive immediate replies. The most recent real direct message succeeded${latestExternalSuccessAt ? ` (${formatTimestamp(latestExternalSuccessAt)})` : ''}, but the public endpoint is currently degraded. Direct messaging can resume after it is restored.`
        : "Send commands in a direct message and receive immediate replies. Recommended commands: status, report, and test.";
    const commandEntryLabel = chatopsDirectChatReady
        ? "Direct message the AI Test Platform bot"
        : chatopsDirectChatDegraded
            ? "Direct messaging worked previously; the public endpoint is currently degraded"
            : "Complete app bot integration testing first";
    const unifiedRobotBadgeLabel = unifiedRobotReady
        ? "Unified bot ready"
        : chatopsDirectChatDegraded
            ? "Unified bot endpoint degraded"
            : unifiedRobotPlatformReady
                ? "Unified bot awaiting group test"
                : "Unified bot setup in progress";
    const unifiedRobotBadgeClass = unifiedRobotReady
        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
        : chatopsDirectChatDegraded
            ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
            : unifiedRobotPlatformReady
                ? 'bg-cyan-100 text-cyan-700 dark:bg-cyan-500/15 dark:text-cyan-300'
                : 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300';
    const chatopsCurrentStatusLabel = chatopsDirectChatReady
        ? "Ready to use now"
        : chatopsDirectChatDegraded
            ? "Previously available; endpoint restoration required"
            : chatopsPlatformReady
                ? "Platform ready; final integration testing pending"
                : "Platform setup in progress";
    const chatopsCurrentStatusClass = chatopsDirectChatReady
        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
        : chatopsDirectChatDegraded
            ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
            : chatopsPlatformReady
                ? 'bg-cyan-100 text-cyan-700 dark:bg-cyan-500/15 dark:text-cyan-300'
                : 'bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300';
    const chatopsLatestVerifiedAt = latestExternalSuccessAt || latestExternalSelfCheckAt || latestSuccessfulChatopsEvent?.created_at || '';
    const chatopsLatestVerifiedLabel = latestExternalSuccessAt
        ? "Latest actual inbound notification event"
        : latestExternalSelfCheckAt
            ? "Latest public connection self-test"
            : latestSuccessfulChatopsEvent?.created_at
                ? "Latest successful platform event"
                : "Not verified yet";
    const chatopsCurrentStatusDescription = chatopsDirectChatReady
        ? `Direct message the AI Test Platform bot. Latest real inbound notification event${chatopsLatestVerifiedAt ? `At ${formatTimestamp(chatopsLatestVerifiedAt)}` : "Verified"}; you can continue sending status, report, and test commands.`
        : chatopsDirectChatDegraded
            ? `Real inbound notification events were received previously${chatopsLatestVerifiedAt ? ` (latest ${formatTimestamp(chatopsLatestVerifiedAt)})` : ''}, but the public endpoint is currently degraded. Retry the probe or run a public connection self-test before resuming direct messages.`
            : chatopsPlatformReady
                ? "The platform and app bot are ready. Complete public callback integration testing and verify one real message next."
                : "Basic configuration for two-way notification commands is still incomplete. Configure the token, app bot, or public callback first.";
    const chatopsOverviewCards = [
        {
            key: 'status',
            title: "Current status",
            value: chatopsCurrentStatusLabel,
            detail: chatopsDirectChatReady
                ? "Direct messaging available"
                : chatopsDirectChatDegraded
                    ? "Restore the public endpoint first"
                    : "Further integration testing required",
        },
        {
            key: 'entry',
            title: "Current command entry point",
            value: commandEntryLabel,
            detail: "Send status, report, and test commands here",
        },
        {
            key: 'verified',
            title: chatopsLatestVerifiedLabel,
            value: chatopsLatestVerifiedAt ? formatTimestamp(chatopsLatestVerifiedAt) : "None",
            detail: chatopsLatestVerifiedAt ? "Most recent successful verification time" : "No successful records yet",
        },
        {
            key: 'notify',
            title: "Team notification entry point",
            value: "Testing platform group",
            detail: "The group continues to receive results and alerts",
        },
    ];
    const localTunnelStatusLabel = !localTunnel?.supported
        ? "Unsupported in this environment"
        : !localTunnel?.script_exists
            ? "Script missing"
            : localTunnel?.running
                ? "Running"
                : "Not running";
    const localTunnelStatusClass = !localTunnel?.supported
        ? 'text-slate-600 dark:text-slate-300'
        : localTunnel?.running
            ? 'text-emerald-600 dark:text-emerald-300'
            : 'text-amber-600 dark:text-amber-300';
    const currentTokenValue = tokenConfigResult?.token || '';
    const currentTokenHint = currentTokenValue
        ? currentTokenValue
        : chatopsOverview?.verification_token_configured
            ? `This page does not cache the plaintext token. Click "${chatopsOverview.verification_token_configured ? "Regenerate token" : "Generate token"}" before copying. Current fingerprint: ${chatopsOverview?.verification_token_masked || "Not generated"}`
            : "No verification token has been generated yet.";
    const notification_platformRoleCards = [
        {
            key: 'group-notify',
            title: "Testing platform group",
            status: productionReady ? "Notifications available" : "Notification setup incomplete",
            statusClass: productionReady
                ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
                : 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
            flow: "Platform → group",
            description: "The team receives test results, report reminders, agent fleet status, and platform alerts here. This entry point does not parse commands.",
            hints: [
                "Suitable for sharing results with the team",
                "Keep the webhook as a stable notification channel",
            ],
        },
        {
            key: 'bot-command',
            title: "AI Test Platform bot",
            status: directChatStatusLabel,
            statusClass: directChatStatusClass,
            flow: "You → platform → you",
            description: directChatDescription,
            hints: [
                "Status",
                "report <task ID>",
                "test <URL>",
            ],
        },
    ];
    const chatopsGuideText = [
        "Notification platform event subscription checklist",
        `1. Event callback URL: ${notification_platformCallbackUrl}`,
        `2. Verification Token: ${currentTokenValue || currentTokenHint}`,
        `3. Project-specific notification app bot: ${chatopsAppBotConfigured ? `Configured ${chatopsAppBotIdMasked || ''}` : "Not configured. Add the app ID and secret in the platform."}`,
        `4. Current public endpoint: ${chatopsCallbackProviderLabel}${chatopsCallbackProviderHost ? ` (${chatopsCallbackProviderHost})` : ''}`,
        `5. Public callback probe: ${callbackProbe?.summary || "No probe has run yet. The platform runs diagnostics automatically after you save a public URL."}`,
        `6. Recommended action: ${chatopsCallbackRecommendation || "Make sure the public callback challenge probe succeeds before testing integration in the notification platform console."}`,
        "7. Enable event subscriptions in the notification platform developer console and subscribe to message-received events.",
        "8. Add this project's notification app bot to the target group. Save the configuration, then send a text message such as status in the group.",
        "9. If inbound notification events remain unverified, follow the public callback probe guidance to fix the external endpoint first.",
    ].join('\n');
    const chatopsSetupSteps = [
        {
            key: 'unified-robot',
            title: "Unified bot mode",
            done: unifiedRobotTarget,
            detail: unifiedRobotTarget
                ? unifiedRobotReady
                    ? "The app bot, callback, and real group messaging are connected. You can use this single bot externally."
                    : unifiedRobotPlatformReady
                        ? "The app bot and public callback are ready. Keep the webhook as a fallback and run a real group message test to finish."
                        : deliveryStrategySummary
                : "Notifications still rely mainly on a custom webhook bot; a unified external bot experience is not yet in place.",
        },
        {
            key: 'public-url',
            title: "Public callback URL",
            done: !!chatopsOverview?.callback_url_public,
            detail: chatopsOverview?.callback_url_public
                ? "A public base URL is configured, allowing the notification platform to reach the callback endpoint."
                : "The URL is still local or private. Save a public base URL or tunnel URL first.",
        },
        {
            key: 'callback-probe',
            title: "Public callback probe",
            done: !!callbackProbe?.success,
            detail: !chatopsOverview?.callback_url_public
                ? "The URL is still local or private, so the platform does not run a public probe yet."
                : callbackProbe?.summary || "Saving a public URL automatically triggers a challenge probe.",
        },
        {
            key: 'verification-token',
            title: 'Verification Token',
            done: !!chatopsOverview?.verification_token_configured,
            detail: chatopsOverview?.verification_token_configured
                ? `Configured; current fingerprint ${chatopsOverview?.verification_token_masked || "Generated"}.`
                : "No verification token has been generated in the platform.",
        },
        {
            key: 'app-bot',
            title: "Notification app bot",
            done: chatopsAppBotConfigured,
            detail: chatopsAppBotConfigured
                ? `App bot configured; current fingerprint ${chatopsAppBotIdMasked || "Saved"}.`
                : "The group currently has only a custom webhook bot. Add an app ID and secret here to route members' messages back to the platform.",
        },
        {
            key: 'subscription-self-check',
            title: "Platform self-check",
            done: !!chatopsOverview?.subscription_endpoint_verified,
            detail: chatopsOverview?.subscription_endpoint_verified
                ? "The challenge self-check passed; the platform callback endpoint format is correct."
                : "Run Verify callback endpoint first to confirm the challenge is returned correctly.",
        },
        {
            key: 'external-self-check',
            title: "Public connection self-test",
            done: externalSelfCheckRecentSuccess,
            detail: !chatopsOverview?.callback_url_public
                ? "Configure a public callback URL before the platform can verify challenges and text messages through the external endpoint."
                : externalSelfCheckRecentSuccess
                    ? `The latest public endpoint self-test passed${latestExternalSelfCheckAt ? ` (${formatTimestamp(latestExternalSelfCheckAt)})` : ''}.`
                    : "Run a public connection self-test to confirm that challenges and text messages reach the platform through the public endpoint.",
        },
        {
            key: 'notification_platform-console',
            title: "Notification platform integration testing",
            done: chatopsDirectChatReady,
            detail: chatopsDirectChatReady
                ? "A real inbound text message was recently received from the notification platform."
                : chatopsExternalConnectionStale
                    ? "Real group messages were received previously, but the public endpoint is now degraded. Fix it before further integration testing."
                : !chatopsAppBotConfigured
                    ? "Configure the notification app bot first, then finish event subscriptions and group testing in the notification platform console."
                    : "Complete event subscriptions in the notification platform developer console and send a real group message for final verification.",
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
                        Notification settings
                    </h2>
                    <p className="text-slate-500 mt-2 text-sm">Automatically notify DingTalk, WeCom, or the notification platform when tests finish</p>
                </div>
                <div className="flex gap-2">
                    <a
                        href={legionControlHref}
                        className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 text-white rounded-xl text-sm font-medium transition-all hover:bg-slate-700 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                    >
                        Open Legion control center
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
                        {drilling ? "Running drill..." : "Test enabled channels"}
                    </button>
                    <button onClick={() => setShowAdd(true)}
                        className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-pink-500 to-rose-500 text-white rounded-xl text-sm font-medium shadow-lg shadow-pink-500/25 transition-all hover:shadow-xl">
                        <Plus className="w-4 h-4" /> Add webhook
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
                                {productionReady ? "Production alert delivery connected" : "Production alerts not ready"}
                            </span>
                        </div>
                        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
                            {overview?.summary || "Loading notification configuration overview..."}
                        </p>
                    </div>
                    <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                        <div className="rounded-xl bg-white/85 px-3 py-3 dark:bg-slate-900/40">
                            <div className="text-xs text-slate-400">Total</div>
                            <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{overview?.total ?? 0}</div>
                        </div>
                        <div className="rounded-xl bg-white/85 px-3 py-3 dark:bg-slate-900/40">
                            <div className="text-xs text-slate-400">Enabled</div>
                            <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{overview?.enabled ?? 0}</div>
                        </div>
                        <div className="rounded-xl bg-white/85 px-3 py-3 dark:bg-slate-900/40">
                            <div className="text-xs text-slate-400">Verified</div>
                            <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{overview?.healthy_enabled ?? 0}</div>
                        </div>
                        <div className="rounded-xl bg-white/85 px-3 py-3 dark:bg-slate-900/40">
                            <div className="text-xs text-slate-400">Not tested</div>
                            <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{overview?.untested_enabled ?? 0}</div>
                        </div>
                    </div>
                </div>
                {!productionReady && (
                    <div className="mt-3 rounded-xl border border-amber-200 bg-white/85 px-4 py-3 text-sm text-slate-700 dark:border-amber-500/20 dark:bg-slate-900/40 dark:text-slate-200">
                        Add one webhook reachable from production and send a test notification. Confirm an HTTP 200 response before relying on maintenance failure and risk alerts.
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
                <div className="font-semibold text-sky-700 dark:text-sky-300">Notification platform setup</div>
                <div className="mt-2 space-y-2">
                    <p>A custom webhook bot only receives platform notifications; it cannot listen to group members. Messages such as "hello" or "help me deploy" in the group will not receive automatic replies.</p>
                    <p>To run platform commands from a notification group and receive replies, configure event subscriptions in the notification platform developer console and set the message callback URL to:</p>
                    <div className="rounded-xl bg-white/90 px-3 py-2 font-mono text-xs text-slate-700 dark:bg-slate-900/40 dark:text-slate-100">
                        {notification_platformCallbackUrl}
                    </div>
                    <p>The platform supports this endpoint and text commands including `status`, `report mission_id`, and `test https://example.com`.</p>
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
                        <div className="font-semibold text-slate-800 dark:text-slate-100">Current notification platform usage</div>
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
                        <div className="font-semibold text-slate-800 dark:text-slate-100">Notification entry point roles</div>
                        <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                            Use one group for notifications and one bot for commands. The current external bot policy is {deliveryStrategySummary}
                        </div>
                    </div>
                    <div className="rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:bg-slate-900/40 dark:text-slate-300">
                        Current command entry point: {commandEntryLabel}
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
                            <div className="mt-2 text-xs text-slate-400">Connection: {card.flow}</div>
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
                            Two-way notification commands
                        </div>
                        <div className="mt-2 text-slate-600 dark:text-slate-300">
                            {chatopsOverview?.summary || "Loading two-way command status..."}
                        </div>
                        <div className="mt-3 rounded-xl bg-white/90 px-3 py-2 font-mono text-xs text-slate-700 dark:bg-slate-900/40 dark:text-slate-100">
                            {notification_platformCallbackUrl}
                        </div>
                        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-3 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-200">
                            <div className="flex flex-wrap items-center gap-2">
                                <span className="font-semibold">External bot configuration</span>
                                <span className={`rounded-full px-2 py-0.5 ${unifiedRobotBadgeClass}`}>
                                    {unifiedRobotBadgeLabel}
                                </span>
                                <span className="rounded-full bg-slate-200 px-2 py-0.5 text-slate-700 dark:bg-slate-700 dark:text-slate-200">
                                    {deliveryStrategy === 'single_robot_with_webhook_fallback'
                                        ? "App bot primary channel with webhook fallback"
                                        : deliveryStrategy === 'app_bot_only'
                                            ? "App bot only"
                                            : deliveryStrategy === 'webhook_only'
                                                ? "Webhook bot only"
                                                : "Not configured"}
                                </span>
                            </div>
                            <div className="mt-2 leading-5">
                                {deliveryStrategySummary}
                            </div>
                        </div>
                        {!chatopsOverview?.callback_url_public && (
                            <div className="mt-2 rounded-xl border border-amber-200 bg-amber-50/80 px-3 py-2 text-xs text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200">
                                The callback URL is still local or private and cannot be reached by the notification platform. Configure a public domain or tunnel URL for real two-way commands.
                            </div>
                        )}
                        {chatopsExternalConnectionStale && (
                            <div className="mt-2 rounded-xl border border-amber-200 bg-amber-50/80 px-3 py-2 text-xs text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200">
                                Real notification group messages were received previously {latestExternalSuccessAt ? ` (latest ${formatTimestamp(latestExternalSuccessAt)})` : ''} , but the public probe now fails. The public endpoint has degraded after a successful connection.
                            </div>
                        )}
                    </div>
                    <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                        <div className="rounded-xl bg-white/85 px-3 py-3 dark:bg-slate-900/40">
                            <div className="text-xs text-slate-400">Notification platform channel</div>
                            <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{chatopsOverview?.healthy_notification_platform_webhook_count ?? 0}</div>
                        </div>
                        <div className="rounded-xl bg-white/85 px-3 py-3 dark:bg-slate-900/40">
                            <div className="text-xs text-slate-400">Verification token</div>
                            <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{chatopsOverview?.verification_token_configured ? "Configured" : "Not configured"}</div>
                        </div>
                        <div className="rounded-xl bg-white/85 px-3 py-3 dark:bg-slate-900/40">
                            <div className="text-xs text-slate-400">Latest event</div>
                            <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{latestChatopsEvent ? formatTimestamp(latestChatopsEvent.created_at) : "None"}</div>
                        </div>
                        <div className="rounded-xl bg-white/85 px-3 py-3 dark:bg-slate-900/40">
                            <div className="text-xs text-slate-400">Latest reply delivery</div>
                            <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">
                                {latestChatopsEvent ? `${latestChatopsEvent.delivery_delivered}/${latestChatopsEvent.delivery_configured}` : "None"}
                            </div>
                        </div>
                    </div>
                </div>

                <div className="mt-4 grid gap-3 sm:grid-cols-5">
                    <div className="rounded-xl border border-slate-200 bg-white/85 px-4 py-3 dark:border-slate-700 dark:bg-slate-900/40">
                        <div className="text-xs text-slate-400">Platform readiness</div>
                        <div className={`mt-1 text-sm font-semibold ${chatopsPlatformReady ? 'text-emerald-600 dark:text-emerald-300' : 'text-violet-600 dark:text-violet-300'}`}>
                            {chatopsPlatformReady ? "Ready" : "Pending"}
                        </div>
                        <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                            Ready only after the webhook, token, and challenge self-check are all configured
                        </div>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-white/85 px-4 py-3 dark:border-slate-700 dark:bg-slate-900/40">
                        <div className="text-xs text-slate-400">Public callback endpoint</div>
                        <div className={`mt-1 text-sm font-semibold ${chatopsExternalCallbackReady ? 'text-emerald-600 dark:text-emerald-300' : 'text-amber-600 dark:text-amber-300'}`}>
                            {chatopsExternalCallbackReady ? "Connected" : "Pending verification"}
                        </div>
                        <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                            {chatopsExternalConnectionStale
                                ? "The connection worked previously, but the challenge probe now fails and the public endpoint has degraded."
                                : chatopsOverview?.callback_url_public
                                    ? "The public endpoint is considered currently available only after the challenge probe passes."
                                    : "Set a public callback URL that the notification platform can reach first"}
                        </div>
                        <div className="mt-1 text-[11px] text-slate-400 dark:text-slate-500">
                            {chatopsCallbackProviderLabel}{chatopsCallbackProviderHost ? ` · ${chatopsCallbackProviderHost}` : ''}
                        </div>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-white/85 px-4 py-3 dark:border-slate-700 dark:bg-slate-900/40">
                        <div className="text-xs text-slate-400">App bot</div>
                        <div className={`mt-1 text-sm font-semibold ${chatopsAppBotConfigured ? 'text-emerald-600 dark:text-emerald-300' : 'text-amber-600 dark:text-amber-300'}`}>
                            {chatopsAppBotConfigured ? "Configured" : "Not configured"}
                        </div>
                        <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                            {chatopsAppBotConfigured ? `Current fingerprint ${chatopsAppBotIdMasked || "Saved"}` : "With only a custom webhook bot, group members' messages do not reach the platform."}
                        </div>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-white/85 px-4 py-3 dark:border-slate-700 dark:bg-slate-900/40">
                        <div className="text-xs text-slate-400">Public endpoint probe</div>
                        <div className={`mt-1 text-sm font-semibold ${
                            callbackProbe?.success
                                ? 'text-emerald-600 dark:text-emerald-300'
                                : callbackProbe?.attempted
                                    ? 'text-amber-600 dark:text-amber-300'
                                    : 'text-slate-600 dark:text-slate-300'
                        }`}>
                            {callbackProbe?.success ? "Passed" : callbackProbe?.attempted ? "Failed" : "Not run"}
                        </div>
                        <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                            {callbackProbe?.summary || "Saving a public URL automatically triggers a challenge probe."}
                        </div>
                        {chatopsCallbackRecommendation && (
                            <div className="mt-1 text-[11px] text-slate-400 dark:text-slate-500">
                                Suggestion: {chatopsCallbackRecommendation}
                            </div>
                        )}
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-white/85 px-4 py-3 dark:border-slate-700 dark:bg-slate-900/40">
                        <div className="text-xs text-slate-400">Historical real inbound events</div>
                        <div className={`mt-1 text-sm font-semibold ${
                            chatopsExternalConnectedCurrent
                                ? 'text-emerald-600 dark:text-emerald-300'
                                : chatopsExternalConnectionStale
                                    ? 'text-amber-600 dark:text-amber-300'
                                    : 'text-slate-600 dark:text-slate-300'
                        }`}>
                            {chatopsExternalConnectedCurrent ? "Currently valid" : chatopsExternalConnectionStale ? "Previously successful" : chatopsExternalHistoryObserved ? "Observed" : "Not observed"}
                        </div>
                        <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                            {chatopsExternalHistoryObserved
                                ? `Latest real inbound group message ${latestExternalSuccessAt ? formatTimestamp(latestExternalSuccessAt) : "Unknown time"}${chatopsExternalConnectionStale ? ", but the public endpoint is currently degraded." : '.'}`
                                : "The platform has not received any real notification group messages yet."}
                        </div>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-white/85 px-4 py-3 dark:border-slate-700 dark:bg-slate-900/40">
                        <div className="text-xs text-slate-400">Token fingerprint</div>
                        <div className="mt-1 font-mono text-xs text-slate-700 dark:text-slate-100">
                            {chatopsOverview?.verification_token_masked || "Not generated"}
                        </div>
                        <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                            {chatopsOverview?.verification_token_updated_at ? `Updated at ${formatTimestamp(chatopsOverview.verification_token_updated_at)}` : "After generation, copy it to the notification platform developer console"}
                        </div>
                    </div>
                </div>

                <div className="mt-4 rounded-xl border border-slate-200 bg-white/85 px-4 py-4 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
                    <div className="font-medium text-slate-700 dark:text-slate-100">Project-specific notification app bot configuration</div>
                    <div className="mt-1">
                        Custom webhook bots only receive outbound notifications. Configure a dedicated notification app bot for this project to trigger the platform with status, report, or test URL messages from group members.
                    </div>
                    <div className="mt-3 grid gap-3 lg:grid-cols-[1fr_1.2fr_auto_auto_auto]">
                        <input
                            value={appBotAppIdInput}
                            onChange={(e) => setAppBotAppIdInput(e.target.value)}
                            placeholder={"Project-specific notification app ID"}
                            className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 outline-none focus:border-violet-300 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100"
                        />
                        <input
                            value={appBotSecretInput}
                            onChange={(e) => setAppBotSecretInput(e.target.value)}
                            placeholder={"Project-specific notification app secret"}
                            type="password"
                            className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 outline-none focus:border-violet-300 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100"
                        />
                        <button
                            onClick={() => { void handleConfigureAppBot(); }}
                            disabled={configuringAppBot || !appBotAppIdInput.trim() || !appBotSecretInput.trim()}
                            className="inline-flex items-center justify-center gap-2 rounded-xl bg-violet-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-600 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {configuringAppBot ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                            {configuringAppBot ? "Saving..." : "Save app bot"}
                        </button>
                        <button
                            onClick={() => { void handleUnbindAppBot(); }}
                            disabled={unbindingAppBot || !chatopsAppBotConfigured}
                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-medium text-rose-700 transition-colors hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-rose-800/60 dark:bg-rose-500/10 dark:text-rose-200 dark:hover:bg-rose-500/20"
                        >
                            {unbindingAppBot ? <Loader2 className="h-4 w-4 animate-spin" /> : <X className="h-4 w-4" />}
                            {unbindingAppBot ? "Unbinding..." : "Unbind current app bot"}
                        </button>
                        <button
                            onClick={() => { void handleSelfCheckAppBot(); }}
                            disabled={checkingAppBot || !chatopsAppBotConfigured}
                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100 dark:hover:bg-slate-700"
                        >
                            {checkingAppBot ? <Loader2 className="h-4 w-4 animate-spin" /> : <TestTubes className="h-4 w-4" />}
                            {checkingAppBot ? "Validating..." : "Verify app bot"}
                        </button>
                    </div>
                    <div className="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-slate-700 dark:bg-slate-800/60 dark:text-slate-100">
                        {chatopsAppBotConfigured
                            ? `A dedicated app bot is configured for this project: ${chatopsAppBotIdMasked || "Saved"}`
                            : "This project has no dedicated app bot. Group members' messages will not automatically reach the platform."}
                    </div>
                    {chatopsAppBotConfigured && (
                        <div className={`mt-3 rounded-xl px-3 py-3 ${
                            chatopsAppBotReady
                                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200'
                                : 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200'
                        }`}>
                            <div className="font-medium">App bot credential verification</div>
                            <div className="mt-1">
                                Status: {chatopsAppBotReady ? "Passed" : "Failed"}
                                {latestAppBotCheck?.created_at ? ` · ${formatTimestamp(latestAppBotCheck.created_at)}` : ''}
                            </div>
                            <div className="mt-1 text-xs opacity-80">
                                {latestAppBotCheck?.message || "The platform attempts to obtain tenant_access_token after saving. You can also verify it manually."}
                            </div>
                            {latestAppBotCheck?.status_code ? (
                                <div className="mt-1 text-[11px] opacity-80">
                                    HTTP {latestAppBotCheck.status_code}
                                    {latestAppBotCheck.app_id_masked ? ` · ${latestAppBotCheck.app_id_masked}` : ''}
                                    {latestAppBotCheck.source ? ` · ${latestAppBotCheck.source === 'config_save' ? "Verify automatically after saving" : "Verify manually"}` : ''}
                                </div>
                            ) : (
                                latestAppBotCheck?.app_id_masked ? (
                                    <div className="mt-1 text-[11px] opacity-80">
                                        {latestAppBotCheck.app_id_masked}
                                        {latestAppBotCheck.source ? ` · ${latestAppBotCheck.source === 'config_save' ? "Verify automatically after saving" : "Verify manually"}` : ''}
                                    </div>
                                ) : null
                            )}
                        </div>
                    )}
                    {appBotUnbindResult && (
                        <div className="mt-3 rounded-xl bg-emerald-50 px-3 py-3 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200">
                            <div className="font-medium">Project app bot unbound</div>
                            <div className="mt-1">{appBotUnbindResult.message}</div>
                            <div className="mt-1 text-xs opacity-80">
                                Cleared: app verifications {appBotUnbindResult.purged?.checks_removed ?? 0} · Session bindings {appBotUnbindResult.purged?.bindings_removed ?? 0} · Integration events {appBotUnbindResult.purged?.events_removed ?? 0} entries
                            </div>
                        </div>
                    )}
                    {appBotConfigResult && (
                        <div className={`mt-3 rounded-xl px-3 py-3 ${
                            appBotConfigResult.validation?.ok
                                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200'
                                : 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200'
                        }`}>
                            <div>App bot configuration saved; current fingerprint {appBotConfigResult.app_id_masked || "Saved"}.</div>
                            <div className="mt-1 text-xs opacity-80">
                                {appBotConfigResult.validation?.message || "Credentials saved. Verification results have not been returned yet."}
                            </div>
                        </div>
                    )}
                    {appBotSelfCheckResult && (
                        <div className={`mt-3 rounded-xl px-3 py-3 ${
                            appBotSelfCheckResult.validation?.ok
                                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200'
                                : 'bg-slate-50 text-slate-700 dark:bg-slate-800/60 dark:text-slate-100'
                        }`}>
                            <div className="font-medium">Latest manual verification</div>
                            <div className="mt-1">{appBotSelfCheckResult.validation?.message || "App bot verification completed."}</div>
                            <div className="mt-1 text-xs opacity-80">
                                {appBotSelfCheckResult.validation?.status_code ? `HTTP ${appBotSelfCheckResult.validation.status_code}` : "No HTTP status returned"}
                                {appBotSelfCheckResult.validation?.app_id_masked ? ` · ${appBotSelfCheckResult.validation.app_id_masked}` : ''}
                            </div>
                        </div>
                    )}
                </div>

                <div className="mt-4 rounded-xl border border-slate-200 bg-white/85 px-4 py-4 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
                    <div className="font-medium text-slate-700 dark:text-slate-100">Public callback URL configuration</div>
                    <div className="mt-1">
                        Enter only the public base URL. The platform appends the notification event subscription callback path automatically.
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
                            {configuringCallbackUrl ? "Saving..." : "Save public URL"}
                        </button>
                        <button
                            onClick={() => { void handleRefreshProbe(); }}
                            disabled={refreshingProbe}
                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100 dark:hover:bg-slate-700"
                        >
                            {refreshingProbe ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                            {refreshingProbe ? "Probing..." : "Retry probe now"}
                        </button>
                    </div>
                    <div className="mt-2 rounded-lg bg-slate-50 px-3 py-2 font-mono text-[11px] text-slate-700 dark:bg-slate-800/60 dark:text-slate-100">
                        {chatopsOverview?.callback_url || `${publicApiBaseUrlInput || 'https://ops.example.com'}/api/commander/notification_platform/events`}
                    </div>
                    <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-3 dark:border-slate-700 dark:bg-slate-800/40">
                        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                            <div>
                                <div className="font-medium text-slate-700 dark:text-slate-100">Local reverse tunnel</div>
                                <div className={`mt-1 text-sm font-semibold ${localTunnelStatusClass}`}>
                                    {localTunnelStatusLabel}
                                    {localTunnel?.pid ? ` · PID ${localTunnel.pid}` : ''}
                                </div>
                                <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                                    {localTunnel?.summary || "Checking local reverse tunnel status..."}
                                </div>
                                {localTunnel?.checked_at ? (
                                    <div className="mt-1 text-[11px] text-slate-400 dark:text-slate-500">
                                        Last checked: {formatTimestamp(localTunnel.checked_at)}
                                    </div>
                                ) : null}
                            </div>
                            <button
                                onClick={() => { void handleRestartLocalTunnel(); }}
                                disabled={restartingLocalTunnel || !localTunnel?.supported || !localTunnel?.script_exists}
                                className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100 dark:hover:bg-slate-700"
                            >
                                {restartingLocalTunnel ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                                {restartingLocalTunnel ? "Restarting..." : "Restart local tunnel"}
                            </button>
                        </div>
                        {(localTunnel?.stderr_tail || localTunnel?.stdout_tail) ? (
                            <div className="mt-3 rounded-lg bg-white px-3 py-2 text-[11px] text-slate-600 dark:bg-slate-900/40 dark:text-slate-300">
                                <div className="font-medium text-slate-700 dark:text-slate-100">Recent logs</div>
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
                                <div className="font-medium">Latest tunnel restart</div>
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
                            <div className="font-medium">Public callback probe</div>
                            <div className="mt-1">{callbackProbe.summary}</div>
                            <div className="mt-1 text-xs opacity-80">
                                {callbackProbe.probed_at ? `Latest probe: ${formatTimestamp(callbackProbe.probed_at)}` : "Latest probe time unknown"}
                                {callbackProbe.status_code ? ` · HTTP ${callbackProbe.status_code}` : ''}
                                {callbackProbe.issue ? ` · ${callbackProbe.issue}` : ''}
                            </div>
                            <div className="mt-1 text-xs opacity-80">
                                Current entry point: {chatopsCallbackProviderLabel}{chatopsCallbackProviderHost ? ` · ${chatopsCallbackProviderHost}` : ''}
                            </div>
                            {chatopsCallbackRecommendation && (
                                <div className="mt-2 text-xs opacity-90">
                                    Suggested action: {chatopsCallbackRecommendation}
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
                            <div className="font-medium">Latest manual retry</div>
                            <div className="mt-1">{probeRefreshResult.probe?.summary || "Probe retry completed."}</div>
                            <div className="mt-1 text-xs opacity-80">
                                {probeRefreshResult.probe?.probed_at ? `Time: ${formatTimestamp(probeRefreshResult.probe.probed_at)}` : "Unknown time"}
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
                                ? `Public base URL saved. Current callback: ${callbackConfigResult.callback_url}`
                                : (callbackConfigResult.message || "Failed to save")}
                        </div>
                    )}
                    <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-3 dark:border-slate-700 dark:bg-slate-800/40">
                        <div className="flex items-center justify-between gap-3">
                            <div className="font-medium text-slate-700 dark:text-slate-100">Recent probe records</div>
                            <div className="text-[11px] text-slate-500 dark:text-slate-400">
                                {callbackProbeHistory.length ? `Latest ${callbackProbeHistory.length} occurrences` : "No history yet"}
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
                                            <span>{item.created_at ? formatTimestamp(item.created_at) : "Unknown time"}</span>
                                            <span>·</span>
                                            <span>{item.success ? "Passed" : item.attempted ? "Failed" : "Not run"}</span>
                                            <span>·</span>
                                            <span>{item.source === 'manual_refresh' ? "Manual retry" : "Automatic diagnostics"}</span>
                                            {item.force_refresh && (
                                                <>
                                                    <span>·</span>
                                                    <span>Force refresh</span>
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
                                No probe history yet. Saving a public URL triggers diagnostics automatically, or click Retry probe now to refresh manually.
                            </div>
                        )}
                    </div>
                </div>

                <div className="mt-4 rounded-xl border border-slate-200 bg-white/85 px-4 py-4 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
                    <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                        <div>
                            <div className="font-medium text-slate-700 dark:text-slate-100">Notification platform developer console checklist</div>
                            <div className="mt-1">
                                Complete all five steps below before status, report mission_id, or test URL commands from the group can reach the platform.
                            </div>
                        </div>
                        <div className="rounded-lg bg-slate-50 px-3 py-2 text-slate-600 dark:bg-slate-800/60 dark:text-slate-200">
                            {chatopsDirectChatReady ? "End-to-end integration testing completed" : !chatopsAppBotConfigured ? "App bot configuration still required" : "Final notification platform console step still required"}
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
                            onClick={() => { void handleCopy('callback-url', notification_platformCallbackUrl, "Callback URL copied. Paste it into the notification platform developer console."); }}
                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100 dark:hover:bg-slate-700"
                        >
                            <Copy className="h-4 w-4" />
                            Copy callback URL
                        </button>
                        <button
                            onClick={() => { void handleCopy('setup-guide', chatopsGuideText, "Configuration checklist copied. Share it with operations or compare it against the notification platform console."); }}
                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100 dark:hover:bg-slate-700"
                        >
                            <Copy className="h-4 w-4" />
                            Copy configuration checklist
                        </button>
                        <button
                            onClick={() => { void handleCopy('token', currentTokenValue, "The current session's verification token was copied."); }}
                            disabled={!currentTokenValue}
                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100 dark:hover:bg-slate-700"
                        >
                            <Copy className="h-4 w-4" />
                            Copy current token
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
                            <div className="font-medium text-slate-700 dark:text-slate-100">Verification token visibility</div>
                            <div className="mt-1">{currentTokenHint}</div>
                        </div>
                    )}
                </div>

                <div className="mt-4 rounded-xl border border-slate-200 bg-white/85 px-4 py-4 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
                    <div className="flex items-center justify-between gap-3">
                        <div className="font-medium text-slate-700 dark:text-slate-100">Recent group chat routing</div>
                        <div className="text-[11px] text-slate-500 dark:text-slate-400">
                            {recentChatBindings.length ? `Latest ${recentChatBindings.length} sessions` : "No sessions yet"}
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
                                        <span className="font-mono">{item.chat_id || "Unknown group session"}</span>
                                        <span>·</span>
                                        <span>{formatBindingSource(item.source)}</span>
                                        <span>·</span>
                                        <span>{formatReplyMode(item.last_reply_mode)}</span>
                                        <span>·</span>
                                        <span>{item.last_delivery_ok ? "Latest reply delivered" : "Latest reply delivery failed"}</span>
                                        <span>·</span>
                                        <span>{item.last_seen_at ? formatTimestamp(item.last_seen_at) : "Unknown time"}</span>
                                    </div>
                                    <div className="mt-1">
                                        <span className="font-medium">Latest message:</span>
                                        <span>{item.last_message || "No content yet"}</span>
                                    </div>
                                    <div className="mt-1 text-[11px] opacity-80">
                                        Latest sender: {item.last_from_user || "Unknown user"}
                                    </div>
                                    <div className="mt-1 text-[11px] opacity-80">
                                        Binding status: {item.binding_status || "Unknown"} · run_id: {item.last_run_id || "Not linked"}
                                    </div>
                                    {item.last_run_id && (
                                        <div className="mt-2">
                                            <a
                                                href={`/legion?tab=control&run=${encodeURIComponent(item.last_run_id)}`}
                                                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-100 dark:hover:bg-slate-800"
                                            >
                                                View linked command
                                            </a>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                            No recent group chat routing records. After a real inbound group message or a platform simulation, this view shows whether replies used the app bot or webhook fallback.
                        </div>
                    )}
                </div>

                {latestChatopsEvent && (
                    <div className="mt-4 rounded-xl border border-slate-200 bg-white/85 px-4 py-3 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
                        <div className="font-medium text-slate-700 dark:text-slate-100">Latest command</div>
                        <div className="mt-2">Message: {latestChatopsEvent.message || '-'}</div>
                        <div className="mt-1">Reply: {latestChatopsEvent.response || '-'}</div>
                        <div className="mt-1">Status: {latestChatopsEvent.status} · Reply delivery {latestChatopsEvent.delivery_delivered}/{latestChatopsEvent.delivery_configured}</div>
                        <div className="mt-1">Command: {latestChatopsEvent.command_id || '-'} · run_id: {latestChatopsEvent.run_id || "Not linked"} · Binding: {latestChatopsEvent.binding_status || "Unknown"}</div>
                        {latestEventRunHref && (
                            <div className="mt-2">
                                <a
                                    href={latestEventRunHref}
                                    className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100 dark:hover:bg-slate-700"
                                >
                                    Open this command's Legion details
                                </a>
                            </div>
                        )}
                        {latestChatopsEvent.status === 'ignored' && latestSuccessfulChatopsEvent && (
                            <div className="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-slate-600 dark:bg-slate-800/60 dark:text-slate-200">
                                Latest successful command: {latestSuccessfulChatopsEvent.message} → {latestSuccessfulChatopsEvent.response}
                            </div>
                        )}
                    </div>
                )}

                <div className="mt-4 rounded-xl border border-slate-200 bg-white/85 px-4 py-4 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div>
                            <div className="font-medium text-slate-700 dark:text-slate-100">Event subscription settings</div>
                            <div className="mt-1">
                                Generate a verification token and run a local challenge self-check before configuring the notification platform console.
                            </div>
                        </div>
                        <div className="rounded-lg bg-slate-50 px-3 py-2 text-slate-600 dark:bg-slate-800/60 dark:text-slate-200">
                            {chatopsOverview?.verification_token_configured ? "Token configured" : "No token generated yet"}
                        </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                        <button
                            onClick={() => { void handleConfigureToken(); }}
                            disabled={configuringToken}
                            className="inline-flex items-center justify-center gap-2 rounded-xl bg-sky-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {configuringToken ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                            {configuringToken ? "Generating..." : (chatopsOverview?.verification_token_configured ? "Regenerate token" : "Generate token")}
                        </button>
                        <button
                            onClick={() => { void handleSubscriptionSelfCheck(); }}
                            disabled={selfCheckingSubscription || !chatopsOverview?.verification_token_configured}
                            className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-600 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {selfCheckingSubscription ? <Loader2 className="h-4 w-4 animate-spin" /> : <TestTubes className="h-4 w-4" />}
                            {selfCheckingSubscription ? "Verifying..." : "Verify callback endpoint"}
                        </button>
                    </div>
                    {tokenConfigResult && (
                        <div className="mt-3 rounded-xl bg-slate-50 px-3 py-3 text-slate-700 dark:bg-slate-800/60 dark:text-slate-100">
                            <div className="font-medium">Most recently generated verification token</div>
                            <div className="mt-2 break-all rounded-lg bg-white/90 px-3 py-2 font-mono text-xs dark:bg-slate-900/60">
                                {tokenConfigResult.token}
                            </div>
                            <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                                Add this token to the event subscription settings in the notification platform developer console. It has also been saved persistently in the platform.
                            </div>
                        </div>
                    )}
                    {subscriptionCheckResult && (
                        <div className={`mt-3 rounded-xl px-3 py-3 ${
                            subscriptionCheckResult.status === 'success'
                                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200'
                                : 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200'
                        }`}>
                            <div className="font-medium">Platform challenge self-check</div>
                            <div className="mt-2">
                                {subscriptionCheckResult.status === 'success'
                                    ? `Verification succeeded, challenge=${subscriptionCheckResult.result?.challenge || 'codex-self-check'}`
                                    : subscriptionCheckResult.message || "Verification failed"}
                            </div>
                            <div className="mt-1 text-xs opacity-80">
                                {latestSubscriptionCheckEvent
                                    ? `Latest self-check: ${formatTimestamp(latestSubscriptionCheckEvent.created_at)}`
                                    : "The latest verification time appears here after a self-check completes."}
                            </div>
                        </div>
                    )}
                    {externalCheckResult && (
                        <div className={`mt-3 rounded-xl px-3 py-3 ${
                            externalCheckResult.status === 'success'
                                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200'
                                : 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200'
                        }`}>
                            <div className="font-medium">Public connection self-test</div>
                            <div className="mt-2 break-all">
                                URL: {externalCheckResult.callback_url}
                            </div>
                            <div className="mt-1">
                                challenge: {externalCheckResult.challenge_check.ok && externalCheckResult.challenge_check.challenge_matched ? "Passed" : "Failed"}
                                {typeof externalCheckResult.challenge_check.status_code === 'number'
                                    ? ` · HTTP ${externalCheckResult.challenge_check.status_code}`
                                    : ''}
                            </div>
                            <div className="mt-1">
                                Text message: {externalCheckResult.message_check.ok ? "Passed" : "Failed"}
                                {typeof externalCheckResult.message_check.status_code === 'number'
                                    ? ` · HTTP ${externalCheckResult.message_check.status_code}`
                                    : ''}
                                {externalCheckResult.message_check.delivery
                                    ? ` · Reply delivery ${externalCheckResult.message_check.delivery.delivered || 0}/${externalCheckResult.message_check.delivery.configured || 0}`
                                    : ''}
                            </div>
                            {!!externalCheckResult.message_check.command_response && (
                                <div className="mt-1 line-clamp-3">
                                    Reply: {externalCheckResult.message_check.command_response}
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
                            <div className="font-medium">Latest public connection self-test</div>
                            <div className="mt-1">
                                Status: {externalSelfCheckRecentSuccess ? "Passed" : "Failed"}
                                {latestExternalSelfCheckAt ? ` · ${formatTimestamp(latestExternalSelfCheckAt)}` : ''}
                            </div>
                            <div className="mt-1 text-xs opacity-80">
                                The platform most recently verified both challenges and text messages through the public endpoint;
                                {chatopsDirectChatReady ? " real notification group messaging is also connected." : " this does not yet confirm that real notification group message integration is complete."}
                            </div>
                            {latestExternalSelfCheckEvent?.response && (
                                <div className="mt-1 line-clamp-3 text-xs opacity-80">
                                    Latest reply: {latestExternalSelfCheckEvent.response}
                                </div>
                            )}
                        </div>
                    )}
                </div>

                <div className="mt-4 rounded-xl border border-slate-200 bg-white/85 px-4 py-4 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                        <div className="flex-1">
                            <div className="font-medium text-slate-700 dark:text-slate-100">Platform self-check</div>
                            <div className="mt-1">
                                Simulate a notification text command inside the platform to verify message receipt, parsing, and reply delivery before opening the notification platform developer console.
                            </div>
                        </div>
                        <div className="rounded-lg bg-slate-50 px-3 py-2 text-slate-600 dark:bg-slate-800/60 dark:text-slate-200">
                            {chatopsDirectChatReady
                                ? "Two-way connection ready"
                                : !chatopsOverview?.callback_url_public
                                    ? "The callback URL is still local"
                                : !chatopsAppBotConfigured
                                    ? "Notification app bot still required"
                                : chatopsPlatformReady
                                    ? "Platform ready; send a real group message from the notification platform"
                                    : chatopsWebhookReady
                                        ? "Token or challenge self-check still required"
                                        : "A healthy notification reply channel is still required"}
                        </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                        {["Status", "report 125c69cd", "test https://example.com"].map(command => (
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
                            placeholder={"Enter a notification text command to simulate, for example: status"}
                            className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 outline-none focus:border-violet-300 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100"
                        />
                        <button
                            onClick={() => { void handleSimulate(); }}
                            disabled={simulating || !simulateMessage.trim()}
                            className="inline-flex items-center justify-center gap-2 rounded-xl bg-violet-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-600 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {simulating ? <Loader2 className="h-4 w-4 animate-spin" /> : <TestTubes className="h-4 w-4" />}
                            {simulating ? "Simulating..." : "Simulate notification command"}
                        </button>
                        <button
                            onClick={() => { void handleExternalSelfCheck(); }}
                            disabled={externallyChecking || !chatopsOverview?.callback_url_public || !chatopsOverview?.verification_token_configured}
                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-700 transition-colors hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200 dark:hover:bg-emerald-500/20"
                        >
                            {externallyChecking ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                            {externallyChecking ? "Running public self-test..." : "Run public connection self-test"}
                        </button>
                    </div>
                    {simulateResult && (
                        <div className="mt-3 rounded-xl bg-slate-50 px-3 py-3 text-slate-700 dark:bg-slate-800/60 dark:text-slate-100">
                            <div className="font-medium">Latest simulation</div>
                            <div className="mt-2">Reply: {simulateResult.result.response || '-'}</div>
                            <div className="mt-1">
                                Reply delivery: {simulateResult.delivery.delivered}/{simulateResult.delivery.configured}
                                {simulateResult.delivery.message ? ` · ${simulateResult.delivery.message}` : ''}
                            </div>
                            <div className="mt-1">Current status: {simulateResult.overview.summary}</div>
                            {simulateRunId && (
                                <div className="mt-1">Linked run_id: {simulateRunId}</div>
                            )}
                            <div className="mt-3 flex flex-wrap gap-2">
                                <a
                                    href={legionControlHref}
                                    className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-100 dark:hover:bg-slate-800"
                                >
                                    Open Legion control center
                                </a>
                                {simulateRunHref && (
                                    <a
                                        href={simulateRunHref}
                                        className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-100 dark:hover:bg-slate-800"
                                    >
                                        Open linked command
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
                        <p className="text-slate-400 text-sm">No notification configuration yet</p>
                        <p className="text-slate-400 text-xs mt-1">Add a webhook to send notifications automatically when tests finish</p>
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
                                            {wh.enabled ? "Enabled" : "Disabled"}
                                        </span>
                                        <span className={`rounded-full px-2 py-0.5 ${
                                            wh.last_test_at
                                                ? wh.last_test_success
                                                    ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300'
                                                    : 'bg-rose-50 text-rose-600 dark:bg-rose-500/15 dark:text-rose-300'
                                                : 'bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-300'
                                        }`}>
                                            {!wh.last_test_at ? "Not tested" : wh.last_test_success ? "Latest test passed" : "Latest test failed"}
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
                                        title={wh.enabled ? "Disable" : "Enable"}
                                    >
                                        {toggling === wh.id ? "Processing..." : wh.enabled ? "Disable" : "Enable"}
                                    </button>
                                    <button onClick={() => handleTest(wh.id)} disabled={testing === wh.id}
                                        className="p-2 rounded-lg text-slate-400 hover:text-indigo-500 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 transition-colors" title={"Test"}>
                                        {testing === wh.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <TestTubes className="w-4 h-4" />}
                                    </button>
                                    <button onClick={() => handleDelete(wh.id)}
                                        className="p-2 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors" title={"Delete"}>
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
                            <Bell className="w-5 h-5 text-pink-500" /> Add webhook
                        </h3>
                        <div className="space-y-3">
                            <div>
                                <label className="text-xs font-medium text-slate-500">Name</label>
                                <input type="text" value={name} onChange={e => setName(e.target.value)}
                                    placeholder={"Example: DingTalk testing group"} className="w-full mt-1 px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600 text-sm outline-none" />
                            </div>
                            <div>
                                <label className="text-xs font-medium text-slate-500">Type</label>
                                <select value={type} onChange={e => setType(e.target.value)}
                                    className="w-full mt-1 px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600 text-sm outline-none">
                                    <option value="dingtalk">DingTalk</option>
                                    <option value="wecom">WeCom</option>
                                    <option value="notification_platform">Notification platform</option>
                                    <option value="custom">Custom</option>
                                </select>
                            </div>
                            <div>
                                <label className="text-xs font-medium text-slate-500">Webhook URL</label>
                                <input type="text" value={url} onChange={e => setUrl(e.target.value)}
                                    placeholder={typePlaceholder}
                                    className="w-full mt-1 px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600 text-sm font-mono outline-none" />
                            </div>
                            <label className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-700/40 dark:text-slate-200">
                                <span>Enable immediately after adding</span>
                                <input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />
                            </label>
                            <label className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-700/40 dark:text-slate-200">
                                <span>Test immediately after adding</span>
                                <input
                                    type="checkbox"
                                    checked={testAfterCreate}
                                    disabled={!enabled}
                                    onChange={e => setTestAfterCreate(e.target.checked)}
                                />
                            </label>
                            <button onClick={handleAdd} disabled={!name.trim() || !url.trim()}
                                className="w-full mt-2 px-4 py-2.5 bg-gradient-to-r from-pink-500 to-rose-500 text-white rounded-xl text-sm font-medium disabled:opacity-50 transition-all">
                                {enabled && testAfterCreate ? "Add and test" : "Add"}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
