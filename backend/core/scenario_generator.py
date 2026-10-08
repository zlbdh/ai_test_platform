# -*- coding: utf-8 -*-
"""
Scenario Generator

Derive exception scenarios from normal workflows:
- Combine parameters to generate boundary cases
- Infer error paths from normal workflows
- Populate performance/security scenario templates
"""

import re

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import json
import logging
import itertools

logger = logging.getLogger(__name__)


# ── Scenario templates ──────────────────────────────────────────────────────

BOUNDARY_TEMPLATES = {
    "string": [
        {"name": "Empty string", "value": ""},
        {"name": "Single character", "value": "a"},
        {"name": "Maximum length", "value": "a" * 255},
        {"name": "Very long string", "value": "a" * 10000},
        {"name": "Special characters", "value": "<script>alert(1)</script>"},
        {"name": "SQL injection", "value": "' OR 1=1 --"},
        {"name": "Unicode characters", "value": "🎯测试émoji"},
        {"name": "Space padding", "value": "   "},
        {"name": "Tabs and newlines", "value": "\t\n\r"},
    ],
    "number": [
        {"name": "Zero", "value": 0},
        {"name": "Negative number", "value": -1},
        {"name": "Very large number", "value": 999999999},
        {"name": "Decimal", "value": 0.001},
        {"name": "Maximum boundary", "value": 2147483647},
        {"name": "Nonnumeric string", "value": "abc"},
    ],
    "email": [
        {"name": "Invalid format", "value": "not-an-email"},
        {"name": "Missing @", "value": "userexample.com"},
        {"name": "Missing domain", "value": "user@"},
        {"name": "Special characters", "value": "user+tag@example.com"},
        {"name": "Very long email", "value": "a" * 200 + "@example.com"},
    ],
    "url": [
        {"name": "Missing protocol", "value": "example.com"},
        {"name": "Invalid protocol", "value": "ftp://example.com"},
        {"name": "Contains special characters", "value": "https://example.com/<script>"},
        {"name": "Local address", "value": "http://localhost:8080"},
        {"name": "IP address", "value": "http://192.168.1.1"},
    ],
}

PERFORMANCE_TEMPLATES = [
    {
        "name": "Concurrent user load",
        "description": "Simulate {users} concurrent users performing the same action",
        "params": {"users": [10, 50, 100, 500]},
    },
    {
        "name": "Large data volume",
        "description": "Submit {size} records and observe the system response",
        "params": {"size": [100, 1000, 10000]},
    },
    {
        "name": "Sustained stress test",
        "description": "Send requests continuously for {duration} minutes",
        "params": {"duration": [5, 15, 30]},
    },
]

SECURITY_TEMPLATES = [
    {"name": "XSS attack", "action": "Enter <script>alert('xss')</script> in every text input"},
    {"name": "SQL injection", "action": "Enter ' OR '1'='1 in query and search inputs"},
    {"name": "CSRF detection", "action": "Check whether forms include a CSRF token"},
    {"name": "Path traversal", "action": "Use ../../../etc/passwd in the file upload path"},
    {"name": "Authentication bypass", "action": "Access authentication-required API endpoints directly without a token"},
    {"name": "Unauthorized access", "action": "Access administrator APIs with a standard-user token"},
    {"name": "Sensitive data exposure", "action": "Check API responses for sensitive fields such as passwords or tokens"},
]


class ScenarioGenerator:
    """Scenario generator"""

    def generate_boundary_scenarios(
        self,
        field_name: str,
        field_type: str = "string",
        custom_values: List[Any] = None,
    ) -> List[Dict]:
        """
        Generate boundary test scenarios for a field.

        Args:
            field_name: Field name
            field_type: Field type (string/number/email/url)
            custom_values: Custom test values

        Returns:
            List of boundary test scenarios
        """
        templates = BOUNDARY_TEMPLATES.get(field_type, BOUNDARY_TEMPLATES["string"])
        scenarios = []

        for t in templates:
            scenarios.append({
                "title": f"{field_name} - {t['name']}",
                "category": "boundary",
                "field": field_name,
                "test_value": t["value"],
                "expected": f"The {field_name} field correctly handles '{t['name']}' input",
            })

        if custom_values:
            for i, val in enumerate(custom_values):
                scenarios.append({
                    "title": f"{field_name} - Custom value {i+1}",
                    "category": "boundary",
                    "field": field_name,
                    "test_value": val,
                    "expected": f"The {field_name} field correctly handles the custom value",
                })

        return scenarios

    def generate_negative_scenarios(self, positive_flow: List[Dict]) -> List[Dict]:
        """
        Derive negative scenarios from the normal workflow.

        Generate variants such as skipped steps, invalid inputs, and timeouts for each step.
        """
        scenarios = []

        for i, step in enumerate(positive_flow):
            action = step.get("action", step.get("instruction", ""))

            # Skip this step
            scenarios.append({
                "title": f"Skip step {i+1}: {action[:30]}",
                "category": "negative",
                "description": f"Skip '{action}' and proceed directly to subsequent actions",
                "skip_step": i,
            })

            # Invalid input
            if (any(kw in action.lower() for kw in ["输入", "填写", "fill", "type"])
                    or re.search(r"\b(?:enter|input)\b", action, re.IGNORECASE)):
                scenarios.append({
                    "title": f"Step {i+1}: Invalid input",
                    "category": "negative",
                    "description": f"Enter invalid data during '{action}'",
                    "modify_step": i,
                    "modification": "Use invalid data",
                })

            # Repeat the action
            scenarios.append({
                "title": f"Repeat step {i+1}: {action[:30]}",
                "category": "negative",
                "description": f"Perform '{action}' twice in succession",
                "repeat_step": i,
            })

        # Reverse execution order
        if len(positive_flow) > 2:
            scenarios.append({
                "title": "Run all steps in reverse order",
                "category": "negative",
                "description": "Execute every action step in reverse order",
            })

        return scenarios

    def generate_performance_scenarios(self, target_url: str) -> List[Dict]:
        """Generate performance test scenarios"""
        return [
            {
                "title": t["name"],
                "category": "performance",
                "description": t["description"].format(**{k: v[0] for k, v in t["params"].items()}),
                "target_url": target_url,
                "variants": [
                    {
                        "params": dict(zip(t["params"].keys(), combo)),
                        "description": t["description"].format(**dict(zip(t["params"].keys(), combo))),
                    }
                    for combo in itertools.product(*t["params"].values())
                ],
            }
            for t in PERFORMANCE_TEMPLATES
        ]

    def generate_security_scenarios(self, target_url: str) -> List[Dict]:
        """Generate security test scenarios"""
        return [
            {
                "title": t["name"],
                "category": "security",
                "action": t["action"],
                "target_url": target_url,
                "priority": "high",
            }
            for t in SECURITY_TEMPLATES
        ]

    def generate_combination_scenarios(
        self,
        fields: Dict[str, List[Any]],
        max_combinations: int = 50,
    ) -> List[Dict]:
        """
        Parameter combination coverage: pairwise or all combinations.

        Args:
            fields: {field_name: [possible values]}
            max_combinations: Maximum number of combinations
        """
        keys = list(fields.keys())
        values = list(fields.values())

        # All combinations
        all_combos = list(itertools.product(*values))
        if len(all_combos) > max_combinations:
            # Fall back to a pairwise approximation: take the first N
            all_combos = all_combos[:max_combinations]

        scenarios = []
        for i, combo in enumerate(all_combos):
            params = dict(zip(keys, combo))
            scenarios.append({
                "title": f"Combination {i+1}: {json.dumps(params, ensure_ascii=False)[:80]}",
                "category": "combination",
                "parameters": params,
            })

        return scenarios
