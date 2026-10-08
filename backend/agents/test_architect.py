# -*- coding: utf-8 -*-
"""
TestArchitect — strategic test architect

Responsibility: decide what to test, upstream of Commander.

Five test-discovery modes:
    1. Requirement-driven: PRD document → RequirementParser → test needs
    2. Change-driven: Git diff → AcceptanceEngine → impact assessment
    3. Exploration-driven: ExploratoryAgent + ScoutAgent → autonomous discovery
    4. Coverage-driven: analyze existing test reports → find gaps
    5. Fault-driven: alert → RCAAgent → regression cases

Key objective: activate AcceptanceEngine (295 lines, no references) and ExploratoryAgent (561 lines, no route).
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Data structures ──────────────────────────────────────────────────────────────────


class DiscoveryMode(Enum):
    """Test-discovery modes"""
    REQUIREMENT = "requirement"   # Requirement-driven
    CHANGE = "change"             # Change-driven
    EXPLORATION = "exploration"   # Exploration-driven
    COVERAGE = "coverage"         # Coverage-driven
    FAULT = "fault"               # Fault-driven


@dataclass
class TestNeed:
    """A test need"""
    title: str
    description: str
    source: DiscoveryMode
    priority: str = "medium"      # critical / high / medium / low
    target_url: str = ""
    test_types: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ArchitectPlan:
    """Test plan produced by the architect"""
    plan_id: str = ""
    discovery_mode: DiscoveryMode = DiscoveryMode.REQUIREMENT
    test_needs: List[TestNeed] = field(default_factory=list)
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "discovery_mode": self.discovery_mode.value,
            "test_needs": [
                {
                    "title": n.title,
                    "description": n.description,
                    "source": n.source.value,
                    "priority": n.priority,
                    "target_url": n.target_url,
                    "test_types": n.test_types,
                }
                for n in self.test_needs
            ],
            "summary": self.summary,
            "created_at": self.created_at,
        }


# ── TestArchitect core ───────────────────────────────────────────────────────


class TestArchitect:
    """
    Test architect — strategic layer

    Answers the question of what to test:
    - Analyze input → choose a discovery mode → generate test needs
    - Pass the output to Commander for execution
    """

    def __init__(self):
        logger.info("[TestArchitect] Initialization complete")

    # ── Unified entry point ──────────────────────────────────────────────────────────

    async def analyze(
        self,
        input_text: str = "",
        target_url: str = "",
        mode: Optional[str] = None,
        diff_text: str = "",
        alert_data: Optional[Dict] = None,
    ) -> ArchitectPlan:
        """
        Analyze the input and generate test needs.

        Args:
            input_text: User-provided requirement description or PRD
            target_url: Target URL
            mode: Discovery mode; infer automatically when omitted
            diff_text: Git diff text for change-driven discovery
            alert_data: Alert data for fault-driven discovery

        Returns:
            ArchitectPlan: Test plan
        """
        import uuid
        plan = ArchitectPlan(plan_id=str(uuid.uuid4())[:8])

        # Infer the mode automatically
        if mode:
            plan.discovery_mode = DiscoveryMode(mode)
        else:
            plan.discovery_mode = self._infer_mode(
                input_text, diff_text, alert_data, target_url,
            )

        logger.info(f"[TestArchitect] Discovery mode: {plan.discovery_mode.value}")

        # Dispatch according to the mode
        if plan.discovery_mode == DiscoveryMode.REQUIREMENT:
            plan.test_needs = await self._discover_from_requirement(input_text)
        elif plan.discovery_mode == DiscoveryMode.CHANGE:
            plan.test_needs = await self._discover_from_change(diff_text, input_text)
        elif plan.discovery_mode == DiscoveryMode.EXPLORATION:
            plan.test_needs = await self._discover_from_exploration(target_url)
        elif plan.discovery_mode == DiscoveryMode.COVERAGE:
            plan.test_needs = await self._discover_from_coverage(input_text)
        elif plan.discovery_mode == DiscoveryMode.FAULT:
            plan.test_needs = await self._discover_from_fault(alert_data or {})

        plan.summary = f"Discovered {len(plan.test_needs)} test needs ({plan.discovery_mode.value} mode)"
        logger.info(f"[TestArchitect] {plan.summary}")

        return plan

    # ── Mode inference ──────────────────────────────────────────────────────────

    def _infer_mode(
        self,
        input_text: str,
        diff_text: str,
        alert_data: Optional[Dict],
        target_url: str,
    ) -> DiscoveryMode:
        """Infer the discovery mode automatically"""
        if diff_text:
            return DiscoveryMode.CHANGE
        if alert_data:
            return DiscoveryMode.FAULT
        if target_url and not input_text:
            return DiscoveryMode.EXPLORATION
        if any(kw in input_text.lower() for kw in ["覆盖", "盲区", "coverage", "gap"]):
            return DiscoveryMode.COVERAGE
        return DiscoveryMode.REQUIREMENT

    # ── Discovery-mode implementations ────────────────────────────────────────────────────

    async def _discover_from_requirement(self, input_text: str) -> List[TestNeed]:
        """Requirement-driven: PRD → RequirementParser → TestNeeds"""
        from core.requirement_parser import get_requirement_parser
        import json

        parser = get_requirement_parser()
        parsed = parser.parse_text(input_text)
        parsed_str = parser.to_json(parsed)
        parsed_json = json.loads(parsed_str) if isinstance(parsed_str, str) else parsed_str

        needs = []
        for case in parsed_json.get("test_cases", []):
            needs.append(TestNeed(
                title=case.get("title", ""),
                description=case.get("description", ""),
                source=DiscoveryMode.REQUIREMENT,
                priority=case.get("priority", "medium"),
                test_types=[case.get("test_type", "ui_e2e")],
            ))

        # Generate at least one input-based need if the parser extracts no cases
        if not needs:
            needs.append(TestNeed(
                title=input_text[:80],
                description=input_text,
                source=DiscoveryMode.REQUIREMENT,
                priority="medium",
                test_types=["ui_e2e"],
            ))

        return needs

    async def _discover_from_change(self, diff_text: str, input_text: str = "") -> List[TestNeed]:
        """Change-driven: Git diff → AcceptanceEngine → impact assessment → TestNeeds"""
        from core.acceptance_engine import get_acceptance_engine

        engine = get_acceptance_engine()
        impact = engine.analyze_change_impact(diff_text=diff_text)

        needs = []

        # Add an API test need when APIs change
        if impact.has_api_change:
            needs.append(TestNeed(
                title="API change regression test",
                description=f"API changes detected; affected modules: {', '.join(impact.modules_affected[:5])}",
                source=DiscoveryMode.CHANGE,
                priority="high",
                test_types=["api_rest"],
                metadata={"impact_score": impact.impact_score},
            ))

        # Add database tests when the schema changes
        if impact.has_schema_change:
            needs.append(TestNeed(
                title="Database schema change validation",
                description="Database schema changes detected; data integrity must be validated",
                source=DiscoveryMode.CHANGE,
                priority="critical",
                test_types=["database"],
            ))

        # Add configuration validation when configuration changes
        if impact.has_config_change:
            needs.append(TestNeed(
                title="Configuration change validation",
                description="Configuration changes detected; system behavior must be validated",
                source=DiscoveryMode.CHANGE,
                priority="high",
                test_types=["ui_e2e", "api_rest"],
            ))

        # General regression based on changed files
        if impact.files_changed:
            needs.append(TestNeed(
                title=f"Change regression test ({len(impact.files_changed)} files)",
                description=f"Changed files: {', '.join(impact.files_changed[:5])}",
                source=DiscoveryMode.CHANGE,
                priority="medium",
                test_types=["ui_e2e"],
                metadata={"files": impact.files_changed[:10]},
            ))

        return needs

    async def _discover_from_exploration(self, target_url: str) -> List[TestNeed]:
        """Exploration-driven: Scout + Exploratory → autonomous discovery"""
        needs = []

        # Run ScoutAgent reconnaissance first
        try:
            from agents.scout_agent import ScoutAgent

            scout_result = await ScoutAgent.scout(target_url)

            if scout_result.get("status") == "success":
                needs.append(TestNeed(
                    title=f"Exploratory test: {scout_result.get('title', target_url)}",
                    description=(
                        f"Page reconnaissance results: {scout_result.get('visible_text', '')[:200]}\n"
                        f"Interactive elements: {scout_result.get('interactive_summary', '')[:200]}"
                    ),
                    source=DiscoveryMode.EXPLORATION,
                    priority="medium",
                    target_url=target_url,
                    test_types=["ui_e2e", "accessibility"],
                    metadata={"scout_result": scout_result},
                ))
        except Exception as e:
            logger.warning(f"[TestArchitect] Scout reconnaissance failed: {e}")
            needs.append(TestNeed(
                title=f"Basic test: {target_url}",
                description=f"Scout reconnaissance failed ({e}); run a basic UI test",
                source=DiscoveryMode.EXPLORATION,
                priority="medium",
                target_url=target_url,
                test_types=["ui_e2e"],
            ))

        return needs

    async def _discover_from_coverage(self, input_text: str) -> List[TestNeed]:
        """Coverage-driven: analyze existing test reports → find gaps"""
        needs = []

        # Query prior test results to find untested or frequently failing areas
        from core.tracing import get_tracer
        recent = get_tracer().get_recent_spans(limit=50)

        # Count how often each agent is called
        agent_counts: Dict[str, int] = {}
        for span in recent:
            agent = span.get("agent_name", "")
            agent_counts[agent] = agent_counts.get(agent, 0) + 1

        # Find test types without coverage
        all_types = {"ui_e2e", "api_rest", "security", "performance", "database", "accessibility"}
        covered = set()
        for span in recent:
            action = span.get("action", "")
            for t in all_types:
                if t in action:
                    covered.add(t)

        uncovered = all_types - covered
        if uncovered:
            needs.append(TestNeed(
                title=f"Coverage gaps: {', '.join(uncovered)}",
                description=f"These test types have not run recently: {', '.join(uncovered)}",
                source=DiscoveryMode.COVERAGE,
                priority="medium",
                test_types=list(uncovered),
            ))

        if not needs:
            needs.append(TestNeed(
                title="Good coverage",
                description="All test types have run recently",
                source=DiscoveryMode.COVERAGE,
                priority="low",
                test_types=[],
            ))

        return needs

    async def _discover_from_fault(self, alert_data: Dict) -> List[TestNeed]:
        """Fault-driven: alert → generate targeted regression cases"""
        needs = []

        error_msg = alert_data.get("error", "")
        url = alert_data.get("url", "")
        component = alert_data.get("component", "")

        needs.append(TestNeed(
            title=f"Fault regression: {component or error_msg[:50]}",
            description=f"Alert: {error_msg}\nComponent: {component}\nURL: {url}",
            source=DiscoveryMode.FAULT,
            priority="critical",
            target_url=url,
            test_types=["ui_e2e", "api_rest"],
            metadata={"alert": alert_data},
        ))

        return needs


# ── Singleton ─────────────────────────────────────────────────────────────────────

_architect: Optional[TestArchitect] = None


def get_test_architect() -> TestArchitect:
    """Get the TestArchitect singleton"""
    global _architect
    if _architect is None:
        _architect = TestArchitect()
    return _architect
