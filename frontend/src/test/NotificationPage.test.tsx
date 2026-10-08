import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import NotificationPage from '../pages/NotificationPage';

const notificationServiceMocks = vi.hoisted(() => ({
    getNotificationOverview: vi.fn(),
    getCommanderChatOpsOverview: vi.fn(),
    configureCommanderChatOpsAppBot: vi.fn(),
    unbindCommanderChatOpsAppBot: vi.fn(),
    selfCheckCommanderChatOpsAppBot: vi.fn(),
    configureCommanderChatOpsCallbackUrl: vi.fn(),
    runCommanderChatOpsExternalSelfCheck: vi.fn(),
    refreshCommanderChatOpsProbe: vi.fn(),
    restartCommanderChatOpsLocalTunnel: vi.fn(),
    configureCommanderChatOpsToken: vi.fn(),
    createNotificationWebhook: vi.fn(),
    deleteNotificationWebhook: vi.fn(),
    drillNotificationWebhooks: vi.fn(),
    selfCheckCommanderChatOpsSubscription: vi.fn(),
    simulateCommanderChatOps: vi.fn(),
    testNotificationWebhook: vi.fn(),
    updateNotificationWebhook: vi.fn(),
}));

vi.mock('../services/notificationService', () => ({
    getNotificationOverview: notificationServiceMocks.getNotificationOverview,
    getCommanderChatOpsOverview: notificationServiceMocks.getCommanderChatOpsOverview,
    configureCommanderChatOpsAppBot: notificationServiceMocks.configureCommanderChatOpsAppBot,
    unbindCommanderChatOpsAppBot: notificationServiceMocks.unbindCommanderChatOpsAppBot,
    selfCheckCommanderChatOpsAppBot: notificationServiceMocks.selfCheckCommanderChatOpsAppBot,
    configureCommanderChatOpsCallbackUrl: notificationServiceMocks.configureCommanderChatOpsCallbackUrl,
    runCommanderChatOpsExternalSelfCheck: notificationServiceMocks.runCommanderChatOpsExternalSelfCheck,
    refreshCommanderChatOpsProbe: notificationServiceMocks.refreshCommanderChatOpsProbe,
    restartCommanderChatOpsLocalTunnel: notificationServiceMocks.restartCommanderChatOpsLocalTunnel,
    configureCommanderChatOpsToken: notificationServiceMocks.configureCommanderChatOpsToken,
    createNotificationWebhook: notificationServiceMocks.createNotificationWebhook,
    deleteNotificationWebhook: notificationServiceMocks.deleteNotificationWebhook,
    drillNotificationWebhooks: notificationServiceMocks.drillNotificationWebhooks,
    selfCheckCommanderChatOpsSubscription: notificationServiceMocks.selfCheckCommanderChatOpsSubscription,
    simulateCommanderChatOps: notificationServiceMocks.simulateCommanderChatOps,
    testNotificationWebhook: notificationServiceMocks.testNotificationWebhook,
    updateNotificationWebhook: notificationServiceMocks.updateNotificationWebhook,
}));

describe('NotificationPage', () => {
    const clipboardWriteText = vi.fn();

    beforeEach(() => {
        vi.clearAllMocks();
        clipboardWriteText.mockReset();
        clipboardWriteText.mockResolvedValue(undefined);
        Object.defineProperty(navigator, 'clipboard', {
            value: { writeText: clipboardWriteText },
            configurable: true,
        });
        notificationServiceMocks.getNotificationOverview.mockResolvedValue({
            overview: {
                total: 1,
                enabled: 1,
                tested_enabled: 1,
                healthy_enabled: 1,
                untested_enabled: 0,
                production_ready: true,
                summary: "1 Webhook configured; 1 passed its latest test",
            },
            webhooks: [
                {
                    id: 'wh_1',
                    name: 'NotificationPlatform Production Alert',
                    url: 'https://open.notification_platform.cn/open-apis/bot/v2/hook/b23a...6e0b',
                    type: 'notification_platform',
                    enabled: true,
                    last_test_at: '2026-03-18 10:00:00',
                    last_test_success: true,
                    last_test_status: 200,
                    last_test_message: "Sent successfully",
                },
            ],
        });
        notificationServiceMocks.getCommanderChatOpsOverview.mockResolvedValue({
            channel: 'notification_platform',
            event_endpoint: '/api/commander/notification_platform/events',
            verification_token_configured: false,
            verification_token_masked: '',
            verification_token_updated_at: '',
            app_bot_configured: false,
            app_bot_ready: false,
            app_bot_id_masked: '',
            app_bot_updated_at: '',
            app_bot_check: null,
            unified_robot_target: false,
            unified_robot_platform_ready: false,
            unified_robot_ready: false,
            delivery_strategy: 'webhook_only',
            delivery_strategy_summary: "Notifications still primarily use notification platform Webhooks; the single-bot experience is not yet complete.",
            callback_url: 'http://127.0.0.1:8020/api/commander/notification_platform/events',
            callback_url_public: false,
            callback_provider: {
                key: 'local',
                label: "Local URL",
                host: '127.0.0.1',
            },
            callback_recommendation: "Set PUBLIC_API_BASE_URL to a public address accessible to the notification platform before running the challenge probe.",
            enabled_notification_platform_webhook_count: 1,
            healthy_notification_platform_webhook_count: 1,
            webhook_ready: true,
            subscription_endpoint_verified: false,
            external_connected: false,
            external_connected_history_observed: false,
            external_connection_stale: false,
            external_callback_ready: false,
            platform_ready: false,
            direct_chat_ready: false,
            ready: false,
            callback_probe: {
                attempted: false,
                success: false,
                issue: 'local_callback',
                summary: "The URL is still local or private, so the platform does not run a public probe yet.",
                status_code: null,
                content_type: '',
                response_excerpt: '',
                probed_at: '2026-03-18T12:10:00',
            },
            local_tunnel: {
                supported: true,
                script_path: 'D:/workspace/ai_test_platform/data/tools/start_native_reverse_tunnel.ps1',
                script_exists: true,
                stdout_log: 'D:/workspace/ai_test_platform/data/native_ssh_reverse_tunnel_stdout.log',
                stderr_log: 'D:/workspace/ai_test_platform/data/native_ssh_reverse_tunnel_stderr.log',
                running: false,
                pid: null,
                status: 'stopped',
                summary: "No local OpenSSH reverse tunnel process was detected.",
                checked_at: '2026-03-20 11:45:00',
                stdout_tail: '',
                stderr_tail: '',
            },
            recent_chat_bindings: [],
            summary: "The notification platform reply channel is healthy, but an event subscription verification token is still missing, so group messages cannot reliably reach the platform.",
            supported_commands: ["Status", "report <mission_id>", "test <url>"],
            latest_event: {
                id: 1,
                channel: 'notification_platform',
                source: 'event_subscription',
                event_type: 'message',
                message: 'health',
                from_user: 'ou_demo',
                chat_id: 'oc_demo',
                response: "🟢 Agent status: 6/6 agents online",
                status: 'ok',
                delivery_configured: 1,
                delivery_delivered: 1,
                delivery_failed: 0,
                run_id: 'run-health',
                command_id: 'platform.status',
                requester_id: 'user_demo',
                binding_status: 'bound',
                created_at: '2026-03-18 11:10:00',
            },
            latest_successful_event: {
                id: 1,
                channel: 'notification_platform',
                source: 'event_subscription',
                event_type: 'message',
                message: 'health',
                from_user: 'ou_demo',
                chat_id: 'oc_demo',
                response: "🟢 Agent status: 6/6 agents online",
                status: 'ok',
                delivery_configured: 1,
                delivery_delivered: 1,
                delivery_failed: 0,
                run_id: 'run-health',
                command_id: 'platform.status',
                requester_id: 'user_demo',
                binding_status: 'bound',
                created_at: '2026-03-18 11:10:00',
            },
            latest_external_successful_event: null,
            latest_subscription_check_event: null,
            recent_events: [],
        });
        notificationServiceMocks.configureCommanderChatOpsAppBot.mockResolvedValue({
            status: 'success',
            app_bot_configured: true,
            app_bot_updated_at: '2026-03-18T12:30:00',
            app_id_masked: 'cli...bot',
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
                unified_robot_target: true,
                unified_robot_platform_ready: true,
                unified_robot_ready: false,
                delivery_strategy: 'single_robot_with_webhook_fallback',
                delivery_strategy_summary: "Expose a single notification platform application bot. Use it for group command replies, with Webhooks only as a fallback notification channel.",
                callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
                callback_url_public: true,
                callback_provider: {
                    key: 'custom',
                    label: "Custom public URL",
                    host: 'ops.example.com',
                },
                callback_recommendation: "The custom public address passed the challenge probe. Complete event subscription and real group testing in the notification platform developer console.",
                enabled_notification_platform_webhook_count: 1,
                healthy_notification_platform_webhook_count: 1,
                webhook_ready: true,
                subscription_endpoint_verified: true,
                external_connected: false,
                external_connected_history_observed: false,
                external_connection_stale: false,
                external_callback_ready: true,
                platform_ready: true,
                direct_chat_ready: false,
                ready: false,
                callback_probe: {
                    attempted: true,
                    success: true,
                    issue: '',
                    summary: "The public callback address passed the active probe and is currently reachable.",
                    status_code: 200,
                    content_type: 'application/json',
                    response_excerpt: '{"challenge":"chatops-probe"}',
                    probed_at: '2026-03-18T12:20:00',
                },
                recent_chat_bindings: [],
                summary: "The notification platform application bot, platform, and public callback are ready, but no real group message has arrived. Add the bot to the target group and send a test message.",
                supported_commands: ["Status", "report <mission_id>", "test <url>"],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: null,
                latest_subscription_check_event: null,
                recent_events: [],
            },
        });
        notificationServiceMocks.unbindCommanderChatOpsAppBot.mockResolvedValue({
            status: 'success',
            message: "The application bot has been unbound from this project; only the Webhook notification channel remains.",
            app_bot_configured: false,
            app_bot_updated_at: '2026-03-19T09:00:00',
            purged: {
                checks_removed: 2,
                bindings_removed: 1,
                events_removed: 3,
            },
            overview: {
                channel: 'notification_platform',
                event_endpoint: '/api/commander/notification_platform/events',
                verification_token_configured: true,
                verification_token_masked: 'demo...oken',
                verification_token_updated_at: '2026-03-18T12:00:00',
                app_bot_configured: false,
                app_bot_ready: false,
                app_bot_id_masked: '',
                app_bot_updated_at: '2026-03-19T09:00:00',
                app_bot_check: null,
                unified_robot_target: false,
                unified_robot_platform_ready: false,
                unified_robot_ready: false,
                delivery_strategy: 'webhook_only',
                delivery_strategy_summary: "Notifications still primarily use notification platform Webhooks; the single-bot experience is not yet complete.",
                callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
                callback_url_public: true,
                callback_provider: {
                    key: 'custom',
                    label: "Custom public URL",
                    host: 'ops.example.com',
                },
                callback_recommendation: "The custom public address passed the challenge probe. Complete event subscription and real group testing in the notification platform developer console.",
                enabled_notification_platform_webhook_count: 1,
                healthy_notification_platform_webhook_count: 1,
                webhook_ready: true,
                subscription_endpoint_verified: true,
                external_connected: false,
                external_connected_history_observed: false,
                external_connection_stale: false,
                external_callback_ready: true,
                platform_ready: true,
                direct_chat_ready: false,
                ready: false,
                callback_probe: {
                    attempted: true,
                    success: true,
                    issue: '',
                    summary: "The public callback address passed the active probe and is currently reachable.",
                    status_code: 200,
                    content_type: 'application/json',
                    response_excerpt: '{"challenge":"chatops-probe"}',
                    probed_at: '2026-03-18T12:20:00',
                },
                recent_chat_bindings: [],
                summary: "The old application bot has been unbound from this project. Only Webhook notifications remain; create a dedicated bot for the testing platform.",
                supported_commands: ["Status", "report <mission_id>", "test <url>"],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: null,
                latest_subscription_check_event: null,
                recent_events: [],
            },
        });
        notificationServiceMocks.configureCommanderChatOpsToken.mockResolvedValue({
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
                unified_robot_target: false,
                unified_robot_platform_ready: false,
                unified_robot_ready: false,
                delivery_strategy: 'webhook_only',
                delivery_strategy_summary: "Notifications still primarily use notification platform Webhooks; the single-bot experience is not yet complete.",
                callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
                callback_url_public: true,
                callback_provider: {
                    key: 'custom',
                    label: "Custom public URL",
                    host: 'ops.example.com',
                },
                callback_recommendation: "The custom public address passed the challenge probe. Complete event subscription and real group testing in the notification platform developer console.",
                enabled_notification_platform_webhook_count: 1,
                healthy_notification_platform_webhook_count: 1,
                webhook_ready: true,
                subscription_endpoint_verified: false,
                external_connected: false,
                external_connected_history_observed: false,
                external_connection_stale: false,
                platform_ready: false,
                ready: false,
                summary: "The verification token is configured, but the platform event subscription challenge check has not run. Run a platform callback verification first.",
                supported_commands: ["Status", "report <mission_id>", "test <url>"],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: null,
                latest_subscription_check_event: null,
                recent_events: [],
            },
        });
        notificationServiceMocks.selfCheckCommanderChatOpsAppBot.mockResolvedValue({
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
                unified_robot_target: true,
                unified_robot_platform_ready: true,
                unified_robot_ready: false,
                delivery_strategy: 'single_robot_with_webhook_fallback',
                delivery_strategy_summary: "Expose a single notification platform application bot. Use it for group command replies, with Webhooks only as a fallback notification channel.",
                callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
                callback_url_public: true,
                enabled_notification_platform_webhook_count: 1,
                healthy_notification_platform_webhook_count: 1,
                webhook_ready: true,
                subscription_endpoint_verified: true,
                external_connected: false,
                external_connected_history_observed: false,
                external_connection_stale: false,
                external_callback_ready: true,
                platform_ready: true,
                direct_chat_ready: false,
                ready: false,
                callback_probe: {
                    attempted: true,
                    success: true,
                    issue: '',
                    summary: "The public callback address passed the active probe and is currently reachable.",
                    status_code: 200,
                    content_type: 'application/json',
                    response_excerpt: '{"challenge":"chatops-probe"}',
                    probed_at: '2026-03-18T12:20:00',
                },
                callback_probe_history: [],
                recent_chat_bindings: [],
                summary: "The notification platform application bot, platform, and public callback are ready, but no real group message has arrived. Add the bot to the target group and send a test message.",
                supported_commands: ["Status", "report <mission_id>", "test <url>"],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: null,
                latest_subscription_check_event: null,
                recent_events: [],
            },
        });
        notificationServiceMocks.configureCommanderChatOpsCallbackUrl.mockResolvedValue({
            status: 'success',
            public_api_base_url: 'https://ops.example.com',
            callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
            callback_url_public: true,
            overview: {
                channel: 'notification_platform',
                event_endpoint: '/api/commander/notification_platform/events',
                verification_token_configured: false,
                verification_token_masked: '',
                verification_token_updated_at: '',
                unified_robot_target: false,
                unified_robot_platform_ready: false,
                unified_robot_ready: false,
                delivery_strategy: 'webhook_only',
                delivery_strategy_summary: "Notifications still primarily use notification platform Webhooks; the single-bot experience is not yet complete.",
                callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
                callback_url_public: true,
                enabled_notification_platform_webhook_count: 1,
                healthy_notification_platform_webhook_count: 1,
                webhook_ready: true,
                subscription_endpoint_verified: false,
                external_connected: false,
                external_connected_history_observed: false,
                external_connection_stale: false,
                platform_ready: false,
                ready: false,
                callback_probe: {
                    attempted: true,
                    success: false,
                    issue: 'connect_error',
                    summary: "Public callback probe failed: ConnectionError",
                    status_code: null,
                    content_type: '',
                    response_excerpt: '',
                    probed_at: '2026-03-18T12:00:00',
                },
                recent_chat_bindings: [],
                summary: "The notification platform reply channel is healthy, but an event subscription verification token is still missing, so group messages cannot reliably reach the platform.",
                supported_commands: ["Status", "report <mission_id>", "test <url>"],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: null,
                latest_subscription_check_event: null,
                recent_events: [],
            },
        });
        notificationServiceMocks.restartCommanderChatOpsLocalTunnel.mockResolvedValue({
            status: 'success',
            ok: true,
            message: "Local reverse tunnel restarted.",
            stdout: 'native_ssh_reverse_tunnel_pid=1234',
            stderr: '',
            tunnel: {
                supported: true,
                script_path: 'D:/workspace/ai_test_platform/data/tools/start_native_reverse_tunnel.ps1',
                script_exists: true,
                stdout_log: 'D:/workspace/ai_test_platform/data/native_ssh_reverse_tunnel_stdout.log',
                stderr_log: 'D:/workspace/ai_test_platform/data/native_ssh_reverse_tunnel_stderr.log',
                running: true,
                pid: 1234,
                status: 'running',
                summary: "A local OpenSSH reverse tunnel process was detected (PID 1234).",
                checked_at: '2026-03-20 11:46:00',
                stdout_tail: '',
                stderr_tail: '',
            },
            overview: {
                channel: 'notification_platform',
                event_endpoint: '/api/commander/notification_platform/events',
                verification_token_configured: false,
                verification_token_masked: '',
                verification_token_updated_at: '',
                app_bot_configured: false,
                app_bot_ready: false,
                app_bot_id_masked: '',
                app_bot_updated_at: '',
                app_bot_check: null,
                unified_robot_target: false,
                unified_robot_platform_ready: false,
                unified_robot_ready: false,
                delivery_strategy: 'webhook_only',
                delivery_strategy_summary: "Notifications still primarily use notification platform Webhooks; the single-bot experience is not yet complete.",
                callback_url: 'http://127.0.0.1:8020/api/commander/notification_platform/events',
                callback_url_public: false,
                callback_provider: {
                    key: 'local',
                    label: "Local URL",
                    host: '127.0.0.1',
                },
                callback_recommendation: "Set PUBLIC_API_BASE_URL to a public address accessible to the notification platform before running the challenge probe.",
                enabled_notification_platform_webhook_count: 1,
                healthy_notification_platform_webhook_count: 1,
                webhook_ready: true,
                subscription_endpoint_verified: false,
                external_connected: false,
                external_connected_history_observed: false,
                external_connection_stale: false,
                external_callback_ready: false,
                platform_ready: false,
                direct_chat_ready: false,
                ready: false,
                callback_probe: {
                    attempted: false,
                    success: false,
                    issue: 'local_callback',
                    summary: "The URL is still local or private, so the platform does not run a public probe yet.",
                    status_code: null,
                    content_type: '',
                    response_excerpt: '',
                    probed_at: '2026-03-18T12:10:00',
                },
                local_tunnel: {
                    supported: true,
                    script_path: 'D:/workspace/ai_test_platform/data/tools/start_native_reverse_tunnel.ps1',
                    script_exists: true,
                    stdout_log: 'D:/workspace/ai_test_platform/data/native_ssh_reverse_tunnel_stdout.log',
                    stderr_log: 'D:/workspace/ai_test_platform/data/native_ssh_reverse_tunnel_stderr.log',
                    running: true,
                    pid: 1234,
                    status: 'running',
                    summary: "A local OpenSSH reverse tunnel process was detected (PID 1234).",
                    checked_at: '2026-03-20 11:46:00',
                    stdout_tail: '',
                    stderr_tail: '',
                },
                recent_chat_bindings: [],
                summary: "The notification platform reply channel is healthy, but an event subscription verification token is still missing, so group messages cannot reliably reach the platform.",
                supported_commands: ["Status", "report <mission_id>", "test <url>"],
                latest_event: {
                    id: 1,
                    channel: 'notification_platform',
                    source: 'event_subscription',
                    event_type: 'message',
                    message: 'health',
                    from_user: 'ou_demo',
                    chat_id: 'oc_demo',
                    response: "🟢 Agent status: 6/6 agents online",
                    status: 'ok',
                    delivery_configured: 1,
                    delivery_delivered: 1,
                    delivery_failed: 0,
                    created_at: '2026-03-18 11:10:00',
                },
                latest_successful_event: {
                    id: 1,
                    channel: 'notification_platform',
                    source: 'event_subscription',
                    event_type: 'message',
                    message: 'health',
                    from_user: 'ou_demo',
                    chat_id: 'oc_demo',
                    response: "🟢 Agent status: 6/6 agents online",
                    status: 'ok',
                    delivery_configured: 1,
                    delivery_delivered: 1,
                    delivery_failed: 0,
                    created_at: '2026-03-18 11:10:00',
                },
                latest_external_successful_event: null,
                latest_subscription_check_event: null,
                recent_events: [],
            },
        });
        notificationServiceMocks.selfCheckCommanderChatOpsSubscription.mockResolvedValue({
            status: 'success',
            result: { challenge: 'codex-self-check' },
            overview: {
                channel: 'notification_platform',
                event_endpoint: '/api/commander/notification_platform/events',
                verification_token_configured: true,
                verification_token_masked: 'demo...oken',
                verification_token_updated_at: '2026-03-18T12:00:00',
                unified_robot_target: false,
                unified_robot_platform_ready: true,
                unified_robot_ready: false,
                delivery_strategy: 'webhook_only',
                delivery_strategy_summary: "Notifications still primarily use notification platform Webhooks; the single-bot experience is not yet complete.",
                callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
                callback_url_public: true,
                enabled_notification_platform_webhook_count: 1,
                healthy_notification_platform_webhook_count: 1,
                webhook_ready: true,
                subscription_endpoint_verified: true,
                external_connected: false,
                external_connected_history_observed: false,
                external_connection_stale: false,
                platform_ready: true,
                ready: false,
                callback_probe: {
                    attempted: true,
                    success: true,
                    issue: '',
                    summary: "The public callback address passed the active probe and is currently reachable.",
                    status_code: 200,
                    content_type: 'application/json',
                    response_excerpt: '{"challenge":"chatops-probe"}',
                    probed_at: '2026-03-18T12:05:00',
                },
                recent_chat_bindings: [],
                summary: "Platform event subscription is ready, but no real notification platform text message has arrived. Complete event subscription in the developer console and send a test message.",
                supported_commands: ["Status", "report <mission_id>", "test <url>"],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: null,
                latest_subscription_check_event: {
                    id: 2,
                    channel: 'notification_platform',
                    source: 'subscription_self_check',
                    event_type: 'url_verification',
                    message: 'url_verification',
                    from_user: '',
                    chat_id: '',
                    response: 'challenge accepted',
                    status: 'verified',
                    delivery_configured: 0,
                    delivery_delivered: 0,
                    delivery_failed: 0,
                    created_at: '2026-03-18 12:05:00',
                },
                recent_events: [],
            },
        });
        notificationServiceMocks.simulateCommanderChatOps.mockResolvedValue({
            status: 'success',
            result: {
                response: "🟢 Agent status: 6/6 agents online",
                run: {
                    run_id: 'run-simulated',
                },
            },
            delivery: { configured: 1, delivered: 1, failed: 0, message: "Sent successfully" },
            overview: {
                channel: 'notification_platform',
                event_endpoint: '/api/commander/notification_platform/events',
                verification_token_configured: false,
                verification_token_masked: '',
                verification_token_updated_at: '',
                unified_robot_target: false,
                unified_robot_platform_ready: false,
                unified_robot_ready: false,
                delivery_strategy: 'webhook_only',
                delivery_strategy_summary: "Notifications still primarily use notification platform Webhooks; the single-bot experience is not yet complete.",
                callback_url: 'http://127.0.0.1:8020/api/commander/notification_platform/events',
                callback_url_public: false,
                enabled_notification_platform_webhook_count: 1,
                healthy_notification_platform_webhook_count: 1,
                webhook_ready: true,
                subscription_endpoint_verified: false,
                external_connected: false,
                external_connected_history_observed: false,
                external_connection_stale: false,
                platform_ready: false,
                ready: false,
                callback_probe: {
                    attempted: false,
                    success: false,
                    issue: 'local_callback',
                    summary: "The URL is still local or private, so the platform does not run a public probe yet.",
                    status_code: null,
                    content_type: '',
                    response_excerpt: '',
                    probed_at: '2026-03-18T12:15:00',
                },
                summary: "The notification platform reply channel is healthy, but an event subscription verification token is still missing, so group messages cannot reliably reach the platform.",
                supported_commands: ["Status", "report <mission_id>", "test <url>"],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: null,
                latest_subscription_check_event: null,
                recent_events: [],
            },
        });
        notificationServiceMocks.runCommanderChatOpsExternalSelfCheck.mockResolvedValue({
            status: 'success',
            callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
            challenge: 'external-self-check-1234',
            challenge_check: {
                label: 'challenge',
                ok: true,
                status_code: 200,
                body_excerpt: '{"challenge":"external-self-check-1234"}',
                challenge_matched: true,
            },
            message_check: {
                label: 'message',
                ok: true,
                status_code: 200,
                body_excerpt: '{"status":"ok"}',
                command_response: "📡 Agent status\n• Registered agents: 6\n• Healthy heartbeats: 6/6",
                delivery: {
                    configured: 1,
                    delivered: 1,
                    failed: 0,
                },
            },
            overview: {
                channel: 'notification_platform',
                event_endpoint: '/api/commander/notification_platform/events',
                verification_token_configured: true,
                verification_token_masked: 'demo...oken',
                verification_token_updated_at: '2026-03-18T12:00:00',
                callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
                callback_url_public: true,
                callback_provider: {
                    key: 'custom',
                    label: "Custom public URL",
                    host: 'ops.example.com',
                },
                callback_recommendation: "The custom public address passed the challenge probe. Complete event subscription and real group testing in the notification platform developer console.",
                enabled_notification_platform_webhook_count: 1,
                healthy_notification_platform_webhook_count: 1,
                webhook_ready: true,
                subscription_endpoint_verified: true,
                external_connected: true,
                external_connected_current: true,
                external_connected_history_observed: true,
                external_connection_stale: false,
                external_callback_ready: true,
                platform_ready: true,
                direct_chat_ready: true,
                app_bot_configured: true,
                app_bot_id_masked: 'cli...bot',
                app_bot_updated_at: '2026-03-18T12:30:00',
                ready: true,
                callback_probe: {
                    attempted: true,
                    success: true,
                    issue: '',
                    summary: "The public callback address passed the active probe and is currently reachable.",
                    status_code: 200,
                    content_type: 'application/json',
                    response_excerpt: '{"challenge":"external-self-check-1234"}',
                    probed_at: '2026-03-18T12:20:00',
                },
                callback_probe_history: [],
                summary: "The notification platform two-way connection is ready.",
                supported_commands: ["Status", "report <mission_id>", "test <url>"],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: {
                    id: 11,
                    channel: 'notification_platform',
                    source: 'event_subscription',
                    event_type: 'message',
                    message: "Status",
                    from_user: 'ou_demo',
                    chat_id: 'oc_demo',
                    response: "📡 Agent status",
                    status: 'ok',
                    delivery_configured: 1,
                    delivery_delivered: 1,
                    delivery_failed: 0,
                    created_at: '2026-03-18 12:35:00',
                },
                latest_external_success_at: '2026-03-18 12:35:00',
                latest_subscription_check_event: null,
                recent_events: [],
            },
        });
        notificationServiceMocks.refreshCommanderChatOpsProbe.mockResolvedValue({
            status: 'success',
            probe: {
                attempted: true,
                success: false,
                issue: 'connect_error',
                summary: "Public callback probe failed: ConnectionError",
                status_code: null,
                content_type: '',
                response_excerpt: '',
                probed_at: '2026-03-18T12:40:00',
            },
            overview: {
                channel: 'notification_platform',
                event_endpoint: '/api/commander/notification_platform/events',
                verification_token_configured: true,
                verification_token_masked: 'demo...oken',
                verification_token_updated_at: '2026-03-18T12:00:00',
                app_bot_configured: false,
                app_bot_id_masked: '',
                app_bot_updated_at: '',
                callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
                callback_url_public: true,
                callback_provider: {
                    key: 'custom',
                    label: "Custom public URL",
                    host: 'ops.example.com',
                },
                callback_recommendation: "The custom public address is currently unreachable. Check that the tunnel is running and the public domain still points to local port 8020.",
                enabled_notification_platform_webhook_count: 1,
                healthy_notification_platform_webhook_count: 1,
                webhook_ready: true,
                subscription_endpoint_verified: true,
                external_connected: false,
                external_connected_history_observed: true,
                external_connection_stale: true,
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
                    probed_at: '2026-03-18T12:40:00',
                },
                callback_probe_history: [
                    {
                        id: 9,
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
                        created_at: '2026-03-18 12:40:00',
                    },
                    {
                        id: 8,
                        callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
                        attempted: true,
                        success: false,
                        issue: 'timeout',
                        summary: "The public callback probe timed out; the notification platform is unlikely to reach this endpoint reliably right now.",
                        status_code: null,
                        content_type: '',
                        response_excerpt: '',
                        source: 'overview',
                        force_refresh: false,
                        created_at: '2026-03-18 12:35:00',
                    },
                ],
                summary: "Public callback probe failed: ConnectionError",
                supported_commands: ["Status", "report <mission_id>", "test <url>"],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: {
                    id: 7,
                    channel: 'notification_platform',
                    source: 'event_subscription',
                    event_type: 'message',
                    message: "Status",
                    from_user: 'ou_demo',
                    chat_id: 'oc_demo',
                    response: "🟢 Agent status: 6/6 agents online",
                    status: 'ok',
                    delivery_configured: 1,
                    delivery_delivered: 1,
                    delivery_failed: 0,
                    created_at: '2026-03-18 12:25:00',
                },
                latest_external_success_at: '2026-03-18 12:25:00',
                latest_subscription_check_event: null,
                recent_events: [],
            },
        });
    });

    it('should render masked webhook url without exposing raw token', async () => {
        render(<NotificationPage />);

        await waitFor(() => {
            expect(notificationServiceMocks.getNotificationOverview).toHaveBeenCalledTimes(1);
            expect(notificationServiceMocks.getCommanderChatOpsOverview).toHaveBeenCalledTimes(1);
        });

        expect(await screen.findByText('NotificationPlatform Production Alert')).toBeInTheDocument();
        expect(screen.getByText('https://open.notification_platform.cn/open-apis/bot/v2/hook/b23a...6e0b')).toBeInTheDocument();
        expect(screen.queryByText(/b23a4f19-0226-4f5d-ba1d-8cfd33736e0b/)).not.toBeInTheDocument();
        expect(screen.getByText("Notification platform setup")).toBeInTheDocument();
        expect(screen.getByText(/A custom webhook bot only receives platform notifications/)).toBeInTheDocument();
        expect(screen.getByText("Notification entry point roles")).toBeInTheDocument();
        expect(screen.getByTestId('notification_platform-role-card-group-notify')).toBeInTheDocument();
        expect(screen.getByTestId('notification_platform-role-card-bot-command')).toBeInTheDocument();
        expect(screen.getByTestId('chatops-overview-card-notify')).toHaveTextContent("Testing platform group");
        expect(screen.getByText("AI Test Platform bot")).toBeInTheDocument();
        expect(screen.getByText("Connection: Platform → group")).toBeInTheDocument();
        expect(screen.getByText("Connection: You → platform → you")).toBeInTheDocument();
        expect(screen.getAllByText(/\/api\/commander\/notification_platform\/events/).length).toBeGreaterThan(0);
        expect(screen.getByText("Two-way notification commands")).toBeInTheDocument();
        expect(screen.getByText("The notification platform reply channel is healthy, but an event subscription verification token is still missing, so group messages cannot reliably reach the platform.")).toBeInTheDocument();
        expect(screen.getByText("Public endpoint probe")).toBeInTheDocument();
        expect(screen.getAllByText(/The callback URL is still local or private/).length).toBeGreaterThan(0);
        expect(screen.getByText("Local URL · 127.0.0.1")).toBeInTheDocument();
        expect(screen.getAllByText(/PUBLIC_API_BASE_URL/).length).toBeGreaterThan(0);
        expect(screen.getByText(/Message: health/)).toBeInTheDocument();
        expect(screen.getByText(/Reply: 🟢 Agent status: 6\/6 agents online/)).toBeInTheDocument();
        expect(screen.getByText(/Command: platform.status · run_id: run-health/)).toBeInTheDocument();
        expect(screen.getByRole('link', { name: "Open Legion control center" })).toHaveAttribute('href', '/legion?tab=control');
        expect(screen.getByRole('link', { name: "Open this command's Legion details" })).toHaveAttribute('href', '/legion?tab=control&run=run-health');
        expect(screen.getAllByText("Platform self-check").length).toBeGreaterThan(0);
        expect(screen.getByText("The callback URL is still local")).toBeInTheDocument();
        expect(screen.getByText("Event subscription settings")).toBeInTheDocument();
        expect(screen.getByText("No token generated yet")).toBeInTheDocument();
        expect(screen.getByText(/The callback URL is still local or private/)).toBeInTheDocument();
        expect(screen.getByText("Project-specific notification app bot configuration")).toBeInTheDocument();
        expect(screen.getByText(/This project has no dedicated app bot/)).toBeInTheDocument();
        expect(screen.getByText("Notification platform developer console checklist")).toBeInTheDocument();
        expect(screen.getByText("App bot configuration still required")).toBeInTheDocument();
    });

    it('should simulate chatops command from notification page', async () => {
        render(<NotificationPage />);

        await screen.findAllByText("Platform self-check");
        fireEvent.click(screen.getByRole('button', { name: "Simulate notification command" }));

        await waitFor(() => {
            expect(notificationServiceMocks.simulateCommanderChatOps).toHaveBeenCalledWith({
                message: "Status",
                from_user: 'notification_debug',
                chat_id: 'notification_debug_chat',
                deliver: true,
            });
        });

        expect(await screen.findByText(/Latest simulation/)).toBeInTheDocument();
        expect(screen.getByText(/Current status: The notification platform reply channel is healthy, but an event subscription verification token is still missing/)).toBeInTheDocument();
        expect(screen.getByText(/Linked run_id: run-simulated/)).toBeInTheDocument();
        expect(screen.getByRole('link', { name: "Open linked command" })).toHaveAttribute('href', '/legion?tab=control&run=run-simulated');
    });

    it('should run external self check and render public chain result', async () => {
        notificationServiceMocks.getCommanderChatOpsOverview.mockResolvedValue({
            channel: 'notification_platform',
            event_endpoint: '/api/commander/notification_platform/events',
            verification_token_configured: true,
            verification_token_masked: 'demo...oken',
            verification_token_updated_at: '2026-03-18T12:00:00',
            app_bot_configured: true,
            app_bot_id_masked: 'cli...bot',
            app_bot_updated_at: '2026-03-18T12:30:00',
            callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
            callback_url_public: true,
            callback_provider: {
                key: 'custom',
                label: "Custom public URL",
                host: 'ops.example.com',
            },
            callback_recommendation: "The custom public address passed the challenge probe. Complete event subscription and real group testing in the notification platform developer console.",
            enabled_notification_platform_webhook_count: 1,
            healthy_notification_platform_webhook_count: 1,
            webhook_ready: true,
            subscription_endpoint_verified: true,
            external_connected: true,
            external_connected_history_observed: true,
            external_connection_stale: false,
            external_callback_ready: true,
            platform_ready: true,
            direct_chat_ready: true,
            ready: true,
            callback_probe: {
                attempted: true,
                success: true,
                issue: '',
                summary: "The public callback address passed the active probe and is currently reachable.",
                status_code: 200,
                content_type: 'application/json',
                response_excerpt: '{"challenge":"external-self-check-1234"}',
                probed_at: '2026-03-18T12:20:00',
            },
            callback_probe_history: [],
            summary: "The notification platform two-way connection is ready.",
            supported_commands: ["Status", "report <mission_id>", "test <url>"],
            latest_event: null,
            latest_successful_event: null,
            latest_external_successful_event: null,
            latest_subscription_check_event: null,
            recent_events: [],
        });

        render(<NotificationPage />);

        await screen.findByText("The notification platform two-way connection is ready.");
        const externalSelfCheckButton = await screen.findByRole('button', { name: "Run public connection self-test" });
        await waitFor(() => {
            expect(externalSelfCheckButton).not.toBeDisabled();
        });
        fireEvent.click(externalSelfCheckButton);

        await waitFor(() => {
            expect(notificationServiceMocks.runCommanderChatOpsExternalSelfCheck).toHaveBeenCalledTimes(1);
        });

        await waitFor(() => {
            expect(screen.getAllByText("Public connection self-test").length).toBeGreaterThan(0);
        });
        expect(screen.getByText(/URL: https:\/\/ops\.example\.com\/api\/commander\/notification_platform\/events/)).toBeInTheDocument();
        expect(screen.getByText(/challenge: Passed · HTTP 200/)).toBeInTheDocument();
        expect(screen.getByText(/Text message: Passed · HTTP 200 · Reply delivery 1\/1/)).toBeInTheDocument();
        expect(screen.getByText(/Reply: 📡 Agent status/)).toBeInTheDocument();
    });

    it('should render persisted latest external self check status from overview', async () => {
        notificationServiceMocks.getCommanderChatOpsOverview.mockResolvedValue({
            channel: 'notification_platform',
            event_endpoint: '/api/commander/notification_platform/events',
            verification_token_configured: true,
            verification_token_masked: 'demo...oken',
            verification_token_updated_at: '2026-03-18T12:00:00',
            app_bot_configured: false,
            app_bot_id_masked: '',
            app_bot_updated_at: '',
            callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
            callback_url_public: true,
            callback_provider: {
                key: 'custom',
                label: "Custom public URL",
                host: 'ops.example.com',
            },
            callback_recommendation: "The current public address passed the platform public self-test, so challenge and text messages reach the callback. Complete event subscription in the developer console, then send a real group message for final integration testing.",
            enabled_notification_platform_webhook_count: 1,
            healthy_notification_platform_webhook_count: 1,
            webhook_ready: true,
            subscription_endpoint_verified: true,
            external_connected: false,
            external_connected_current: false,
            external_connected_history_observed: false,
            external_connection_stale: false,
            external_self_check_recent_success: true,
            external_callback_ready: true,
            platform_ready: true,
            direct_chat_ready: false,
            ready: false,
            callback_probe: {
                attempted: true,
                success: false,
                issue: 'timeout',
                summary: "Public callback probe failed: timeout",
                status_code: 0,
                content_type: '',
                response_excerpt: 'timeout',
                probed_at: '2026-03-18T12:20:00',
            },
            callback_probe_history: [],
            summary: "The latest platform public self-test passed: the callback, challenge, and text message path work. This does not verify real group messaging; send a real message in the target group to complete verification.",
            supported_commands: ["Status", "report <mission_id>", "test <url>"],
            latest_event: null,
            latest_successful_event: null,
            latest_external_successful_event: null,
            latest_external_success_at: '',
            latest_external_self_check_event: {
                id: 21,
                channel: 'notification_platform',
                source: 'external_self_check',
                event_type: 'message',
                message: 'status',
                from_user: 'user',
                chat_id: 'oc_external_self_check',
                response: "📡 Agent status",
                status: 'ok',
                delivery_configured: 1,
                delivery_delivered: 1,
                delivery_failed: 0,
                created_at: '2026-03-18 12:35:00',
            },
            latest_external_self_check_at: '2026-03-18 12:35:00',
            latest_subscription_check_event: null,
            recent_events: [],
        });

        render(<NotificationPage />);

        const verifiedCard = await screen.findByTestId('chatops-overview-card-verified');
        await waitFor(() => {
            expect(verifiedCard).toHaveTextContent("Latest public connection self-test");
        });
        expect(screen.getByText(/Status: Passed/)).toBeInTheDocument();
        expect(screen.getByText(/The platform most recently verified both challenges and text messages through the public endpoint/)).toBeInTheDocument();
        expect(screen.getByText(/this does not yet confirm that real notification group message integration is complete/)).toBeInTheDocument();
        expect(screen.getByText(/Latest reply: 📡 Agent status/)).toBeInTheDocument();
    });

    it('should configure public callback url from notification page', async () => {
        render(<NotificationPage />);

        await screen.findByText("Public callback URL configuration");
        const callbackInput = await screen.findByDisplayValue('http://127.0.0.1:8020');
        fireEvent.change(callbackInput, {
            target: { value: 'https://ops.example.com' },
        });
        await waitFor(() => {
            expect(callbackInput).toHaveValue('https://ops.example.com');
        });
        fireEvent.click(screen.getByRole('button', { name: "Save public URL" }));

        await waitFor(() => {
            expect(notificationServiceMocks.configureCommanderChatOpsCallbackUrl).toHaveBeenCalledWith({
                public_api_base_url: 'https://ops.example.com',
            });
        });

        expect(await screen.findByText(/Public base URL saved/)).toBeInTheDocument();
        expect(screen.getAllByText('https://ops.example.com/api/commander/notification_platform/events').length).toBeGreaterThan(0);
    });

    it('should refresh callback probe and render recent probe history', async () => {
        render(<NotificationPage />);

        await screen.findByText("Public callback URL configuration");
        fireEvent.click(screen.getByRole('button', { name: "Retry probe now" }));

        await waitFor(() => {
            expect(notificationServiceMocks.refreshCommanderChatOpsProbe).toHaveBeenCalledTimes(1);
        });

        expect(await screen.findByText("Latest manual retry")).toBeInTheDocument();
        expect(screen.getAllByText("Public callback probe failed: ConnectionError").length).toBeGreaterThan(0);
        expect(screen.getByText("Recent probe records")).toBeInTheDocument();
        expect(screen.getByText("Manual retry")).toBeInTheDocument();
        expect(screen.getByText("Force refresh")).toBeInTheDocument();
        expect(screen.getByText(/the public probe now fails. The public endpoint has degraded/)).toBeInTheDocument();
        expect(screen.getByText(/Previously successful/)).toBeInTheDocument();
        expect(screen.getByText("Custom public URL · ops.example.com")).toBeInTheDocument();
        expect(screen.getAllByText(/Suggested action: The custom public address is currently unreachable/).length).toBeGreaterThan(0);
    });

    it('should restart local tunnel from notification page', async () => {
        render(<NotificationPage />);

        await screen.findByText("Local reverse tunnel");
        expect(screen.getByText(/Unsupported in this environment|Script missing|Running|Not running/)).toBeInTheDocument();
        const restartButton = screen.getByRole('button', { name: "Restart local tunnel" });
        await waitFor(() => {
            expect(restartButton).not.toBeDisabled();
        });
        fireEvent.click(restartButton);

        await waitFor(() => {
            expect(notificationServiceMocks.restartCommanderChatOpsLocalTunnel).toHaveBeenCalledTimes(1);
        });

        expect(await screen.findByText("Latest tunnel restart")).toBeInTheDocument();
        expect(screen.getByText("Local reverse tunnel restarted.")).toBeInTheDocument();
        expect(screen.getByText(/Running · PID 1234/)).toBeInTheDocument();
    });

    it('should configure app bot credentials from notification page', async () => {
        render(<NotificationPage />);

        await screen.findByText("Project-specific notification app bot configuration");
        fireEvent.change(screen.getByPlaceholderText("Project-specific notification app ID"), {
            target: { value: 'cli_demo_bot' },
        });
        fireEvent.change(screen.getByPlaceholderText("Project-specific notification app secret"), {
            target: { value: 'secret-demo' },
        });
        fireEvent.click(screen.getByRole('button', { name: "Save app bot" }));

        await waitFor(() => {
            expect(notificationServiceMocks.configureCommanderChatOpsAppBot).toHaveBeenCalledWith({
                app_id: 'cli_demo_bot',
                app_secret: 'secret-demo',
            });
        });

        expect(await screen.findByText(/App bot configuration saved/)).toBeInTheDocument();
        expect(screen.getByText(/tenant_access_token/)).toBeInTheDocument();
    });

    it('should unbind app bot credentials from notification page', async () => {
        notificationServiceMocks.getCommanderChatOpsOverview.mockResolvedValueOnce({
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
            unified_robot_target: true,
            unified_robot_platform_ready: true,
            unified_robot_ready: false,
            delivery_strategy: 'single_robot_with_webhook_fallback',
            delivery_strategy_summary: "Expose a single notification platform application bot. Use it for group command replies, with Webhooks only as a fallback notification channel.",
            callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
            callback_url_public: true,
            enabled_notification_platform_webhook_count: 1,
            healthy_notification_platform_webhook_count: 1,
            webhook_ready: true,
            subscription_endpoint_verified: true,
            external_connected: false,
            external_connected_history_observed: false,
            external_connection_stale: false,
            external_callback_ready: true,
            platform_ready: true,
            direct_chat_ready: false,
            ready: false,
            callback_probe: {
                attempted: true,
                success: true,
                issue: '',
                summary: "The public callback address passed the active probe and is currently reachable.",
                status_code: 200,
                content_type: 'application/json',
                response_excerpt: '{"challenge":"chatops-probe"}',
                probed_at: '2026-03-18T12:20:00',
            },
            recent_chat_bindings: [],
            summary: "The notification platform application bot, platform, and public callback are ready.",
            supported_commands: ["Status", "report <mission_id>", "test <url>"],
            latest_event: null,
            latest_successful_event: null,
            latest_external_successful_event: null,
            latest_subscription_check_event: null,
            recent_events: [],
        });

        render(<NotificationPage />);

        const unbindButton = await screen.findByRole('button', { name: "Unbind current app bot" });
        await waitFor(() => {
            expect(unbindButton).not.toBeDisabled();
        });
        fireEvent.click(unbindButton);

        await waitFor(() => {
            expect(notificationServiceMocks.unbindCommanderChatOpsAppBot).toHaveBeenCalledWith({ purge_history: true });
        });

        expect(await screen.findByText("Project app bot unbound")).toBeInTheDocument();
        expect(screen.getByText(/Cleared: app verifications 2/)).toBeInTheDocument();
    });

    it('should self check app bot credentials from notification page', async () => {
        notificationServiceMocks.getCommanderChatOpsOverview.mockResolvedValueOnce({
            channel: 'notification_platform',
            event_endpoint: '/api/commander/notification_platform/events',
            verification_token_configured: true,
            verification_token_masked: 'demo...oken',
            verification_token_updated_at: '2026-03-18T12:00:00',
            app_bot_configured: true,
            app_bot_ready: false,
            app_bot_id_masked: 'cli...bot',
            app_bot_updated_at: '2026-03-18T12:30:00',
            app_bot_check: {
                id: 1,
                success: false,
                message: "The latest verification failed.",
                status_code: 401,
                source: 'config_save',
                app_id_masked: 'cli...bot',
                created_at: '2026-03-18 12:30:00',
            },
            unified_robot_target: true,
            unified_robot_platform_ready: false,
            unified_robot_ready: false,
            delivery_strategy: 'single_robot_with_webhook_fallback',
            delivery_strategy_summary: "Expose a single notification platform application bot. Use it for group command replies, with Webhooks only as a fallback notification channel.",
            callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
            callback_url_public: true,
            enabled_notification_platform_webhook_count: 1,
            healthy_notification_platform_webhook_count: 1,
            webhook_ready: true,
            subscription_endpoint_verified: true,
            external_connected: false,
            external_connected_history_observed: false,
            external_connection_stale: false,
            external_callback_ready: true,
            platform_ready: true,
            direct_chat_ready: false,
            ready: false,
            callback_probe: {
                attempted: true,
                success: true,
                issue: '',
                summary: "The public callback address passed the active probe and is currently reachable.",
                status_code: 200,
                content_type: 'application/json',
                response_excerpt: '{"challenge":"chatops-probe"}',
                probed_at: '2026-03-18T12:20:00',
            },
            callback_probe_history: [],
            recent_chat_bindings: [],
            summary: "The notification platform application bot is configured, but its latest credential verification failed.",
            supported_commands: ["Status", "report <mission_id>", "test <url>"],
            latest_event: null,
            latest_successful_event: null,
            latest_external_successful_event: null,
            latest_subscription_check_event: null,
            recent_events: [],
        });

        render(<NotificationPage />);

        await screen.findByText("App bot credential verification");
        fireEvent.click(screen.getByRole('button', { name: "Verify app bot" }));

        await waitFor(() => {
            expect(notificationServiceMocks.selfCheckCommanderChatOpsAppBot).toHaveBeenCalledTimes(1);
        });

        expect(await screen.findByText("Latest manual verification")).toBeInTheDocument();
        expect(screen.getAllByText(/Application bot credentials verified/).length).toBeGreaterThan(0);
    });

    it('should render single-robot strategy with webhook fallback after app bot is configured', async () => {
        render(<NotificationPage />);

        await screen.findByText("External bot configuration");
        expect(screen.getByText("Unified bot setup in progress")).toBeInTheDocument();
        expect(screen.getByText("Webhook bot only")).toBeInTheDocument();

        fireEvent.change(screen.getByPlaceholderText("Project-specific notification app ID"), {
            target: { value: 'cli_demo_bot' },
        });
        fireEvent.change(screen.getByPlaceholderText("Project-specific notification app secret"), {
            target: { value: 'secret-demo' },
        });
        fireEvent.click(screen.getByRole('button', { name: "Save app bot" }));

        expect(await screen.findByText("Unified bot awaiting group test")).toBeInTheDocument();
        expect(screen.getByText("App bot primary channel with webhook fallback")).toBeInTheDocument();
        expect(screen.getAllByText(/Webhooks only as a fallback notification channel/)).not.toHaveLength(0);
    });

    it('should render recent chat bindings with reply mode labels', async () => {
        notificationServiceMocks.getCommanderChatOpsOverview.mockResolvedValueOnce({
            channel: 'notification_platform',
            event_endpoint: '/api/commander/notification_platform/events',
            verification_token_configured: true,
            verification_token_masked: 'demo...oken',
            verification_token_updated_at: '2026-03-18T12:00:00',
            app_bot_configured: true,
            app_bot_id_masked: 'cli...bot',
            app_bot_updated_at: '2026-03-18T12:30:00',
            unified_robot_target: true,
            unified_robot_platform_ready: true,
            unified_robot_ready: false,
            delivery_strategy: 'single_robot_with_webhook_fallback',
            delivery_strategy_summary: "Expose a single notification platform application bot. Use it for group command replies, with Webhooks only as a fallback notification channel.",
            callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
            callback_url_public: true,
            enabled_notification_platform_webhook_count: 1,
            healthy_notification_platform_webhook_count: 1,
            webhook_ready: true,
            subscription_endpoint_verified: true,
            external_connected: false,
            external_connected_history_observed: false,
            external_connection_stale: false,
            external_callback_ready: true,
            platform_ready: true,
            direct_chat_ready: false,
            ready: false,
            callback_probe: {
                attempted: true,
                success: true,
                issue: '',
                summary: "The public callback address passed the active probe and is currently reachable.",
                status_code: 200,
                content_type: 'application/json',
                response_excerpt: '{"challenge":"chatops-probe"}',
                probed_at: '2026-03-18T12:20:00',
            },
            callback_probe_history: [],
            recent_chat_bindings: [
                {
                    chat_id: 'oc_group_a',
                    channel: 'notification_platform',
                    source: 'event_subscription',
                    last_from_user: 'ou_demo_a',
                    last_message: "Status",
                    last_seen_at: '2026-03-18 12:31:00',
                    last_reply_mode: 'app_bot',
                    last_delivery_ok: 1,
                    last_run_id: 'run-group-a',
                    last_command_id: 'platform.status',
                    last_requester_id: 'user_a',
                    binding_status: 'bound',
                },
                {
                    chat_id: 'oc_group_b',
                    channel: 'notification_platform',
                    source: 'simulate',
                    last_from_user: 'ou_demo_b',
                    last_message: "report 125c69cd",
                    last_seen_at: '2026-03-18 12:32:00',
                    last_reply_mode: 'app_bot_fallback_webhook',
                    last_delivery_ok: 0,
                    last_run_id: 'run-group-b',
                    last_command_id: 'commander.mission.report',
                    last_requester_id: 'user_b',
                    binding_status: 'bound',
                },
            ],
            summary: "The notification platform application bot, platform, and public callback are ready, but no real group message has arrived. Add the bot to the target group and send a test message.",
            supported_commands: ["Status", "report <mission_id>", "test <url>"],
            latest_event: null,
            latest_successful_event: null,
            latest_external_successful_event: null,
            latest_subscription_check_event: null,
            recent_events: [],
        });

        render(<NotificationPage />);

        const bindingList = await screen.findByTestId('chatops-binding-list');
        expect(bindingList).toBeInTheDocument();
        expect(within(bindingList).getAllByTestId('chatops-binding-item')).toHaveLength(2);
        expect(within(bindingList).getByText("App bot")).toBeInTheDocument();
        expect(within(bindingList).getByText("App bot failed; webhook fallback used")).toBeInTheDocument();
        expect(within(bindingList).getByText("Notification platform event subscription")).toBeInTheDocument();
        expect(within(bindingList).getByText("Platform simulation")).toBeInTheDocument();
        expect(within(bindingList).getAllByRole('link', { name: "View linked command" })).toHaveLength(2);
    });

    it('should render degraded direct chat status when historical chat succeeded but current public callback is stale', async () => {
        notificationServiceMocks.getCommanderChatOpsOverview.mockResolvedValueOnce({
            channel: 'notification_platform',
            event_endpoint: '/api/commander/notification_platform/events',
            verification_token_configured: true,
            verification_token_masked: 'demo...oken',
            verification_token_updated_at: '2026-03-20T11:00:00',
            app_bot_configured: true,
            app_bot_ready: true,
            app_bot_id_masked: 'cli...bot',
            app_bot_updated_at: '2026-03-20T10:58:00',
            app_bot_check: {
                id: 3,
                success: true,
                message: "Application bot credentials verified; tenant_access_token obtained successfully.",
                status_code: 200,
                source: 'config_save',
                app_id_masked: 'cli...bot',
                created_at: '2026-03-20 10:58:12',
            },
            unified_robot_target: true,
            unified_robot_platform_ready: false,
            unified_robot_ready: false,
            delivery_strategy: 'single_robot_with_webhook_fallback',
            delivery_strategy_summary: "Expose only the dedicated application bot for this project. Use it for group command replies, with Webhooks only as a fallback notification channel.",
            callback_url: 'https://test.example-user.top:8443/api/commander/notification_platform/events',
            callback_url_public: true,
            callback_provider: {
                key: 'custom',
                label: "Custom public URL",
                host: 'test.example-user.top',
            },
            callback_recommendation: "The custom public address probe timed out. Use a more stable public endpoint or check whether network policy blocks the tunnel.",
            enabled_notification_platform_webhook_count: 1,
            healthy_notification_platform_webhook_count: 1,
            webhook_ready: true,
            subscription_endpoint_verified: true,
            external_connected: false,
            external_connected_current: false,
            external_connected_history_observed: true,
            external_connection_stale: true,
            external_callback_ready: false,
            platform_ready: true,
            direct_chat_ready: false,
            ready: false,
            callback_probe: {
                attempted: true,
                success: false,
                issue: 'timeout',
                summary: "The public callback probe timed out; the notification platform is unlikely to reach this endpoint reliably right now.",
                status_code: null,
                content_type: '',
                response_excerpt: '',
                probed_at: '2026-03-20T11:36:42',
            },
            callback_probe_history: [],
            recent_chat_bindings: [
                {
                    chat_id: 'oc_group_a',
                    channel: 'notification_platform',
                    source: 'event_subscription',
                    last_from_user: 'ou_demo_a',
                    last_message: "Status",
                    last_seen_at: '2026-03-20 10:49:47',
                    last_reply_mode: 'app_bot',
                    last_delivery_ok: 1,
                },
            ],
            summary: "The public callback probe timed out, but the platform previously received real notification platform messages.",
            supported_commands: ["Status", "report <mission_id>", "test <url>"],
            latest_event: {
                id: 219,
                channel: 'notification_platform',
                source: 'event_subscription',
                event_type: 'url_verification',
                message: 'url_verification',
                from_user: '',
                chat_id: '',
                response: 'challenge accepted',
                status: 'verified',
                delivery_configured: 0,
                delivery_delivered: 0,
                delivery_failed: 0,
                created_at: '2026-03-20 11:36:42',
            },
            latest_successful_event: {
                id: 217,
                channel: 'notification_platform',
                source: 'event_subscription',
                event_type: 'message',
                message: "Hello",
                from_user: 'user',
                chat_id: 'oc_group_a',
                response: "Received",
                status: 'ok',
                delivery_configured: 1,
                delivery_delivered: 1,
                delivery_failed: 0,
                created_at: '2026-03-20 10:49:47',
            },
            latest_external_successful_event: {
                id: 217,
                channel: 'notification_platform',
                source: 'event_subscription',
                event_type: 'message',
                message: "Hello",
                from_user: 'user',
                chat_id: 'oc_group_a',
                response: "Received",
                status: 'ok',
                delivery_configured: 1,
                delivery_delivered: 1,
                delivery_failed: 0,
                created_at: '2026-03-20 10:49:47',
            },
            latest_external_success_at: '2026-03-20 10:49:47',
            latest_subscription_check_event: {
                id: 219,
                channel: 'notification_platform',
                source: 'event_subscription',
                event_type: 'url_verification',
                message: 'url_verification',
                from_user: '',
                chat_id: '',
                response: 'challenge accepted',
                status: 'verified',
                delivery_configured: 0,
                delivery_delivered: 0,
                delivery_failed: 0,
                created_at: '2026-03-20 11:36:42',
            },
            recent_events: [],
        });

        render(<NotificationPage />);

        expect(await screen.findByText("Previously connected")).toBeInTheDocument();
        expect(screen.getByText("Current notification platform usage")).toBeInTheDocument();
        expect(screen.getByTestId('chatops-current-usage')).toHaveTextContent("Previously available; endpoint restoration required");
        expect(screen.getByText("Current command entry point: Direct messaging worked previously; the public endpoint is currently degraded")).toBeInTheDocument();
        expect(screen.getByText("Unified bot endpoint degraded")).toBeInTheDocument();
        expect(screen.getByText(/The most recent real direct message succeeded/)).toBeInTheDocument();
        expect(screen.getByTestId('chatops-overview-card-entry')).toHaveTextContent("Direct messaging worked previously; the public endpoint is currently degraded");
        expect(screen.getByTestId('chatops-overview-card-verified')).toHaveTextContent("Latest actual inbound notification event");
        expect(screen.getByTestId('chatops-overview-card-notify')).toHaveTextContent("Testing platform group");
    });

    it('should copy callback url and setup guide from notification page', async () => {
        render(<NotificationPage />);

        await screen.findByText("Notification platform developer console checklist");
        fireEvent.click(screen.getByRole('button', { name: "Copy callback URL" }));

        await waitFor(() => {
            expect(clipboardWriteText).toHaveBeenCalledWith('http://127.0.0.1:8020/api/commander/notification_platform/events');
        });
        expect(await screen.findByTestId('chatops-copy-feedback')).toHaveTextContent("Callback URL copied");

        fireEvent.click(screen.getByRole('button', { name: "Copy configuration checklist" }));
        await waitFor(() => {
            expect(clipboardWriteText).toHaveBeenCalledTimes(2);
        });
        expect(clipboardWriteText.mock.calls[1]?.[0]).toContain("Notification platform event subscription checklist");
        expect(clipboardWriteText.mock.calls[1]?.[0]).toContain('http://127.0.0.1:8020/api/commander/notification_platform/events');
        expect(clipboardWriteText.mock.calls[1]?.[0]).toContain("notification app bot");
    });

    it('should configure verification token and run subscription self check', async () => {
        render(<NotificationPage />);

        await screen.findByText("Event subscription settings");
        fireEvent.click(screen.getByRole('button', { name: "Generate token" }));

        await waitFor(() => {
            expect(notificationServiceMocks.configureCommanderChatOpsToken).toHaveBeenCalledWith({ regenerate: true });
        });

        expect(await screen.findByText("Most recently generated verification token")).toBeInTheDocument();
        expect(screen.getByText('demo-token')).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: "Verify callback endpoint" }));

        await waitFor(() => {
            expect(notificationServiceMocks.selfCheckCommanderChatOpsSubscription).toHaveBeenCalledWith({ challenge: 'codex-self-check' });
        });

        expect(await screen.findByText(/Verification succeeded, challenge=codex-self-check/)).toBeInTheDocument();
        expect(screen.getByText("Ready")).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: "Copy current token" }));

        await waitFor(() => {
            expect(clipboardWriteText).toHaveBeenCalledWith('demo-token');
        });
        expect(await screen.findByTestId('chatops-copy-feedback')).toHaveTextContent("The current session's verification token was copied.");
    });
});
