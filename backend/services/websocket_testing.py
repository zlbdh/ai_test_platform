"""
WebSocket testing service.

Supports:
- Connection and disconnection
- Sending and receiving messages
- Assertion verification
- Performance metrics
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
import asyncio
import json
import time
import websockets
from websockets.exceptions import WebSocketException


@dataclass
class WSMessage:
    """WebSocket message"""
    direction: str  # send, receive
    content: Any
    timestamp: float
    message_type: str = "text"  # text, binary, ping, pong


@dataclass 
class WSAssertion:
    """WebSocket assertion"""
    message_index: int  # -1 means any message
    path: Optional[str]  # JSON path
    operator: str  # eq, ne, contains, exists, type
    expected: Any


@dataclass
class WSTestResult:
    """WebSocket test result"""
    connected: bool
    messages: List[WSMessage]
    assertions_passed: int
    assertions_failed: int
    total_time_ms: int
    error: Optional[str]


class WebSocketTestService:
    """WebSocket testing service"""
    
    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        subprotocols: Optional[List[str]] = None
    ):
        self.url = url
        self.headers = headers or {}
        self.subprotocols = subprotocols
        self.messages: List[WSMessage] = []
        self.connection = None
    
    async def connect(self, timeout: float = 10.0) -> bool:
        """Connect"""
        try:
            connect_kwargs = {
                "subprotocols": self.subprotocols,
            }
            if self.headers:
                connect_kwargs["additional_headers"] = self.headers
            try:
                self.connection = await asyncio.wait_for(
                    websockets.connect(
                        self.url,
                        **connect_kwargs,
                    ),
                    timeout=timeout
                )
            except TypeError as exc:
                if "additional_headers" not in str(exc):
                    raise
                fallback_kwargs = dict(connect_kwargs)
                fallback_kwargs["extra_headers"] = fallback_kwargs.pop("additional_headers", self.headers)
                self.connection = await asyncio.wait_for(
                    websockets.connect(
                        self.url,
                        **fallback_kwargs,
                    ),
                    timeout=timeout
                )
            return True
        except Exception as e:
            return False
    
    async def disconnect(self):
        """Disconnect"""
        if self.connection:
            await self.connection.close()
            self.connection = None
    
    async def send(self, message: Any, is_json: bool = True):
        """Send a message"""
        if not self.connection:
            raise RuntimeError("Not connected")
        
        if is_json and not isinstance(message, str):
            content = json.dumps(message)
        else:
            content = message
        
        await self.connection.send(content)
        
        self.messages.append(WSMessage(
            direction="send",
            content=message,
            timestamp=time.time()
        ))
    
    async def receive(self, timeout: float = 10.0) -> Any:
        """Receive a message"""
        if not self.connection:
            raise RuntimeError("Not connected")
        
        try:
            data = await asyncio.wait_for(
                self.connection.recv(),
                timeout=timeout
            )
            
            # Attempt to parse JSON
            try:
                content = json.loads(data)
            except Exception:
                content = data
            
            msg = WSMessage(
                direction="receive",
                content=content,
                timestamp=time.time()
            )
            self.messages.append(msg)
            
            return content
        
        except asyncio.TimeoutError:
            return None
    
    async def receive_all(
        self,
        count: int = 10,
        timeout: float = 5.0
    ) -> List[Any]:
        """Receive multiple messages"""
        received = []
        for _ in range(count):
            msg = await self.receive(timeout=timeout)
            if msg is None:
                break
            received.append(msg)
        return received
    
    def _get_value_by_path(self, data: Any, path: str) -> Any:
        """Get a value by path"""
        if not path:
            return data
        
        keys = path.split(".")
        value = data
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            elif isinstance(value, list) and key.isdigit():
                value = value[int(key)]
            else:
                return None
        
        return value
    
    def assert_messages(
        self,
        assertions: List[WSAssertion]
    ) -> List[Dict[str, Any]]:
        """Verify a message"""
        results = []
        
        received_messages = [m for m in self.messages if m.direction == "receive"]
        
        for assertion in assertions:
            if assertion.message_index == -1:
                # Check any message
                targets = received_messages
            elif 0 <= assertion.message_index < len(received_messages):
                targets = [received_messages[assertion.message_index]]
            else:
                results.append({
                    "passed": False,
                    "message": f"Message index {assertion.message_index} out of range"
                })
                continue
            
            passed = False
            actual = None
            
            for msg in targets:
                actual = self._get_value_by_path(msg.content, assertion.path)
                
                if assertion.operator == "eq":
                    passed = actual == assertion.expected
                elif assertion.operator == "ne":
                    passed = actual != assertion.expected
                elif assertion.operator == "contains":
                    passed = assertion.expected in str(actual) if actual else False
                elif assertion.operator == "exists":
                    passed = actual is not None
                elif assertion.operator == "type":
                    passed = type(actual).__name__ == assertion.expected
                
                if passed:
                    break
            
            results.append({
                "message_index": assertion.message_index,
                "path": assertion.path,
                "operator": assertion.operator,
                "expected": assertion.expected,
                "actual": actual,
                "passed": passed
            })
        
        return results
    
    async def run_scenario(
        self,
        scenario: List[Dict[str, Any]],
        assertions: Optional[List[WSAssertion]] = None
    ) -> WSTestResult:
        """Run a test scenario"""
        start_time = time.time()
        self.messages.clear()
        error = None
        connected = False
        
        try:
            # Connect
            connected = await self.connect()
            if not connected:
                raise RuntimeError("Failed to connect")
            
            # Execute scenario steps
            for step in scenario:
                action = step.get("action")
                
                if action == "send":
                    await self.send(
                        step.get("message", step.get("data")),
                        step.get("json", step.get("is_json", True))
                    )
                
                elif action == "receive":
                    count = step.get("count", 1)
                    timeout = step.get("timeout", 5.0)
                    for _ in range(count):
                        await self.receive(timeout=timeout)
                
                elif action == "wait":
                    await asyncio.sleep(step.get("seconds", 1))
        
        except Exception as e:
            error = str(e)
        
        finally:
            await self.disconnect()
        
        # Verify assertions
        assertions_passed = 0
        assertions_failed = 0
        
        if assertions:
            results = self.assert_messages(assertions)
            assertions_passed = sum(1 for r in results if r["passed"])
            assertions_failed = sum(1 for r in results if not r["passed"])
        
        total_time = int((time.time() - start_time) * 1000)
        
        return WSTestResult(
            connected=connected,
            messages=self.messages.copy(),
            assertions_passed=assertions_passed,
            assertions_failed=assertions_failed,
            total_time_ms=total_time,
            error=error
        )


def create_ws_test_service(
    url: str,
    headers: Optional[Dict[str, str]] = None
) -> WebSocketTestService:
    """Create a WebSocket testing service"""
    return WebSocketTestService(url, headers)
