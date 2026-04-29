# -*- coding: utf-8 -*-
"""
Quality Gate Router — 质量门禁 API

端点：
- POST /api/quality-gate/check     执行质量门禁检查
- GET  /api/quality-gate/rules     获取规则列表
- POST /api/quality-gate/rules     添加/更新规则
- GET  /api/quality-gate/history   门禁历史
- POST /api/quality-gate/webhook   GitHub Webhook 入口
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict
import logging
from core.api_response import ok, safe_handler
from core.project_playbooks import get_playbook_catalog_entry, get_quality_gate_rules, get_requirement_playbook

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/quality-gate", tags=["quality-gate"])


class CheckRequest(BaseModel):
    metric_scores: Dict[str, float]
    run_id: str = ""

class AddRuleRequest(BaseModel):
    name: str
    description: str = ""
    metric: str
    operator: str = ">="
    threshold: float = 0.7
    severity: str = "blocking"


@router.post("/check")
async def check_quality_gate(req: CheckRequest):
    """执行质量门禁检查"""
    from cicd.quality_gate import get_quality_gate
    gate = get_quality_gate()
    verdict = gate.check(req.metric_scores, req.run_id)
    return ok({"verdict": verdict.to_dict()})


@router.get("/rules")
async def list_rules():
    """获取所有门禁规则"""
    from cicd.quality_gate import get_quality_gate
    gate = get_quality_gate()
    return ok({"rules": gate.list_rules()})


@router.post("/rules")
async def add_rule(req: AddRuleRequest):
    """添加/更新质量门禁规则"""
    from cicd.quality_gate import get_quality_gate, GateRule
    gate = get_quality_gate()
    rule = GateRule(
        name=req.name,
        description=req.description,
        metric=req.metric,
        operator=req.operator,
        threshold=req.threshold,
        severity=req.severity,
    )
    gate.add_rule(rule)
    return ok({"rule": rule.to_dict()})


@router.post("/rules/import/{playbook_id}")
async def import_rules_from_playbook(playbook_id: str):
    """导入项目级质量门禁规则。"""
    from cicd.quality_gate import get_quality_gate, GateRule

    rules = get_quality_gate_rules(playbook_id)
    if not rules:
        raise HTTPException(status_code=404, detail="门禁规则包不存在")

    gate = get_quality_gate()
    playbook_meta = get_playbook_catalog_entry(playbook_id) or {}
    requirement_playbook = get_requirement_playbook(playbook_id) or {}
    imported = []
    for item in rules:
        rule = GateRule(**item)
        gate.add_rule(rule)
        imported.append(rule.to_dict())

    return ok({
        "playbook_id": playbook_id,
        "playbook_name": playbook_meta.get("name", ""),
        "project_name": playbook_meta.get("project_name", ""),
        "playbook_title": requirement_playbook.get("title", playbook_meta.get("name", "")),
        "imported_count": len(imported),
        "rules": imported,
    })


@router.get("/history")
async def gate_history(
    limit: int = 20,
    run_id: str = "",
    status: str = "",
):
    """获取门禁检查历史"""
    from cicd.quality_gate import get_quality_gate
    gate = get_quality_gate()
    history = gate.get_history(limit=limit, run_id=run_id, status=status)
    return ok({"count": len(history), "history": history})


@router.post("/webhook")
async def github_webhook(request: Request):
    """GitHub Webhook 入口 — 接收 PR 事件"""
    try:
        payload = await request.json()
        from cicd import GitHubIntegration

        gh = GitHubIntegration()
        result = gh.process_webhook(payload)
        return {"status": "success", **result}
    except Exception as e:
        logger.error(f"Webhook 处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
