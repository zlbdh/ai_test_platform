"""
Data Agent - 数据审计 Agent
负责数据一致性验证、事务验证、数据清理
"""
from typing import Dict, Any, List, Optional
from core.config import Config
from core.llm_manager import get_llm_for_role
from skills.data_tools import DATA_TOOLS, query_db_natural_language_tool


class DataAgent:
    """数据审计 Agent"""
    
    def __init__(self):
        """初始化 Data Agent"""
        self.llm = get_llm_for_role("executor")
        
        self.tools = DATA_TOOLS
    
    def execute_test(self, test_scenario: str, verification_rules: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        执行数据验证测试
        
        Args:
            test_scenario: 测试场景描述
            verification_rules: 验证规则列表
            
        Returns:
            验证结果
        """
        results = {
            "agent": "data_agent",
            "scenario": test_scenario,
            "verifications": [],
            "status": "success",
            "errors": []
        }
        
        try:
            # 根据场景执行不同的验证
            if "订单" in test_scenario or "order" in test_scenario.lower():
                # 验证订单创建
                order_result = self._verify_order_creation()
                results["verifications"].append(order_result)
            
            if "库存" in test_scenario or "inventory" in test_scenario.lower():
                # 验证库存扣减
                # 尝试从场景中提取 product_id
                import re
                product_match = re.search(r'(product|item|id)[_ ]?id[^\d]*(\d+)', test_scenario, re.IGNORECASE)
                product_id = int(product_match.group(2)) if product_match else None
                
                inventory_result = self._verify_inventory_deduction(product_id)
                results["verifications"].append(inventory_result)
            
            if "购物车" in test_scenario or "cart" in test_scenario.lower():
                # 验证购物车数据
                # 尝试从场景中提取 user_id
                import re
                user_match = re.search(r'(user|account)[_ ]?id[^\d]*(\d+)', test_scenario, re.IGNORECASE)
                user_id = int(user_match.group(2)) if user_match else None
                
                cart_result = self._verify_cart_data(user_id)
                results["verifications"].append(cart_result)
            
            # 执行自定义验证规则
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
        使用自然语言查询数据库
        
        Args:
            natural_language_query: 自然语言查询（如"查询张三的订单状态"）
            
        Returns:
            查询结果
        """
        return query_db_natural_language_tool.invoke({
            "natural_language_query": natural_language_query
        })
    
    def _verify_order_creation(self) -> Dict[str, Any]:
        """验证订单创建"""
        # 使用自然语言查询（Text-to-SQL）
        try:
            result = self.query_with_natural_language("查询最新的订单记录")
            if result.get("status") == "success" and result.get("results"):
                order = result["results"][0] if result["results"] else {}
                return {
                    "type": "order_creation",
                    "order_id": order.get("id"),
                    "status": order.get("status"),
                    "is_valid": order.get("status") in ["pending", "paid", "processing"],
                    "message": f"订单 {order.get('id')} 创建成功，状态：{order.get('status')}",
                    "method": "text_to_sql"
                }
        except Exception:
            pass
        
        # 如果 Text-to-SQL 失败，回退到传统 SQL
        query = "SELECT * FROM orders ORDER BY id DESC LIMIT 1"
        orders = DATA_TOOLS[0].invoke({"query": query})  # execute_query
        
        if orders and not orders[0].get("error"):
            order = orders[0]
            return {
                "type": "order_creation",
                "order_id": order.get("id"),
                "status": order.get("status"),
                "is_valid": order.get("status") in ["pending", "paid", "processing"],
                "message": f"订单 {order.get('id')} 创建成功，状态：{order.get('status')}"
            }
        else:
            return {
                "type": "order_creation",
                "is_valid": False,
                "message": "未找到订单记录"
            }
    
    def _verify_inventory_deduction(self, product_id: int = None) -> Dict[str, Any]:
        """验证库存扣减"""
        # 尝试动态获取 product_id
        if product_id is None:
            return {
                "type": "inventory_deduction",
                "is_valid": False,
                "message": "验证库存扣减失败：未提供 product_id"
            }
            
        # 查询库存表
        query = f"SELECT product_id, quantity FROM inventory WHERE product_id = {product_id}"
        inventory = DATA_TOOLS[0].invoke({"query": query})  # execute_query
        
        if inventory and not inventory[0].get("error"):
            item = inventory[0]
            return {
                "type": "inventory_deduction",
                "product_id": item.get("product_id"),
                "quantity": item.get("quantity"),
                "is_valid": item.get("quantity", 0) >= 0,
                "message": f"产品 {item.get('product_id')} 当前库存：{item.get('quantity')}"
            }
        else:
            return {
                "type": "inventory_deduction",
                "is_valid": False,
                "message": "未找到库存记录"
            }
    
    def _verify_cart_data(self, user_id: int = None) -> Dict[str, Any]:
        """验证购物车数据"""
        # 如果未提供 user_id，尝试默认或从上下文获取（此处需根据实际情况完善）
        if user_id is None:
             # 这里可以抛出异常或者返回提示，不再硬编码为 1
             return {
                "type": "cart_data",
                "is_valid": False,
                "message": "验证购物车失败：未提供 user_id"
            }
            
        query = f"SELECT * FROM cart WHERE user_id = {user_id}"
        cart_items = DATA_TOOLS[0].invoke({"query": query})  # execute_query
        
        return {
            "type": "cart_data",
            "item_count": len(cart_items) if cart_items and not cart_items[0].get("error") else 0,
            "is_valid": True,
            "message": f"购物车中有 {len(cart_items) if cart_items else 0} 件商品"
        }
    
    def _execute_verification_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """执行验证规则"""
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
        清理测试数据
        
        Args:
            cleanup_rules: 清理规则列表
            
        Returns:
            清理结果
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
