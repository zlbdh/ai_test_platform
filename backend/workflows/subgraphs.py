"""
Subgraph management - central management for all subgraphs
"""
from workflows.ui_healing_subgraph import UIHealingSubgraph, get_healing_subgraph
from workflows.api_fuzzing_subgraph import APIFuzzingSubgraph, get_fuzzing_subgraph


def create_ui_healing_subgraph() -> UIHealingSubgraph:
    """Create a UI healing subgraph"""
    return get_healing_subgraph()


def create_api_fuzzing_subgraph() -> APIFuzzingSubgraph:
    """Create an API fuzzing subgraph"""
    return get_fuzzing_subgraph()


# Subgraph registry
SUBGRAPHS = {
    "ui_healing": create_ui_healing_subgraph,
    "api_fuzzing": create_api_fuzzing_subgraph,
}


def get_subgraph(name: str):
    """
    Get a subgraph
    
    Args:
        name: Subgraph name (ui_healing, api_fuzzing)
        
    Returns:
        Subgraph instance
    """
    if name not in SUBGRAPHS:
        raise ValueError(f"Unknown subgraph name: {name}")
    
    return SUBGRAPHS[name]()
