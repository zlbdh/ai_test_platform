# -*- coding: utf-8 -*-
"""
SkillLoader — 技能包加载引擎

加载 SKILL.yaml + strategy.md，为 Agent 注入测试策略知识。
借鉴 OpenClaw 的 SKILL.md 理念，适配测试领域。

技能包目录结构：
    skills/test_skills/
        login_e2e/
            SKILL.yaml          # 元数据
            strategy.md         # LLM 可读测试策略
            examples/           # 可选：示例用例
        form_validation/
            SKILL.yaml
            strategy.md
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills" / "test_skills"


@dataclass
class TestSkill:
    """一个测试技能包"""
    skill_id: str                           # 目录名，如 "login_e2e"
    name: str                               # 显示名
    description: str                        # 简要描述
    version: str = "1.0"
    test_type: str = "ui_e2e"               # 关联测试类型
    target_squad: str = ""                  # 目标 squad
    tags: List[str] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    strategy_text: str = ""                 # strategy.md 全文（注入 LLM）
    examples: List[Dict[str, Any]] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_prompt(self) -> str:
        """生成可注入 LLM 的策略提示词"""
        parts = [f"## 技能：{self.name}", ""]
        if self.description:
            parts.append(f"**描述**：{self.description}")
        if self.preconditions:
            parts.append(f"**前置条件**：")
            for p in self.preconditions:
                parts.append(f"  - {p}")
        if self.strategy_text:
            parts.append("")
            parts.append("**测试策略**：")
            parts.append(self.strategy_text)
        if self.examples:
            parts.append("")
            parts.append(f"**参考用例**：共 {len(self.examples)} 条")
        return "\n".join(parts)


class SkillLoader:
    """技能包加载器"""

    def __init__(self, skills_dir: Optional[str] = None):
        self._dir = Path(skills_dir) if skills_dir else _SKILLS_DIR
        self._skills: Dict[str, TestSkill] = {}
        self._load_all()

    def _load_all(self) -> None:
        """扫描 skills 目录，加载所有技能包"""
        if not self._dir.exists():
            logger.warning(f"[SkillLoader] 技能目录不存在: {self._dir}")
            return

        try:
            import yaml
        except ImportError:
            logger.warning("[SkillLoader] PyYAML 未安装，跳过技能加载")
            return

        import json

        count = 0
        for skill_dir in sorted(self._dir.iterdir()):
            if not skill_dir.is_dir():
                continue

            yaml_file = skill_dir / "SKILL.yaml"
            if not yaml_file.exists():
                continue

            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if not data or not isinstance(data, dict):
                    continue

                # 加载 strategy.md
                strategy_text = ""
                strategy_file = skill_dir / "strategy.md"
                if strategy_file.exists():
                    strategy_text = strategy_file.read_text(encoding="utf-8")

                # 加载 examples（JSON 文件）
                examples = []
                examples_dir = skill_dir / "examples"
                if examples_dir.exists():
                    for f in sorted(examples_dir.glob("*.json")):
                        try:
                            examples.extend(json.loads(f.read_text(encoding="utf-8")))
                        except Exception:
                            pass

                skill = TestSkill(
                    skill_id=skill_dir.name,
                    name=data.get("name", skill_dir.name),
                    description=data.get("description", ""),
                    version=data.get("version", "1.0"),
                    test_type=data.get("test_type", "ui_e2e"),
                    target_squad=data.get("target_squad", ""),
                    tags=data.get("tags", []),
                    preconditions=data.get("preconditions", []),
                    strategy_text=strategy_text,
                    examples=examples,
                    extra={k: v for k, v in data.items()
                           if k not in ("name", "description", "version", "test_type",
                                        "target_squad", "tags", "preconditions")},
                )
                self._skills[skill.skill_id] = skill
                count += 1
            except Exception as e:
                logger.warning(f"[SkillLoader] 加载 {skill_dir.name} 失败: {e}")

        logger.info(f"[SkillLoader] 加载 {count} 个技能包")

    # ── 查询 ──────────────────────────────────────────────────────────────

    def get(self, skill_id: str) -> Optional[TestSkill]:
        """按 ID 获取技能包"""
        return self._skills.get(skill_id)

    def list_all(self) -> List[TestSkill]:
        """返回全部技能包"""
        return list(self._skills.values())

    def get_by_test_type(self, test_type: str) -> List[TestSkill]:
        """按测试类型查找技能包"""
        return [s for s in self._skills.values() if s.test_type == test_type]

    def get_by_squad(self, squad_id: str) -> List[TestSkill]:
        """按 squad 查找技能包"""
        return [s for s in self._skills.values() if s.target_squad == squad_id]

    def get_by_tags(self, tags: List[str]) -> List[TestSkill]:
        """按标签查找技能包"""
        tag_set = set(tags)
        return [s for s in self._skills.values() if tag_set & set(s.tags)]

    def get_strategy_prompt(self, skill_ids: List[str]) -> str:
        """将多个技能包的策略合并为一个 LLM 提示词"""
        parts = ["# 测试技能策略", ""]
        for sid in skill_ids:
            skill = self._skills.get(sid)
            if skill:
                parts.append(skill.to_prompt())
                parts.append("")
                parts.append("---")
                parts.append("")
        return "\n".join(parts)

    def to_summary(self) -> List[Dict]:
        """导出所有技能包摘要（供 API）"""
        return [
            {
                "skill_id": s.skill_id,
                "name": s.name,
                "description": s.description,
                "test_type": s.test_type,
                "target_squad": s.target_squad,
                "tags": s.tags,
                "has_strategy": bool(s.strategy_text),
                "examples_count": len(s.examples),
            }
            for s in self._skills.values()
        ]


# ── 单例 ─────────────────────────────────────────────────────────────────────

_loader: Optional[SkillLoader] = None


def get_skill_loader() -> SkillLoader:
    """获取 SkillLoader 单例"""
    global _loader
    if _loader is None:
        _loader = SkillLoader()
    return _loader
