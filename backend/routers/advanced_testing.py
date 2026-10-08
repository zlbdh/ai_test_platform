# -*- coding: utf-8 -*-
"""
Advanced testing routes - gRPC, security scanning, contract testing, reports, scheduling, load testing, and visual regression
"""
from fastapi import APIRouter, HTTPException
from core.models import (
    GrpcTestRequest, EnhancedSecurityScanRequest,
    ContractCreateRequest, ReportRequest, ScheduleRequest,
    LoadTestRequest,
)
from services.grpc_testing import create_grpc_service, GrpcRequest
from services.enhanced_security import get_enhanced_scanner
from services.contract_testing import get_contract_service
from core.report_generator import create_report_generator, TestSuite, TestResult as ReportTestResult, ReportFormat
from core.test_scheduler import get_scheduler, TaskPriority
from services.distributed_load_testing import get_load_tester
from services.distributed_load_testing import LoadTestConfig as DistLoadTestConfig
from services.visual_regression import get_visual_tester

router = APIRouter(tags=["Advanced Testing"])


# --- gRPC Testing ---

@router.post("/api/test/grpc")
async def test_grpc(req: GrpcTestRequest):
    """Run gRPC tests"""
    service = create_grpc_service(req.host, req.port, req.use_tls)
    request = GrpcRequest(
        service=req.service,
        method=req.method,
        data=req.data
    )
    response = await service.call(request)

    return {
        "status": "success" if response.success else "error",
        "data": response.data,
        "error": response.error,
        "response_time_ms": response.response_time_ms
    }


@router.get("/api/test/grpc/services")
async def list_grpc_services(host: str, port: int = 50051):
    """List gRPC services"""
    service = create_grpc_service(host, port)
    services = await service.list_services()
    return {"status": "success", "services": services}


# --- Enhanced Security ---

@router.post("/api/security/scan-enhanced")
async def enhanced_security_scan(req: EnhancedSecurityScanRequest):
    """Run enhanced security scanning"""
    scanner = get_enhanced_scanner()
    result = await scanner.scan(req.target_url, req.scan_types)
    report = scanner.generate_report(result)
    return {"status": "success", "report": report}


# --- Contract Testing ---

@router.post("/api/contract/create")
async def create_contract(req: ContractCreateRequest):
    """Create an API contract"""
    service = get_contract_service()
    contract = service.create_contract(
        req.consumer, req.provider, req.interactions, req.version
    )
    return {
        "status": "success",
        "contract_id": contract.contract_id,
        "consumer": contract.consumer,
        "provider": contract.provider
    }


@router.post("/api/contract/{contract_id}/verify")
async def verify_contract(contract_id: str, provider_url: str):
    """Validate a contract"""
    service = get_contract_service()
    result = await service.verify_contract(contract_id, provider_url)
    return {
        "status": "success" if result.passed else "failed",
        "passed": result.passed,
        "total": result.total_interactions,
        "passed_count": result.passed_interactions,
        "failures": result.failures
    }


@router.get("/api/contract/stats")
async def get_contract_stats():
    """Get contract statistics"""
    return get_contract_service().get_statistics()


# --- Enhanced Report ---

@router.post("/api/report/generate-enhanced")
async def api_generate_enhanced_report(req: ReportRequest):
    """Generate a test report"""
    generator = create_report_generator()

    test_results = [
        ReportTestResult(
            name=t.get("name", "Unknown"),
            status=t.get("status", "passed"),
            duration_ms=t.get("duration_ms", 0),
            error_message=t.get("error")
        )
        for t in req.tests
    ]

    suite = TestSuite(
        name=req.suite_name,
        tests=test_results,
        start_time="",
        end_time=""
    )

    format_map = {
        "html": ReportFormat.HTML,
        "json": ReportFormat.JSON,
        "markdown": ReportFormat.MARKDOWN,
        "junit": ReportFormat.JUNIT_XML
    }

    filepath = generator.generate(suite, format_map.get(req.format, ReportFormat.HTML))
    return {"status": "success", "report_path": filepath}


# --- Test Scheduler ---

@router.post("/api/scheduler/schedule")
async def schedule_test(req: ScheduleRequest):
    """Schedule a test task"""
    scheduler = get_scheduler()
    priority = TaskPriority(req.priority)
    task = scheduler.schedule(req.name, req.test_config, priority, req.scheduled_at)
    return {
        "status": "success",
        "task_id": task.task_id,
        "name": task.name,
        "priority": task.priority.value
    }


@router.get("/api/scheduler/queue")
async def get_scheduler_queue():
    """Get the scheduling queue"""
    scheduler = get_scheduler()
    return {
        "status": "success",
        "queue": scheduler.get_queue(),
        "running": scheduler.get_running(),
        "stats": scheduler.get_statistics()
    }


@router.delete("/api/scheduler/{task_id}")
async def cancel_scheduled_task(task_id: str):
    """Cancel a scheduled task"""
    scheduler = get_scheduler()
    cancelled = scheduler.cancel(task_id)
    return {"status": "success" if cancelled else "not_found"}


# --- Distributed Load Testing ---

@router.post("/api/loadtest/run")
async def run_load_test(req: LoadTestRequest):
    """Run a load test"""
    tester = get_load_tester()
    config = DistLoadTestConfig(
        target_url=req.target_url,
        users=req.users,
        spawn_rate=req.spawn_rate,
        duration_seconds=req.duration_seconds
    )
    result = await tester.start_test(config)
    return result


@router.get("/api/loadtest/status")
async def get_loadtest_status():
    """Get load test status"""
    return get_load_tester().get_status()


@router.post("/api/loadtest/stop")
async def stop_load_test():
    """Stop a load test"""
    get_load_tester().stop_test()
    return {"status": "stopped"}


# --- Visual Regression ---

@router.post("/api/visual/baseline")
async def save_visual_baseline(name: str, image: bytes = None):
    """Save a baseline image"""
    tester = get_visual_tester()
    if image:
        result = tester.save_baseline(name, image)
        return {"status": "success", "name": result.name}
    return {"status": "error", "message": "No image provided"}


@router.get("/api/visual/baselines")
async def list_visual_baselines():
    """List all baselines"""
    return {
        "status": "success",
        "baselines": get_visual_tester().list_baselines()
    }


@router.delete("/api/visual/baseline/{name}")
async def delete_visual_baseline(name: str):
    """Delete a baseline"""
    deleted = get_visual_tester().delete_baseline(name)
    return {"status": "success" if deleted else "not_found"}
