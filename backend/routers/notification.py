# -*- coding: utf-8 -*-
"""
Notification routes — send webhook notifications after tests finish
Supports DingTalk, WeCom, the notification platform, and custom webhooks
Persist data to SQLite
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import httpx
import json
import logging
import uuid
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from core.db_helper import get_connection, query_all, query_one, execute

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/notify", tags=["notification"])


# ── Initialize tables ──

def _get_columns(conn, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def _init_table():
    with get_connection() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS notification_webhooks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            type TEXT DEFAULT 'custom',
            enabled INTEGER DEFAULT 1,
            secret TEXT,
            last_test_at TEXT DEFAULT '',
            last_test_success INTEGER DEFAULT 0,
            last_test_status INTEGER DEFAULT 0,
            last_test_message TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        )''')
        columns = _get_columns(conn, "notification_webhooks")
        if "last_test_at" not in columns:
            conn.execute("ALTER TABLE notification_webhooks ADD COLUMN last_test_at TEXT DEFAULT ''")
        if "last_test_success" not in columns:
            conn.execute("ALTER TABLE notification_webhooks ADD COLUMN last_test_success INTEGER DEFAULT 0")
        if "last_test_status" not in columns:
            conn.execute("ALTER TABLE notification_webhooks ADD COLUMN last_test_status INTEGER DEFAULT 0")
        if "last_test_message" not in columns:
            conn.execute("ALTER TABLE notification_webhooks ADD COLUMN last_test_message TEXT DEFAULT ''")

_init_table()


# ── Data models ──

class WebhookConfig(BaseModel):
    name: str
    url: str
    type: str = "custom"
    enabled: bool = True
    secret: Optional[str] = None


class WebhookUpdateRequest(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    type: Optional[str] = None
    enabled: Optional[bool] = None
    secret: Optional[str] = None


class NotificationPayload(BaseModel):
    title: str = "AI test report"
    status: str = "completed"
    summary: str = ""
    details: Optional[dict] = None
    webhook_ids: Optional[List[str]] = None


class NotificationDrillPayload(BaseModel):
    title: str = "Platform alert drill"
    status: str = "warning"
    summary: str = "This production alert drill checks whether enabled webhooks are actually reachable."


# ── CRUD ──

def _build_overview(rows: List[dict]) -> dict:
    total = len(rows)
    enabled = [row for row in rows if bool(row.get("enabled"))]
    tested_enabled = [row for row in enabled if str(row.get("last_test_at") or "").strip()]
    healthy_enabled = [row for row in enabled if bool(row.get("last_test_success"))]
    production_ready = len(healthy_enabled) > 0

    if not enabled:
        summary = "No enabled production alert webhook is configured"
    elif not tested_enabled:
        summary = f"{len(enabled)} webhooks configured, but no alert channel has been verified"
    elif not healthy_enabled:
        summary = f"{len(enabled)} webhooks configured, but all recent tests failed"
    else:
        summary = f"{len(enabled)} webhooks configured; {len(healthy_enabled)} passed recent tests"

    return {
        "total": total,
        "enabled": len(enabled),
        "tested_enabled": len(tested_enabled),
        "healthy_enabled": len(healthy_enabled),
        "untested_enabled": max(len(enabled) - len(tested_enabled), 0),
        "production_ready": production_ready,
        "summary": summary,
    }


def _mask_secret_value(value: str, visible_start: int = 4, visible_end: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= visible_start + visible_end:
        return "*" * min(len(value), 8)
    return f"{value[:visible_start]}...{value[-visible_end:]}"


def _mask_webhook_url(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlsplit(url)
        path_segments = parsed.path.split("/")
        masked_segments = path_segments[:]
        for index in range(len(masked_segments) - 1, -1, -1):
            segment = masked_segments[index]
            if segment:
                masked_segments[index] = _mask_secret_value(segment)
                break
        masked_query = urlencode(
            [
                (key, _mask_secret_value(value, visible_start=2, visible_end=2) if value else value)
                for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            ]
        )
        return urlunsplit((
            parsed.scheme,
            parsed.netloc,
            "/".join(masked_segments),
            masked_query,
            parsed.fragment,
        ))
    except Exception:
        return _mask_secret_value(url, visible_start=8, visible_end=6)


def _serialize_webhook_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "url": _mask_webhook_url(str(row.get("url") or "")),
        "type": row.get("type", "custom"),
        "enabled": bool(row.get("enabled")),
        "last_test_at": row.get("last_test_at", ""),
        "last_test_success": bool(row.get("last_test_success")),
        "last_test_status": int(row.get("last_test_status") or 0),
        "last_test_message": row.get("last_test_message", ""),
        "created_at": row.get("created_at", ""),
    }


async def _deliver_webhook_test(row: dict, title: str, status: str, summary: str) -> dict:
    payload = _format_message(row["type"], title, status, summary)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(row["url"], json=payload)
            ok = resp.status_code < 300
            message = "Sent successfully" if ok else f"HTTP {resp.status_code}"
            execute(
                """
                UPDATE notification_webhooks
                SET last_test_at = datetime('now'),
                    last_test_success = ?,
                    last_test_status = ?,
                    last_test_message = ?
                WHERE id = ?
                """,
                (1 if ok else 0, int(resp.status_code), message, row["id"]),
            )
            return {
                "id": row["id"],
                "name": row["name"],
                "success": ok,
                "status_code": resp.status_code,
                "message": message,
            }
    except Exception as e:
        message = str(e)
        execute(
            """
            UPDATE notification_webhooks
            SET last_test_at = datetime('now'),
                last_test_success = 0,
                last_test_status = 0,
                last_test_message = ?
            WHERE id = ?
            """,
            (message[:300], row["id"]),
        )
        return {
            "id": row["id"],
            "name": row["name"],
            "success": False,
            "status_code": 0,
            "message": message,
        }


@router.get("/webhooks")
async def list_webhooks():
    """List all webhook configurations"""
    rows = query_all(
        """
        SELECT id, name, url, type, enabled, secret,
               last_test_at, last_test_success, last_test_status, last_test_message,
               created_at
        FROM notification_webhooks
        ORDER BY created_at DESC
        """
    )
    return {"webhooks": [_serialize_webhook_row(row) for row in rows]}


@router.get("/overview")
async def get_notification_overview():
    """Get notification configuration production readiness"""
    rows = query_all(
        """
        SELECT id, name, url, type, enabled,
               last_test_at, last_test_success, last_test_status, last_test_message
        FROM notification_webhooks
        ORDER BY created_at DESC
        """
    )
    normalized_rows = []
    for row in rows:
        normalized_rows.append({
            **row,
            "enabled": bool(row["enabled"]),
            "last_test_success": bool(row.get("last_test_success")),
        })
    return {
        "overview": _build_overview(normalized_rows),
        "webhooks": [_serialize_webhook_row(row) for row in normalized_rows],
    }


@router.post("/webhooks")
async def add_webhook(config: WebhookConfig):
    """Add a webhook"""
    wid = f"wh_{uuid.uuid4().hex[:8]}"
    execute(
        "INSERT INTO notification_webhooks (id, name, url, type, enabled, secret) VALUES (?, ?, ?, ?, ?, ?)",
        (wid, config.name, config.url, config.type, int(config.enabled), config.secret),
    )
    logger.info(f"[Notify] Webhook added: {config.name} ({config.type})")
    created = query_one(
        """
        SELECT id, name, url, type, enabled, secret,
               last_test_at, last_test_success, last_test_status, last_test_message,
               created_at
        FROM notification_webhooks
        WHERE id=?
        """,
        (wid,),
    )
    if not created:
        raise HTTPException(status_code=500, detail="Webhook created but failed to load")
    return _serialize_webhook_row(created)


@router.patch("/webhooks/{webhook_id}")
async def update_webhook(webhook_id: str, payload: WebhookUpdateRequest):
    """Update a webhook configuration to enable/disable it or correct its URL."""
    row = query_one("SELECT * FROM notification_webhooks WHERE id=?", (webhook_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")

    next_name = payload.name if payload.name is not None else row["name"]
    next_url = payload.url if payload.url is not None else row["url"]
    next_type = payload.type if payload.type is not None else row["type"]
    next_enabled = int(payload.enabled if payload.enabled is not None else bool(row["enabled"]))
    next_secret = payload.secret if payload.secret is not None else row.get("secret")

    should_reset_test_status = (
        (payload.url is not None and payload.url != row["url"])
        or (payload.type is not None and payload.type != row["type"])
        or (payload.secret is not None and payload.secret != row.get("secret"))
    )

    if should_reset_test_status:
        execute(
            """
            UPDATE notification_webhooks
            SET name=?, url=?, type=?, enabled=?, secret=?,
                last_test_at='',
                last_test_success=0,
                last_test_status=0,
                last_test_message=''
            WHERE id=?
            """,
            (next_name, next_url, next_type, next_enabled, next_secret, webhook_id),
        )
    else:
        execute(
            """
            UPDATE notification_webhooks
            SET name=?, url=?, type=?, enabled=?, secret=?
            WHERE id=?
            """,
            (next_name, next_url, next_type, next_enabled, next_secret, webhook_id),
        )

    updated = query_one(
        """
        SELECT id, name, url, type, enabled, secret,
               last_test_at, last_test_success, last_test_status, last_test_message, created_at
        FROM notification_webhooks
        WHERE id=?
        """,
        (webhook_id,),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return _serialize_webhook_row(updated)


@router.delete("/webhooks/{webhook_id}")
async def remove_webhook(webhook_id: str):
    """Delete a webhook"""
    affected = execute("DELETE FROM notification_webhooks WHERE id=?", (webhook_id,))
    if affected == 0:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"status": "deleted"}


@router.post("/webhooks/{webhook_id}/test")
async def test_webhook(webhook_id: str):
    """Test webhook connectivity"""
    row = query_one("SELECT * FROM notification_webhooks WHERE id=?", (webhook_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")
    result = await _deliver_webhook_test(
        row,
        "🔔 Test notification",
        "success",
        "This test message confirms that the webhook works.",
    )
    if result["success"]:
        return {
            "success": True,
            "status_code": result["status_code"],
            "body": result["message"],
            "message": result["message"],
        }
    return {
        "success": False,
        "status_code": result["status_code"],
        "error": result["message"],
        "message": result["message"],
    }


@router.post("/drill")
async def drill_notification_webhooks(payload: NotificationDrillPayload):
    """Run a production alert drill for all enabled webhooks"""
    rows = query_all("SELECT * FROM notification_webhooks WHERE enabled=1 ORDER BY created_at DESC")
    if not rows:
        return {
            "configured": 0,
            "attempted": 0,
            "delivered": 0,
            "failed": 0,
            "results": [],
            "summary": "No webhooks are enabled; cannot run an alert drill.",
        }

    results = []
    delivered = 0
    failed = 0
    for row in rows:
        result = await _deliver_webhook_test(row, payload.title, payload.status, payload.summary)
        results.append(result)
        if result["success"]:
            delivered += 1
        else:
            failed += 1

    return {
        "configured": len(rows),
        "attempted": len(rows),
        "delivered": delivered,
        "failed": failed,
        "results": results,
        "summary": (
            f"Alert drill completed for {len(rows)} enabled channels: {delivered} succeeded, {failed} failed."
            if rows else "No webhooks are enabled; cannot run an alert drill."
        ),
    }


# ── Send notifications ──

@router.post("/send")
async def send_notification(payload: NotificationPayload):
    """Send a notification to selected webhooks or all webhooks"""
    if payload.webhook_ids:
        placeholders = ",".join("?" for _ in payload.webhook_ids)
        rows = query_all(f"SELECT * FROM notification_webhooks WHERE id IN ({placeholders})", tuple(payload.webhook_ids))
    else:
        rows = query_all("SELECT * FROM notification_webhooks WHERE enabled=1")

    results = []
    for row in rows:
        if not row.get("enabled", True):
            results.append({"id": row["id"], "name": row["name"], "skipped": True})
            continue

        message = _format_message(row["type"], payload.title, payload.status, payload.summary, payload.details)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(row["url"], json=message)
                results.append({"id": row["id"], "name": row["name"], "success": resp.status_code < 300})
        except Exception as e:
            results.append({"id": row["id"], "name": row["name"], "success": False, "error": str(e)})
            logger.error(f"[Notify] Failed to send to {row['name']}: {e}")

    return {"sent": len(results), "results": results}


# ── Message formatting ──

def _format_message(webhook_type: str, title: str, status: str, summary: str, details: dict = None) -> dict:
    status_emoji = {"completed": "✅", "failed": "❌", "stopped": "⏹️"}.get(status, "📋")
    text = f"{status_emoji} **{title}**\n\n{summary}"

    if details:
        if "total_steps" in details:
            text += f"\n\n📊 Steps: {details['total_steps']} | Passed: {details.get('passed', 0)} | Failed: {details.get('failed', 0)}"
        if "duration" in details:
            text += f"\n⏱️ Duration: {details['duration']}"

    if webhook_type == "dingtalk":
        return {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": text},
        }
    elif webhook_type == "wecom":
        return {
            "msgtype": "markdown",
            "markdown": {"content": text},
        }
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
