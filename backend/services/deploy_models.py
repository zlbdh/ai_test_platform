# -*- coding: utf-8 -*-
"""
Deploy Models — 部署服务数据模型与工具函数

从 deploy_service.py 提取的公共数据结构和实用工具。
"""

import json
import logging
import os
import re
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


# ── 路径常量 ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent          # backend
PROJECT_ROOT = BASE_DIR.parent                              # ai_test_platform
DEPLOY_DIR = PROJECT_ROOT / "data" / "deploy"
DEPLOY_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = DEPLOY_DIR / "deploy_state.json"
HISTORY_FILE = DEPLOY_DIR / "deploy_history.json"
PROJECTS_FILE = DEPLOY_DIR / "projects.json"
JOBS_FILE = DEPLOY_DIR / "deploy_jobs.json"
APPROVALS_FILE = DEPLOY_DIR / "deploy_approvals.json"
MEMORY_DIR = DEPLOY_DIR / "memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)


# ── 数据类 ────────────────────────────────────────────────────────────────────

@dataclass
class RepoConfig:
    """项目内的单个仓库配置（前端/后端/微服务等）"""
    id: str                          # 仓库唯一标识
    label: str                       # 显示名称: "前端" / "后端"
    repo_url: str                    # Git 仓库 URL
    local_dir: str                   # 本地目录名
    tech_stack: str = ""             # 技术栈 (可自动探测)
    install_cmd: str = ""            # 安装命令
    start_cmd: str = ""              # 启动命令
    port: int = 0                    # 端口
    branch: str = "master"           # 分支
    deploy_context: dict = field(default_factory=dict)  # 用户补充的部署上下文


@dataclass
class ProjectConfig:
    """待测项目 (可包含多个仓库)"""
    key: str                         # 项目唯一标识
    name: str                        # 项目显示名称
    repos: List[RepoConfig] = field(default_factory=list)
    git_token: str = ""              # 项目级 Git 令牌


@dataclass
class DeployStep:
    """一键部署的子步骤"""
    name: str = ""                   # clone / install / start
    status: str = "pending"          # pending / running / success / failed
    message: str = ""
    duration_ms: float = 0
    logs: List[str] = field(default_factory=list)


@dataclass
class DeployRecord:
    """部署历史记录"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    project_key: str = ""
    repo_id: str = ""                # 关联仓库 ID
    repo_label: str = ""             # 仓库名称
    action: str = ""
    status: str = "pending"
    message: str = ""
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    finished_at: str = ""
    duration_ms: float = 0
    logs: List[str] = field(default_factory=list)
    steps: List[DeployStep] = field(default_factory=list)


@dataclass
class DeployJob:
    """后台部署作业记录。"""
    id: str = field(default_factory=lambda: f"job_{uuid.uuid4().hex[:12]}")
    action: str = ""
    project_key: str = ""
    repo_id: str = ""
    repo_label: str = ""
    record_id: str = ""
    branch: str = ""
    status: str = "queued"          # queued / running / cancel_requested / cancelled / success / failed / orphaned
    message: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: str = ""
    finished_at: str = ""


@dataclass
class DeployApproval:
    """部署审批单。"""
    id: str = field(default_factory=lambda: f"approval_{uuid.uuid4().hex[:12]}")
    action: str = ""
    project_key: str = ""
    repo_id: str = ""
    repo_label: str = ""
    branch: str = ""
    status: str = "pending"         # pending / approved / rejected
    message: str = ""
    request_comment: str = ""
    requested_by: str = ""
    requested_by_name: str = ""
    requested_at: str = field(default_factory=lambda: datetime.now().isoformat())
    reviewed_by: str = ""
    reviewed_by_name: str = ""
    reviewed_at: str = ""
    review_comment: str = ""
    job_id: str = ""
    record_id: str = ""


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def cmd_available(cmd: str) -> bool:
    """检查系统命令是否可用"""
    return shutil.which(cmd) is not None


def dir_name_from_url(url: str) -> str:
    """从 Git URL 提取目录名"""
    name = url.rstrip("/").split("/")[-1]
    return name[:-4] if name.endswith(".git") else name


def detect_tech_stack(project_dir: Path) -> Dict[str, str]:
    """根据项目文件自动探测技术栈并返回推荐的命令"""
    result = {"tech_stack": "", "install_cmd": "", "start_cmd": "", "port": 0}

    if (project_dir / "package.json").exists():
        try:
            pkg = json.loads((project_dir / "package.json").read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {})
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            stack_parts = []
            if "vue" in deps:
                stack_parts.append(f"Vue {deps.get('vue', '')}")
            elif "react" in deps:
                stack_parts.append(f"React {deps.get('react', '')}")
            elif "next" in deps:
                stack_parts.append(f"Next.js {deps.get('next', '')}")
            if "vite" in deps:
                stack_parts.append(f"Vite {deps.get('vite', '')}")
            elif "webpack" in deps:
                stack_parts.append("Webpack")
            result["tech_stack"] = " + ".join(stack_parts) if stack_parts else "Node.js"
            result["install_cmd"] = "npm install"
            result["start_cmd"] = "npm run dev" if "dev" in scripts else "npm start"
            result["port"] = 3000
        except Exception:
            result["tech_stack"] = "Node.js"
            result["install_cmd"] = "npm install"
            result["start_cmd"] = "npm run dev"

    elif (project_dir / "pom.xml").exists():
        result["tech_stack"] = "Java + Maven"
        try:
            pom_text = (project_dir / "pom.xml").read_text(encoding="utf-8")
            if "spring-cloud" in pom_text:
                result["tech_stack"] = "Java + Spring Cloud"
            elif "spring-boot" in pom_text:
                result["tech_stack"] = "Java + Spring Boot"
            m = re.search(r"<java\.version>(\d+)</java\.version>", pom_text)
            if m:
                result["tech_stack"] = f"Java {m.group(1)} + {result['tech_stack'].split('+ ', 1)[-1]}"
        except Exception:
            pass
        # 优先使用 Maven Wrapper
        if (project_dir / "mvnw.cmd").exists() and os.name == "nt":
            mvn_cmd = ".\\mvnw.cmd"
        elif (project_dir / "mvnw").exists():
            mvn_cmd = "./mvnw"
        else:
            mvn_cmd = "mvn"
        result["install_cmd"] = f"{mvn_cmd} clean install -DskipTests"
        result["start_cmd"] = f"{mvn_cmd} spring-boot:run"
        result["port"] = 8080

    elif (project_dir / "build.gradle").exists() or (project_dir / "build.gradle.kts").exists():
        result["tech_stack"] = "Java + Gradle"
        if (project_dir / "gradlew.bat").exists() and os.name == "nt":
            gradle_cmd = ".\\gradlew.bat"
        elif (project_dir / "gradlew").exists():
            gradle_cmd = "./gradlew"
        else:
            gradle_cmd = "gradle"
        result["install_cmd"] = f"{gradle_cmd} build -x test"
        result["start_cmd"] = f"{gradle_cmd} bootRun"
        result["port"] = 8080

    elif (project_dir / "requirements.txt").exists() or (project_dir / "pyproject.toml").exists():
        result["tech_stack"] = "Python"
        if (project_dir / "manage.py").exists():
            result["tech_stack"] = "Python + Django"
            result["install_cmd"] = "pip install -r requirements.txt"
            result["start_cmd"] = "python manage.py runserver"
            result["port"] = 8000
        else:
            result["install_cmd"] = "pip install -r requirements.txt"
            result["start_cmd"] = "python main.py"
            result["port"] = 8000

    elif (project_dir / "go.mod").exists():
        result["tech_stack"] = "Go"
        result["install_cmd"] = "go mod download"
        result["start_cmd"] = "go run ."
        result["port"] = 8080

    return result
