from langgraph.graph import StateGraph, END
from agents.state import EngineState
from agents.planner import PlannerNode
from agents.executor import ExecutorNode

# Instantiate Nodes
planner_node = PlannerNode()
executor_node = ExecutorNode()

# Define the Workflow Graph
workflow = StateGraph(EngineState)

# Nodes
workflow.add_node("planner", planner_node.plan)
workflow.add_node("executor", executor_node.execute_step)

# Edges
workflow.set_entry_point("planner")

def should_continue(state: EngineState):
    if state.get("error"):
        return END
    
    if state["current_step_index"] < len(state["plan"]):
        return "executor"
        
    return END

workflow.add_edge("planner", "executor")
workflow.add_conditional_edges(
    "executor",
    should_continue,
    {
        "executor": "executor",
        END: END
    }
)

# Compile
app_graph = workflow.compile()
