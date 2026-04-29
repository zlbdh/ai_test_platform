"""
API Agent - 后端测试 Agent
负责接口测试、安全扫描、参数验证
"""
from typing import Dict, Any, List, Optional
from core.config import Config
from core.llm_manager import get_llm_for_role
from skills.api_tools import API_TOOLS


class APIAgent:
    """API 测试 Agent"""
    
    def __init__(self):
        """初始化 API Agent"""
        self.llm = get_llm_for_role("executor")
        
        self.tools = API_TOOLS
    
    def execute_test(self, test_scenario: str, swagger_url: Optional[str] = None) -> Dict[str, Any]:
        """
        执行 API 测试
        
        Args:
            test_scenario: 测试场景描述
            swagger_url: Swagger 文档 URL（可选）
            
        Returns:
            测试结果
        """
        results = {
            "agent": "api_agent",
            "scenario": test_scenario,
            "endpoints_tested": [],
            "security_scan": [],
            "status": "success",
            "errors": []
        }
        
        try:
            # 1. 解析 Swagger 文档（如果提供）
            if swagger_url:
                swagger_info = API_TOOLS[1].invoke({"swagger_url": swagger_url})  # parse_swagger
                results["swagger_info"] = swagger_info
                endpoints = swagger_info.get("endpoints", [])
            else:
                # 如果没有 Swagger，尝试从场景描述中提取链接，或者报错
                # 移除硬编码的 Demo 端点，确保真实环境
                import re
                url_matches = re.findall(r'https?://[^\s]+', test_scenario)
                if url_matches:
                    endpoints = [{"path": url, "method": "GET"} for url in url_matches]
                else:
                    results["status"] = "warning"
                    results["errors"].append("未提供 Swagger URL 且无法从场景中提取 URL")
                    endpoints = []
            
            # 2. 测试每个端点
            for endpoint in endpoints[:3]:  # 限制测试数量
                path = endpoint.get("path", "")
                method = endpoint.get("method", "GET")
                
                # 生成测试数据
                test_data = API_TOOLS[2].invoke({"data_type": "number", "count": 1})  # generate_test_data
                
                # 调用接口
                if method == "POST":
                    response = API_TOOLS[0].invoke({
                        "method": "POST",
                        "endpoint": path,
                        "body": {"product_id": 1, "quantity": 1}
                    })
                else:
                    response = API_TOOLS[0].invoke({
                        "method": method,
                        "endpoint": path
                    })
                
                results["endpoints_tested"].append({
                    "endpoint": path,
                    "method": method,
                    "response": response,
                    "status": "success" if response.get("status_code", 0) < 400 else "error"
                })
                
                # 3. 安全扫描
                if "cart" in path.lower() or "order" in path.lower():
                    auth_check = API_TOOLS[5].invoke({  # check_auth (索引可能变化)
                        "endpoint": path,
                        "method": method,
                        "requires_auth": True
                    })
                    
                    results["security_scan"].append(auth_check)
                    
                    # 使用模糊测试子图进行深度测试
                    try:
                        from workflows.api_fuzzing_subgraph import get_fuzzing_subgraph
                        fuzzing_subgraph = get_fuzzing_subgraph()
                        fuzz_results = fuzzing_subgraph.run(
                            endpoint=path,
                            method=method,
                            base_params={"product_id": 1},
                            max_iterations=20
                        )
                        results["security_scan"].append({
                            "type": "fuzzing_subgraph",
                            "results": fuzz_results
                        })
                    except Exception as e:
                        # 如果子图失败，使用基础模糊测试
                        fuzz_results = API_TOOLS[3].invoke({
                            "endpoint": path,
                            "method": method,
                            "base_params": {"product_id": 1}
                        })  # fuzz_api
                        results["security_scan"].extend(fuzz_results)
        
        except Exception as e:
            results["status"] = "error"
            results["errors"].append(str(e))
        
        return results
    
    def chain_api_calls(self, api_sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        链式调用 API（处理依赖关系）
        
        Args:
            api_sequence: API 调用序列，如 [{"action": "login"}, {"action": "add_to_cart", "depends_on": "login"}]
            
        Returns:
            链式调用结果
        """
        results = []
        context = {}  # 存储中间结果（如 token）
        
        for api_call in api_sequence:
            action = api_call.get("action")
            
            if action == "login":
                # 模拟登录获取 token
                response = API_TOOLS[0].invoke({
                    "method": "POST",
                    "endpoint": "/api/login",
                    "body": api_call.get("credentials", {})
                })
                
                # 假设响应中包含 token
                if response.get("status_code") == 200:
                    # 尝试从响应中提取 token
                    resp_body = response.get("body", {})
                    if isinstance(resp_body, dict):
                        token = resp_body.get("token") or resp_body.get("access_token") or resp_body.get("data", {}).get("token")
                        if token:
                            context["token"] = token
                            # 尝试提取 user_id
                            context["user_id"] = resp_body.get("user_id") or resp_body.get("data", {}).get("user_id")
                        else:
                            context["error"] = "Login successful but no token found in response"
                    else:
                        context["error"] = "Login response is not a dictionary"
            
            elif action == "add_to_cart":
                # 使用之前获取的 token
                headers = {"Authorization": f"Bearer {context.get('token', '')}"}
                response = API_TOOLS[0].invoke({
                    "method": "POST",
                    "endpoint": "/api/cart/add",
                    "headers": headers,
                    "body": api_call.get("data", {})
                })
                results.append(response)
            
            else:
                # 通用 API 调用
                response = API_TOOLS[0].invoke({
                    "method": api_call.get("method", "GET"),
                    "endpoint": api_call.get("endpoint", ""),
                    "headers": context.get("headers", {}),
                    "body": api_call.get("body")
                })
                results.append(response)
        
        return {
            "chain_results": results,
            "context": context,
            "status": "success"
        }
