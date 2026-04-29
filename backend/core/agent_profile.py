# -*- coding: utf-8 -*-
"""
AgentProfile — Agent 身份配置管理器

为军团中的每个 Agent 赋予身份（人格、能力、汇报链），
加载 YAML 配置并自动生成 LLM 系统提示词。
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Profile YAML 目录
_PROFILES_DIR = Path(__file__).resolve().parent.parent / "agents" / "profiles"


@dataclass
class AgentProfile:
    """Agent 身份档案"""
    agent_id: str                           # "ui_squad"
    name: str                               # "UI 测试班"
    role: str                               # "commander" | "squad" | "specialist"
    personality: str = ""                   # 人格描述 → 注入 LLM system prompt
    model: str = ""                         # 可按 Agent 指定模型
    skills: List[str] = field(default_factory=list)         # 关联技能包（预留）
    report_to: Optional[str] = None         # 汇报上级 agent_id
    supported_types: List[str] = field(default_factory=list)  # 支持的测试类型
    members: List[str] = field(default_factory=list)         # 蜂群成员（squad 专用）
    description: str = ""                   # 一行描述
    extra: Dict[str, Any] = field(default_factory=dict)      # 扩展配置


class ProfileManager:
    """Agent Profile 管理器"""

    def __init__(self, profiles_dir: Optional[str] = None):
        self._dir = Path(profiles_dir) if profiles_dir else _PROFILES_DIR
        self._profiles: Dict[str, AgentProfile] = {}
        self._load_all()

    # ── 加载 ──────────────────────────────────────────────────────────────

    def _load_all(self) -> None:
        """扫描 profiles 目录，加载所有 YAML"""
        if not self._dir.exists():
            logger.warning(f"[ProfileManager] Profile 目录不存在: {self._dir}")
            return

        try:
            import yaml
        except ImportError:
            logger.warning("[ProfileManager] PyYAML 未安装，跳过 Profile 加载")
            return

        count = 0
        for f in sorted(self._dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if not data or not isinstance(data, dict):
                    continue
                profile = AgentProfile(
                    agent_id=data.get("agent_id", f.stem),
                    name=data.get("name", f.stem),
                    role=data.get("role", "specialist"),
                    personality=data.get("personality", ""),
                    model=data.get("model", ""),
                    skills=data.get("skills", []),
                    report_to=data.get("report_to"),
                    supported_types=data.get("supported_types", []),
                    members=data.get("members", []),
                    description=data.get("description", ""),
                    extra={k: v for k, v in data.items()
                           if k not in ("agent_id", "name", "role", "personality",
                                        "model", "skills", "report_to",
                                        "supported_types", "members", "description")},
                )
                self._profiles[profile.agent_id] = profile
                count += 1
            except Exception as e:
                logger.warning(f"[ProfileManager] 加载 {f.name} 失败: {e}")

        logger.info(f"[ProfileManager] 加载 {count} 个 Agent Profile")

    # ── 查询 ──────────────────────────────────────────────────────────────

    def get(self, agent_id: str) -> Optional[AgentProfile]:
        """按 ID 获取 Profile"""
        return self._profiles.get(agent_id)

    def list_all(self) -> List[AgentProfile]:
        """返回全部 Profile"""
        return list(self._profiles.values())

    def get_squad_members(self, squad_id: str) -> List[AgentProfile]:
        """获取某个 squad 的所有成员 Profile"""
        squad = self._profiles.get(squad_id)
        if not squad or not squad.members:
            return []
        return [self._profiles[m] for m in squad.members if m in self._profiles]

    def get_by_test_type(self, test_type: str) -> List[AgentProfile]:
        """查找能处理指定测试类型的 Agent"""
        return [
            p for p in self._profiles.values()
            if test_type in p.supported_types or "all" in p.supported_types
        ]

    # ── 提示词生成 ────────────────────────────────────────────────────────

    def get_system_prompt(self, agent_id: str) -> str:
        """根据 Profile 生成 LLM 系统提示词"""
        profile = self._profiles.get(agent_id)
        if not profile:
            return ""

        parts = [f"你是 {profile.name}。"]

        if profile.personality:
            parts.append(f"你的性格特征：{profile.personality}")

        if profile.role == "commander":
            parts.append("你是测试军团的总指挥，负责全局协调和资源调配。")
        elif profile.role == "squad":
            parts.append(f"你负责管理{profile.name}团队。")
            if profile.members:
                parts.append(f"你的团队成员包括：{', '.join(profile.members)}")
        elif profile.role == "specialist":
            parts.append(f"你是一名专业的测试执行者。")

        if profile.supported_types:
            parts.append(f"你擅长的测试类型：{', '.join(profile.supported_types)}")

        if profile.description:
            parts.append(profile.description)

        return "\n".join(parts)

    def to_summary(self) -> List[Dict]:
        """导出所有 Profile 摘要（供 API 返回）"""
        return [
            {
                "agent_id": p.agent_id,
                "name": p.name,
                "role": p.role,
                "supported_types": p.supported_types,
                "report_to": p.report_to,
                "members": p.members,
            }
            for p in self._profiles.values()
        ]


# ── 单例 ─────────────────────────────────────────────────────────────────────

_manager: Optional[ProfileManager] = None


def get_profile_manager() -> ProfileManager:
    """获取 ProfileManager 单例"""
    global _manager
    if _manager is None:
        _manager = ProfileManager()
    return _manager
