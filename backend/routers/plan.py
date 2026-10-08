"""
Plan & AI Config Router — Migrated from main.py
Includes test plan generation and AI/LLM configuration management
"""
from fastapi import APIRouter
import logging

from core.models import PlanGenerateRequest, AIConfigUpdate
from services.planner_service import planner_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["plan"])


@router.post("/api/plan/generate")
async def generate_test_plan(req: PlanGenerateRequest):
    """Generate a test plan"""
    try:
        result = await planner_service.generate_plan(
            req.requirement,
            req.enable_rag,
            req.target_url or "",
            execution_mode=req.execution_mode or "default",
            interaction_policy=req.interaction_policy or "default",
        )

        steps = []
        for test_case in result.get('test_cases', []):
            priority = test_case.get('priority', 'P1')
            scenario_name = test_case.get('scenario', '')
            for step in test_case.get('steps', []):
                steps.append({
                    "action": step.get('action', ''),
                    "target": step.get('target', ''),
                    "value": step.get('value', ''),
                    "description": f"[{priority}] {scenario_name}: {step.get('action', '')}",
                    "priority": priority,
                    "scenario": scenario_name
                })

        if not steps:
            return {
                "status": "error",
                "message": "The LLM could not generate valid test steps. Check the API key configuration and network connection",
                "steps": [],
                "scenarios": [],
                "sources": [],
                "coverage_summary": {}
            }

        return {
            "status": "success",
            "steps": steps,
            "scenarios": result.get('test_cases', []),
            "sources": result.get('sources', []),
            "coverage_summary": result.get('coverage_summary', {})
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "steps": []
        }


@router.get("/api/config/ai")
async def get_ai_config():
    """Get current AI/LLM configuration with API keys redacted"""
    from core.config import Config
    return {"status": "success", "config": Config.get_llm_config()}


@router.post("/api/config/ai")
async def update_ai_config(req: AIConfigUpdate):
    """Update AI/LLM configuration dynamically"""
    from core.config import Config
    Config.update_llm_config(
        provider=req.provider,
        model=req.model,
        vision_model=req.vision_model,
        api_key=req.api_key,
        base_url=req.base_url,
        planner_model=req.planner_model,
        executor_model=req.executor_model,
        temperature=req.temperature,
        top_p=req.top_p,
        max_tokens=req.max_tokens,
    )
    current_config = Config.get_llm_config()
    logger.info(
        "AI config updated: provider=%s, model=%s, planner=%s, executor=%s",
        current_config["provider"],
        current_config["model"],
        current_config["planner_model"],
        current_config["executor_model"],
    )
    return {"status": "success", "config": current_config}
