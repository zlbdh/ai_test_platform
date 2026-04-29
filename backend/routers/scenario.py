# -*- coding: utf-8 -*-
"""
E2E Scenario Chain Router — 场景链管理 API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import logging

from core.project_playbooks import get_playbook_catalog_entry, get_requirement_playbook, get_scenario_playbook
from core.scenario_chain import get_scenario_engine

logger = logging.getLogger(__name__)
router = APIRouter(tags=["scenario"])


@router.get("/api/scenarios")
async def list_scenarios():
    """列出所有场景"""
    engine = get_scenario_engine()
    return {"scenarios": engine.list_scenarios()}


@router.get("/api/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    """获取场景详情"""
    engine = get_scenario_engine()
    sc = engine.get_scenario(scenario_id)
    if not sc:
        raise HTTPException(status_code=404, detail="场景不存在")
    return sc


class CreateScenarioRequest(BaseModel):
    name: str
    description: str = ""
    steps: List[Dict] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


@router.post("/api/scenarios")
async def create_scenario(req: CreateScenarioRequest):
    """创建场景"""
    engine = get_scenario_engine()
    sc = engine.create_scenario(req.name, req.description, req.steps, req.tags)
    return {"status": "success", **sc}


@router.post("/api/scenarios/import-playbook/{playbook_id}")
async def import_scenario_playbook(playbook_id: str):
    """导入项目级场景包。"""
    engine = get_scenario_engine()
    playbook = get_scenario_playbook(playbook_id)
    if not playbook:
        raise HTTPException(status_code=404, detail="场景包不存在")
    playbook_meta = get_playbook_catalog_entry(playbook_id) or {}
    requirement_playbook = get_requirement_playbook(playbook_id) or {}

    imported = []
    for scenario in playbook:
        sc = engine.upsert_scenario_by_name(
            name=scenario["name"],
            description=scenario.get("description", ""),
            steps=scenario.get("steps", []),
            tags=scenario.get("tags", []),
        )
        imported.append({
            "id": sc["id"],
            "name": sc["name"],
            "stepCount": len(sc.get("steps", [])),
            "tags": sc.get("tags", []),
        })

    return {
        "status": "success",
        "playbook_id": playbook_id,
        "playbook_name": playbook_meta.get("name", ""),
        "project_name": playbook_meta.get("project_name", ""),
        "playbook_title": requirement_playbook.get("title", playbook_meta.get("name", "")),
        "imported_count": len(imported),
        "scenarios": imported,
    }


class UpdateScenarioRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    steps: Optional[List[Dict]] = None
    tags: Optional[List[str]] = None


@router.put("/api/scenarios/{scenario_id}")
async def update_scenario(scenario_id: str, req: UpdateScenarioRequest):
    """更新场景"""
    engine = get_scenario_engine()
    data = req.model_dump(exclude_none=True)
    sc = engine.update_scenario(scenario_id, data)
    if not sc:
        raise HTTPException(status_code=404, detail="场景不存在")
    return {"status": "success", **sc}


@router.delete("/api/scenarios/{scenario_id}")
async def delete_scenario(scenario_id: str):
    """删除场景"""
    engine = get_scenario_engine()
    if not engine.delete_scenario(scenario_id):
        raise HTTPException(status_code=404, detail="场景不存在")
    return {"status": "success"}


@router.post("/api/scenarios/{scenario_id}/execute")
async def execute_scenario(scenario_id: str):
    """执行场景链"""
    engine = get_scenario_engine()
    result = await engine.execute_scenario(scenario_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return {"status": "success", **result}


@router.get("/api/ci/templates")
async def list_ci_templates():
    """列出可用的 CI 配置模板"""
    return {
        "templates": [
            {"id": "github-actions", "label": "GitHub Actions", "filename": "github-actions.yml", "icon": "🐙"},
            {"id": "jenkinsfile", "label": "Jenkins Pipeline", "filename": "Jenkinsfile", "icon": "🔧"},
            {"id": "gitlab-ci", "label": "GitLab CI", "filename": ".gitlab-ci.yml", "icon": "🦊"},
        ]
    }


@router.get("/api/ci/templates/{template_id}")
async def get_ci_template(template_id: str):
    """获取 CI 配置模板内容"""
    import os
    template_map = {
        "github-actions": "github-actions.yml",
        "jenkinsfile": "Jenkinsfile",
        "gitlab-ci": ".gitlab-ci.yml",
    }
    filename = template_map.get(template_id)
    if not filename:
        raise HTTPException(status_code=404, detail="模板不存在")

    from core.config import Config
    path = os.path.join(Config.PROJECT_ROOT, "templates", "ci", filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="模板文件缺失")

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    return {"id": template_id, "filename": filename, "content": content}
