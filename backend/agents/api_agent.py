"""
API Agent - backend testing agent
Handles API testing, security scanning, and parameter validation
"""
from typing import Dict, Any, List, Optional
from core.config import Config
from core.llm_manager import get_llm_for_role
from skills.api_tools import API_TOOLS


class APIAgent:
    """API testing agent"""

    def __init__(self):
        """Initialize API Agent"""
        self.llm = get_llm_for_role("executor")

        self.tools = API_TOOLS

    def execute_test(self, test_scenario: str, swagger_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Run API tests

        Args:
            test_scenario: Test scenario description
            swagger_url: Swagger document URL (optional)

        Returns:
            Test results
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
            # 1. Parse the Swagger document if provided
            if swagger_url:
                swagger_info = API_TOOLS[1].invoke({"swagger_url": swagger_url})  # parse_swagger
                results["swagger_info"] = swagger_info
                endpoints = swagger_info.get("endpoints", [])
            else:
                # If Swagger is unavailable, try to extract a URL from the scenario or report an error
                # Remove hardcoded demo endpoints to use the actual environment
                import re
                url_matches = re.findall(r'https?://[^\s]+', test_scenario)
                if url_matches:
                    endpoints = [{"path": url, "method": "GET"} for url in url_matches]
                else:
                    results["status"] = "warning"
                    results["errors"].append("No Swagger URL was provided and no URL could be extracted from the scenario")
                    endpoints = []

            # 2. Test each endpoint
            for endpoint in endpoints[:3]:  # Limit the number of tests
                path = endpoint.get("path", "")
                method = endpoint.get("method", "GET")

                # Generate test data
                test_data = API_TOOLS[2].invoke({"data_type": "number", "count": 1})  # generate_test_data

                # Call the endpoint
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

                # 3. Security scanning
                if "cart" in path.lower() or "order" in path.lower():
                    auth_check = API_TOOLS[5].invoke({  # check_auth (Index may change)
                        "endpoint": path,
                        "method": method,
                        "requires_auth": True
                    })

                    results["security_scan"].append(auth_check)

                    # Use the fuzzing subgraph for deeper testing
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
                        # Use basic fuzz testing if the subgraph fails
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
        Chain API calls while handling dependencies

        Args:
            api_sequence: API call sequence, such as [{"action": "login"}, {"action": "add_to_cart", "depends_on": "login"}]

        Returns:
            Chained call results
        """
        results = []
        context = {}  # Store intermediate results such as tokens

        for api_call in api_sequence:
            action = api_call.get("action")

            if action == "login":
                # Simulate login to obtain a token
                response = API_TOOLS[0].invoke({
                    "method": "POST",
                    "endpoint": "/api/login",
                    "body": api_call.get("credentials", {})
                })

                # Assume the response contains a token
                if response.get("status_code") == 200:
                    # Try to extract a token from the response
                    resp_body = response.get("body", {})
                    if isinstance(resp_body, dict):
                        token = resp_body.get("token") or resp_body.get("access_token") or resp_body.get("data", {}).get("token")
                        if token:
                            context["token"] = token
                            # Try to extract user_id
                            context["user_id"] = resp_body.get("user_id") or resp_body.get("data", {}).get("user_id")
                        else:
                            context["error"] = "Login successful but no token found in response"
                    else:
                        context["error"] = "Login response is not a dictionary"

            elif action == "add_to_cart":
                # Use the previously obtained token
                headers = {"Authorization": f"Bearer {context.get('token', '')}"}
                response = API_TOOLS[0].invoke({
                    "method": "POST",
                    "endpoint": "/api/cart/add",
                    "headers": headers,
                    "body": api_call.get("data", {})
                })
                results.append(response)

            else:
                # General API call
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
