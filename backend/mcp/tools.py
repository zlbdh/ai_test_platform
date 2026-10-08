# -*- coding: utf-8 -*-
"""
MCP Tools — Define the platform tools exposed to external AI assistants

Each tool represents a core platform capability, available over MCP to
Claude Code, Cursor, and other AI assistants.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import json


@dataclass
class ToolParameter:
    """MCP tool parameter"""
    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Any = None


@dataclass
class MCPTool:
    """MCP tool definition"""
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)

    def to_schema(self) -> Dict:
        """Convert to an MCP tool schema"""
        properties = {}
        required = []
        for p in self.parameters:
            properties[p.name] = {
                "type": p.type,
                "description": p.description,
            }
            if p.default is not None:
                properties[p.name]["default"] = p.default
            if p.required:
                required.append(p.name)

        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }


# ── Tool definitions ──────────────────────────────────────────────────────────────────

PLATFORM_TOOLS: List[MCPTool] = [
    MCPTool(
        name="run_test",
        description="Run an AI-driven end-to-end test. Provide a target URL and natural-language instructions; the platform plans and executes the test steps automatically.",
        parameters=[
            ToolParameter(name="url", type="string", description="Test target URL", required=True),
            ToolParameter(name="instructions", type="string", description="Natural-language test instructions, such as 'Search for AI testing and verify the results'", required=True),
            ToolParameter(name="session_id", type="string", description="Test session ID (optional)", default="mcp_session"),
        ],
    ),
    MCPTool(
        name="get_test_status",
        description="Get the test execution status for a session, including its current step, progress, and errors.",
        parameters=[
            ToolParameter(name="session_id", type="string", description="Test session ID", required=True),
        ],
    ),
    MCPTool(
        name="get_screenshot",
        description="Capture the current browser window and return a base64-encoded JPEG image.",
        parameters=[
            ToolParameter(name="session_id", type="string", description="Test session ID", default="mcp_session"),
        ],
    ),
    MCPTool(
        name="browse_and_verify",
        description="Navigate to a URL and verify a semantic assertion against the page content.",
        parameters=[
            ToolParameter(name="url", type="string", description="URL to visit", required=True),
            ToolParameter(name="assertion", type="string", description="Assertion to verify, such as 'The page contains a login button'", required=True),
            ToolParameter(name="session_id", type="string", description="Test session ID", default="mcp_session"),
        ],
    ),
    MCPTool(
        name="get_test_report",
        description="Get a session's complete test report, including step details, screenshots, and pass/fail status.",
        parameters=[
            ToolParameter(name="session_id", type="string", description="Test session ID", required=True),
        ],
    ),
    MCPTool(
        name="list_sessions",
        description="List all active test sessions on the platform.",
        parameters=[],
    ),
    MCPTool(
        name="run_api_test",
        description="Run API tests with support for REST/GraphQL/gRPC.",
        parameters=[
            ToolParameter(name="method", type="string", description="HTTP method", required=True, default="GET"),
            ToolParameter(name="url", type="string", description="API URL", required=True),
            ToolParameter(name="headers", type="string", description="Request headers (JSON string)", default="{}"),
            ToolParameter(name="body", type="string", description="Request body (JSON string)", default=""),
            ToolParameter(name="assertions", type="string", description="Assertion condition, such as 'status_code == 200 and body.data is not empty'"),
        ],
    ),
    MCPTool(
        name="evaluate_agent",
        description="Run agent quality evaluation and return scores for each dimension.",
        parameters=[
            ToolParameter(name="scenario_id", type="string", description="Benchmark scenario ID (optional; evaluates the most recent execution if omitted)"),
        ],
    ),
    # ── Tools added in P1 ──
    MCPTool(
        name="generate_test_data",
        description="Generate test data from user/address/payment/search/boundary templates, automatically including boundary values and security attack data.",
        parameters=[
            ToolParameter(name="template", type="string", description="Template type: user/address/payment/search/boundary", required=True, default="user"),
            ToolParameter(name="count", type="integer", description="Number to generate", default=5),
            ToolParameter(name="include_edge", type="boolean", description="Whether to include boundary values and attack data", default=True),
        ],
    ),
    MCPTool(
        name="get_analytics",
        description="Get platform analytics: total executions, pass rate, average duration, today's and this week's statistics, and more.",
        parameters=[],
    ),
    MCPTool(
        name="get_execution_history",
        description="Get a list of recent test execution records.",
        parameters=[
            ToolParameter(name="limit", type="integer", description="Number of results to return", default=10),
        ],
    ),
    MCPTool(
        name="trigger_ci_test",
        description="Trigger test execution from CI/CD, supporting Jenkins/GitLab/GitHub Actions webhook formats.",
        parameters=[
            ToolParameter(name="source", type="string", description="Trigger source: github/gitlab/jenkins/manual", required=True),
            ToolParameter(name="ref", type="string", description="Branch/tag", default="main"),
            ToolParameter(name="commit", type="string", description="Commit hash", default=""),
        ],
    ),
]
