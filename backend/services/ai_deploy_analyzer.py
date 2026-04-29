# -*- coding: utf-8 -*-
"""
AI 部署分析器 — 用 LLM 深度分析项目结构并生成部署配置推荐

参考 Railway AI Assisted DevOps 模式:
  克隆完成 → 采集项目文件 → 构造 Prompt → LLM 分析 → 结构化 JSON 配置

若 LLM 调用失败，自动降级到规则引擎 (detect_tech_stack)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# 需要采集的关键文件 (按优先级排列)
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

# 忽略的目录
IGNORE_DIRS = {
    "node_modules", ".git", ".idea", ".vscode", "__pycache__",
    "dist", "build", "target", ".gradle", ".mvn", "vendor",
    ".next", ".nuxt", ".output", "coverage", ".cache",
}

# 单个文件最大 / 总上下文最大字符数 (严控避免 token 溢出)
MAX_FILE_SIZE = 1500
MAX_TOTAL_CONTEXT = 6000


SYSTEM_PROMPT = """你是一名资深 DevOps 工程师。根据项目源码结构，精准推荐部署配置。

规则:
1. 只基于给定内容分析
2. start_cmd 是开发模式启动命令；前端项目加 --host 0.0.0.0
3. port 根据配置或框架默认端口推断
4. 如果给出了“当前生效环境变量”，默认沿用它们，除非源码或用户信息明确要求变更
5. 不要凭空把 test 改成 dev，也不要随意改动 Nacos 命名空间、分组等环境标识
6. notes 用简短中文说明
7. confidence 为信心度 (0.0-1.0)

回复纯 JSON，不要 markdown 代码块。"""

USER_PROMPT_TEMPLATE = """分析以下项目并给出部署配置。

仓库: {label} ({repo_url})

目录结构:
{tree}

关键文件:
{files_content}

当前生效环境变量（如无必要请沿用）:
{current_env_text}

JSON 格式:
{{"tech_stack":"","install_cmd":"","start_cmd":"","build_cmd":"","port":0,"env_vars":{{}},"notes":"","confidence":0.9}}"""


def _get_dir_tree(root: Path, max_depth: int = 2, prefix: str = "") -> str:
    """生成简洁的目录树"""
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
    """读取关键配置文件内容（严控总量）"""
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
                    content = content[:MAX_FILE_SIZE] + "\n...(截断)"
                sections.append(f"### {fname}\n```\n{content}\n```")
                total += len(content)
            except Exception:
                pass

    return "\n\n".join(sections) if sections else "(未找到配置文件)"


def collect_project_context(project_dir: Path, label: str = "", repo_url: str = "", current_env_text: str = "") -> str:
    """采集项目上下文"""
    tree = _get_dir_tree(project_dir)
    files_content = _read_key_files(project_dir)
    return USER_PROMPT_TEMPLATE.format(
        label=label or "未知",
        repo_url=repo_url or "未知",
        tree=tree,
        files_content=files_content,
        current_env_text=current_env_text or "(未检测到当前生效环境变量)",
    )


def _parse_llm_response(text: str) -> Optional[Dict]:
    """从 LLM 响应中提取 JSON"""
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
    """LLM 失败时降级到规则引擎"""
    from services.deploy_service import detect_tech_stack
    detected = detect_tech_stack(project_dir)
    return {
        "tech_stack": detected.get("tech_stack", ""),
        "install_cmd": detected.get("install_cmd", ""),
        "start_cmd": detected.get("start_cmd", ""),
        "build_cmd": "",
        "port": detected.get("port", 0),
        "env_vars": {},
        "notes": "⚠️ AI 分析失败，已降级为规则引擎自动检测",
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
    调用 LLM 分析项目结构并返回部署配置推荐。
    使用 LangChain 统一调用（llm_manager 已修复网关兼容性），LLM 失败时自动降级到规则引擎。
    """
    try:
        from core.llm_manager import get_llm_for_role, traced_invoke
        from langchain_core.messages import SystemMessage, HumanMessage
    except ImportError as e:
        logger.warning(f"[AI 分析] LLM 不可用，降级: {e}")
        return _fallback_detect(project_dir)

    # 1. 采集项目上下文
    user_prompt = collect_project_context(project_dir, label, repo_url, current_env_text=current_env_text)
    logger.info(f"[AI 分析] 项目: {project_dir.name}, prompt 长度={len(user_prompt)}")

    # 2. 调用 LLM (使用全局配置的模型，如 claude-opus-4-6-thinking)
    try:
        import asyncio
        llm = get_llm_for_role("planner")
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt + (
                f"\n\n部署记忆（历史经验，优先参考）:\n{memory_hint}" if memory_hint else ""
            )),
        ]
        # 使用 asyncio.to_thread 避免阻塞事件循环（thinking 模型可能耗时 60s+）
        result = await asyncio.to_thread(
            traced_invoke, llm, messages,
            agent_name="deploy_analyzer", action="analyze_project"
        )
        raw_text = result.content
        logger.info(f"[AI 分析] LLM 返回 {len(raw_text)} 字符")
    except Exception as e:
        logger.warning(f"[AI 分析] LLM 调用失败，降级到规则引擎: {e}")
        return _fallback_detect(project_dir)

    # 3. 解析 JSON
    parsed = _parse_llm_response(raw_text)
    if not parsed:
        logger.warning(f"[AI 分析] JSON 解析失败，降级")
        return _fallback_detect(project_dir)

    # 4. 标准化输出
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
    logger.info(f"[AI 分析] ✅ {config['tech_stack']} | confidence={config['confidence']}")
    # 5. 检测 pom.xml 建议修改（Maven 项目）
    pom_suggestions = detect_pom_suggestions(project_dir)
    if pom_suggestions:
        config["suggested_changes"] = pom_suggestions

    return config


def detect_pom_suggestions(project_dir: Path) -> list:
    """
    检测 Maven 多模块项目中可能需要 Profile 排除的模块。
    返回 suggested_changes 列表供用户确认。
    """
    import re as _re
    suggestions = []

    # 已知可能编译失败的模块模式
    PROBLEMATIC_MODULES = {"sample-aigc", "sample-api-aigc"}

    for pom_path in project_dir.rglob("pom.xml"):
        if pom_path.resolve() == (project_dir / "pom.xml").resolve():
            continue  # 跳过根 pom

        try:
            content = pom_path.read_text(encoding="utf-8")
        except Exception:
            continue

        # 提取当前 <modules> 中的模块列表
        modules_match = _re.search(r'<modules>(.*?)</modules>', content, _re.DOTALL)
        if not modules_match:
            continue

        modules_block = modules_match.group(1)
        current_modules = _re.findall(r'<module>([\w-]+)</module>', modules_block)

        # 检查是否包含已知问题模块
        problematic_found = [m for m in current_modules if m in PROBLEMATIC_MODULES]
        if not problematic_found:
            continue

        # 检查这些模块的目录是否存在、是否有编译问题的迹象
        rel_path = str(pom_path.relative_to(project_dir).parent)
        for mod in problematic_found:
            mod_dir = pom_path.parent / mod
            # 生成 Maven Profile 建议
            remaining = [m for m in current_modules if m != mod]
            suggestion = {
                "file": str(pom_path.relative_to(project_dir)),
                "type": "maven_profile",
                "module": mod,
                "description": f"将 {mod} 移至 Maven Profile 中，默认不参与编译",
                "original_modules": current_modules,
                "new_modules": remaining,
                "profile_id": "aigc",
                "profile_modules": [mod],
            }
            suggestions.append(suggestion)

    return suggestions


# ── AI 二次确认 Prompt ─────────────────────────────────────────────────────────

REFINE_SYSTEM_PROMPT = """你是一名资深 DevOps 工程师。用户已经提供了额外的部署上下文信息。
请综合初始 AI 分析结果和用户补充的信息，输出最终的部署配置。

规则:
1. 如果用户提供了服务器地址，在 notes 中说明部署目标
2. 如果用户提供了数据库连接，将其加入 env_vars
3. 如果用户提供了环境变量，合并到 env_vars 中
4. 根据用户备注调整命令或配置
5. confidence 应该随着用户补充信息的完善而提高
6. notes 中简要说明你做了哪些调整

回复纯 JSON，不要 markdown 代码块。"""

REFINE_USER_TEMPLATE = """初始 AI 分析结果:
{initial_config}

用户补充的部署上下文:
- 目标服务器: {server_address}
- 数据库连接: {db_connection}
- 环境变量:
{env_vars_text}
- 备注: {user_notes}

请综合以上信息，输出最终部署配置 JSON:
{{"tech_stack":"","install_cmd":"","start_cmd":"","build_cmd":"","port":0,"env_vars":{{}},"notes":"","confidence":0.9}}"""


async def refine_deploy_config(initial_config: Dict, deploy_context: Dict) -> Dict:
    """
    AI 二次确认：结合用户补充的部署上下文，优化部署配置。
    """
    try:
        from core.llm_manager import get_llm_for_role, traced_invoke
        from langchain_core.messages import SystemMessage, HumanMessage
    except ImportError as e:
        logger.warning(f"[AI 确认] LLM 不可用: {e}")
        # 降级：直接将用户上下文合并到初始配置
        return _merge_context_fallback(initial_config, deploy_context)

    # 构造环境变量文本
    env_vars_text = ""
    if deploy_context.get("env_vars"):
        env_vars_text = deploy_context["env_vars"]
    if not env_vars_text:
        env_vars_text = "(无)"

    user_prompt = REFINE_USER_TEMPLATE.format(
        initial_config=json.dumps(initial_config, ensure_ascii=False, indent=2),
        server_address=deploy_context.get("server_address", "(未提供)"),
        db_connection=deploy_context.get("db_connection", "(未提供)"),
        env_vars_text=env_vars_text,
        user_notes=deploy_context.get("user_notes", "(无)"),
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
        logger.info(f"[AI 确认] LLM 返回 {len(raw_text)} 字符")
    except Exception as e:
        logger.warning(f"[AI 确认] LLM 调用失败，降级: {e}")
        return _merge_context_fallback(initial_config, deploy_context)

    parsed = _parse_llm_response(raw_text)
    if not parsed:
        logger.warning("[AI 确认] JSON 解析失败，降级")
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
    logger.info(f"[AI 确认] ✅ confidence={config['confidence']}")
    return config


def _merge_context_fallback(initial_config: Dict, deploy_context: Dict) -> Dict:
    """LLM 不可用时，手动合并用户上下文到配置"""
    config = dict(initial_config)
    env_vars = dict(config.get("env_vars", {}))

    # 合并数据库连接
    if deploy_context.get("db_connection"):
        env_vars["DATABASE_URL"] = deploy_context["db_connection"]

    # 合并用户自定义环境变量
    if deploy_context.get("env_vars"):
        for line in deploy_context["env_vars"].strip().split("\n"):
            line = line.strip()
            if "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()

    config["env_vars"] = env_vars

    # 合并备注
    notes = [config.get("notes", "")]
    if deploy_context.get("server_address"):
        notes.append(f"目标服务器: {deploy_context['server_address']}")
    if deploy_context.get("user_notes"):
        notes.append(deploy_context["user_notes"])
    config["notes"] = " | ".join(n for n in notes if n)
    config["source"] = "context_merged"
    return config

