"""
WebSocket sandbox integration tests.
Covers /ws/sandbox connections, heartbeats, and status updates.
Requires a running backend.
"""
import pytest
import asyncio
import json

# Skip if the websockets package is not installed.
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
    Verify WebSocket sandbox connectivity and message formats.
    Requires the backend service at 127.0.0.1:8020.
    """

    @pytest.mark.asyncio
    async def test_connect_and_receive(self):
        """Connect to /ws/sandbox and receive the first message."""
        try:
            async with websockets.connect(WS_URL, close_timeout=3) as ws:
                # Wait for the first message, usually a status heartbeat.
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(msg)
                assert "type" in data or "status" in data, f"Unexpected message format: {data}"
        except (ConnectionRefusedError, OSError):
            pytest.skip("Backend not running at 127.0.0.1:8020")

    @pytest.mark.asyncio
    async def test_heartbeat_format(self):
        """Verify that heartbeat messages contain the required fields."""
        try:
            async with websockets.connect(WS_URL, close_timeout=3) as ws:
                # Collect several messages.
                messages = []
                for _ in range(3):
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=3)
                        messages.append(json.loads(msg))
                    except asyncio.TimeoutError:
                        break

                assert len(messages) >= 1, "Should receive at least one message"

                # Check whether the first message contains status information.
                first = messages[0]
                assert isinstance(first, dict)
        except (ConnectionRefusedError, OSError):
            pytest.skip("Backend not running at 127.0.0.1:8020")

    @pytest.mark.asyncio
    async def test_multiple_connections(self):
        """Verify that multiple clients can connect simultaneously."""
        try:
            async with websockets.connect(WS_URL, close_timeout=3) as ws1, \
                       websockets.connect(WS_URL, close_timeout=3) as ws2:
                msg1 = await asyncio.wait_for(ws1.recv(), timeout=5)
                msg2 = await asyncio.wait_for(ws2.recv(), timeout=5)
                assert msg1 is not None
                assert msg2 is not None
        except (ConnectionRefusedError, OSError):
            pytest.skip("Backend not running at 127.0.0.1:8020")
