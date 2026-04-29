# -*- coding: utf-8 -*-
import inspect
from typing import Any, Callable, Dict, List, Optional, Type
from pydantic import BaseModel, create_model

class ActionRegistry:
    """工具注册表，用于管理和生成 Agent 可用的工具"""
    
    def __init__(self):
        self.actions: Dict[str, Dict[str, Any]] = {}
        
    def action(self, description: str, param_model: Optional[Type[BaseModel]] = None):
        """装饰器：注册一个工具"""
        def decorator(func: Callable):
            tool_name = func.__name__
            
            # 如果没有提供 param_model，尝试从函数签名推断 (简化版)
            # 完整版应该使用 inspect 生成动态 Pydantic model
            model = param_model
            
            self.actions[tool_name] = {
                "name": tool_name,
                "description": description,
                "func": func,
                "param_model": model
            }
            return func
        return decorator

    def get_prompt_description(self) -> str:
        """生成用于 System Prompt 的工具描述表格"""
        table = "| 工具名称 | 参数 (JSON Key) | 说明 |\n"
        table += "| :--- | :--- | :--- |\n"
        
        for name, info in self.actions.items():
            param_str = ""
            if info["param_model"]:
                # 获取 Pydantic model 的字段
                fields = info["param_model"].model_fields.keys()
                param_str = ", ".join([f"`{f}`" for f in fields])
            else:
                # 尝试从函数注解获取
                sig = inspect.signature(info["func"])
                params = [p for p in sig.parameters if p != 'self']
                param_str = ", ".join([f"`{p}`" for p in params])
                
            table += f"| `{name}` | {param_str} | {info['description']} |\n"
            
        return table

    def get_tool(self, name: str) -> Optional[Callable]:
        """获取工具函数"""
        if name in self.actions:
            return self.actions[name]["func"]
        return None

# 全局注册表实例
registry = ActionRegistry()
