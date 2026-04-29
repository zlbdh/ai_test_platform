# -*- coding: utf-8 -*-
"""
API 响应标准化工具

统一所有 Router 的响应格式，简化错误处理样板代码。
"""
import logging
import inspect
import traceback
from typing import Any, Optional

from fastapi import HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def ok(data: Any = None, message: str = "success") -> dict:
    """
    构建标准成功响应。

    Examples:
        @router.get("/items")
        async def list_items():
            items = await fetch_items()
            return ok(items)
        # → {"status": "ok", "data": [...], "message": "success"}
    """
    resp = {"status": "ok", "message": message}
    if data is not None:
        resp["data"] = data
    return resp


def fail(message: str, code: int = 400, detail: Any = None) -> JSONResponse:
    """
    构建标准失败响应（HTTP 200 但业务状态失败）。

    Examples:
        return fail("项目不存在", 404)
        # → status 200, {"status": "error", "message": "项目不存在"}
    """
    body: dict = {"status": "error", "message": message}
    if detail is not None:
        body["detail"] = detail
    return JSONResponse(content=body, status_code=code)


def safe_handler(func):
    """
    装饰器：自动包裹 try/except，统一异常响应。

    Examples:
        @router.post("/analyze")
        @safe_handler
        async def analyze(req: AnalyzeRequest):
            result = await heavy_computation(req)
            return ok(result)
        # 异常时自动返回: {"status": "error", "message": "...", "trace": "..."}
    """
    import functools

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            if inspect.isawaitable(result):
                return await result
            return result
        except HTTPException:
            raise  # 让 FastAPI 处理 HTTP 异常
        except ValueError as e:
            logger.warning(f"[{func.__name__}] 业务错误: {e}")
            return fail(str(e), 400)
        except Exception as e:
            logger.error(f"[{func.__name__}] 未预期异常: {e}\n{traceback.format_exc()}")
            return fail(
                f"服务器内部错误: {type(e).__name__}",
                500,
                detail=str(e),
            )

    return wrapper
