"""
Exploratory Test Agent

Enable autonomous AI exploration of applications:
- Automatically discover page elements
- Intelligent path exploration
- Anomaly detection
- Track coverage
"""

from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import hashlib
import inspect
import time
import re
import json
import logging
import random

from core.llm_manager import get_llm_for_role

logger = logging.getLogger(__name__)


class ActionType(Enum):
    CLICK = "click"
    INPUT = "input"
    SELECT = "select"
    NAVIGATE = "navigate"
    SCROLL = "scroll"
    HOVER = "hover"


@dataclass
class PageState:
    """Page state"""
    url: str
    title: str
    html_hash: str
    elements_count: int
    forms_count: int
    links_count: int


@dataclass
class ExplorationAction:
    """Exploration action"""
    action_type: ActionType
    target: str
    value: Optional[str] = None


@dataclass
class AnomalyFound:
    """Detected anomaly"""
    anomaly_type: str
    description: str
    url: str
    evidence: str
    severity: str


@dataclass
class ExplorationResult:
    """Exploration results"""
    total_states: int
    total_actions: int
    unique_urls: int
    anomalies: List[AnomalyFound]
    coverage: float
    duration_seconds: float


class ExploratoryTestAgent:
    """Exploratory test agent"""

    def __init__(self, browser=None, llm=None):
        self.browser = browser
        self.llm = llm

        self.visited_states: Set[str] = set()
        self.visited_urls: Set[str] = set()
        self.action_history: List[ExplorationAction] = []
        self.anomalies: List[AnomalyFound] = []

        # UI state-transition graph: {state_hash: {action_str: target_state_hash}}
        self.state_graph: Dict[str, Dict[str, str]] = {}
        self._current_state_hash: str = ""

        # Automatically generated regression cases
        self.regression_cases: List[Dict[str, Any]] = []

        # Anomaly detection patterns (enhanced)
        self.error_patterns = [
            (r"500\s*Internal Server Error", "server_error"),
            (r"404\s*Not Found", "not_found"),
            (r"403\s*Forbidden", "forbidden"),
            (r"Error|Exception|Traceback", "application_error"),
            (r"undefined|null reference|NaN", "javascript_error"),
            (r"SQLSTATE|SQL syntax", "database_error"),
            # Added in P1-7: performance, network, and console anomaly detection
            (r"Failed to load resource", "network_error"),
            (r"net::ERR_", "network_error"),
            (r"TypeError|ReferenceError|SyntaxError", "js_runtime_error"),
            (r"Loading\.{3,}|Spinner|skeleton", "slow_render"),
        ]

    async def _resolve_browser_attr(self, attr_name: str, *args, default=None, **kwargs):
        """Support raw and bridged pages, synchronous properties, and asynchronous methods."""
        if not self.browser:
            return default

        attr = getattr(self.browser, attr_name, None)
        if attr is None:
            return default

        try:
            value = attr(*args, **kwargs) if callable(attr) else attr
            if inspect.isawaitable(value):
                return await value
            return value
        except Exception:
            return default

    def _compute_state_hash(self, html: str, url: str) -> str:
        """Compute the page-state hash"""
        # Remove dynamic content
        normalized = re.sub(r'\d+', '', html)
        normalized = re.sub(r'[a-f0-9]{8,}', '', normalized)
        content = f"{url}:{normalized[:5000]}"
        return hashlib.md5(content.encode()).hexdigest()

    async def explore(
        self,
        start_url: str,
        max_steps: int = 50,
        max_depth: int = 3
    ) -> ExplorationResult:
        """Run exploratory tests"""
        start_time = time.time()

        if not self.browser:
            return ExplorationResult(
                total_states=0,
                total_actions=0,
                unique_urls=0,
                anomalies=[],
                coverage=0,
                duration_seconds=0
            )

        self.visited_states.clear()
        self.visited_urls.clear()
        self.action_history.clear()
        self.anomalies.clear()
        self.state_graph.clear()
        self.regression_cases.clear()
        self._current_state_hash = ""

        # Initial navigation
        await self._navigate(start_url)

        step = 0
        current_depth = 0

        while step < max_steps and current_depth < max_depth:
            step += 1

            # Read the current state
            state = await self._get_current_state()
            state_hash = self._compute_state_hash(
                await self._get_page_html(),
                state.url
            )

            # Detect anomalies
            await self._detect_anomalies(state)

            # Record the state transition
            prev_hash = self._current_state_hash
            self._current_state_hash = state_hash

            # When this is a new state
            if state_hash not in self.visited_states:
                self.visited_states.add(state_hash)
                self.visited_urls.add(state.url)
                self.state_graph.setdefault(state_hash, {})

                # Find possible actions
                actions = await self._discover_actions()

                if actions:
                    # Intelligent LLM-driven selection
                    action = await self._select_action(actions)

                    # Execute the action
                    await self._execute_action(action)
                    self.action_history.append(action)

                    # Record the state-transition edge
                    action_key = f"{action.action_type.value}:{action.target[:50]}"
                    new_state = await self._get_current_state()
                    new_hash = self._compute_state_hash(
                        await self._get_page_html(), new_state.url
                    )
                    self.state_graph[state_hash][action_key] = new_hash
                else:
                    # Go back when no executable actions are available
                    await self._go_back()
                    current_depth = max(0, current_depth - 1)
            else:
                # Previously visited state: find unexplored branches in the state graph
                unexplored = self._find_unexplored_branches(state_hash)
                if unexplored:
                    action = unexplored[0]
                    await self._execute_action(action)
                    self.action_history.append(action)
                else:
                    await self._go_back()

        duration = time.time() - start_time

        return ExplorationResult(
            total_states=len(self.visited_states),
            total_actions=len(self.action_history),
            unique_urls=len(self.visited_urls),
            anomalies=self.anomalies,
            coverage=self._calculate_coverage(),
            duration_seconds=duration
        )

    async def _navigate(self, url: str):
        """Navigate to a URL"""
        if self.browser:
            await self.browser.goto(url)
            await asyncio.sleep(1)

    async def _get_current_state(self) -> PageState:
        """Read the current page state"""
        if not self.browser:
            return PageState("", "", "", 0, 0, 0)

        url = await self._resolve_browser_attr("current_url", default=None)
        if url is None:
            url = await self._resolve_browser_attr("url", default="")

        title = await self._resolve_browser_attr("title", default="")

        return PageState(
            url=url or "",
            title=title or "",
            html_hash="",
            elements_count=0,
            forms_count=0,
            links_count=0
        )

    async def _get_page_html(self) -> str:
        """Get the page HTML"""
        if self.browser and hasattr(self.browser, 'content'):
            return await self.browser.content()
        return ""

    async def _discover_actions(self) -> List[ExplorationAction]:
        """Discover executable actions"""
        actions = []

        if not self.browser:
            return actions

        # Find links
        try:
            links = await self.browser.query_selector_all('a[href]')
            for link in links[:10]:  # Limit the count
                href = await link.get_attribute('href')
                if href and not href.startswith('#') and not href.startswith('javascript:'):
                    actions.append(ExplorationAction(
                        action_type=ActionType.CLICK,
                        target=f"a[href='{href}']"
                    ))
        except Exception:
            pass

        # Find buttons
        try:
            buttons = await self.browser.query_selector_all('button, input[type="submit"]')
            for btn in buttons[:5]:
                text = await btn.inner_text() if hasattr(btn, 'inner_text') else ""
                actions.append(ExplorationAction(
                    action_type=ActionType.CLICK,
                    target=f"button:has-text('{text[:20]}')" if text else "button"
                ))
        except Exception:
            pass

        # Find input fields
        try:
            inputs = await self.browser.query_selector_all('input[type="text"], input[type="search"]')
            for inp in inputs[:3]:
                name = await inp.get_attribute('name') or await inp.get_attribute('id') or ""
                actions.append(ExplorationAction(
                    action_type=ActionType.INPUT,
                    target=f"input[name='{name}']" if name else "input",
                    value="test_input"
                ))
        except Exception:
            pass

        return actions

    async def _select_action(self, actions: List[ExplorationAction]) -> ExplorationAction:
        """Select an action using the LLM, with a rule-based fallback"""
        # Try LLM reasoning first
        if self.llm and len(actions) > 1:
            try:
                llm_choice = await self._llm_select_action(actions)
                if llm_choice is not None:
                    return llm_choice
            except Exception as e:
                logger.warning(f"[ExploratoryAgent] LLM selection failed; falling back to rules: {e}")

        # Rule-based fallback: prioritize actions that have not run
        for action in actions:
            if action not in self.action_history:
                return action

        # Choose randomly
        return random.choice(actions)

    async def _llm_select_action(self, actions: List[ExplorationAction]) -> Optional[ExplorationAction]:
        """Use the LLM to select the most valuable exploration action"""
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser

        actions_desc = "\n".join([
            f"{i+1}. [{a.action_type.value}] target={a.target} value={a.value}"
            for i, a in enumerate(actions[:10])
        ])
        history_desc = "\n".join([
            f"  - [{a.action_type.value}] {a.target}"
            for a in self.action_history[-5:]
        ]) or "(No history)"

        prompt = ChatPromptTemplate.from_template(
            """You are an exploratory testing expert. Based on execution history and available actions, choose the action most likely to discover a new feature or bug.

[Execution history: last five steps]
{history}

[Available actions]
{actions}

[Number of states covered]{states_count}

Selection principles:
1. Prioritize new paths that have not been covered
2. Form submissions and button clicks are more valuable than scrolling
3. Avoid repeating the same actions

Return only JSON:{{"choice": 1, "reason": "Reason for the choice"}} (choice is the action number, starting at 1)"""
        )
        chain = prompt | get_llm_for_role("executor") | JsonOutputParser()
        result = await asyncio.to_thread(
            chain.invoke,
            {
                "history": history_desc,
                "actions": actions_desc,
                "states_count": len(self.visited_states),
            }
        )
        choice_idx = result.get("choice", 1) - 1
        if 0 <= choice_idx < len(actions):
            logger.info(f"[ExploratoryAgent] LLM selected action #{choice_idx+1}: {result.get('reason', '')}")
            return actions[choice_idx]
        return None

    async def _execute_action(self, action: ExplorationAction):
        """Execute the action"""
        if not self.browser:
            return

        try:
            if action.action_type == ActionType.CLICK:
                elem = await self.browser.query_selector(action.target)
                if elem:
                    await elem.click()
                    await asyncio.sleep(1)

            elif action.action_type == ActionType.INPUT:
                elem = await self.browser.query_selector(action.target)
                if elem:
                    await elem.fill(action.value or "")
                    await asyncio.sleep(0.5)
        except Exception:
            pass

    async def _go_back(self):
        """Go back to the previous page"""
        if self.browser and hasattr(self.browser, 'go_back'):
            try:
                await self.browser.go_back()
                await asyncio.sleep(1)
            except Exception:
                pass

    async def _detect_anomalies(self, state: PageState):
        """Enhanced anomaly detection: HTML regular expressions, JS console, network requests, and performance metrics"""
        html = await self._get_page_html()

        # 1. HTML regular-expression matching
        for pattern, anomaly_type in self.error_patterns:
            if re.search(pattern, html, re.IGNORECASE):
                self.anomalies.append(AnomalyFound(
                    anomaly_type=anomaly_type,
                    description=f"Detected {anomaly_type} pattern in page",
                    url=state.url,
                    evidence=pattern,
                    severity="high" if "error" in anomaly_type else "medium"
                ))

        # 2. JS console error detection (requires browser support)
        if self.browser and hasattr(self.browser, 'evaluate'):
            try:
                js_errors = await self.browser.evaluate("""
                    () => {
                        if (window.__console_errors) return window.__console_errors;
                        return [];
                    }
                """)
                for err in (js_errors or []):
                    self.anomalies.append(AnomalyFound(
                        anomaly_type="js_console_error",
                        description=f"JS Console Error: {str(err)[:200]}",
                        url=state.url,
                        evidence=str(err)[:300],
                        severity="high"
                    ))
            except Exception:
                pass

        # 3. Performance-metric anomaly detection
        if self.browser and hasattr(self.browser, 'evaluate'):
            try:
                perf = await self.browser.evaluate("""
                    () => {
                        const nav = performance.getEntriesByType('navigation')[0];
                        if (!nav) return null;
                        return {
                            load_time: nav.loadEventEnd - nav.startTime,
                            dom_complete: nav.domComplete - nav.startTime,
                        };
                    }
                """)
                if perf and perf.get('load_time', 0) > 10000:  # >10s
                    self.anomalies.append(AnomalyFound(
                        anomaly_type="slow_page_load",
                        description=f"Page load took {perf['load_time']:.0f}ms (>10s threshold)",
                        url=state.url,
                        evidence=json.dumps(perf),
                        severity="medium"
                    ))
            except Exception:
                pass

    def _calculate_coverage(self) -> float:
        """Calculate coverage based on state-graph edges"""
        if not self.action_history:
            return 0.0

        # Enhancement: state-graph edge coverage
        total_edges = sum(len(edges) for edges in self.state_graph.values())
        total_possible = len(self.visited_states) * 3  # Estimate an average of three edges per state
        if total_possible == 0:
            return 0.0
        return min(1.0, total_edges / max(1, total_possible))

    def _find_unexplored_branches(self, state_hash: str) -> List[ExplorationAction]:
        """Find unexplored branches in the state graph"""
        explored_actions = set(self.state_graph.get(state_hash, {}).keys())
        unexplored = []
        for action in self.action_history:
            action_key = f"{action.action_type.value}:{action.target[:50]}"
            if action_key not in explored_actions:
                unexplored.append(action)
        return unexplored[:3]

    def generate_regression_cases(self) -> List[Dict[str, Any]]:
        """Generate replayable regression cases automatically from the exploration path"""
        cases = []

        # Generate regression cases from paths with anomalies
        if self.anomalies:
            for anomaly in self.anomalies:
                # Trace the action path that led to the page with the anomaly
                path_actions = []
                for action in self.action_history:
                    path_actions.append({
                        "action": action.action_type.value,
                        "target": action.target,
                        "value": action.value
                    })
                cases.append({
                    "name": f"Regression test: {anomaly.anomaly_type} @ {anomaly.url}",
                    "description": anomaly.description,
                    "severity": anomaly.severity,
                    "steps": path_actions,
                    "expected_result": f"The page should not show {anomaly.anomaly_type}",
                    "anomaly_evidence": anomaly.evidence
                })

        # Generate smoke tests from the complete exploration path
        if self.action_history:
            smoke_steps = []
            for action in self.action_history[:20]:  # Take the first 20 steps
                smoke_steps.append({
                    "action": action.action_type.value,
                    "target": action.target,
                    "value": action.value
                })
            cases.append({
                "name": f"Smoke test: explore core paths ({len(smoke_steps)} steps)",
                "description": f"Cover {len(self.visited_urls)} pages through their core interaction paths",
                "severity": "high",
                "steps": smoke_steps,
                "expected_result": "All pages load normally without anomalies"
            })

        self.regression_cases = cases
        logger.info(f"[ExploratoryAgent] Generated {len(cases)} regression cases")
        return cases

    def get_state_graph_summary(self) -> Dict[str, Any]:
        """Get a state-transition graph summary"""
        return {
            "total_states": len(self.state_graph),
            "total_transitions": sum(len(e) for e in self.state_graph.values()),
            "states": {
                state: list(edges.keys())
                for state, edges in self.state_graph.items()
            }
        }

    def generate_report(self) -> Dict[str, Any]:
        """Generate an enhanced exploration report"""
        return {
            "summary": {
                "total_states_visited": len(self.visited_states),
                "total_actions_performed": len(self.action_history),
                "unique_urls": len(self.visited_urls),
                "anomalies_found": len(self.anomalies),
                "state_transitions": sum(len(e) for e in self.state_graph.values()),
                "regression_cases": len(self.regression_cases)
            },
            "visited_urls": list(self.visited_urls),
            "action_history": [
                {
                    "type": a.action_type.value,
                    "target": a.target,
                    "value": a.value
                }
                for a in self.action_history[-20:]
            ],
            "anomalies": [
                {
                    "type": a.anomaly_type,
                    "description": a.description,
                    "url": a.url,
                    "severity": a.severity
                }
                for a in self.anomalies
            ],
            "state_graph": self.get_state_graph_summary(),
            "regression_cases": self.regression_cases[:10]  # Up to 10
        }


def create_exploratory_agent(browser=None, llm=None) -> ExploratoryTestAgent:
    """Create an exploratory test agent"""
    return ExploratoryTestAgent(browser, llm)
