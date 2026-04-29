# -*- coding: utf-8 -*-
"""
MCP Tools — 定义平台暴露给外部 AI 的工具

每个 Tool 对应平台的一项核心能力，通过 MCP 协议供
Claude Code / Cursor / 其他 AI 助手调用。
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import json


@dataclass
class ToolParameter:
    """MCP 工具参数"""
    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Any = None


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)

    def to_schema(self) -> Dict:
        """转为 MCP Tool Schema"""
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


# ── 工具定义 ──────────────────────────────────────────────────────────────────

PLATFORM_TOOLS: List[MCPTool] = [
    MCPTool(
        name="run_test",
        description="执行AI驱动的端到端测试。提供目标URL和自然语言测试指令，平台会自动规划并执行测试步骤。",
        parameters=[
            ToolParameter(name="url", type="string", description="测试目标URL", required=True),
            ToolParameter(name="instructions", type="string", description="自然语言测试指令，如 '搜索AI测试并验证结果'", required=True),
            ToolParameter(name="session_id", type="string", description="测试会话ID（可选）", default="mcp_session"),
        ],
    ),
    MCPTool(
        name="get_test_status",
        description="查询指定会话的测试执行状态，包括当前步骤、进度和任何错误信息。",
        parameters=[
            ToolParameter(name="session_id", type="string", description="测试会话ID", required=True),
        ],
    ),
    MCPTool(
        name="get_screenshot",
        description="获取当前浏览器窗口的截图，返回 base64 编码的 JPEG 图像。",
        parameters=[
            ToolParameter(name="session_id", type="string", description="测试会话ID", default="mcp_session"),
        ],
    ),
    MCPTool(
        name="browse_and_verify",
        description="导航到指定URL并对页面内容执行语义断言验证。",
        parameters=[
            ToolParameter(name="url", type="string", description="要访问的URL", required=True),
            ToolParameter(name="assertion", type="string", description="要验证的断言，如 '页面包含登录按钮'", required=True),
            ToolParameter(name="session_id", type="string", description="测试会话ID", default="mcp_session"),
        ],
    ),
    MCPTool(
        name="get_test_report",
        description="获取指定会话的完整测试报告，包括步骤详情、截图、成功/失败状态。",
        parameters=[
            ToolParameter(name="session_id", type="string", description="测试会话ID", required=True),
        ],
    ),
    MCPTool(
        name="list_sessions",
        description="列出当前平台上所有活跃的测试会话。",
        parameters=[],
    ),
    MCPTool(
        name="run_api_test",
        description="执行API测试，支持REST/GraphQL/gRPC。",
        parameters=[
            ToolParameter(name="method", type="string", description="HTTP方法", required=True, default="GET"),
            ToolParameter(name="url", type="string", description="API URL", required=True),
            ToolParameter(name="headers", type="string", description="请求头（JSON字符串）", default="{}"),
            ToolParameter(name="body", type="string", description="请求体（JSON字符串）", default=""),
            ToolParameter(name="assertions", type="string", description="断言条件，如 'status_code == 200 and body.data is not empty'"),
        ],
    ),
    MCPTool(
        name="evaluate_agent",
        description="运行Agent质量评估，返回各维度的评分。",
        parameters=[
            ToolParameter(name="scenario_id", type="string", description="基准场景ID（可选，不传则评估最近一次执行）"),
        ],
    ),
    # ── P1 新增工具 ──
    MCPTool(
        name="generate_test_data",
        description="生成测试数据，支持用户/地址/支付/搜索词/边界值模板，自动包含边界值和安全攻击数据。",
        parameters=[
            ToolParameter(name="template", type="string", description="模板类型: user/address/payment/search/boundary", required=True, default="user"),
            ToolParameter(name="count", type="integer", description="生成数量", default=5),
            ToolParameter(name="include_edge", type="boolean", description="是否包含边界值/攻击数据", default=True),
        ],
    ),
    MCPTool(
        name="get_analytics",
        description="获取测试平台的分析摘要：总执行数、通过率、平均耗时、今日/本周统计等。",
        parameters=[],
    ),
    MCPTool(
        name="get_execution_history",
        description="获取最近的测试执行历史记录列表。",
        parameters=[
            ToolParameter(name="limit", type="integer", description="返回条数", default=10),
        ],
    ),
    MCPTool(
        name="trigger_ci_test",
        description="从CI/CD系统触发测试执行，支持Jenkins/GitLab/GitHub Actions webhook格式。",
        parameters=[
            ToolParameter(name="source", type="string", description="触发源: github/gitlab/jenkins/manual", required=True),
            ToolParameter(name="ref", type="string", description="分支/标签", default="main"),
            ToolParameter(name="commit", type="string", description="提交哈希", default=""),
        ],
    ),
]
