# -*- coding: utf-8 -*-
"""
Agent fleet unit tests

Modules under test:
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

# Ensure the import path is available.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# AgentBus tests


class TestAgentBus:
    """AgentBus communication bus tests."""

    def test_import(self):
        """Test that the module imports successfully."""
        from core.agent_bus import AgentBus, AgentMessage, Topics, get_agent_bus
        bus = get_agent_bus()
        assert isinstance(bus, AgentBus)

    def test_register_agent(self):
        """Test agent registration."""
        from core.agent_bus import AgentBus

        bus = AgentBus()
        reg = bus.register_agent(
            agent_name="test_ui",
            agent_type="ui_tester",
            supported_test_types=["ui_e2e"],
            description="UI test agent",
        )
        assert reg.agent_name == "test_ui"
        assert reg.agent_type == "ui_tester"
        assert reg.is_active is True

    def test_list_agents(self):
        """Test the agent list."""
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
        """Test finding agents by type."""
        from core.agent_bus import AgentBus

        bus = AgentBus()
        bus.register_agent("sec1", "security", ["security"])
        result = bus.get_agents_by_type("security")
        assert len(result) == 1
        assert result[0].agent_name == "sec1"

    def test_find_agent_for_test_type(self):
        """Test finding agents by test type."""
        from core.agent_bus import AgentBus

        bus = AgentBus()
        bus.register_agent("ui1", "ui_tester", ["ui_e2e"])
        bus.register_agent("api1", "api_tester", ["api_rest", "api_graphql"])

        agent = bus.get_agent_for_test_type("api_rest")
        assert agent is not None
        assert agent.agent_name == "api1"

    def test_unregister_agent(self):
        """Test agent unregistration."""
        from core.agent_bus import AgentBus

        bus = AgentBus()
        bus.register_agent("temp", "temp", [])
        assert len(bus.list_agents()) == 1

        result = bus.unregister_agent("temp")
        assert result is True
        assert len(bus.list_agents()) == 0

    @pytest.mark.asyncio
    async def test_publish_subscribe(self):
        """Test publish/subscribe."""
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
        """Test request/response."""
        from core.agent_bus import AgentBus, AgentMessage, Topics

        bus = AgentBus()

        # Simulate an automatic agent response.
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
        """Test statistics."""
        from core.agent_bus import AgentBus

        bus = AgentBus()
        bus.register_agent("a1", "type_a")
        stats = bus.get_statistics()
        assert stats["registered_agents"] == 1
        assert stats["active_agents"] == 1


# Tracing tests


class TestTracing:
    """Distributed tracing tests."""

    def test_import(self):
        """Test that the module imports successfully."""
        from core.tracing import Tracer, TraceSpan, get_tracer
        tracer = get_tracer()
        assert isinstance(tracer, Tracer)

    def test_start_end_trace(self):
        """Test the trace lifecycle."""
        from core.tracing import Tracer

        tracer = Tracer()
        tid = tracer.start_trace()
        assert tid is not None
        assert tracer.current_trace_id == tid

        ended = tracer.end_trace()
        assert ended == tid
        assert tracer.current_trace_id is None

    def test_span_context_manager(self):
        """Test the span context manager."""
        from core.tracing import Tracer

        tracer = Tracer()
        tracer.start_trace("test-trace-001")

        with tracer.span("planner", "generate_plan", "deepseek-chat") as s:
            s.input_tokens = 100
            s.output_tokens = 200

        assert s.total_tokens == 300
        assert s.duration_ms >= 0  # An empty operation may take 0.0 milliseconds.

        tracer.end_trace()

    def test_record_span(self):
        """Test recording a span directly."""
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
        """Test the trace statistics summary."""
        from core.tracing import Tracer
        tracer = Tracer()
        summary = tracer.get_trace_summary()
        assert "total_calls" in summary
        assert "total_cost_usd" in summary

    def test_cost_estimate(self):
        """Test cost estimation."""
        from core.tracing import _estimate_cost

        cost = _estimate_cost("deepseek-chat", 1000, 2000)
        assert cost > 0
        assert cost < 0.01  # DeepSeek has a low rate in this pricing fixture.


# NotifyGateway tests


class TestNotifyGateway:
    """NotifyGateway notification gateway tests."""

    def test_import(self):
        """Test that the module imports successfully."""
        from core.notify_gateway import NotifyGateway, get_notify_gateway
        gw = get_notify_gateway()
        assert isinstance(gw, NotifyGateway)

    @pytest.mark.asyncio
    async def test_send_info(self):
        """Test sending an INFO notification."""
        from core.notify_gateway import NotifyGateway

        gw = NotifyGateway()
        notification = await gw.send(
            level="info",
            title="Test complete",
            body="3/3 passed",
        )
        assert "console" in notification.channels_sent

    @pytest.mark.asyncio
    async def test_send_critical(self):
        """Test sending a CRITICAL notification."""
        from core.notify_gateway import NotifyGateway

        gw = NotifyGateway()
        notification = await gw.send(
            level="critical",
            title="Core API failure",
            body="API /login returned 500",
        )
        assert "console" in notification.channels_sent

    def test_history(self):
        """Test notification history."""
        from core.notify_gateway import NotifyGateway

        gw = NotifyGateway()
        history = gw.get_history()
        assert isinstance(history, list)


# Commander tests


class TestCommander:
    """Commander coordination tests."""

    def test_import(self):
        """Test that the module imports successfully."""
        from agents.commander import Commander, Mission, MissionStatus, get_commander
        commander = get_commander()
        assert isinstance(commander, Commander)

    def test_mission_creation(self):
        """Test mission creation."""
        from agents.commander import Mission, MissionStatus

        m = Mission(user_input="Test Taobao login")
        assert m.user_input == "Test Taobao login"
        assert m.status == MissionStatus.PENDING
        assert m.mission_id  # Automatically generated

    def test_mission_to_dict(self):
        """Test mission serialization."""
        from agents.commander import Mission

        m = Mission(user_input="test")
        d = m.to_dict()
        assert "mission_id" in d
        assert d["status"] == "pending"

    def test_mission_log(self):
        """Test mission logs."""
        from agents.commander import Mission

        m = Mission(user_input="test")
        m.log("Test started")
        m.log("Test complete", level="info", data={"count": 3})
        assert len(m.logs) == 2

    def test_list_missions(self):
        """Test the mission list."""
        from agents.commander import Commander

        cmd = Commander()
        missions = cmd.list_missions()
        assert isinstance(missions, list)

    def test_cancel_nonexistent(self):
        """Test canceling a nonexistent mission."""
        from agents.commander import Commander

        cmd = Commander()
        result = cmd.cancel_mission("nonexistent")
        assert result is False


# TestArchitect tests


class TestTestArchitect:
    """TestArchitect test design tests."""

    def test_import(self):
        """Test that the module imports successfully."""
        from agents.test_architect import TestArchitect, DiscoveryMode, get_test_architect
        arch = get_test_architect()
        assert isinstance(arch, TestArchitect)

    def test_infer_mode_diff(self):
        """Test mode inference: change-driven."""
        from agents.test_architect import TestArchitect

        arch = TestArchitect()
        mode = arch._infer_mode("", "diff --git ...", None, "")
        assert mode.value == "change"

    def test_infer_mode_fault(self):
        """Test mode inference: failure-driven."""
        from agents.test_architect import TestArchitect

        arch = TestArchitect()
        mode = arch._infer_mode("", "", {"error": "500"}, "")
        assert mode.value == "fault"

    def test_infer_mode_exploration(self):
        """Test mode inference: exploration-driven."""
        from agents.test_architect import TestArchitect

        arch = TestArchitect()
        mode = arch._infer_mode("", "", None, "https://example.com")
        assert mode.value == "exploration"

    def test_infer_mode_coverage(self):
        """Test mode inference: coverage-driven."""
        from agents.test_architect import TestArchitect

        arch = TestArchitect()
        mode = arch._infer_mode("分析覆盖盲区", "", None, "")
        assert mode.value == "coverage"

    def test_infer_mode_requirement(self):
        """Test mode inference: requirement-driven (default)."""
        from agents.test_architect import TestArchitect

        arch = TestArchitect()
        mode = arch._infer_mode("Comprehensively test Taobao login", "", None, "")
        assert mode.value == "requirement"

    @pytest.mark.asyncio
    async def test_analyze_requirement(self):
        """Test requirement-driven analysis."""
        from agents.test_architect import TestArchitect

        arch = TestArchitect()
        plan = await arch.analyze(input_text="User login must validate the username and password")
        assert plan.discovery_mode.value == "requirement"
        assert len(plan.test_needs) > 0

    @pytest.mark.asyncio
    async def test_analyze_change(self):
        """Test change-driven analysis."""
        from agents.test_architect import TestArchitect

        arch = TestArchitect()
        plan = await arch.analyze(
            diff_text="diff --git a/api/login.py b/api/login.py\n+new code",
        )
        assert plan.discovery_mode.value == "change"

    @pytest.mark.asyncio
    async def test_analyze_fault(self):
        """Test failure-driven analysis."""
        from agents.test_architect import TestArchitect

        arch = TestArchitect()
        plan = await arch.analyze(
            alert_data={"error": "500 Internal Server Error", "component": "auth"},
        )
        assert plan.discovery_mode.value == "fault"
        assert len(plan.test_needs) > 0


# Router tests


class TestRouterRegistration:
    """Verify router registration."""

    def test_commander_routes_registered(self):
        """Verify that Commander routes are registered."""
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
        """Verify that the total route count is reasonable."""
        from main import app

        routes = [r for r in app.routes if hasattr(r, "path")]
        assert len(routes) > 100  # There were approximately 166 existing routes.
