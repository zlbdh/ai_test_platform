"""
GraphQL API testing service.

Supports:
- Query, mutation, and subscription testing
- Variables and fragments
- Introspection queries
- Assertion verification
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import json
import httpx
import asyncio


@dataclass
class GraphQLRequest:
    """GraphQL request"""
    query: str
    variables: Optional[Dict[str, Any]] = None
    operation_name: Optional[str] = None


@dataclass
class GraphQLResponse:
    """GraphQL response"""
    data: Optional[Dict[str, Any]]
    errors: Optional[List[Dict]]
    extensions: Optional[Dict[str, Any]]
    status_code: int
    response_time_ms: int


@dataclass
class GraphQLAssertion:
    """GraphQL assertion"""
    path: str  # e.g., "data.user.name"
    operator: str  # eq, ne, contains, exists, type
    expected: Any


class GraphQLTestService:
    """GraphQL testing service"""
    
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
        """Execute a GraphQL request"""
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
        """Get the GraphQL schema using introspection"""
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
        """Get a value by path"""
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
        """Verify the response"""
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
        """Run a test suite"""
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
        """Generate a query from the schema"""
        if not self.schema:
            return ""
        
        # Find the type
        type_def = None
        for t in self.schema.get("types", []):
            if t.get("name") == type_name:
                type_def = t
                break
        
        if not type_def or not type_def.get("fields"):
            return f"{{ {type_name.lower()} {{ id }} }}"
        
        # Generate fields
        fields = []
        for field in type_def.get("fields", [])[:10]:  # Limit the number of fields
            field_name = field.get("name")
            if not field_name.startswith("_"):
                fields.append(field_name)
        
        return f"{{ {type_name.lower()} {{ {' '.join(fields)} }} }}"


# Factory function
def create_graphql_service(
    endpoint: str,
    headers: Optional[Dict[str, str]] = None
) -> GraphQLTestService:
    """Create a GraphQL testing service"""
    return GraphQLTestService(endpoint, headers)
