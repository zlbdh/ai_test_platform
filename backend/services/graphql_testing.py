"""
GraphQL Testing Service - GraphQL API 测试服务

支持 GraphQL API 的完整测试能力：
- Query/Mutation/Subscription 测试
- 变量和片段支持
- 自省查询 (Introspection)
- 断言验证
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import json
import httpx
import asyncio


@dataclass
class GraphQLRequest:
    """GraphQL 请求"""
    query: str
    variables: Optional[Dict[str, Any]] = None
    operation_name: Optional[str] = None


@dataclass
class GraphQLResponse:
    """GraphQL 响应"""
    data: Optional[Dict[str, Any]]
    errors: Optional[List[Dict]]
    extensions: Optional[Dict[str, Any]]
    status_code: int
    response_time_ms: int


@dataclass
class GraphQLAssertion:
    """GraphQL 断言"""
    path: str  # e.g., "data.user.name"
    operator: str  # eq, ne, contains, exists, type
    expected: Any


class GraphQLTestService:
    """GraphQL 测试服务"""
    
    def __init__(self, endpoint: str, headers: Optional[Dict[str, str]] = None):
        self.endpoint = endpoint
        self.headers = headers or {}
        self.headers.setdefault("Content-Type", "application/json")
        self.schema: Optional[Dict] = None
    
    async def execute(
        self,
        request: GraphQLRequest,
        timeout: float = 30.0
    ) -> GraphQLResponse:
        """执行 GraphQL 请求"""
        import time
        
        payload = {
            "query": request.query
        }
        if request.variables:
            payload["variables"] = request.variables
        if request.operation_name:
            payload["operationName"] = request.operation_name
        
        start = time.time()
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                self.endpoint,
                json=payload,
                headers=self.headers
            )
        
        elapsed = int((time.time() - start) * 1000)
        
        try:
            result = response.json()
        except Exception:
            result = {"errors": [{"message": "Invalid JSON response"}]}
        
        return GraphQLResponse(
            data=result.get("data"),
            errors=result.get("errors"),
            extensions=result.get("extensions"),
            status_code=response.status_code,
            response_time_ms=elapsed
        )
    
    async def introspect(self) -> Dict[str, Any]:
        """获取 GraphQL Schema (自省查询)"""
        introspection_query = """
        query IntrospectionQuery {
            __schema {
                queryType { name }
                mutationType { name }
                subscriptionType { name }
                types {
                    ...FullType
                }
            }
        }
        
        fragment FullType on __Type {
            kind
            name
            description
            fields(includeDeprecated: true) {
                name
                description
                args {
                    ...InputValue
                }
                type {
                    ...TypeRef
                }
                isDeprecated
                deprecationReason
            }
            inputFields {
                ...InputValue
            }
            interfaces {
                ...TypeRef
            }
            enumValues(includeDeprecated: true) {
                name
                description
                isDeprecated
                deprecationReason
            }
            possibleTypes {
                ...TypeRef
            }
        }
        
        fragment InputValue on __InputValue {
            name
            description
            type {
                ...TypeRef
            }
            defaultValue
        }
        
        fragment TypeRef on __Type {
            kind
            name
            ofType {
                kind
                name
                ofType {
                    kind
                    name
                    ofType {
                        kind
                        name
                    }
                }
            }
        }
        """
        
        request = GraphQLRequest(query=introspection_query)
        response = await self.execute(request)
        
        if response.data:
            self.schema = response.data.get("__schema")
        
        return self.schema or {}
    
    def _get_value_by_path(self, data: Dict, path: str) -> Any:
        """根据路径获取值"""
        keys = path.split(".")
        value = data
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            elif isinstance(value, list) and key.isdigit():
                value = value[int(key)]
            else:
                return None
        
        return value
    
    def assert_response(
        self,
        response: GraphQLResponse,
        assertions: List[GraphQLAssertion]
    ) -> List[Dict[str, Any]]:
        """验证响应"""
        results = []
        
        for assertion in assertions:
            actual = self._get_value_by_path(
                {"data": response.data, "errors": response.errors},
                assertion.path
            )
            
            passed = False
            message = ""
            
            if assertion.operator == "eq":
                passed = actual == assertion.expected
                message = f"Expected {assertion.expected}, got {actual}"
            
            elif assertion.operator == "ne":
                passed = actual != assertion.expected
                message = f"Expected not {assertion.expected}, got {actual}"
            
            elif assertion.operator == "contains":
                if isinstance(actual, str):
                    passed = assertion.expected in actual
                elif isinstance(actual, list):
                    passed = assertion.expected in actual
                message = f"Expected {actual} to contain {assertion.expected}"
            
            elif assertion.operator == "exists":
                passed = actual is not None
                message = f"Expected {assertion.path} to exist"
            
            elif assertion.operator == "type":
                actual_type = type(actual).__name__
                passed = actual_type == assertion.expected
                message = f"Expected type {assertion.expected}, got {actual_type}"
            
            results.append({
                "path": assertion.path,
                "operator": assertion.operator,
                "expected": assertion.expected,
                "actual": actual,
                "passed": passed,
                "message": message if not passed else "OK"
            })
        
        return results
    
    async def run_test_suite(
        self,
        tests: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """运行测试套件"""
        results = []
        total_passed = 0
        total_failed = 0
        
        for test in tests:
            request = GraphQLRequest(
                query=test["query"],
                variables=test.get("variables"),
                operation_name=test.get("operation_name")
            )
            
            response = await self.execute(request)
            
            assertions = [
                GraphQLAssertion(**a) for a in test.get("assertions", [])
            ]
            
            assertion_results = self.assert_response(response, assertions)
            
            passed = all(r["passed"] for r in assertion_results)
            if passed:
                total_passed += 1
            else:
                total_failed += 1
            
            results.append({
                "name": test.get("name", "Unnamed Test"),
                "passed": passed,
                "response_time_ms": response.response_time_ms,
                "status_code": response.status_code,
                "errors": response.errors,
                "assertions": assertion_results
            })
        
        return {
            "total": len(tests),
            "passed": total_passed,
            "failed": total_failed,
            "success_rate": total_passed / len(tests) if tests else 0,
            "results": results
        }
    
    def generate_query_from_schema(
        self,
        type_name: str,
        depth: int = 2
    ) -> str:
        """根据 Schema 自动生成查询"""
        if not self.schema:
            return ""
        
        # 查找类型
        type_def = None
        for t in self.schema.get("types", []):
            if t.get("name") == type_name:
                type_def = t
                break
        
        if not type_def or not type_def.get("fields"):
            return f"{{ {type_name.lower()} {{ id }} }}"
        
        # 生成字段
        fields = []
        for field in type_def.get("fields", [])[:10]:  # 限制字段数
            field_name = field.get("name")
            if not field_name.startswith("_"):
                fields.append(field_name)
        
        return f"{{ {type_name.lower()} {{ {' '.join(fields)} }} }}"


# 工厂函数
def create_graphql_service(
    endpoint: str,
    headers: Optional[Dict[str, str]] = None
) -> GraphQLTestService:
    """创建 GraphQL 测试服务"""
    return GraphQLTestService(endpoint, headers)
