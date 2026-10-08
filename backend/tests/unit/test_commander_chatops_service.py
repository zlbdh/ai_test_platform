# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import json
from unittest.mock import MagicMock, patch

import requests

from services.commander_chatops_service import CommanderChatOpsService


def _query_all_side_effect(events, webhooks, probe_history=None, bindings=None, app_bot_checks=None):
    calls = {"count": 0}
    probe_history = probe_history or []
    bindings = bindings or []
    app_bot_checks = app_bot_checks or []

    def _side_effect(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return events
        if calls["count"] == 2:
            return webhooks
        if calls["count"] == 3:
            return probe_history
        if calls["count"] == 4:
            return bindings
        if calls["count"] == 5:
            return app_bot_checks
        return []

    return _side_effect


def test_chatops_overview_marks_callback_probe_success_when_public_callback_returns_challenge():
    service = CommanderChatOpsService()
    events = [
        {
            "id": 1,
            "channel": "notification_platform",
            "source": "subscription_self_check",
            "event_type": "url_verification",
            "message": "url_verification",
            "from_user": "",
            "chat_id": "",
            "response": "challenge accepted",
            "status": "verified",
            "delivery_configured": 0,
            "delivery_delivered": 0,
            "delivery_failed": 0,
            "created_at": "2026-03-18 12:00:00",
        },
    ]
    webhooks = [
        {"id": "wh_1", "name": "NotificationPlatform Production Alert", "enabled": 1, "last_test_success": 1},
    ]
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "application/json"}
    response.text = '{"challenge":"chatops-probe"}'
    response.json.return_value = {"challenge": "chatops-probe"}
    session = MagicMock()
    session.post.return_value = response

    with patch.dict("os.environ", {"NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT": "", "PUBLIC_API_BASE_URL_UPDATED_AT": "", "NOTIFICATION_PLATFORM_APP_ID": "", "NOTIFICATION_PLATFORM_APP_SECRET": ""}, clear=False), \
         patch("services.commander_chatops_service.os.getenv", side_effect=lambda key, default='': {
             "NOTIFICATION_PLATFORM_APP_ID": "",
             "NOTIFICATION_PLATFORM_APP_SECRET": "",
             "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT": "",
             "PUBLIC_API_BASE_URL_UPDATED_AT": "",
         }.get(key, default)), \
         patch("services.commander_chatops_service.query_all", side_effect=_query_all_side_effect(events, webhooks)), \
         patch("services.commander_chatops_service.requests.Session", return_value=session), \
         patch.object(CommanderChatOpsService, "_save_probe_history"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL", "https://ops.example.com"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL_UPDATED_AT", ""), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_ID", ""), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_SECRET", ""), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", ""):
        overview = service.get_overview()

    assert overview["callback_url_public"] is True
    assert overview["platform_ready"] is True
    assert overview["callback_probe"]["attempted"] is True
    assert overview["callback_probe"]["success"] is True
    assert overview["callback_probe"]["issue"] == ""
    assert "Public callback URL passed an active probe" in overview["callback_probe"]["summary"]
    assert overview["callback_provider"]["label"] == "Custom public URL"
    assert "passed the challenge probe" in overview["callback_recommendation"]


def test_chatops_overview_can_skip_live_probe_and_reuse_cached_state():
    service = CommanderChatOpsService()
    events = []
    webhooks = [
        {"id": "wh_1", "name": "NotificationPlatform Production Alert", "enabled": 1, "last_test_success": 1},
    ]

    with patch.dict("os.environ", {"NOTIFICATION_PLATFORM_APP_ID": "", "NOTIFICATION_PLATFORM_APP_SECRET": ""}, clear=False), \
         patch("services.commander_chatops_service.os.getenv", side_effect=lambda key, default='': {
             "NOTIFICATION_PLATFORM_APP_ID": "",
             "NOTIFICATION_PLATFORM_APP_SECRET": "",
             "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT": "",
             "PUBLIC_API_BASE_URL_UPDATED_AT": "",
         }.get(key, default)), \
         patch("services.commander_chatops_service.query_all", side_effect=_query_all_side_effect(events, webhooks)), \
         patch.object(CommanderChatOpsService, "_probe_callback_url") as mock_probe, \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL", "https://ops.example.com"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL_UPDATED_AT", ""), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_ID", ""), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_SECRET", ""), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", ""):
        overview = service.get_overview(allow_live_probe=False)

    mock_probe.assert_not_called()
    assert overview["callback_probe"]["attempted"] is False
    assert overview["callback_probe"]["issue"] == "probe_skipped"
    assert "Reusing the most recent public probe result" in overview["callback_probe"]["summary"]


def test_chatops_overview_detects_interstitial_warning_page_from_public_tunnel():
    service = CommanderChatOpsService()
    events = [
        {
            "id": 1,
            "channel": "notification_platform",
            "source": "subscription_self_check",
            "event_type": "url_verification",
            "message": "url_verification",
            "from_user": "",
            "chat_id": "",
            "response": "challenge accepted",
            "status": "verified",
            "delivery_configured": 0,
            "delivery_delivered": 0,
            "delivery_failed": 0,
            "created_at": "2026-03-18 12:00:00",
        },
    ]
    webhooks = [
        {"id": "wh_1", "name": "NotificationPlatform Production Alert", "enabled": 1, "last_test_success": 1},
    ]
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "text/html; charset=UTF-8"}
    response.text = "Caution: website hosted for free through pinggy.io"
    response.json.side_effect = ValueError("not json")
    session = MagicMock()
    session.post.return_value = response

    with patch.dict("os.environ", {"NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT": "", "PUBLIC_API_BASE_URL_UPDATED_AT": "", "NOTIFICATION_PLATFORM_APP_ID": "", "NOTIFICATION_PLATFORM_APP_SECRET": ""}, clear=False), \
         patch("services.commander_chatops_service.os.getenv", side_effect=lambda key, default='': {
             "NOTIFICATION_PLATFORM_APP_ID": "",
             "NOTIFICATION_PLATFORM_APP_SECRET": "",
             "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT": "",
             "PUBLIC_API_BASE_URL_UPDATED_AT": "",
         }.get(key, default)), \
         patch("services.commander_chatops_service.query_all", side_effect=_query_all_side_effect(events, webhooks)), \
         patch("services.commander_chatops_service.requests.Session", return_value=session), \
         patch.object(CommanderChatOpsService, "_save_probe_history"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL", "https://ops.example.com"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL_UPDATED_AT", ""), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_ID", ""), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_SECRET", ""), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", ""):
        overview = service.get_overview()

    assert overview["callback_probe"]["attempted"] is True
    assert overview["callback_probe"]["success"] is False
    assert overview["callback_probe"]["issue"] == "interstitial_page"
    assert "tunnel warning page" in overview["callback_probe"]["summary"]
    assert overview["ready"] is False
    assert "Public callback URL returned a tunnel warning page" in overview["summary"]
    assert overview["callback_provider"]["label"] == "Custom public URL"
    assert "public reverse proxy or tunnel without an intermediate page" in overview["callback_recommendation"]


def test_chatops_overview_marks_external_history_as_stale_when_current_probe_fails():
    service = CommanderChatOpsService()
    now = datetime.now()
    token_updated_at = (now - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    callback_updated_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    old_message_at = (now - timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S")
    current_verify_at = (now - timedelta(minutes=4)).strftime("%Y-%m-%d %H:%M:%S")
    events = [
        {
            "id": 3,
            "channel": "notification_platform",
            "source": "event_subscription",
            "event_type": "url_verification",
            "message": "url_verification",
            "from_user": "",
            "chat_id": "",
            "response": "challenge accepted",
            "status": "verified",
            "delivery_configured": 0,
            "delivery_delivered": 0,
            "delivery_failed": 0,
            "created_at": current_verify_at,
        },
        {
            "id": 2,
            "channel": "notification_platform",
            "source": "event_subscription",
            "event_type": "message",
            "message": "状态",
            "from_user": "user",
            "chat_id": "oc_live",
            "response": "The latest notification command was received and successfully sent back to the group.",
            "status": "ok",
            "delivery_configured": 1,
            "delivery_delivered": 1,
            "delivery_failed": 0,
            "created_at": old_message_at,
        },
        {
            "id": 1,
            "channel": "notification_platform",
            "source": "subscription_self_check",
            "event_type": "url_verification",
            "message": "url_verification",
            "from_user": "",
            "chat_id": "",
            "response": "challenge accepted",
            "status": "verified",
            "delivery_configured": 0,
            "delivery_delivered": 0,
            "delivery_failed": 0,
            "created_at": (now - timedelta(minutes=31)).strftime("%Y-%m-%d %H:%M:%S"),
        },
    ]
    webhooks = [
        {"id": "wh_1", "name": "NotificationPlatform Production Alert", "enabled": 1, "last_test_success": 1},
    ]

    with patch.dict("os.environ", {"NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT": "", "PUBLIC_API_BASE_URL_UPDATED_AT": ""}, clear=False), \
         patch("services.commander_chatops_service.query_all", side_effect=_query_all_side_effect(events, webhooks)), \
         patch.object(
             CommanderChatOpsService,
             "_probe_callback_url",
             return_value={
                 "attempted": True,
                 "success": False,
                 "issue": "timeout",
                 "summary": "Public callback probe timed out; the notification provider will likely be unable to reach this endpoint reliably.",
                 "status_code": None,
                 "content_type": "",
                 "response_excerpt": "",
                 "probed_at": "2026-03-18T12:01:05",
             },
         ), \
         patch.object(CommanderChatOpsService, "_save_probe_history"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL", "https://ops.example.com"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL_UPDATED_AT", callback_updated_at), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", token_updated_at), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_ID", "cli_123456"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_SECRET", "secret-demo"):
        overview = service.get_overview()

    assert overview["external_connected"] is False
    assert overview["external_connected_history_observed"] is False
    assert overview["external_connection_stale"] is False
    assert overview["subscription_check_recent_success"] is True
    assert overview["external_callback_ready"] is True
    assert overview["ready"] is False
    assert "The latest notification challenge passed" in overview["summary"]
    assert "send a real message in the target group or direct chat" in overview["callback_recommendation"]


def test_chatops_overview_keeps_chatops_ready_when_public_callback_is_ready_without_saved_app_bot():
    service = CommanderChatOpsService()
    events = [
        {
            "id": 2,
            "channel": "notification_platform",
            "source": "event_subscription",
            "event_type": "message",
            "message": "状态",
            "from_user": "user",
            "chat_id": "oc_live",
            "response": "The latest notification command was received and successfully sent back to the group.",
            "status": "ok",
            "delivery_configured": 1,
            "delivery_delivered": 1,
            "delivery_failed": 0,
            "created_at": "2026-03-18 12:01:00",
        },
        {
            "id": 1,
            "channel": "notification_platform",
            "source": "subscription_self_check",
            "event_type": "url_verification",
            "message": "url_verification",
            "from_user": "",
            "chat_id": "",
            "response": "challenge accepted",
            "status": "verified",
            "delivery_configured": 0,
            "delivery_delivered": 0,
            "delivery_failed": 0,
            "created_at": "2026-03-18 12:00:00",
        },
    ]
    webhooks = [
        {"id": "wh_1", "name": "NotificationPlatform Production Alert", "enabled": 1, "last_test_success": 1},
    ]

    with patch.dict("os.environ", {"NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT": "", "PUBLIC_API_BASE_URL_UPDATED_AT": "", "NOTIFICATION_PLATFORM_APP_ID": "", "NOTIFICATION_PLATFORM_APP_SECRET": ""}, clear=False), \
         patch("services.commander_chatops_service.os.getenv", side_effect=lambda key, default='': {
             "NOTIFICATION_PLATFORM_APP_ID": "",
             "NOTIFICATION_PLATFORM_APP_SECRET": "",
             "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT": "",
             "PUBLIC_API_BASE_URL_UPDATED_AT": "",
         }.get(key, default)), \
         patch("services.commander_chatops_service.query_all", side_effect=_query_all_side_effect(events, webhooks)), \
         patch.object(
             CommanderChatOpsService,
             "_probe_callback_url",
             return_value={
                 "attempted": True,
                 "success": True,
                 "issue": "",
                 "summary": "Public callback URL passed an active probe; the current endpoint is publicly reachable.",
                 "status_code": 200,
                 "content_type": "application/json",
                 "response_excerpt": "{\"challenge\":\"chatops-probe\"}",
                 "probed_at": "2026-03-18T12:01:05",
             },
         ), \
         patch.object(CommanderChatOpsService, "_save_probe_history"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL", "https://ops.example.com"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL_UPDATED_AT", ""), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_ID", ""), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_SECRET", ""), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", ""):
        overview = service.get_overview()

    assert overview["external_connected"] is True
    assert overview["external_connection_stale"] is False
    assert overview["external_callback_ready"] is True
    assert overview["direct_chat_ready"] is True
    assert overview["ready"] is True
    assert "successfully sent back to the group" in overview["summary"]
    assert "passed the challenge probe" in overview["callback_recommendation"]


def test_chatops_probe_uses_curl_fallback_when_requests_times_out():
    service = CommanderChatOpsService()
    session = MagicMock()
    session.post.side_effect = requests.Timeout()

    with patch("services.commander_chatops_service.requests.Session", return_value=session), \
         patch("services.commander_chatops_service.shutil.which", return_value="curl.exe"), \
         patch("services.commander_chatops_service.subprocess.run") as mock_run, \
         patch.object(CommanderChatOpsService, "_save_probe_history"):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"challenge":"chatops-probe"}\n200',
            stderr="",
        )
        result = service._probe_callback_url(
            "https://ops.example.com/api/commander/notification_platform/events",
            "demo-token",
            force_refresh=True,
        )

    assert result["attempted"] is True
    assert result["success"] is True
    assert result["issue"] == ""
    assert "curl fallback" in result["summary"]


def test_chatops_overview_identifies_localtunnel_provider_and_recommendation():
    service = CommanderChatOpsService()
    events = []
    webhooks = [
        {"id": "wh_1", "name": "NotificationPlatform Production Alert", "enabled": 1, "last_test_success": 1},
    ]
    with patch.dict("os.environ", {"NOTIFICATION_PLATFORM_APP_ID": "", "NOTIFICATION_PLATFORM_APP_SECRET": ""}, clear=False), \
         patch("services.commander_chatops_service.os.getenv", side_effect=lambda key, default='': {
             "NOTIFICATION_PLATFORM_APP_ID": "",
             "NOTIFICATION_PLATFORM_APP_SECRET": "",
             "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT": "",
             "PUBLIC_API_BASE_URL_UPDATED_AT": "",
         }.get(key, default)), \
         patch("services.commander_chatops_service.query_all", side_effect=_query_all_side_effect(events, webhooks)), \
         patch.object(
             CommanderChatOpsService,
             "_probe_callback_url",
             return_value={
                 "attempted": True,
                 "success": False,
                 "issue": "tunnel_unavailable",
                 "summary": "Public callback URL currently returns Tunnel Unavailable; the tunnel is not stable.",
                 "status_code": 503,
                 "content_type": "text/html",
                 "response_excerpt": "<h1>no tunnel here :(</h1>",
                 "probed_at": "2026-03-18T12:01:05",
             },
         ), \
         patch.object(CommanderChatOpsService, "_save_probe_history"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL", "https://demo-name.loca.lt"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", ""):
        overview = service.get_overview()

    assert overview["callback_provider"]["key"] == "localtunnel"
    assert overview["callback_provider"]["label"] == "LocalTunnel"
    assert "Create a new LocalTunnel" in overview["callback_recommendation"]


def test_chatops_refresh_probe_bypasses_cache_and_returns_latest_overview():
    service = CommanderChatOpsService()
    with patch.object(
        CommanderChatOpsService,
        "_probe_callback_url",
        return_value={
            "attempted": True,
            "success": False,
            "issue": "connect_error",
            "summary": "Public callback probe failed: ConnectionError",
            "status_code": None,
            "content_type": "",
            "response_excerpt": "",
            "probed_at": "2026-03-18T12:21:00",
        },
    ) as mock_probe, \
        patch.object(
            CommanderChatOpsService,
            "get_overview",
            return_value={"callback_probe_history": [{"id": 1}], "summary": "demo"},
        ) as mock_overview, \
        patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL", "https://ops.example.com"), \
        patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token"):
        result = service.refresh_callback_probe()

    assert result["probe"]["issue"] == "connect_error"
    assert result["overview"]["summary"] == "demo"
    mock_probe.assert_called_once_with(
        "https://ops.example.com/api/commander/notification_platform/events",
        "demo-token",
        force_refresh=True,
        source="manual_refresh",
    )
    mock_overview.assert_called_once()


def test_chatops_overview_reuses_recent_probe_history_before_live_reprobe():
    service = CommanderChatOpsService()
    recent_probe_at = (datetime.now() - timedelta(seconds=20)).strftime("%Y-%m-%d %H:%M:%S")
    events = [
        {
            "id": 1,
            "channel": "notification_platform",
            "source": "subscription_self_check",
            "event_type": "url_verification",
            "message": "url_verification",
            "from_user": "",
            "chat_id": "",
            "response": "challenge accepted",
            "status": "verified",
            "delivery_configured": 0,
            "delivery_delivered": 0,
            "delivery_failed": 0,
            "created_at": recent_probe_at,
        },
    ]
    webhooks = [
        {"id": "wh_1", "name": "NotificationPlatform Production Alert", "enabled": 1, "last_test_success": 1},
    ]
    probe_history = [
        {
            "id": 99,
            "callback_url": "https://ops.example.com/api/commander/notification_platform/events",
            "attempted": 1,
            "success": 1,
            "issue": "",
            "summary": "The latest probe succeeded (cached history).",
            "status_code": 200,
            "content_type": "application/json",
            "response_excerpt": '{"challenge":"chatops-probe"}',
            "source": "overview",
            "force_refresh": 0,
            "created_at": recent_probe_at,
        },
    ]

    with patch.dict("os.environ", {"NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT": "", "PUBLIC_API_BASE_URL_UPDATED_AT": ""}, clear=False), \
         patch("services.commander_chatops_service.query_all", side_effect=_query_all_side_effect(events, webhooks, probe_history)), \
         patch.object(CommanderChatOpsService, "_probe_callback_url", side_effect=AssertionError("should not re-probe")), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL", "https://ops.example.com"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL_UPDATED_AT", ""), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", ""):
        overview = service.get_overview()

    assert overview["callback_probe"]["success"] is True
    assert overview["callback_probe"]["summary"] == "The latest probe succeeded (cached history)."
    assert overview["callback_probe"]["probed_at"] == recent_probe_at


def test_chatops_overview_uses_quick_probe_without_curl_fallback():
    service = CommanderChatOpsService()
    events = []
    webhooks = [
        {"id": "wh_1", "name": "NotificationPlatform Production Alert", "enabled": 1, "last_test_success": 1},
    ]

    with patch.dict("os.environ", {"NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT": "", "PUBLIC_API_BASE_URL_UPDATED_AT": ""}, clear=False), \
         patch("services.commander_chatops_service.query_all", side_effect=_query_all_side_effect(events, webhooks)), \
         patch.object(
             CommanderChatOpsService,
             "_probe_callback_url",
             return_value={
                 "attempted": True,
                 "success": False,
                 "issue": "timeout",
                 "summary": "Public callback probe timed out.",
                 "status_code": None,
                 "content_type": "",
                 "response_excerpt": "",
                 "probed_at": "2026-03-19T11:30:00",
             },
         ) as mock_probe, \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL", "https://ops.example.com"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL_UPDATED_AT", ""), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", ""):
        overview = service.get_overview()

    assert overview["callback_probe"]["issue"] == "timeout"
    mock_probe.assert_called_once_with(
        "https://ops.example.com/api/commander/notification_platform/events",
        "demo-token",
        source="overview",
        allow_curl_fallback=False,
    )


def test_chatops_overview_accepts_recent_real_event_on_current_callback_when_probe_times_out():
    service = CommanderChatOpsService()
    now = datetime.now()
    token_updated_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    callback_updated_at = (now - timedelta(minutes=4)).strftime("%Y-%m-%d %H:%M:%S")
    recent_message_at = (now - timedelta(minutes=3)).strftime("%Y-%m-%d %H:%M:%S")
    recent_verify_at = (now - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
    events = [
        {
            "id": 3,
            "channel": "notification_platform",
            "source": "event_subscription",
            "event_type": "url_verification",
            "message": "url_verification",
            "from_user": "",
            "chat_id": "",
            "response": "challenge accepted",
            "status": "verified",
            "delivery_configured": 0,
            "delivery_delivered": 0,
            "delivery_failed": 0,
            "created_at": recent_verify_at,
        },
        {
            "id": 2,
            "channel": "notification_platform",
            "source": "event_subscription",
            "event_type": "message",
            "message": "状态",
            "from_user": "user",
            "chat_id": "oc_live",
            "response": "The latest notification command was received and successfully sent back to the group.",
            "status": "ok",
            "delivery_configured": 1,
            "delivery_delivered": 1,
            "delivery_failed": 0,
            "created_at": recent_message_at,
        },
    ]
    webhooks = [
        {"id": "wh_1", "name": "NotificationPlatform Production Alert", "enabled": 1, "last_test_success": 1},
    ]

    with patch.dict("os.environ", {"NOTIFICATION_PLATFORM_APP_ID": "", "NOTIFICATION_PLATFORM_APP_SECRET": ""}, clear=False), \
         patch("services.commander_chatops_service.os.getenv", side_effect=lambda key, default='': {
             "NOTIFICATION_PLATFORM_APP_ID": "",
             "NOTIFICATION_PLATFORM_APP_SECRET": "",
             "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT": "",
             "PUBLIC_API_BASE_URL_UPDATED_AT": "",
         }.get(key, default)), \
         patch("services.commander_chatops_service.query_all", side_effect=_query_all_side_effect(events, webhooks)), \
         patch.object(
             CommanderChatOpsService,
             "_probe_callback_url",
             return_value={
                 "attempted": True,
                 "success": False,
                 "issue": "timeout",
                 "summary": "Public callback probe failed (curl fallback): curl: (28) Operation timed out after 10006 milliseconds with 0 bytes received",
                 "status_code": 0,
                 "content_type": "",
                 "response_excerpt": "curl: (28) Operation timed out after 10006 milliseconds with 0 bytes received",
                 "probed_at": "2026-03-18T12:03:00",
             },
         ), \
         patch.object(CommanderChatOpsService, "_save_probe_history"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL", "https://ops.example.com"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL_UPDATED_AT", callback_updated_at), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", token_updated_at), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_ID", ""), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_SECRET", ""):
        overview = service.get_overview()

    assert overview["external_connected"] is True
    assert overview["external_connected_current"] is True
    assert overview["external_connected_via_recent_success"] is True
    assert overview["external_connection_stale"] is False
    assert overview["external_callback_ready"] is True
    assert overview["direct_chat_ready"] is True
    assert overview["ready"] is True
    assert "received real notification group messages within the last 15 minutes" in overview["summary"]
    assert "The current public URL received real notification group messages within the last 15 minutes" in overview["callback_recommendation"]


def test_chatops_overview_separates_external_self_check_from_real_group_message():
    service = CommanderChatOpsService()
    now = datetime.now()
    token_updated_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    callback_updated_at = (now - timedelta(minutes=4)).strftime("%Y-%m-%d %H:%M:%S")
    recent_self_check_at = (now - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
    recent_verify_at = (now - timedelta(minutes=3)).strftime("%Y-%m-%d %H:%M:%S")
    events = [
        {
            "id": 2,
            "channel": "notification_platform",
            "source": "external_self_check",
            "event_type": "message",
            "message": "status",
            "from_user": "user",
            "chat_id": "oc_external_self_check",
            "response": "Platform public endpoint self-test passed",
            "status": "ok",
            "delivery_configured": 1,
            "delivery_delivered": 1,
            "delivery_failed": 0,
            "created_at": recent_self_check_at,
        },
        {
            "id": 1,
            "channel": "notification_platform",
            "source": "subscription_self_check",
            "event_type": "url_verification",
            "message": "url_verification",
            "from_user": "",
            "chat_id": "",
            "response": "challenge accepted",
            "status": "verified",
            "delivery_configured": 0,
            "delivery_delivered": 0,
            "delivery_failed": 0,
            "created_at": recent_verify_at,
        },
    ]
    webhooks = [
        {"id": "wh_1", "name": "NotificationPlatform Production Alert", "enabled": 1, "last_test_success": 1},
    ]

    with patch("services.commander_chatops_service.query_all", side_effect=_query_all_side_effect(events, webhooks)), \
         patch.object(
             CommanderChatOpsService,
             "_probe_callback_url",
             return_value={
                 "attempted": True,
                 "success": False,
                 "issue": "timeout",
                 "summary": "Public callback probe failed: timeout",
                 "status_code": 0,
                 "content_type": "",
                 "response_excerpt": "timeout",
                 "probed_at": "2026-03-18T12:03:00",
             },
         ), \
         patch.object(CommanderChatOpsService, "_save_probe_history"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL", "https://ops.example.com"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL_UPDATED_AT", callback_updated_at), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", token_updated_at), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_ID", ""), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_SECRET", ""):
        overview = service.get_overview()

    assert overview["external_self_check_recent_success"] is True
    assert overview["latest_external_self_check_at"] == recent_self_check_at
    assert overview["external_callback_ready"] is True
    assert overview["external_connected"] is False
    assert overview["direct_chat_ready"] is False
    assert overview["ready"] is False
    assert "The latest notification challenge passed" in overview["summary"]
    assert "send a real message in the target group or direct chat" in overview["callback_recommendation"]


def test_chatops_overview_prefers_positive_summary_when_recent_self_check_and_history_both_exist():
    service = CommanderChatOpsService()
    now = datetime.utcnow()
    token_updated_at = (now - timedelta(minutes=40)).strftime("%Y-%m-%d %H:%M:%S")
    callback_updated_at = (now - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    historical_message_at = (now - timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S")
    recent_verify_at = (now - timedelta(minutes=3)).strftime("%Y-%m-%d %H:%M:%S")
    recent_self_check_at = (now - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
    events = [
        {
            "id": 3,
            "channel": "notification_platform",
            "source": "external_self_check",
            "event_type": "message",
            "message": "status",
            "from_user": "ops-live-check",
            "chat_id": "oc_external_self_check",
            "response": "Platform public endpoint self-test passed",
            "status": "ok",
            "delivery_configured": 1,
            "delivery_delivered": 1,
            "delivery_failed": 0,
            "created_at": recent_self_check_at,
        },
        {
            "id": 2,
            "channel": "notification_platform",
            "source": "event_subscription",
            "event_type": "message",
            "message": "状态",
            "from_user": "real-user",
            "chat_id": "oc_live_group",
            "response": "The latest notification command was received and successfully sent back to the group.",
            "status": "ok",
            "delivery_configured": 1,
            "delivery_delivered": 1,
            "delivery_failed": 0,
            "created_at": historical_message_at,
        },
        {
            "id": 1,
            "channel": "notification_platform",
            "source": "event_subscription",
            "event_type": "url_verification",
            "message": "url_verification",
            "from_user": "",
            "chat_id": "",
            "response": "challenge accepted",
            "status": "verified",
            "delivery_configured": 0,
            "delivery_delivered": 0,
            "delivery_failed": 0,
            "created_at": recent_verify_at,
        },
    ]
    webhooks = [
        {"id": "wh_1", "name": "NotificationPlatform Production Alert", "enabled": 1, "last_test_success": 1},
    ]

    with patch("services.commander_chatops_service.query_all", side_effect=_query_all_side_effect(events, webhooks)), \
         patch.object(
             CommanderChatOpsService,
             "_probe_callback_url",
             return_value={
                 "attempted": True,
                 "success": False,
                 "issue": "timeout",
                 "summary": "Public callback probe failed: timeout",
                 "status_code": 0,
                 "content_type": "",
                 "response_excerpt": "timeout",
                 "probed_at": "2026-03-18T12:03:00",
             },
         ), \
         patch.object(CommanderChatOpsService, "_save_probe_history"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL", "https://ops.example.com"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL_UPDATED_AT", callback_updated_at), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", token_updated_at), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_ID", "cli_demo_bot"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_SECRET", "secret-demo"):
        overview = service.get_overview()

    assert overview["external_connected"] is True
    assert overview["direct_chat_ready"] is True
    assert overview["ready"] is True
    assert "The latest platform public endpoint self-test passed" in overview["summary"]
    assert "the bidirectional channel remains usable" in overview["summary"]
    assert "the bidirectional channel remains usable" in overview["callback_recommendation"]


def test_chatops_overview_treats_recent_subscription_check_as_current_connectivity_signal():
    service = CommanderChatOpsService()
    now = datetime.utcnow()
    token_updated_at = (now - timedelta(minutes=40)).strftime("%Y-%m-%d %H:%M:%S")
    callback_updated_at = (now - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    historical_message_at = (now - timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S")
    recent_verify_at = (now - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
    events = [
        {
            "id": 2,
            "channel": "notification_platform",
            "source": "event_subscription",
            "event_type": "message",
            "message": "状态",
            "from_user": "real-user",
            "chat_id": "oc_live_group",
            "response": "The latest notification command was received and successfully sent back to the group.",
            "status": "ok",
            "delivery_configured": 1,
            "delivery_delivered": 1,
            "delivery_failed": 0,
            "created_at": historical_message_at,
        },
        {
            "id": 1,
            "channel": "notification_platform",
            "source": "event_subscription",
            "event_type": "url_verification",
            "message": "url_verification",
            "from_user": "",
            "chat_id": "",
            "response": "challenge accepted",
            "status": "verified",
            "delivery_configured": 0,
            "delivery_delivered": 0,
            "delivery_failed": 0,
            "created_at": recent_verify_at,
        },
    ]
    webhooks = [
        {"id": "wh_1", "name": "NotificationPlatform Production Alert", "enabled": 1, "last_test_success": 1},
    ]

    with patch("services.commander_chatops_service.query_all", side_effect=_query_all_side_effect(events, webhooks)), \
         patch.object(
             CommanderChatOpsService,
             "_probe_callback_url",
             return_value={
                 "attempted": True,
                 "success": False,
                 "issue": "timeout",
                 "summary": "Public callback probe timed out.",
                 "status_code": 0,
                 "content_type": "",
                 "response_excerpt": "timeout",
                 "probed_at": now.strftime("%Y-%m-%dT%H:%M:%S"),
             },
         ), \
         patch.object(CommanderChatOpsService, "_save_probe_history"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL", "https://ops.example.com"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL_UPDATED_AT", callback_updated_at), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", token_updated_at), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_ID", "cli_demo_bot"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_SECRET", "secret-demo"), \
         patch.object(CommanderChatOpsService, "_load_latest_app_bot_check", return_value={"success": True}):
        overview = service.get_overview()

    assert overview["subscription_check_recent_success"] is True
    assert overview["external_connected"] is True
    assert overview["external_connected_current"] is True
    assert overview["external_connection_stale"] is False
    assert overview["external_callback_ready"] is True
    assert overview["direct_chat_ready"] is True
    assert overview["ready"] is True
    assert "The latest notification challenge passed" in overview["summary"]
    assert "the bidirectional channel remains usable" in overview["summary"]
    assert "the bidirectional channel remains usable" in overview["callback_recommendation"]


def test_chatops_overview_treats_legacy_self_check_event_as_non_external_history():
    service = CommanderChatOpsService()
    now = datetime.now()
    token_updated_at = (now - timedelta(minutes=120)).strftime("%Y-%m-%d %H:%M:%S")
    callback_updated_at = (now - timedelta(minutes=119)).strftime("%Y-%m-%d %H:%M:%S")
    legacy_self_check_at = (now - timedelta(minutes=110)).strftime("%Y-%m-%d %H:%M:%S")
    recent_verify_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    events = [
        {
            "id": 2,
            "channel": "notification_platform",
            "source": "event_subscription",
            "event_type": "message",
            "message": "status",
            "from_user": "user",
            "chat_id": "oc_external_self_check",
            "response": "📡 Legion status",
            "status": "ok",
            "delivery_configured": 1,
            "delivery_delivered": 1,
            "delivery_failed": 0,
            "created_at": legacy_self_check_at,
        },
        {
            "id": 1,
            "channel": "notification_platform",
            "source": "event_subscription",
            "event_type": "url_verification",
            "message": "url_verification",
            "from_user": "",
            "chat_id": "",
            "response": "challenge accepted",
            "status": "verified",
            "delivery_configured": 0,
            "delivery_delivered": 0,
            "delivery_failed": 0,
            "created_at": recent_verify_at,
        },
    ]
    webhooks = [
        {"id": "wh_1", "name": "NotificationPlatform Production Alert", "enabled": 1, "last_test_success": 1},
    ]

    with patch("services.commander_chatops_service.query_all", side_effect=_query_all_side_effect(events, webhooks)), \
         patch.object(
             CommanderChatOpsService,
             "_probe_callback_url",
             return_value={
                 "attempted": True,
                 "success": False,
                 "issue": "connect_error",
                 "summary": "Public callback probe failed: ConnectionError",
                 "status_code": 0,
                 "content_type": "",
                 "response_excerpt": "ConnectionError",
                 "probed_at": "2026-03-19T08:40:28",
             },
         ), \
         patch.object(CommanderChatOpsService, "_save_probe_history"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL", "https://ops.example.com"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL_UPDATED_AT", callback_updated_at), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", token_updated_at):
        overview = service.get_overview()

    assert overview["external_connected_history_observed"] is False
    assert overview["external_connected"] is False
    assert overview["direct_chat_ready"] is False
    assert overview["latest_external_success_at"] == ""
    assert "The platform previously received real notification group messages" not in overview["summary"]


def test_chatops_overview_treats_pinggy_live_status_as_synthetic_validation_message():
    service = CommanderChatOpsService()
    now = datetime.now()
    token_updated_at = (now - timedelta(minutes=120)).strftime("%Y-%m-%d %H:%M:%S")
    callback_updated_at = (now - timedelta(minutes=119)).strftime("%Y-%m-%d %H:%M:%S")
    synthetic_message_at = (now - timedelta(minutes=100)).strftime("%Y-%m-%d %H:%M:%S")
    recent_verify_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    events = [
        {
            "id": 2,
            "channel": "notification_platform",
            "source": "event_subscription",
            "event_type": "message",
            "message": "status",
            "from_user": "user",
            "chat_id": "oc_pinggy_live_status",
            "response": "📡 Legion status",
            "status": "ok",
            "delivery_configured": 1,
            "delivery_delivered": 1,
            "delivery_failed": 0,
            "created_at": synthetic_message_at,
        },
        {
            "id": 1,
            "channel": "notification_platform",
            "source": "event_subscription",
            "event_type": "url_verification",
            "message": "url_verification",
            "from_user": "",
            "chat_id": "",
            "response": "challenge accepted",
            "status": "verified",
            "delivery_configured": 0,
            "delivery_delivered": 0,
            "delivery_failed": 0,
            "created_at": recent_verify_at,
        },
    ]
    webhooks = [
        {"id": "wh_1", "name": "NotificationPlatform Production Alert", "enabled": 1, "last_test_success": 1},
    ]

    with patch("services.commander_chatops_service.query_all", side_effect=_query_all_side_effect(events, webhooks)), \
         patch.object(
             CommanderChatOpsService,
             "_probe_callback_url",
             return_value={
                 "attempted": True,
                 "success": False,
                 "issue": "connect_error",
                 "summary": "Public callback probe failed: ConnectionError",
                 "status_code": 0,
                 "content_type": "",
                 "response_excerpt": "ConnectionError",
                 "probed_at": "2026-03-19T08:42:10",
             },
         ), \
         patch.object(CommanderChatOpsService, "_save_probe_history"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL", "https://ops.example.com"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL_UPDATED_AT", callback_updated_at), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", token_updated_at):
        overview = service.get_overview()

    assert overview["external_connected_history_observed"] is False
    assert overview["external_connected"] is False
    assert overview["latest_external_success_at"] == ""
    assert overview["latest_external_self_check_at"] == synthetic_message_at


def test_chatops_overview_exposes_single_robot_strategy_with_webhook_fallback():
    service = CommanderChatOpsService()
    events = [
        {
            "id": 3,
            "channel": "notification_platform",
            "source": "event_subscription",
            "event_type": "message",
            "message": "状态",
            "from_user": "user",
            "chat_id": "oc_real_group",
            "response": "📡 Legion status",
            "status": "ok",
            "delivery_configured": 1,
            "delivery_delivered": 1,
            "delivery_failed": 0,
            "created_at": "2026-03-19 10:05:00",
        },
        {
            "id": 2,
            "channel": "notification_platform",
            "source": "subscription_self_check",
            "event_type": "url_verification",
            "message": "url_verification",
            "from_user": "",
            "chat_id": "",
            "response": "challenge accepted",
            "status": "verified",
            "delivery_configured": 0,
            "delivery_delivered": 0,
            "delivery_failed": 0,
            "created_at": "2026-03-19 10:03:00",
        },
    ]
    webhooks = [
        {"id": "wh_1", "name": "NotificationPlatform Production Alert", "enabled": 1, "last_test_success": 1},
    ]
    app_bot_checks = [
        {
            "id": 1,
            "success": 1,
            "message": "App bot credentials validated; tenant_access_token obtained successfully.",
            "status_code": 200,
            "source": "config_save",
            "app_id_masked": "cli...app",
            "created_at": "2026-03-19 10:04:30",
        },
    ]

    with patch("services.commander_chatops_service.query_all", side_effect=_query_all_side_effect(events, webhooks, [], [], app_bot_checks)), \
         patch.object(
             CommanderChatOpsService,
             "_probe_callback_url",
             return_value={
                 "attempted": True,
                 "success": True,
                 "issue": "",
                 "summary": "Public callback URL passed an active probe; the current endpoint is publicly reachable.",
                 "status_code": 200,
                 "content_type": "application/json",
                 "response_excerpt": '{"challenge":"chatops-probe"}',
                 "probed_at": "2026-03-19T10:04:00",
             },
         ), \
         patch.object(CommanderChatOpsService, "_save_probe_history"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL", "https://ops.example.com"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", "2026-03-19 10:00:00"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_ID", "cli_demo_app"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_SECRET", "secret-demo"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_BOT_UPDATED_AT", "2026-03-19 09:59:00"):
        overview = service.get_overview()

    assert overview["app_bot_configured"] is True
    assert overview["app_bot_ready"] is True
    assert overview["webhook_ready"] is True
    assert overview["direct_chat_ready"] is True
    assert overview["unified_robot_target"] is True
    assert overview["unified_robot_platform_ready"] is True
    assert overview["unified_robot_ready"] is True
    assert overview["delivery_strategy"] == "single_robot_with_webhook_fallback"
    assert "Webhook as a fallback notification channel" in overview["delivery_strategy_summary"]


def test_chatops_overview_marks_unified_robot_as_in_progress_without_app_bot():
    service = CommanderChatOpsService()
    events = []
    webhooks = [
        {"id": "wh_1", "name": "NotificationPlatform Production Alert", "enabled": 1, "last_test_success": 1},
    ]

    with patch.dict("os.environ", {"NOTIFICATION_PLATFORM_APP_ID": "", "NOTIFICATION_PLATFORM_APP_SECRET": ""}, clear=False), \
         patch("services.commander_chatops_service.os.getenv", side_effect=lambda key, default='': {
             "NOTIFICATION_PLATFORM_APP_ID": "",
             "NOTIFICATION_PLATFORM_APP_SECRET": "",
             "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT": "",
             "PUBLIC_API_BASE_URL_UPDATED_AT": "",
         }.get(key, default)), \
         patch("services.commander_chatops_service.query_all", side_effect=_query_all_side_effect(events, webhooks)), \
         patch.object(
             CommanderChatOpsService,
             "_probe_callback_url",
             return_value={
                 "attempted": True,
                 "success": True,
                 "issue": "",
                 "summary": "Public callback URL passed an active probe; the current endpoint is publicly reachable.",
                 "status_code": 200,
                 "content_type": "application/json",
                 "response_excerpt": '{"challenge":"chatops-probe"}',
                 "probed_at": "2026-03-19T10:04:00",
             },
         ), \
         patch.object(CommanderChatOpsService, "_save_probe_history"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL", "https://ops.example.com"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", "2026-03-19 10:00:00"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_ID", ""), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_SECRET", ""):
        overview = service.get_overview()

    assert overview["ready"] is False
    assert overview["platform_ready"] is False
    assert overview["delivery_strategy"] in {"webhook_only", "single_robot_with_webhook_fallback"}


def test_chatops_overview_exposes_recent_chat_bindings():
    service = CommanderChatOpsService()
    events = []
    webhooks = [
        {"id": "wh_1", "name": "NotificationPlatform Production Alert", "enabled": 1, "last_test_success": 1},
    ]
    bindings = [
        {
            "chat_id": "oc_group_a",
            "channel": "notification_platform",
            "source": "event_subscription",
            "last_from_user": "ou_real_a",
            "last_message": "状态",
            "last_seen_at": "2026-03-19 10:05:00",
            "last_reply_mode": "app_bot",
            "last_delivery_ok": 1,
        },
        {
            "chat_id": "oc_group_b",
            "channel": "notification_platform",
            "source": "event_subscription",
            "last_from_user": "ou_real_b",
            "last_message": "报告 125c69cd",
            "last_seen_at": "2026-03-19 10:03:00",
            "last_reply_mode": "app_bot_fallback_webhook",
            "last_delivery_ok": 0,
        },
        {
            "chat_id": "oc_external_self_check",
            "channel": "notification_platform",
            "source": "external_self_check",
            "last_from_user": "user",
            "last_message": "status",
            "last_seen_at": "2026-03-19 10:06:00",
            "last_reply_mode": "app_bot_fallback_webhook",
            "last_delivery_ok": 1,
        },
        {
            "chat_id": "oc_demo",
            "channel": "notification_platform",
            "source": "event_subscription",
            "last_from_user": "ou_demo",
            "last_message": "状态",
            "last_seen_at": "2026-03-19 10:07:00",
            "last_reply_mode": "app_bot",
            "last_delivery_ok": 1,
        },
    ]
    app_bot_checks = [
        {
            "id": 1,
            "success": 1,
            "message": "App bot credentials validated; tenant_access_token obtained successfully.",
            "status_code": 200,
            "source": "config_save",
            "app_id_masked": "cli...app",
            "created_at": "2026-03-19 10:04:30",
        },
    ]

    with patch.dict("os.environ", {"NOTIFICATION_PLATFORM_APP_ID": "", "NOTIFICATION_PLATFORM_APP_SECRET": ""}, clear=False), \
         patch("services.commander_chatops_service.query_all", side_effect=_query_all_side_effect(events, webhooks, [], bindings, app_bot_checks)), \
         patch.object(
             CommanderChatOpsService,
             "_probe_callback_url",
             return_value={
                 "attempted": True,
                 "success": True,
                 "issue": "",
                 "summary": "Public callback URL passed an active probe; the current endpoint is publicly reachable.",
                 "status_code": 200,
                 "content_type": "application/json",
                 "response_excerpt": '{"challenge":"chatops-probe"}',
                 "probed_at": "2026-03-19T10:04:00",
             },
         ), \
         patch.object(CommanderChatOpsService, "_save_probe_history"), \
         patch("services.commander_chatops_service.Config.PUBLIC_API_BASE_URL", "https://ops.example.com"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "demo-token"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_ID", "cli_demo_app"), \
         patch("services.commander_chatops_service.Config.NOTIFICATION_PLATFORM_APP_SECRET", "secret-demo"):
        overview = service.get_overview()

    assert len(overview["recent_chat_bindings"]) == 2
    assert overview["recent_chat_bindings"][0]["chat_id"] == "oc_group_a"
    assert overview["recent_chat_bindings"][0]["last_reply_mode"] == "app_bot"
    assert overview["recent_chat_bindings"][1]["chat_id"] == "oc_group_b"
    assert overview["recent_chat_bindings"][1]["last_reply_mode"] == "app_bot_fallback_webhook"
    assert all(item["chat_id"] not in {"oc_external_self_check", "oc_demo"} for item in overview["recent_chat_bindings"])


def test_chatops_local_tunnel_status_detects_running_process(tmp_path):
    service = CommanderChatOpsService()
    script_path = tmp_path / "start_native_reverse_tunnel.ps1"
    script_path.write_text("Write-Host started", encoding="utf-8")
    stdout_log = tmp_path / "stdout.log"
    stderr_log = tmp_path / "stderr.log"
    stdout_log.write_text("native_ssh_reverse_tunnel_pid=1234", encoding="utf-8")
    stderr_log.write_text("", encoding="utf-8")

    proc_payload = {
        "ProcessId": 1234,
        "CreationDate": "20260320114500.000000+480",
        "CommandLine": "ssh.exe -NT -R 127.0.0.1:18020:127.0.0.1:8020 root@test.example-user.top",
    }

    with patch("services.commander_chatops_service.os.name", "nt"), \
         patch.object(CommanderChatOpsService, "_local_tunnel_script_path", return_value=script_path), \
         patch.object(CommanderChatOpsService, "_local_tunnel_log_paths", return_value={"stdout": stdout_log, "stderr": stderr_log}), \
         patch("services.commander_chatops_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(proc_payload, ensure_ascii=False),
            stderr="",
        )
        status = service._get_local_tunnel_status()

    assert status["supported"] is True
    assert status["script_exists"] is True
    assert status["running"] is True
    assert status["pid"] == 1234
    assert status["status"] == "running"
    assert "PID 1234" in status["summary"]
    assert status["stdout_tail"] == "native_ssh_reverse_tunnel_pid=1234"
    assert status["stderr_tail"] == ""
    assert "127.0.0.1:18020:127.0.0.1:8020" in status["command_line"]


def test_chatops_restart_local_tunnel_returns_running_overview(tmp_path):
    service = CommanderChatOpsService()
    script_path = tmp_path / "start_native_reverse_tunnel.ps1"
    script_path.write_text("Write-Host started", encoding="utf-8")
    before = {
        "supported": True,
        "script_path": str(script_path),
        "script_exists": True,
        "running": False,
        "status": "stopped",
        "summary": "No local OpenSSH reverse tunnel process detected.",
    }
    after = {
        "supported": True,
        "script_path": str(script_path),
        "script_exists": True,
        "running": True,
        "pid": 4321,
        "status": "running",
        "summary": "Local OpenSSH reverse tunnel process detected (PID 4321).",
        "stdout_tail": "native_ssh_reverse_tunnel_pid=4321",
        "stderr_tail": "",
    }

    with patch.object(service, "_get_local_tunnel_status", side_effect=[before, after]), \
         patch.object(service, "get_overview", return_value={"local_tunnel": after}), \
         patch("services.commander_chatops_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="native_ssh_reverse_tunnel_pid=4321",
            stderr="",
        )
        result = service.restart_local_tunnel()

    assert result["ok"] is True
    assert result["message"] == "Local reverse tunnel restarted."
    assert result["stdout"] == "native_ssh_reverse_tunnel_pid=4321"
    assert result["stderr"] == ""
    assert result["tunnel"]["running"] is True
    assert result["tunnel"]["pid"] == 4321
    assert result["overview"]["local_tunnel"]["running"] is True
