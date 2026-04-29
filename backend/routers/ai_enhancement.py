# -*- coding: utf-8 -*-
"""
AI 增强路由 - 智能策略、自愈、知识库
"""
from fastapi import APIRouter
from core.models import StrategyRequest, KnowledgeRecordRequest
from core.strategy_selector import get_strategy_selector, TestType
from core.self_healing import get_healing_engine
from core.knowledge_base import get_knowledge_base

router = APIRouter(prefix="/api/ai", tags=["AI Enhancement"])


@router.post("/strategy")
async def ai_select_strategy(req: StrategyRequest):
    """AI 智能选择测试策略"""
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
    """获取自愈引擎统计"""
    engine = get_healing_engine()
    return {"status": "success", "stats": engine.get_statistics()}


@router.get("/knowledge/stats")
async def get_knowledge_stats():
    """获取知识库统计"""
    kb = get_knowledge_base()
    return {"status": "success", "stats": kb.get_statistics()}


@router.post("/knowledge/record")
async def record_test_knowledge(req: KnowledgeRecordRequest):
    """记录测试结果到知识库"""
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
    """根据历史推荐测试类型"""
    kb = get_knowledge_base()
    recommendations = kb.recommend_test_types(req.requirement)
    return {"status": "success", "recommendations": recommendations}


@router.get("/knowledge/report")
async def export_knowledge_report():
    """导出知识库报告"""
    kb = get_knowledge_base()
    return {"status": "success", "report": kb.export_report()}
