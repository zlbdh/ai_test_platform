# -*- coding: utf-8 -*-
"""
测试服务路由: 性能测试、安全扫描
"""
from fastapi import APIRouter
from typing import List, Optional, Dict, Any

router = APIRouter(tags=["testing"])

from core.models import PerformanceTestRequest, SecurityScanRequest

# === Performance Routes ===

@router.post("/api/performance/run")
async def api_performance_run(request: PerformanceTestRequest):
    """启动性能测试"""
    try:
        from services.performance_runner import get_performance_runner, LoadTestConfig
        runner = get_performance_runner()
        config = LoadTestConfig(
            target_url=request.target_url,
            users=request.users,
            spawn_rate=request.spawn_rate,
            duration=request.duration,
            endpoints=request.endpoints or [],
            headers=request.headers or {},
            session_id=request.session_id or "default_session",
            execution_group_id=request.execution_group_id,
            group_title=request.group_title,
        )
        result = await runner.run_test(config)
        return {
            "status": "success",
            "test_id": result.test_id,
            "stats": result.stats,
            "duration": result.duration
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "detail": f"性能测试执行失败: {str(e)}"
        }


@router.get("/api/performance/status")
async def api_performance_status():
    """获取性能测试状态"""
    from services.performance_runner import get_performance_runner
    runner = get_performance_runner()
    return {"status": runner.status.value}


@router.get("/api/performance/history")
async def api_performance_history(limit: int = 10):
    """获取性能测试历史"""
    from services.performance_runner import get_performance_runner
    runner = get_performance_runner()
    return {"status": "success", "history": runner.get_history(limit)}


@router.delete("/api/performance/history/{test_id}")
async def api_performance_delete(test_id: str):
    """删除单条性能测试历史"""
    from services.performance_runner import get_performance_runner
    runner = get_performance_runner()
    ok = runner.delete_history(test_id)
    if ok:
        return {"status": "success", "message": f"已删除 {test_id}"}
    return {"status": "error", "message": "未找到该记录"}


@router.delete("/api/performance/history")
async def api_performance_clear():
    """清空全部性能测试历史"""
    from services.performance_runner import get_performance_runner
    runner = get_performance_runner()
    count = runner.clear_history()
    return {"status": "success", "message": f"已清空 {count} 条记录"}


@router.post("/api/performance/stop")
async def api_performance_stop():
    """停止性能测试"""
    from services.performance_runner import get_performance_runner
    runner = get_performance_runner()
    runner.stop_test()
    return {"status": "success", "message": "Test stopped"}


# === Security Routes ===

@router.post("/api/security/scan")
async def api_security_scan(request: SecurityScanRequest):
    """启动安全扫描"""
    from services.security_scanner import get_security_scanner, ScanConfig, ScanType
    scanner = get_security_scanner()
    config = ScanConfig(
        target_url=request.target_url,
        scan_type=ScanType(request.scan_type),
        max_depth=request.max_depth,
        session_id=request.session_id or "default_session",
        execution_group_id=request.execution_group_id,
        group_title=request.group_title,
    )
    result = await scanner.scan(config)
    return {
        "status": "success",
        "scan_id": result.scan_id,
        "alerts": len(result.alerts),
        "high": result.high_count,
        "medium": result.medium_count,
        "low": result.low_count,
    }


@router.get("/api/security/status")
async def api_security_status():
    """获取安全扫描状态"""
    from services.security_scanner import get_security_scanner
    scanner = get_security_scanner()
    return {"status": scanner.status.value}


@router.get("/api/security/history")
async def api_security_history(limit: int = 10):
    """获取安全扫描历史"""
    from services.security_scanner import get_security_scanner
    scanner = get_security_scanner()
    return {"status": "success", "history": scanner.get_history(limit)}


@router.delete("/api/security/history/{scan_id}")
async def api_security_delete(scan_id: str):
    """删除单条安全扫描历史"""
    from services.security_scanner import get_security_scanner
    scanner = get_security_scanner()
    ok = scanner.delete_history(scan_id)
    if ok:
        return {"status": "success", "message": f"已删除 {scan_id}"}
    return {"status": "error", "message": "未找到该记录"}


@router.delete("/api/security/history")
async def api_security_clear():
    """清空全部安全扫描历史"""
    from services.security_scanner import get_security_scanner
    scanner = get_security_scanner()
    count = scanner.clear_history()
    return {"status": "success", "message": f"已清空 {count} 条记录"}


@router.get("/api/security/report/{scan_id}")
async def api_security_report(scan_id: str):
    """生成安全报告"""
    from services.security_scanner import get_security_scanner
    scanner = get_security_scanner()
    return scanner.generate_report(scan_id)


@router.post("/api/security/stop")
async def api_security_stop():
    """停止安全扫描"""
    from services.security_scanner import get_security_scanner
    scanner = get_security_scanner()
    scanner.stop_scan()
    return {"status": "success", "message": "Scan stopped"}
