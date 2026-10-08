"""
API testing tools
For API testing, parameter generation, security scanning, and related tasks
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
    Call an API endpoint

    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        endpoint: API endpoint path
        params: URL parameters
        headers: Request headers
        body: Request body

    Returns:
        API response result
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
    Parse a Swagger/OpenAPI document

    Args:
        swagger_url: URL of the Swagger JSON document

    Returns:
        Parsed API information
    """
    try:
        response = requests.get(swagger_url, timeout=Config.API_TIMEOUT)
        swagger_doc = response.json()

        # Extract all endpoints
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
    Generate test data (normal, boundary, and invalid values) - enhanced version

    Args:
        data_type: Data type (email, phone, number, string, sql_injection, xss, integer, float, date, url)
        count: Number to generate
        include_boundary: Whether to include boundary values

    Returns:
        List of generated test data
    """
    test_data = []

    for i in range(count):
        if data_type == "email":
            test_data.append({"value": f"test{i}@example.com", "type": "normal"})
            test_data.append({"value": "invalid-email", "type": "invalid"})
            test_data.append({"value": f"test+{i}@example.co.uk", "type": "normal"})
            if include_boundary:
                test_data.append({"value": "a" * 250 + "@example.com", "type": "boundary"})  # Overly long email address
        elif data_type == "phone":
            test_data.append({"value": f"1380013800{i}", "type": "normal"})
            test_data.append({"value": "abc", "type": "invalid"})
            if include_boundary:
                test_data.append({"value": "1" * 20, "type": "boundary"})  # Overly long phone number
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
                test_data.append({"value": "", "type": "boundary"})  # Empty string
                test_data.append({"value": "A" * 10000, "type": "boundary"})  # Overly long string
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

    return test_data[:count * (3 if include_boundary else 2)]  # Return normal, boundary, and invalid values


@tool
def fuzz_api(endpoint: str, method: str = "POST", base_params: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """
    Perform API fuzz testing

    Args:
        endpoint: API endpoint
        method: HTTP method
        base_params: Base parameters

    Returns:
        List of fuzz testing results
    """
    results = []
    base_params = base_params or {}

    # Generate various attack payloads
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
    Check whether an endpoint requires authentication

    Args:
        endpoint: API endpoint
        method: HTTP method
        requires_auth: Whether authentication should be required

    Returns:
        Authentication check result
    """
    # Request without a token
    response_no_auth = call_api.invoke({
        "method": method,
        "endpoint": endpoint
    })

    # Request with an invalid token
    response_invalid_auth = call_api.invoke({
        "method": method,
        "endpoint": endpoint,
        "headers": {"Authorization": "Bearer invalid_token"}
    })

    no_auth_status = response_no_auth.get("status_code", 0)
    invalid_auth_status = response_invalid_auth.get("status_code", 0)

    # Determine whether an authentication vulnerability exists
    is_vulnerable = False
    if requires_auth:
        # Access without authentication is a vulnerability when authentication is required
        if no_auth_status == 200:
            is_vulnerable = True

    return {
        "endpoint": endpoint,
        "requires_auth": requires_auth,
        "no_auth_status": no_auth_status,
        "invalid_auth_status": invalid_auth_status,
        "is_vulnerable": is_vulnerable,
        "vulnerability": "Authentication bypass vulnerability" if is_vulnerable else "Normal"
    }


@tool
def fuzz_with_schemathesis_tool(swagger_url: str, endpoint: Optional[str] = None,
                                 max_test_cases: int = 50) -> Dict[str, Any]:
    """
    Run API fuzz tests with Schemathesis (tool wrapper)

    Args:
        swagger_url: Swagger document URL
        endpoint: Optional specific endpoint
        max_test_cases: Maximum test case count

    Returns:
        Fuzz testing results
    """
    return fuzz_with_schemathesis.invoke({
        "swagger_url": swagger_url,
        "endpoint": endpoint,
        "max_test_cases": max_test_cases
    })


@tool
def assert_response_schema(response: Dict[str, Any], expected_schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a response against JSON Schema

    Args:
        response: API response (including status_code, body, and other fields)
        expected_schema: Expected JSON Schema

    Returns:
        Validation result
    """
    try:
        from jsonschema import validate, ValidationError

        body = response.get("body", {})

        try:
            validate(instance=body, schema=expected_schema)
            return {
                "status": "success",
                "valid": True,
                "message": "Response conforms to the schema"
            }
        except ValidationError as e:
            return {
                "status": "error",
                "valid": False,
                "message": f"Response does not conform to the schema: {str(e)}",
                "validation_error": str(e)
            }
    except ImportError:
        return {
            "status": "error",
            "error": "jsonschema is not installed; run: pip install jsonschema"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


# Tool list
API_TOOLS = [
    call_api,
    parse_swagger,
    generate_test_data,
    fuzz_api,
    fuzz_with_schemathesis_tool,  # Added
    check_auth,
    assert_response_schema,  # Added
]
