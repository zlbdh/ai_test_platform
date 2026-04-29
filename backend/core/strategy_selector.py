"""
AI Test Strategy Selector - 智能测试策略选择器

根据输入自动选择最佳测试策略，实现 AI 100% 自动化决策：
- 分析目标类型 (Web/API/Database)
- 自动选择测试类型组合
- 动态调整并发和超时
- 智能优先级排序
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import re
import json
import sqlite3
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class TestType(Enum):
    __test__ = False
    UI_E2E = "ui_e2e"
    API_REST = "api_rest"
    API_GRAPHQL = "api_graphql"
    PERFORMANCE = "performance"
    SECURITY = "security"
    DATABASE = "database"
    VISUAL_REGRESSION = "visual_regression"
    ACCESSIBILITY = "accessibility"


class Priority(Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class TestStrategy:
    """测试策略"""
    __test__ = False
    test_types: List[TestType]
    priority: Priority
    parallel: bool = True
    timeout_seconds: int = 300
    retry_count: int = 3
    stop_on_failure: bool = False
    ai_confidence: float = 0.0
    reasoning: str = ""
    recommended_agents: List[str] = field(default_factory=list)


class AITestStrategySelector:
    """AI 驱动的测试策略选择器"""
    
    def __init__(self):
        self.patterns = self._init_patterns()
        self.history: List[Dict] = []
        self._db_path = self._get_db_path()
        self._init_db()

    @staticmethod
    def _get_db_path() -> str:
        """获取 SQLite 数据库路径"""
        import os
        db_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(db_dir, exist_ok=True)
        return os.path.join(db_dir, 'strategy_history.db')

    def _init_db(self):
        """初始化策略历史表"""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS strategy_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    requirement TEXT NOT NULL,
                    strategy_json TEXT NOT NULL,
                    success INTEGER,
                    feedback TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"策略历史 DB 初始化失败: {e}")
    
    def _init_patterns(self) -> Dict:
        """初始化模式识别规则"""
        return {
            "api_keywords": [
                "api", "接口", "endpoint", "rest", "graphql", "grpc",
                "request", "response", "请求", "响应", "json", "xml"
            ],
            "ui_keywords": [
                "页面", "page", "button", "click", "form", "input",
                "登录", "login", "注册", "register", "表单", "element",
                "浏览器", "browser", "网站", "website", "ui", "界面"
            ],
            "db_keywords": [
                "数据库", "database", "sql", "mysql", "postgres", "sqlite",
                "table", "insert", "update", "delete", "query", "表"
            ],
            "perf_keywords": [
                "性能", "performance", "压力", "stress", "负载", "load",
                "并发", "concurrent", "qps", "tps", "响应时间"
            ],
            "security_keywords": [
                "安全", "security", "xss", "sql注入", "injection", "csrf",
                "漏洞", "vulnerability", "attack", "渗透", "penetration"
            ],
            "visual_keywords": [
                "视觉", "visual", "截图", "screenshot", "对比", "diff",
                "regression", "回归", "样式", "style", "ui一致性"
            ]
        }
    
    def analyze_target(self, target: str) -> Dict[str, Any]:
        """分析测试目标"""
        result = {
            "is_url": False,
            "is_api_endpoint": False,
            "is_database": False,
            "domain": None,
            "path": None,
            "protocol": None
        }
        
        # URL 分析
        try:
            parsed = urlparse(target)
            if parsed.scheme in ["http", "https"]:
                result["is_url"] = True
                result["domain"] = parsed.netloc
                result["path"] = parsed.path
                result["protocol"] = parsed.scheme
                
                # API 端点检测
                api_patterns = ["/api/", "/v1/", "/v2/", "/graphql", "/rest/"]
                if any(p in parsed.path.lower() for p in api_patterns):
                    result["is_api_endpoint"] = True
        except Exception:
            pass
        
        # 数据库连接字符串检测
        db_patterns = ["mysql://", "postgres://", "sqlite://", "mongodb://"]
        if any(target.lower().startswith(p) for p in db_patterns):
            result["is_database"] = True
        
        return result
    
    def analyze_requirement(self, requirement: str, target_url: str = "") -> Dict[str, float]:
        """分析需求文本，返回各测试类型的匹配分数（规则 + LLM fallback）"""
        scores = {
            TestType.UI_E2E: 0.0,
            TestType.API_REST: 0.0,
            TestType.API_GRAPHQL: 0.0,
            TestType.PERFORMANCE: 0.0,
            TestType.SECURITY: 0.0,
            TestType.DATABASE: 0.0,
            TestType.VISUAL_REGRESSION: 0.0,
            TestType.ACCESSIBILITY: 0.0
        }

        if not requirement or not requirement.strip():
            return scores
        
        req_lower = requirement.lower()
        
        # 关键词匹配
        for kw in self.patterns["ui_keywords"]:
            if kw in req_lower:
                scores[TestType.UI_E2E] += 1.0
                scores[TestType.VISUAL_REGRESSION] += 0.3
        
        for kw in self.patterns["api_keywords"]:
            if kw in req_lower:
                scores[TestType.API_REST] += 1.0
                if "graphql" in req_lower:
                    scores[TestType.API_GRAPHQL] += 2.0
        
        for kw in self.patterns["db_keywords"]:
            if kw in req_lower:
                scores[TestType.DATABASE] += 1.0
        
        for kw in self.patterns["perf_keywords"]:
            if kw in req_lower:
                scores[TestType.PERFORMANCE] += 1.0
        
        for kw in self.patterns["security_keywords"]:
            if kw in req_lower:
                scores[TestType.SECURITY] += 1.0
        
        for kw in self.patterns["visual_keywords"]:
            if kw in req_lower:
                scores[TestType.VISUAL_REGRESSION] += 1.0
        
        # 归一化
        max_score = max(scores.values()) if max(scores.values()) > 0 else 1
        rule_scores = {k: v / max_score for k, v in scores.items()}

        # ── LLM fallback: 当规则匹配置信度低时调用 LLM 深度分析 ──
        if max_score < 1.5:  # 低置信度阈值
            llm_scores = self._llm_analyze(requirement, target_url)
            if llm_scores:
                # 加权合并: rule 0.4 + llm 0.6
                merged = {}
                for tt in rule_scores:
                    r_val = rule_scores.get(tt, 0.0)
                    l_val = llm_scores.get(tt, 0.0)
                    merged[tt] = r_val * 0.4 + l_val * 0.6
                return merged

        return rule_scores

    def _llm_analyze(self, requirement: str, target_url: str = "") -> Optional[Dict[TestType, float]]:
        """使用 LLM 深度分析需求文本（fallback）"""
        try:
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import JsonOutputParser
            from core.llm_manager import get_llm_for_role
            from core.prompts import STRATEGY_ANALYSIS_PROMPT

            prompt = ChatPromptTemplate.from_template(STRATEGY_ANALYSIS_PROMPT)
            chain = prompt | get_llm_for_role("planner") | JsonOutputParser()
            result = chain.invoke({
                "requirement": requirement,
                "target_info": target_url or "无"
            })

            type_map = {t.value: t for t in TestType}
            scores: Dict[TestType, float] = {t: 0.0 for t in TestType}
            for item in result.get("test_types", []):
                tt = type_map.get(item.get("type"))
                if tt:
                    scores[tt] = float(item.get("confidence", 0.0))
            logger.info(f"[StrategySelector] LLM 分析完成: {result.get('reasoning', '')}")
            return scores
        except Exception as e:
            logger.warning(f"[StrategySelector] LLM fallback 失败, 降级到纯规则: {e}")
            return None

    
    def select_strategy(
        self,
        requirement: str,
        target_url: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> TestStrategy:
        """
        AI 智能选择测试策略
        
        Args:
            requirement: 测试需求描述
            target_url: 目标 URL
            context: 额外上下文 (历史记录、项目配置等)
        
        Returns:
            TestStrategy: 推荐的测试策略
        """
        # 分析需求
        scores = self.analyze_requirement(requirement)
        
        # 分析目标
        target_info = {}
        if target_url:
            target_info = self.analyze_target(target_url)
        
        # 选择测试类型
        selected_types = []
        threshold = 0.3
        
        for test_type, score in sorted(scores.items(), key=lambda x: -x[1]):
            if score >= threshold:
                selected_types.append(test_type)
        
        # 如果没有明确匹配，根据目标类型推断
        if not selected_types:
            if target_info.get("is_api_endpoint"):
                selected_types = [TestType.API_REST]
            elif target_info.get("is_database"):
                selected_types = [TestType.DATABASE]
            elif target_info.get("is_url"):
                selected_types = [TestType.UI_E2E]
            else:
                # 默认 UI 测试
                selected_types = [TestType.UI_E2E]
        
        # 计算 AI 置信度
        confidence = max(scores.values()) if scores else 0.5
        
        # 确定优先级
        if any(t in selected_types for t in [TestType.SECURITY]):
            priority = Priority.CRITICAL
        elif any(t in selected_types for t in [TestType.API_REST, TestType.DATABASE]):
            priority = Priority.HIGH
        else:
            priority = Priority.MEDIUM
        
        # 推荐 Agent
        agent_map = {
            TestType.UI_E2E: ["UIAgent", "ExecutorAgent"],
            TestType.API_REST: ["APIAgent"],
            TestType.API_GRAPHQL: ["APIAgent"],
            TestType.PERFORMANCE: ["OpsAgent"],
            TestType.SECURITY: ["APIAgent", "OpsAgent"],
            TestType.DATABASE: ["DataAgent"],
            TestType.VISUAL_REGRESSION: ["UIAgent"],
        }
        
        recommended_agents = []
        for t in selected_types:
            recommended_agents.extend(agent_map.get(t, []))
        recommended_agents = list(set(recommended_agents))
        
        # 生成策略
        strategy = TestStrategy(
            test_types=selected_types,
            priority=priority,
            parallel=len(selected_types) > 1,
            timeout_seconds=300 if TestType.PERFORMANCE not in selected_types else 600,
            retry_count=3,
            stop_on_failure=priority == Priority.CRITICAL,
            ai_confidence=confidence,
            reasoning=self._generate_reasoning(requirement, selected_types, scores),
            recommended_agents=recommended_agents
        )
        
        # 记录历史
        self.history.append({
            "requirement": requirement,
            "strategy": strategy,
            "scores": scores
        })
        
        return strategy
    
    def _generate_reasoning(
        self,
        requirement: str,
        selected_types: List[TestType],
        scores: Dict[TestType, float]
    ) -> str:
        """生成决策推理说明"""
        type_names = [t.value for t in selected_types]
        top_scores = sorted(scores.items(), key=lambda x: -x[1])[:3]
        
        reasoning = f"基于需求分析，识别到以下测试类型需求：\n"
        for t, s in top_scores:
            if s > 0:
                reasoning += f"  - {t.value}: {s:.1%} 匹配度\n"
        reasoning += f"\n推荐执行: {', '.join(type_names)}"
        
        return reasoning
    
    def learn_from_result(
        self,
        requirement: str,
        strategy: TestStrategy,
        success: bool,
        feedback: Optional[str] = None
    ):
        """从测试结果学习，持久化到 SQLite"""
        # 内存记录
        self.history.append({
            "requirement": requirement,
            "strategy": strategy,
            "success": success,
            "feedback": feedback
        })
        # SQLite 持久化
        try:
            strategy_json = json.dumps({
                "test_types": [t.value for t in strategy.test_types],
                "priority": strategy.priority.value,
                "ai_confidence": strategy.ai_confidence,
                "reasoning": strategy.reasoning,
            }, ensure_ascii=False)
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                'INSERT INTO strategy_history (requirement, strategy_json, success, feedback) VALUES (?, ?, ?, ?)',
                (requirement, strategy_json, 1 if success else 0, feedback)
            )
            conn.commit()
            conn.close()
            logger.info(f"[StrategySelector] 学习结果已持久化 (success={success})")
        except Exception as e:
            logger.warning(f"[StrategySelector] 持久化失败: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """获取策略选择统计数据"""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.execute('SELECT COUNT(*), SUM(success) FROM strategy_history')
            row = cursor.fetchone()
            conn.close()
            total = row[0] or 0
            successes = row[1] or 0
            return {
                "total_decisions": total,
                "success_count": successes,
                "success_rate": (successes / total * 100) if total > 0 else 0.0
            }
        except Exception:
            return {"total_decisions": 0, "success_count": 0, "success_rate": 0.0}


# 单例
_strategy_selector: Optional[AITestStrategySelector] = None

def get_strategy_selector() -> AITestStrategySelector:
    """获取策略选择器单例"""
    global _strategy_selector
    if _strategy_selector is None:
        _strategy_selector = AITestStrategySelector()
    return _strategy_selector
