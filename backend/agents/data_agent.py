"""
Data Agent - data auditing agent
Handles data consistency checks, transaction validation, and data cleanup
"""
from typing import Dict, Any, List, Optional
from core.config import Config
from core.llm_manager import get_llm_for_role
from skills.data_tools import DATA_TOOLS, query_db_natural_language_tool


class DataAgent:
    """Data auditing agent"""

    def __init__(self):
        """Initialize Data Agent"""
        self.llm = get_llm_for_role("executor")

        self.tools = DATA_TOOLS

    def execute_test(self, test_scenario: str, verification_rules: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Run data validation tests

        Args:
            test_scenario: Test scenario description
            verification_rules: List of validation rules

        Returns:
            Validation result
        """
        results = {
            "agent": "data_agent",
            "scenario": test_scenario,
            "verifications": [],
            "status": "success",
            "errors": []
        }

        try:
            # Run different validation checks based on the scenario
            if "订单" in test_scenario or "order" in test_scenario.lower():
                # Verify order creation
                order_result = self._verify_order_creation()
                results["verifications"].append(order_result)

            if "库存" in test_scenario or "inventory" in test_scenario.lower():
                # Verify inventory deduction
                # Try to extract product_id from the scenario
                import re
                product_match = re.search(r'(product|item|id)[_ ]?id[^\d]*(\d+)', test_scenario, re.IGNORECASE)
                product_id = int(product_match.group(2)) if product_match else None

                inventory_result = self._verify_inventory_deduction(product_id)
                results["verifications"].append(inventory_result)

            if "购物车" in test_scenario or "cart" in test_scenario.lower():
                # Validate cart data
                # Try to extract user_id from the scenario
                import re
                user_match = re.search(r'(user|account)[_ ]?id[^\d]*(\d+)', test_scenario, re.IGNORECASE)
                user_id = int(user_match.group(2)) if user_match else None

                cart_result = self._verify_cart_data(user_id)
                results["verifications"].append(cart_result)

            # Execute custom validation rules
            if verification_rules:
                for rule in verification_rules:
                    verification = self._execute_verification_rule(rule)
                    results["verifications"].append(verification)

        except Exception as e:
            results["status"] = "error"
            results["errors"].append(str(e))

        return results

    def query_with_natural_language(self, natural_language_query: str) -> Dict[str, Any]:
        """
        Query the database with natural language

        Args:
            natural_language_query: Natural-language query (such as "Get Zhang San's order status")

        Returns:
            Query results
        """
        return query_db_natural_language_tool.invoke({
            "natural_language_query": natural_language_query
        })

    def _verify_order_creation(self) -> Dict[str, Any]:
        """Verify order creation"""
        # Use a natural-language query (Text-to-SQL)
        try:
            result = self.query_with_natural_language("Query the latest order record")
            if result.get("status") == "success" and result.get("results"):
                order = result["results"][0] if result["results"] else {}
                return {
                    "type": "order_creation",
                    "order_id": order.get("id"),
                    "status": order.get("status"),
                    "is_valid": order.get("status") in ["pending", "paid", "processing"],
                    "message": f"Order {order.get('id')} created successfully; status: {order.get('status')}",
                    "method": "text_to_sql"
                }
        except Exception:
            pass

        # Fall back to conventional SQL if Text-to-SQL fails
        query = "SELECT * FROM orders ORDER BY id DESC LIMIT 1"
        orders = DATA_TOOLS[0].invoke({"query": query})  # execute_query

        if orders and not orders[0].get("error"):
            order = orders[0]
            return {
                "type": "order_creation",
                "order_id": order.get("id"),
                "status": order.get("status"),
                "is_valid": order.get("status") in ["pending", "paid", "processing"],
                "message": f"Order {order.get('id')} created successfully; status: {order.get('status')}"
            }
        else:
            return {
                "type": "order_creation",
                "is_valid": False,
                "message": "No order record found"
            }

    def _verify_inventory_deduction(self, product_id: int = None) -> Dict[str, Any]:
        """Verify inventory deduction"""
        # Try to obtain product_id dynamically
        if product_id is None:
            return {
                "type": "inventory_deduction",
                "is_valid": False,
                "message": "Cannot verify inventory deduction: product_id was not provided"
            }

        # Query the inventory table
        query = f"SELECT product_id, quantity FROM inventory WHERE product_id = {product_id}"
        inventory = DATA_TOOLS[0].invoke({"query": query})  # execute_query

        if inventory and not inventory[0].get("error"):
            item = inventory[0]
            return {
                "type": "inventory_deduction",
                "product_id": item.get("product_id"),
                "quantity": item.get("quantity"),
                "is_valid": item.get("quantity", 0) >= 0,
                "message": f"Current stock for product {item.get('product_id')}: {item.get('quantity')}"
            }
        else:
            return {
                "type": "inventory_deduction",
                "is_valid": False,
                "message": "No inventory record found"
            }

    def _verify_cart_data(self, user_id: int = None) -> Dict[str, Any]:
        """Validate cart data"""
        # If user_id is missing, try a default or obtain it from context (adapt to the actual use case)
        if user_id is None:
             # Raise an exception or return a message here instead of hardcoding 1
             return {
                "type": "cart_data",
                "is_valid": False,
                "message": "Cart validation failed: user_id was not provided"
            }

        query = f"SELECT * FROM cart WHERE user_id = {user_id}"
        cart_items = DATA_TOOLS[0].invoke({"query": query})  # execute_query

        return {
            "type": "cart_data",
            "item_count": len(cart_items) if cart_items and not cart_items[0].get("error") else 0,
            "is_valid": True,
            "message": f"The cart contains {len(cart_items) if cart_items else 0} items"
        }

    def _execute_verification_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a validation rule"""
        rule_type = rule.get("type")

        if rule_type == "consistency":
            return DATA_TOOLS[1].invoke({
                "table": rule.get("table"),
                "condition": rule.get("condition"),
                "expected_count": rule.get("expected_count")
            })  # verify_data_consistency

        elif rule_type == "transaction":
            return DATA_TOOLS[4].invoke({
                "table": rule.get("table"),
                "transaction_id": rule.get("transaction_id"),
                "expected_status": rule.get("expected_status")
            })  # verify_transaction

        return {"status": "unknown_rule_type"}

    def cleanup_test_data(self, cleanup_rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Clean up test data

        Args:
            cleanup_rules: List of cleanup rules

        Returns:
            Cleanup result
        """
        results = {
            "cleaned_tables": [],
            "total_affected_rows": 0
        }

        for rule in cleanup_rules:
            cleanup_result = DATA_TOOLS[5].invoke({
                "table": rule.get("table"),
                "condition": rule.get("condition")
            })  # cleanup_test_data

            results["cleaned_tables"].append(cleanup_result)
            results["total_affected_rows"] += cleanup_result.get("affected_rows", 0)

        return results
