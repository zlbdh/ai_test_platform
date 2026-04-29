# -*- coding: utf-8 -*-
"""
TestArchitect — 测试架构师（战略层）

职责：决定"测什么"，是 Commander 的上游。

五种测试发现模式：
    1. 需求驱动：PRD 文档 → RequirementParser → 测试需求列表
    2. 变更驱动：Git diff → AcceptanceEngine → 影响评估
    3. 探索驱动：ExploratoryAgent + ScoutAgent → 自主发现
    4. 覆盖驱动：分析现有测试报告 → 找盲区
    5. 故障驱动：告警 → RCAAgent → 回归用例

关键：激活 AcceptanceEngine（295行，零引用）和 ExploratoryAgent（561行，缺路由）。
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── 数据结构 ──────────────────────────────────────────────────────────────────


class DiscoveryMode(Enum):
    """测试发现模式"""
    REQUIREMENT = "requirement"   # 需求驱动
    CHANGE = "change"             # 变更驱动
    EXPLORATION = "exploration"   # 探索驱动
    COVERAGE = "coverage"         # 覆盖驱动
    FAULT = "fault"               # 故障驱动


@dataclass
class TestNeed:
    """一条测试需求"""
    title: str
    description: str
    source: DiscoveryMode
    priority: str = "medium"      # critical / high / medium / low
    target_url: str = ""
    test_types: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ArchitectPlan:
    """架构师输出的测试计划"""
    plan_id: str = ""
    discovery_mode: DiscoveryMode = DiscoveryMode.REQUIREMENT
    test_needs: List[TestNeed] = field(default_factory=list)
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "discovery_mode": self.discovery_mode.value,
            "test_needs": [
                {
                    "title": n.title,
                    "description": n.description,
                    "source": n.source.value,
                    "priority": n.priority,
                    "target_url": n.target_url,
                    "test_types": n.test_types,
                }
                for n in self.test_needs
            ],
            "summary": self.summary,
            "created_at": self.created_at,
        }


# ── TestArchitect 核心 ───────────────────────────────────────────────────────


class TestArchitect:
    """
    测试架构师 — 战略层

    回答"测什么？"：
    - 分析输入 → 确定发现模式 → 生成测试需求列表
    - 输出交给 Commander 执行
    """

    def __init__(self):
        logger.info("[TestArchitect] 初始化完成")

    # ── 统一入口 ──────────────────────────────────────────────────────────

    async def analyze(
        self,
        input_text: str = "",
        target_url: str = "",
        mode: Optional[str] = None,
        diff_text: str = "",
        alert_data: Optional[Dict] = None,
    ) -> ArchitectPlan:
        """
        分析输入并生成测试需求列表。

        Args:
            input_text: 用户输入的需求描述/PRD
            target_url: 目标 URL
            mode: 指定发现模式（留空则自动推断）
            diff_text: Git diff 文本（变更驱动时使用）
            alert_data: 告警数据（故障驱动时使用）

        Returns:
            ArchitectPlan: 测试计划
        """
        import uuid
        plan = ArchitectPlan(plan_id=str(uuid.uuid4())[:8])

        # 自动推断模式
        if mode:
            plan.discovery_mode = DiscoveryMode(mode)
        else:
            plan.discovery_mode = self._infer_mode(
                input_text, diff_text, alert_data, target_url,
            )

        logger.info(f"[TestArchitect] 发现模式: {plan.discovery_mode.value}")

        # 根据模式分发
        if plan.discovery_mode == DiscoveryMode.REQUIREMENT:
            plan.test_needs = await self._discover_from_requirement(input_text)
        elif plan.discovery_mode == DiscoveryMode.CHANGE:
            plan.test_needs = await self._discover_from_change(diff_text, input_text)
        elif plan.discovery_mode == DiscoveryMode.EXPLORATION:
            plan.test_needs = await self._discover_from_exploration(target_url)
        elif plan.discovery_mode == DiscoveryMode.COVERAGE:
            plan.test_needs = await self._discover_from_coverage(input_text)
        elif plan.discovery_mode == DiscoveryMode.FAULT:
            plan.test_needs = await self._discover_from_fault(alert_data or {})

        plan.summary = f"共发现 {len(plan.test_needs)} 条测试需求（{plan.discovery_mode.value} 模式）"
        logger.info(f"[TestArchitect] {plan.summary}")

        return plan

    # ── 模式推断 ──────────────────────────────────────────────────────────

    def _infer_mode(
        self,
        input_text: str,
        diff_text: str,
        alert_data: Optional[Dict],
        target_url: str,
    ) -> DiscoveryMode:
        """自动推断发现模式"""
        if diff_text:
            return DiscoveryMode.CHANGE
        if alert_data:
            return DiscoveryMode.FAULT
        if target_url and not input_text:
            return DiscoveryMode.EXPLORATION
        if any(kw in input_text.lower() for kw in ["覆盖", "盲区", "coverage", "gap"]):
            return DiscoveryMode.COVERAGE
        return DiscoveryMode.REQUIREMENT

    # ── 各发现模式实现 ────────────────────────────────────────────────────

    async def _discover_from_requirement(self, input_text: str) -> List[TestNeed]:
        """需求驱动：PRD → RequirementParser → TestNeeds"""
        from core.requirement_parser import get_requirement_parser
        import json

        parser = get_requirement_parser()
        parsed = parser.parse_text(input_text)
        parsed_str = parser.to_json(parsed)
        parsed_json = json.loads(parsed_str) if isinstance(parsed_str, str) else parsed_str

        needs = []
        for case in parsed_json.get("test_cases", []):
            needs.append(TestNeed(
                title=case.get("title", ""),
                description=case.get("description", ""),
                source=DiscoveryMode.REQUIREMENT,
                priority=case.get("priority", "medium"),
                test_types=[case.get("test_type", "ui_e2e")],
            ))

        # 如果解析器没提取出用例，至少生成一条基于输入的需求
        if not needs:
            needs.append(TestNeed(
                title=input_text[:80],
                description=input_text,
                source=DiscoveryMode.REQUIREMENT,
                priority="medium",
                test_types=["ui_e2e"],
            ))

        return needs

    async def _discover_from_change(self, diff_text: str, input_text: str = "") -> List[TestNeed]:
        """变更驱动：Git diff → AcceptanceEngine → 影响评估 → TestNeeds"""
        from core.acceptance_engine import get_acceptance_engine

        engine = get_acceptance_engine()
        impact = engine.analyze_change_impact(diff_text=diff_text)

        needs = []

        # 如果有 API 变更，添加 API 测试需求
        if impact.has_api_change:
            needs.append(TestNeed(
                title="API 变更回归测试",
                description=f"检测到 API 变更，影响模块: {', '.join(impact.modules_affected[:5])}",
                source=DiscoveryMode.CHANGE,
                priority="high",
                test_types=["api_rest"],
                metadata={"impact_score": impact.impact_score},
            ))

        # 如果有 Schema 变更，添加数据库测试
        if impact.has_schema_change:
            needs.append(TestNeed(
                title="数据库 Schema 变更验证",
                description="检测到数据库 Schema 变更，需要验证数据完整性",
                source=DiscoveryMode.CHANGE,
                priority="critical",
                test_types=["database"],
            ))

        # 如果有配置变更，添加配置验证
        if impact.has_config_change:
            needs.append(TestNeed(
                title="配置变更验证",
                description="检测到配置变更，需要验证系统行为",
                source=DiscoveryMode.CHANGE,
                priority="high",
                test_types=["ui_e2e", "api_rest"],
            ))

        # 通用回归：基于变更文件
        if impact.files_changed:
            needs.append(TestNeed(
                title=f"变更回归测试 ({len(impact.files_changed)} 文件)",
                description=f"变更文件: {', '.join(impact.files_changed[:5])}",
                source=DiscoveryMode.CHANGE,
                priority="medium",
                test_types=["ui_e2e"],
                metadata={"files": impact.files_changed[:10]},
            ))

        return needs

    async def _discover_from_exploration(self, target_url: str) -> List[TestNeed]:
        """探索驱动：Scout + Exploratory → 自主发现"""
        needs = []

        # 先用 ScoutAgent 侦察
        try:
            from agents.scout_agent import ScoutAgent

            scout_result = await ScoutAgent.scout(target_url)

            if scout_result.get("status") == "success":
                needs.append(TestNeed(
                    title=f"探索测试: {scout_result.get('title', target_url)}",
                    description=(
                        f"页面侦察结果: {scout_result.get('visible_text', '')[:200]}\n"
                        f"交互元素: {scout_result.get('interactive_summary', '')[:200]}"
                    ),
                    source=DiscoveryMode.EXPLORATION,
                    priority="medium",
                    target_url=target_url,
                    test_types=["ui_e2e", "accessibility"],
                    metadata={"scout_result": scout_result},
                ))
        except Exception as e:
            logger.warning(f"[TestArchitect] Scout 侦察失败: {e}")
            needs.append(TestNeed(
                title=f"基础测试: {target_url}",
                description=f"Scout 侦察失败 ({e})，执行基础 UI 测试",
                source=DiscoveryMode.EXPLORATION,
                priority="medium",
                target_url=target_url,
                test_types=["ui_e2e"],
            ))

        return needs

    async def _discover_from_coverage(self, input_text: str) -> List[TestNeed]:
        """覆盖驱动：分析现有测试报告 → 找盲区"""
        needs = []

        # 查询历史测试结果，找出从未测过或频繁失败的区域
        from core.tracing import get_tracer
        recent = get_tracer().get_recent_spans(limit=50)

        # 统计各 Agent 的调用频率
        agent_counts: Dict[str, int] = {}
        for span in recent:
            agent = span.get("agent_name", "")
            agent_counts[agent] = agent_counts.get(agent, 0) + 1

        # 找出未覆盖的测试类型
        all_types = {"ui_e2e", "api_rest", "security", "performance", "database", "accessibility"}
        covered = set()
        for span in recent:
            action = span.get("action", "")
            for t in all_types:
                if t in action:
                    covered.add(t)

        uncovered = all_types - covered
        if uncovered:
            needs.append(TestNeed(
                title=f"覆盖盲区: {', '.join(uncovered)}",
                description=f"以下测试类型近期未运行过: {', '.join(uncovered)}",
                source=DiscoveryMode.COVERAGE,
                priority="medium",
                test_types=list(uncovered),
            ))

        if not needs:
            needs.append(TestNeed(
                title="覆盖率良好",
                description="所有测试类型近期均有执行记录",
                source=DiscoveryMode.COVERAGE,
                priority="low",
                test_types=[],
            ))

        return needs

    async def _discover_from_fault(self, alert_data: Dict) -> List[TestNeed]:
        """故障驱动：告警 → 生成针对性回归用例"""
        needs = []

        error_msg = alert_data.get("error", "")
        url = alert_data.get("url", "")
        component = alert_data.get("component", "")

        needs.append(TestNeed(
            title=f"故障回归: {component or error_msg[:50]}",
            description=f"告警信息: {error_msg}\n组件: {component}\nURL: {url}",
            source=DiscoveryMode.FAULT,
            priority="critical",
            target_url=url,
            test_types=["ui_e2e", "api_rest"],
            metadata={"alert": alert_data},
        ))

        return needs


# ── 单例 ─────────────────────────────────────────────────────────────────────

_architect: Optional[TestArchitect] = None


def get_test_architect() -> TestArchitect:
    """获取 TestArchitect 单例"""
    global _architect
    if _architect is None:
        _architect = TestArchitect()
    return _architect
