from typing import TypedDict, List, Dict, Optional, Any

class TestStep(TypedDict):
    action: str
    target: str
    value: str
    selector: str

class EngineState(TypedDict):
    task: str
    plan: List[TestStep]
    logs: List[Dict]
    current_step_index: int
    current_url: str
    error: Optional[str]
    retry_count: int
    last_api_response: Optional[Dict]
    last_db_result: Optional[List]
    context: Dict[str, Any] # Global Context for variables
    action_history: List[str] # ReAct Agent History
    scratchpad: str # ReAct Agent Thought Process
    snapshots: Optional[Dict[str, List]] # DB Snapshots
