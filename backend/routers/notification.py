# -*- coding: utf-8 -*-
"""
通知服务路由 — 测试完成后发送 Webhook 通知
支持钉钉、企业微信、通知平台、自定义 Webhook
数据持久化到 SQLite
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


# ── 初始化表 ──

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


# ── 数据模型 ──

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
    title: str = "AI 测试报告"
    status: str = "completed"
    summary: str = ""
    details: Optional[dict] = None
    webhook_ids: Optional[List[str]] = None


class NotificationDrillPayload(BaseModel):
    title: str = "平台告警演练"
    status: str = "warning"
    summary: str = "这是一条平台生产告警演练消息，用于验证启用中的 Webhook 是否真正可达。"


# ── CRUD ──

def _build_overview(rows: List[dict]) -> dict:
    total = len(rows)
    enabled = [row for row in rows if bool(row.get("enabled"))]
    tested_enabled = [row for row in enabled if str(row.get("last_test_at") or "").strip()]
    healthy_enabled = [row for row in enabled if bool(row.get("last_test_success"))]
    production_ready = len(healthy_enabled) > 0

    if not enabled:
        summary = "尚未配置启用中的生产告警 Webhook"
    elif not tested_enabled:
        summary = f"已配置 {len(enabled)} 个 Webhook，但还没有任何已验证的告警通道"
    elif not healthy_enabled:
        summary = f"已配置 {len(enabled)} 个 Webhook，但最近测试都未通过"
    else:
        summary = f"已配置 {len(enabled)} 个 Webhook，其中 {len(healthy_enabled)} 个最近测试通过"

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
            message = "发送成功" if ok else f"HTTP {resp.status_code}"
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
    """列出所有 Webhook 配置"""
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
    """获取通知配置生产就绪概览"""
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
    """添加 Webhook"""
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
    """更新 Webhook 配置，可用于启用/停用或修正 URL。"""
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
    """删除 Webhook"""
    affected = execute("DELETE FROM notification_webhooks WHERE id=?", (webhook_id,))
    if affected == 0:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"status": "deleted"}


@router.post("/webhooks/{webhook_id}/test")
async def test_webhook(webhook_id: str):
    """测试 Webhook 连通性"""
    row = query_one("SELECT * FROM notification_webhooks WHERE id=?", (webhook_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")
    result = await _deliver_webhook_test(
        row,
        "🔔 测试通知",
        "success",
        "这是一条测试消息，确认 Webhook 可用。",
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
    """对所有启用中的 Webhook 执行一次生产告警演练"""
    rows = query_all("SELECT * FROM notification_webhooks WHERE enabled=1 ORDER BY created_at DESC")
    if not rows:
        return {
            "configured": 0,
            "attempted": 0,
            "delivered": 0,
            "failed": 0,
            "results": [],
            "summary": "当前没有启用中的 Webhook，无法执行告警演练。",
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
            f"已完成 {len(rows)} 个启用通道的告警演练，成功 {delivered} 个，失败 {failed} 个。"
            if rows else "当前没有启用中的 Webhook，无法执行告警演练。"
        ),
    }


# ── 发送通知 ──

@router.post("/send")
async def send_notification(payload: NotificationPayload):
    """发送通知到指定或全部 Webhook"""
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


# ── 消息格式化 ──

def _format_message(webhook_type: str, title: str, status: str, summary: str, details: dict = None) -> dict:
    status_emoji = {"completed": "✅", "failed": "❌", "stopped": "⏹️"}.get(status, "📋")
    text = f"{status_emoji} **{title}**\n\n{summary}"

    if details:
        if "total_steps" in details:
            text += f"\n\n📊 步骤: {details['total_steps']} | 通过: {details.get('passed', 0)} | 失败: {details.get('failed', 0)}"
        if "duration" in details:
            text += f"\n⏱️ 耗时: {details['duration']}"

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
