# -*- coding: utf-8 -*-
"""
测试智能体军团 — 单元测试

测试模块：
- core/agent_bus.py
- core/tracing.py
- core/notify_gateway.py
- agents/commander.py
- agents/test_architect.py
"""

import asyncio
import pytest
import sys
import os

# 确保导入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── AgentBus 测试 ────────────────────────────────────────────────────────────


class TestAgentBus:
    """AgentBus 通信总线测试"""

    def test_import(self):
        """测试模块可正常导入"""
        from core.agent_bus import AgentBus, AgentMessage, Topics, get_agent_bus
        bus = get_agent_bus()
        assert isinstance(bus, AgentBus)

    def test_register_agent(self):
        """测试 Agent 注册"""
        from core.agent_bus import AgentBus

        bus = AgentBus()
        reg = bus.register_agent(
            agent_name="test_ui",
            agent_type="ui_tester",
            supported_test_types=["ui_e2e"],
            description="UI 测试 Agent",
        )
        assert reg.agent_name == "test_ui"
        assert reg.agent_type == "ui_tester"
        assert reg.is_active is True

    def test_list_agents(self):
        """测试 Agent 列表"""
        from core.agent_bus import AgentBus

        bus = AgentBus()
        bus.register_agent("a1", "type_a", ["t1"])
        bus.register_agent("a2", "type_b", ["t2"])

        agents = bus.list_agents()
        assert len(agents) == 2
        names = [a["name"] for a in agents]
        assert "a1" in names
        assert "a2" in names

    def test_find_agent_by_type(self):
        """测试按类型查找 Agent"""
        from core.agent_bus import AgentBus

        bus = AgentBus()
        bus.register_agent("sec1", "security", ["security"])
        result = bus.get_agents_by_type("security")
        assert len(result) == 1
        assert result[0].agent_name == "sec1"

    def test_find_agent_for_test_type(self):
        """测试按测试类型查找 Agent"""
        from core.agent_bus import AgentBus

        bus = AgentBus()
        bus.register_agent("ui1", "ui_tester", ["ui_e2e"])
        bus.register_agent("api1", "api_tester", ["api_rest", "api_graphql"])

        agent = bus.get_agent_for_test_type("api_rest")
        assert agent is not None
        assert agent.agent_name == "api1"

    def test_unregister_agent(self):
        """测试 Agent 注销"""
        from core.agent_bus import AgentBus

        bus = AgentBus()
        bus.register_agent("temp", "temp", [])
        assert len(bus.list_agents()) == 1

        result = bus.unregister_agent("temp")
        assert result is True
        assert len(bus.list_agents()) == 0

    @pytest.mark.asyncio
    async def test_publish_subscribe(self):
        """测试发布/订阅"""
        from core.agent_bus import AgentBus, AgentMessage

        bus = AgentBus()
        received = []

        async def handler(msg: AgentMessage):
            received.append(msg)

        bus.subscribe("test.event", handler)

        await bus.publish(AgentMessage(
            topic="test.event",
            sender="test",
            payload={"data": "hello"},
        ))

        assert len(received) == 1
        assert received[0].payload["data"] == "hello"

    @pytest.mark.asyncio
    async def test_request_respond(self):
        """测试请求/响应"""
        from core.agent_bus import AgentBus, AgentMessage, Topics

        bus = AgentBus()

        # 模拟 Agent 自动响应
        async def auto_responder(msg: AgentMessage):
            if msg.correlation_id:
                await bus.respond(
                    correlation_id=msg.correlation_id,
                    payload={"result": "ok", "test_type": "mock"},
                    sender="mock_agent",
                )

        bus.subscribe(Topics.TASK_DISPATCHED, auto_responder)

        result = await bus.request(
            receiver="mock_agent",
            payload={"task": "test"},
            timeout=5.0,
        )

        assert result is not None
        assert result["result"] == "ok"

    def test_statistics(self):
        """测试统计信息"""
        from core.agent_bus import AgentBus

        bus = AgentBus()
        bus.register_agent("a1", "type_a")
        stats = bus.get_statistics()
        assert stats["registered_agents"] == 1
        assert stats["active_agents"] == 1


# ── Tracing 测试 ─────────────────────────────────────────────────────────────


class TestTracing:
    """Tracing 链路追踪测试"""

    def test_import(self):
        """测试模块可正常导入"""
        from core.tracing import Tracer, TraceSpan, get_tracer
        tracer = get_tracer()
        assert isinstance(tracer, Tracer)

    def test_start_end_trace(self):
        """测试 trace 生命周期"""
        from core.tracing import Tracer

        tracer = Tracer()
        tid = tracer.start_trace()
        assert tid is not None
        assert tracer.current_trace_id == tid

        ended = tracer.end_trace()
        assert ended == tid
        assert tracer.current_trace_id is None

    def test_span_context_manager(self):
        """测试 span 上下文管理器"""
        from core.tracing import Tracer

        tracer = Tracer()
        tracer.start_trace("test-trace-001")

        with tracer.span("planner", "generate_plan", "deepseek-chat") as s:
            s.input_tokens = 100
            s.output_tokens = 200

        assert s.total_tokens == 300
        assert s.duration_ms >= 0  # 空操作可能是 0.0 毫秒

        tracer.end_trace()

    def test_record_span(self):
        """测试直接记录 span"""
        from core.tracing import Tracer, TraceSpan

        tracer = Tracer()
        span = TraceSpan(
            trace_id="t-001",
            agent_name="commander",
            action="dispatch",
            input_tokens=50,
            output_tokens=100,
            total_tokens=150,
            duration_ms=250.0,
        )
        tracer.record(span)

        spans = tracer.get_trace_spans("t-001")
        assert len(spans) >= 1

    def test_trace_summary(self):
        """测试 trace 统计摘要"""
        from core.tracing import Tracer
        tracer = Tracer()
        summary = tracer.get_trace_summary()
        assert "total_calls" in summary
        assert "total_cost_usd" in summary

    def test_cost_estimate(self):
        """测试成本估算"""
        from core.tracing import _estimate_cost

        cost = _estimate_cost("deepseek-chat", 1000, 2000)
        assert cost > 0
        assert cost < 0.01  # deepseek 很便宜


# ── NotifyGateway 测试 ───────────────────────────────────────────────────────


class TestNotifyGateway:
    """NotifyGateway 通知网关测试"""

    def test_import(self):
        """测试模块可正常导入"""
        from core.notify_gateway import NotifyGateway, get_notify_gateway
        gw = get_notify_gateway()
        assert isinstance(gw, NotifyGateway)

    @pytest.mark.asyncio
    async def test_send_info(self):
        """测试发送 INFO 通知"""
        from core.notify_gateway import NotifyGateway

        gw = NotifyGateway()
        notification = await gw.send(
            level="info",
            title="测试完成",
            body="3/3 通过",
        )
        assert "console" in notification.channels_sent

    @pytest.mark.asyncio
    async def test_send_critical(self):
        """测试发送 CRITICAL 通知"""
        from core.notify_gateway import NotifyGateway

        gw = NotifyGateway()
        notification = await gw.send(
            level="critical",
            title="核心接口崩溃",
            body="API /login 返回 500",
        )
        assert "console" in notification.channels_sent

    def test_history(self):
        """测试通知历史"""
        from core.notify_gateway import NotifyGateway

        gw = NotifyGateway()
        history = gw.get_history()
        assert isinstance(history, list)


# ── Commander 测试 ───────────────────────────────────────────────────────────


class TestCommander:
    """Commander 总指挥测试"""

    def test_import(self):
        """测试模块可正常导入"""
        from agents.commander import Commander, Mission, MissionStatus, get_commander
        commander = get_commander()
        assert isinstance(commander, Commander)

    def test_mission_creation(self):
        """测试 Mission 创建"""
        from agents.commander import Mission, MissionStatus

        m = Mission(user_input="测试淘宝登录")
        assert m.user_input == "测试淘宝登录"
        assert m.status == MissionStatus.PENDING
        assert m.mission_id  # 自动生成

    def test_mission_to_dict(self):
        """测试 Mission 序列化"""
        from agents.commander import Mission

        m = Mission(user_input="test")
        d = m.to_dict()
        assert "mission_id" in d
        assert d["status"] == "pending"

    def test_mission_log(self):
        """测试 Mission 日志"""
        from agents.commander import Mission

        m = Mission(user_input="test")
        m.log("测试开始")
        m.log("测试完成", level="info", data={"count": 3})
        assert len(m.logs) == 2

    def test_list_missions(self):
        """测试任务列表"""
        from agents.commander import Commander

        cmd = Commander()
        missions = cmd.list_missions()
        assert isinstance(missions, list)

    def test_cancel_nonexistent(self):
        """测试取消不存在的任务"""
        from agents.commander import Commander

        cmd = Commander()
        result = cmd.cancel_mission("nonexistent")
        assert result is False


# ── TestArchitect 测试 ───────────────────────────────────────────────────────


class TestTestArchitect:
    """TestArchitect 测试架构师测试"""

    def test_import(self):
        """测试模块可正常导入"""
        from agents.test_architect import TestArchitect, DiscoveryMode, get_test_architect
        arch = get_test_architect()
        assert isinstance(arch, TestArchitect)

    def test_infer_mode_diff(self):
        """测试模式推断 — 变更驱动"""
        from agents.test_architect import TestArchitect

        arch = TestArchitect()
        mode = arch._infer_mode("", "diff --git ...", None, "")
        assert mode.value == "change"

    def test_infer_mode_fault(self):
        """测试模式推断 — 故障驱动"""
        from agents.test_architect import TestArchitect

        arch = TestArchitect()
        mode = arch._infer_mode("", "", {"error": "500"}, "")
        assert mode.value == "fault"

    def test_infer_mode_exploration(self):
        """测试模式推断 — 探索驱动"""
        from agents.test_architect import TestArchitect

        arch = TestArchitect()
        mode = arch._infer_mode("", "", None, "https://example.com")
        assert mode.value == "exploration"

    def test_infer_mode_coverage(self):
        """测试模式推断 — 覆盖驱动"""
        from agents.test_architect import TestArchitect

        arch = TestArchitect()
        mode = arch._infer_mode("分析覆盖盲区", "", None, "")
        assert mode.value == "coverage"

    def test_infer_mode_requirement(self):
        """测试模式推断 — 需求驱动（默认）"""
        from agents.test_architect import TestArchitect

        arch = TestArchitect()
        mode = arch._infer_mode("全面测试淘宝登录", "", None, "")
        assert mode.value == "requirement"

    @pytest.mark.asyncio
    async def test_analyze_requirement(self):
        """测试需求驱动分析"""
        from agents.test_architect import TestArchitect

        arch = TestArchitect()
        plan = await arch.analyze(input_text="用户登录功能需要验证用户名和密码")
        assert plan.discovery_mode.value == "requirement"
        assert len(plan.test_needs) > 0

    @pytest.mark.asyncio
    async def test_analyze_change(self):
        """测试变更驱动分析"""
        from agents.test_architect import TestArchitect

        arch = TestArchitect()
        plan = await arch.analyze(
            diff_text="diff --git a/api/login.py b/api/login.py\n+new code",
        )
        assert plan.discovery_mode.value == "change"

    @pytest.mark.asyncio
    async def test_analyze_fault(self):
        """测试故障驱动分析"""
        from agents.test_architect import TestArchitect

        arch = TestArchitect()
        plan = await arch.analyze(
            alert_data={"error": "500 Internal Server Error", "component": "auth"},
        )
        assert plan.discovery_mode.value == "fault"
        assert len(plan.test_needs) > 0


# ── 路由测试 ─────────────────────────────────────────────────────────────────


class TestRouterRegistration:
    """路由注册验证"""

    def test_commander_routes_registered(self):
        """验证 Commander 路由已注册"""
        from main import app

        routes = [r.path for r in app.routes if hasattr(r, "path")]
        expected = [
            "/api/commander/run",
            "/api/commander/status/{mission_id}",
            "/api/commander/cancel",
            "/api/commander/missions",
            "/api/commander/stream/{mission_id}",
            "/api/commander/architect",
            "/api/commander/agents",
            "/api/commander/tracing",
        ]
        for route in expected:
            assert route in routes, f"Missing route: {route}"

    def test_total_routes_reasonable(self):
        """验证总路由数合理"""
        from main import app

        routes = [r for r in app.routes if hasattr(r, "path")]
        assert len(routes) > 100  # 之前已有 ~166 条
