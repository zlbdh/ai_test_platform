# -*- coding: utf-8 -*-
"""
CI/CD Integration Module — Deep CI/CD integration

github_action.py: GitHub Actions integration
- Receive PR events through webhooks
- Analyze code diffs to select a relevant test subset
- Call the platform API to run tests
- Write back the PR check status
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import json
import re
import logging
import time
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class PREvent:
    """GitHub PR event"""
    action: str = ""          # opened, synchronize, closed
    pr_number: int = 0
    repo: str = ""
    branch: str = ""
    base_branch: str = ""
    title: str = ""
    changed_files: List[str] = field(default_factory=list)
    diff_content: str = ""
    commit_sha: str = ""


@dataclass
class TestSelectionResult:
    """Test selection result"""
    selected_tests: List[str] = field(default_factory=list)
    reason: str = ""
    coverage_estimate: float = 0.0
    impact_score: float = 0.0  # Change impact from 0.0 to 1.0

    def to_dict(self) -> Dict:
        return {
            "selected_tests": self.selected_tests,
            "reason": self.reason,
            "coverage_estimate": round(self.coverage_estimate, 3),
            "impact_score": round(self.impact_score, 3),
            "test_count": len(self.selected_tests),
        }


class ChangeImpactAnalyzer:
    """
    Change impact analyzer

    Analyze the impact of code changes (diffs) and select the test subset to run.
    """

    # File type → impact area mapping
    IMPACT_MAP = {
        # Frontend changes
        r"\.tsx?$": {"area": "ui", "weight": 0.7},
        r"\.css$": {"area": "visual", "weight": 0.3},
        r"\.html$": {"area": "ui", "weight": 0.5},
        # Backend changes
        r"agents/.*\.py$": {"area": "agent", "weight": 0.9},
        r"core/.*\.py$": {"area": "core", "weight": 1.0},
        r"routers/.*\.py$": {"area": "api", "weight": 0.8},
        r"services/.*\.py$": {"area": "service", "weight": 0.8},
        r"skills/.*\.py$": {"area": "skill", "weight": 0.6},
        # Configuration changes
        r"\.env": {"area": "config", "weight": 0.5},
        r"config\.py$": {"area": "config", "weight": 0.7},
        r"requirements\.txt$": {"area": "dependency", "weight": 0.4},
    }

    # Impact area → recommended test types
    AREA_TESTS = {
        "ui": ["ui_functional", "visual_regression", "accessibility"],
        "visual": ["visual_regression"],
        "agent": ["agent_evaluation", "integration", "e2e"],
        "core": ["unit", "integration", "e2e", "agent_evaluation"],
        "api": ["api_contract", "integration"],
        "service": ["unit", "integration"],
        "skill": ["unit"],
        "config": ["smoke", "health_check"],
        "dependency": ["full_regression"],
    }

    def analyze(self, changed_files: List[str]) -> TestSelectionResult:
        """Analyze change impact and select tests"""
        if not changed_files:
            return TestSelectionResult(reason="No file changes")

        affected_areas = set()
        max_weight = 0.0

        for filepath in changed_files:
            for pattern, impact in self.IMPACT_MAP.items():
                if re.search(pattern, filepath):
                    affected_areas.add(impact["area"])
                    max_weight = max(max_weight, impact["weight"])
                    break

        if not affected_areas:
            affected_areas.add("general")
            max_weight = 0.3

        # Collect recommended tests
        selected = set()
        for area in affected_areas:
            tests = self.AREA_TESTS.get(area, ["smoke"])
            selected.update(tests)

        # Determine whether a full regression run is needed
        if max_weight >= 0.9 or len(changed_files) > 20:
            selected.add("full_regression")

        return TestSelectionResult(
            selected_tests=sorted(selected),
            reason=f"Affected areas: {', '.join(affected_areas)}",
            coverage_estimate=min(1.0, len(selected) * 0.15),
            impact_score=max_weight,
        )


class GitHubIntegration:
    """
    GitHub Actions integration

    Handle GitHub webhook events and trigger the corresponding test flow.
    """

    def __init__(self, webhook_secret: str = ""):
        self.webhook_secret = webhook_secret
        self.analyzer = ChangeImpactAnalyzer()

    def process_webhook(self, payload: Dict) -> Dict[str, Any]:
        """Handle a GitHub webhook event"""
        event = self._parse_event(payload)

        if event.action not in ("opened", "synchronize", "reopened"):
            return {"action": "skip", "reason": f"Ignoring PR event: {event.action}"}

        # Analyze change impact
        selection = self.analyzer.analyze(event.changed_files)

        # Build a test plan
        test_plan = {
            "pr_number": event.pr_number,
            "repo": event.repo,
            "branch": event.branch,
            "commit_sha": event.commit_sha,
            "selection": selection.to_dict(),
            "recommended_action": self._determine_action(selection),
        }

        return {"action": "run_tests", "plan": test_plan}

    def _parse_event(self, payload: Dict) -> PREvent:
        """Parse the webhook payload"""
        pr = payload.get("pull_request", {})
        return PREvent(
            action=payload.get("action", ""),
            pr_number=pr.get("number", 0),
            repo=payload.get("repository", {}).get("full_name", ""),
            branch=pr.get("head", {}).get("ref", ""),
            base_branch=pr.get("base", {}).get("ref", ""),
            title=pr.get("title", ""),
            changed_files=[f.get("filename", "") for f in payload.get("files", [])],
            commit_sha=pr.get("head", {}).get("sha", ""),
        )

    def _determine_action(self, selection: TestSelectionResult) -> str:
        if selection.impact_score >= 0.9:
            return "full_regression + agent_evaluation"
        elif selection.impact_score >= 0.6:
            return "targeted_tests + smoke"
        else:
            return "smoke_only"

    def create_check_result(self, run_result: Dict) -> Dict:
        """Create a GitHub Check result for the API callback"""
        success = run_result.get("success", False)
        return {
            "status": "completed",
            "conclusion": "success" if success else "failure",
            "output": {
                "title": "AI Test Platform Results",
                "summary": run_result.get("summary", ""),
                "text": json.dumps(run_result, ensure_ascii=False, indent=2)[:65535],
            },
        }
