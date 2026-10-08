# -*- coding: utf-8 -*-
"""
AI enhancement routes - intelligent strategies, healing, and knowledge base
"""
from fastapi import APIRouter
from core.models import StrategyRequest, KnowledgeRecordRequest
from core.strategy_selector import get_strategy_selector, TestType
from core.self_healing import get_healing_engine
from core.knowledge_base import get_knowledge_base

router = APIRouter(prefix="/api/ai", tags=["AI Enhancement"])


@router.post("/strategy")
async def ai_select_strategy(req: StrategyRequest):
    """Select a test strategy with AI"""
    selector = get_strategy_selector()
    strategy = selector.select_strategy(req.requirement, req.target_url)
    return {
        "status": "success",
        "strategy": {
            "test_types": [t.value for t in strategy.test_types],
            "priority": strategy.priority.value,
            "parallel": strategy.parallel,
            "timeout_seconds": strategy.timeout_seconds,
            "retry_count": strategy.retry_count,
            "ai_confidence": strategy.ai_confidence,
            "reasoning": strategy.reasoning,
            "recommended_agents": strategy.recommended_agents
        }
    }


@router.get("/healing/stats")
async def get_healing_stats():
    """Get healing engine statistics"""
    engine = get_healing_engine()
    return {"status": "success", "stats": engine.get_statistics()}


@router.get("/knowledge/stats")
async def get_knowledge_stats():
    """Get knowledge base statistics"""
    kb = get_knowledge_base()
    return {"status": "success", "stats": kb.get_statistics()}


@router.post("/knowledge/record")
async def record_test_knowledge(req: KnowledgeRecordRequest):
    """Record test results in the knowledge base"""
    kb = get_knowledge_base()
    case = kb.record_test(
        requirement=req.requirement,
        target_url=req.target_url,
        test_types=req.test_types,
        result=req.result,
        duration_ms=req.duration_ms,
        error_message=req.error_message
    )
    return {"status": "success", "case_id": case.case_id}


@router.post("/knowledge/recommend")
async def recommend_test_types(req: StrategyRequest):
    """Recommend test types based on history"""
    kb = get_knowledge_base()
    recommendations = kb.recommend_test_types(req.requirement)
    return {"status": "success", "recommendations": recommendations}


@router.get("/knowledge/report")
async def export_knowledge_report():
    """Export a knowledge base report"""
    kb = get_knowledge_base()
    return {"status": "success", "report": kb.export_report()}
