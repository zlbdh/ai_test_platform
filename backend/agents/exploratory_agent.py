"""
Exploratory Test Agent - 探索性测试 Agent

实现 AI 自主探索应用：
- 自动发现页面元素
- 智能路径探索
- 异常检测
- 覆盖率追踪
"""

from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import hashlib
import inspect
import time
import re
import json
import logging
import random

from core.llm_manager import get_llm_for_role

logger = logging.getLogger(__name__)


class ActionType(Enum):
    CLICK = "click"
    INPUT = "input"
    SELECT = "select"
    NAVIGATE = "navigate"
    SCROLL = "scroll"
    HOVER = "hover"


@dataclass
class PageState:
    """页面状态"""
    url: str
    title: str
    html_hash: str
    elements_count: int
    forms_count: int
    links_count: int


@dataclass
class ExplorationAction:
    """探索动作"""
    action_type: ActionType
    target: str
    value: Optional[str] = None


@dataclass
class AnomalyFound:
    """发现的异常"""
    anomaly_type: str
    description: str
    url: str
    evidence: str
    severity: str


@dataclass
class ExplorationResult:
    """探索结果"""
    total_states: int
    total_actions: int
    unique_urls: int
    anomalies: List[AnomalyFound]
    coverage: float
    duration_seconds: float


class ExploratoryTestAgent:
    """探索性测试 Agent"""
    
    def __init__(self, browser=None, llm=None):
        self.browser = browser
        self.llm = llm
        
        self.visited_states: Set[str] = set()
        self.visited_urls: Set[str] = set()
        self.action_history: List[ExplorationAction] = []
        self.anomalies: List[AnomalyFound] = []
        
        # UI 状态转换图: {state_hash: {action_str: target_state_hash}}
        self.state_graph: Dict[str, Dict[str, str]] = {}
        self._current_state_hash: str = ""
        
        # 自动回归用例列表
        self.regression_cases: List[Dict[str, Any]] = []
        
        # 异常检测模式（增强版）
        self.error_patterns = [
            (r"500\s*Internal Server Error", "server_error"),
            (r"404\s*Not Found", "not_found"),
            (r"403\s*Forbidden", "forbidden"),
            (r"Error|Exception|Traceback", "application_error"),
            (r"undefined|null reference|NaN", "javascript_error"),
            (r"SQLSTATE|SQL syntax", "database_error"),
            # P1-7 新增: 性能/网络/控制台异常检测
            (r"Failed to load resource", "network_error"),
            (r"net::ERR_", "network_error"),
            (r"TypeError|ReferenceError|SyntaxError", "js_runtime_error"),
            (r"Loading\.{3,}|Spinner|skeleton", "slow_render"),
        ]

    async def _resolve_browser_attr(self, attr_name: str, *args, default=None, **kwargs):
        """兼容 raw page、bridged page 以及同步属性/异步方法。"""
        if not self.browser:
            return default

        attr = getattr(self.browser, attr_name, None)
        if attr is None:
            return default

        try:
            value = attr(*args, **kwargs) if callable(attr) else attr
            if inspect.isawaitable(value):
                return await value
            return value
        except Exception:
            return default
    
    def _compute_state_hash(self, html: str, url: str) -> str:
        """计算页面状态哈希"""
        # 移除动态内容
        normalized = re.sub(r'\d+', '', html)
        normalized = re.sub(r'[a-f0-9]{8,}', '', normalized)
        content = f"{url}:{normalized[:5000]}"
        return hashlib.md5(content.encode()).hexdigest()
    
    async def explore(
        self,
        start_url: str,
        max_steps: int = 50,
        max_depth: int = 3
    ) -> ExplorationResult:
        """执行探索性测试"""
        start_time = time.time()
        
        if not self.browser:
            return ExplorationResult(
                total_states=0,
                total_actions=0,
                unique_urls=0,
                anomalies=[],
                coverage=0,
                duration_seconds=0
            )
        
        self.visited_states.clear()
        self.visited_urls.clear()
        self.action_history.clear()
        self.anomalies.clear()
        self.state_graph.clear()
        self.regression_cases.clear()
        self._current_state_hash = ""
        
        # 初始导航
        await self._navigate(start_url)
        
        step = 0
        current_depth = 0
        
        while step < max_steps and current_depth < max_depth:
            step += 1
            
            # 获取当前状态
            state = await self._get_current_state()
            state_hash = self._compute_state_hash(
                await self._get_page_html(),
                state.url
            )
            
            # 检测异常
            await self._detect_anomalies(state)
            
            # 记录状态转换
            prev_hash = self._current_state_hash
            self._current_state_hash = state_hash
            
            # 如果是新状态
            if state_hash not in self.visited_states:
                self.visited_states.add(state_hash)
                self.visited_urls.add(state.url)
                self.state_graph.setdefault(state_hash, {})
                
                # 获取可能的动作
                actions = await self._discover_actions()
                
                if actions:
                    # LLM 驱动的智能选择
                    action = await self._select_action(actions)
                    
                    # 执行动作
                    await self._execute_action(action)
                    self.action_history.append(action)
                    
                    # 记录状态转换边
                    action_key = f"{action.action_type.value}:{action.target[:50]}"
                    new_state = await self._get_current_state()
                    new_hash = self._compute_state_hash(
                        await self._get_page_html(), new_state.url
                    )
                    self.state_graph[state_hash][action_key] = new_hash
                else:
                    # 无可执行动作，回退
                    await self._go_back()
                    current_depth = max(0, current_depth - 1)
            else:
                # 已访问状态: 查找状态图中未探索的分支
                unexplored = self._find_unexplored_branches(state_hash)
                if unexplored:
                    action = unexplored[0]
                    await self._execute_action(action)
                    self.action_history.append(action)
                else:
                    await self._go_back()
        
        duration = time.time() - start_time
        
        return ExplorationResult(
            total_states=len(self.visited_states),
            total_actions=len(self.action_history),
            unique_urls=len(self.visited_urls),
            anomalies=self.anomalies,
            coverage=self._calculate_coverage(),
            duration_seconds=duration
        )
    
    async def _navigate(self, url: str):
        """导航到 URL"""
        if self.browser:
            await self.browser.goto(url)
            await asyncio.sleep(1)
    
    async def _get_current_state(self) -> PageState:
        """获取当前页面状态"""
        if not self.browser:
            return PageState("", "", "", 0, 0, 0)

        url = await self._resolve_browser_attr("current_url", default=None)
        if url is None:
            url = await self._resolve_browser_attr("url", default="")

        title = await self._resolve_browser_attr("title", default="")

        return PageState(
            url=url or "",
            title=title or "",
            html_hash="",
            elements_count=0,
            forms_count=0,
            links_count=0
        )
    
    async def _get_page_html(self) -> str:
        """获取页面 HTML"""
        if self.browser and hasattr(self.browser, 'content'):
            return await self.browser.content()
        return ""
    
    async def _discover_actions(self) -> List[ExplorationAction]:
        """发现可执行的动作"""
        actions = []
        
        if not self.browser:
            return actions
        
        # 查找链接
        try:
            links = await self.browser.query_selector_all('a[href]')
            for link in links[:10]:  # 限制数量
                href = await link.get_attribute('href')
                if href and not href.startswith('#') and not href.startswith('javascript:'):
                    actions.append(ExplorationAction(
                        action_type=ActionType.CLICK,
                        target=f"a[href='{href}']"
                    ))
        except Exception:
            pass
        
        # 查找按钮
        try:
            buttons = await self.browser.query_selector_all('button, input[type="submit"]')
            for btn in buttons[:5]:
                text = await btn.inner_text() if hasattr(btn, 'inner_text') else ""
                actions.append(ExplorationAction(
                    action_type=ActionType.CLICK,
                    target=f"button:has-text('{text[:20]}')" if text else "button"
                ))
        except Exception:
            pass
        
        # 查找输入框
        try:
            inputs = await self.browser.query_selector_all('input[type="text"], input[type="search"]')
            for inp in inputs[:3]:
                name = await inp.get_attribute('name') or await inp.get_attribute('id') or ""
                actions.append(ExplorationAction(
                    action_type=ActionType.INPUT,
                    target=f"input[name='{name}']" if name else "input",
                    value="test_input"
                ))
        except Exception:
            pass
        
        return actions
    
    async def _select_action(self, actions: List[ExplorationAction]) -> ExplorationAction:
        """LLM 驱动选择要执行的动作（带规则降级）"""
        # 优先尝试 LLM 推理
        if self.llm and len(actions) > 1:
            try:
                llm_choice = await self._llm_select_action(actions)
                if llm_choice is not None:
                    return llm_choice
            except Exception as e:
                logger.warning(f"[ExploratoryAgent] LLM 选择失败, 降级规则: {e}")
        
        # 规则降级: 优先未执行过的动作
        for action in actions:
            if action not in self.action_history:
                return action
        
        # 随机选择
        return random.choice(actions)

    async def _llm_select_action(self, actions: List[ExplorationAction]) -> Optional[ExplorationAction]:
        """使用 LLM 智能选择最有价值的探索动作"""
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser
        
        actions_desc = "\n".join([
            f"{i+1}. [{a.action_type.value}] target={a.target} value={a.value}"
            for i, a in enumerate(actions[:10])
        ])
        history_desc = "\n".join([
            f"  - [{a.action_type.value}] {a.target}"
            for a in self.action_history[-5:]
        ]) or "(无历史)"
        
        prompt = ChatPromptTemplate.from_template(
            """你是一个探索性测试专家。根据已执行历史和可用动作，选择最能发现新功能/Bug 的动作。

【已执行历史(最近5步)】
{history}

【可用动作】
{actions}

【已覆盖状态数】{states_count}

选择原则：
1. 优先探索未覆盖的新路径
2. 表单提交和按钮点击比滚动更有价值
3. 避免重复已执行的相同动作

请只返回 JSON：{{"choice": 1, "reason": "选择理由"}} （choice 为动作编号，从1开始）"""
        )
        chain = prompt | get_llm_for_role("executor") | JsonOutputParser()
        result = await asyncio.to_thread(
            chain.invoke,
            {
                "history": history_desc,
                "actions": actions_desc,
                "states_count": len(self.visited_states),
            }
        )
        choice_idx = result.get("choice", 1) - 1
        if 0 <= choice_idx < len(actions):
            logger.info(f"[ExploratoryAgent] LLM 选择动作 #{choice_idx+1}: {result.get('reason', '')}")
            return actions[choice_idx]
        return None
    
    async def _execute_action(self, action: ExplorationAction):
        """执行动作"""
        if not self.browser:
            return
        
        try:
            if action.action_type == ActionType.CLICK:
                elem = await self.browser.query_selector(action.target)
                if elem:
                    await elem.click()
                    await asyncio.sleep(1)
            
            elif action.action_type == ActionType.INPUT:
                elem = await self.browser.query_selector(action.target)
                if elem:
                    await elem.fill(action.value or "")
                    await asyncio.sleep(0.5)
        except Exception:
            pass
    
    async def _go_back(self):
        """返回上一页"""
        if self.browser and hasattr(self.browser, 'go_back'):
            try:
                await self.browser.go_back()
                await asyncio.sleep(1)
            except Exception:
                pass
    
    async def _detect_anomalies(self, state: PageState):
        """增强异常检测: HTML 正则 + JS 控制台 + 网络请求 + 性能指标"""
        html = await self._get_page_html()
        
        # 1. HTML 正则模式匹配
        for pattern, anomaly_type in self.error_patterns:
            if re.search(pattern, html, re.IGNORECASE):
                self.anomalies.append(AnomalyFound(
                    anomaly_type=anomaly_type,
                    description=f"Detected {anomaly_type} pattern in page",
                    url=state.url,
                    evidence=pattern,
                    severity="high" if "error" in anomaly_type else "medium"
                ))
        
        # 2. JS 控制台错误检测 (需要 browser 支持)
        if self.browser and hasattr(self.browser, 'evaluate'):
            try:
                js_errors = await self.browser.evaluate("""
                    () => {
                        if (window.__console_errors) return window.__console_errors;
                        return [];
                    }
                """)
                for err in (js_errors or []):
                    self.anomalies.append(AnomalyFound(
                        anomaly_type="js_console_error",
                        description=f"JS Console Error: {str(err)[:200]}",
                        url=state.url,
                        evidence=str(err)[:300],
                        severity="high"
                    ))
            except Exception:
                pass
        
        # 3. 性能指标异常检测
        if self.browser and hasattr(self.browser, 'evaluate'):
            try:
                perf = await self.browser.evaluate("""
                    () => {
                        const nav = performance.getEntriesByType('navigation')[0];
                        if (!nav) return null;
                        return {
                            load_time: nav.loadEventEnd - nav.startTime,
                            dom_complete: nav.domComplete - nav.startTime,
                        };
                    }
                """)
                if perf and perf.get('load_time', 0) > 10000:  # >10s
                    self.anomalies.append(AnomalyFound(
                        anomaly_type="slow_page_load",
                        description=f"Page load took {perf['load_time']:.0f}ms (>10s threshold)",
                        url=state.url,
                        evidence=json.dumps(perf),
                        severity="medium"
                    ))
            except Exception:
                pass
    
    def _calculate_coverage(self) -> float:
        """计算覆盖率 (基于状态图边覆盖)"""
        if not self.action_history:
            return 0.0
        
        # 增强: 基于状态图的边覆盖率
        total_edges = sum(len(edges) for edges in self.state_graph.values())
        total_possible = len(self.visited_states) * 3  # 估计每状态平均 3 条边
        if total_possible == 0:
            return 0.0
        return min(1.0, total_edges / max(1, total_possible))

    def _find_unexplored_branches(self, state_hash: str) -> List[ExplorationAction]:
        """在状态图中查找未探索的分支"""
        explored_actions = set(self.state_graph.get(state_hash, {}).keys())
        unexplored = []
        for action in self.action_history:
            action_key = f"{action.action_type.value}:{action.target[:50]}"
            if action_key not in explored_actions:
                unexplored.append(action)
        return unexplored[:3]

    def generate_regression_cases(self) -> List[Dict[str, Any]]:
        """从探索路径自动生成可重放回归测试用例"""
        cases = []
        
        # 从异常路径生成回归用例
        if self.anomalies:
            for anomaly in self.anomalies:
                # 回溯找到到达异常页面的动作路径
                path_actions = []
                for action in self.action_history:
                    path_actions.append({
                        "action": action.action_type.value,
                        "target": action.target,
                        "value": action.value
                    })
                cases.append({
                    "name": f"回归测试: {anomaly.anomaly_type} @ {anomaly.url}",
                    "description": anomaly.description,
                    "severity": anomaly.severity,
                    "steps": path_actions,
                    "expected_result": f"页面不应出现 {anomaly.anomaly_type}",
                    "anomaly_evidence": anomaly.evidence
                })
        
        # 从完整探索路径生成冒烟测试
        if self.action_history:
            smoke_steps = []
            for action in self.action_history[:20]:  # 取前 20 步
                smoke_steps.append({
                    "action": action.action_type.value,
                    "target": action.target,
                    "value": action.value
                })
            cases.append({
                "name": f"冒烟测试: 核心路径探索 ({len(smoke_steps)} 步)",
                "description": f"覆盖 {len(self.visited_urls)} 个页面的核心交互路径",
                "severity": "high",
                "steps": smoke_steps,
                "expected_result": "所有页面正常加载，无异常"
            })
        
        self.regression_cases = cases
        logger.info(f"[ExploratoryAgent] 生成 {len(cases)} 个回归测试用例")
        return cases
    
    def get_state_graph_summary(self) -> Dict[str, Any]:
        """获取状态转换图摘要"""
        return {
            "total_states": len(self.state_graph),
            "total_transitions": sum(len(e) for e in self.state_graph.values()),
            "states": {
                state: list(edges.keys())
                for state, edges in self.state_graph.items()
            }
        }
    
    def generate_report(self) -> Dict[str, Any]:
        """生成探索报告（增强版）"""
        return {
            "summary": {
                "total_states_visited": len(self.visited_states),
                "total_actions_performed": len(self.action_history),
                "unique_urls": len(self.visited_urls),
                "anomalies_found": len(self.anomalies),
                "state_transitions": sum(len(e) for e in self.state_graph.values()),
                "regression_cases": len(self.regression_cases)
            },
            "visited_urls": list(self.visited_urls),
            "action_history": [
                {
                    "type": a.action_type.value,
                    "target": a.target,
                    "value": a.value
                }
                for a in self.action_history[-20:]
            ],
            "anomalies": [
                {
                    "type": a.anomaly_type,
                    "description": a.description,
                    "url": a.url,
                    "severity": a.severity
                }
                for a in self.anomalies
            ],
            "state_graph": self.get_state_graph_summary(),
            "regression_cases": self.regression_cases[:10]  # 最多 10 个
        }


def create_exploratory_agent(browser=None, llm=None) -> ExploratoryTestAgent:
    """创建探索性测试 Agent"""
    return ExploratoryTestAgent(browser, llm)
