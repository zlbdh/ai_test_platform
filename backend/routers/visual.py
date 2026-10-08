# -*- coding: utf-8 -*-
"""
Visual Regression Router — Visual regression testing API
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
    """List all visual baselines"""
    tester = get_visual_tester()
    baselines = tester.list_baselines()
    # Add a base64 thumbnail to each baseline
    result = []
    for b in baselines:
        item = {
            "name": b.get("name", ""),
            "width": b.get("width", 0),
            "height": b.get("height", 0),
            "timestamp": b.get("timestamp", ""),
            "hash": b.get("hash", ""),
        }
        # Read the thumbnail
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
    """Compare a screenshot against the baseline"""
    tester = get_visual_tester()
    try:
        image_data = base64.b64decode(req.image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")

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

    # Include the difference image
    if result.diff_filepath and os.path.exists(result.diff_filepath):
        try:
            with open(result.diff_filepath, "rb") as f:
                resp["diff_image"] = base64.b64encode(f.read()).decode()
        except Exception:
            pass

    # Include the baseline image
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
    """Save or update a baseline"""
    tester = get_visual_tester()
    try:
        image_data = base64.b64decode(req.image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")

    result = tester.save_baseline(req.name, image_data)
    return ok({"baseline": {
        "name": result.name,
        "width": result.width,
        "height": result.height,
        "timestamp": result.timestamp,
    }})


@router.put("/baselines/{name}/approve")
async def approve_baseline(name: str):
    """Approve the current screenshot as the new baseline using the latest comparison result"""
    tester = get_visual_tester()
    results_dir = tester.results_dir
    current_path = os.path.join(results_dir, f"{name}_current.png")
    if not os.path.exists(current_path):
        raise HTTPException(status_code=404, detail="No recent comparison result found")

    with open(current_path, "rb") as f:
        image_data = f.read()

    tester.update_baseline(name, image_data)
    return ok({"message": f"Approved the new baseline for {name}"})


@router.delete("/baselines/{name}")
async def delete_baseline(name: str):
    """Delete a baseline"""
    tester = get_visual_tester()
    success = tester.delete_baseline(name)
    if not success:
        raise HTTPException(status_code=404, detail="Baseline does not exist")
    return {"status": "success"}


@router.post("/capture")
async def capture_and_compare(req: CompareRequest):
    """One click: save screenshot → compare baseline → return differences"""
    tester = get_visual_tester()
    try:
        image_data = base64.b64decode(req.image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")

    # Save a baseline first if none exists
    baselines = tester.list_baselines()
    has_baseline = any(b.get("name") == req.name for b in baselines)

    if not has_baseline:
        baseline = tester.save_baseline(req.name, image_data)
        return {
            "result": "new_baseline",
            "message": f"Saved the baseline for {req.name}",
            "baseline": {"name": baseline.name, "width": baseline.width, "height": baseline.height},
        }

    # Compare
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
