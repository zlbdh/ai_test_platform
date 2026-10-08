"""
api_response unit tests.
Covers ok, fail, and safe_handler for sync/async, HTTP, value, and general exceptions.
"""
import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from core.api_response import ok, fail, safe_handler


class TestOk:
    def test_returns_basic_payload(self):
        assert ok() == {"status": "ok", "message": "success"}

    def test_includes_data_when_present(self):
        assert ok({"id": 1}, message="created") == {
            "status": "ok",
            "message": "created",
            "data": {"id": 1},
        }


class TestFail:
    def test_returns_json_response(self):
        resp = fail("not found", 404, detail={"id": 1})
        assert isinstance(resp, JSONResponse)
        assert resp.status_code == 404
        assert resp.body == b'{"status":"error","message":"not found","detail":{"id":1}}'

    def test_omits_detail_when_absent(self):
        resp = fail("bad request")
        assert resp.status_code == 400
        assert resp.body == b'{"status":"error","message":"bad request"}'


class TestSafeHandler:
    @pytest.mark.asyncio
    async def test_wraps_async_success(self):
        @safe_handler
        async def handler():
            return ok({"name": "demo"})

        result = await handler()
        assert result["data"]["name"] == "demo"

    @pytest.mark.asyncio
    async def test_wraps_sync_success(self):
        @safe_handler
        def handler():
            return ok({"sync": True})

        result = await handler()
        assert result["data"]["sync"] is True

    @pytest.mark.asyncio
    async def test_reraises_http_exception(self):
        @safe_handler
        async def handler():
            raise HTTPException(status_code=403, detail="forbidden")

        with pytest.raises(HTTPException) as exc:
            await handler()
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_value_error_becomes_business_error(self):
        @safe_handler
        async def handler():
            raise ValueError("invalid payload")

        result = await handler()
        assert result.status_code == 400
        assert result.body == b'{"status":"error","message":"invalid payload"}'

    @pytest.mark.asyncio
    async def test_general_exception_becomes_server_error(self):
        @safe_handler
        async def handler():
            raise RuntimeError("boom")

        result = await handler()
        assert result.status_code == 500
        assert b'"status":"error"' in result.body
        assert b'"detail":"boom"' in result.body
