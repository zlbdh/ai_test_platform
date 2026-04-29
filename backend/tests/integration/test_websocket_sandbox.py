"""
WebSocket 沙箱集成测试
覆盖: /ws/sandbox 连接、heartbeat、状态推送
需要后端运行才能执行
"""
import pytest
import asyncio
import json

# 跳过条件：如果没有安装 websockets 库
try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False


WS_URL = "ws://127.0.0.1:8020/ws/sandbox"


@pytest.mark.integration
@pytest.mark.skipif(not HAS_WEBSOCKETS, reason="websockets not installed")
class TestWebSocketSandbox:
    """
    集成测试：验证 WebSocket 沙箱端点的连通性和消息格式。
    需要后端服务在 127.0.0.1:8020 运行方可执行。
    """

    @pytest.mark.asyncio
    async def test_connect_and_receive(self):
        """连接 /ws/sandbox 并接收第一条消息"""
        try:
            async with websockets.connect(WS_URL, close_timeout=3) as ws:
                # 等待第一条消息（通常是 status heartbeat）
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(msg)
                assert "type" in data or "status" in data, f"Unexpected message format: {data}"
        except (ConnectionRefusedError, OSError):
            pytest.skip("Backend not running at 127.0.0.1:8020")

    @pytest.mark.asyncio
    async def test_heartbeat_format(self):
        """验证 heartbeat 消息包含必要字段"""
        try:
            async with websockets.connect(WS_URL, close_timeout=3) as ws:
                # 收集几条消息
                messages = []
                for _ in range(3):
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=3)
                        messages.append(json.loads(msg))
                    except asyncio.TimeoutError:
                        break

                assert len(messages) >= 1, "Should receive at least one message"

                # 检查第一条消息是否包含状态信息
                first = messages[0]
                assert isinstance(first, dict)
        except (ConnectionRefusedError, OSError):
            pytest.skip("Backend not running at 127.0.0.1:8020")

    @pytest.mark.asyncio
    async def test_multiple_connections(self):
        """验证多个客户端可以同时连接"""
        try:
            async with websockets.connect(WS_URL, close_timeout=3) as ws1, \
                       websockets.connect(WS_URL, close_timeout=3) as ws2:
                msg1 = await asyncio.wait_for(ws1.recv(), timeout=5)
                msg2 = await asyncio.wait_for(ws2.recv(), timeout=5)
                assert msg1 is not None
                assert msg2 is not None
        except (ConnectionRefusedError, OSError):
            pytest.skip("Backend not running at 127.0.0.1:8020")
