# -*- coding: utf-8 -*-
"""
AgentBus — 跨 Agent 通信总线

设计：
- 发布/订阅模式：Agent 通过 topic 订阅感兴趣的事件
- 请求/响应模式：Commander 向特定 Agent 发送任务并等待结果
- Agent 注册表：每个 Agent 启动时注册自己的类型和能力
- 消息日志：所有消息持久化，支持审计

与现有 EventBus 的关系：
- EventBus 是会话级的 Planner↔Executor 通信（queue.Queue）
- AgentBus 是全局级的跨 Agent 通信网络
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


# ── 数据结构 ──────────────────────────────────────────────────────────────────


class MessageType(Enum):
    """消息类型"""
    EVENT = "event"         # 广播事件（发布/订阅）
    REQUEST = "request"     # 任务请求（请求/响应）
    RESPONSE = "response"   # 任务响应
    HANDOFF = "handoff"     # Agent 间任务交接
    LOG = "log"             # 日志消息


class MessagePriority(Enum):
    """消息优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class AgentMessage:
    """统一消息格式"""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    msg_type: MessageType = MessageType.EVENT
    topic: str = ""               # 事件主题，如 "test.completed"
    sender: str = ""              # 发送方 Agent 名称
    receiver: str = ""            # 接收方（空 = 广播）
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    correlation_id: str = ""      # 请求/响应关联 ID

    def to_dict(self) -> dict:
        d = asdict(self)
        d["msg_type"] = self.msg_type.value
        d["priority"] = self.priority.value
        return d


@dataclass
class AgentRegistration:
    """Agent 注册信息"""
    agent_name: str
    agent_type: str               # 如 "ui_tester", "api_tester", "security_scanner"
    supported_test_types: List[str] = field(default_factory=list)
    description: str = ""
    registered_at: float = field(default_factory=time.time)
    is_active: bool = True
    last_heartbeat: float = field(default_factory=time.time)
    profile_id: str = ""          # 关联 AgentProfile


# ── 预定义 Topic ─────────────────────────────────────────────────────────────


class Topics:
    """预定义事件主题"""
    # 测试生命周期
    TEST_STARTED = "test.started"
    TEST_COMPLETED = "test.completed"
    TEST_FAILED = "test.failed"
    TEST_CANCELLED = "test.cancelled"

    # 任务分发
    TASK_DISPATCHED = "task.dispatched"
    TASK_ACCEPTED = "task.accepted"

    # 异常与告警
    ANOMALY_FOUND = "anomaly.found"
    CRITICAL_FAILURE = "critical.failure"

    # 编排
    MISSION_STARTED = "mission.started"
    MISSION_COMPLETED = "mission.completed"
    MISSION_PROGRESS = "mission.progress"

    # 系统
    AGENT_REGISTERED = "agent.registered"
    AGENT_UNREGISTERED = "agent.unregistered"


# ── 回调类型别名 ─────────────────────────────────────────────────────────────

SubscriberCallback = Callable[[AgentMessage], Coroutine[Any, Any, None]]


# ── AgentBus 核心 ────────────────────────────────────────────────────────────


class AgentBus:
    """
    跨 Agent 通信总线

    功能：
    1. Agent 注册表（谁在线、擅长什么）
    2. 发布/订阅（广播事件）
    3. 请求/响应（定向任务）
    4. 消息日志（审计追踪）
    """

    def __init__(self):
        # Agent 注册表
        self._agents: Dict[str, AgentRegistration] = {}

        # 订阅表：topic -> [callback]
        self._subscribers: Dict[str, List[SubscriberCallback]] = {}

        # 等待中的请求：correlation_id -> Future
        self._pending_requests: Dict[str, asyncio.Future] = {}

        # 消息日志（最近 N 条）
        self._message_log: List[Dict] = []
        self._max_log_size = 500

        logger.info("[AgentBus] 初始化完成")

    # ── Agent 注册 ────────────────────────────────────────────────────────

    def register_agent(
        self,
        agent_name: str,
        agent_type: str,
        supported_test_types: Optional[List[str]] = None,
        description: str = "",
        profile_id: str = "",
    ) -> AgentRegistration:
        """注册 Agent 到总线（支持关联 Profile）"""
        reg = AgentRegistration(
            agent_name=agent_name,
            agent_type=agent_type,
            supported_test_types=supported_test_types or [],
            description=description,
            profile_id=profile_id,
        )
        self._agents[agent_name] = reg
        logger.info(f"[AgentBus] Agent 注册: {agent_name} ({agent_type})")

        # 广播注册事件
        try:
            asyncio.ensure_future(self.publish(AgentMessage(
                topic=Topics.AGENT_REGISTERED,
                sender="agent_bus",
                payload={"agent_name": agent_name, "agent_type": agent_type, "profile_id": profile_id},
            )))
        except RuntimeError:
            pass  # 无事件循环时静默（启动阶段）
        return reg

    def unregister_agent(self, agent_name: str) -> bool:
        """注销 Agent"""
        if agent_name in self._agents:
            self._agents[agent_name].is_active = False
            del self._agents[agent_name]
            logger.info(f"[AgentBus] Agent 注销: {agent_name}")
            return True
        return False

    def get_agent(self, agent_name: str) -> Optional[AgentRegistration]:
        """获取 Agent 注册信息"""
        return self._agents.get(agent_name)

    def get_agents_by_type(self, agent_type: str) -> List[AgentRegistration]:
        """按类型查找 Agent"""
        return [a for a in self._agents.values() if a.agent_type == agent_type and a.is_active]

    def get_agent_for_test_type(self, test_type: str) -> Optional[AgentRegistration]:
        """找到能处理指定测试类型的 Agent"""
        for agent in self._agents.values():
            if agent.is_active and test_type in agent.supported_test_types:
                return agent
        return None

    def list_agents(self) -> List[Dict]:
        """列出所有在线 Agent"""
        return [
            {
                "name": a.agent_name,
                "type": a.agent_type,
                "test_types": a.supported_test_types,
                "active": a.is_active,
            }
            for a in self._agents.values()
        ]

    # ── 发布/订阅 ────────────────────────────────────────────────────────

    def subscribe(self, topic: str, callback: SubscriberCallback) -> None:
        """订阅事件主题"""
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(callback)
        logger.debug(f"[AgentBus] 订阅: {topic} (共 {len(self._subscribers[topic])} 个)")

    def unsubscribe(self, topic: str, callback: SubscriberCallback) -> None:
        """取消订阅"""
        if topic in self._subscribers and callback in self._subscribers[topic]:
            self._subscribers[topic].remove(callback)

    async def publish(self, message: AgentMessage) -> None:
        """发布事件到所有订阅者"""
        self._log_message(message)

        callbacks = self._subscribers.get(message.topic, [])
        if not callbacks:
            return

        # 并行通知所有订阅者
        tasks = []
        for cb in callbacks:
            tasks.append(self._safe_call(cb, message))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_call(self, callback: SubscriberCallback, message: AgentMessage) -> None:
        """安全调用回调，捕获异常"""
        try:
            await callback(message)
        except Exception as e:
            logger.error(f"[AgentBus] 订阅回调异常: {e}", exc_info=True)

    # ── 请求/响应 ─────────────────────────────────────────────────────────

    async def request(
        self,
        receiver: str,
        payload: Dict[str, Any],
        sender: str = "commander",
        timeout: float = 300.0,
    ) -> Optional[Dict[str, Any]]:
        """
        向指定 Agent 发送任务请求并等待响应。

        Args:
            receiver: 目标 Agent 名称
            payload: 任务参数
            sender: 发送方名称
            timeout: 超时时间（秒）

        Returns:
            响应 payload，超时返回 None
        """
        correlation_id = str(uuid.uuid4())[:12]
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_requests[correlation_id] = future

        # 发送请求消息
        request_msg = AgentMessage(
            msg_type=MessageType.REQUEST,
            topic=Topics.TASK_DISPATCHED,
            sender=sender,
            receiver=receiver,
            payload=payload,
            correlation_id=correlation_id,
        )
        await self.publish(request_msg)

        # 等待响应
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"[AgentBus] 请求超时: {receiver} (correlation={correlation_id})")
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
        响应一个请求。

        Args:
            correlation_id: 关联 ID（与请求一致）
            payload: 响应数据
            sender: 响应方名称
        """
        # 通过 Future 直接唤醒等待方
        future = self._pending_requests.get(correlation_id)
        if future and not future.done():
            future.set_result(payload)

        # 同时发布响应事件（供审计/追踪）
        response_msg = AgentMessage(
            msg_type=MessageType.RESPONSE,
            topic=Topics.TEST_COMPLETED,
            sender=sender,
            correlation_id=correlation_id,
            payload=payload,
        )
        self._log_message(response_msg)

    # ── 批量分发与收集 ────────────────────────────────────────────────────

    async def dispatch_and_collect(
        self,
        tasks: List[Dict[str, Any]],
        parallel: bool = True,
        timeout: float = 600.0,
    ) -> List[Dict[str, Any]]:
        """
        批量分发任务到对应 Agent 并收集结果。

        Args:
            tasks: 任务列表，每个任务需包含 "test_type" 和 "config"
            parallel: 是否并行执行
            timeout: 单任务超时

        Returns:
            结果列表
        """
        results = []

        if parallel:
            # 并行分发
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
                    logger.warning(f"[AgentBus] 没有 Agent 能处理: {test_type}")
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
            # 串行执行
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

    # ── Agent 间任务交接（Handoff）────────────────────────────────────────

    async def handoff(
        self,
        sender: str,
        receiver: str,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Agent 间任务交接（携带上下文）。

        类似 OpenClaw 的 agentToAgent handoff。
        sender 将任务连同上下文一起转交给 receiver。

        Args:
            sender: 交接方 Agent
            receiver: 接收方 Agent
            task: 任务数据
            context: 上下文（前置 Agent 的执行结果等）

        Returns:
            接收方的执行结果
        """
        handoff_payload = {
            "handoff_from": sender,
            "task": task,
            "context": context or {},
        }

        # 记录 handoff 消息
        handoff_msg = AgentMessage(
            msg_type=MessageType.HANDOFF,
            topic="agent.handoff",
            sender=sender,
            receiver=receiver,
            payload=handoff_payload,
        )
        self._log_message(handoff_msg)
        logger.info(f"[AgentBus] Handoff: {sender} → {receiver}")

        # 通过 request 机制转发
        return await self.request(
            receiver=receiver,
            payload=handoff_payload,
            sender=sender,
            timeout=task.get("timeout", 300),
        )

    # ── 心跳 & 健康检查 ───────────────────────────────────────────────────

    def heartbeat(self, agent_name: str) -> bool:
        """Agent 心跳上报"""
        agent = self._agents.get(agent_name)
        if agent:
            agent.last_heartbeat = time.time()
            agent.is_active = True
            return True
        return False

    def get_health(self, timeout_threshold: float = 120.0) -> List[Dict]:
        """获取所有 Agent 的健康状态"""
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

    # ── 按测试类型广播 ────────────────────────────────────────────────────

    async def broadcast_by_type(
        self,
        test_types: List[str],
        message: Dict[str, Any],
        sender: str = "commander",
    ) -> None:
        """向所有能处理指定测试类型的 Agent 广播消息"""
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

    # ── 消息日志 ──────────────────────────────────────────────────────────

    def _log_message(self, message: AgentMessage) -> None:
        """记录消息到内存日志"""
        entry = message.to_dict()
        entry["logged_at"] = datetime.now().isoformat()
        self._message_log.append(entry)

        # 限制日志大小
        if len(self._message_log) > self._max_log_size:
            self._message_log = self._message_log[-self._max_log_size:]

    def get_message_log(self, limit: int = 50, topic: Optional[str] = None) -> List[Dict]:
        """获取消息日志"""
        logs = self._message_log
        if topic:
            logs = [m for m in logs if m.get("topic") == topic]
        return logs[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """获取通信统计"""
        return {
            "registered_agents": len(self._agents),
            "active_agents": sum(1 for a in self._agents.values() if a.is_active),
            "subscriptions": {t: len(cbs) for t, cbs in self._subscribers.items()},
            "pending_requests": len(self._pending_requests),
            "message_log_size": len(self._message_log),
        }


# ── 单例 ─────────────────────────────────────────────────────────────────────

_agent_bus: Optional[AgentBus] = None


def get_agent_bus() -> AgentBus:
    """获取 AgentBus 单例"""
    global _agent_bus
    if _agent_bus is None:
        _agent_bus = AgentBus()
    return _agent_bus
