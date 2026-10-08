import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockFetch = vi.fn();
global.fetch = mockFetch;

import {
    configureCommanderChatOpsAppBot,
    selfCheckCommanderChatOpsAppBot,
    configureCommanderChatOpsCallbackUrl,
    runCommanderChatOpsExternalSelfCheck,
    refreshCommanderChatOpsProbe,
    configureCommanderChatOpsToken,
    getCommanderChatOpsOverview,
    selfCheckCommanderChatOpsSubscription,
    simulateCommanderChatOps,
    createNotificationWebhook,
    deleteNotificationWebhook,
    drillNotificationWebhooks,
    getNotificationOverview,
    listNotificationWebhooks,
    testNotificationWebhook,
    updateNotificationWebhook,
} from '../services/notificationService';

function mockResponse(body: unknown, ok = true, status = 200): Response {
    return {
        ok,
        status,
        statusText: ok ? 'OK' : 'Error',
        json: vi.fn().mockResolvedValue(body),
        text: vi.fn().mockResolvedValue(JSON.stringify(body)),
        headers: new Headers(),
    } as unknown as Response;
}

describe('notificationService.ts', () => {
    beforeEach(() => {
        mockFetch.mockReset();
    });

    it('should request notification overview', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            overview: { total: 1, enabled: 1, tested_enabled: 1, healthy_enabled: 1, untested_enabled: 0, production_ready: true, summary: 'ok' },
            webhooks: [],
        }));

        const result = await getNotificationOverview();

        expect(mockFetch.mock.calls[0][0]).toContain('/api/notify/overview');
        expect(result.overview.production_ready).toBe(true);
    });

    it('should request commander chatops overview', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            status: 'success',
            overview: {
                channel: 'notification_platform',
                event_endpoint: '/api/commander/notification_platform/events',
                verification_token_configured: false,
                verification_token_masked: '',
                verification_token_updated_at: '',
                callback_url: 'http://127.0.0.1:8020/api/commander/notification_platform/events',
                callback_url_public: false,
                enabled_notification_platform_webhook_count: 1,
                healthy_notification_platform_webhook_count: 1,
                webhook_ready: true,
                subscription_endpoint_verified: false,
                external_connected: false,
                platform_ready: false,
                ready: true,
                summary: 'ok',
                supported_commands: ["Status"],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: null,
                latest_subscription_check_event: null,
                recent_events: [],
            },
        }));

        const result = await getCommanderChatOpsOverview();

        expect(mockFetch.mock.calls[0][0]).toContain('/api/commander/chatops/overview');
        expect(result.channel).toBe('notification_platform');
        expect(result.ready).toBe(true);
    });

    it('should refresh commander chatops callback probe', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            status: 'success',
            probe: {
                attempted: true,
                success: false,
                issue: 'connect_error',
                summary: "Public callback probe failed: ConnectionError",
                status_code: null,
                content_type: '',
                response_excerpt: '',
                probed_at: '2026-03-18T13:00:00',
            },
            overview: {
                channel: 'notification_platform',
                event_endpoint: '/api/commander/notification_platform/events',
                verification_token_configured: true,
                verification_token_masked: 'demo...oken',
                verification_token_updated_at: '2026-03-18T12:00:00',
                callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
                callback_url_public: true,
                enabled_notification_platform_webhook_count: 1,
                healthy_notification_platform_webhook_count: 1,
                webhook_ready: true,
                subscription_endpoint_verified: true,
                external_connected: false,
                external_callback_ready: false,
                platform_ready: true,
                direct_chat_ready: false,
                ready: false,
                callback_probe: {
                    attempted: true,
                    success: false,
                    issue: 'connect_error',
                    summary: "Public callback probe failed: ConnectionError",
                    status_code: null,
                    content_type: '',
                    response_excerpt: '',
                    probed_at: '2026-03-18T13:00:00',
                },
                callback_probe_history: [
                    {
                        id: 3,
                        callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
                        attempted: true,
                        success: false,
                        issue: 'connect_error',
                        summary: "Public callback probe failed: ConnectionError",
                        status_code: null,
                        content_type: '',
                        response_excerpt: '',
                        source: 'manual_refresh',
                        force_refresh: true,
                        created_at: '2026-03-18 13:00:00',
                    },
                ],
                summary: "Public callback probe failed: ConnectionError",
                supported_commands: ["Status"],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: null,
                latest_subscription_check_event: null,
                recent_events: [],
            },
        }));

        const result = await refreshCommanderChatOpsProbe();

        const [url, options] = mockFetch.mock.calls[0];
        expect(url).toContain('/api/commander/chatops/probe-refresh');
        expect(options.method).toBe('POST');
        expect(JSON.parse(options.body)).toEqual({});
        expect(result.probe.issue).toBe('connect_error');
        expect(result.overview.callback_probe_history?.[0].source).toBe('manual_refresh');
    });

    it('should run commander chatops external self check', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            status: 'success',
            callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
            challenge: 'external-self-check-demo',
            challenge_check: {
                label: 'challenge',
                ok: true,
                status_code: 200,
                challenge_matched: true,
                body_excerpt: '{"challenge":"external-self-check-demo"}',
            },
            message_check: {
                label: 'message',
                ok: true,
                status_code: 200,
                command_response: "📡 Agent status",
                delivery: { configured: 1, delivered: 1, failed: 0 },
            },
            overview: {
                channel: 'notification_platform',
                event_endpoint: '/api/commander/notification_platform/events',
                verification_token_configured: true,
                verification_token_masked: 'demo...oken',
                verification_token_updated_at: '2026-03-18T12:00:00',
                callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
                callback_url_public: true,
                enabled_notification_platform_webhook_count: 1,
                healthy_notification_platform_webhook_count: 1,
                webhook_ready: true,
                subscription_endpoint_verified: true,
                external_connected: true,
                platform_ready: true,
                ready: true,
                summary: 'ok',
                supported_commands: ["Status"],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: null,
                latest_subscription_check_event: null,
                recent_events: [],
            },
        }));

        const result = await runCommanderChatOpsExternalSelfCheck();

        const [url, options] = mockFetch.mock.calls[0];
        expect(url).toContain('/api/commander/chatops/external-self-check');
        expect(options.method).toBe('POST');
        expect(JSON.parse(options.body)).toEqual({});
        expect(result.challenge_check.challenge_matched).toBe(true);
        expect(result.message_check.delivery?.delivered).toBe(1);
    });

    it('should simulate commander chatops command', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            status: 'success',
            result: { response: "🟢 Agent status: 6/6 agents online" },
            delivery: { configured: 1, delivered: 1, failed: 0, message: "Sent successfully" },
            overview: {
                channel: 'notification_platform',
                event_endpoint: '/api/commander/notification_platform/events',
                verification_token_configured: false,
                verification_token_masked: '',
                verification_token_updated_at: '',
                callback_url: 'http://127.0.0.1:8020/api/commander/notification_platform/events',
                callback_url_public: false,
                enabled_notification_platform_webhook_count: 1,
                healthy_notification_platform_webhook_count: 1,
                webhook_ready: true,
                subscription_endpoint_verified: false,
                external_connected: false,
                platform_ready: false,
                ready: false,
                summary: "An event subscription token must be configured",
                supported_commands: ["Status"],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: null,
                latest_subscription_check_event: null,
                recent_events: [],
            },
        }));

        const result = await simulateCommanderChatOps({ message: "Status", deliver: true });

        const [url, options] = mockFetch.mock.calls[0];
        expect(url).toContain('/api/commander/chatops/simulate');
        expect(options.method).toBe('POST');
        expect(JSON.parse(options.body)).toEqual({ message: "Status", deliver: true });
        expect(result.result.response).toContain("Agent status");
    });

    it('should configure commander chatops token', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            status: 'success',
            token: 'demo-token',
            token_masked: 'demo...oken',
            verification_token_updated_at: '2026-03-18T12:00:00',
            overview: {
                channel: 'notification_platform',
                event_endpoint: '/api/commander/notification_platform/events',
                verification_token_configured: true,
                verification_token_masked: 'demo...oken',
                verification_token_updated_at: '2026-03-18T12:00:00',
                callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
                callback_url_public: true,
                enabled_notification_platform_webhook_count: 1,
                healthy_notification_platform_webhook_count: 1,
                webhook_ready: true,
                subscription_endpoint_verified: false,
                external_connected: false,
                platform_ready: false,
                ready: false,
                summary: 'ok',
                supported_commands: ["Status"],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: null,
                latest_subscription_check_event: null,
                recent_events: [],
            },
        }));

        const result = await configureCommanderChatOpsToken({ regenerate: true });

        const [url, options] = mockFetch.mock.calls[0];
        expect(url).toContain('/api/commander/chatops/config/token');
        expect(options.method).toBe('POST');
        expect(JSON.parse(options.body)).toEqual({ regenerate: true });
        expect(result.token).toBe('demo-token');
    });

    it('should configure commander chatops callback url', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            status: 'success',
            public_api_base_url: 'https://ops.example.com',
            callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
            callback_url_public: true,
            overview: {
                channel: 'notification_platform',
                event_endpoint: '/api/commander/notification_platform/events',
                verification_token_configured: true,
                verification_token_masked: 'demo...oken',
                verification_token_updated_at: '2026-03-18T12:00:00',
                callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
                callback_url_public: true,
                enabled_notification_platform_webhook_count: 1,
                healthy_notification_platform_webhook_count: 1,
                webhook_ready: true,
                subscription_endpoint_verified: true,
                external_connected: false,
                platform_ready: true,
                ready: false,
                summary: 'ok',
                supported_commands: ["Status"],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: null,
                latest_subscription_check_event: null,
                recent_events: [],
            },
        }));

        const result = await configureCommanderChatOpsCallbackUrl({ public_api_base_url: 'https://ops.example.com' });

        const [url, options] = mockFetch.mock.calls[0];
        expect(url).toContain('/api/commander/chatops/config/callback-url');
        expect(options.method).toBe('POST');
        expect(JSON.parse(options.body)).toEqual({ public_api_base_url: 'https://ops.example.com' });
        expect(result.callback_url_public).toBe(true);
    });

    it('should configure commander chatops app bot', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            status: 'success',
            app_bot_configured: true,
            app_bot_updated_at: '2026-03-18T12:30:00',
            app_id_masked: 'cli...bot',
            validation: {
                ok: true,
                message: "Application bot credentials verified; tenant_access_token obtained successfully.",
                status_code: 200,
                app_id_masked: 'cli...bot',
            },
            overview: {
                channel: 'notification_platform',
                event_endpoint: '/api/commander/notification_platform/events',
                verification_token_configured: true,
                verification_token_masked: 'demo...oken',
                verification_token_updated_at: '2026-03-18T12:00:00',
                app_bot_configured: true,
                app_bot_ready: true,
                app_bot_id_masked: 'cli...bot',
                app_bot_updated_at: '2026-03-18T12:30:00',
                app_bot_check: {
                    id: 1,
                    success: true,
                    message: "Application bot credentials verified; tenant_access_token obtained successfully.",
                    status_code: 200,
                    source: 'config_save',
                    app_id_masked: 'cli...bot',
                    created_at: '2026-03-18 12:30:00',
                },
                callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
                callback_url_public: true,
                enabled_notification_platform_webhook_count: 1,
                healthy_notification_platform_webhook_count: 1,
                webhook_ready: true,
                subscription_endpoint_verified: true,
                external_connected: false,
                external_callback_ready: true,
                platform_ready: true,
                direct_chat_ready: false,
                ready: false,
                summary: "Webhook notifications and public callbacks work, but no notification platform application bot is configured. Group messages do not yet flow back automatically.",
                supported_commands: ["Status"],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: null,
                latest_subscription_check_event: null,
                recent_events: [],
            },
        }));

        const result = await configureCommanderChatOpsAppBot({ app_id: 'cli_demo_bot', app_secret: 'secret-demo' });

        const [url, options] = mockFetch.mock.calls[0];
        expect(url).toContain('/api/commander/chatops/config/app-bot');
        expect(options.method).toBe('POST');
        expect(JSON.parse(options.body)).toEqual({ app_id: 'cli_demo_bot', app_secret: 'secret-demo' });
        expect(result.app_bot_configured).toBe(true);
        expect(result.app_id_masked).toBe('cli...bot');
    });

    it('should self check commander chatops app bot', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            status: 'success',
            validation: {
                ok: true,
                message: "Application bot credentials verified; tenant_access_token obtained successfully.",
                status_code: 200,
                app_id_masked: 'cli...bot',
            },
            overview: {
                channel: 'notification_platform',
                event_endpoint: '/api/commander/notification_platform/events',
                verification_token_configured: true,
                verification_token_masked: 'demo...oken',
                verification_token_updated_at: '2026-03-18T12:00:00',
                app_bot_configured: true,
                app_bot_ready: true,
                app_bot_id_masked: 'cli...bot',
                app_bot_updated_at: '2026-03-18T12:35:00',
                app_bot_check: {
                    id: 2,
                    success: true,
                    message: "Application bot credentials verified; tenant_access_token obtained successfully.",
                    status_code: 200,
                    source: 'manual_self_check',
                    app_id_masked: 'cli...bot',
                    created_at: '2026-03-18 12:35:00',
                },
                callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
                callback_url_public: true,
                enabled_notification_platform_webhook_count: 1,
                healthy_notification_platform_webhook_count: 1,
                webhook_ready: true,
                subscription_endpoint_verified: true,
                external_connected: false,
                external_callback_ready: true,
                platform_ready: true,
                direct_chat_ready: false,
                ready: false,
                summary: 'ok',
                supported_commands: ["Status"],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: null,
                latest_subscription_check_event: null,
                recent_events: [],
            },
        }));

        const result = await selfCheckCommanderChatOpsAppBot();

        const [url, options] = mockFetch.mock.calls[0];
        expect(url).toContain('/api/commander/chatops/app-bot-self-check');
        expect(options.method).toBe('POST');
        expect(JSON.parse(options.body)).toEqual({});
        expect(result.validation.ok).toBe(true);
    });

    it('should self check commander chatops subscription', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            status: 'success',
            result: { challenge: 'codex-self-check' },
            overview: {
                channel: 'notification_platform',
                event_endpoint: '/api/commander/notification_platform/events',
                verification_token_configured: true,
                verification_token_masked: 'demo...oken',
                verification_token_updated_at: '2026-03-18T12:00:00',
                callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
                callback_url_public: true,
                enabled_notification_platform_webhook_count: 1,
                healthy_notification_platform_webhook_count: 1,
                webhook_ready: true,
                subscription_endpoint_verified: true,
                external_connected: false,
                platform_ready: true,
                ready: false,
                summary: 'ok',
                supported_commands: ["Status"],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: null,
                latest_subscription_check_event: null,
                recent_events: [],
            },
        }));

        const result = await selfCheckCommanderChatOpsSubscription({ challenge: 'codex-self-check' });

        const [url, options] = mockFetch.mock.calls[0];
        expect(url).toContain('/api/commander/chatops/subscription-self-check');
        expect(options.method).toBe('POST');
        expect(JSON.parse(options.body)).toEqual({ challenge: 'codex-self-check' });
        expect(result.result?.challenge).toBe('codex-self-check');
    });

    it('should request webhook list', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            webhooks: [{ id: 'wh_1', name: 'ops', url: 'https://example.com', type: 'custom', enabled: true }],
        }));

        const result = await listNotificationWebhooks();

        expect(mockFetch.mock.calls[0][0]).toContain('/api/notify/webhooks');
        expect(result[0].name).toBe('ops');
    });

    it('should create webhook with POST body', async () => {
        mockFetch.mockResolvedValue(mockResponse({ id: 'wh_1', name: 'ops', url: 'https://example.com', type: 'custom', enabled: true }));

        const result = await createNotificationWebhook({ name: 'ops', url: 'https://example.com', type: 'custom', enabled: false });

        const [url, options] = mockFetch.mock.calls[0];
        expect(url).toContain('/api/notify/webhooks');
        expect(options.method).toBe('POST');
        expect(JSON.parse(options.body)).toEqual({ name: 'ops', url: 'https://example.com', type: 'custom', enabled: false });
        expect(result.id).toBe('wh_1');
    });

    it('should update webhook with PATCH body', async () => {
        mockFetch.mockResolvedValue(mockResponse({ id: 'wh_1', name: 'ops', url: 'https://example.com', type: 'custom', enabled: false }));

        const result = await updateNotificationWebhook('wh_1', { enabled: false });

        const [url, options] = mockFetch.mock.calls[0];
        expect(url).toContain('/api/notify/webhooks/wh_1');
        expect(options.method).toBe('PATCH');
        expect(JSON.parse(options.body)).toEqual({ enabled: false });
        expect(result.enabled).toBe(false);
    });

    it('should test webhook', async () => {
        mockFetch.mockResolvedValue(mockResponse({ success: true, message: "Sent successfully" }));

        const result = await testNotificationWebhook('wh_1');

        const [url, options] = mockFetch.mock.calls[0];
        expect(url).toContain('/api/notify/webhooks/wh_1/test');
        expect(options.method).toBe('POST');
        expect(result.success).toBe(true);
    });

    it('should drill enabled webhooks with POST body', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            configured: 1,
            attempted: 1,
            delivered: 1,
            failed: 0,
            results: [{ id: 'wh_1', name: 'ops', success: true, status_code: 200, message: "Sent successfully" }],
            summary: "Alert drill completed for 1 enabled channel: 1 succeeded, 0 failed.",
        }));

        const result = await drillNotificationWebhooks({ title: "Platform alert drill" });

        const [url, options] = mockFetch.mock.calls[0];
        expect(url).toContain('/api/notify/drill');
        expect(options.method).toBe('POST');
        expect(JSON.parse(options.body)).toEqual({ title: "Platform alert drill" });
        expect(result.delivered).toBe(1);
    });

    it('should delete webhook', async () => {
        mockFetch.mockResolvedValue(mockResponse({ status: 'deleted' }));

        await deleteNotificationWebhook('wh_1');

        const [url, options] = mockFetch.mock.calls[0];
        expect(url).toContain('/api/notify/webhooks/wh_1');
        expect(options.method).toBe('DELETE');
    });
});
