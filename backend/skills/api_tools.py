"""
API 测试工具
用于接口测试、参数生成、安全扫描等
"""
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
import requests
import json
from core.config import Config
from skills.schemathesis_integration import fuzz_with_schemathesis


@tool
def call_api(method: str, endpoint: str, params: Optional[Dict] = None, 
              headers: Optional[Dict] = None, body: Optional[Dict] = None) -> Dict[str, Any]:
    """
    调用 API 接口
    
    Args:
        method: HTTP 方法 (GET, POST, PUT, DELETE)
        endpoint: API 端点路径
        params: URL 参数
        headers: 请求头
        body: 请求体
        
    Returns:
        API 响应结果
    """
    try:
        url = f"{Config.API_BASE_URL}{endpoint}"
        
        response = requests.request(
            method=method.upper(),
            url=url,
            params=params,
            headers=headers or {},
            json=body,
            timeout=Config.API_TIMEOUT
        )
        
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
            "url": url
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@tool
def parse_swagger(swagger_url: str) -> Dict[str, Any]:
    """
    解析 Swagger/OpenAPI 文档
    
    Args:
        swagger_url: Swagger JSON 文档的 URL
        
    Returns:
        解析后的 API 信息
    """
    try:
        response = requests.get(swagger_url, timeout=Config.API_TIMEOUT)
        swagger_doc = response.json()
        
        # 提取所有端点
        endpoints = []
        paths = swagger_doc.get("paths", {})
        
        for path, methods in paths.items():
            for method, details in methods.items():
                endpoints.append({
                    "path": path,
                    "method": method.upper(),
                    "summary": details.get("summary", ""),
                    "parameters": details.get("parameters", []),
                    "requestBody": details.get("requestBody", {}),
                    "responses": details.get("responses", {})
                })
        
        return {
            "info": swagger_doc.get("info", {}),
            "endpoints": endpoints,
            "total": len(endpoints)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@tool
def generate_test_data(data_type: str, count: int = 1, include_boundary: bool = True) -> List[Dict[str, Any]]:
    """
    生成测试数据（正常值、边界值、异常值）- 增强版
    
    Args:
        data_type: 数据类型 (email, phone, number, string, sql_injection, xss, integer, float, date, url)
        count: 生成数量
        include_boundary: 是否包含边界值
        
    Returns:
        生成的测试数据列表
    """
    test_data = []
    
    for i in range(count):
        if data_type == "email":
            test_data.append({"value": f"test{i}@example.com", "type": "normal"})
            test_data.append({"value": "invalid-email", "type": "invalid"})
            test_data.append({"value": f"test+{i}@example.co.uk", "type": "normal"})
            if include_boundary:
                test_data.append({"value": "a" * 250 + "@example.com", "type": "boundary"})  # 超长邮箱
        elif data_type == "phone":
            test_data.append({"value": f"1380013800{i}", "type": "normal"})
            test_data.append({"value": "abc", "type": "invalid"})
            if include_boundary:
                test_data.append({"value": "1" * 20, "type": "boundary"})  # 超长号码
        elif data_type == "number" or data_type == "integer":
            test_data.append({"value": 100, "type": "normal"})
            if include_boundary:
                test_data.append({"value": -1, "type": "boundary"})
                test_data.append({"value": 0, "type": "boundary"})
                test_data.append({"value": 2147483647, "type": "boundary"})  # INT_MAX
                test_data.append({"value": -2147483648, "type": "boundary"})  # INT_MIN
        elif data_type == "float":
            test_data.append({"value": 100.5, "type": "normal"})
            if include_boundary:
                test_data.append({"value": 0.0, "type": "boundary"})
                test_data.append({"value": -1.0, "type": "boundary"})
                test_data.append({"value": 1.7976931348623157e+308, "type": "boundary"})  # FLOAT_MAX
        elif data_type == "string":
            test_data.append({"value": f"test_string_{i}", "type": "normal"})
            if include_boundary:
                test_data.append({"value": "", "type": "boundary"})  # 空字符串
                test_data.append({"value": "A" * 10000, "type": "boundary"})  # 超长字符串
                test_data.append({"value": "测试中文", "type": "normal"})  # Unicode
        elif data_type == "sql_injection":
            test_data.append({"value": "1' OR '1'='1", "type": "attack"})
            test_data.append({"value": "'; DROP TABLE users; --", "type": "attack"})
            test_data.append({"value": "1' UNION SELECT * FROM users--", "type": "attack"})
        elif data_type == "xss":
            test_data.append({"value": "<script>alert('XSS')</script>", "type": "attack"})
            test_data.append({"value": "<img src=x onerror=alert(1)>", "type": "attack"})
            test_data.append({"value": "javascript:alert(1)", "type": "attack"})
        elif data_type == "date":
            test_data.append({"value": "2024-01-01", "type": "normal"})
            if include_boundary:
                test_data.append({"value": "1900-01-01", "type": "boundary"})
                test_data.append({"value": "2099-12-31", "type": "boundary"})
                test_data.append({"value": "invalid-date", "type": "invalid"})
        elif data_type == "url":
            test_data.append({"value": f"https://example.com/page{i}", "type": "normal"})
            if include_boundary:
                test_data.append({"value": "not-a-url", "type": "invalid"})
                test_data.append({"value": "javascript:alert(1)", "type": "attack"})
        else:
            test_data.append({"value": f"test_string_{i}", "type": "normal"})
    
    return test_data[:count * (3 if include_boundary else 2)]  # 返回正常值、边界值和异常值


@tool
def fuzz_api(endpoint: str, method: str = "POST", base_params: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """
    对 API 进行模糊测试（Fuzzing）
    
    Args:
        endpoint: API 端点
        method: HTTP 方法
        base_params: 基础参数
        
    Returns:
        模糊测试结果列表
    """
    results = []
    base_params = base_params or {}
    
    # 生成各种攻击载荷
    attack_payloads = [
        {"type": "sql_injection", "value": "1' OR '1'='1"},
        {"type": "xss", "value": "<script>alert(1)</script>"},
        {"type": "command_injection", "value": "; ls -la"},
        {"type": "path_traversal", "value": "../../../etc/passwd"},
        {"type": "null_byte", "value": "\x00"},
        {"type": "overflow", "value": "A" * 10000},
    ]
    
    for payload in attack_payloads:
        test_params = {**base_params, "test_field": payload["value"]}
        result = call_api.invoke({
            "method": method,
            "endpoint": endpoint,
            "body": test_params
        })
        
        results.append({
            "payload_type": payload["type"],
            "payload": payload["value"],
            "response": result,
            "vulnerable": result.get("status_code", 0) == 200 and "error" not in str(result).lower()
        })
    
    return results


@tool
def check_auth(endpoint: str, method: str = "GET", requires_auth: bool = True) -> Dict[str, Any]:
    """
    检查接口是否需要认证
    
    Args:
        endpoint: API 端点
        method: HTTP 方法
        requires_auth: 是否应该需要认证
        
    Returns:
        认证检查结果
    """
    # 不带 token 的请求
    response_no_auth = call_api.invoke({
        "method": method,
        "endpoint": endpoint
    })
    
    # 带无效 token 的请求
    response_invalid_auth = call_api.invoke({
        "method": method,
        "endpoint": endpoint,
        "headers": {"Authorization": "Bearer invalid_token"}
    })
    
    no_auth_status = response_no_auth.get("status_code", 0)
    invalid_auth_status = response_invalid_auth.get("status_code", 0)
    
    # 判断是否存在认证漏洞
    is_vulnerable = False
    if requires_auth:
        # 如果应该需要认证，但未认证也能访问，则存在漏洞
        if no_auth_status == 200:
            is_vulnerable = True
    
    return {
        "endpoint": endpoint,
        "requires_auth": requires_auth,
        "no_auth_status": no_auth_status,
        "invalid_auth_status": invalid_auth_status,
        "is_vulnerable": is_vulnerable,
        "vulnerability": "认证绕过漏洞" if is_vulnerable else "正常"
    }


@tool
def fuzz_with_schemathesis_tool(swagger_url: str, endpoint: Optional[str] = None, 
                                 max_test_cases: int = 50) -> Dict[str, Any]:
    """
    使用 Schemathesis 进行 API 模糊测试（工具包装）
    
    Args:
        swagger_url: Swagger 文档 URL
        endpoint: 可选，指定端点
        max_test_cases: 最大测试用例数
        
    Returns:
        模糊测试结果
    """
    return fuzz_with_schemathesis.invoke({
        "swagger_url": swagger_url,
        "endpoint": endpoint,
        "max_test_cases": max_test_cases
    })


@tool
def assert_response_schema(response: Dict[str, Any], expected_schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    基于 JSON Schema 验证响应
    
    Args:
        response: API 响应（包含 status_code, body 等）
        expected_schema: 期望的 JSON Schema
        
    Returns:
        验证结果
    """
    try:
        from jsonschema import validate, ValidationError
        
        body = response.get("body", {})
        
        try:
            validate(instance=body, schema=expected_schema)
            return {
                "status": "success",
                "valid": True,
                "message": "响应符合 Schema"
            }
        except ValidationError as e:
            return {
                "status": "error",
                "valid": False,
                "message": f"响应不符合 Schema: {str(e)}",
                "validation_error": str(e)
            }
    except ImportError:
        return {
            "status": "error",
            "error": "jsonschema 未安装，请运行: pip install jsonschema"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


# 工具列表
API_TOOLS = [
    call_api,
    parse_swagger,
    generate_test_data,
    fuzz_api,
    fuzz_with_schemathesis_tool,  # 新增
    check_auth,
    assert_response_schema,  # 新增
]
