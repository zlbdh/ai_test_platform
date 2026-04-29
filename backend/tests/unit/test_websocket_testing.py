"""
WebSocketTestService 单元测试
覆盖: 数据类, _get_value_by_path, assert_messages,
      send/receive (not connected), connect/disconnect mock, 工厂函数
"""
import pytest
import time
from unittest.mock import patch, AsyncMock, MagicMock

from services.websocket_testing import (
    WSMessage, WSAssertion, WSTestResult,
    WebSocketTestService, create_ws_test_service
)


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------
class TestWSMessage:
    def test_creation(self):
        m = WSMessage(direction="send", content="hi", timestamp=time.time())
        assert m.message_type == "text"


class TestWSAssertion:
    def test_creation(self):
        a = WSAssertion(message_index=0, path="data.id", operator="eq", expected=1)
        assert a.message_index == 0


class TestWSTestResult:
    def test_creation(self):
        r = WSTestResult(connected=True, messages=[], assertions_passed=1,
                         assertions_failed=0, total_time_ms=50, error=None)
        assert r.connected is True


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def svc():
    return WebSocketTestService(url="ws://localhost:8080/ws")


# ---------------------------------------------------------------------------
# _get_value_by_path
# ---------------------------------------------------------------------------
class TestGetValueByPath:
    def test_dict(self, svc):
        assert svc._get_value_by_path({"a": {"b": 1}}, "a.b") == 1

    def test_empty_path(self, svc):
        data = {"x": 1}
        assert svc._get_value_by_path(data, "") == data

    def test_list(self, svc):
        assert svc._get_value_by_path({"items": [10, 20]}, "items.1") == 20

    def test_missing(self, svc):
        assert svc._get_value_by_path({"a": 1}, "b.c") is None


# ---------------------------------------------------------------------------
# assert_messages
# ---------------------------------------------------------------------------
class TestAssertMessages:
    def _setup_messages(self, svc, contents):
        """给 svc 注入模拟接收消息"""
        svc.messages = [
            WSMessage(direction="receive", content=c, timestamp=time.time())
            for c in contents
        ]

    def test_eq_pass(self, svc):
        self._setup_messages(svc, [{"name": "Alice"}])
        results = svc.assert_messages([
            WSAssertion(message_index=0, path="name", operator="eq", expected="Alice")
        ])
        assert results[0]["passed"] is True

    def test_eq_fail(self, svc):
        self._setup_messages(svc, [{"name": "Bob"}])
        results = svc.assert_messages([
            WSAssertion(message_index=0, path="name", operator="eq", expected="Alice")
        ])
        assert results[0]["passed"] is False

    def test_any_message(self, svc):
        """message_index=-1 应搜索所有消息"""
        self._setup_messages(svc, [{"x": 1}, {"x": 2}, {"x": 3}])
        results = svc.assert_messages([
            WSAssertion(message_index=-1, path="x", operator="eq", expected=3)
        ])
        assert results[0]["passed"] is True

    def test_out_of_range(self, svc):
        self._setup_messages(svc, [{"a": 1}])
        results = svc.assert_messages([
            WSAssertion(message_index=99, path="a", operator="eq", expected=1)
        ])
        assert results[0]["passed"] is False

    def test_contains(self, svc):
        self._setup_messages(svc, [{"msg": "hello world"}])
        results = svc.assert_messages([
            WSAssertion(message_index=0, path="msg", operator="contains", expected="world")
        ])
        assert results[0]["passed"] is True

    def test_exists(self, svc):
        self._setup_messages(svc, [{"key": "val"}])
        results = svc.assert_messages([
            WSAssertion(message_index=0, path="key", operator="exists", expected=True)
        ])
        assert results[0]["passed"] is True

    def test_type(self, svc):
        self._setup_messages(svc, [{"count": 5}])
        results = svc.assert_messages([
            WSAssertion(message_index=0, path="count", operator="type", expected="int")
        ])
        assert results[0]["passed"] is True


# ---------------------------------------------------------------------------
# send / receive 未连接
# ---------------------------------------------------------------------------
class TestNotConnected:
    @pytest.mark.asyncio
    async def test_send_raises(self, svc):
        with pytest.raises(RuntimeError, match="Not connected"):
            await svc.send("hello")

    @pytest.mark.asyncio
    async def test_receive_raises(self, svc):
        with pytest.raises(RuntimeError, match="Not connected"):
            await svc.receive()


# ---------------------------------------------------------------------------
# connect / disconnect (mock websockets)
# ---------------------------------------------------------------------------
class TestConnection:
    @pytest.mark.asyncio
    async def test_connect_success(self, svc):
        mock_ws = AsyncMock()
        # websockets.connect returns a coroutine, so we need AsyncMock for it
        with patch("websockets.connect", new_callable=AsyncMock, return_value=mock_ws) as mocked_connect:
            result = await svc.connect()
        assert result is True
        assert svc.connection is not None
        mocked_connect.assert_called_once_with(
            svc.url,
            subprotocols=svc.subprotocols,
        )

    @pytest.mark.asyncio
    async def test_connect_success_with_headers_uses_additional_headers(self):
        svc = WebSocketTestService(url="ws://localhost:8080/ws", headers={"X-Trace": "demo"})
        mock_ws = AsyncMock()
        with patch("websockets.connect", new_callable=AsyncMock, return_value=mock_ws) as mocked_connect:
            result = await svc.connect()
        assert result is True
        mocked_connect.assert_called_once_with(
            svc.url,
            additional_headers={"X-Trace": "demo"},
            subprotocols=svc.subprotocols,
        )

    @pytest.mark.asyncio
    async def test_connect_falls_back_to_extra_headers_for_legacy_websockets(self):
        svc = WebSocketTestService(url="ws://localhost:8080/ws", headers={"X-Trace": "demo"})
        mock_ws = AsyncMock()
        mocked_connect = AsyncMock(side_effect=[TypeError("unexpected keyword argument 'additional_headers'"), mock_ws])
        with patch("websockets.connect", mocked_connect):
            result = await svc.connect()
        assert result is True
        assert mocked_connect.await_args_list[0].kwargs["additional_headers"] == {"X-Trace": "demo"}
        assert mocked_connect.await_args_list[1].kwargs["extra_headers"] == {"X-Trace": "demo"}

    @pytest.mark.asyncio
    async def test_connect_failure(self, svc):
        with patch("websockets.connect", side_effect=Exception("refused")):
            result = await svc.connect()
        assert result is False

    @pytest.mark.asyncio
    async def test_disconnect(self, svc):
        mock_ws = AsyncMock()
        svc.connection = mock_ws
        await svc.disconnect()
        assert svc.connection is None


# ---------------------------------------------------------------------------
# 工厂
# ---------------------------------------------------------------------------
class TestFactory:
    def test_create(self):
        svc = create_ws_test_service("ws://localhost:8080", {"X-Auth": "token"})
        assert isinstance(svc, WebSocketTestService)
        assert svc.headers["X-Auth"] == "token"
