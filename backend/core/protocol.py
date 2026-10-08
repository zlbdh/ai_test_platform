from typing import TypedDict, List, Optional, Any, Literal
from dataclasses import dataclass, field
import datetime

try:
    from typing import NotRequired
except ImportError:  # Python 3.10 fallback
    from typing_extensions import NotRequired

# === Event Types ===

class TaskEvent(TypedDict):
    """Planner -> Executor: An atomic instruction"""
    id: str                 # Unique UUID
    type: str               # "action"
    action: str             # click, fill, goto, assert, etc.
    target: str             # CSS selector or description
    value: Optional[str]    # Input value or assertion expectation
    timestamp: str          # ISO timestamp
    step_index: NotRequired[int]  # Structured step tracking in the frontend
    scenario: NotRequired[str]

class ResultEvent(TypedDict):
    """Executor -> Planner: The outcome of an action"""
    task_id: str            # Corresponds to TaskEvent.id
    status: Literal['success', 'error']
    message: str            # Log message or error details
    screenshot: Optional[str] # Base64 encoded screenshot (for vision)
    data: Optional[Any]     # Extracted text, DB result, etc.
    duration: float         # Execution time in seconds
    timestamp: str
    action: Optional[str]   # Action name
    target: Optional[str]   # Action target
    value: Optional[str]    # Action value
    step_index: NotRequired[int]

class ControlEvent(TypedDict):
    """Orchestrator command"""
    type: Literal['shutdown', 'pause', 'resume']
    reason: Optional[str]

# === Sentinel Objects ===
# Used for graceful thread termination
class Sentinel:
    pass

SENTINEL = Sentinel()
