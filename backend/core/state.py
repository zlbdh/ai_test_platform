"""
QA 平台状态定义
定义整个测试流程中的共享状态
"""
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage


class QAState(TypedDict):
    """QA 平台全局状态"""
    # 任务信息
    task_description: Annotated[str, "测试任务描述"]
    test_scenario: Annotated[str, "测试场景"]
    
    # Agent 执行结果
    ui_results: Annotated[List[Dict[str, Any]], "UI Agent 执行结果"]
    api_results: Annotated[List[Dict[str, Any]], "API Agent 执行结果"]
    data_results: Annotated[List[Dict[str, Any]], "Data Agent 执行结果"]
    ops_results: Annotated[List[Dict[str, Any]], "Ops Agent 执行结果"]
    
    # 工作流状态
    current_step: Annotated[str, "当前执行步骤"]
    completed_steps: Annotated[List[str], "已完成的步骤"]
    failed_steps: Annotated[List[str], "失败的步骤"]
    
    # 消息历史
    messages: Annotated[List[BaseMessage], "Agent 之间的消息通信"]
    
    # 诊断信息
    errors: Annotated[List[Dict[str, Any]], "错误信息列表"]
    warnings: Annotated[List[str], "警告信息列表"]
    
    # 测试数据
    test_data: Annotated[Dict[str, Any], "测试过程中产生的数据"]
    
    # 最终报告
    final_report: Annotated[Optional[Dict[str, Any]], "最终测试报告"]
    
    # 子图状态（用于追踪子图执行）
    subgraph_states: Annotated[Dict[str, Any], "子图状态追踪"]
    
    # Inspector 视觉质检结果
    inspection_results: Annotated[List[Dict[str, Any]], "Inspector 审查结果列表"]

    # 自愈上下文
    healing_context: Annotated[Optional[Dict[str, Any]], "自愈上下文信息"]
