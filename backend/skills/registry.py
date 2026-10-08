# -*- coding: utf-8 -*-
import inspect
from typing import Any, Callable, Dict, List, Optional, Type
from pydantic import BaseModel, create_model

class ActionRegistry:
    """Tool registry for managing and generating tools available to agents"""

    def __init__(self):
        self.actions: Dict[str, Dict[str, Any]] = {}

    def action(self, description: str, param_model: Optional[Type[BaseModel]] = None):
        """Decorator that registers a tool"""
        def decorator(func: Callable):
            tool_name = func.__name__

            # If param_model is omitted, try to infer it from the function signature (simplified)
            # A complete implementation should use inspect to generate a dynamic Pydantic model
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
        """Generate a tool description table for the system prompt"""
        table = "| Tool name | Parameters (JSON key) | Description |\n"
        table += "| :--- | :--- | :--- |\n"

        for name, info in self.actions.items():
            param_str = ""
            if info["param_model"]:
                # Get Pydantic model fields
                fields = info["param_model"].model_fields.keys()
                param_str = ", ".join([f"`{f}`" for f in fields])
            else:
                # Try to obtain parameters from function annotations
                sig = inspect.signature(info["func"])
                params = [p for p in sig.parameters if p != 'self']
                param_str = ", ".join([f"`{p}`" for p in params])

            table += f"| `{name}` | {param_str} | {info['description']} |\n"

        return table

    def get_tool(self, name: str) -> Optional[Callable]:
        """Get a tool function"""
        if name in self.actions:
            return self.actions[name]["func"]
        return None

# Global registry instance
registry = ActionRegistry()
