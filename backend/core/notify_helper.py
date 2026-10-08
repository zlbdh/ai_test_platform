# -*- coding: utf-8 -*-
"""
Notification helpers called by modules when tests finish
"""
import asyncio
import logging
import httpx
from core.db_helper import query_all

logger = logging.getLogger(__name__)
MAX_DELIVERY_ATTEMPTS = 3


async def send_completion_notification(
    title: str,
    status: str,
    summary: str,
    details: dict = None,
):
    """
    Send test-completion notifications to all enabled webhooks.

    Args:
        title: Notification title, such as "AI orchestration test report"
        status: Status (completed / failed / stopped)
        summary: Summary text
        details: Additional details dictionary (total_steps, passed, failed, duration, etc.)
    """
    result = {
        "configured": 0,
        "attempted": 0,
        "delivered": 0,
        "failed": 0,
    }
    try:
        rows = query_all("SELECT * FROM notification_webhooks WHERE enabled=1")
    except Exception:
        return result  # Return silently if the table does not exist

    if not rows:
        return result

    result["configured"] = len(rows)

    async with httpx.AsyncClient(timeout=10) as client:
        for row in rows:
            result["attempted"] += 1
            message = _format_message(row["type"], title, status, summary, details)
            for attempt in range(1, MAX_DELIVERY_ATTEMPTS + 1):
                try:
                    resp = await client.post(row["url"], json=message)
                    if resp.status_code < 300:
                        logger.info(f"[Notify] Sent to {row['name']}")
                        result["delivered"] += 1
                        break
                    retryable = resp.status_code >= 500 and attempt < MAX_DELIVERY_ATTEMPTS
                    if retryable:
                        logger.warning(
                            f"[Notify] {row['name']} returned {resp.status_code}, retry {attempt}/{MAX_DELIVERY_ATTEMPTS - 1}"
                        )
                        await asyncio.sleep(0.5 * attempt)
                        continue
                    logger.warning(f"[Notify] {row['name']} returned {resp.status_code}")
                    result["failed"] += 1
                    break
                except Exception as e:
                    retryable = attempt < MAX_DELIVERY_ATTEMPTS
                    if retryable:
                        logger.warning(
                            f"[Notify] Failed to send to {row['name']}: {e}; retry {attempt}/{MAX_DELIVERY_ATTEMPTS - 1}"
                        )
                        await asyncio.sleep(0.5 * attempt)
                        continue
                    logger.warning(f"[Notify] Failed to send to {row['name']}: {e}")
                    result["failed"] += 1
                    break
    return result


def _format_message(webhook_type: str, title: str, status: str, summary: str, details: dict = None) -> dict:
    status_emoji = {"completed": "✅", "failed": "❌", "stopped": "⏹️", "warning": "⚠️"}.get(status, "📋")
    text = f"{status_emoji} **{title}**\n\n{summary}"

    if details:
        annotations = details.get("annotations") or []
        if annotations:
            text += "\n\n" + "\n".join(str(item) for item in annotations if str(item).strip())
        if "total_steps" in details:
            text += f"\n\n📊 Steps: {details['total_steps']} | Passed: {details.get('passed', 0)} | Failed: {details.get('failed', 0)}"
        if "duration" in details:
            text += f"\n⏱️ Duration: {details['duration']}"

    if webhook_type == "dingtalk":
        return {"msgtype": "markdown", "markdown": {"title": title, "text": text}}
    elif webhook_type == "wecom":
        return {"msgtype": "markdown", "markdown": {"content": text}}
    elif webhook_type == "notification_platform":
        return {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": f"{status_emoji} {title}"}},
                "elements": [{"tag": "markdown", "content": text}],
            },
        }
    else:
        return {"title": title, "status": status, "message": text, "details": details or {}}
