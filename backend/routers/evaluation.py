# -*- coding: utf-8 -*-
"""
Evaluation Router — Agent 评估体系 API

端点：
- POST /api/evaluation/run       运行基准评估
- GET  /api/evaluation/results    获取评估结果
- GET  /api/evaluation/compare    模型对比报告
- GET  /api/evaluation/metrics    获取指标定义
- GET  /api/evaluation/scenarios  获取可用场景
- POST /api/evaluation/scenarios  添加自定义场景
- GET  /api/evaluation/trend      趋势报告
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from core.api_response import ok, safe_handler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


# ── 请求模型 ──────────────────────────────────────────────────────────────────

class RunBenchmarkRequest(BaseModel):
    scenario_ids: List[str] = []          # 空 = 运行所有
    category: str = ""                     # 按分类过滤
    use_judge: bool = False                # 是否启用 LLM-as-Judge
    model_override: str = ""               # 指定模型

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


# ── 路由 ──────────────────────────────────────────────────────────────────────

@router.get("/metrics")
async def list_metrics():
    """获取所有可用的评估指标"""
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
    """获取可用的基准测试场景"""
    from evaluation.benchmark_suite import BenchmarkSuite
    suite = BenchmarkSuite()
    scenarios = suite.list_scenarios(category=category)
    return ok({"count": len(scenarios), "scenarios": scenarios})


@router.post("/scenarios")
async def add_scenario(req: AddScenarioRequest):
    """添加自定义基准场景"""
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
    运行基准评估。

    注意：这是一个轻量级评估，不会真正启动浏览器执行。
    完整的基准测试需要通过 Commander 触发。
    此端点主要用于：
    - 对已有的 trace 数据运行评估指标
    - 获取历史数据对比
    """
    from evaluation.benchmark_suite import BenchmarkSuite
    from evaluation.reporter import EvaluationReporter

    suite = BenchmarkSuite()
    reporter = EvaluationReporter()

    # 获取要评估的场景
    if req.scenario_ids:
        scenarios = [s for s in suite.list_scenarios() if s["id"] in req.scenario_ids]
    elif req.category:
        scenarios = suite.list_scenarios(category=req.category)
    else:
        scenarios = suite.list_scenarios()

    if not scenarios:
        raise HTTPException(status_code=404, detail="未找到匹配的基准场景")

    return ok({
        "message": f"找到 {len(scenarios)} 个基准场景。使用 Commander 执行后，评估指标将自动计算。",
        "scenarios": scenarios,
        "hint": "POST /api/commander/execute 并传入基准场景的 goal 来执行完整评估",
    })


@router.get("/results")
async def get_results(scenario_id: str = "", limit: int = 50):
    """获取评估历史结果"""
    from evaluation.benchmark_suite import BenchmarkSuite
    suite = BenchmarkSuite()
    results = suite.get_results(scenario_id=scenario_id, limit=limit)
    return ok({"count": len(results), "results": results})


@router.get("/compare")
async def compare_models(scenario_id: str = ""):
    """模型对比报告"""
    from evaluation.benchmark_suite import BenchmarkSuite
    from evaluation.reporter import EvaluationReporter

    suite = BenchmarkSuite()
    reporter = EvaluationReporter()

    comparison = suite.compare_models(scenario_id=scenario_id)

    # 获取详细结果生成对比报告
    results = suite.get_results(scenario_id=scenario_id, limit=200)
    report = reporter.generate_comparison(results)

    return ok({"comparison": comparison, "report": report})


@router.get("/trend")
async def get_trend(scenario_id: str = "", limit: int = 100):
    """趋势分析报告"""
    from evaluation.benchmark_suite import BenchmarkSuite
    from evaluation.reporter import EvaluationReporter


    suite = BenchmarkSuite()
    reporter = EvaluationReporter()

    results = suite.get_results(scenario_id=scenario_id, limit=limit)
    trend = reporter.generate_trend(results)

    return ok({"trend": trend})
