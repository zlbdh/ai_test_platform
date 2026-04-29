# -*- coding: utf-8 -*-
"""
NotifyGateway — A2P 通知推送网关

多通道插件架构：
- ConsoleChannel:  控制台输出（默认, 零配置）
- WebhookChannel:  企微/钉钉 Webhook
- EmailChannel:    SMTP 邮件

通知等级：
- CRITICAL: 核心接口崩溃 → 全渠道推送
- INFO:     测试完成     → IM 群通知
- REPORT:   每日汇总     → 邮件
- LOG:      内部日志     → 本地存储
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


# ── 数据结构 ──────────────────────────────────────────────────────────────────


class NotifyLevel(Enum):
    """通知等级"""
    CRITICAL = "critical"   # 🔴 核心故障
    INFO = "info"           # 🟡 测试完成
    REPORT = "report"       # ⚪ 日报/汇总
    LOG = "log"             # 📝 内部日志


@dataclass
class Notification:
    """通知消息"""
    notification_id: str = field(default_factory=lambda: f"n-{int(time.time()*1000)}")
    level: NotifyLevel = NotifyLevel.INFO
    title: str = ""
    body: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    channels_sent: List[str] = field(default_factory=list)


# ── 通道接口 ─────────────────────────────────────────────────────────────────


class NotifyChannel(ABC):
    """通知通道基类"""
    name: str = "base"

    @abstractmethod
    async def send(self, notification: Notification) -> bool:
        """发送通知，返回是否成功"""
        ...


class ConsoleChannel(NotifyChannel):
    """控制台通道（默认, 零配置）"""
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
    """企微/钉钉 Webhook 通道"""
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
                # 企业微信群机器人
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
                # 钉钉群机器人
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
                # 通用 Webhook
                payload = asdict(notification)
                payload["level"] = notification.level.value

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        logger.info(f"[Notify] Webhook 发送成功: {notification.title}")
                        return True
                    else:
                        text = await resp.text()
                        logger.warning(f"[Notify] Webhook 响应异常: {resp.status} {text}")
                        return False

        except ImportError:
            logger.warning("[Notify] aiohttp 未安装，跳过 Webhook 通知")
            return False
        except Exception as e:
            logger.error(f"[Notify] Webhook 发送失败: {e}")
            return False


class EmailChannel(NotifyChannel):
    """SMTP 邮件通道"""
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
                msg["Subject"] = f"[AI测试平台] {notification.title}"
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
            logger.info(f"[Notify] 邮件发送成功: {notification.title}")
            return True

        except Exception as e:
            logger.error(f"[Notify] 邮件发送失败: {e}")
            return False


# ── NotifyGateway 核心 ───────────────────────────────────────────────────────


class NotifyGateway:
    """
    A2P 通知推送网关

    自动根据 .env 配置启用通道。
    默认始终启用 ConsoleChannel。
    """

    def __init__(self):
        self._channels: List[NotifyChannel] = []
        self._history: List[Notification] = []
        self._max_history = 200

        # 始终启用控制台
        self._channels.append(ConsoleChannel())

        # 从环境变量配置其他通道
        self._init_from_env()

        logger.info(
            f"[NotifyGateway] 初始化完成，活跃通道: "
            f"{[c.name for c in self._channels]}"
        )

    def _init_from_env(self) -> None:
        """从环境变量初始化通道"""
        # 企微/钉钉 Webhook
        webhook_url = os.environ.get("NOTIFY_WEBHOOK_URL", "")
        webhook_type = os.environ.get("NOTIFY_WEBHOOK_TYPE", "wecom")
        if webhook_url:
            self._channels.append(WebhookChannel(webhook_url, webhook_type))

        # 邮件
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
        """动态添加通知通道"""
        self._channels.append(channel)

    async def send(
        self,
        level: str = "info",
        title: str = "",
        body: str = "",
        data: Optional[Dict] = None,
    ) -> Notification:
        """
        发送通知。

        Args:
            level: 通知等级 (critical/info/report/log)
            title: 标题
            body: 正文
            data: 附加数据

        Returns:
            Notification 对象
        """
        notification = Notification(
            level=NotifyLevel(level),
            title=title,
            body=body,
            data=data or {},
        )

        # 根据等级决定发送到哪些通道
        for channel in self._channels:
            try:
                # CRITICAL 发送到所有通道
                # INFO 发送到 console + webhook
                # REPORT 发送到 console + email
                # LOG 只发送到 console
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
                logger.error(f"[NotifyGateway] 通道 {channel.name} 发送失败: {e}")

        # 记录历史
        self._history.append(notification)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        return notification

    def get_history(self, limit: int = 20) -> List[Dict]:
        """获取通知历史"""
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


# ── 单例 ─────────────────────────────────────────────────────────────────────

_gateway: Optional[NotifyGateway] = None


def get_notify_gateway() -> NotifyGateway:
    """获取 NotifyGateway 单例"""
    global _gateway
    if _gateway is None:
        _gateway = NotifyGateway()
    return _gateway
