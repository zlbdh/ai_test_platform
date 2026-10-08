# -*- coding: utf-8 -*-
"""
NotifyGateway — A2P notification gateway

Multichannel plugin architecture:
- ConsoleChannel:  Console output (default, no configuration)
- WebhookChannel:  WeCom/DingTalk webhook
- EmailChannel:    SMTP email

Notification levels:
- CRITICAL: Critical API failure → all channels
- INFO:     Test completion → group-chat notification
- REPORT:   Daily summary → email
- LOG:      Internal logs → local storage
"""

import asyncio
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Data structures ──────────────────────────────────────────────────────────────────


class NotifyLevel(Enum):
    """Notification level"""
    CRITICAL = "critical"   # 🔴 Critical failure
    INFO = "info"           # 🟡 Test completed
    REPORT = "report"       # ⚪ Daily report/summary
    LOG = "log"             # 📝 Internal logs


@dataclass
class Notification:
    """Notification message"""
    notification_id: str = field(default_factory=lambda: f"n-{int(time.time()*1000)}")
    level: NotifyLevel = NotifyLevel.INFO
    title: str = ""
    body: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    channels_sent: List[str] = field(default_factory=list)


# ── Channel interface ─────────────────────────────────────────────────────────────────


class NotifyChannel(ABC):
    """Notification channel base class"""
    name: str = "base"

    @abstractmethod
    async def send(self, notification: Notification) -> bool:
        """Send a notification and return whether it succeeded"""
        ...


class ConsoleChannel(NotifyChannel):
    """Console channel (default, no configuration)"""
    name = "console"

    async def send(self, notification: Notification) -> bool:
        icon = {
            NotifyLevel.CRITICAL: "🔴",
            NotifyLevel.INFO: "🟡",
            NotifyLevel.REPORT: "⚪",
            NotifyLevel.LOG: "📝",
        }.get(notification.level, "📌")

        logger.info(
            f"[Notify] {icon} [{notification.level.value.upper()}] "
            f"{notification.title}\n{notification.body}"
        )
        return True


class WebhookChannel(NotifyChannel):
    """WeCom/DingTalk webhook channel"""
    name = "webhook"

    def __init__(self, webhook_url: str = "", webhook_type: str = "wecom"):
        self.webhook_url = webhook_url
        self.webhook_type = webhook_type  # wecom / dingtalk / notification_platform / custom

    async def send(self, notification: Notification) -> bool:
        if not self.webhook_url:
            return False

        try:
            import aiohttp

            if self.webhook_type == "wecom":
                # WeCom group bot
                payload = {
                    "msgtype": "markdown",
                    "markdown": {
                        "content": (
                            f"### {notification.title}\n"
                            f"{notification.body}\n"
                            f"> {notification.timestamp}"
                        ),
                    },
                }
            elif self.webhook_type == "dingtalk":
                # DingTalk group bot
                payload = {
                    "msgtype": "markdown",
                    "markdown": {
                        "title": notification.title,
                        "text": (
                            f"### {notification.title}\n"
                            f"{notification.body}\n"
                            f"> {notification.timestamp}"
                        ),
                    },
                }
            else:
                # Generic webhook
                payload = asdict(notification)
                payload["level"] = notification.level.value

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        logger.info(f"[Notify] Webhook sent successfully: {notification.title}")
                        return True
                    else:
                        text = await resp.text()
                        logger.warning(f"[Notify] Unexpected webhook response: {resp.status} {text}")
                        return False

        except ImportError:
            logger.warning("[Notify] aiohttp is not installed; skipping webhook notifications")
            return False
        except Exception as e:
            logger.error(f"[Notify] Failed to send webhook: {e}")
            return False


class EmailChannel(NotifyChannel):
    """SMTP email channel"""
    name = "email"

    def __init__(
        self,
        smtp_host: str = "",
        smtp_port: int = 465,
        smtp_user: str = "",
        smtp_pass: str = "",
        to_addrs: List[str] = None,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_pass = smtp_pass
        self.to_addrs = [addr.strip() for addr in (to_addrs or []) if addr and addr.strip()]

    async def send(self, notification: Notification) -> bool:
        if not all([self.smtp_host, self.smtp_user, self.smtp_pass, self.to_addrs]):
            return False

        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            def _send():
                msg = MIMEMultipart("alternative")
                msg["Subject"] = f"[AI Test Platform] {notification.title}"
                msg["From"] = self.smtp_user
                msg["To"] = ", ".join(self.to_addrs)

                html = f"""
                <h2>{notification.title}</h2>
                <pre>{notification.body}</pre>
                <hr>
                <small>{notification.timestamp}</small>
                """
                msg.attach(MIMEText(html, "html", "utf-8"))

                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as server:
                    server.login(self.smtp_user, self.smtp_pass)
                    server.sendmail(self.smtp_user, self.to_addrs, msg.as_string())

            await asyncio.to_thread(_send)
            logger.info(f"[Notify] Email sent successfully: {notification.title}")
            return True

        except Exception as e:
            logger.error(f"[Notify] Failed to send email: {e}")
            return False


# ── NotifyGateway core ───────────────────────────────────────────────────────


class NotifyGateway:
    """
    A2P notification gateway

    Enable channels automatically from .env configuration.
    ConsoleChannel is always enabled by default.
    """

    def __init__(self):
        self._channels: List[NotifyChannel] = []
        self._history: List[Notification] = []
        self._max_history = 200

        # Always enable the console
        self._channels.append(ConsoleChannel())

        # Configure other channels from environment variables
        self._init_from_env()

        logger.info(
            f"[NotifyGateway] Initialized; active channels: "
            f"{[c.name for c in self._channels]}"
        )

    def _init_from_env(self) -> None:
        """Initialize channels from environment variables"""
        # WeCom/DingTalk webhook
        webhook_url = os.environ.get("NOTIFY_WEBHOOK_URL", "")
        webhook_type = os.environ.get("NOTIFY_WEBHOOK_TYPE", "wecom")
        if webhook_url:
            self._channels.append(WebhookChannel(webhook_url, webhook_type))

        # Email
        smtp_host = os.environ.get("NOTIFY_SMTP_HOST", "")
        if smtp_host:
            self._channels.append(EmailChannel(
                smtp_host=smtp_host,
                smtp_port=int(os.environ.get("NOTIFY_SMTP_PORT", "465")),
                smtp_user=os.environ.get("NOTIFY_SMTP_USER", ""),
                smtp_pass=os.environ.get("NOTIFY_SMTP_PASS", ""),
                to_addrs=os.environ.get("NOTIFY_EMAIL_TO", "").split(","),
            ))

    def add_channel(self, channel: NotifyChannel) -> None:
        """Add a notification channel dynamically"""
        self._channels.append(channel)

    async def send(
        self,
        level: str = "info",
        title: str = "",
        body: str = "",
        data: Optional[Dict] = None,
    ) -> Notification:
        """
        Send a notification.

        Args:
            level: Notification level (critical/info/report/log)
            title: Title
            body: Body
            data: Additional data

        Returns:
            Notification object
        """
        notification = Notification(
            level=NotifyLevel(level),
            title=title,
            body=body,
            data=data or {},
        )

        # Choose channels according to the notification level
        for channel in self._channels:
            try:
                # Send CRITICAL notifications to every channel
                # Send INFO notifications to console and webhook
                # Send REPORT notifications to console and email
                # Send LOG notifications only to console
                should_send = False
                if notification.level == NotifyLevel.CRITICAL:
                    should_send = True
                elif notification.level == NotifyLevel.INFO:
                    should_send = channel.name in ("console", "webhook")
                elif notification.level == NotifyLevel.REPORT:
                    should_send = channel.name in ("console", "email")
                elif notification.level == NotifyLevel.LOG:
                    should_send = channel.name == "console"

                if should_send:
                    success = await channel.send(notification)
                    if success:
                        notification.channels_sent.append(channel.name)

            except Exception as e:
                logger.error(f"[NotifyGateway] Channel {channel.name} failed to send: {e}")

        # Record history
        self._history.append(notification)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        return notification

    def get_history(self, limit: int = 20) -> List[Dict]:
        """Get notification history"""
        return [
            {
                "id": n.notification_id,
                "level": n.level.value,
                "title": n.title,
                "body": n.body[:200],
                "channels": n.channels_sent,
                "timestamp": n.timestamp,
            }
            for n in self._history[-limit:]
        ]


# ── Singleton ─────────────────────────────────────────────────────────────────────

_gateway: Optional[NotifyGateway] = None


def get_notify_gateway() -> NotifyGateway:
    """Get the NotifyGateway singleton"""
    global _gateway
    if _gateway is None:
        _gateway = NotifyGateway()
    return _gateway
