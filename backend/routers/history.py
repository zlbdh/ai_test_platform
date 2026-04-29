"""
History & Gallery Router — 从 main.py 迁移
包含执行历史 CRUD + 截图画廊
"""
from fastapi import APIRouter, HTTPException
import json
import os
import base64
import logging

from core.db_helper import query_one, query_all, execute_safe
from core.config import Config
from services.execution_center_service import get_execution_center_service
from services.platform_maintenance_service import get_platform_maintenance_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["history"])


@router.get("/api/history")
async def api_history(limit: int = 50, view: str = "flat"):
    """Get list of recent test runs from persistent storage"""
    get_platform_maintenance_service().run(reason="history_list")
    service = get_execution_center_service()
    if view == "groups":
        return service.list_grouped_runs(limit=limit)
    try:
        rows = query_all("""
            SELECT task_id, requirement, status, log_count, error_count,
                   COALESCE(duration_ms, 0) as duration_ms,
                   COALESCE(target_url, '') as target_url,
                   COALESCE(mode, 'smart') as mode,
                   COALESCE(requirement_display, '') as requirement_display,
                   COALESCE(requirement_raw_present, 0) as requirement_raw_present,
                   COALESCE(task_text_state, 'normal') as task_text_state,
                   created_at 
            FROM test_runs ORDER BY created_at DESC LIMIT ?
        """, (limit,))
        if rows:
            return rows
    except Exception:
        pass  # test_runs 表不存在，回退到旧表

    try:
        return query_all("SELECT id, timestamp, goal, status FROM test_records ORDER BY timestamp DESC LIMIT ?", (limit,))
    except Exception:
        return []


@router.get("/api/history/{task_id}")
async def api_history_detail(task_id: str):
    """获取单条执行记录详情（含完整日志）"""
    get_platform_maintenance_service().run(reason="history_detail")
    service = get_execution_center_service()
    try:
        result = query_one("""
            SELECT task_id, requirement, status, log_count, error_count,
                   COALESCE(duration_ms, 0) as duration_ms,
                   COALESCE(target_url, '') as target_url,
                   COALESCE(mode, 'smart') as mode,
                   COALESCE(requirement_display, '') as requirement_display,
                   COALESCE(requirement_raw_present, 0) as requirement_raw_present,
                   COALESCE(task_text_state, 'normal') as task_text_state,
                   logs_json, created_at
            FROM test_runs WHERE task_id=?
        """, (task_id,))
        if not result:
            raise HTTPException(status_code=404, detail="Record not found")
        try:
            result["logs"] = json.loads(result.pop("logs_json", "[]") or "[]")
        except (json.JSONDecodeError, TypeError):
            result["logs"] = []
        return result
    except HTTPException:
        raise
    except Exception:
        group_detail = service.get_group_detail(task_id)
        if group_detail:
            return {"entity_type": "group", **group_detail}
        raise HTTPException(status_code=404, detail="Record not found")


@router.delete("/api/history/{task_id}")
async def api_delete_history(task_id: str):
    """Delete a single test run record"""
    service = get_execution_center_service()
    deleted_group = service.delete_group(task_id)
    if deleted_group > 0:
        return {"status": "success", "deleted": deleted_group, "entity_type": "group"}
    service.mark_ignored([task_id])
    deleted = execute_safe("DELETE FROM test_runs WHERE task_id=?", (task_id,))
    deleted += execute_safe("DELETE FROM test_records WHERE id=?", (task_id,))
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"status": "success", "deleted": deleted, "entity_type": "record"}


@router.delete("/api/history")
async def api_clear_history():
    """Clear all test run records"""
    existing = query_all("SELECT task_id FROM test_runs")
    get_execution_center_service().mark_ignored(row["task_id"] for row in existing)
    total = execute_safe("DELETE FROM test_runs")
    total += execute_safe("DELETE FROM test_records")
    return {"status": "success", "deleted": total}


@router.get("/api/gallery/{task_id}")
async def api_gallery(task_id: str):
    """获取任务的步骤截图时间线（用于视觉回廊）"""
    from core.db_helper import get_connection

    logs_json_str = None

    with get_connection() as conn:
        # 优先从 test_runs 表按 task_id 查询（新表）
        try:
            row = conn.execute("SELECT logs_json FROM test_runs WHERE task_id=?", (task_id,)).fetchone()
            if row:
                logs_json_str = row['logs_json']
        except Exception:
            pass

        # Fallback: 旧表 test_records 按 id 查询
        if not logs_json_str:
            try:
                row = conn.execute("SELECT logs_json FROM test_records WHERE id=?", (task_id,)).fetchone()
                if row:
                    logs_json_str = row['logs_json']
            except Exception:
                pass

    if not logs_json_str:
        return []

    try:
        logs = json.loads(logs_json_str)
    except (json.JSONDecodeError, TypeError):
        return []

    # 提取所有带截图的日志条目，或 visual_result / assertion 类型
    gallery = []
    step_index = 0
    for log in logs:
        log_type = log.get('type', '')
        screenshot = log.get('screenshot')
        snapshots = log.get('snapshots', {})

        # 跳过无截图且非关键类型的日志
        if not screenshot and not snapshots and log_type not in ('visual_result', 'assertion'):
            continue

        step_name = log.get('step', '') or log.get('content', '') or f'Step {step_index + 1}'

        # 映射 status
        raw_status = log.get('status', '')
        if raw_status in ('success', 'pass'):
            status = 'pass'
        elif raw_status in ('error', 'fail', 'failed'):
            status = 'fail'
        else:
            status = 'pass' if log_type != 'error' else 'fail'

        item = {
            'index': step_index,
            'step': step_name,
            'content': log.get('content', ''),
            'type': log_type,
            'status': status,
            'duration': log.get('duration', 0),
            'screenshot': f"data:image/jpeg;base64,{screenshot}" if screenshot else None,
            'snapshots': snapshots if snapshots else None,
        }
        gallery.append(item)
        step_index += 1

    return gallery

