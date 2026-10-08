"""
Schemathesis integration - API fuzz testing
"""
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
import requests
from core.config import Config


@tool
def fuzz_with_schemathesis(swagger_url: str, endpoint: Optional[str] = None,
                          max_test_cases: int = 50) -> Dict[str, Any]:
    """
    Run API fuzz tests with Schemathesis

    Args:
        swagger_url: Swagger/OpenAPI document URL
        endpoint: Optional endpoint to test (such as /api/users)
        max_test_cases: Maximum test case count

    Returns:
        Fuzz testing results
    """
    try:
        # Check whether schemathesis is installed
        try:
            import schemathesis
        except ImportError:
            return {
                "status": "error",
                "error": "Schemathesis is not installed; run: pip install schemathesis"
            }

        # Run tests with Schemathesis
        # Note: this implementation is simplified; a full implementation should use all Schemathesis features

        # Get the Swagger document
        response = requests.get(swagger_url, timeout=Config.API_TIMEOUT)
        swagger_doc = response.json()

        # Run tests with schemathesis
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

        # Run tests
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

                # Check for vulnerabilities
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
    Automatically generate Schemathesis test cases from a Swagger document

    Args:
        swagger_url: Swagger document URL

    Returns:
        List of generated test cases
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


# Tool list
SCHEMATHESIS_TOOLS = [
    fuzz_with_schemathesis,
    generate_schemathesis_tests,
]
