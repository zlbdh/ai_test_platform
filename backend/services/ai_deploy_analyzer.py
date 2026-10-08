# -*- coding: utf-8 -*-
"""
AI deployment analyzer: use an LLM to analyze project structure and recommend deployment settings.

Inspired by the Railway AI-assisted DevOps workflow:
  Clone → collect project files → construct prompt → analyze with LLM → structured JSON configuration

Fall back to the rule engine (detect_tech_stack) when the LLM call fails.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Key files to collect, in priority order
KEY_FILES = [
    "package.json",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "requirements.txt",
    "pyproject.toml",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".env.example",
    "vite.config.ts",
    "vite.config.js",
    "vue.config.js",
    "next.config.js",
    "next.config.mjs",
    "nuxt.config.ts",
    "angular.json",
    "application.yml",
    "application.properties",
    "application.yaml",
    "Makefile",
    "Procfile",
]

# Directories to ignore
IGNORE_DIRS = {
    "node_modules", ".git", ".idea", ".vscode", "__pycache__",
    "dist", "build", "target", ".gradle", ".mvn", "vendor",
    ".next", ".nuxt", ".output", "coverage", ".cache",
}

# Per-file and total context character limits to prevent token overflow
MAX_FILE_SIZE = 1500
MAX_TOTAL_CONTEXT = 6000


SYSTEM_PROMPT = """You are a senior DevOps engineer. Recommend accurate deployment settings based on the project source structure.

Rules:
1. Analyze only the supplied content.
2. start_cmd is the development startup command; add --host 0.0.0.0 for frontend projects.
3. Infer port from configuration or the default for the framework.
4. Retain any current effective environment variables unless the source or user information explicitly requires a change.
5. Do not arbitrarily change test to dev, or alter environment identifiers such as Nacos namespaces or groups.
6. Write concise notes in English.
7. confidence is a value from 0.0 to 1.0.

Return only JSON, without Markdown code fences."""

USER_PROMPT_TEMPLATE = """Analyze the following project and provide deployment settings.

Repository: {label} ({repo_url})

Directory structure:
{tree}

Key files:
{files_content}

Current effective environment variables (retain unless a change is necessary):
{current_env_text}

JSON format:
{{"tech_stack":"","install_cmd":"","start_cmd":"","build_cmd":"","port":0,"env_vars":{{}},"notes":"","confidence":0.9}}"""


def _get_dir_tree(root: Path, max_depth: int = 2, prefix: str = "") -> str:
    """Generate a compact directory tree"""
    lines = []
    try:
        entries = sorted(root.iterdir(), key=lambda e: (not e.is_dir(), e.name))
    except PermissionError:
        return ""

    dirs = [e for e in entries if e.is_dir() and e.name not in IGNORE_DIRS]
    files = [e for e in entries if e.is_file()]

    for f in files[:15]:
        lines.append(f"{prefix}{f.name}")
    if len(files) > 15:
        lines.append(f"{prefix}... (+{len(files) - 15})")

    for d in dirs[:10]:
        lines.append(f"{prefix}{d.name}/")
        if max_depth > 1:
            subtree = _get_dir_tree(d, max_depth - 1, prefix + "  ")
            if subtree:
                lines.append(subtree)

    return "\n".join(lines)


def _read_key_files(root: Path) -> str:
    """Read key configuration files within the total size limit"""
    sections = []
    total = 0

    for fname in KEY_FILES:
        if total >= MAX_TOTAL_CONTEXT:
            break
        fpath = root / fname
        if fpath.exists() and fpath.is_file():
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
                if len(content) > MAX_FILE_SIZE:
                    content = content[:MAX_FILE_SIZE] + "\n...(truncated)"
                sections.append(f"### {fname}\n```\n{content}\n```")
                total += len(content)
            except Exception:
                pass

    return "\n\n".join(sections) if sections else "(No configuration files found)"


def collect_project_context(project_dir: Path, label: str = "", repo_url: str = "", current_env_text: str = "") -> str:
    """Collect project context"""
    tree = _get_dir_tree(project_dir)
    files_content = _read_key_files(project_dir)
    return USER_PROMPT_TEMPLATE.format(
        label=label or "Unknown",
        repo_url=repo_url or "Unknown",
        tree=tree,
        files_content=files_content,
        current_env_text=current_env_text or "(No effective environment variables detected)",
    )


def _parse_llm_response(text: str) -> Optional[Dict]:
    """Extract JSON from an LLM response"""
    import re
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    return None


def _fallback_detect(project_dir: Path) -> Dict:
    """Fall back to the rule engine when the LLM fails"""
    from services.deploy_service import detect_tech_stack
    detected = detect_tech_stack(project_dir)
    return {
        "tech_stack": detected.get("tech_stack", ""),
        "install_cmd": detected.get("install_cmd", ""),
        "start_cmd": detected.get("start_cmd", ""),
        "build_cmd": "",
        "port": detected.get("port", 0),
        "env_vars": {},
        "notes": "⚠️ AI analysis failed; using automatic rule-based detection",
        "confidence": 0.6,
        "source": "rule_fallback",
    }


async def analyze_project(
    project_dir: Path,
    label: str = "",
    repo_url: str = "",
    memory_hint: str = "",
    current_env_text: str = "",
) -> Dict:
    """
    Analyze project structure with an LLM and return deployment recommendations.
    Use the shared LangChain interface, whose llm_manager handles gateway compatibility.
    Fall back to the rule engine when the LLM fails.
    """
    try:
        from core.llm_manager import get_llm_for_role, traced_invoke
        from langchain_core.messages import SystemMessage, HumanMessage
    except ImportError as e:
        logger.warning(f"[AI analysis] LLM unavailable; falling back: {e}")
        return _fallback_detect(project_dir)

    # 1. Collect project context
    user_prompt = collect_project_context(project_dir, label, repo_url, current_env_text=current_env_text)
    logger.info(f"[AI analysis] Project: {project_dir.name}, prompt length={len(user_prompt)}")

    # 2. Call the globally configured LLM, such as claude-opus-4-6-thinking
    try:
        import asyncio
        llm = get_llm_for_role("planner")
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt + (
                f"\n\nDeployment memory (prior experience; consult first):\n{memory_hint}" if memory_hint else ""
            )),
        ]
        # Use asyncio.to_thread to avoid blocking the event loop; reasoning models may take 60+ seconds
        result = await asyncio.to_thread(
            traced_invoke, llm, messages,
            agent_name="deploy_analyzer", action="analyze_project"
        )
        raw_text = result.content
        logger.info(f"[AI analysis] LLM returned {len(raw_text)} characters")
    except Exception as e:
        logger.warning(f"[AI analysis] LLM call failed; falling back to the rule engine: {e}")
        return _fallback_detect(project_dir)

    # 3. Parse JSON
    parsed = _parse_llm_response(raw_text)
    if not parsed:
        logger.warning(f"[AI analysis] JSON parsing failed; falling back")
        return _fallback_detect(project_dir)

    # 4. Normalize output
    config = {
        "tech_stack": str(parsed.get("tech_stack", "")),
        "install_cmd": str(parsed.get("install_cmd", "")),
        "start_cmd": str(parsed.get("start_cmd", "")),
        "build_cmd": str(parsed.get("build_cmd", "")),
        "port": int(parsed.get("port", 0)),
        "env_vars": parsed.get("env_vars", {}),
        "notes": str(parsed.get("notes", "")),
        "confidence": float(parsed.get("confidence", 0.0)),
        "source": "ai",
    }
    logger.info(f"[AI analysis] ✅ {config['tech_stack']} | confidence={config['confidence']}")
    # 5. Suggest pom.xml changes for Maven projects
    pom_suggestions = detect_pom_suggestions(project_dir)
    if pom_suggestions:
        config["suggested_changes"] = pom_suggestions

    return config


def detect_pom_suggestions(project_dir: Path) -> list:
    """
    Detect Maven multi-module project modules that may need to be excluded through a profile.
    Return suggested_changes for user confirmation.
    """
    import re as _re
    suggestions = []

    # Known patterns for modules that may fail to compile
    PROBLEMATIC_MODULES = {"sample-aigc", "sample-api-aigc"}

    for pom_path in project_dir.rglob("pom.xml"):
        if pom_path.resolve() == (project_dir / "pom.xml").resolve():
            continue  # Skip the root pom

        try:
            content = pom_path.read_text(encoding="utf-8")
        except Exception:
            continue

        # Extract the current <modules> list
        modules_match = _re.search(r'<modules>(.*?)</modules>', content, _re.DOTALL)
        if not modules_match:
            continue

        modules_block = modules_match.group(1)
        current_modules = _re.findall(r'<module>([\w-]+)</module>', modules_block)

        # Check for known problematic modules
        problematic_found = [m for m in current_modules if m in PROBLEMATIC_MODULES]
        if not problematic_found:
            continue

        # Check whether those module directories exist and show signs of compilation problems
        rel_path = str(pom_path.relative_to(project_dir).parent)
        for mod in problematic_found:
            mod_dir = pom_path.parent / mod
            # Generate a Maven profile recommendation
            remaining = [m for m in current_modules if m != mod]
            suggestion = {
                "file": str(pom_path.relative_to(project_dir)),
                "type": "maven_profile",
                "module": mod,
                "description": f"Move {mod} into a Maven profile and exclude it from the default build",
                "original_modules": current_modules,
                "new_modules": remaining,
                "profile_id": "aigc",
                "profile_modules": [mod],
            }
            suggestions.append(suggestion)

    return suggestions


# AI confirmation prompt

REFINE_SYSTEM_PROMPT = """You are a senior DevOps engineer. The user has supplied additional deployment context.
Combine the initial AI analysis with this information to produce final deployment settings.

Rules:
1. If a server address is supplied, describe the deployment target in notes.
2. If a database connection is supplied, add it to env_vars.
3. Merge any supplied environment variables into env_vars.
4. Adjust commands or configuration according to the user notes.
5. Confidence should increase as the additional information becomes more complete.
6. Briefly explain your adjustments in notes, in English.

Return only JSON, without Markdown code fences."""

REFINE_USER_TEMPLATE = """Initial AI analysis:
{initial_config}

Additional deployment context supplied by the user:
- Target server: {server_address}
- Database connection: {db_connection}
- Environment variables:
{env_vars_text}
- Notes: {user_notes}

Combine this information and return the final deployment settings as JSON:
{{"tech_stack":"","install_cmd":"","start_cmd":"","build_cmd":"","port":0,"env_vars":{{}},"notes":"","confidence":0.9}}"""


async def refine_deploy_config(initial_config: Dict, deploy_context: Dict) -> Dict:
    """
    AI confirmation: refine deployment settings using additional user context.
    """
    try:
        from core.llm_manager import get_llm_for_role, traced_invoke
        from langchain_core.messages import SystemMessage, HumanMessage
    except ImportError as e:
        logger.warning(f"[AI confirmation] LLM unavailable: {e}")
        # Fallback: merge user context directly into the initial configuration
        return _merge_context_fallback(initial_config, deploy_context)

    # Construct the environment variable text
    env_vars_text = ""
    if deploy_context.get("env_vars"):
        env_vars_text = deploy_context["env_vars"]
    if not env_vars_text:
        env_vars_text = "(None)"

    user_prompt = REFINE_USER_TEMPLATE.format(
        initial_config=json.dumps(initial_config, ensure_ascii=False, indent=2),
        server_address=deploy_context.get("server_address", "(Not provided)"),
        db_connection=deploy_context.get("db_connection", "(Not provided)"),
        env_vars_text=env_vars_text,
        user_notes=deploy_context.get("user_notes", "(None)"),
    )

    try:
        import asyncio
        llm = get_llm_for_role("planner")
        messages = [
            SystemMessage(content=REFINE_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]
        result = await asyncio.to_thread(
            traced_invoke, llm, messages,
            agent_name="deploy_analyzer", action="refine_config"
        )
        raw_text = result.content
        logger.info(f"[AI confirmation] LLM returned {len(raw_text)} characters")
    except Exception as e:
        logger.warning(f"[AI confirmation] LLM call failed; falling back: {e}")
        return _merge_context_fallback(initial_config, deploy_context)

    parsed = _parse_llm_response(raw_text)
    if not parsed:
        logger.warning("[AI confirmation] JSON parsing failed; falling back")
        return _merge_context_fallback(initial_config, deploy_context)

    config = {
        "tech_stack": str(parsed.get("tech_stack", initial_config.get("tech_stack", ""))),
        "install_cmd": str(parsed.get("install_cmd", initial_config.get("install_cmd", ""))),
        "start_cmd": str(parsed.get("start_cmd", initial_config.get("start_cmd", ""))),
        "build_cmd": str(parsed.get("build_cmd", initial_config.get("build_cmd", ""))),
        "port": int(parsed.get("port", initial_config.get("port", 0))),
        "env_vars": parsed.get("env_vars", initial_config.get("env_vars", {})),
        "notes": str(parsed.get("notes", "")),
        "confidence": float(parsed.get("confidence", 0.0)),
        "source": "ai_refined",
    }
    logger.info(f"[AI confirmation] ✅ confidence={config['confidence']}")
    return config


def _merge_context_fallback(initial_config: Dict, deploy_context: Dict) -> Dict:
    """Merge user context manually when the LLM is unavailable"""
    config = dict(initial_config)
    env_vars = dict(config.get("env_vars", {}))

    # Merge database connection
    if deploy_context.get("db_connection"):
        env_vars["DATABASE_URL"] = deploy_context["db_connection"]

    # Merge user-supplied environment variables
    if deploy_context.get("env_vars"):
        for line in deploy_context["env_vars"].strip().split("\n"):
            line = line.strip()
            if "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()

    config["env_vars"] = env_vars

    # Merge notes
    notes = [config.get("notes", "")]
    if deploy_context.get("server_address"):
        notes.append(f"Target server: {deploy_context['server_address']}")
    if deploy_context.get("user_notes"):
        notes.append(deploy_context["user_notes"])
    config["notes"] = " | ".join(n for n in notes if n)
    config["source"] = "context_merged"
    return config

