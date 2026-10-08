# -*- coding: utf-8 -*-
"""
AgentProfile — agent identity configuration manager

Assign each legion agent an identity with a personality, capabilities, and reporting relationships,
load YAML configuration, and generate LLM system prompts automatically.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Profile YAML directory
_PROFILES_DIR = Path(__file__).resolve().parent.parent / "agents" / "profiles"


@dataclass
class AgentProfile:
    """Agent identity profile"""
    agent_id: str                           # "ui_squad"
    name: str                               # "UI testing squad"
    role: str                               # "commander" | "squad" | "specialist"
    personality: str = ""                   # Personality description injected into the LLM system prompt
    model: str = ""                         # Optional agent-specific model
    skills: List[str] = field(default_factory=list)         # Associated skill packages (reserved)
    report_to: Optional[str] = None         # Supervisor agent_id
    supported_types: List[str] = field(default_factory=list)  # Supported test types
    members: List[str] = field(default_factory=list)         # Swarm members (squads only)
    description: str = ""                   # One-line description
    extra: Dict[str, Any] = field(default_factory=dict)      # Extended configuration


class ProfileManager:
    """Agent profile manager"""

    def __init__(self, profiles_dir: Optional[str] = None):
        self._dir = Path(profiles_dir) if profiles_dir else _PROFILES_DIR
        self._profiles: Dict[str, AgentProfile] = {}
        self._load_all()

    # ── Loading ──────────────────────────────────────────────────────────────

    def _load_all(self) -> None:
        """Scan the profiles directory and load all YAML files"""
        if not self._dir.exists():
            logger.warning(f"[ProfileManager] Profile directory does not exist: {self._dir}")
            return

        try:
            import yaml
        except ImportError:
            logger.warning("[ProfileManager] PyYAML is not installed; skipping profile loading")
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
                logger.warning(f"[ProfileManager] Failed to load {f.name}: {e}")

        logger.info(f"[ProfileManager] Loaded {count} agent profiles")

    # ── Queries ──────────────────────────────────────────────────────────────

    def get(self, agent_id: str) -> Optional[AgentProfile]:
        """Get a profile by ID"""
        return self._profiles.get(agent_id)

    def list_all(self) -> List[AgentProfile]:
        """Return all profiles"""
        return list(self._profiles.values())

    def get_squad_members(self, squad_id: str) -> List[AgentProfile]:
        """Get all member profiles for a squad"""
        squad = self._profiles.get(squad_id)
        if not squad or not squad.members:
            return []
        return [self._profiles[m] for m in squad.members if m in self._profiles]

    def get_by_test_type(self, test_type: str) -> List[AgentProfile]:
        """Find agents that support the specified test type"""
        return [
            p for p in self._profiles.values()
            if test_type in p.supported_types or "all" in p.supported_types
        ]

    # ── Prompt generation ────────────────────────────────────────────────────────

    def get_system_prompt(self, agent_id: str) -> str:
        """Generate an LLM system prompt from a profile"""
        profile = self._profiles.get(agent_id)
        if not profile:
            return ""

        parts = [f"You are {profile.name}."]

        if profile.personality:
            parts.append(f"Your personality: {profile.personality}")

        if profile.role == "commander":
            parts.append("You command the testing legion and are responsible for overall coordination and resource allocation.")
        elif profile.role == "squad":
            parts.append(f"You manage the {profile.name} team.")
            if profile.members:
                parts.append(f"Your team members are: {', '.join(profile.members)}")
        elif profile.role == "specialist":
            parts.append(f"You are a professional test executor.")

        if profile.supported_types:
            parts.append(f"Your testing specialties: {', '.join(profile.supported_types)}")

        if profile.description:
            parts.append(profile.description)

        return "\n".join(parts)

    def to_summary(self) -> List[Dict]:
        """Export all profile summaries for API responses"""
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


# ── Singleton ─────────────────────────────────────────────────────────────────────

_manager: Optional[ProfileManager] = None


def get_profile_manager() -> ProfileManager:
    """Get the ProfileManager singleton"""
    global _manager
    if _manager is None:
        _manager = ProfileManager()
    return _manager
