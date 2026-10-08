# -*- coding: utf-8 -*-
"""
AgentBus — inter-agent communication bus

Design:
- Publish/subscribe: agents subscribe to topics of interest
- Request/response: Commander sends tasks to specific agents and waits for results
- Agent registry: agents register their type and capabilities at startup
- Message log: persist all messages for auditing

Relationship with the existing EventBus:
- EventBus provides session-level Planner↔Executor communication through queue.Queue
- AgentBus provides the global inter-agent communication network
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import (
    Any, Callable, Coroutine, Dict, List, Optional, Set,
)

logger = logging.getLogger(__name__)


# ── Data structures ──────────────────────────────────────────────────────────────────


class MessageType(Enum):
    """Message type"""
    EVENT = "event"         # Broadcast event (publish/subscribe)
    REQUEST = "request"     # Task request (request/response)
    RESPONSE = "response"   # Task response
    HANDOFF = "handoff"     # Inter-agent task handoff
    LOG = "log"             # Log message


class MessagePriority(Enum):
    """Message priority"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class AgentMessage:
    """Unified message format"""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    msg_type: MessageType = MessageType.EVENT
    topic: str = ""               # Event topic, such as "test.completed"
    sender: str = ""              # Sender agent name
    receiver: str = ""            # Receiver (empty means broadcast)
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    correlation_id: str = ""      # Request/response correlation ID

    def to_dict(self) -> dict:
        d = asdict(self)
        d["msg_type"] = self.msg_type.value
        d["priority"] = self.priority.value
        return d


@dataclass
class AgentRegistration:
    """Agent registration information"""
    agent_name: str
    agent_type: str               # For example: "ui_tester", "api_tester", "security_scanner"
    supported_test_types: List[str] = field(default_factory=list)
    description: str = ""
    registered_at: float = field(default_factory=time.time)
    is_active: bool = True
    last_heartbeat: float = field(default_factory=time.time)
    profile_id: str = ""          # Linked AgentProfile


# ── Predefined topics ─────────────────────────────────────────────────────────────


class Topics:
    """Predefined event topics"""
    # Test lifecycle
    TEST_STARTED = "test.started"
    TEST_COMPLETED = "test.completed"
    TEST_FAILED = "test.failed"
    TEST_CANCELLED = "test.cancelled"

    # Task dispatch
    TASK_DISPATCHED = "task.dispatched"
    TASK_ACCEPTED = "task.accepted"

    # Errors and alerts
    ANOMALY_FOUND = "anomaly.found"
    CRITICAL_FAILURE = "critical.failure"

    # Orchestration
    MISSION_STARTED = "mission.started"
    MISSION_COMPLETED = "mission.completed"
    MISSION_PROGRESS = "mission.progress"

    # System
    AGENT_REGISTERED = "agent.registered"
    AGENT_UNREGISTERED = "agent.unregistered"


# ── Callback type alias ─────────────────────────────────────────────────────────────

SubscriberCallback = Callable[[AgentMessage], Coroutine[Any, Any, None]]


# ── AgentBus core ────────────────────────────────────────────────────────────


class AgentBus:
    """
    Inter-agent communication bus

    Features:
    1. Agent registry (availability and capabilities)
    2. Publish/subscribe (broadcast events)
    3. Request/response (targeted tasks)
    4. Message log (audit trail)
    """

    def __init__(self):
        # Agent registry
        self._agents: Dict[str, AgentRegistration] = {}

        # Subscriptions: topic -> [callback]
        self._subscribers: Dict[str, List[SubscriberCallback]] = {}

        # Pending requests: correlation_id -> Future
        self._pending_requests: Dict[str, asyncio.Future] = {}

        # Message log (latest N entries)
        self._message_log: List[Dict] = []
        self._max_log_size = 500

        logger.info("[AgentBus] Initialization complete")

    # ── Agent registration ────────────────────────────────────────────────────────

    def register_agent(
        self,
        agent_name: str,
        agent_type: str,
        supported_test_types: Optional[List[str]] = None,
        description: str = "",
        profile_id: str = "",
    ) -> AgentRegistration:
        """Register an agent with the bus, optionally linking a profile"""
        reg = AgentRegistration(
            agent_name=agent_name,
            agent_type=agent_type,
            supported_test_types=supported_test_types or [],
            description=description,
            profile_id=profile_id,
        )
        self._agents[agent_name] = reg
        logger.info(f"[AgentBus] Agent registered: {agent_name} ({agent_type})")

        # Broadcast registration event
        try:
            asyncio.ensure_future(self.publish(AgentMessage(
                topic=Topics.AGENT_REGISTERED,
                sender="agent_bus",
                payload={"agent_name": agent_name, "agent_type": agent_type, "profile_id": profile_id},
            )))
        except RuntimeError:
            pass  # Ignore the absence of an event loop during startup
        return reg

    def unregister_agent(self, agent_name: str) -> bool:
        """Unregister an agent"""
        if agent_name in self._agents:
            self._agents[agent_name].is_active = False
            del self._agents[agent_name]
            logger.info(f"[AgentBus] Agent unregistered: {agent_name}")
            return True
        return False

    def get_agent(self, agent_name: str) -> Optional[AgentRegistration]:
        """Get agent registration information"""
        return self._agents.get(agent_name)

    def get_agents_by_type(self, agent_type: str) -> List[AgentRegistration]:
        """Find agents by type"""
        return [a for a in self._agents.values() if a.agent_type == agent_type and a.is_active]

    def get_agent_for_test_type(self, test_type: str) -> Optional[AgentRegistration]:
        """Find agents capable of the requested test type"""
        for agent in self._agents.values():
            if agent.is_active and test_type in agent.supported_test_types:
                return agent
        return None

    def list_agents(self) -> List[Dict]:
        """List all online agents"""
        return [
            {
                "name": a.agent_name,
                "type": a.agent_type,
                "test_types": a.supported_test_types,
                "active": a.is_active,
            }
            for a in self._agents.values()
        ]

    # ── Publish/subscribe ────────────────────────────────────────────────────────

    def subscribe(self, topic: str, callback: SubscriberCallback) -> None:
        """Subscribe to an event topic"""
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(callback)
        logger.debug(f"[AgentBus] Subscribed: {topic} ({len(self._subscribers[topic])} total)")

    def unsubscribe(self, topic: str, callback: SubscriberCallback) -> None:
        """Unsubscribe"""
        if topic in self._subscribers and callback in self._subscribers[topic]:
            self._subscribers[topic].remove(callback)

    async def publish(self, message: AgentMessage) -> None:
        """Publish an event to all subscribers"""
        self._log_message(message)

        callbacks = self._subscribers.get(message.topic, [])
        if not callbacks:
            return

        # Notify all subscribers concurrently
        tasks = []
        for cb in callbacks:
            tasks.append(self._safe_call(cb, message))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_call(self, callback: SubscriberCallback, message: AgentMessage) -> None:
        """Call a callback safely, catching exceptions"""
        try:
            await callback(message)
        except Exception as e:
            logger.error(f"[AgentBus] Subscriber callback failed: {e}", exc_info=True)

    # ── Request/response ─────────────────────────────────────────────────────────

    async def request(
        self,
        receiver: str,
        payload: Dict[str, Any],
        sender: str = "commander",
        timeout: float = 300.0,
    ) -> Optional[Dict[str, Any]]:
        """
        Send a task request to an agent and wait for its response.

        Args:
            receiver: Target agent name
            payload: Task parameters
            sender: Sender name
            timeout: Timeout in seconds

        Returns:
            Response payload, or None on timeout
        """
        correlation_id = str(uuid.uuid4())[:12]
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_requests[correlation_id] = future

        # Send the request message
        request_msg = AgentMessage(
            msg_type=MessageType.REQUEST,
            topic=Topics.TASK_DISPATCHED,
            sender=sender,
            receiver=receiver,
            payload=payload,
            correlation_id=correlation_id,
        )
        await self.publish(request_msg)

        # Wait for the response
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"[AgentBus] Request timed out: {receiver} (correlation={correlation_id})")
            return None
        finally:
            self._pending_requests.pop(correlation_id, None)

    async def respond(
        self,
        correlation_id: str,
        payload: Dict[str, Any],
        sender: str = "",
    ) -> None:
        """
        Respond to a request.

        Args:
            correlation_id: Correlation ID matching the request
            payload: Response data
            sender: Responder name
        """
        # Wake the waiting caller directly through its Future
        future = self._pending_requests.get(correlation_id)
        if future and not future.done():
            future.set_result(payload)

        # Also publish the response event for auditing and tracing
        response_msg = AgentMessage(
            msg_type=MessageType.RESPONSE,
            topic=Topics.TEST_COMPLETED,
            sender=sender,
            correlation_id=correlation_id,
            payload=payload,
        )
        self._log_message(response_msg)

    # ── Batch dispatch and collection ────────────────────────────────────────────────────

    async def dispatch_and_collect(
        self,
        tasks: List[Dict[str, Any]],
        parallel: bool = True,
        timeout: float = 600.0,
    ) -> List[Dict[str, Any]]:
        """
        Dispatch tasks to matching agents and collect the results.

        Args:
            tasks: Task list; each task must include "test_type" and "config"
            parallel: Whether to run concurrently
            timeout: Per-task timeout

        Returns:
            Result list
        """
        results = []

        if parallel:
            # Concurrent dispatch
            coros = []
            for task in tasks:
                test_type = task.get("test_type", "")
                agent_reg = self.get_agent_for_test_type(test_type)
                if agent_reg:
                    coros.append(self.request(
                        receiver=agent_reg.agent_name,
                        payload=task,
                        timeout=timeout,
                    ))
                else:
                    logger.warning(f"[AgentBus] No agent can handle: {test_type}")
                    results.append({
                        "test_type": test_type,
                        "status": "skipped",
                        "reason": f"No agent registered for {test_type}",
                    })

            if coros:
                gathered = await asyncio.gather(*coros, return_exceptions=True)
                for i, res in enumerate(gathered):
                    if isinstance(res, Exception):
                        results.append({
                            "test_type": tasks[i].get("test_type", ""),
                            "status": "error",
                            "error": str(res),
                        })
                    elif res is None:
                        results.append({
                            "test_type": tasks[i].get("test_type", ""),
                            "status": "timeout",
                        })
                    else:
                        results.append(res)
        else:
            # Sequential execution
            for task in tasks:
                test_type = task.get("test_type", "")
                agent_reg = self.get_agent_for_test_type(test_type)
                if agent_reg:
                    res = await self.request(
                        receiver=agent_reg.agent_name,
                        payload=task,
                        timeout=timeout,
                    )
                    results.append(res or {
                        "test_type": test_type,
                        "status": "timeout",
                    })
                else:
                    results.append({
                        "test_type": test_type,
                        "status": "skipped",
                        "reason": f"No agent registered for {test_type}",
                    })

        return results

    # ── Inter-agent task handoff(Handoff)────────────────────────────────────────

    async def handoff(
        self,
        sender: str,
        receiver: str,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Hand off tasks between agents, including context.

        Similar to OpenClaw agentToAgent handoff.
        The sender forwards the task and context to the receiver.

        Args:
            sender: Handing-off agent
            receiver: Receiving agent
            task: Task data
            context: Context, including prior agent results

        Returns:
            Execution result from the receiving agent
        """
        handoff_payload = {
            "handoff_from": sender,
            "task": task,
            "context": context or {},
        }

        # Record the handoff message
        handoff_msg = AgentMessage(
            msg_type=MessageType.HANDOFF,
            topic="agent.handoff",
            sender=sender,
            receiver=receiver,
            payload=handoff_payload,
        )
        self._log_message(handoff_msg)
        logger.info(f"[AgentBus] Handoff: {sender} → {receiver}")

        # Forward through the request mechanism
        return await self.request(
            receiver=receiver,
            payload=handoff_payload,
            sender=sender,
            timeout=task.get("timeout", 300),
        )

    # ── Heartbeats and health checks ───────────────────────────────────────────────────

    def heartbeat(self, agent_name: str) -> bool:
        """Report an agent heartbeat"""
        agent = self._agents.get(agent_name)
        if agent:
            agent.last_heartbeat = time.time()
            agent.is_active = True
            return True
        return False

    def get_health(self, timeout_threshold: float = 120.0) -> List[Dict]:
        """Get health status for all agents"""
        now = time.time()
        return [
            {
                "name": a.agent_name,
                "type": a.agent_type,
                "active": a.is_active,
                "profile_id": a.profile_id,
                "last_heartbeat_ago": round(now - a.last_heartbeat, 1),
                "healthy": (now - a.last_heartbeat) < timeout_threshold,
            }
            for a in self._agents.values()
        ]

    # ── Broadcast by test type ────────────────────────────────────────────────────

    async def broadcast_by_type(
        self,
        test_types: List[str],
        message: Dict[str, Any],
        sender: str = "commander",
    ) -> None:
        """Broadcast to every agent capable of the requested test type"""
        for agent in self._agents.values():
            if not agent.is_active:
                continue
            if any(t in agent.supported_test_types for t in test_types):
                await self.publish(AgentMessage(
                    topic="squad.broadcast",
                    sender=sender,
                    receiver=agent.agent_name,
                    payload=message,
                ))

    # ── Message log ──────────────────────────────────────────────────────────

    def _log_message(self, message: AgentMessage) -> None:
        """Record a message in the in-memory log"""
        entry = message.to_dict()
        entry["logged_at"] = datetime.now().isoformat()
        self._message_log.append(entry)

        # Limit log size
        if len(self._message_log) > self._max_log_size:
            self._message_log = self._message_log[-self._max_log_size:]

    def get_message_log(self, limit: int = 50, topic: Optional[str] = None) -> List[Dict]:
        """Get the message log"""
        logs = self._message_log
        if topic:
            logs = [m for m in logs if m.get("topic") == topic]
        return logs[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get communication statistics"""
        return {
            "registered_agents": len(self._agents),
            "active_agents": sum(1 for a in self._agents.values() if a.is_active),
            "subscriptions": {t: len(cbs) for t, cbs in self._subscribers.items()},
            "pending_requests": len(self._pending_requests),
            "message_log_size": len(self._message_log),
        }


# ── Singleton ─────────────────────────────────────────────────────────────────────

_agent_bus: Optional[AgentBus] = None


def get_agent_bus() -> AgentBus:
    """Get the AgentBus singleton"""
    global _agent_bus
    if _agent_bus is None:
        _agent_bus = AgentBus()
    return _agent_bus
