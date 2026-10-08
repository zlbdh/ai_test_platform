# -*- coding: utf-8 -*-
"""
Quality Gate Router — Quality gate API

Endpoints:
- POST /api/quality-gate/check     Run quality gate checks
- GET  /api/quality-gate/rules     Get the rule list
- POST /api/quality-gate/rules     Add or update rules
- GET  /api/quality-gate/history   Quality gate history
- POST /api/quality-gate/webhook   GitHub webhook entry point
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
    """Run quality gate checks"""
    from cicd.quality_gate import get_quality_gate
    gate = get_quality_gate()
    verdict = gate.check(req.metric_scores, req.run_id)
    return ok({"verdict": verdict.to_dict()})


@router.get("/rules")
async def list_rules():
    """Get all quality gate rules"""
    from cicd.quality_gate import get_quality_gate
    gate = get_quality_gate()
    return ok({"rules": gate.list_rules()})


@router.post("/rules")
async def add_rule(req: AddRuleRequest):
    """Add or update a quality gate rule"""
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
    """Import project-level quality gate rules."""
    from cicd.quality_gate import get_quality_gate, GateRule

    rules = get_quality_gate_rules(playbook_id)
    if not rules:
        raise HTTPException(status_code=404, detail="Quality gate rule package does not exist")

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
    """Get quality gate check history"""
    from cicd.quality_gate import get_quality_gate
    gate = get_quality_gate()
    history = gate.get_history(limit=limit, run_id=run_id, status=status)
    return ok({"count": len(history), "history": history})


@router.post("/webhook")
async def github_webhook(request: Request):
    """GitHub webhook entry point — Receive PR events"""
    try:
        payload = await request.json()
        from cicd import GitHubIntegration

        gh = GitHubIntegration()
        result = gh.process_webhook(payload)
        return {"status": "success", **result}
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
