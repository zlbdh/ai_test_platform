"""
Report Router — 从 main.py 迁移
包含测试报告生成 + 历史查询 + 清除
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import logging
from typing import Optional

from core.allure_reporter import get_reporter
from core.models import ReportGenerateRequest
from services.platform_maintenance_service import get_platform_maintenance_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["report"])


@router.post("/api/report/generate")
async def api_generate_report(payload: Optional[ReportGenerateRequest] = None):
    """生成测试报告，支持单条记录或整批测试批次输出专属报告"""
    try:
        get_platform_maintenance_service().run(reason="report_generate")
        reporter = get_reporter()
        selected_id = None
        if payload:
            selected_id = payload.execution_group_id or payload.task_id
        result = reporter.generate_report(task_id=selected_id)
        return result
    except Exception as e:
        logger.error(f"Report generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/report/history")
async def api_report_history(limit: int = 10):
    """获取报告历史"""
    get_platform_maintenance_service().run(reason="report_history")
    reporter = get_reporter()
    return {"status": "success", "history": reporter.get_history(limit)}


@router.get("/api/report/view/{report_id}")
async def api_view_report(report_id: str):
    """查看指定报告 HTML 快照"""
    reporter = get_reporter()
    report_path = reporter.get_report_path(report_id)
    if not report_path:
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(str(report_path), media_type="text/html")


@router.delete("/api/report/{report_id}")
async def api_delete_report(report_id: str):
    """删除指定报告"""
    reporter = get_reporter()
    deleted = reporter.delete_report(report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"status": "success", "message": "Report deleted"}


@router.post("/api/report/clear")
async def api_clear_results():
    """清除测试结果"""
    reporter = get_reporter()
    reporter.clear_results()
    return {"status": "success", "message": "Results cleared"}
