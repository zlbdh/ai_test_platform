# -*- coding: utf-8 -*-
"""
Evaluation Router — Agent evaluation API

Endpoints:
- POST /api/evaluation/run       Run benchmark evaluation
- GET  /api/evaluation/results    Get evaluation results
- GET  /api/evaluation/compare    Model comparison report
- GET  /api/evaluation/metrics    Get metric definitions
- GET  /api/evaluation/scenarios  Get available scenarios
- POST /api/evaluation/scenarios  Add a custom scenario
- GET  /api/evaluation/trend      Trend report
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from core.api_response import ok, safe_handler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


# ── Request models ──────────────────────────────────────────────────────────────────

class RunBenchmarkRequest(BaseModel):
    scenario_ids: List[str] = []          # Empty = run all
    category: str = ""                     # Filter by category
    use_judge: bool = False                # Whether to enable LLM-as-Judge
    model_override: str = ""               # Model override

class AddScenarioRequest(BaseModel):
    name: str
    description: str = ""
    category: str = "general"
    goal: str
    target_url: str = ""
    expected_steps: int = 5
    timeout_seconds: int = 120
    difficulty: str = "medium"
    tags: List[str] = []


# ── Routes ──────────────────────────────────────────────────────────────────────

@router.get("/metrics")
async def list_metrics():
    """Get all available evaluation metrics"""
    from evaluation.metrics import ALL_METRICS
    return {
        "status": "success",
        "metrics": [
            {"name": m.name, "description": m.description}
            for m in ALL_METRICS
        ],
    }


@router.get("/scenarios")
async def list_scenarios(category: str = ""):
    """Get available benchmark scenarios"""
    from evaluation.benchmark_suite import BenchmarkSuite
    suite = BenchmarkSuite()
    scenarios = suite.list_scenarios(category=category)
    return ok({"count": len(scenarios), "scenarios": scenarios})


@router.post("/scenarios")
async def add_scenario(req: AddScenarioRequest):
    """Add a custom benchmark scenario"""
    from evaluation.benchmark_suite import BenchmarkSuite, BenchmarkScenario
    suite = BenchmarkSuite()
    scenario = BenchmarkScenario(
        name=req.name,
        description=req.description,
        category=req.category,
        goal=req.goal,
        target_url=req.target_url,
        expected_steps=req.expected_steps,
        timeout_seconds=req.timeout_seconds,
        difficulty=req.difficulty,
        tags=req.tags,
    )
    suite.add_custom_scenario(scenario)
    return ok({"scenario": scenario.to_dict()})


@router.post("/run")
async def run_benchmark(req: RunBenchmarkRequest):
    """
    Run benchmark evaluation.

    Note: this lightweight evaluation does not launch a browser.
    A full benchmark run must be triggered through Commander.
    This endpoint primarily supports:
    - Run evaluation metrics on existing trace data
    - Compare historical data
    """
    from evaluation.benchmark_suite import BenchmarkSuite
    from evaluation.reporter import EvaluationReporter

    suite = BenchmarkSuite()
    reporter = EvaluationReporter()

    # Get the scenarios to evaluate
    if req.scenario_ids:
        scenarios = [s for s in suite.list_scenarios() if s["id"] in req.scenario_ids]
    elif req.category:
        scenarios = suite.list_scenarios(category=req.category)
    else:
        scenarios = suite.list_scenarios()

    if not scenarios:
        raise HTTPException(status_code=404, detail="No matching benchmark scenarios found")

    return ok({
        "message": f"Found {len(scenarios)} benchmark scenarios. Evaluation metrics are calculated automatically after execution through Commander.",
        "scenarios": scenarios,
        "hint": "POST /api/commander/execute with the benchmark scenario's goal to run a full evaluation",
    })


@router.get("/results")
async def get_results(scenario_id: str = "", limit: int = 50):
    """Get historical evaluation results"""
    from evaluation.benchmark_suite import BenchmarkSuite
    suite = BenchmarkSuite()
    results = suite.get_results(scenario_id=scenario_id, limit=limit)
    return ok({"count": len(results), "results": results})


@router.get("/compare")
async def compare_models(scenario_id: str = ""):
    """Model comparison report"""
    from evaluation.benchmark_suite import BenchmarkSuite
    from evaluation.reporter import EvaluationReporter

    suite = BenchmarkSuite()
    reporter = EvaluationReporter()

    comparison = suite.compare_models(scenario_id=scenario_id)

    # Get detailed results to generate a comparison report
    results = suite.get_results(scenario_id=scenario_id, limit=200)
    report = reporter.generate_comparison(results)

    return ok({"comparison": comparison, "report": report})


@router.get("/trend")
async def get_trend(scenario_id: str = "", limit: int = 100):
    """Trend analysis report"""
    from evaluation.benchmark_suite import BenchmarkSuite
    from evaluation.reporter import EvaluationReporter


    suite = BenchmarkSuite()
    reporter = EvaluationReporter()

    results = suite.get_results(scenario_id=scenario_id, limit=limit)
    trend = reporter.generate_trend(results)

    return ok({"trend": trend})
