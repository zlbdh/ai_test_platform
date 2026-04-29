# -*- coding: utf-8 -*-
"""
知识库路由 — 使用 KnowledgeBase 单例
"""
from fastapi import APIRouter, HTTPException
from fastapi import UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, Dict, Any
from pathlib import Path
import os
import tempfile

router = APIRouter(tags=["knowledge"])


class KnowledgeAddRequest(BaseModel):
    content: str
    metadata: Optional[Dict[str, Any]] = None


class KnowledgeQueryRequest(BaseModel):
    query: str
    k: int = 5


def _get_kb():
    """获取 KnowledgeBase 单例"""
    from services.knowledge import KnowledgeBase
    return KnowledgeBase.get_instance()


@router.get("/api/knowledge/status")
async def api_knowledge_status():
    """获取知识库状态"""
    kb = _get_kb()
    return {"status": "success", **kb.get_status()}


@router.post("/api/knowledge/add")
async def api_knowledge_add(request: KnowledgeAddRequest):
    """添加知识条目"""
    kb = _get_kb()
    success = kb.add_knowledge(request.content, request.metadata)
    if success:
        return {"status": "success", "message": "Knowledge added"}
    raise HTTPException(status_code=500, detail="Failed to add knowledge")


@router.post("/api/knowledge/query")
async def api_knowledge_query(request: KnowledgeQueryRequest):
    """查询相关知识"""
    kb = _get_kb()
    results = kb.query_knowledge(request.query, request.k)
    return {"status": "success", "results": results}


@router.get("/api/knowledge/list")
async def api_knowledge_list(limit: int = 100):
    """列出所有知识"""
    kb = _get_kb()
    items = kb.list_knowledge(limit)
    return {"status": "success", "items": items, "count": len(items)}


@router.get("/api/knowledge/{doc_id}/content")
async def api_knowledge_content(doc_id: str):
    """获取单条知识内容用于预览"""
    kb = _get_kb()
    item = kb.get_knowledge_item(doc_id)
    if not item:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    return {
        "status": "success",
        "content": item.get("content", ""),
        "metadata": item.get("metadata", {}),
    }


@router.post("/api/knowledge/upload")
async def api_knowledge_upload(
    file: UploadFile = File(...),
    description: str = Form(""),
):
    """上传并摄入知识文件"""
    suffix = Path(file.filename or "upload.txt").suffix.lower()
    if suffix == ".pdf":
        raise HTTPException(status_code=400, detail="暂不支持 PDF 上传，请先转换为 Markdown、TXT 或 JSON")

    kb = _get_kb()
    fd, temp_path = tempfile.mkstemp(prefix="kb-upload-", suffix=suffix or ".txt")
    os.close(fd)
    try:
        data = await file.read()
        with open(temp_path, "wb") as fh:
            fh.write(data)
        success = kb.ingest_file(temp_path, {
            "description": description,
            "original_filename": file.filename or "",
        })
        if success:
            return {"status": "success", "message": "Knowledge uploaded", "filename": file.filename}
        raise HTTPException(status_code=500, detail="Failed to ingest knowledge file")
    finally:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass


@router.delete("/api/knowledge/{doc_id}")
async def api_knowledge_delete(doc_id: str):
    """删除知识条目"""
    kb = _get_kb()
    success = kb.delete_knowledge(doc_id)
    if success:
        return {"status": "success", "message": f"Knowledge {doc_id} deleted"}
    raise HTTPException(status_code=500, detail="Failed to delete knowledge")


@router.post("/api/knowledge/clear")
async def api_knowledge_clear():
    """清空所有知识"""
    kb = _get_kb()
    if not kb.enabled:
        return {"status": "success", "message": "Knowledge base not enabled, nothing to clear"}
    success = kb.clear_knowledge()
    if success:
        return {"status": "success", "message": "All knowledge cleared"}
    raise HTTPException(status_code=500, detail="Failed to clear knowledge")
