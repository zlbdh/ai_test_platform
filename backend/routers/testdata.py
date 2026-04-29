# -*- coding: utf-8 -*-
"""
TestData Router — 测试数据管理 API
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging

from core.test_data_generator import TestDataGenerator
from core.api_response import ok, safe_handler

logger = logging.getLogger(__name__)
router = APIRouter(tags=["testdata"])


@router.get("/api/testdata/templates")
async def list_templates():
    """列出所有可用的测试数据模板"""
    return {"templates": TestDataGenerator.list_templates()}


class GenerateRequest(BaseModel):
    template: str
    count: int = Field(default=5, ge=0, le=1000)
    include_edge: bool = True


@router.post("/api/testdata/generate")
async def generate_data(req: GenerateRequest):
    """按模板生成测试数据"""
    result = TestDataGenerator.generate(req.template, req.count, req.include_edge)
    if "error" in result:
        return {"status": "error", "message": result["error"]}
    return {"status": "success", **result}


class CustomFieldDef(BaseModel):
    name: str
    type: str = "string"
    min: int = 1
    max: int = 100


class CustomGenerateRequest(BaseModel):
    fields: List[CustomFieldDef]
    count: int = Field(default=5, ge=0, le=1000)


@router.post("/api/testdata/generate-custom")
async def generate_custom_data(req: CustomGenerateRequest):
    """自定义字段生成测试数据"""
    fields = [f.model_dump() for f in req.fields]
    result = TestDataGenerator.generate_custom(fields, req.count)
    return {"status": "success", **result}
