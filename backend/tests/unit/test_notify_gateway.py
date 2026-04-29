"""
notify_gateway 单元测试
覆盖: channel 初始化、Webhook/Email 通道、等级路由、历史裁剪、环境变量加载
"""
from email import message_from_string
from email.header import decode_header, make_header
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.notify_gateway import (
    ConsoleChannel,
    EmailChannel,
    Notification,
    NotifyGateway,
    NotifyLevel,
    WebhookChannel,
)


class _FakeAsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeWebhookResponse:
    def __init__(self, status=200, text="ok"):
        self.status = status
        self._text = text

    async def text(self):
        return self._text


class _FakeWebhookSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json=None, timeout=None):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return _FakeAsyncContext(self.response)


class _FakeSmtpServer:
    def __init__(self):
        self.logged_in = None
        self.sent = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def login(self, user, password):
        self.logged_in = (user, password)

    def sendmail(self, from_addr, to_addrs, message):
        self.sent = (from_addr, to_addrs, message)


class _DummyChannel:
    def __init__(self, name, should_succeed=True, should_raise=False):
        self.name = name
        self.should_succeed = should_succeed
        self.should_raise = should_raise
        self.calls = []

    async def send(self, notification):
        self.calls.append(notification)
        if self.should_raise:
            raise RuntimeError(f"{self.name} boom")
        return self.should_succeed


class TestConsoleChannel:
    @pytest.mark.asyncio
    async def test_send_returns_true(self):
        channel = ConsoleChannel()
        notification = Notification(level=NotifyLevel.LOG, title="日志", body="内容")
        assert await channel.send(notification) is True


class TestWebhookChannel:
    @pytest.mark.asyncio
    async def test_returns_false_without_url(self):
        channel = WebhookChannel()
        assert await channel.send(Notification()) is False

    @pytest.mark.asyncio
    async def test_wecom_payload_success(self):
        response = _FakeWebhookResponse(status=200)
        session = _FakeWebhookSession(response)
        aiohttp = SimpleNamespace(
            ClientSession=lambda: session,
            ClientTimeout=lambda total: {"total": total},
        )
        channel = WebhookChannel("https://example.com/webhook", "wecom")
        notification = Notification(title="报告", body="正文")

        with patch.dict(sys.modules, {"aiohttp": aiohttp}):
            result = await channel.send(notification)

        assert result is True
        assert session.calls[0]["json"]["msgtype"] == "markdown"
        assert "### 报告" in session.calls[0]["json"]["markdown"]["content"]

    @pytest.mark.asyncio
    async def test_dingtalk_payload_non_200(self):
        response = _FakeWebhookResponse(status=500, text="failed")
        session = _FakeWebhookSession(response)
        aiohttp = SimpleNamespace(
            ClientSession=lambda: session,
            ClientTimeout=lambda total: {"total": total},
        )
        channel = WebhookChannel("https://example.com/webhook", "dingtalk")

        with patch.dict(sys.modules, {"aiohttp": aiohttp}):
            result = await channel.send(Notification(title="报告", body="正文"))

        assert result is False
        assert session.calls[0]["json"]["markdown"]["title"] == "报告"

    @pytest.mark.asyncio
    async def test_custom_payload_uses_serialized_notification(self):
        response = _FakeWebhookResponse(status=200)
        session = _FakeWebhookSession(response)
        aiohttp = SimpleNamespace(
            ClientSession=lambda: session,
            ClientTimeout=lambda total: {"total": total},
        )
        notification = Notification(level=NotifyLevel.CRITICAL, title="报告", body="正文")
        channel = WebhookChannel("https://example.com/webhook", "custom")

        with patch.dict(sys.modules, {"aiohttp": aiohttp}):
            result = await channel.send(notification)

        assert result is True
        assert session.calls[0]["json"]["level"] == "critical"

    @pytest.mark.asyncio
    async def test_import_error_returns_false(self):
        channel = WebhookChannel("https://example.com/webhook", "wecom")

        original_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "aiohttp":
                raise ImportError("missing aiohttp")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            result = await channel.send(Notification(title="报告"))

        assert result is False


class TestEmailChannel:
    @pytest.mark.asyncio
    async def test_returns_false_when_missing_config(self):
        channel = EmailChannel(smtp_host="smtp.example.com", to_addrs=["  "])
        assert await channel.send(Notification(title="报告")) is False

    @pytest.mark.asyncio
    async def test_send_success(self):
        smtp_server = _FakeSmtpServer()
        channel = EmailChannel(
            smtp_host="smtp.example.com",
            smtp_port=465,
            smtp_user="robot@example.com",
            smtp_pass="secret",
            to_addrs=[" a@example.com ", "", "b@example.com"],
        )
        notification = Notification(title="日报", body="内容")

        async def run_sync(func):
            func()

        with patch("asyncio.to_thread", side_effect=run_sync), \
             patch("smtplib.SMTP_SSL", return_value=smtp_server):
            result = await channel.send(notification)

        assert result is True
        assert smtp_server.logged_in == ("robot@example.com", "secret")
        assert smtp_server.sent[1] == ["a@example.com", "b@example.com"]
        parsed = message_from_string(smtp_server.sent[2])
        subject = str(make_header(decode_header(parsed["Subject"])))
        assert subject == "[AI测试平台] 日报"

    @pytest.mark.asyncio
    async def test_send_failure_returns_false(self):
        channel = EmailChannel(
            smtp_host="smtp.example.com",
            smtp_user="robot@example.com",
            smtp_pass="secret",
            to_addrs=["a@example.com"],
        )

        with patch("asyncio.to_thread", side_effect=RuntimeError("smtp down")):
            result = await channel.send(Notification(title="日报"))

        assert result is False


class TestNotifyGateway:
    def test_init_from_env_adds_channels(self):
        with patch.dict("os.environ", {
            "NOTIFY_WEBHOOK_URL": "https://example.com/webhook",
            "NOTIFY_WEBHOOK_TYPE": "dingtalk",
            "NOTIFY_SMTP_HOST": "smtp.example.com",
            "NOTIFY_SMTP_PORT": "587",
            "NOTIFY_SMTP_USER": "robot@example.com",
            "NOTIFY_SMTP_PASS": "secret",
            "NOTIFY_EMAIL_TO": " a@example.com , ,b@example.com ",
        }, clear=False):
            gateway = NotifyGateway()

        assert [channel.name for channel in gateway._channels] == ["console", "webhook", "email"]
        email_channel = next(channel for channel in gateway._channels if channel.name == "email")
        assert email_channel.to_addrs == ["a@example.com", "b@example.com"]

    @pytest.mark.asyncio
    async def test_send_routes_by_level_and_records_history(self):
        gateway = NotifyGateway()
        console = _DummyChannel("console")
        webhook = _DummyChannel("webhook")
        email = _DummyChannel("email")
        gateway._channels = [console, webhook, email]

        info_notice = await gateway.send(level="info", title="完成", body="通过")
        report_notice = await gateway.send(level="report", title="日报", body="内容")
        log_notice = await gateway.send(level="log", title="日志", body="内容")
        critical_notice = await gateway.send(level="critical", title="故障", body="内容")

        assert info_notice.channels_sent == ["console", "webhook"]
        assert report_notice.channels_sent == ["console", "email"]
        assert log_notice.channels_sent == ["console"]
        assert critical_notice.channels_sent == ["console", "webhook", "email"]
        assert len(gateway.get_history()) == 4

    @pytest.mark.asyncio
    async def test_send_tolerates_channel_exception_and_trims_history(self):
        gateway = NotifyGateway()
        gateway._max_history = 2
        gateway._channels = [
            _DummyChannel("console"),
            _DummyChannel("webhook", should_raise=True),
        ]

        await gateway.send(level="critical", title="1", body="a")
        await gateway.send(level="critical", title="2", body="b")
        third = await gateway.send(level="critical", title="3", body="c")

        history = gateway.get_history(limit=10)
        assert third.channels_sent == ["console"]
        assert [item["title"] for item in history] == ["2", "3"]
