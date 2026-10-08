import pytest
from unittest.mock import AsyncMock

from routers import commander


class _DummyResponse:
    def __init__(self, body: dict, status_code: int = 200):
        self._body = body
        self.status_code = status_code
        self.content = b"{}" if body is not None else b""

    def json(self):
        return self._body


class _DummyAsyncClient:
    def __init__(self, response: _DummyResponse):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        return self._response


@pytest.mark.asyncio
async def test_get_notification_platform_tenant_access_token_accepts_code_zero(monkeypatch):
    monkeypatch.setattr(commander.Config, "NOTIFICATION_PLATFORM_APP_ID", "cli_a932544ff57a9bcb")
    monkeypatch.setattr(commander.Config, "NOTIFICATION_PLATFORM_APP_SECRET", "secret-demo")
    monkeypatch.setattr(
        commander.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _DummyAsyncClient(
            _DummyResponse(
                {
                    "code": 0,
                    "msg": "ok",
                    "tenant_access_token": "t-demo-token",
                },
                status_code=200,
            )
        ),
    )

    result = await commander._get_notification_platform_tenant_access_token()

    assert result["ok"] is True
    assert result["token"] == "t-demo-token"
    assert result["status_code"] == 200
    assert "tenant_access_token" in result["message"]


@pytest.mark.asyncio
async def test_deliver_commander_response_via_notification_platform_app_bot_accepts_code_zero(monkeypatch):
    monkeypatch.setattr(
        commander,
        "_get_notification_platform_tenant_access_token",
        AsyncMock(
            return_value={
                "ok": True,
                "token": "t-demo-token",
                "app_bot_configured": True,
                "message": "应用机器人凭据校验通过，已成功获取 tenant_access_token。",
            }
        ),
    )
    monkeypatch.setattr(
        commander.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _DummyAsyncClient(
            _DummyResponse(
                {
                    "code": 0,
                    "msg": "ok",
                    "data": {"message_id": "om_xxx"},
                },
                status_code=200,
            )
        ),
    )

    result = await commander._deliver_commander_response_via_notification_platform_app_bot("hello", "oc_demo")

    assert result["configured"] == 1
    assert result["delivered"] == 1
    assert result["failed"] == 0
    assert result["mode"] == "app_bot"
    assert "reply sent" in result["message"]
