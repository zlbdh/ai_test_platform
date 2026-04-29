# -*- coding: utf-8 -*-
"""
Visual Regression Router — 视觉回归测试 API
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import base64
import logging
import os

from services.visual_regression import get_visual_tester
from core.api_response import ok, safe_handler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/visual", tags=["visual-regression"])


@router.get("/baselines")
async def list_baselines():
    """列出所有视觉基线"""
    tester = get_visual_tester()
    baselines = tester.list_baselines()
    # 为每个基线添加缩略图 base64
    result = []
    for b in baselines:
        item = {
            "name": b.get("name", ""),
            "width": b.get("width", 0),
            "height": b.get("height", 0),
            "timestamp": b.get("timestamp", ""),
            "hash": b.get("hash", ""),
        }
        # 读取缩略图
        filepath = b.get("filepath", "")
        if filepath and os.path.exists(filepath):
            try:
                with open(filepath, "rb") as f:
                    img_bytes = f.read()
                item["thumbnail"] = base64.b64encode(img_bytes).decode()[:500] + "..."
                item["size_bytes"] = len(img_bytes)
            except Exception:
                pass
        result.append(item)

    return {"baselines": result, "count": len(result)}


class CompareRequest(BaseModel):
    name: str
    image_base64: str
    threshold: float = 0.01


@router.post("/compare")
async def compare_screenshot(req: CompareRequest):
    """将截图与基线比较"""
    tester = get_visual_tester()
    try:
        image_data = base64.b64decode(req.image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="无效的 base64 图片数据")

    result = tester.compare(req.name, image_data, req.threshold)
    resp = {
        "result": result.result.value if hasattr(result.result, 'value') else str(result.result),
        "diff_percentage": result.diff_percentage,
        "threshold": result.threshold,
        "baseline": {
            "name": result.baseline.name if result.baseline else "",
            "width": result.baseline.width if result.baseline else 0,
            "height": result.baseline.height if result.baseline else 0,
        },
        "current": {
            "name": result.current.name if result.current else "",
            "width": result.current.width if result.current else 0,
            "height": result.current.height if result.current else 0,
        },
    }

    # 包含差异图片
    if result.diff_filepath and os.path.exists(result.diff_filepath):
        try:
            with open(result.diff_filepath, "rb") as f:
                resp["diff_image"] = base64.b64encode(f.read()).decode()
        except Exception:
            pass

    # 包含基线图片
    if result.baseline and result.baseline.filepath and os.path.exists(result.baseline.filepath):
        try:
            with open(result.baseline.filepath, "rb") as f:
                resp["baseline_image"] = base64.b64encode(f.read()).decode()
        except Exception:
            pass

    return resp


class SaveBaselineRequest(BaseModel):
    name: str
    image_base64: str


@router.post("/baselines")
async def save_baseline(req: SaveBaselineRequest):
    """保存/更新基线"""
    tester = get_visual_tester()
    try:
        image_data = base64.b64decode(req.image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="无效的 base64 图片数据")

    result = tester.save_baseline(req.name, image_data)
    return ok({"baseline": {
        "name": result.name,
        "width": result.width,
        "height": result.height,
        "timestamp": result.timestamp,
    }})


@router.put("/baselines/{name}/approve")
async def approve_baseline(name: str):
    """批准当前截图为新基线（从最新比较结果中更新）"""
    tester = get_visual_tester()
    results_dir = tester.results_dir
    current_path = os.path.join(results_dir, f"{name}_current.png")
    if not os.path.exists(current_path):
        raise HTTPException(status_code=404, detail="未找到最近的比较结果")

    with open(current_path, "rb") as f:
        image_data = f.read()

    tester.update_baseline(name, image_data)
    return ok({"message": f"已批准 {name} 的新基线"})


@router.delete("/baselines/{name}")
async def delete_baseline(name: str):
    """删除基线"""
    tester = get_visual_tester()
    success = tester.delete_baseline(name)
    if not success:
        raise HTTPException(status_code=404, detail="基线不存在")
    return {"status": "success"}


@router.post("/capture")
async def capture_and_compare(req: CompareRequest):
    """一键：保存截图 → 比较基线 → 返回差异"""
    tester = get_visual_tester()
    try:
        image_data = base64.b64decode(req.image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="无效的 base64 图片数据")

    # 如果没有基线，先保存
    baselines = tester.list_baselines()
    has_baseline = any(b.get("name") == req.name for b in baselines)

    if not has_baseline:
        baseline = tester.save_baseline(req.name, image_data)
        return {
            "result": "new_baseline",
            "message": f"已保存 {req.name} 的基线",
            "baseline": {"name": baseline.name, "width": baseline.width, "height": baseline.height},
        }

    # 比较
    result = tester.compare(req.name, image_data, req.threshold)
    resp = {
        "result": result.result.value if hasattr(result.result, 'value') else str(result.result),
        "diff_percentage": result.diff_percentage,
        "threshold": result.threshold,
    }

    if result.diff_filepath and os.path.exists(result.diff_filepath):
        try:
            with open(result.diff_filepath, "rb") as f:
                resp["diff_image"] = base64.b64encode(f.read()).decode()
        except Exception:
            pass

    return resp
