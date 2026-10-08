"""
Data Factory & Batch Runner Router — Migrated from main.py
Includes test data generation and batch test execution
"""
from fastapi import APIRouter, HTTPException
import logging

from core.models import DataGenerateRequest, BatchRunRequest
from core.data_factory import generate_test_data, generate_test_data_batch, get_data_factory
from services.batch_runner import get_batch_runner, BatchRunner, TestCase

logger = logging.getLogger(__name__)
router = APIRouter(tags=["data"])


@router.post("/api/data/generate")
async def api_data_generate(request: DataGenerateRequest):
    """Generate test data"""
    try:
        if request.count == 1:
            data = generate_test_data(request.template)
            return {"status": "success", "data": data}
        else:
            data = generate_test_data_batch(request.template, request.count)
            return {"status": "success", "data": data, "count": len(data)}
    except Exception as e:
        logger.error(f"Data generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/data/types")
async def api_data_types():
    """Get all available data types"""
    factory = get_data_factory()
    return {"status": "success", "types": factory.get_available_types()}


@router.post("/api/batch/run")
async def api_batch_run(request: BatchRunRequest):
    """Start a batch testing task"""
    try:
        runner = get_batch_runner(request.max_concurrency)

        if request.data_template:
            test_cases = BatchRunner.create_from_data_factory(
                template=request.data_template,
                instruction_template=request.instruction_template,
                count=request.count,
                base_url=request.base_url
            )
        else:
            test_cases = [TestCase(
                instruction=request.instruction_template,
                url=request.base_url
            )]

        async def simple_executor(tc: TestCase):
            logger.info(f"Executing: {tc.instruction[:50]}...")
            return {"executed": True, "instruction": tc.instruction}

        result = await runner.run_batch(test_cases, simple_executor)
        return {"status": "success", "result": result.to_dict()}

    except Exception as e:
        logger.error(f"Batch run error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
