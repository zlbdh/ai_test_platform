# -*- coding: utf-8 -*-
"""
MCP Server — Model Context Protocol 服务器

通过 stdio 协议暴露平台能力给外部 AI 助手。
支持工具调用 (tools/call) 和工具列表 (tools/list)。

启动方式:
    python -m mcp.server
"""

import sys
import os
import json
import asyncio
import logging
import base64
from typing import Dict, Any, Optional

# 将项目根目录加入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.app_meta import APP_VERSION

logger = logging.getLogger("mcp_server")


class MCPServer:
    """
    MCP Server 实现

    通过 stdin/stdout 进行 JSONRPC 通信，
    符合 Model Context Protocol 规范。
    """

    def __init__(self):
        self.tools = {}
        self._register_tools()

    def _register_tools(self):
        """注册所有 MCP tools"""
        self.tools = {
            "run_test": self._tool_run_test,
            "get_test_status": self._tool_get_test_status,
            "get_screenshot": self._tool_get_screenshot,
            "browse_and_verify": self._tool_browse_and_verify,
            "get_test_report": self._tool_get_test_report,
            "list_sessions": self._tool_list_sessions,
            "run_api_test": self._tool_run_api_test,
            "evaluate_agent": self._tool_evaluate_agent,
            # P1 新增
            "generate_test_data": self._tool_generate_test_data,
            "get_analytics": self._tool_get_analytics,
            "get_execution_history": self._tool_get_execution_history,
            "trigger_ci_test": self._tool_trigger_ci_test,
        }

    # ── MCP Protocol Handlers ────────────────────────────────────────────────

    async def handle_message(self, message: Dict) -> Dict:
        """处理 MCP JSONRPC 消息"""
        method = message.get("method", "")
        msg_id = message.get("id")
        params = message.get("params", {})

        try:
            if method == "initialize":
                return self._response(msg_id, {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "ai-test-platform",
                        "version": APP_VERSION,
                    },
                })

            elif method == "tools/list":
                from mcp.tools import PLATFORM_TOOLS
                return self._response(msg_id, {
                    "tools": [t.to_schema() for t in PLATFORM_TOOLS],
                })

            elif method == "tools/call":
                tool_name = params.get("name", "")
                arguments = params.get("arguments", {})
                result = await self._call_tool(tool_name, arguments)
                return self._response(msg_id, {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
                })

            elif method == "notifications/initialized":
                return None  # 无需响应

            else:
                return self._error(msg_id, -32601, f"Method not found: {method}")

        except Exception as e:
            logger.error(f"MCP Error: {e}", exc_info=True)
            return self._error(msg_id, -32603, str(e))

    async def _call_tool(self, name: str, arguments: Dict) -> Dict:
        """调用工具"""
        handler = self.tools.get(name)
        if not handler:
            return {"error": f"Unknown tool: {name}"}
        return await handler(arguments)

    # ── Tool Implementations ─────────────────────────────────────────────────

    async def _tool_run_test(self, args: Dict) -> Dict:
        """执行测试"""
        url = args.get("url", "")
        instructions = args.get("instructions", "")
        session_id = args.get("session_id", "mcp_session")

        if not url or not instructions:
            return {"error": "url 和 instructions 为必填参数"}

        try:
            import httpx
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    "http://localhost:8020/api/commander/execute",
                    json={
                        "instruction": f"打开 {url}，{instructions}",
                        "session_id": session_id,
                    },
                )
                return resp.json()
        except Exception as e:
            return {"error": f"调用测试API失败: {str(e)}",
                    "hint": "请确保后端服务已启动 (localhost:8020)"}

    async def _tool_get_test_status(self, args: Dict) -> Dict:
        """获取测试状态"""
        session_id = args.get("session_id", "")
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"http://localhost:8020/api/commander/status/{session_id}"
                )
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    async def _tool_get_screenshot(self, args: Dict) -> Dict:
        """获取截图"""
        session_id = args.get("session_id", "mcp_session")
        try:
            from core.session_manager import session_manager
            session = session_manager.get_session(session_id)
            frame = session.get_frame()
            if frame:
                b64 = base64.b64encode(frame).decode("utf-8")
                return {"status": "success", "image_base64": b64[:100] + "...(truncated)", "size_bytes": len(frame)}
            return {"status": "no_frame", "message": "当前无活跃浏览器会话"}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_browse_and_verify(self, args: Dict) -> Dict:
        """浏览并验证"""
        url = args.get("url", "")
        assertion = args.get("assertion", "")
        session_id = args.get("session_id", "mcp_session")

        if not url or not assertion:
            return {"error": "url 和 assertion 为必填参数"}

        try:
            import httpx
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    "http://localhost:8020/api/commander/execute",
                    json={
                        "instruction": f"打开 {url}，然后验证: {assertion}",
                        "session_id": session_id,
                    },
                )
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    async def _tool_get_test_report(self, args: Dict) -> Dict:
        """获取测试报告"""
        session_id = args.get("session_id", "")
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"http://localhost:8020/api/history/runs?session_id={session_id}&limit=1"
                )
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    async def _tool_list_sessions(self, args: Dict) -> Dict:
        """列出活跃会话"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("http://localhost:8020/api/status")
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    async def _tool_run_api_test(self, args: Dict) -> Dict:
        """运行API测试"""
        try:
            import httpx
            method = args.get("method", "GET").upper()
            url = args.get("url", "")
            headers_str = args.get("headers", "{}")
            body_str = args.get("body", "")

            headers = json.loads(headers_str) if isinstance(headers_str, str) else headers_str

            async with httpx.AsyncClient(timeout=30) as client:
                if method == "GET":
                    resp = await client.get(url, headers=headers)
                elif method == "POST":
                    resp = await client.post(url, headers=headers, content=body_str)
                elif method == "PUT":
                    resp = await client.put(url, headers=headers, content=body_str)
                elif method == "DELETE":
                    resp = await client.delete(url, headers=headers)
                else:
                    return {"error": f"不支持的 HTTP 方法: {method}"}

                result = {
                    "status_code": resp.status_code,
                    "headers": dict(resp.headers),
                    "body_preview": resp.text[:2000],
                    "elapsed_ms": resp.elapsed.total_seconds() * 1000 if resp.elapsed else 0,
                }

                # 执行断言
                assertions = args.get("assertions", "")
                if assertions:
                    result["assertion_result"] = self._check_assertions(assertions, resp)

                return result
        except Exception as e:
            return {"error": str(e)}

    async def _tool_evaluate_agent(self, args: Dict) -> Dict:
        """运行Agent评估"""
        try:
            import httpx
            scenario_id = args.get("scenario_id", "")
            async with httpx.AsyncClient(timeout=30) as client:
                params = {}
                if scenario_id:
                    params["scenario_id"] = scenario_id
                resp = await client.get(
                    "http://localhost:8020/api/evaluation/results",
                    params=params,
                )
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def _check_assertions(assertions: str, response) -> Dict:
        """简单断言检查"""
        results = {"passed": True, "checks": []}
        if "status_code == 200" in assertions:
            ok = response.status_code == 200
            results["checks"].append({"check": "status_code == 200", "passed": ok})
            if not ok:
                results["passed"] = False
        if "body" in assertions and "not empty" in assertions:
            ok = len(response.text.strip()) > 0
            results["checks"].append({"check": "body not empty", "passed": ok})
            if not ok:
                results["passed"] = False
        return results

    # ── P1 新增 Tool Implementations ────────────────────────────────────────

    async def _tool_generate_test_data(self, args: Dict) -> Dict:
        """生成测试数据"""
        try:
            from core.test_data_generator import TestDataGenerator
            template = args.get("template", "user")
            count = int(args.get("count", 5))
            include_edge = args.get("include_edge", True)
            result = TestDataGenerator.generate(template, count, include_edge)
            return result
        except Exception as e:
            return {"error": str(e)}

    async def _tool_get_analytics(self, args: Dict) -> Dict:
        """获取分析摘要"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("http://localhost:8020/api/analytics/summary")
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    async def _tool_get_execution_history(self, args: Dict) -> Dict:
        """获取执行历史"""
        try:
            import httpx
            limit = int(args.get("limit", 10))
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"http://localhost:8020/api/history?limit={limit}")
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    async def _tool_trigger_ci_test(self, args: Dict) -> Dict:
        """触发 CI 测试"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "http://localhost:8020/api/ci/webhook",
                    json={
                        "source": args.get("source", "manual"),
                        "ref": args.get("ref", "main"),
                        "commit": args.get("commit", ""),
                    },
                )
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    # ── JSONRPC Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _response(msg_id, result):
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    @staticmethod
    def _error(msg_id, code, message):
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


# ── stdio Helpers ───────────────────────────────────────────────────────────

def _stdio_reader():
    """优先使用二进制流，避免 Windows pipe transport 兼容问题。"""
    return getattr(sys.stdin, "buffer", sys.stdin)


def _stdio_writer():
    """优先使用二进制流，避免 Windows pipe transport 兼容问题。"""
    return getattr(sys.stdout, "buffer", sys.stdout)


async def _read_message_line() -> bytes | str:
    """在线程中阻塞读取一行，兼容控制台和重定向 pipe。"""
    return await asyncio.to_thread(_stdio_reader().readline)


async def _write_message_line(payload: str) -> None:
    """在线程中写回一行 JSONRPC 响应并立即刷新。"""

    def _write() -> None:
        writer = _stdio_writer()
        data = (payload + "\n").encode("utf-8")
        try:
            writer.write(data)
        except TypeError:
            writer.write(payload + "\n")
        writer.flush()

    await asyncio.to_thread(_write)


# ── 主入口 ───────────────────────────────────────────────────────────────────

async def main():
    """通过 stdio 运行 MCP Server"""
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    logger.info("🚀 AI Test Platform MCP Server 启动")

    server = MCPServer()
    while True:
        try:
            raw_line = await _read_message_line()
            if not raw_line:
                break

            if isinstance(raw_line, bytes):
                line = raw_line.decode("utf-8").strip()
            else:
                line = raw_line.strip()
            line = line.lstrip("\ufeff")

            if not line:
                continue

            try:
                message = json.loads(line)
                response = await server.handle_message(message)
                if response:
                    out = json.dumps(response, ensure_ascii=False)
                    await _write_message_line(out)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON: {line[:100]}")

        except Exception as e:
            logger.error(f"MCP Server Error: {e}", exc_info=True)
            break

    logger.info("MCP Server 已关闭")


if __name__ == "__main__":
    asyncio.run(main())
