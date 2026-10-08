# -*- coding: utf-8 -*-
"""
SkillLoader — skill-package loader

Load SKILL.yaml and strategy.md to give agents testing strategy knowledge.
Adapt OpenClaw's SKILL.md concept to testing.

Skill-package directory structure:
    skills/test_skills/
        login_e2e/
            SKILL.yaml          # Metadata
            strategy.md         # LLM-readable test strategy
            examples/           # Optional example cases
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
    """A test skill package"""
    skill_id: str                           # Directory name, such as "login_e2e"
    name: str                               # Display name
    description: str                        # Brief description
    version: str = "1.0"
    test_type: str = "ui_e2e"               # Associated test type
    target_squad: str = ""                  # Target squad
    tags: List[str] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    strategy_text: str = ""                 # Full strategy.md text injected into the LLM
    examples: List[Dict[str, Any]] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_prompt(self) -> str:
        """Generate a strategy prompt for the LLM"""
        parts = [f"## Skill: {self.name}", ""]
        if self.description:
            parts.append(f"**Description**: {self.description}")
        if self.preconditions:
            parts.append(f"**Prerequisites**:")
            for p in self.preconditions:
                parts.append(f"  - {p}")
        if self.strategy_text:
            parts.append("")
            parts.append("**Test strategy**:")
            parts.append(self.strategy_text)
        if self.examples:
            parts.append("")
            parts.append(f"**Example cases**: {len(self.examples)}")
        return "\n".join(parts)


class SkillLoader:
    """Skill-package loader"""

    def __init__(self, skills_dir: Optional[str] = None):
        self._dir = Path(skills_dir) if skills_dir else _SKILLS_DIR
        self._skills: Dict[str, TestSkill] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Scan the skills directory and load all skill packages"""
        if not self._dir.exists():
            logger.warning(f"[SkillLoader] Skills directory does not exist: {self._dir}")
            return

        try:
            import yaml
        except ImportError:
            logger.warning("[SkillLoader] PyYAML is not installed; skipping skill loading")
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

                # Load strategy.md
                strategy_text = ""
                strategy_file = skill_dir / "strategy.md"
                if strategy_file.exists():
                    strategy_text = strategy_file.read_text(encoding="utf-8")

                # Load examples from JSON files
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
                logger.warning(f"[SkillLoader] Failed to load {skill_dir.name}: {e}")

        logger.info(f"[SkillLoader] Loaded {count} skill packages")

    # ── Queries ──────────────────────────────────────────────────────────────

    def get(self, skill_id: str) -> Optional[TestSkill]:
        """Get a skill package by ID"""
        return self._skills.get(skill_id)

    def list_all(self) -> List[TestSkill]:
        """Return all skill packages"""
        return list(self._skills.values())

    def get_by_test_type(self, test_type: str) -> List[TestSkill]:
        """Find skill packages by test type"""
        return [s for s in self._skills.values() if s.test_type == test_type]

    def get_by_squad(self, squad_id: str) -> List[TestSkill]:
        """Find skill packages by squad"""
        return [s for s in self._skills.values() if s.target_squad == squad_id]

    def get_by_tags(self, tags: List[str]) -> List[TestSkill]:
        """Find skill packages by tag"""
        tag_set = set(tags)
        return [s for s in self._skills.values() if tag_set & set(s.tags)]

    def get_strategy_prompt(self, skill_ids: List[str]) -> str:
        """Combine strategies from multiple skill packages into one LLM prompt"""
        parts = ["# Test skill strategies", ""]
        for sid in skill_ids:
            skill = self._skills.get(sid)
            if skill:
                parts.append(skill.to_prompt())
                parts.append("")
                parts.append("---")
                parts.append("")
        return "\n".join(parts)

    def to_summary(self) -> List[Dict]:
        """Export summaries of all skill packages for the API"""
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


# ── Singleton ─────────────────────────────────────────────────────────────────────

_loader: Optional[SkillLoader] = None


def get_skill_loader() -> SkillLoader:
    """Get the SkillLoader singleton"""
    global _loader
    if _loader is None:
        _loader = SkillLoader()
    return _loader
