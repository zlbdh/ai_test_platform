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
                summary: '已配置 1 个 Webhook，其中 1 个最近测试通过',
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
                    last_test_message: '发送成功',
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
            delivery_strategy_summary: '当前仍主要依赖通知平台 Webhook 机器人发通知，尚未形成“一个机器人”对外体验。',
            callback_url: 'http://127.0.0.1:8020/api/commander/notification_platform/events',
            callback_url_public: false,
            callback_provider: {
                key: 'local',
                label: '本地地址',
                host: '127.0.0.1',
            },
            callback_recommendation: '先把 PUBLIC_API_BASE_URL 改成通知平台云侧可访问的公网地址，再执行 challenge 回探。',
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
                summary: '当前还是本地或内网地址，平台暂不执行公网回探。',
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
                summary: '未检测到本机 OpenSSH 反向隧道进程。',
                checked_at: '2026-03-20 11:45:00',
                stdout_tail: '',
                stderr_tail: '',
            },
            recent_chat_bindings: [],
            summary: '通知平台回推通道已健康，但还缺少事件订阅 verification token，群消息还不能稳定回流到平台。',
            supported_commands: ['状态', '报告 <mission_id>', '测试 <url>'],
            latest_event: {
                id: 1,
                channel: 'notification_platform',
                source: 'event_subscription',
                event_type: 'message',
                message: 'health',
                from_user: 'ou_demo',
                chat_id: 'oc_demo',
                response: '🟢 军团状态：6/6 Agent 在线',
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
                response: '🟢 军团状态：6/6 Agent 在线',
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
                    message: '应用机器人凭据校验通过，已成功获取 tenant_access_token。',
                    status_code: 200,
                    source: 'config_save',
                    app_id_masked: 'cli...bot',
                    created_at: '2026-03-18 12:30:00',
                },
                unified_robot_target: true,
                unified_robot_platform_ready: true,
                unified_robot_ready: false,
                delivery_strategy: 'single_robot_with_webhook_fallback',
                delivery_strategy_summary: '对外建议只暴露一个通知平台应用机器人，群内命令回复优先走应用机器人，Webhook 仅作为兜底通知通道。',
                callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
                callback_url_public: true,
                callback_provider: {
                    key: 'custom',
                    label: '自定义公网地址',
                    host: 'ops.example.com',
                },
                callback_recommendation: '自定义公网地址 已通过 challenge 回探，可以继续去通知平台开发者后台完成事件订阅和真实群测。',
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
                    summary: '公网回调地址已通过主动回探，当前入口对外可达。',
                    status_code: 200,
                    content_type: 'application/json',
                    response_excerpt: '{"challenge":"chatops-probe"}',
                    probed_at: '2026-03-18T12:20:00',
                },
                recent_chat_bindings: [],
                summary: '通知平台应用机器人已配置，平台侧和公网回调都已就绪，但还没收到真实群消息回流；请把应用机器人加入目标群并发一条测试消息。',
                supported_commands: ['状态', '报告 <mission_id>', '测试 <url>'],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: null,
                latest_subscription_check_event: null,
                recent_events: [],
            },
        });
        notificationServiceMocks.unbindCommanderChatOpsAppBot.mockResolvedValue({
            status: 'success',
            message: '当前项目已解绑通知平台应用机器人，现仅保留 Webhook 通知通道。',
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
                delivery_strategy_summary: '当前仍主要依赖通知平台 Webhook 机器人发通知，尚未形成“一个机器人”对外体验。',
                callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
                callback_url_public: true,
                callback_provider: {
                    key: 'custom',
                    label: '自定义公网地址',
                    host: 'ops.example.com',
                },
                callback_recommendation: '自定义公网地址 已通过 challenge 回探，可以继续去通知平台开发者后台完成事件订阅和真实群测。',
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
                    summary: '公网回调地址已通过主动回探，当前入口对外可达。',
                    status_code: 200,
                    content_type: 'application/json',
                    response_excerpt: '{"challenge":"chatops-probe"}',
                    probed_at: '2026-03-18T12:20:00',
                },
                recent_chat_bindings: [],
                summary: '当前项目已解绑旧应用机器人，现阶段仅保留 Webhook 通知通道；请为测试平台单独创建新的专属机器人。',
                supported_commands: ['状态', '报告 <mission_id>', '测试 <url>'],
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
                delivery_strategy_summary: '当前仍主要依赖通知平台 Webhook 机器人发通知，尚未形成“一个机器人”对外体验。',
                callback_url: 'https://ops.example.com/api/commander/notification_platform/events',
                callback_url_public: true,
                callback_provider: {
                    key: 'custom',
                    label: '自定义公网地址',
                    host: 'ops.example.com',
                },
                callback_recommendation: '自定义公网地址 已通过 challenge 回探，可以继续去通知平台开发者后台完成事件订阅和真实群测。',
                enabled_notification_platform_webhook_count: 1,
                healthy_notification_platform_webhook_count: 1,
                webhook_ready: true,
                subscription_endpoint_verified: false,
                external_connected: false,
                external_connected_history_observed: false,
                external_connection_stale: false,
                platform_ready: false,
                ready: false,
                summary: 'verification token 已配置，但平台侧还没完成事件订阅 challenge 自检；请先执行一次平台侧回调验证。',
                supported_commands: ['状态', '报告 <mission_id>', '测试 <url>'],
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
                message: '应用机器人凭据校验通过，已成功获取 tenant_access_token。',
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
                    message: '应用机器人凭据校验通过，已成功获取 tenant_access_token。',
                    status_code: 200,
                    source: 'manual_self_check',
                    app_id_masked: 'cli...bot',
                    created_at: '2026-03-18 12:35:00',
                },
                unified_robot_target: true,
                unified_robot_platform_ready: true,
                unified_robot_ready: false,
                delivery_strategy: 'single_robot_with_webhook_fallback',
                delivery_strategy_summary: '对外建议只暴露一个通知平台应用机器人，群内命令回复优先走应用机器人，Webhook 仅作为兜底通知通道。',
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
                    summary: '公网回调地址已通过主动回探，当前入口对外可达。',
                    status_code: 200,
                    content_type: 'application/json',
                    response_excerpt: '{"challenge":"chatops-probe"}',
                    probed_at: '2026-03-18T12:20:00',
                },
                callback_probe_history: [],
                recent_chat_bindings: [],
                summary: '通知平台应用机器人已配置，平台侧和公网回调都已就绪，但还没收到真实群消息回流；请把应用机器人加入目标群并发一条测试消息。',
                supported_commands: ['状态', '报告 <mission_id>', '测试 <url>'],
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
                delivery_strategy_summary: '当前仍主要依赖通知平台 Webhook 机器人发通知，尚未形成“一个机器人”对外体验。',
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
                    summary: '公网回调地址回探失败：ConnectionError',
                    status_code: null,
                    content_type: '',
                    response_excerpt: '',
                    probed_at: '2026-03-18T12:00:00',
                },
                recent_chat_bindings: [],
                summary: '通知平台回推通道已健康，但还缺少事件订阅 verification token，群消息还不能稳定回流到平台。',
                supported_commands: ['状态', '报告 <mission_id>', '测试 <url>'],
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
            message: '本机反向隧道已重启。',
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
                summary: '检测到本机 OpenSSH 反向隧道进程（PID 1234）。',
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
                delivery_strategy_summary: '当前仍主要依赖通知平台 Webhook 机器人发通知，尚未形成“一个机器人”对外体验。',
                callback_url: 'http://127.0.0.1:8020/api/commander/notification_platform/events',
                callback_url_public: false,
                callback_provider: {
                    key: 'local',
                    label: '本地地址',
                    host: '127.0.0.1',
                },
                callback_recommendation: '先把 PUBLIC_API_BASE_URL 改成通知平台云侧可访问的公网地址，再执行 challenge 回探。',
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
                    summary: '当前还是本地或内网地址，平台暂不执行公网回探。',
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
                    summary: '检测到本机 OpenSSH 反向隧道进程（PID 1234）。',
                    checked_at: '2026-03-20 11:46:00',
                    stdout_tail: '',
                    stderr_tail: '',
                },
                recent_chat_bindings: [],
                summary: '通知平台回推通道已健康，但还缺少事件订阅 verification token，群消息还不能稳定回流到平台。',
                supported_commands: ['状态', '报告 <mission_id>', '测试 <url>'],
                latest_event: {
                    id: 1,
                    channel: 'notification_platform',
                    source: 'event_subscription',
                    event_type: 'message',
                    message: 'health',
                    from_user: 'ou_demo',
                    chat_id: 'oc_demo',
                    response: '🟢 军团状态：6/6 Agent 在线',
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
                    response: '🟢 军团状态：6/6 Agent 在线',
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
                delivery_strategy_summary: '当前仍主要依赖通知平台 Webhook 机器人发通知，尚未形成“一个机器人”对外体验。',
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
                    summary: '公网回调地址已通过主动回探，当前入口对外可达。',
                    status_code: 200,
                    content_type: 'application/json',
                    response_excerpt: '{"challenge":"chatops-probe"}',
                    probed_at: '2026-03-18T12:05:00',
                },
                recent_chat_bindings: [],
                summary: '平台侧事件订阅已就绪，但还没收到通知平台真实文本消息回流；请在通知平台开发者后台完成事件订阅后发一条测试消息。',
                supported_commands: ['状态', '报告 <mission_id>', '测试 <url>'],
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
                response: '🟢 军团状态：6/6 Agent 在线',
                run: {
                    run_id: 'run-simulated',
                },
            },
            delivery: { configured: 1, delivered: 1, failed: 0, message: '发送成功' },
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
                delivery_strategy_summary: '当前仍主要依赖通知平台 Webhook 机器人发通知，尚未形成“一个机器人”对外体验。',
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
                    summary: '当前还是本地或内网地址，平台暂不执行公网回探。',
                    status_code: null,
                    content_type: '',
                    response_excerpt: '',
                    probed_at: '2026-03-18T12:15:00',
                },
                summary: '通知平台回推通道已健康，但还缺少事件订阅 verification token，群消息还不能稳定回流到平台。',
                supported_commands: ['状态', '报告 <mission_id>', '测试 <url>'],
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
                command_response: '📡 军团状态\n• 已注册 Agent: 6\n• 健康心跳: 6/6',
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
                    label: '自定义公网地址',
                    host: 'ops.example.com',
                },
                callback_recommendation: '自定义公网地址 已通过 challenge 回探，可以继续去通知平台开发者后台完成事件订阅和真实群测。',
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
                    summary: '公网回调地址已通过主动回探，当前入口对外可达。',
                    status_code: 200,
                    content_type: 'application/json',
                    response_excerpt: '{"challenge":"external-self-check-1234"}',
                    probed_at: '2026-03-18T12:20:00',
                },
                callback_probe_history: [],
                summary: '通知平台双向链路已就绪。',
                supported_commands: ['状态', '报告 <mission_id>', '测试 <url>'],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: {
                    id: 11,
                    channel: 'notification_platform',
                    source: 'event_subscription',
                    event_type: 'message',
                    message: '状态',
                    from_user: 'ou_demo',
                    chat_id: 'oc_demo',
                    response: '📡 军团状态',
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
                summary: '公网回调地址回探失败：ConnectionError',
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
                    label: '自定义公网地址',
                    host: 'ops.example.com',
                },
                callback_recommendation: '自定义公网地址 当前连接失败，建议检查隧道进程是否存活，并确认公网域名仍指向本机 8020。',
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
                    summary: '公网回调地址回探失败：ConnectionError',
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
                        summary: '公网回调地址回探失败：ConnectionError',
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
                        summary: '公网回调地址回探超时，通知平台云侧当前大概率无法稳定访问该入口。',
                        status_code: null,
                        content_type: '',
                        response_excerpt: '',
                        source: 'overview',
                        force_refresh: false,
                        created_at: '2026-03-18 12:35:00',
                    },
                ],
                summary: '公网回调地址回探失败：ConnectionError',
                supported_commands: ['状态', '报告 <mission_id>', '测试 <url>'],
                latest_event: null,
                latest_successful_event: null,
                latest_external_successful_event: {
                    id: 7,
                    channel: 'notification_platform',
                    source: 'event_subscription',
                    event_type: 'message',
                    message: '状态',
                    from_user: 'ou_demo',
                    chat_id: 'oc_demo',
                    response: '🟢 军团状态：6/6 Agent 在线',
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
        expect(screen.getByText('通知平台接入说明')).toBeInTheDocument();
        expect(screen.getByText(/当前这里配置的是“自定义 Webhook 机器人”/)).toBeInTheDocument();
        expect(screen.getByText('通知平台入口分工')).toBeInTheDocument();
        expect(screen.getByTestId('notification_platform-role-card-group-notify')).toBeInTheDocument();
        expect(screen.getByTestId('notification_platform-role-card-bot-command')).toBeInTheDocument();
        expect(screen.getByTestId('chatops-overview-card-notify')).toHaveTextContent('测试平台群');
        expect(screen.getByText('AI Test Platform 机器人')).toBeInTheDocument();
        expect(screen.getByText('链路：平台 -> 群')).toBeInTheDocument();
        expect(screen.getByText('链路：你 -> 平台 -> 你')).toBeInTheDocument();
        expect(screen.getAllByText(/\/api\/commander\/notification_platform\/events/).length).toBeGreaterThan(0);
        expect(screen.getByText('通知平台双向指令')).toBeInTheDocument();
        expect(screen.getByText('通知平台回推通道已健康，但还缺少事件订阅 verification token，群消息还不能稳定回流到平台。')).toBeInTheDocument();
        expect(screen.getByText('公网回探')).toBeInTheDocument();
        expect(screen.getAllByText(/当前还是本地或内网地址/).length).toBeGreaterThan(0);
        expect(screen.getByText('本地地址 · 127.0.0.1')).toBeInTheDocument();
        expect(screen.getAllByText(/PUBLIC_API_BASE_URL/).length).toBeGreaterThan(0);
        expect(screen.getByText(/消息：health/)).toBeInTheDocument();
        expect(screen.getByText(/回复：🟢 军团状态：6\/6 Agent 在线/)).toBeInTheDocument();
        expect(screen.getByText(/命令：platform.status · run_id：run-health/)).toBeInTheDocument();
        expect(screen.getByRole('link', { name: '前往 Legion 控制中心' })).toHaveAttribute('href', '/legion?tab=control');
        expect(screen.getByRole('link', { name: '打开这条命令的 Legion 详情' })).toHaveAttribute('href', '/legion?tab=control&run=run-health');
        expect(screen.getAllByText('平台侧自检').length).toBeGreaterThan(0);
        expect(screen.getByText('当前还是本地回调地址')).toBeInTheDocument();
        expect(screen.getByText('事件订阅配置')).toBeInTheDocument();
        expect(screen.getByText('还未生成 Token')).toBeInTheDocument();
        expect(screen.getByText(/当前回调地址还是本地\/内网地址/)).toBeInTheDocument();
        expect(screen.getByText('当前项目专属通知平台应用机器人配置')).toBeInTheDocument();
        expect(screen.getByText(/当前项目尚未配置专属应用机器人/)).toBeInTheDocument();
        expect(screen.getByText('通知平台开发者后台配置清单')).toBeInTheDocument();
        expect(screen.getByText('仍差应用机器人配置')).toBeInTheDocument();
    });

    it('should simulate chatops command from notification page', async () => {
        render(<NotificationPage />);

        await screen.findAllByText('平台侧自检');
        fireEvent.click(screen.getByRole('button', { name: '模拟通知平台指令' }));

        await waitFor(() => {
            expect(notificationServiceMocks.simulateCommanderChatOps).toHaveBeenCalledWith({
                message: '状态',
                from_user: 'notification_debug',
                chat_id: 'notification_debug_chat',
                deliver: true,
            });
        });

        expect(await screen.findByText(/最近一次模拟/)).toBeInTheDocument();
        expect(screen.getByText(/当前状态：通知平台回推通道已健康，但还缺少事件订阅 verification token/)).toBeInTheDocument();
        expect(screen.getByText(/关联 run_id：run-simulated/)).toBeInTheDocument();
        expect(screen.getByRole('link', { name: '打开关联命令' })).toHaveAttribute('href', '/legion?tab=control&run=run-simulated');
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
                label: '自定义公网地址',
                host: 'ops.example.com',
            },
            callback_recommendation: '自定义公网地址 已通过 challenge 回探，可以继续去通知平台开发者后台完成事件订阅和真实群测。',
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
                summary: '公网回调地址已通过主动回探，当前入口对外可达。',
                status_code: 200,
                content_type: 'application/json',
                response_excerpt: '{"challenge":"external-self-check-1234"}',
                probed_at: '2026-03-18T12:20:00',
            },
            callback_probe_history: [],
            summary: '通知平台双向链路已就绪。',
            supported_commands: ['状态', '报告 <mission_id>', '测试 <url>'],
            latest_event: null,
            latest_successful_event: null,
            latest_external_successful_event: null,
            latest_subscription_check_event: null,
            recent_events: [],
        });

        render(<NotificationPage />);

        await screen.findByText('通知平台双向链路已就绪。');
        const externalSelfCheckButton = await screen.findByRole('button', { name: '跑公网链路自测' });
        await waitFor(() => {
            expect(externalSelfCheckButton).not.toBeDisabled();
        });
        fireEvent.click(externalSelfCheckButton);

        await waitFor(() => {
            expect(notificationServiceMocks.runCommanderChatOpsExternalSelfCheck).toHaveBeenCalledTimes(1);
        });

        await waitFor(() => {
            expect(screen.getAllByText('公网链路自测').length).toBeGreaterThan(0);
        });
        expect(screen.getByText(/地址：https:\/\/ops\.example\.com\/api\/commander\/notification_platform\/events/)).toBeInTheDocument();
        expect(screen.getByText(/challenge：通过 · HTTP 200/)).toBeInTheDocument();
        expect(screen.getByText(/文本消息：通过 · HTTP 200 · 回推 1\/1/)).toBeInTheDocument();
        expect(screen.getByText(/回复：📡 军团状态/)).toBeInTheDocument();
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
                label: '自定义公网地址',
                host: 'ops.example.com',
            },
            callback_recommendation: '当前公网地址已通过平台公网自测，说明 challenge 与文本消息都能打到回调入口；下一步请在通知平台开发者后台完成事件订阅，并在目标群里发送一条真实消息做最终联调。',
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
                summary: '公网回调地址回探失败：timeout',
                status_code: 0,
                content_type: '',
                response_excerpt: 'timeout',
                probed_at: '2026-03-18T12:20:00',
            },
            callback_probe_history: [],
            summary: '最近一次平台公网自测已经通过，说明公网回调入口、challenge 和文本消息链路都可用；但这还不等同于真实通知平台群消息已经联通，下一步仍需在目标群里发送一条真实消息完成最终验证。',
            supported_commands: ['状态', '报告 <mission_id>', '测试 <url>'],
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
                response: '📡 军团状态',
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
            expect(verifiedCard).toHaveTextContent('最近公网链路自测');
        });
        expect(screen.getByText(/状态：已通过/)).toBeInTheDocument();
        expect(screen.getByText(/这代表平台最近一次从公网入口跑通了 challenge 与文本消息双验证/)).toBeInTheDocument();
        expect(screen.getByText(/但这还不等同于真实通知平台群消息已经完成联调/)).toBeInTheDocument();
        expect(screen.getByText(/最近回复：📡 军团状态/)).toBeInTheDocument();
    });

    it('should configure public callback url from notification page', async () => {
        render(<NotificationPage />);

        await screen.findByText('公网回调地址配置');
        const callbackInput = await screen.findByDisplayValue('http://127.0.0.1:8020');
        fireEvent.change(callbackInput, {
            target: { value: 'https://ops.example.com' },
        });
        await waitFor(() => {
            expect(callbackInput).toHaveValue('https://ops.example.com');
        });
        fireEvent.click(screen.getByRole('button', { name: '保存公网地址' }));

        await waitFor(() => {
            expect(notificationServiceMocks.configureCommanderChatOpsCallbackUrl).toHaveBeenCalledWith({
                public_api_base_url: 'https://ops.example.com',
            });
        });

        expect(await screen.findByText(/已保存公网基地址/)).toBeInTheDocument();
        expect(screen.getAllByText('https://ops.example.com/api/commander/notification_platform/events').length).toBeGreaterThan(0);
    });

    it('should refresh callback probe and render recent probe history', async () => {
        render(<NotificationPage />);

        await screen.findByText('公网回调地址配置');
        fireEvent.click(screen.getByRole('button', { name: '立即重试回探' }));

        await waitFor(() => {
            expect(notificationServiceMocks.refreshCommanderChatOpsProbe).toHaveBeenCalledTimes(1);
        });

        expect(await screen.findByText('最近一次手动重试')).toBeInTheDocument();
        expect(screen.getAllByText('公网回调地址回探失败：ConnectionError').length).toBeGreaterThan(0);
        expect(screen.getByText('最近回探记录')).toBeInTheDocument();
        expect(screen.getByText('手动重试')).toBeInTheDocument();
        expect(screen.getByText('强制刷新')).toBeInTheDocument();
        expect(screen.getByText(/当前公网回探失败，说明现在是公网入口退化/)).toBeInTheDocument();
        expect(screen.getByText(/历史曾成功/)).toBeInTheDocument();
        expect(screen.getByText('自定义公网地址 · ops.example.com')).toBeInTheDocument();
        expect(screen.getAllByText(/建议动作：自定义公网地址 当前连接失败/).length).toBeGreaterThan(0);
    });

    it('should restart local tunnel from notification page', async () => {
        render(<NotificationPage />);

        await screen.findByText('本机反向隧道');
        expect(screen.getByText(/当前环境不支持|脚本缺失|运行中|未运行/)).toBeInTheDocument();
        const restartButton = screen.getByRole('button', { name: '重启本机隧道' });
        await waitFor(() => {
            expect(restartButton).not.toBeDisabled();
        });
        fireEvent.click(restartButton);

        await waitFor(() => {
            expect(notificationServiceMocks.restartCommanderChatOpsLocalTunnel).toHaveBeenCalledTimes(1);
        });

        expect(await screen.findByText('最近一次隧道重启')).toBeInTheDocument();
        expect(screen.getByText('本机反向隧道已重启。')).toBeInTheDocument();
        expect(screen.getByText(/运行中 · PID 1234/)).toBeInTheDocument();
    });

    it('should configure app bot credentials from notification page', async () => {
        render(<NotificationPage />);

        await screen.findByText('当前项目专属通知平台应用机器人配置');
        fireEvent.change(screen.getByPlaceholderText('当前项目专属通知平台 App ID'), {
            target: { value: 'cli_demo_bot' },
        });
        fireEvent.change(screen.getByPlaceholderText('当前项目专属通知平台 App Secret'), {
            target: { value: 'secret-demo' },
        });
        fireEvent.click(screen.getByRole('button', { name: '保存应用机器人' }));

        await waitFor(() => {
            expect(notificationServiceMocks.configureCommanderChatOpsAppBot).toHaveBeenCalledWith({
                app_id: 'cli_demo_bot',
                app_secret: 'secret-demo',
            });
        });

        expect(await screen.findByText(/已保存应用机器人配置/)).toBeInTheDocument();
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
                message: '应用机器人凭据校验通过，已成功获取 tenant_access_token。',
                status_code: 200,
                source: 'config_save',
                app_id_masked: 'cli...bot',
                created_at: '2026-03-18 12:30:00',
            },
            unified_robot_target: true,
            unified_robot_platform_ready: true,
            unified_robot_ready: false,
            delivery_strategy: 'single_robot_with_webhook_fallback',
            delivery_strategy_summary: '对外建议只暴露一个通知平台应用机器人，群内命令回复优先走应用机器人，Webhook 仅作为兜底通知通道。',
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
                summary: '公网回调地址已通过主动回探，当前入口对外可达。',
                status_code: 200,
                content_type: 'application/json',
                response_excerpt: '{"challenge":"chatops-probe"}',
                probed_at: '2026-03-18T12:20:00',
            },
            recent_chat_bindings: [],
            summary: '通知平台应用机器人已配置，平台侧和公网回调都已就绪。',
            supported_commands: ['状态', '报告 <mission_id>', '测试 <url>'],
            latest_event: null,
            latest_successful_event: null,
            latest_external_successful_event: null,
            latest_subscription_check_event: null,
            recent_events: [],
        });

        render(<NotificationPage />);

        const unbindButton = await screen.findByRole('button', { name: '解绑当前应用机器人' });
        await waitFor(() => {
            expect(unbindButton).not.toBeDisabled();
        });
        fireEvent.click(unbindButton);

        await waitFor(() => {
            expect(notificationServiceMocks.unbindCommanderChatOpsAppBot).toHaveBeenCalledWith({ purge_history: true });
        });

        expect(await screen.findByText('已解绑当前项目应用机器人')).toBeInTheDocument();
        expect(screen.getByText(/已清理：应用校验 2 条/)).toBeInTheDocument();
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
                message: '最近一次校验失败。',
                status_code: 401,
                source: 'config_save',
                app_id_masked: 'cli...bot',
                created_at: '2026-03-18 12:30:00',
            },
            unified_robot_target: true,
            unified_robot_platform_ready: false,
            unified_robot_ready: false,
            delivery_strategy: 'single_robot_with_webhook_fallback',
            delivery_strategy_summary: '对外建议只暴露一个通知平台应用机器人，群内命令回复优先走应用机器人，Webhook 仅作为兜底通知通道。',
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
                summary: '公网回调地址已通过主动回探，当前入口对外可达。',
                status_code: 200,
                content_type: 'application/json',
                response_excerpt: '{"challenge":"chatops-probe"}',
                probed_at: '2026-03-18T12:20:00',
            },
            callback_probe_history: [],
            recent_chat_bindings: [],
            summary: '通知平台应用机器人已配置，但最近一次凭据校验未通过。',
            supported_commands: ['状态', '报告 <mission_id>', '测试 <url>'],
            latest_event: null,
            latest_successful_event: null,
            latest_external_successful_event: null,
            latest_subscription_check_event: null,
            recent_events: [],
        });

        render(<NotificationPage />);

        await screen.findByText('应用机器人凭据校验');
        fireEvent.click(screen.getByRole('button', { name: '验证应用机器人' }));

        await waitFor(() => {
            expect(notificationServiceMocks.selfCheckCommanderChatOpsAppBot).toHaveBeenCalledTimes(1);
        });

        expect(await screen.findByText('最近一次手动校验')).toBeInTheDocument();
        expect(screen.getAllByText(/应用机器人凭据校验通过/).length).toBeGreaterThan(0);
    });

    it('should render single-robot strategy with webhook fallback after app bot is configured', async () => {
        render(<NotificationPage />);

        await screen.findByText('对外机器人方案');
        expect(screen.getByText('单机器人建设中')).toBeInTheDocument();
        expect(screen.getByText('仅 Webhook 机器人')).toBeInTheDocument();

        fireEvent.change(screen.getByPlaceholderText('当前项目专属通知平台 App ID'), {
            target: { value: 'cli_demo_bot' },
        });
        fireEvent.change(screen.getByPlaceholderText('当前项目专属通知平台 App Secret'), {
            target: { value: 'secret-demo' },
        });
        fireEvent.click(screen.getByRole('button', { name: '保存应用机器人' }));

        expect(await screen.findByText('单机器人待群测')).toBeInTheDocument();
        expect(screen.getByText('应用机器人主通道 + Webhook 兜底')).toBeInTheDocument();
        expect(screen.getAllByText(/Webhook 仅作为兜底通知通道/)).not.toHaveLength(0);
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
            delivery_strategy_summary: '对外建议只暴露一个通知平台应用机器人，群内命令回复优先走应用机器人，Webhook 仅作为兜底通知通道。',
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
                summary: '公网回调地址已通过主动回探，当前入口对外可达。',
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
                    last_message: '状态',
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
                    last_message: '报告 125c69cd',
                    last_seen_at: '2026-03-18 12:32:00',
                    last_reply_mode: 'app_bot_fallback_webhook',
                    last_delivery_ok: 0,
                    last_run_id: 'run-group-b',
                    last_command_id: 'commander.mission.report',
                    last_requester_id: 'user_b',
                    binding_status: 'bound',
                },
            ],
            summary: '通知平台应用机器人已配置，平台侧和公网回调都已就绪，但还没收到真实群消息回流；请把应用机器人加入目标群并发一条测试消息。',
            supported_commands: ['状态', '报告 <mission_id>', '测试 <url>'],
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
        expect(within(bindingList).getByText('应用机器人')).toBeInTheDocument();
        expect(within(bindingList).getByText('应用机器人失败，已走 Webhook 兜底')).toBeInTheDocument();
        expect(within(bindingList).getByText('通知平台事件订阅')).toBeInTheDocument();
        expect(within(bindingList).getByText('平台模拟')).toBeInTheDocument();
        expect(within(bindingList).getAllByRole('link', { name: '查看关联命令' })).toHaveLength(2);
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
                message: '应用机器人凭据校验通过，已成功获取 tenant_access_token。',
                status_code: 200,
                source: 'config_save',
                app_id_masked: 'cli...bot',
                created_at: '2026-03-20 10:58:12',
            },
            unified_robot_target: true,
            unified_robot_platform_ready: false,
            unified_robot_ready: false,
            delivery_strategy: 'single_robot_with_webhook_fallback',
            delivery_strategy_summary: '对外建议只暴露当前项目专属的通知平台应用机器人，群内命令回复优先走应用机器人，Webhook 仅作为兜底通知通道。',
            callback_url: 'https://test.example-user.top:8443/api/commander/notification_platform/events',
            callback_url_public: true,
            callback_provider: {
                key: 'custom',
                label: '自定义公网地址',
                host: 'test.example-user.top',
            },
            callback_recommendation: '自定义公网地址 回探超时，建议更换为时延更稳定的公网入口，或检查当前隧道是否被网络策略阻断。',
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
                summary: '公网回调地址回探超时，通知平台云侧当前大概率无法稳定访问该入口。',
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
                    last_message: '状态',
                    last_seen_at: '2026-03-20 10:49:47',
                    last_reply_mode: 'app_bot',
                    last_delivery_ok: 1,
                },
            ],
            summary: '公网回调地址回探超时，但平台历史上曾收到真实通知平台消息回流。',
            supported_commands: ['状态', '报告 <mission_id>', '测试 <url>'],
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
                message: '你好',
                from_user: 'user',
                chat_id: 'oc_group_a',
                response: '收到',
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
                message: '你好',
                from_user: 'user',
                chat_id: 'oc_group_a',
                response: '收到',
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

        expect(await screen.findByText('历史已联通')).toBeInTheDocument();
        expect(screen.getByText('当前通知平台使用方式')).toBeInTheDocument();
        expect(screen.getByTestId('chatops-current-usage')).toHaveTextContent('历史可用，当前需恢复入口');
        expect(screen.getByText('当前命令入口：单聊历史已联通，当前公网入口退化')).toBeInTheDocument();
        expect(screen.getByText('单机器人入口退化')).toBeInTheDocument();
        expect(screen.getByText(/最近一次真实单聊已成功/)).toBeInTheDocument();
        expect(screen.getByTestId('chatops-overview-card-entry')).toHaveTextContent('单聊历史已联通，当前公网入口退化');
        expect(screen.getByTestId('chatops-overview-card-verified')).toHaveTextContent('最近真实通知平台回流');
        expect(screen.getByTestId('chatops-overview-card-notify')).toHaveTextContent('测试平台群');
    });

    it('should copy callback url and setup guide from notification page', async () => {
        render(<NotificationPage />);

        await screen.findByText('通知平台开发者后台配置清单');
        fireEvent.click(screen.getByRole('button', { name: '复制回调地址' }));

        await waitFor(() => {
            expect(clipboardWriteText).toHaveBeenCalledWith('http://127.0.0.1:8020/api/commander/notification_platform/events');
        });
        expect(await screen.findByTestId('chatops-copy-feedback')).toHaveTextContent('回调地址已复制');

        fireEvent.click(screen.getByRole('button', { name: '复制配置清单' }));
        await waitFor(() => {
            expect(clipboardWriteText).toHaveBeenCalledTimes(2);
        });
        expect(clipboardWriteText.mock.calls[1]?.[0]).toContain('通知平台事件订阅配置清单');
        expect(clipboardWriteText.mock.calls[1]?.[0]).toContain('http://127.0.0.1:8020/api/commander/notification_platform/events');
        expect(clipboardWriteText.mock.calls[1]?.[0]).toContain('通知平台应用机器人');
    });

    it('should configure verification token and run subscription self check', async () => {
        render(<NotificationPage />);

        await screen.findByText('事件订阅配置');
        fireEvent.click(screen.getByRole('button', { name: '生成 Token' }));

        await waitFor(() => {
            expect(notificationServiceMocks.configureCommanderChatOpsToken).toHaveBeenCalledWith({ regenerate: true });
        });

        expect(await screen.findByText('最近生成的 verification token')).toBeInTheDocument();
        expect(screen.getByText('demo-token')).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: '验证回调入口' }));

        await waitFor(() => {
            expect(notificationServiceMocks.selfCheckCommanderChatOpsSubscription).toHaveBeenCalledWith({ challenge: 'codex-self-check' });
        });

        expect(await screen.findByText(/验证成功，challenge=codex-self-check/)).toBeInTheDocument();
        expect(screen.getByText('已就绪')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: '复制当前 Token' }));

        await waitFor(() => {
            expect(clipboardWriteText).toHaveBeenCalledWith('demo-token');
        });
        expect(await screen.findByTestId('chatops-copy-feedback')).toHaveTextContent('当前会话里的 verification token 已复制');
    });
});
