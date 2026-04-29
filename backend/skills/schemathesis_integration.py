"""
Schemathesis 集成 - API 模糊测试
"""
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
import requests
from core.config import Config


@tool
def fuzz_with_schemathesis(swagger_url: str, endpoint: Optional[str] = None, 
                          max_test_cases: int = 50) -> Dict[str, Any]:
    """
    使用 Schemathesis 进行 API 模糊测试
    
    Args:
        swagger_url: Swagger/OpenAPI 文档 URL
        endpoint: 可选，指定要测试的端点（如 /api/users）
        max_test_cases: 最大测试用例数
        
    Returns:
        模糊测试结果
    """
    try:
        # 检查是否安装了 schemathesis
        try:
            import schemathesis
        except ImportError:
            return {
                "status": "error",
                "error": "Schemathesis 未安装，请运行: pip install schemathesis"
            }
        
        # 使用 Schemathesis 进行测试
        # 注意：这里简化实现，实际应该使用 schemathesis 的完整功能
        
        # 获取 Swagger 文档
        response = requests.get(swagger_url, timeout=Config.API_TIMEOUT)
        swagger_doc = response.json()
        
        # 使用 schemathesis 运行测试
        schema = schemathesis.from_dict(swagger_doc)
        
        results = {
            "status": "success",
            "swagger_url": swagger_url,
            "endpoint": endpoint,
            "test_cases": [],
            "vulnerabilities": [],
            "total_tests": 0,
            "passed": 0,
            "failed": 0
        }
        
        # 运行测试
        for case in schema[endpoint].parametrize()[:max_test_cases]:
            results["total_tests"] += 1
            try:
                response = case.call()
                
                test_result = {
                    "endpoint": case.operation.path,
                    "method": case.operation.method,
                    "status_code": response.status_code,
                    "passed": response.status_code < 500
                }
                
                # 检查是否有漏洞
                if response.status_code >= 500:
                    results["failed"] += 1
                    results["vulnerabilities"].append({
                        "endpoint": case.operation.path,
                        "method": case.operation.method,
                        "status_code": response.status_code,
                        "response": response.text[:200] if response.text else "",
                        "severity": "high" if response.status_code == 500 else "medium"
                    })
                else:
                    results["passed"] += 1
                
                results["test_cases"].append(test_result)
                
            except Exception as e:
                results["failed"] += 1
                results["test_cases"].append({
                    "endpoint": case.operation.path if hasattr(case, 'operation') else "unknown",
                    "error": str(e),
                    "passed": False
                })
        
        return results
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@tool
def generate_schemathesis_tests(swagger_url: str) -> List[Dict[str, Any]]:
    """
    从 Swagger 文档自动生成 Schemathesis 测试用例
    
    Args:
        swagger_url: Swagger 文档 URL
        
    Returns:
        生成的测试用例列表
    """
    try:
        import schemathesis
        
        response = requests.get(swagger_url, timeout=Config.API_TIMEOUT)
        swagger_doc = response.json()
        
        schema = schemathesis.from_dict(swagger_doc)
        
        test_cases = []
        
        for endpoint_path, methods in swagger_doc.get("paths", {}).items():
            for method, details in methods.items():
                if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    test_cases.append({
                        "endpoint": endpoint_path,
                        "method": method.upper(),
                        "summary": details.get("summary", ""),
                        "parameters": details.get("parameters", []),
                        "testable": True
                    })
        
        return {
            "status": "success",
            "swagger_url": swagger_url,
            "test_cases": test_cases,
            "total": len(test_cases)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


# 工具列表
SCHEMATHESIS_TOOLS = [
    fuzz_with_schemathesis,
    generate_schemathesis_tests,
]
