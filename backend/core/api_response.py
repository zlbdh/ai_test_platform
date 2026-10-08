# -*- coding: utf-8 -*-
"""
API response standardization utilities

Standardize router responses and reduce error-handling boilerplate.
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
    Build a standard success response.

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
    Build a standard failure response with HTTP 200 and a failed business status.

    Examples:
        return fail("Project not found", 404)
        # → status 200, {"status": "error", "message": "Project not found"}
    """
    body: dict = {"status": "error", "message": message}
    if detail is not None:
        body["detail"] = detail
    return JSONResponse(content=body, status_code=code)


def safe_handler(func):
    """
    Decorator that wraps calls in try/except for consistent error responses.

    Examples:
        @router.post("/analyze")
        @safe_handler
        async def analyze(req: AnalyzeRequest):
            result = await heavy_computation(req)
            return ok(result)
        # Automatically return on exception: {"status": "error", "message": "...", "trace": "..."}
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
            raise  # Let FastAPI handle HTTP exceptions
        except ValueError as e:
            logger.warning(f"[{func.__name__}] Business error: {e}")
            return fail(str(e), 400)
        except Exception as e:
            logger.error(f"[{func.__name__}] Unexpected exception: {e}\n{traceback.format_exc()}")
            return fail(
                f"Internal server error: {type(e).__name__}",
                500,
                detail=str(e),
            )

    return wrapper
