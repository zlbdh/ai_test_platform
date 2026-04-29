"""
Master Agent - 主脑规划器
负责任务分解、Agent 协调、结果汇总
"""
from typing import Dict, Any, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from core.config import Config
from core.llm_manager import get_llm_for_role
from core.state import QAState
from skills.knowledge_tools import get_similar_test_plans, get_prd_context, get_api_documentation
from langchain_core.output_parsers import JsonOutputParser


from core.prompts import PLAN_TEST_SYSTEM, PLAN_TEST_USER_TEMPLATE, AGENT_EXTRACTION_PROMPT
import logging

logger = logging.getLogger(__name__)

class MasterAgent:
    """主脑规划器 Agent"""
    
    def __init__(self):
        """初始化 Master Agent"""
        self.llm = get_llm_for_role("executor")
        
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", PLAN_TEST_SYSTEM),
            ("human", PLAN_TEST_USER_TEMPLATE)
        ])
    
    def plan_test(self, scenario: str, prd_context: Optional[str] = None) -> Dict[str, Any]:
        """
        规划测试任务（增强版：集成 Vector DB）
        
        Args:
            scenario: 测试场景描述
            prd_context: 可选，PRD 上下文
            
        Returns:
            测试计划
        """
        # 从 Vector DB 检索相似的测试计划
        similar_plans = []
        try:
            similar_plans = get_similar_test_plans.invoke({
                "scenario": scenario,
                "n_results": 3
            })
        except Exception as e:
            logger.warning(f"  [Master Agent] Vector DB 检索失败: {str(e)}")
        
        # 获取 PRD 上下文
        prd_info = []
        if prd_context:
            try:
                prd_info = get_prd_context.invoke({
                    "query": scenario,
                    "n_results": 2
                })
            except Exception as e:
                pass
        
        # 构建增强的提示（包含历史计划参考）
        enhanced_prompt = f"测试场景：{scenario}\n\n"
        
        if similar_plans:
            enhanced_prompt += "参考历史相似测试计划：\n"
            for plan in similar_plans[:2]:
                plan_content = plan.get("content", "")[:200]
                enhanced_prompt += f"- {plan_content}\n"
            enhanced_prompt += "\n"
        
        if prd_info:
            enhanced_prompt += "PRD 上下文：\n"
            for info in prd_info[:1]:
                info_content = info.get("content", "")[:200]
                enhanced_prompt += f"- {info_content}\n"
            enhanced_prompt += "\n"
        
        enhanced_prompt += "请分解任务并规划执行步骤。"
        
        chain = self.prompt_template | self.llm | StrOutputParser()
        plan_text = chain.invoke({"scenario": enhanced_prompt})
        
        # 解析计划
        plan = {
            "scenario": scenario,
            "plan_text": plan_text,
            "required_agents": self._extract_agents(plan_text),
            "steps": self._extract_steps(plan_text),
            "similar_plans_referenced": len(similar_plans),
            "prd_context_used": len(prd_info) > 0
        }
        
        return plan
    
    def _extract_agents(self, plan_text: str) -> List[str]:
        """从计划文本中提取需要的 Agent（LLM 推理 + 关键词降级）"""
        # 优先使用 LLM 推理
        try:
            prompt = ChatPromptTemplate.from_template(AGENT_EXTRACTION_PROMPT)
            chain = prompt | get_llm_for_role("executor") | JsonOutputParser()
            result = chain.invoke({"plan_text": plan_text})
            agents = result.get("agents", [])
            valid_agents = {"ui_agent", "api_agent", "data_agent", "ops_agent"}
            llm_agents = [a for a in agents if a in valid_agents]
            if llm_agents:
                logger.info(f"[MasterAgent] LLM 提取 agents: {llm_agents} | {result.get('reasoning', '')}")
                return llm_agents
        except Exception as e:
            logger.warning(f"[MasterAgent] LLM 提取 agents 失败, 降级到关键词: {e}")

        # Fallback: 关键词匹配
        agents = []
        plan_lower = plan_text.lower()
        
        if "ui" in plan_lower or "前端" in plan_lower or "界面" in plan_lower:
            agents.append("ui_agent")
        if "api" in plan_lower or "接口" in plan_lower or "后端" in plan_lower:
            agents.append("api_agent")
        if "data" in plan_lower or "数据" in plan_lower or "数据库" in plan_lower:
            agents.append("data_agent")
        if "ops" in plan_lower or "日志" in plan_lower or "运维" in plan_lower:
            agents.append("ops_agent")
        
        # 默认至少需要 UI 和 API
        if not agents:
            agents = ["ui_agent", "api_agent"]
        
        return agents
    
    def _extract_steps(self, plan_text: str) -> List[str]:
        """从计划文本中提取步骤"""
        # 简化处理：根据关键词提取步骤
        steps = []
        lines = plan_text.split('\n')
        
        for i, line in enumerate(lines):
            if any(keyword in line for keyword in ['1.', '2.', '3.', '步骤', 'step']):
                steps.append(line.strip())
        
        # 如果没有找到步骤，创建默认步骤
        if not steps:
            steps = [
                "1. UI Agent 执行前端测试",
                "2. API Agent 执行接口测试",
                "3. Data Agent 验证数据一致性",
                "4. 汇总结果生成报告"
            ]
        
        return steps
    
    def generate_report(self, state: QAState) -> Dict[str, Any]:
        """
        生成最终测试报告
        
        Args:
            state: QA 状态
            
        Returns:
            测试报告
        """
        report = {
            "test_scenario": state.get("test_scenario", ""),
            "task_description": state.get("task_description", ""),
            "summary": {
                "total_steps": len(state.get("completed_steps", [])),
                "failed_steps": len(state.get("failed_steps", [])),
                "success_rate": self._calculate_success_rate(state),
                "inspection_total": len(state.get("inspection_results", [])),
                "inspection_passed": sum(1 for r in state.get("inspection_results", []) if r.get("passed")),
                "inspection_rejected": sum(1 for r in state.get("inspection_results", []) if not r.get("passed")),
            },
            "ui_results": state.get("ui_results", []),
            "api_results": state.get("api_results", []),
            "data_results": state.get("data_results", []),
            "ops_results": state.get("ops_results", []),
            "inspection_results": state.get("inspection_results", []),
            "errors": state.get("errors", []),
            "warnings": state.get("warnings", []),
            "recommendations": self._generate_recommendations(state)
        }
        
        return report
    
    def _calculate_success_rate(self, state: QAState) -> float:
        """计算成功率"""
        completed = len(state.get("completed_steps", []))
        failed = len(state.get("failed_steps", []))
        total = completed + failed
        
        if total == 0:
            return 0.0
        
        return (completed / total) * 100
    
    def _generate_recommendations(self, state: QAState) -> List[str]:
        """生成建议"""
        recommendations = []

        errors = state.get("errors", [])
        if errors:
            recommendations.append(f"发现 {len(errors)} 个错误，建议优先修复")

        failed_steps = state.get("failed_steps", [])
        if failed_steps:
            recommendations.append(f"以下步骤失败：{', '.join(failed_steps)}")

        # Inspector 驳回建议
        rejected = [r for r in state.get("inspection_results", []) if not r.get("passed")]
        if rejected:
            recommendations.append(f"Inspector 视觉质检驳回 {len(rejected)} 项，请检查相关截图和异常描述")
            for r in rejected[:3]:
                recommendations.append(f"  - {r.get('step', '?')}: {r.get('reason', '未知原因')}")

        if not errors and not failed_steps and not rejected:
            recommendations.append("所有测试通过，可以发布")

        return recommendations
