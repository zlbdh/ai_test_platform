# -*- coding: utf-8 -*-
"""
Scheduled task routes — supports scheduled tests with Cron expressions
Persist data to SQLite
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
import json
import logging
import uuid
from datetime import datetime, timedelta

from core.db_helper import get_connection, query_all, query_one, execute

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


# ── Initialize tables ──

def _init_table():
    with get_connection() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS scheduler_tasks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            cron TEXT DEFAULT '0 8 * * *',
            task_type TEXT DEFAULT 'exploratory',
            config_json TEXT DEFAULT '{}',
            enabled INTEGER DEFAULT 1,
            notify_on_complete INTEGER DEFAULT 1,
            webhook_ids_json TEXT,
            last_run TEXT,
            next_run TEXT,
            status TEXT DEFAULT 'scheduled',
            created_at TEXT DEFAULT (datetime('now'))
        )''')

_init_table()


# ── Data models ──

class ScheduledTask(BaseModel):
    name: str
    cron: str = "0 8 * * *"
    task_type: str = "exploratory"
    config: dict = Field(default_factory=dict)
    enabled: bool = True
    notify_on_complete: bool = True
    webhook_ids: Optional[List[str]] = None


def _row_to_dict(row: dict) -> dict:
    """Convert a database row to the frontend format"""
    result = dict(row)
    result["enabled"] = bool(result.pop("enabled", 1))
    result["notify_on_complete"] = bool(result.pop("notify_on_complete", 1))
    result["config"] = json.loads(result.pop("config_json", "{}") or "{}")
    result["webhook_ids"] = json.loads(result.pop("webhook_ids_json", "null") or "null")
    return result


# ── CRUD ──

@router.get("/tasks")
async def list_tasks():
    """List all scheduled tasks"""
    rows = query_all("SELECT * FROM scheduler_tasks ORDER BY created_at DESC")
    return {"tasks": [_row_to_dict(r) for r in rows]}


@router.post("/tasks")
async def create_task(task: ScheduledTask):
    """Create a scheduled task"""
    tid = f"sched_{uuid.uuid4().hex[:8]}"
    next_run = _calc_next_run(task.cron)
    execute(
        """INSERT INTO scheduler_tasks 
           (id, name, cron, task_type, config_json, enabled, notify_on_complete, webhook_ids_json, next_run, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'scheduled')""",
        (tid, task.name, task.cron, task.task_type,
         json.dumps(task.config), int(task.enabled), int(task.notify_on_complete),
         json.dumps(task.webhook_ids) if task.webhook_ids else None,
         next_run),
    )
    logger.info(f"[Scheduler] Task created: {task.name} (cron: {task.cron})")
    row = query_one("SELECT * FROM scheduler_tasks WHERE id=?", (tid,))
    return {"id": tid, **_row_to_dict(row)}


@router.put("/tasks/{task_id}")
async def update_task(task_id: str, task: ScheduledTask):
    """Update a scheduled task"""
    existing = query_one("SELECT id FROM scheduler_tasks WHERE id=?", (task_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")
    next_run = _calc_next_run(task.cron)
    execute(
        """UPDATE scheduler_tasks SET name=?, cron=?, task_type=?, config_json=?, 
           enabled=?, notify_on_complete=?, webhook_ids_json=?, next_run=? WHERE id=?""",
        (task.name, task.cron, task.task_type, json.dumps(task.config),
         int(task.enabled), int(task.notify_on_complete),
         json.dumps(task.webhook_ids) if task.webhook_ids else None,
         next_run, task_id),
    )
    row = query_one("SELECT * FROM scheduler_tasks WHERE id=?", (task_id,))
    return {"id": task_id, **_row_to_dict(row)}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a scheduled task"""
    affected = execute("DELETE FROM scheduler_tasks WHERE id=?", (task_id,))
    if affected == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "deleted"}


@router.post("/tasks/{task_id}/toggle")
async def toggle_task(task_id: str):
    """Enable/disable a scheduled task"""
    row = query_one("SELECT enabled FROM scheduler_tasks WHERE id=?", (task_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    new_enabled = 0 if row["enabled"] else 1
    execute("UPDATE scheduler_tasks SET enabled=? WHERE id=?", (new_enabled, task_id))
    return {"id": task_id, "enabled": bool(new_enabled)}


@router.post("/tasks/{task_id}/run-now")
async def run_task_now(task_id: str):
    """Run a scheduled task immediately"""
    row = query_one("SELECT * FROM scheduler_tasks WHERE id=?", (task_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    now = datetime.now().isoformat()
    execute("UPDATE scheduler_tasks SET last_run=?, status='running' WHERE id=?", (now, task_id))
    logger.info(f"[Scheduler] Manual trigger: {row['name']}")

    # Execute asynchronously in the background
    import asyncio
    task_data = _row_to_dict(row)
    asyncio.create_task(_execute_task(task_id, task_data))

    task = query_one("SELECT * FROM scheduler_tasks WHERE id=?", (task_id,))
    return {"status": "triggered", "task": _row_to_dict(task)}


async def _execute_task(task_id: str, task_data: dict):
    """Run a scheduled task in the background"""
    task_type = task_data.get("task_type", "exploratory")
    config = task_data.get("config", {})
    name = task_data.get("name", "unknown")

    try:
        logger.info(f"[Scheduler] Executing {name} (type={task_type})")

        if task_type == "exploratory":
            # Call the exploratory testing API
            import httpx
            url = config.get("url", "")
            if url:
                session_id = config.get("session_id") or f"scheduled_{task_id}"
                planner_mode = config.get("planner_mode", "smart")
                async with httpx.AsyncClient(timeout=300) as client:
                    resp = await client.post(
                        "http://localhost:8020/api/start",
                        json={
                            "requirement": f"Exploratory testing {url}",
                            "target_url": url,
                            "planner_mode": planner_mode,
                            "session_id": session_id,
                        },
                    )
                    logger.info(f"[Scheduler] Exploratory test started: {resp.status_code}")
            else:
                logger.warning(f"[Scheduler] No URL configured for task {name}")

        elif task_type == "commander":
            import httpx
            goal = config.get("goal", f"Comprehensive testing {config.get('url', '')}")
            async with httpx.AsyncClient(timeout=300) as client:
                resp = await client.post(
                    "http://localhost:8020/api/commander/run",
                    json={"goal": goal, "max_agents": config.get("max_agents", 3)},
                )
                logger.info(f"[Scheduler] Commander task started: {resp.status_code}")

        elif task_type == "api":
            import httpx
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "http://localhost:8020/api/testing/run",
                    json=config,
                )
                logger.info(f"[Scheduler] API test started: {resp.status_code}")

        execute("UPDATE scheduler_tasks SET status='completed', next_run=? WHERE id=?",
                (_calc_next_run(task_data.get("cron", "0 8 * * *")), task_id))

        # Send notifications
        if task_data.get("notify_on_complete", True):
            try:
                from core.notify_helper import send_completion_notification
                await send_completion_notification(
                    title=f"Scheduled task completed: {name}",
                    status="completed",
                    summary=f"Task type: {task_type}\nConfiguration: {json.dumps(config, ensure_ascii=False)[:200]}",
                )
            except Exception:
                pass

    except Exception as e:
        logger.error(f"[Scheduler] Task {name} failed: {e}")
        execute("UPDATE scheduler_tasks SET status='failed' WHERE id=?", (task_id,))


# ── Cron calculation (simplified) ──

def _calc_next_run(cron: str) -> str:
    """Simplified calculation of the next Cron execution time"""
    try:
        parts = cron.split()
        if len(parts) == 5:
            minute, hour = int(parts[0]), int(parts[1])
            now = datetime.now()
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run.isoformat()
    except Exception:
        pass
    return datetime.now().isoformat()


# ── Scheduler status ──

@router.get("/status")
async def scheduler_status():
    """Get scheduler runtime status"""
    rows = query_all("SELECT enabled FROM scheduler_tasks")
    return {
        "running": True,
        "total_tasks": len(rows),
        "enabled_tasks": sum(1 for r in rows if r["enabled"]),
    }
