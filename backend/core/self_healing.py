"""
Self-Healing Test Engine - 自愈测试引擎

实现测试失败时的自动修复机制：
- 元素定位失败 -> 智能查找替代元素
- 超时失败 -> 动态调整等待时间
- 断言失败 -> 分析根因并建议修复
- 网络失败 -> 自动重试
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import asyncio
import time
import json
import sqlite3
import os
import logging

logger = logging.getLogger(__name__)


class FailureType(Enum):
    ELEMENT_NOT_FOUND = "element_not_found"
    TIMEOUT = "timeout"
    ASSERTION = "assertion"
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    DATA_MISMATCH = "data_mismatch"
    UNKNOWN = "unknown"


@dataclass
class HealingAction:
    """修复动作"""
    action_type: str
    description: str
    parameters: Dict[str, Any]
    success_probability: float


@dataclass
class HealingResult:
    """修复结果"""
    success: bool
    action_taken: Optional[HealingAction]
    retry_count: int
    total_time_ms: int
    original_error: str
    healed_error: Optional[str] = None


class SelfHealingEngine:
    """自愈测试引擎"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.healing_history: List[Dict] = []
        self.learned_patterns: Dict[str, HealingAction] = {}
        self._db_path = self._get_db_path()
        self._init_db()
        self._load_learned_patterns()

    @staticmethod
    def _get_db_path() -> str:
        db_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(db_dir, exist_ok=True)
        return os.path.join(db_dir, 'healing_history.db')

    def _init_db(self):
        """初始化自愈历史表"""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS healing_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_key TEXT NOT NULL,
                    error_full TEXT,
                    action_type TEXT NOT NULL,
                    action_desc TEXT,
                    action_params TEXT,
                    success INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"自愈历史 DB 初始化失败: {e}")

    def _load_learned_patterns(self):
        """从 SQLite 加载历史成功模式到内存"""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.execute(
                'SELECT error_key, action_type, action_desc, action_params '
                'FROM healing_history WHERE success = 1 ORDER BY created_at DESC'
            )
            for row in cursor.fetchall():
                error_key, action_type, action_desc, action_params = row
                if error_key not in self.learned_patterns:
                    params = json.loads(action_params) if action_params else {}
                    self.learned_patterns[error_key] = HealingAction(
                        action_type=action_type,
                        description=action_desc or '',
                        parameters=params,
                        success_probability=0.9  # 历史成功模式高置信
                    )
            conn.close()
            if self.learned_patterns:
                logger.info(f"[SelfHealing] 加载 {len(self.learned_patterns)} 个历史修复模式")
        except Exception as e:
            logger.warning(f"[SelfHealing] 加载历史模式失败: {e}")
    
    def classify_failure(self, error: Exception, context: Dict[str, Any]) -> FailureType:
        """分类失败类型"""
        error_str = str(error).lower()
        
        if any(kw in error_str for kw in ["not found", "no such element", "找不到"]):
            return FailureType.ELEMENT_NOT_FOUND
        elif any(kw in error_str for kw in ["timeout", "超时", "timed out"]):
            return FailureType.TIMEOUT
        elif any(kw in error_str for kw in ["assert", "断言", "expected", "actual"]):
            return FailureType.ASSERTION
        elif any(kw in error_str for kw in ["connection", "network", "网络", "refused"]):
            return FailureType.NETWORK
        elif any(kw in error_str for kw in ["401", "403", "unauthorized", "forbidden"]):
            return FailureType.AUTHENTICATION
        elif any(kw in error_str for kw in ["mismatch", "不匹配", "differ"]):
            return FailureType.DATA_MISMATCH
        else:
            return FailureType.UNKNOWN
    
    def suggest_healing_actions(
        self,
        failure_type: FailureType,
        error: Exception,
        context: Dict[str, Any]
    ) -> List[HealingAction]:
        """根据失败类型建议修复动作"""
        actions = []
        
        if failure_type == FailureType.ELEMENT_NOT_FOUND:
            # 优先检查历史学习的成功模式
            error_key = str(error)[:100]
            if error_key in self.learned_patterns:
                learned = self.learned_patterns[error_key]
                actions.append(HealingAction(
                    action_type=learned.action_type,
                    description=f"[历史学习] {learned.description}",
                    parameters=learned.parameters,
                    success_probability=0.9
                ))
            
            # LLM 辅助定位 (SoM 集成)
            actions.append(HealingAction(
                action_type="llm_relocate",
                description="LLM 分析 DOM 推理替代选择器",
                parameters={"use_som": True},
                success_probability=0.75
            ))
            
            # 原有规则策略
            actions.extend([
                HealingAction(
                    action_type="retry_with_wait",
                    description="增加等待时间后重试",
                    parameters={"wait_seconds": 3},
                    success_probability=0.6
                ),
                HealingAction(
                    action_type="find_similar_element",
                    description="查找相似元素",
                    parameters={"similarity_threshold": 0.7},
                    success_probability=0.5
                ),
                HealingAction(
                    action_type="scroll_and_retry",
                    description="滚动页面后重试",
                    parameters={"scroll_amount": 500},
                    success_probability=0.4
                )
            ])
        
        elif failure_type == FailureType.TIMEOUT:
            actions.extend([
                HealingAction(
                    action_type="increase_timeout",
                    description="增加超时时间",
                    parameters={"multiplier": 2},
                    success_probability=0.7
                ),
                HealingAction(
                    action_type="wait_for_network_idle",
                    description="等待网络空闲",
                    parameters={"idle_time": 2000},
                    success_probability=0.6
                )
            ])
        
        elif failure_type == FailureType.NETWORK:
            actions.extend([
                HealingAction(
                    action_type="retry_with_backoff",
                    description="指数退避重试",
                    parameters={"initial_delay": 1, "max_delay": 30},
                    success_probability=0.8
                ),
                HealingAction(
                    action_type="check_connectivity",
                    description="检查网络连接",
                    parameters={},
                    success_probability=0.3
                )
            ])
        
        elif failure_type == FailureType.AUTHENTICATION:
            actions.extend([
                HealingAction(
                    action_type="refresh_token",
                    description="刷新认证令牌",
                    parameters={},
                    success_probability=0.7
                ),
                HealingAction(
                    action_type="re_login",
                    description="重新登录",
                    parameters={},
                    success_probability=0.8
                )
            ])
        
        elif failure_type == FailureType.ASSERTION:
            actions.extend([
                HealingAction(
                    action_type="retry_with_refresh",
                    description="刷新页面后重试断言",
                    parameters={},
                    success_probability=0.4
                ),
                HealingAction(
                    action_type="loosen_assertion",
                    description="放宽断言条件 (需人工确认)",
                    parameters={"threshold": 0.9},
                    success_probability=0.3
                )
            ])
        
        # 通用重试
        actions.append(HealingAction(
            action_type="simple_retry",
            description="简单重试",
            parameters={},
            success_probability=0.3
        ))
        
        # 按成功概率排序
        return sorted(actions, key=lambda a: -a.success_probability)
    
    async def execute_with_healing(
        self,
        func: Callable,
        *args,
        context: Optional[Dict] = None,
        **kwargs
    ) -> HealingResult:
        """
        执行函数并在失败时自动修复
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            context: 执行上下文
            **kwargs: 函数关键字参数
        
        Returns:
            HealingResult: 修复结果
        """
        context = context or {}
        start_time = time.time()
        retry_count = 0
        last_error = None
        action_taken = None
        
        while retry_count <= self.max_retries:
            try:
                # 执行函数
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # 成功
                total_time = int((time.time() - start_time) * 1000)
                
                if retry_count > 0:
                    # 记录成功的修复模式
                    self._record_success(last_error, action_taken)
                
                return HealingResult(
                    success=True,
                    action_taken=action_taken,
                    retry_count=retry_count,
                    total_time_ms=total_time,
                    original_error="" if retry_count == 0 else str(last_error)
                )
                
            except Exception as e:
                last_error = e
                retry_count += 1
                
                if retry_count > self.max_retries:
                    break
                
                # 分类失败
                failure_type = self.classify_failure(e, context)
                logger.warning(f"Failure detected: {failure_type.value} - {e}")
                
                # 获取修复动作
                actions = self.suggest_healing_actions(failure_type, e, context)
                
                if actions:
                    action_taken = actions[0]
                    logger.info(f"Attempting healing: {action_taken.description}")
                    
                    # 执行修复动作
                    await self._execute_healing_action(action_taken, context)
                else:
                    # 默认延迟重试
                    delay = self.base_delay * (2 ** (retry_count - 1))
                    await asyncio.sleep(delay)
        
        # 所有重试失败
        total_time = int((time.time() - start_time) * 1000)
        return HealingResult(
            success=False,
            action_taken=action_taken,
            retry_count=retry_count,
            total_time_ms=total_time,
            original_error=str(last_error)
        )
    
    async def _execute_healing_action(
        self,
        action: HealingAction,
        context: Dict[str, Any]
    ):
        """执行修复动作"""
        if action.action_type == "retry_with_wait":
            wait = action.parameters.get("wait_seconds", 3)
            await asyncio.sleep(wait)
        
        elif action.action_type == "increase_timeout":
            multiplier = action.parameters.get("multiplier", 2)
            if "timeout" in context:
                context["timeout"] *= multiplier
        
        elif action.action_type == "retry_with_backoff":
            initial = action.parameters.get("initial_delay", 1)
            await asyncio.sleep(initial)
        
        elif action.action_type == "scroll_and_retry":
            # 需要浏览器上下文
            if "browser" in context:
                await context["browser"].scroll(action.parameters.get("scroll_amount", 500))
        
        else:
            # 默认等待
            await asyncio.sleep(self.base_delay)
    
    def _record_success(self, error: Exception, action: Optional[HealingAction]):
        """记录成功的修复模式 → 内存 + SQLite 持久化"""
        if action:
            error_key = str(error)[:100]
            self.learned_patterns[error_key] = action
            record = {
                "error": str(error),
                "action": action,
                "success": True
            }
            self.healing_history.append(record)
            # SQLite 持久化
            try:
                conn = sqlite3.connect(self._db_path)
                conn.execute(
                    'INSERT INTO healing_history (error_key, error_full, action_type, action_desc, action_params, success) '
                    'VALUES (?, ?, ?, ?, ?, ?)',
                    (
                        error_key,
                        str(error)[:500],
                        action.action_type,
                        action.description,
                        json.dumps(action.parameters, ensure_ascii=False),
                        1
                    )
                )
                conn.commit()
                conn.close()
                logger.info(f"[SelfHealing] 修复模式已持久化: {action.action_type}")
            except Exception as e:
                logger.warning(f"[SelfHealing] 持久化失败: {e}")

    async def llm_relocate_element(self, original_selector: str, error_msg: str, dom_snapshot: str = "") -> Optional[List[Dict]]:
        """使用 LLM 分析 DOM 推理替代选择器（SoM 深度集成）"""
        try:
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import JsonOutputParser
            from core.llm_manager import get_llm_for_role
            from core.prompts import SELF_HEALING_LLM_PROMPT

            prompt = ChatPromptTemplate.from_template(SELF_HEALING_LLM_PROMPT)
            chain = prompt | get_llm_for_role("executor") | JsonOutputParser()
            result = chain.invoke({
                "original_selector": original_selector,
                "failure_type": "element_not_found",
                "error_message": error_msg[:300],
                "dom_snapshot": dom_snapshot[:3000] if dom_snapshot else "(无 DOM 快照)"
            })
            alternatives = result.get("alternative_selectors", [])
            analysis = result.get("analysis", "")
            logger.info(f"[SelfHealing/LLM] 分析: {analysis} | 替代选择器: {len(alternatives)} 个")
            return alternatives
        except Exception as e:
            logger.warning(f"[SelfHealing/LLM] LLM 定位失败: {e}")
            return None

    
    def get_statistics(self) -> Dict[str, Any]:
        """获取自愈统计"""
        total = len(self.healing_history)
        success = sum(1 for h in self.healing_history if h.get("success"))
        
        return {
            "total_healings": total,
            "successful_healings": success,
            "success_rate": success / total if total > 0 else 0,
            "learned_patterns": len(self.learned_patterns)
        }

    # === Sync 接口（供 Executor sync 线程调用） ===
    
    def execute_with_healing_sync(
        self,
        func: Callable,
        *args,
        context: Optional[Dict] = None,
        **kwargs
    ) -> HealingResult:
        """
        同步版本：执行函数并在失败时自动修复。
        适用于 Executor 的 sync Playwright 线程。
        """
        context = context or {}
        start_time = time.time()
        retry_count = 0
        last_error = None
        action_taken = None
        
        while retry_count <= self.max_retries:
            try:
                result = func(*args, **kwargs)
                total_time = int((time.time() - start_time) * 1000)
                
                if retry_count > 0:
                    self._record_success(last_error, action_taken)
                
                return HealingResult(
                    success=True,
                    action_taken=action_taken,
                    retry_count=retry_count,
                    total_time_ms=total_time,
                    original_error="" if retry_count == 0 else str(last_error)
                )
                
            except Exception as e:
                last_error = e
                retry_count += 1
                
                if retry_count > self.max_retries:
                    break
                
                failure_type = self.classify_failure(e, context)
                logger.warning(f"[SelfHealing/Sync] {failure_type.value}: {e}")
                
                actions = self.suggest_healing_actions(failure_type, e, context)
                
                if actions:
                    action_taken = actions[0]
                    logger.info(f"[SelfHealing/Sync] Healing: {action_taken.description}")
                    self._execute_healing_action_sync(action_taken, context)
                else:
                    delay = self.base_delay * (2 ** (retry_count - 1))
                    time.sleep(delay)
        
        total_time = int((time.time() - start_time) * 1000)
        # 记录失败的修复尝试
        self.healing_history.append({
            "error": str(last_error),
            "action": action_taken,
            "success": False
        })
        return HealingResult(
            success=False,
            action_taken=action_taken,
            retry_count=retry_count,
            total_time_ms=total_time,
            original_error=str(last_error)
        )
    
    def _execute_healing_action_sync(
        self,
        action: HealingAction,
        context: Dict[str, Any]
    ):
        """同步执行修复动作"""
        if action.action_type == "retry_with_wait":
            wait = action.parameters.get("wait_seconds", 3)
            time.sleep(wait)
        
        elif action.action_type == "increase_timeout":
            multiplier = action.parameters.get("multiplier", 2)
            if "timeout" in context:
                context["timeout"] *= multiplier
        
        elif action.action_type == "retry_with_backoff":
            initial = action.parameters.get("initial_delay", 1)
            time.sleep(initial)
        
        elif action.action_type == "scroll_and_retry":
            if "page" in context:
                try:
                    context["page"].evaluate(
                        f"window.scrollBy(0, {action.parameters.get('scroll_amount', 500)})"
                    )
                except Exception:
                    pass
        
        else:
            time.sleep(self.base_delay)


# 单例
_healing_engine: Optional[SelfHealingEngine] = None

def get_healing_engine() -> SelfHealingEngine:
    """获取自愈引擎单例"""
    global _healing_engine
    if _healing_engine is None:
        _healing_engine = SelfHealingEngine()
    return _healing_engine
