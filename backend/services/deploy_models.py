# -*- coding: utf-8 -*-
"""
Deployment models: data models and utility functions.

Shared structures and utilities extracted from deploy_service.py.
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


# Path constants
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


# Data classes

@dataclass
class RepoConfig:
    """Configuration for a repository within a project, such as a frontend, backend, or microservice"""
    id: str                          # Unique repository identifier
    label: str                       # Display name, such as Frontend or Backend
    repo_url: str                    # Git repository URL
    local_dir: str                   # Local directory name
    tech_stack: str = ""             # Technology stack, which can be detected automatically
    install_cmd: str = ""            # Installation command
    start_cmd: str = ""              # Startup command
    port: int = 0                    # Port
    branch: str = "master"           # Branch
    deploy_context: dict = field(default_factory=dict)  # Additional deployment context supplied by the user


@dataclass
class ProjectConfig:
    """Project under test, which can contain multiple repositories"""
    key: str                         # Unique project identifier
    name: str                        # Project display name
    repos: List[RepoConfig] = field(default_factory=list)
    git_token: str = ""              # Project-level Git token


@dataclass
class DeployStep:
    """Substep of a one-click deployment"""
    name: str = ""                   # clone / install / start
    status: str = "pending"          # pending / running / success / failed
    message: str = ""
    duration_ms: float = 0
    logs: List[str] = field(default_factory=list)


@dataclass
class DeployRecord:
    """Deployment history record"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    project_key: str = ""
    repo_id: str = ""                # Associated repository ID
    repo_label: str = ""             # Repository name
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
    """Background deployment job record."""
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
    """Deployment approval request."""
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


# Utility functions

def cmd_available(cmd: str) -> bool:
    """Check whether a system command is available"""
    return shutil.which(cmd) is not None


def dir_name_from_url(url: str) -> str:
    """Extract a directory name from a Git URL"""
    name = url.rstrip("/").split("/")[-1]
    return name[:-4] if name.endswith(".git") else name


def detect_tech_stack(project_dir: Path) -> Dict[str, str]:
    """Detect the technology stack from project files and recommend commands"""
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
        # Prefer Maven Wrapper
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
