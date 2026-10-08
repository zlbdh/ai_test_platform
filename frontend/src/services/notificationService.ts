import { API_BASE_URL } from '../config';

export interface NotificationWebhook {
    id: string;
    name: string;
    url: string;
    type: string;
    enabled: boolean;
    last_test_at?: string;
    last_test_success?: boolean;
    last_test_status?: number;
    last_test_message?: string;
}

export interface NotificationOverview {
    total: number;
    enabled: number;
    tested_enabled: number;
    healthy_enabled: number;
    untested_enabled: number;
    production_ready: boolean;
    summary: string;
}

export interface NotificationOverviewResponse {
    overview: NotificationOverview;
    webhooks: NotificationWebhook[];
}

export interface NotificationDrillResultItem {
    id: string;
    name: string;
    success: boolean;
    status_code: number;
    message: string;
}

export interface NotificationDrillResponse {
    configured: number;
    attempted: number;
    delivered: number;
    failed: number;
    results: NotificationDrillResultItem[];
    summary: string;
}

export interface CommanderChatOpsEvent {
    id: number;
    channel: string;
    source: string;
    event_type: string;
    message: string;
    from_user: string;
    chat_id: string;
    response: string;
    status: string;
    delivery_configured: number;
    delivery_delivered: number;
    delivery_failed: number;
    run_id?: string;
    command_id?: string;
    requester_id?: string;
    binding_status?: string;
    created_at: string;
}

export interface CommanderChatOpsCallbackProbe {
    attempted: boolean;
    success: boolean;
    issue: string;
    summary: string;
    status_code?: number | null;
    content_type?: string;
    response_excerpt?: string;
    probed_at?: string;
}

export interface CommanderChatOpsCallbackProbeHistoryItem {
    id: number;
    callback_url: string;
    attempted: boolean;
    success: boolean;
    issue: string;
    summary: string;
    status_code?: number | null;
    content_type?: string;
    response_excerpt?: string;
    source: string;
    force_refresh: boolean;
    created_at: string;
}

export interface CommanderChatOpsChatBinding {
    chat_id: string;
    channel: string;
    source: string;
    last_from_user: string;
    last_message: string;
    last_seen_at: string;
    last_reply_mode: string;
    last_delivery_ok: number;
    last_run_id?: string;
    last_command_id?: string;
    last_requester_id?: string;
    binding_status?: string;
}

export interface CommanderChatOpsLocalTunnelStatus {
    supported: boolean;
    script_path: string;
    script_exists: boolean;
    stdout_log: string;
    stderr_log: string;
    running: boolean;
    pid?: number | null;
    status: string;
    summary: string;
    checked_at: string;
    created_at?: string;
    command_line?: string;
    stdout_tail?: string;
    stderr_tail?: string;
}

export interface CommanderChatOpsAppBotCheck {
    id: number;
    success: boolean;
    message: string;
    status_code?: number | null;
    source: string;
    app_id_masked: string;
    created_at: string;
}

export interface CommanderChatOpsOverview {
    channel: string;
    event_endpoint: string;
    verification_token_configured: boolean;
    verification_token_masked: string;
    verification_token_updated_at: string;
    app_bot_configured?: boolean;
    app_bot_ready?: boolean;
    app_bot_id_masked?: string;
    app_bot_updated_at?: string;
    app_bot_check?: CommanderChatOpsAppBotCheck | null;
    unified_robot_target?: boolean;
    unified_robot_platform_ready?: boolean;
    unified_robot_ready?: boolean;
    delivery_strategy?: string;
    delivery_strategy_summary?: string;
    callback_url: string;
    callback_url_public: boolean;
    callback_provider?: {
        key?: string;
        label?: string;
        host?: string;
    };
    callback_recommendation?: string;
    enabled_notification_platform_webhook_count: number;
    healthy_notification_platform_webhook_count: number;
    webhook_ready: boolean;
    subscription_endpoint_verified: boolean;
    external_connected: boolean;
    external_connected_current?: boolean;
    external_connected_history_observed?: boolean;
    external_connection_stale?: boolean;
    external_self_check_recent_success?: boolean;
    external_callback_ready?: boolean;
    platform_ready: boolean;
    direct_chat_ready?: boolean;
    ready: boolean;
    callback_probe?: CommanderChatOpsCallbackProbe | null;
    callback_probe_history?: CommanderChatOpsCallbackProbeHistoryItem[];
    local_tunnel?: CommanderChatOpsLocalTunnelStatus;
    recent_chat_bindings?: CommanderChatOpsChatBinding[];
    summary: string;
    supported_commands: string[];
    latest_event: CommanderChatOpsEvent | null;
    latest_successful_event: CommanderChatOpsEvent | null;
    latest_external_successful_event: CommanderChatOpsEvent | null;
    latest_external_success_at?: string;
    latest_external_self_check_event?: CommanderChatOpsEvent | null;
    latest_external_self_check_at?: string;
    latest_subscription_check_event: CommanderChatOpsEvent | null;
    recent_events: CommanderChatOpsEvent[];
}

export interface CommanderChatOpsSimulateResponse {
    status: string;
    result: {
        response: string;
        target_url?: string;
        mission?: unknown;
        run?: {
            run_id?: string;
        };
    };
    delivery: {
        configured: number;
        delivered: number;
        failed: number;
        message?: string;
    };
    overview: CommanderChatOpsOverview;
}

export interface CommanderChatOpsTokenConfigResponse {
    status: string;
    token: string;
    token_masked: string;
    verification_token_updated_at: string;
    overview: CommanderChatOpsOverview;
}

export interface CommanderChatOpsCallbackConfigResponse {
    status: string;
    message?: string;
    public_api_base_url?: string;
    callback_url?: string;
    callback_url_public?: boolean;
    overview: CommanderChatOpsOverview;
}

export interface CommanderChatOpsAppBotConfigResponse {
    status: string;
    app_bot_configured: boolean;
    app_bot_updated_at: string;
    app_id_masked: string;
    validation?: {
        ok: boolean;
        message: string;
        status_code?: number | null;
        app_id_masked?: string;
    };
    overview: CommanderChatOpsOverview;
}

export interface CommanderChatOpsAppBotSelfCheckResponse {
    status: string;
    validation: {
        ok: boolean;
        message: string;
        status_code?: number | null;
        app_id_masked?: string;
    };
    overview: CommanderChatOpsOverview;
}

export interface CommanderChatOpsAppBotUnbindResponse {
    status: string;
    message: string;
    app_bot_configured: boolean;
    app_bot_updated_at: string;
    purged: {
        checks_removed: number;
        bindings_removed: number;
        events_removed: number;
    };
    overview: CommanderChatOpsOverview;
}

export interface CommanderChatOpsSubscriptionSelfCheckResponse {
    status: string;
    message?: string;
    result?: {
        challenge?: string;
        code?: number;
        msg?: string;
    };
    overview: CommanderChatOpsOverview;
}

export interface CommanderChatOpsProbeRefreshResponse {
    status: string;
    probe: CommanderChatOpsCallbackProbe;
    overview: CommanderChatOpsOverview;
}

export interface CommanderChatOpsLocalTunnelRestartResponse {
    status: string;
    ok: boolean;
    message: string;
    stdout?: string;
    stderr?: string;
    tunnel: CommanderChatOpsLocalTunnelStatus;
    overview: CommanderChatOpsOverview;
}

export interface CommanderChatOpsExternalSelfCheckItem {
    label: string;
    ok: boolean;
    status_code: number;
    body_excerpt?: string;
    error?: string;
    challenge_matched?: boolean;
    command_response?: string;
    delivery?: {
        configured?: number;
        delivered?: number;
        failed?: number;
        message?: string;
    };
}

export interface CommanderChatOpsExternalSelfCheckResponse {
    status: string;
    callback_url: string;
    challenge: string;
    challenge_check: CommanderChatOpsExternalSelfCheckItem;
    message_check: CommanderChatOpsExternalSelfCheckItem;
    overview: CommanderChatOpsOverview;
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
    const response = await fetch(url, options);
    if (!response.ok) {
        const text = await response.text().catch(() => response.statusText);
        throw new Error(`Request failed [${response.status}]: ${text}`);
    }
    return response.json() as Promise<T>;
}

export async function listNotificationWebhooks(): Promise<NotificationWebhook[]> {
    const data = await fetchJson<{ webhooks: NotificationWebhook[] }>(`${API_BASE_URL}/api/notify/webhooks`);
    return data.webhooks || [];
}

export async function getNotificationOverview(): Promise<NotificationOverviewResponse> {
    return fetchJson<NotificationOverviewResponse>(`${API_BASE_URL}/api/notify/overview`);
}

export async function getCommanderChatOpsOverview(): Promise<CommanderChatOpsOverview> {
    const data = await fetchJson<{ status: string; overview: CommanderChatOpsOverview }>(`${API_BASE_URL}/api/commander/chatops/overview`);
    return data.overview;
}

export async function refreshCommanderChatOpsProbe(): Promise<CommanderChatOpsProbeRefreshResponse> {
    return fetchJson<CommanderChatOpsProbeRefreshResponse>(`${API_BASE_URL}/api/commander/chatops/probe-refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
    });
}

export async function restartCommanderChatOpsLocalTunnel(): Promise<CommanderChatOpsLocalTunnelRestartResponse> {
    return fetchJson<CommanderChatOpsLocalTunnelRestartResponse>(`${API_BASE_URL}/api/commander/chatops/local-tunnel/restart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
    });
}

export async function runCommanderChatOpsExternalSelfCheck(): Promise<CommanderChatOpsExternalSelfCheckResponse> {
    return fetchJson<CommanderChatOpsExternalSelfCheckResponse>(`${API_BASE_URL}/api/commander/chatops/external-self-check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
    });
}

export async function simulateCommanderChatOps(payload: {
    message: string;
    from_user?: string;
    chat_id?: string;
    deliver?: boolean;
}): Promise<CommanderChatOpsSimulateResponse> {
    return fetchJson<CommanderChatOpsSimulateResponse>(`${API_BASE_URL}/api/commander/chatops/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
}

export async function configureCommanderChatOpsToken(payload?: {
    verification_token?: string;
    regenerate?: boolean;
}): Promise<CommanderChatOpsTokenConfigResponse> {
    return fetchJson<CommanderChatOpsTokenConfigResponse>(`${API_BASE_URL}/api/commander/chatops/config/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload || {}),
    });
}

export async function configureCommanderChatOpsCallbackUrl(payload?: {
    public_api_base_url?: string;
}): Promise<CommanderChatOpsCallbackConfigResponse> {
    return fetchJson<CommanderChatOpsCallbackConfigResponse>(`${API_BASE_URL}/api/commander/chatops/config/callback-url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload || {}),
    });
}

export async function configureCommanderChatOpsAppBot(payload?: {
    app_id?: string;
    app_secret?: string;
}): Promise<CommanderChatOpsAppBotConfigResponse> {
    return fetchJson<CommanderChatOpsAppBotConfigResponse>(`${API_BASE_URL}/api/commander/chatops/config/app-bot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload || {}),
    });
}

export async function selfCheckCommanderChatOpsAppBot(): Promise<CommanderChatOpsAppBotSelfCheckResponse> {
    return fetchJson<CommanderChatOpsAppBotSelfCheckResponse>(`${API_BASE_URL}/api/commander/chatops/app-bot-self-check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
    });
}

export async function unbindCommanderChatOpsAppBot(payload?: {
    purge_history?: boolean;
}): Promise<CommanderChatOpsAppBotUnbindResponse> {
    return fetchJson<CommanderChatOpsAppBotUnbindResponse>(`${API_BASE_URL}/api/commander/chatops/config/app-bot/unbind`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload || {}),
    });
}

export async function selfCheckCommanderChatOpsSubscription(payload?: {
    challenge?: string;
}): Promise<CommanderChatOpsSubscriptionSelfCheckResponse> {
    return fetchJson<CommanderChatOpsSubscriptionSelfCheckResponse>(`${API_BASE_URL}/api/commander/chatops/subscription-self-check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload || {}),
    });
}

export async function createNotificationWebhook(payload: {
    name: string;
    url: string;
    type: string;
    enabled?: boolean;
}): Promise<NotificationWebhook> {
    return fetchJson<NotificationWebhook>(`${API_BASE_URL}/api/notify/webhooks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
}

export async function updateNotificationWebhook(
    id: string,
    payload: {
        name?: string;
        url?: string;
        type?: string;
        enabled?: boolean;
        secret?: string;
    }
): Promise<NotificationWebhook> {
    return fetchJson<NotificationWebhook>(`${API_BASE_URL}/api/notify/webhooks/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
}

export async function deleteNotificationWebhook(id: string): Promise<void> {
    await fetchJson(`${API_BASE_URL}/api/notify/webhooks/${id}`, { method: 'DELETE' });
}

export async function testNotificationWebhook(id: string): Promise<{ success: boolean; status_code?: number; error?: string; message?: string }> {
    return fetchJson(`${API_BASE_URL}/api/notify/webhooks/${id}/test`, { method: 'POST' });
}

export async function drillNotificationWebhooks(payload?: {
    title?: string;
    status?: string;
    summary?: string;
}): Promise<NotificationDrillResponse> {
    return fetchJson(`${API_BASE_URL}/api/notify/drill`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload || {}),
    });
}
