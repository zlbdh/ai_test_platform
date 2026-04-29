"""
子图管理 - 统一管理所有子图
"""
from workflows.ui_healing_subgraph import UIHealingSubgraph, get_healing_subgraph
from workflows.api_fuzzing_subgraph import APIFuzzingSubgraph, get_fuzzing_subgraph


def create_ui_healing_subgraph() -> UIHealingSubgraph:
    """创建 UI 自愈子图"""
    return get_healing_subgraph()


def create_api_fuzzing_subgraph() -> APIFuzzingSubgraph:
    """创建 API 模糊测试子图"""
    return get_fuzzing_subgraph()


# 子图注册表
SUBGRAPHS = {
    "ui_healing": create_ui_healing_subgraph,
    "api_fuzzing": create_api_fuzzing_subgraph,
}


def get_subgraph(name: str):
    """
    获取子图
    
    Args:
        name: 子图名称 (ui_healing, api_fuzzing)
        
    Returns:
        子图实例
    """
    if name not in SUBGRAPHS:
        raise ValueError(f"未知的子图名称: {name}")
    
    return SUBGRAPHS[name]()
