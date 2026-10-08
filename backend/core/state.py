"""
QA platform state definitions
Define shared state across the testing workflow
"""
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage


class QAState(TypedDict):
    """Global QA platform state"""
    # Task information
    task_description: Annotated[str, "Test task description"]
    test_scenario: Annotated[str, "Test scenario"]

    # Agent execution results
    ui_results: Annotated[List[Dict[str, Any]], "UI Agent execution results"]
    api_results: Annotated[List[Dict[str, Any]], "API Agent execution results"]
    data_results: Annotated[List[Dict[str, Any]], "Data Agent execution results"]
    ops_results: Annotated[List[Dict[str, Any]], "Ops Agent execution results"]

    # Workflow state
    current_step: Annotated[str, "Current execution step"]
    completed_steps: Annotated[List[str], "Completed steps"]
    failed_steps: Annotated[List[str], "Failed steps"]

    # Message history
    messages: Annotated[List[BaseMessage], "Messages exchanged between agents"]

    # Diagnostics
    errors: Annotated[List[Dict[str, Any]], "Error messages"]
    warnings: Annotated[List[str], "Warnings"]

    # Test data
    test_data: Annotated[Dict[str, Any], "Data generated during testing"]

    # Final report
    final_report: Annotated[Optional[Dict[str, Any]], "Final test report"]

    # Subgraph state for tracking subgraph execution
    subgraph_states: Annotated[Dict[str, Any], "Subgraph state tracking"]

    # Inspector visual review results
    inspection_results: Annotated[List[Dict[str, Any]], "Inspector review results"]

    # Healing context
    healing_context: Annotated[Optional[Dict[str, Any]], "Healing context information"]
