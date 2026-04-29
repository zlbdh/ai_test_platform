# -*- coding: utf-8 -*-
"""
待测项目自动化部署服务

数据模型: Project → Repos (二级结构)
一个项目可包含多个仓库（前端/后端/微服务等），在同一个项目下统一管理。

注: 数据类和工具函数已移至 deploy_models.py
"""

import logging
import os
import json
import uuid
import re
import subprocess
import signal
import socket
import asyncio
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from services.deploy_models import (
    RepoConfig, ProjectConfig, DeployStep, DeployRecord, DeployJob, DeployApproval,
    cmd_available, dir_name_from_url, detect_tech_stack,
    BASE_DIR, PROJECT_ROOT, DEPLOY_DIR,
    STATE_FILE, HISTORY_FILE, PROJECTS_FILE, JOBS_FILE, APPROVALS_FILE, MEMORY_DIR,
)

logger = logging.getLogger(__name__)


# ── 部署服务 ──────────────────────────────────────────────────────────────────
class DeployService:
    """待测项目部署管理服务"""

    SENSITIVE_ENV_KEYWORDS = ("PASSWORD", "SECRET", "TOKEN", "API_KEY", "ACCESS_KEY")

    def __init__(self):
        self.projects: Dict[str, ProjectConfig] = {}
        self.processes: Dict[str, subprocess.Popen] = {}   # key = repo.id
        self.docker_repos: Dict[str, Dict] = {}              # key = repo.id, val = {cwd, compose_file, cmd}
        self.history: List[DeployRecord] = []
        self.jobs: Dict[str, DeployJob] = {}
        self.approvals: Dict[str, DeployApproval] = {}
        self.memory: Dict[str, Dict] = {}                    # key = repo.id, val = 部署记忆
        self._deploy_event_bus: Dict[str, asyncio.Queue] = {}  # repo_id -> Queue
        self._active_job_tasks: Dict[str, asyncio.Task] = {}
        self._load_projects()
        self._load_history()
        self._load_jobs()
        self._load_approvals()
        self._mark_incomplete_jobs_orphaned()
        self._load_state()
        self._load_all_memory()

    # ── 持久化 ────────────────────────────────────────────────────────────────
    def _ensure_job_runtime(self):
        if not hasattr(self, "jobs") or self.jobs is None:
            self.jobs = {}
        if not hasattr(self, "approvals") or self.approvals is None:
            self.approvals = {}
        if not hasattr(self, "_active_job_tasks") or self._active_job_tasks is None:
            self._active_job_tasks = {}

    def _load_state(self):
        """加载全局状态 (历史兼容)"""
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                # 兼容旧版本: 将全局 token 迁移到第一个项目
                self._legacy_token = data.get("git_token", "")
            except Exception:
                self._legacy_token = ""

    def _save_state(self):
        try:
            STATE_FILE.write_text(
                json.dumps({"git_token": self.git_token}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"保存状态失败: {e}")

    def _load_projects(self):
        if PROJECTS_FILE.exists():
            try:
                raw = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
                for item in raw:
                    repos = [RepoConfig(**r) for r in item.pop("repos", [])]
                    cfg = ProjectConfig(**item, repos=repos)
                    self.projects[cfg.key] = cfg
            except Exception as e:
                logger.warning(f"加载项目列表失败: {e}")
                self.projects = {}

    def _save_projects(self):
        try:
            data = [asdict(p) for p in self.projects.values()]
            PROJECTS_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"保存项目列表失败: {e}")

    def _load_history(self):
        if HISTORY_FILE.exists():
            try:
                raw = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
                self.history = [DeployRecord(**r) for r in raw[-100:]]
            except Exception:
                self.history = []

    def _save_history(self):
        try:
            HISTORY_FILE.write_text(
                json.dumps([asdict(r) for r in self.history[-100:]], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"保存历史失败: {e}")

    def _load_jobs(self):
        self._ensure_job_runtime()
        if JOBS_FILE.exists():
            try:
                raw = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
                self.jobs = {
                    item["id"]: DeployJob(**item)
                    for item in raw[-200:]
                    if isinstance(item, dict) and item.get("id")
                }
            except Exception as exc:
                logger.warning(f"加载部署作业失败: {exc}")
                self.jobs = {}

    def _save_jobs(self):
        self._ensure_job_runtime()
        try:
            JOBS_FILE.write_text(
                json.dumps([asdict(job) for job in list(self.jobs.values())[-200:]], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"保存部署作业失败: {e}")

    def _load_approvals(self):
        self._ensure_job_runtime()
        if APPROVALS_FILE.exists():
            try:
                raw = json.loads(APPROVALS_FILE.read_text(encoding="utf-8"))
                self.approvals = {
                    item["id"]: DeployApproval(**item)
                    for item in raw[-200:]
                    if isinstance(item, dict) and item.get("id")
                }
            except Exception as exc:
                logger.warning(f"加载部署审批失败: {exc}")
                self.approvals = {}

    def _save_approvals(self):
        self._ensure_job_runtime()
        try:
            APPROVALS_FILE.write_text(
                json.dumps([asdict(item) for item in list(self.approvals.values())[-200:]], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"保存部署审批失败: {e}")

    def _mark_incomplete_jobs_orphaned(self):
        self._ensure_job_runtime()
        changed = False
        now = datetime.now().isoformat()
        for job in self.jobs.values():
            if job.status in {"queued", "running"}:
                job.status = "orphaned"
                reason = "服务重启前任务未完成，已标记为 orphaned"
                job.message = f"{job.message} | {reason}" if job.message else reason
                job.finished_at = now
                changed = True
        if changed:
            self._save_jobs()

    def _add_record(self, project_key: str, repo_id: str, repo_label: str, action: str) -> DeployRecord:
        record = DeployRecord(
            project_key=project_key, repo_id=repo_id,
            repo_label=repo_label, action=action, status="running",
        )
        self.history.append(record)
        return record

    def _finish_record(self, record: DeployRecord, status: str, message: str = ""):
        record.status = status
        record.message = message
        record.finished_at = datetime.now().isoformat()
        started = datetime.fromisoformat(record.started_at)
        record.duration_ms = (datetime.now() - started).total_seconds() * 1000
        self._save_history()

    def _create_job(
        self,
        *,
        action: str,
        project_key: str,
        repo_id: str,
        repo_label: str,
        record_id: str,
        branch: str = "",
        message: str = "",
    ) -> DeployJob:
        self._ensure_job_runtime()
        job = DeployJob(
            action=action,
            project_key=project_key,
            repo_id=repo_id,
            repo_label=repo_label,
            record_id=record_id,
            branch=branch,
            message=message,
        )
        self.jobs[job.id] = job
        self._save_jobs()
        return job

    def _update_job(
        self,
        job_id: str,
        *,
        status: str,
        message: str = "",
        started: bool = False,
        finished: bool = False,
    ) -> Optional[DeployJob]:
        self._ensure_job_runtime()
        job = self.jobs.get(job_id)
        if not job:
            return None
        job.status = status
        if message:
            job.message = message
        now = datetime.now().isoformat()
        if started and not job.started_at:
            job.started_at = now
        if finished:
            job.finished_at = now
        self._save_jobs()
        return job

    def get_job_detail(self, job_id: str) -> Optional[Dict]:
        self._ensure_job_runtime()
        job = self.jobs.get(job_id)
        if not job:
            return None
        payload = asdict(job)
        record = next((item for item in reversed(self.history) if item.id == job.record_id), None)
        if record:
            payload["record_status"] = record.status
            payload["record_message"] = record.message
        return payload

    def list_jobs(self, limit: int = 30, status: str = "") -> List[Dict]:
        self._ensure_job_runtime()
        items = list(self.jobs.values())
        if status:
            items = [job for job in items if job.status == status]
        items.sort(key=lambda job: job.created_at, reverse=True)
        return [self.get_job_detail(job.id) for job in items[:max(limit, 0)]]

    def _approval_to_payload(self, approval: DeployApproval) -> Dict:
        payload = asdict(approval)
        if approval.job_id:
            job = self.get_job_detail(approval.job_id)
            if job:
                payload["job"] = job
        if approval.record_id:
            record = self._get_history_record(approval.record_id)
            if record:
                payload["record_status"] = record.status
                payload["record_message"] = record.message
        return payload

    def create_deploy_approval(
        self,
        *,
        action: str,
        project_key: str,
        repo_id: str = "",
        branch: str = "",
        request_comment: str = "",
        requested_by: str,
        requested_by_name: str = "",
    ) -> Dict:
        self._ensure_job_runtime()
        if action == "full_deploy":
            _, repo = self._find_repo(project_key, repo_id)
            repo_label = repo.label
        elif action == "full_deploy_all":
            if project_key not in self.projects:
                raise ValueError(f"项目不存在: {project_key}")
            repo_label = self.projects[project_key].name
            repo_id = ""
        else:
            raise ValueError("不支持的审批动作")

        approval = DeployApproval(
            action=action,
            project_key=project_key,
            repo_id=repo_id,
            repo_label=repo_label,
            branch=branch,
            request_comment=request_comment,
            requested_by=requested_by,
            requested_by_name=requested_by_name or requested_by,
            message="等待审批",
        )
        self.approvals[approval.id] = approval
        self._save_approvals()
        return self._approval_to_payload(approval)

    def get_approval_detail(self, approval_id: str) -> Optional[Dict]:
        self._ensure_job_runtime()
        approval = self.approvals.get(approval_id)
        if not approval:
            return None
        return self._approval_to_payload(approval)

    def list_approvals(self, limit: int = 30, status: str = "") -> List[Dict]:
        self._ensure_job_runtime()
        items = list(self.approvals.values())
        if status:
            items = [item for item in items if item.status == status]
        items.sort(key=lambda item: item.requested_at, reverse=True)
        return [self._approval_to_payload(item) for item in items[:max(limit, 0)]]

    def review_approval(
        self,
        approval_id: str,
        *,
        approved: bool,
        reviewed_by: str,
        reviewed_by_name: str = "",
        comment: str = "",
    ) -> Dict:
        self._ensure_job_runtime()
        approval = self.approvals.get(approval_id)
        if not approval:
            raise ValueError("审批单不存在")
        if approval.status != "pending":
            raise ValueError("审批单已处理")

        approval.reviewed_by = reviewed_by
        approval.reviewed_by_name = reviewed_by_name or reviewed_by
        approval.reviewed_at = datetime.now().isoformat()
        approval.review_comment = comment

        if not approved:
            approval.status = "rejected"
            approval.message = "审批已拒绝"
            self._save_approvals()
            return self._approval_to_payload(approval)

        if approval.action == "full_deploy":
            job = self.schedule_full_deploy(approval.project_key, approval.repo_id, approval.branch)
        elif approval.action == "full_deploy_all":
            job = self.schedule_full_deploy_all(approval.project_key)
        else:
            raise ValueError("不支持的审批动作")

        approval.status = "approved"
        approval.job_id = job.id
        approval.record_id = job.record_id
        approval.message = "审批已通过，部署任务已创建"
        self._save_approvals()
        return self._approval_to_payload(approval)

    def _job_cancellation_requested(self, job_id: str) -> bool:
        self._ensure_job_runtime()
        job = self.jobs.get(job_id)
        return bool(job and job.status == "cancel_requested")

    def _get_history_record(self, record_id: str) -> Optional[DeployRecord]:
        return next((item for item in reversed(self.history) if item.id == record_id), None)

    def _finalize_job_cancellation(self, job_id: str, message: str) -> Optional[Dict]:
        self._ensure_job_runtime()
        job = self.jobs.get(job_id)
        if not job:
            return None

        record = self._get_history_record(job.record_id)
        if record and record.status == "running":
            running_steps = False
            for step in record.steps:
                if step.status == "running":
                    step.status = "cancelled"
                    step.message = message
                    running_steps = True
                elif step.status == "pending":
                    step.status = "skipped"
                    step.message = "任务已取消，未执行"
            if not running_steps and not record.steps:
                record.logs.append(f"⛔ {message}")
            else:
                record.logs.append(f"⛔ {message}")
            self._finish_record(record, "cancelled", message)

        self._update_job(job_id, status="cancelled", message=message, started=True, finished=True)
        return self.get_job_detail(job_id)

    def cancel_job(self, job_id: str) -> Dict:
        self._ensure_job_runtime()
        job = self.jobs.get(job_id)
        if not job:
            raise ValueError("作业不存在")
        if job.status in {"success", "failed", "cancelled", "orphaned"}:
            raise ValueError("作业已结束，无法取消")
        if job.status == "cancel_requested":
            payload = self.get_job_detail(job_id)
            if payload is None:
                raise ValueError("作业不存在")
            return payload

        job.status = "cancel_requested"
        job.message = "已收到取消请求"
        self._save_jobs()

        record = self._get_history_record(job.record_id)
        if record and record.status == "running":
            record.logs.append("⛔ 已收到取消请求，将在当前步骤结束后停止后续执行")
            self._save_history()

        task = self._active_job_tasks.get(job_id)
        if task is None or task.done():
            payload = self._finalize_job_cancellation(job_id, "任务已取消")
            if payload is None:
                raise ValueError("作业不存在")
            return payload

        payload = self.get_job_detail(job_id)
        if payload is None:
            raise ValueError("作业不存在")
        return payload

    def schedule_full_deploy(self, project_key: str, repo_id: str, branch: str = "") -> DeployJob:
        """调度一键部署后台作业并立即返回作业信息。"""
        self._ensure_job_runtime()
        _, repo = self._find_repo(project_key, repo_id)

        record = self._add_record(project_key, repo_id, repo.label, "full_deploy")
        record.logs.append(f"🔄 一键部署 [{repo.label}]...")
        record.steps = [DeployStep(name="clone"), DeployStep(name="install"), DeployStep(name="start")]
        self._save_history()

        job = self._create_job(
            action="full_deploy",
            project_key=project_key,
            repo_id=repo_id,
            repo_label=repo.label,
            record_id=record.id,
            branch=branch,
            message="后台部署任务已创建",
        )

        async def _runner():
            if self._job_cancellation_requested(job.id):
                self._finalize_job_cancellation(job.id, "任务在启动前已取消")
                return
            self._update_job(job.id, status="running", message="后台部署执行中", started=True)
            try:
                final_record = await self.full_deploy_repo(project_key, repo_id, branch, record, job_id=job.id)
            except Exception as exc:
                logger.exception("[DeployService] 后台部署任务执行失败: %s", exc)
                self._update_job(job.id, status="failed", message=str(exc), started=True, finished=True)
                return

            if final_record.status == "cancelled":
                self._update_job(job.id, status="cancelled", message=final_record.message or "任务已取消", started=True, finished=True)
                return
            final_status = "success" if final_record.status == "success" else "failed"
            final_message = final_record.message or ("一键部署完成 ✅" if final_status == "success" else "部署失败")
            self._update_job(job.id, status=final_status, message=final_message, started=True, finished=True)

        task = asyncio.create_task(_runner(), name=f"deploy-job-{job.id}")
        self._active_job_tasks[job.id] = task

        def _cleanup(_task: asyncio.Task):
            self._active_job_tasks.pop(job.id, None)

        task.add_done_callback(_cleanup)
        return job

    def schedule_full_deploy_all(self, project_key: str) -> DeployJob:
        """调度项目级一键部署后台作业并立即返回作业信息。"""
        self._ensure_job_runtime()
        if project_key not in self.projects:
            raise ValueError(f"项目不存在: {project_key}")

        project = self.projects[project_key]
        record = self._add_record(project_key, "", project.name, "full_deploy_all")
        record.logs.append(f"🔄 一键部署全部 ({len(project.repos)} 个仓库)...")
        self._save_history()

        job = self._create_job(
            action="full_deploy_all",
            project_key=project_key,
            repo_id="",
            repo_label=project.name,
            record_id=record.id,
            message="后台项目级部署任务已创建",
        )

        async def _runner():
            if self._job_cancellation_requested(job.id):
                self._finalize_job_cancellation(job.id, "任务在启动前已取消")
                return
            self._update_job(job.id, status="running", message="项目级后台部署执行中", started=True)
            try:
                final_record = await self.full_deploy_all(project_key, existing_record=record, job_id=job.id)
            except Exception as exc:
                logger.exception("[DeployService] 项目级后台部署任务执行失败: %s", exc)
                self._update_job(job.id, status="failed", message=str(exc), started=True, finished=True)
                return

            if final_record.status == "cancelled":
                self._update_job(job.id, status="cancelled", message=final_record.message or "任务已取消", started=True, finished=True)
                return
            final_status = "success" if final_record.status == "success" else "failed"
            final_message = final_record.message or (
                f"全部 {len(project.repos)} 个仓库部署完成 ✅"
                if final_status == "success"
                else "项目级部署失败"
            )
            self._update_job(job.id, status=final_status, message=final_message, started=True, finished=True)

        task = asyncio.create_task(_runner(), name=f"deploy-job-{job.id}")
        self._active_job_tasks[job.id] = task

        def _cleanup(_task: asyncio.Task):
            self._active_job_tasks.pop(job.id, None)

        task.add_done_callback(_cleanup)
        return job

    # ── 部署记忆系统 ────────────────────────────────────────────────────────────
    def _memory_file(self, repo_id: str) -> Path:
        return MEMORY_DIR / f"{repo_id}.json"

    def _load_all_memory(self):
        """启动时加载所有 repo 的部署记忆"""
        for f in MEMORY_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                self.memory[f.stem] = data
            except Exception:
                pass
        if self.memory:
            logger.info(f"[Memory] 已加载 {len(self.memory)} 个仓库的部署记忆")

    def _load_memory(self, repo_id: str) -> Dict:
        """加载指定 repo 的记忆"""
        if repo_id in self.memory:
            return self.memory[repo_id]
        mf = self._memory_file(repo_id)
        if mf.exists():
            try:
                data = json.loads(mf.read_text(encoding="utf-8"))
                self.memory[repo_id] = data
                return data
            except Exception:
                pass
        return {}

    def _save_memory(self, repo_id: str, data: Dict):
        """保存 repo 的部署记忆到磁盘"""
        self.memory[repo_id] = data
        try:
            self._memory_file(repo_id).write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"[Memory] 保存记忆失败 ({repo_id}): {e}")

    def _update_memory(self, repo_id: str, key: str, value, record: DeployRecord = None):
        """更新 repo 记忆的某个字段"""
        mem = self._load_memory(repo_id)
        mem[key] = value
        mem["last_updated"] = datetime.now().isoformat()
        # 构建成功或启动成功都算一次有效部署
        should_inc = (
            key == "last_success"
            or (key == "build_strategy" and isinstance(value, dict) and value.get("success"))
        )
        mem["deploy_count"] = mem.get("deploy_count", 0) + (1 if should_inc else 0)
        self._save_memory(repo_id, mem)
        if record:
            record.logs.append(f"🧠 记忆已更新: {key}")

    @staticmethod
    def _parse_env_text(env_text: str) -> Dict[str, str]:
        """解析 KEY=VALUE 文本为环境变量字典。"""
        env_vars: Dict[str, str] = {}
        if not env_text:
            return env_vars
        for raw_line in env_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env_vars[key.strip()] = value.strip().strip("'\"")
        return env_vars

    @staticmethod
    def _dump_env_text(env_vars: Dict[str, str]) -> str:
        """将环境变量字典转回 KEY=VALUE 文本。"""
        if not env_vars:
            return ""
        return "\n".join(f"{key}={value}" for key, value in env_vars.items())

    @classmethod
    def _mask_env_vars(cls, env_vars: Dict[str, str]) -> Dict[str, str]:
        """脱敏环境变量，避免在 UI/记忆中重复暴露敏感信息。"""
        masked: Dict[str, str] = {}
        for key, value in env_vars.items():
            upper_key = key.upper()
            if any(token in upper_key for token in cls.SENSITIVE_ENV_KEYWORDS):
                if not value:
                    masked[key] = value
                elif len(value) <= 6:
                    masked[key] = "*" * len(value)
                else:
                    masked[key] = f"{value[:2]}***{value[-2:]}"
            else:
                masked[key] = value
        return masked

    @staticmethod
    def _summarize_env_vars(env_vars: Dict[str, str]) -> str:
        """提炼关键环境变量摘要供记忆/提示使用。"""
        if not env_vars:
            return ""
        keys = [
            "SPRING_PROFILES_ACTIVE",
            "NACOS_SERVER_ADDR",
            "NACOS_NAMESPACE",
            "NACOS_GROUP",
            "SEATA_SERVER_ADDR",
        ]
        parts = [f"{key}={env_vars[key]}" for key in keys if env_vars.get(key)]
        if not parts:
            parts = [f"{key}={value}" for key, value in list(env_vars.items())[:4]]
        return " | ".join(parts)

    def _get_env_file_path(self, project_dir: Path, create: bool = False) -> Path:
        """定位仓库实际使用的环境变量文件，优先 docker/.env。"""
        docker_env = project_dir / "docker" / ".env"
        root_env = project_dir / ".env"
        if docker_env.exists():
            return docker_env
        if root_env.exists():
            return root_env
        if create and (project_dir / "docker").exists():
            return docker_env
        return docker_env if create else root_env

    @staticmethod
    def _env_source_label(project_dir: Path, env_file: Path) -> str:
        """将环境文件路径转换成对前端友好的来源标签。"""
        try:
            return str(env_file.relative_to(project_dir)).replace("\\", "/")
        except ValueError:
            return env_file.name

    def _read_env_file(self, env_file: Path) -> Dict[str, str]:
        """读取指定环境文件。"""
        if not env_file.exists():
            return {}
        return self._parse_env_text(env_file.read_text(encoding="utf-8"))

    def _merge_env_file(self, project_dir: Path, overrides: Dict[str, str], record: Optional[DeployRecord] = None) -> Dict[str, str]:
        """将环境变量增量合并到生效的 .env 文件，保留未改项。"""
        env_file = self._get_env_file_path(project_dir, create=True)
        env_file.parent.mkdir(parents=True, exist_ok=True)
        merged = self._read_env_file(env_file)
        merged.update(overrides)
        with open(env_file, "w", encoding="utf-8") as handle:
            for key, value in merged.items():
                handle.write(f"{key}={value}\n")
        if record and overrides:
            changed = ", ".join(overrides.keys())
            record.logs.append(f"📝 已增量更新环境配置 ({self._env_source_label(project_dir, env_file)}): {changed}")
        return merged

    def _get_repo_env_state(self, repo: RepoConfig) -> Dict[str, object]:
        """汇总仓库当前生效环境、已保存覆盖项和前端可展示说明。"""
        target = self._repo_path(repo)
        saved_context = {
            "server_address": "",
            "db_connection": "",
            "env_vars": "",
            "user_notes": "",
            **(repo.deploy_context or {}),
        }
        saved_env_vars = self._parse_env_text(saved_context.get("env_vars", ""))

        effective_env_vars: Dict[str, str] = {}
        effective_env_source = ""
        if target.exists():
            env_file = self._get_env_file_path(target)
            effective_env_vars = self._read_env_file(env_file)
            if env_file.exists():
                effective_env_source = self._env_source_label(target, env_file)

        if not effective_env_vars and saved_env_vars:
            effective_env_vars = dict(saved_env_vars)
            effective_env_source = "已保存的部署覆盖项"

        masked_effective = self._mask_env_vars(effective_env_vars)
        masked_saved = self._mask_env_vars(saved_env_vars)
        return {
            "saved_context": saved_context,
            "saved_env_vars": masked_saved,
            "saved_env_text": self._dump_env_text(saved_env_vars),
            "effective_env_vars": masked_effective,
            "effective_env_text": self._dump_env_text(effective_env_vars),
            "effective_env_source": effective_env_source,
            "env_apply_behavior": "不填写补充信息时沿用当前生效值；补充信息中的 KEY=VALUE 会增量合并到现有 .env，并在后续部署继续生效。",
        }

    def _remember_effective_env(self, repo: RepoConfig, project_dir: Path, record: Optional[DeployRecord] = None):
        """在部署成功后记录当前生效环境摘要，供下次 AI 分析参考。"""
        env_file = self._get_env_file_path(project_dir)
        env_vars = self._read_env_file(env_file)
        if not env_vars:
            return
        self._update_memory(repo.id, "effective_env", {
            "source": self._env_source_label(project_dir, env_file),
            "vars": self._mask_env_vars(env_vars),
            "summary": self._summarize_env_vars(env_vars),
            "keys": list(env_vars.keys()),
            "timestamp": datetime.now().isoformat(),
        }, record)

    def _prefer_stable_ai_start_command(self, repo: RepoConfig, result: Dict, mem: Dict) -> Dict:
        """对 AI 建议做稳定性保护，优先沿用已验证成功的启动命令。"""
        suggested_start = str(result.get("start_cmd") or "").strip()
        current_start = str(repo.start_cmd or "").strip()
        docker_cmd = str(mem.get("start_config", {}).get("docker_cmd") or "").strip()
        stable_start = docker_cmd or current_start

        if not stable_start:
            return result

        target = self._repo_path(repo)
        has_compose = any((target / "docker" / name).exists() or (target / name).exists() for name in ("docker-compose-dev.yml", "docker-compose.yml"))
        if not has_compose:
            return result

        stable_is_docker = "docker" in stable_start.lower()
        suggested_is_docker = "docker" in suggested_start.lower()
        if not stable_is_docker or suggested_is_docker:
            return result

        result["start_cmd"] = stable_start
        suffix = "已沿用当前验证通过的 Docker 启动命令，避免 AI 建议覆盖稳定部署链路。"
        result["notes"] = f"{result.get('notes', '').strip()} {suffix}".strip()
        result["stability_guard_applied"] = True
        logger.info(f"[AI] 启用稳定命令保护: {repo.label} -> {stable_start}")
        return result

    def _auto_start_docker(self, record: DeployRecord) -> bool:
        """自动启动 Docker Desktop 并等待 daemon 就绪（最多等 60 秒）"""
        import time as _time

        # 查找 Docker Desktop 可执行文件
        docker_desktop_path = None
        if os.name == "nt":
            # Windows: 常见安装路径
            candidates = [
                Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Docker" / "Docker" / "Docker Desktop.exe",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Docker" / "Docker Desktop.exe",
            ]
            for c in candidates:
                if c.exists():
                    docker_desktop_path = str(c)
                    break
            # 如果找不到固定路径，尝试 where 命令
            if not docker_desktop_path:
                try:
                    r = subprocess.run(["where", "Docker Desktop"], capture_output=True, text=True, timeout=5)
                    if r.returncode == 0 and r.stdout.strip():
                        docker_desktop_path = r.stdout.strip().split("\n")[0].strip()
                except Exception:
                    pass
        else:
            # macOS / Linux
            mac_path = Path("/Applications/Docker.app/Contents/MacOS/Docker")
            if mac_path.exists():
                docker_desktop_path = str(mac_path)
            else:
                try:
                    r = subprocess.run(["which", "docker"], capture_output=True, text=True, timeout=5)
                    if r.returncode == 0:
                        docker_desktop_path = "open -a Docker"
                except Exception:
                    pass

        if not docker_desktop_path:
            record.logs.append("⚠️ 找不到 Docker Desktop 安装路径，无法自动启动")
            return False

        # 启动 Docker Desktop
        try:
            record.logs.append(f"🐳 正在启动 Docker Desktop...")
            if os.name == "nt":
                subprocess.Popen(
                    [docker_desktop_path],
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    docker_desktop_path, shell=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
        except Exception as e:
            record.logs.append(f"⚠️ 启动 Docker Desktop 失败: {e}")
            return False

        # 等待 Docker daemon 就绪（最多 60 秒）
        max_wait = 60
        interval = 3
        waited = 0
        record.logs.append(f"⏳ 等待 Docker daemon 就绪 (最多 {max_wait}s)...")
        while waited < max_wait:
            _time.sleep(interval)
            waited += interval
            try:
                r = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=10)
                if r.returncode == 0:
                    record.logs.append(f"✅ Docker Desktop 已就绪 (等待了 {waited}s)")
                    return True
            except Exception:
                pass
            if waited % 15 == 0:
                record.logs.append(f"⏳ 仍在等待 Docker 启动... ({waited}s/{max_wait}s)")

        record.logs.append(f"⚠️ Docker Desktop 启动超时 ({max_wait}s)，请手动检查")
        return False

    def _kill_project_java_processes(self, project_dir: Path, record: DeployRecord):
        """构建前清理该项目残留的 Java 进程（防止 jar 被占用）"""
        killed = 0
        # 使用项目目录名来匹配 — 比全路径更可靠
        dir_name = project_dir.name.lower()
        jar_markers = {
            dir_name,
            *(jar.stem.lower() for jar in self._list_local_microservice_jars(project_dir)),
            *(jar.name.lower() for jar in self._list_local_microservice_jars(project_dir)),
        }

        # 1) 先杀 docker_repos 中记录的微服务 PID
        for repo_id, info in list(self.docker_repos.items()):
            cwd = info.get("cwd", "").lower()
            if dir_name in cwd:
                for svc in info.get("service_pids", []):
                    pid = svc.get("pid")
                    if pid:
                        try:
                            if os.name == "nt":
                                subprocess.run(
                                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                                    capture_output=True, timeout=5
                                )
                            else:
                                os.kill(pid, signal.SIGTERM)
                            killed += 1
                        except Exception:
                            pass
                self.docker_repos.pop(repo_id, None)

        # 2) 通过 PowerShell/ps 查找命令行含项目目录名的 java 进程
        try:
            if os.name == "nt":
                # PowerShell Get-CimInstance 比 WMIC 更可靠
                ps_cmd = (
                    "Get-CimInstance Win32_Process -Filter \"Name='java.exe'\" "
                    "| Select-Object ProcessId, CommandLine "
                    "| ForEach-Object { $_.ProcessId.ToString() + '|' + $_.CommandLine }"
                )
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    capture_output=True, text=True, timeout=15
                )
                for line in result.stdout.strip().split("\n"):
                    line = line.strip()
                    if not line or "|" not in line:
                        continue
                    lower_line = line.lower()
                    if any(marker and marker in lower_line for marker in jar_markers):
                        pid_str = line.split("|", 1)[0].strip()
                        if pid_str.isdigit():
                            subprocess.run(
                                ["taskkill", "/F", "/T", "/PID", pid_str],
                                capture_output=True, timeout=5
                            )
                            killed += 1
                            logger.info(f"[进程清理] 杀掉 Java PID {pid_str}")
            else:
                result = subprocess.run(
                    ["ps", "aux"], capture_output=True, text=True, timeout=10
                )
                for line in result.stdout.split("\n"):
                    lower_line = line.lower()
                    if "java" in lower_line and any(marker and marker in lower_line for marker in jar_markers):
                        parts = line.split()
                        if len(parts) > 1 and parts[1].isdigit():
                            os.kill(int(parts[1]), signal.SIGTERM)
                            killed += 1
        except Exception as e:
            logger.debug(f"[进程清理] 扫描异常: {e}")

        if killed:
            record.logs.append(f"🧹 构建前清理: 已终止 {killed} 个残留 Java 进程")
            logger.info(f"[进程清理] 项目 {project_dir.name}: 终止 {killed} 个 Java 进程")
            time.sleep(2)  # 等待文件句柄释放
        else:
            record.logs.append("🔍 构建前检查: 无残留 Java 进程")

    @staticmethod
    def _is_frontend_repo(repo: RepoConfig) -> bool:
        label = repo.label or ""
        tech_stack = (repo.tech_stack or "").lower()
        return label == "前端" or any(keyword in tech_stack for keyword in ("vite", "vue", "react", "next"))

    def _kill_project_frontend_processes(self, project_dir: Path, record: DeployRecord) -> int:
        """启动/停止前清理同仓库残留的 Vite/Node 前端进程，避免旧实例占住端口。"""
        killed = 0
        project_marker = str(project_dir).lower()
        dev_markers = ("vite", "npm run dev", "pnpm dev", "yarn dev")

        try:
            if os.name == "nt":
                ps_cmd = (
                    "$marker = @'\n"
                    f"{project_marker}\n"
                    "'@.Trim().ToLower();"
                    "$markers = @('vite','npm run dev','pnpm dev','yarn dev');"
                    "Get-CimInstance Win32_Process "
                    "| Where-Object { $_.CommandLine -and $_.CommandLine.ToLower().Contains($marker) } "
                    "| Where-Object { $cmd = $_.CommandLine.ToLower(); $markers | Where-Object { $cmd.Contains($_) } } "
                    "| Select-Object -ExpandProperty ProcessId"
                )
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                pid_candidates = {
                    int(line.strip())
                    for line in result.stdout.splitlines()
                    if line.strip().isdigit()
                }
                for pid in sorted(pid_candidates):
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True,
                        timeout=5,
                    )
                    killed += 1
            else:
                result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=10)
                for line in result.stdout.splitlines():
                    lower_line = line.lower()
                    if project_marker in lower_line and any(marker in lower_line for marker in dev_markers):
                        parts = line.split()
                        if len(parts) > 1 and parts[1].isdigit():
                            os.kill(int(parts[1]), signal.SIGTERM)
                            killed += 1
        except Exception as e:
            logger.debug(f"[前端进程清理] 扫描异常: {e}")

        if killed:
            record.logs.append(f"🧹 前端运行前清理: 已终止 {killed} 个残留 Node/Vite 进程")
            time.sleep(1)
        else:
            record.logs.append("🔍 前端运行前检查: 无残留 Node/Vite 进程")
        return killed

    # ── 事件流 ─────────────────────────────────────────────────────────────────
    def _emit_event(self, repo_id: str, event: dict):
        """向事件总线推送一条部署事件"""
        q = self._deploy_event_bus.get(repo_id)
        if q:
            try: q.put_nowait(event)
            except asyncio.QueueFull: pass

    async def get_event_stream(self, repo_id: str):
        """SSE 消费端：yield 事件直到部署完成"""
        # 使用已预注册的队列，若无则创建新队列
        q = self._deploy_event_bus.get(repo_id)
        if q is None:
            q = asyncio.Queue(maxsize=500)
            self._deploy_event_bus[repo_id] = q
        try:
            while True:
                event = await asyncio.wait_for(q.get(), timeout=300)
                yield event
                if event.get("type") == "deploy_done":
                    break
        except asyncio.TimeoutError:
            yield {"type": "deploy_done", "status": "timeout", "message": "事件流超时"}
        finally:
            self._deploy_event_bus.pop(repo_id, None)

    def _repo_path(self, repo: RepoConfig) -> Path:
        return DEPLOY_DIR / repo.local_dir

    def _find_repo(self, project_key: str, repo_id: str) -> tuple:
        """查找项目和仓库, 返回 (ProjectConfig, RepoConfig)"""
        if project_key not in self.projects:
            raise ValueError(f"项目不存在: {project_key}")
        proj = self.projects[project_key]
        repo = next((r for r in proj.repos if r.id == repo_id), None)
        if not repo:
            raise ValueError(f"仓库不存在: {repo_id}")
        return proj, repo

    # ── Git Token ─────────────────────────────────────────────────────────────
    def set_project_token(self, project_key: str, token: str):
        """设置项目级 Git 令牌"""
        if project_key not in self.projects:
            raise ValueError(f"项目不存在: {project_key}")
        self.projects[project_key].git_token = token
        self._save_projects()

    def _auth_url(self, url: str, token: str = "") -> str:
        if token and "://" in url:
            parts = url.split("://", 1)
            return f"{parts[0]}://oauth2:{token}@{parts[1]}"
        return url

    # ── 项目 CRUD ─────────────────────────────────────────────────────────────
    def add_project(self, name: str, repos: List[dict]) -> ProjectConfig:
        """添加新项目 (含多个仓库)"""
        key = str(uuid.uuid4())[:8]
        existing_dirs = set()
        for p in self.projects.values():
            for r in p.repos:
                existing_dirs.add(r.local_dir)

        repo_configs = []
        for rd in repos:
            repo_id = str(uuid.uuid4())[:8]
            local_dir = dir_name_from_url(rd["repo_url"])
            base_dir = local_dir
            counter = 1
            while local_dir in existing_dirs:
                local_dir = f"{base_dir}_{counter}"
                counter += 1
            existing_dirs.add(local_dir)

            repo_configs.append(RepoConfig(
                id=repo_id,
                label=rd.get("label", "默认"),
                repo_url=rd["repo_url"],
                local_dir=local_dir,
                tech_stack=rd.get("tech_stack", ""),
                install_cmd=rd.get("install_cmd", ""),
                start_cmd=rd.get("start_cmd", ""),
                port=rd.get("port", 0),
                branch=rd.get("branch", "master"),
                deploy_context=rd.get("deploy_context", {}),
            ))

        # 从参数或旧版全局 token 获取令牌
        token = ""
        if repos and repos[0].get("git_token"):
            token = repos[0].get("git_token", "")
        elif hasattr(self, '_legacy_token') and self._legacy_token:
            token = self._legacy_token
            self._legacy_token = ""  # 迁移后清除

        cfg = ProjectConfig(key=key, name=name, repos=repo_configs, git_token=token)
        self.projects[key] = cfg
        self._save_projects()
        logger.info(f"新增项目: {name} ({len(repo_configs)} 个仓库)")
        return cfg

    def update_project(self, key: str, name: str = None, repos: List[dict] = None) -> ProjectConfig:
        """更新项目 (可更新名称和仓库列表)"""
        if key not in self.projects:
            raise ValueError(f"项目不存在: {key}")
        cfg = self.projects[key]
        if name:
            cfg.name = name
        if repos is not None:
            existing_dirs = set()
            for p in self.projects.values():
                if p.key != key:
                    for r in p.repos:
                        existing_dirs.add(r.local_dir)

            new_repos = []
            for rd in repos:
                repo_id = rd.get("id", str(uuid.uuid4())[:8])
                local_dir = rd.get("local_dir") or dir_name_from_url(rd["repo_url"])
                base_dir = local_dir
                counter = 1
                while local_dir in existing_dirs:
                    local_dir = f"{base_dir}_{counter}"
                    counter += 1
                existing_dirs.add(local_dir)

                new_repos.append(RepoConfig(
                    id=repo_id,
                    label=rd.get("label", "默认"),
                    repo_url=rd["repo_url"],
                    local_dir=local_dir,
                    tech_stack=rd.get("tech_stack", ""),
                    install_cmd=rd.get("install_cmd", ""),
                    start_cmd=rd.get("start_cmd", ""),
                    port=rd.get("port", 0),
                    branch=rd.get("branch", "master"),
                    deploy_context=rd.get("deploy_context", {}),
                ))
            cfg.repos = new_repos
        self._save_projects()
        return cfg

    def delete_project(self, key: str) -> bool:
        if key not in self.projects:
            raise ValueError(f"项目不存在: {key}")
        for repo in self.projects[key].repos:
            if repo.id in self.processes and self.processes[repo.id].poll() is None:
                try:
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.processes[repo.id].pid)], capture_output=True)
                    else:
                        os.killpg(os.getpgid(self.processes[repo.id].pid), signal.SIGTERM)
                except Exception:
                    pass
                self.processes.pop(repo.id, None)
        del self.projects[key]
        self._save_projects()
        return True

    # ── 部署操作 (以 repo 为单位) ─────────────────────────────────────────────
    async def clone_repo(self, project_key: str, repo_id: str, branch: str = "") -> DeployRecord:
        proj, repo = self._find_repo(project_key, repo_id)
        record = self._add_record(project_key, repo_id, repo.label, "clone")
        target = self._repo_path(repo)
        use_branch = branch or repo.branch

        try:
            if target.exists() and (target / ".git").exists():
                record.logs.append(f"📂 已存在，执行 git pull ({use_branch})")
                # 使用同步 subprocess.run 避免 Windows asyncio 兼容问题
                r1 = subprocess.run(
                    ["git", "checkout", use_branch], cwd=str(target),
                    capture_output=True, text=True, timeout=30,
                )
                if r1.stdout.strip():
                    record.logs.append(r1.stdout.strip())
                if r1.stderr.strip():
                    record.logs.append(r1.stderr.strip())

                # 自动 stash 本地修改（如 AI 修改的 pom.xml），防止 pull 冲突
                stash_result = subprocess.run(
                    ["git", "stash", "--include-untracked"], cwd=str(target),
                    capture_output=True, text=True, timeout=30,
                )
                has_stash = "No local changes" not in (stash_result.stdout or "")
                if has_stash:
                    record.logs.append(f"📦 已暂存本地修改 (git stash)")

                r2 = subprocess.run(
                    ["git", "pull", "origin", use_branch], cwd=str(target),
                    capture_output=True, text=True, timeout=120,
                )
                if r2.stdout.strip():
                    record.logs.append(r2.stdout.strip())
                if r2.stderr.strip():
                    record.logs.append(r2.stderr.strip())

                if r2.returncode != 0:
                    # pull 失败，恢复 stash
                    if has_stash:
                        subprocess.run(["git", "stash", "pop"], cwd=str(target),
                                       capture_output=True, text=True, timeout=30)
                    self._finish_record(record, "failed", f"拉取失败 (exit={r2.returncode})")
                    return record

                # pull 成功后，尝试恢复本地修改
                if has_stash:
                    pop_result = subprocess.run(
                        ["git", "stash", "pop"], cwd=str(target),
                        capture_output=True, text=True, timeout=30,
                    )
                    if pop_result.returncode == 0:
                        record.logs.append("📦 已恢复本地修改")
                    else:
                        record.logs.append("⚠️ 恢复本地修改时有冲突，已丢弃旧修改")
                        subprocess.run(["git", "stash", "drop"], cwd=str(target),
                                       capture_output=True, text=True, timeout=30)
                        subprocess.run(["git", "checkout", "."], cwd=str(target),
                                       capture_output=True, text=True, timeout=30)

                self._finish_record(record, "success", f"已拉取 ({use_branch})")
            else:
                auth_url = self._auth_url(repo.repo_url, proj.git_token)
                record.logs.append(f"🔄 克隆 {repo.repo_url}")
                # 使用同步 subprocess.run 避免 Windows asyncio 兼容问题
                r = subprocess.run(
                    ["git", "clone", "-b", use_branch, auth_url, str(target)],
                    capture_output=True, text=True, timeout=300,
                    encoding="utf-8", errors="replace",
                )
                if r.stdout.strip():
                    record.logs.append(r.stdout.strip())
                if r.stderr.strip():
                    record.logs.append(r.stderr.strip())

                if r.returncode == 0:
                    if not repo.tech_stack or not repo.install_cmd:
                        detected = detect_tech_stack(target)
                        if detected["tech_stack"] and not repo.tech_stack:
                            repo.tech_stack = detected["tech_stack"]
                        if detected["install_cmd"] and not repo.install_cmd:
                            repo.install_cmd = detected["install_cmd"]
                        if detected["start_cmd"] and not repo.start_cmd:
                            repo.start_cmd = detected["start_cmd"]
                        if detected["port"] and not repo.port:
                            repo.port = detected["port"]
                        self._save_projects()
                        record.logs.append(f"🔍 探测: {repo.tech_stack}")
                    self._finish_record(record, "success", "克隆完成")
                else:
                    self._finish_record(record, "failed", f"克隆失败 (exit={r.returncode})")
        except subprocess.TimeoutExpired:
            self._finish_record(record, "failed", "克隆超时 (>300s)")
        except Exception as e:
            self._finish_record(record, "failed", str(e))
        return record

    # ── 自愈辅助 ────────────────────────────────────────────────────────────
    @staticmethod
    def _find_free_port(preferred: int, range_size: int = 100) -> int:
        """从 preferred 开始扫描可用端口"""
        for port in range(preferred, preferred + range_size):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("0.0.0.0", port))
                    return port
            except OSError:
                continue
        return 0  # 未找到

    @staticmethod
    def _is_privileged_port(port: int) -> bool:
        return isinstance(port, int) and 0 < port < 1024

    def _normalize_frontend_port(
        self,
        repo: RepoConfig,
        requested_port: int,
        record: Optional[DeployRecord] = None,
        *,
        allow_port_scan: bool = False,
    ) -> int:
        """前端低位端口会在本地环境下触发 EACCES，统一改写到安全端口。"""
        if not self._is_frontend_repo(repo):
            return requested_port

        port = int(requested_port or 0)
        if port and not self._is_privileged_port(port):
            return port

        safe_port = 81
        if allow_port_scan:
            safe_port = self._find_free_port(81) or 81

        if record is not None:
            record.logs.append(
                f"🔧 自愈: 前端低位端口 {port or '未配置'} 不适合当前本地环境，已改写到 {safe_port}"
            )
        return safe_port

    def _get_deploy_env(self, repo: 'RepoConfig') -> dict:
        """构建部署环境变量：OS 环境 + 用户补充的 deploy_context.env_vars"""
        env = dict(os.environ)
        ctx = repo.deploy_context or {}
        # 解析用户补充的 KEY=VALUE 环境变量
        env.update(self._parse_env_text(ctx.get("env_vars", "")))
        # 数据库连接
        if ctx.get("db_connection"):
            env["DATABASE_URL"] = ctx["db_connection"]
        return env

    def _write_env_file(self, target: Path, repo: 'RepoConfig', record: DeployRecord):
        """将 deploy_context 增量合并到项目的环境文件，保留当前未修改项。"""
        ctx = repo.deploy_context or {}
        overrides = self._parse_env_text(ctx.get("env_vars", ""))
        if ctx.get("server_address"):
            overrides["DEPLOY_SERVER"] = ctx["server_address"]
        if ctx.get("db_connection"):
            overrides["DATABASE_URL"] = ctx["db_connection"]
        if not overrides:
            return
        try:
            self._merge_env_file(target, overrides, record)
        except Exception as e:
            env_file = self._get_env_file_path(target, create=True)
            record.logs.append(f"⚠️ 写入 {self._env_source_label(target, env_file)} 失败: {e}")

    def _apply_pom_changes(self, target: Path, suggested_changes: list, record: DeployRecord):
        """用户确认后，自动应用 pom.xml Maven Profile 修改（不修改不相关的代码）"""
        import re as _re
        for change in suggested_changes:
            if change.get("type") != "maven_profile":
                continue
            pom_file = target / change["file"]
            if not pom_file.exists():
                record.logs.append(f"⚠️ 文件不存在: {change['file']}")
                continue
            try:
                content = pom_file.read_text(encoding="utf-8")
                mod = change["module"]
                profile_id = change.get("profile_id", "aigc")

                # 检查是否已经有该 profile
                if f'<id>{profile_id}</id>' in content:
                    record.logs.append(f"ℹ️ {change['file']} 已有 {profile_id} profile，跳过")
                    continue

                # 将 <module>mod</module> 替换为注释
                pattern = f'(\\s*)<module>{_re.escape(mod)}</module>'
                match = _re.search(pattern, content)
                if not match:
                    record.logs.append(f"ℹ️ {change['file']} 中未找到 {mod}，跳过")
                    continue

                indent = match.group(1)
                # 替换为注释
                content = _re.sub(
                    pattern,
                    f'{indent}<!-- {mod} 移至 profile 中，默认不打包 -->',
                    content,
                )

                # 在 </modules> 后插入 <profiles> 节
                profiles_block = f"""\n
    <profiles>
        <profile>
            <id>{profile_id}</id>
            <modules>
                <module>{mod}</module>
            </modules>
        </profile>
    </profiles>"""
                content = content.replace('</modules>', '</modules>' + profiles_block, 1)

                pom_file.write_text(content, encoding="utf-8")
                record.logs.append(f"✅ 已应用: {change['file']} → {mod} 移至 Profile '{profile_id}'")
            except Exception as e:
                record.logs.append(f"⚠️ 修改 {change['file']} 失败: {e}")


    def _run_install_cmd(self, cmd: str, cwd: str, record: DeployRecord, env: dict = None) -> int:
        """执行安装命令并记录日志, 返回 exit code"""
        record.logs.append(f"📦 {cmd}")
        run_kwargs = dict(
            cwd=cwd, shell=True,
            capture_output=True, text=True, timeout=600,
            encoding="utf-8", errors="replace",
        )
        if env:
            run_kwargs["env"] = env
        result = subprocess.run(cmd, **run_kwargs)
        if result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            record.logs.extend(lines[-80:])
        if result.stderr.strip():
            err_lines = result.stderr.strip().split("\n")
            record.logs.extend(err_lines[-30:])
        return result.returncode

    async def install_repo(self, project_key: str, repo_id: str) -> DeployRecord:
        proj, repo = self._find_repo(project_key, repo_id)
        record = self._add_record(project_key, repo_id, repo.label, "install")
        target = self._repo_path(repo)

        if not target.exists():
            self._finish_record(record, "failed", "请先克隆")
            return record
        if not repo.install_cmd:
            self._finish_record(record, "failed", "未配置安装命令")
            return record

        # ── 预检: Maven 项目构建前清理残留 Java 进程 ──
        if "mvn" in (repo.install_cmd or ""):
            self._kill_project_java_processes(target, record)

        # ── 预检: 确认构建工具可用，尝试自愈 ──
        cmd_first = repo.install_cmd.split()[0]
        cmd_base = cmd_first.replace("./", "").replace(".\\" , "")
        wrapper_path = target / cmd_first.replace("./", "").replace(".\\" , "")

        if not wrapper_path.exists() and not cmd_available(cmd_base):
            # ── 自愈: Maven/Gradle 缺失 → 检查 Docker 配置 ──
            if cmd_base in ("mvn", "mvnw", "mvnw.cmd", "gradle", "gradlew", "gradlew.bat"):
                docker_compose = None
                for dc_name in ["docker-compose.yml", "docker-compose-dev.yml"]:
                    for sub in ["", "docker"]:
                        check_path = target / sub / dc_name if sub else target / dc_name
                        if check_path.exists():
                            docker_compose = check_path
                            break
                    if docker_compose:
                        break

                if docker_compose and cmd_available("docker-compose"):
                    # Docker 可用 → 切换到 Docker 部署路径
                    record.logs.append(f"🔧 自愈: {cmd_base} 未安装，检测到 Docker 配置 → 跳过本地构建")
                    dc_dir = str(docker_compose.parent.relative_to(target)).replace("\\", "/")
                    if dc_dir and dc_dir != ".":
                        new_start = f"cd {dc_dir} && docker-compose -f {docker_compose.name} up -d"
                    else:
                        new_start = f"docker-compose -f {docker_compose.name} up -d"
                    repo.install_cmd = "echo [自愈] 跳过本地构建，使用 Docker 部署"
                    repo.start_cmd = new_start
                    self._save_projects()
                    record.logs.append(f"🔧 自愈: 启动命令已切换为: {new_start}")
                    self._finish_record(record, "success", "自愈: 跳过本地构建 (使用 Docker)")
                    return record
                else:
                    # 两者均不可用 → 给出清晰的双选提示
                    tool_name = "Maven" if "mvn" in cmd_base else "Gradle"
                    hints = [f"❌ {tool_name} 和 Docker 均未安装，无法自动部署"]
                    hints.append(f"  方案一: 安装 {tool_name} → https://maven.apache.org/download.cgi" if "mvn" in cmd_base else f"  方案一: 安装 {tool_name} → https://gradle.org/install/")
                    hints.append("  方案二: 安装 Docker Desktop → https://www.docker.com/products/docker-desktop/")
                    hints.append("  安装任一工具后重新部署即可")
                    for h in hints:
                        record.logs.append(h)
                    self._finish_record(record, "failed", f"{tool_name} 和 Docker 均未安装，请安装任一工具后重试")
                    return record
            else:
                hint_map = {
                    "npm": "npm 未安装。请安装 Node.js: https://nodejs.org/",
                    "pip": "pip 未安装。请确认 Python 环境正确配置",
                }
                hint = hint_map.get(cmd_base, f"命令 '{cmd_base}' 未找到")
                record.logs.append(f"❌ 预检失败: {hint}")
                self._finish_record(record, "failed", hint)
                return record

        try:
            deploy_env = self._get_deploy_env(repo)
            rc = self._run_install_cmd(repo.install_cmd, str(target), record, env=deploy_env)
            if rc == 0:
                self._update_memory(repo.id, "build_strategy", {
                    "cmd": repo.install_cmd, "success": True,
                    "timestamp": datetime.now().isoformat()
                }, record)
                self._finish_record(record, "success", "安装完成")
            else:
                # ── 自愈: 安装失败自动修复尝试 ──
                log_text = "\n".join(record.logs[-30:])

                # 自愈 1: npm install 失败 → 淘宝镜像重试
                if "npm" in repo.install_cmd and "registry" not in repo.install_cmd:
                    record.logs.append("🔧 自愈: npm install 失败，切换淘宝镜像重试...")
                    mirror_cmd = f"{repo.install_cmd} --registry=https://registry.npmmirror.com"
                    rc2 = self._run_install_cmd(mirror_cmd, str(target), record, env=deploy_env)
                    if rc2 == 0:
                        self._finish_record(record, "success", "自愈: 使用淘宝镜像安装成功")
                    else:
                        self._finish_record(record, "failed", f"安装失败 (原始+镜像均失败, exit={rc2})")

                # 自愈 2: Maven 构建失败 → 多级自愈策略
                elif "mvn" in repo.install_cmd:
                    healed = False
                    current_cmd = repo.install_cmd

                    # 策略 A: 测试编译失败 → 添加 -Dmaven.test.skip=true
                    if ("testCompile" in log_text or "test-compile" in log_text) and "-Dmaven.test.skip=true" not in current_cmd:
                        record.logs.append("🔧 自愈: Maven 测试编译失败，添加 -Dmaven.test.skip=true 重试...")
                        current_cmd = current_cmd.replace("-DskipTests", "").strip() + " -Dmaven.test.skip=true"
                        rc2 = self._run_install_cmd(current_cmd, str(target), record, env=deploy_env)
                        if rc2 == 0:
                            repo.install_cmd = current_cmd
                            self._save_projects()
                            self._finish_record(record, "success", "自愈: 跳过测试编译后构建成功")
                            healed = True
                        else:
                            log_text = "\n".join(record.logs[-30:])

                    # 策略 B: 某模块编译失败 → 用 -pl 命令行排除（不修改源码）
                    if not healed and ("FAILURE" in log_text or "BUILD FAILURE" in log_text or "Compilation failure" in log_text or "Could not find" in log_text):
                        excluded_modules = set()

                        # ── 预检: 检测 POM Profile 中已排除的模块，避免 -pl ! 冲突 ──
                        profile_excluded = set()
                        for pom_sub in ["sample-modules/pom.xml", "sample-api/pom.xml"]:
                            pom_path = target / pom_sub
                            if pom_path.exists():
                                pom_content = pom_path.read_text(encoding="utf-8", errors="replace")
                                if "<profiles>" in pom_content:
                                    # 提取 <profiles> 中的 <module> 名称
                                    profiles_section = pom_content.split("<profiles>", 1)[-1].split("</profiles>", 1)[0]
                                    for m in re.findall(r'<module>([^<]+)</module>', profiles_section):
                                        profile_excluded.add(m)
                        if profile_excluded:
                            record.logs.append(f"📋 POM Profile 已排除: {', '.join(profile_excluded)}")

                        # 聚合父模块不应被排除
                        parent_modules = {"sample-modules", "sample-api", "sample-common", "sample-auth",
                                          "sample-gateway", "sample-visual", "sample-base", "sample-ui"}
                        for _round in range(3):  # 最多排除 3 个模块
                            failed_module = None
                            recent_logs = record.logs[-80:]

                            # 优先: [ERROR] on project xxx / Could not find ... reactor
                            for log_line in recent_logs:
                                if "[ERROR]" in log_line and "on project" in log_line:
                                    match = re.search(r'on project (\S+)', log_line)
                                    if match:
                                        mod = match.group(1).rstrip(":")
                                        if mod not in excluded_modules and mod not in parent_modules and mod not in profile_excluded:
                                            failed_module = mod
                                            break
                                if "Could not find" in log_line and "reactor" in log_line:
                                    match = re.search(r'reactor:\s*(\S+)', log_line)
                                    if match:
                                        mod = match.group(1).rstrip(":")
                                        if mod not in excluded_modules and mod not in parent_modules and mod not in profile_excluded:
                                            failed_module = mod
                                            break

                            # 次选: Compilation failure 路径中的模块名
                            if not failed_module:
                                for log_line in recent_logs:
                                    if "Compilation failure" in log_line or "[ERROR]" in log_line:
                                        match = re.search(r'[\\/](sample-\w+)[\\/]', log_line)
                                        if match:
                                            mod = match.group(1)
                                            if mod not in excluded_modules and mod not in parent_modules and mod not in profile_excluded:
                                                failed_module = mod
                                                break

                            # 最后: Reactor Summary 中的 FAILURE 行
                            if not failed_module:
                                for log_line in recent_logs:
                                    if "FAILURE" in log_line and "[INFO]" in log_line:
                                        parts = log_line.split()
                                        for p in parts:
                                            clean = p.strip().rstrip(".").rstrip(":")
                                            if (clean.startswith("sample-") or clean.startswith("ruyi-")) and clean not in excluded_modules and clean not in parent_modules and clean not in profile_excluded:
                                                failed_module = clean
                                                break
                                        if failed_module:
                                            break

                            if not failed_module:
                                break  # 没有新的失败模块

                            excluded_modules.add(failed_module)
                            # 同时排除对应的 api 模块
                            api_mod = failed_module.replace("sample-", "sample-api-").replace("ruyi-", "sample-api-")
                            excluded_modules.add(api_mod)
                            # 构建 -pl 排除参数（用逗号分隔）
                            pl_excludes = ",".join([f"!{m}" for m in excluded_modules])
                            # PowerShell 下 ! 需要用引号包裹
                            exclude_cmd = f'{current_cmd} -pl "{pl_excludes}" --fail-at-end'
                            record.logs.append(f"🔧 自愈[轮{_round+1}]: 排除 {failed_module} + {api_mod}（命令行 -pl，不修改源码）")
                            rc2 = self._run_install_cmd(exclude_cmd, str(target), record, env=deploy_env)
                            if rc2 == 0:
                                self._update_memory(repo.id, "build_strategy", {
                                    "cmd": exclude_cmd, "success": True,
                                    "excluded_modules": list(excluded_modules),
                                    "self_healed": True,
                                    "timestamp": datetime.now().isoformat()
                                }, record)
                                self._finish_record(record, "success", f"自愈: 排除 {', '.join(excluded_modules)} 后构建成功")
                                healed = True
                                break
                            else:
                                log_text = "\n".join(record.logs[-30:])
                                if _round == 2:
                                    self._finish_record(record, "failed", f"Maven 构建失败 (已排除 {', '.join(excluded_modules)}，仍失败)")
                                    healed = True

                    if not healed:
                        self._finish_record(record, "failed", f"Maven 构建失败 (exit={rc})")
        except subprocess.TimeoutExpired:
            self._finish_record(record, "failed", "安装超时 (>600s)")
        except Exception as e:
            self._finish_record(record, "failed", str(e))
        return record

    async def start_repo(self, project_key: str, repo_id: str) -> DeployRecord:
        proj, repo = self._find_repo(project_key, repo_id)
        record = self._add_record(project_key, repo_id, repo.label, "start")
        target = self._repo_path(repo)

        if not target.exists():
            self._finish_record(record, "failed", "请先克隆")
            return record
        if not repo.start_cmd:
            self._finish_record(record, "failed", "未配置启动命令")
            return record
        if repo.id in self.processes and self.processes[repo.id].poll() is None:
            self._finish_record(record, "failed", "已在运行中")
            return record

        if self._is_frontend_repo(repo):
            self._kill_project_frontend_processes(target, record)

        # ── 预检: 检查启动命令中使用的工具是否可用 ──
        # 处理 "cd dir && docker-compose ..." 等复合命令
        if "docker" in repo.start_cmd:
            docker_ok = False
            daemon_running = False
            # 检测 docker compose v2 子命令
            if cmd_available("docker"):
                # docker 命令存在，但 daemon 可能未启动
                try:
                    r = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=10)
                    daemon_running = r.returncode == 0
                except Exception:
                    daemon_running = False

                if daemon_running:
                    try:
                        r = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True, timeout=5)
                        if r.returncode == 0:
                            docker_ok = True
                            if "docker-compose" in repo.start_cmd:
                                current_cmd = re.sub(r'docker-compose(?=\s|$)', 'docker compose', repo.start_cmd)
                                record.logs.append("🔧 自愈: docker-compose → docker compose (v2)")
                                repo.start_cmd = current_cmd
                                self._save_projects()
                    except Exception:
                        pass
                    if not docker_ok and cmd_available("docker-compose"):
                        docker_ok = True
                else:
                    # Docker 已安装但 daemon 未运行 → 自动启动 Docker Desktop
                    record.logs.append("🐳 检测到 Docker 已安装但未启动，正在自动启动 Docker Desktop...")
                    started = self._auto_start_docker(record)
                    if started:
                        docker_ok = True
                        # 启动成功后重新检查 compose 版本
                        try:
                            r = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True, timeout=5)
                            if r.returncode == 0 and "docker-compose" in repo.start_cmd:
                                current_cmd = re.sub(r'docker-compose(?=\s|$)', 'docker compose', repo.start_cmd)
                                record.logs.append("🔧 自愈: docker-compose → docker compose (v2)")
                                repo.start_cmd = current_cmd
                                self._save_projects()
                        except Exception:
                            pass

            if not docker_ok:
                # 检测 docker-compose v1 独立命令
                if cmd_available("docker-compose") and daemon_running:
                    docker_ok = True

            if not docker_ok:
                if self._has_local_microservice_jars(target):
                    return self._start_microservices_without_docker(repo, target, record)
                record.logs.append("❌ Docker 未安装或无法启动")
                record.logs.append("  安装方式: https://www.docker.com/products/docker-desktop/")
                record.logs.append("  安装后请确保 docker 命令在 PATH 中可用")
                self._finish_record(record, "failed",
                    "Docker 未安装或无法启动。请安装 Docker Desktop: https://www.docker.com/products/docker-desktop/")
                return record

        # 最多重试 1 次 (用于端口自愈)
        max_attempts = 2
        current_cmd = repo.start_cmd
        current_port = repo.port

        # ── 自愈: Windows 下 source xxx.sh 不可用 → 解析 .sh 文件加载环境变量 ──
        if os.name == "nt" and "source " in current_cmd:
            match = re.search(r'source\s+(\S+\.sh)\s*&&\s*', current_cmd)
            if match:
                sh_file = match.group(1)
                sh_path = target / sh_file
                env_loaded = {}
                if sh_path.exists():
                    for line in sh_path.read_text(encoding="utf-8", errors="replace").splitlines():
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        # 处理 export KEY=VALUE 和 KEY=VALUE 格式
                        line = line.replace("export ", "")
                        if "=" in line:
                            k, v = line.split("=", 1)
                            v = v.strip().strip("'").strip('"')
                            env_loaded[k.strip()] = v
                    if env_loaded:
                        # 将环境变量写入 docker/.env (合并)
                        env_file = target / "docker" / ".env"
                        env_file.parent.mkdir(parents=True, exist_ok=True)
                        self._merge_env_file(target, env_loaded, record)
                        env_keys = ", ".join(k for k in env_loaded if "PASSWORD" not in k)
                        record.logs.append(f"🔧 自愈: Windows 不支持 source → 已从 {sh_file} 加载环境变量: {env_keys}")
                else:
                    record.logs.append(f"⚠️ 未找到 {sh_file}，跳过 source 命令")
                # 去掉 source xxx.sh && 部分
                current_cmd = re.sub(r'source\s+\S+\.sh\s*&&\s*', '', current_cmd).strip()
                record.logs.append(f"🔧 自愈: 启动命令调整为: {current_cmd}")
                repo.start_cmd = current_cmd
                self._save_projects()

        if self._is_frontend_repo(repo):
            normalized_port = self._normalize_frontend_port(
                repo,
                current_port,
                record,
                allow_port_scan=True,
            )
            if normalized_port != current_port:
                current_port = normalized_port
                repo.port = current_port
                self._save_projects()

        current_cmd = self._normalize_start_command(repo, current_cmd, current_port, record)
        current_cmd = self._normalize_compose_command(target, current_cmd, record)
        if current_cmd != repo.start_cmd or current_port != repo.port:
            repo.port = current_port
            repo.start_cmd = current_cmd
            self._save_projects()

        if self._should_start_local_microservices(repo, target, current_cmd):
            compose_cmd = self._derive_compose_start_cmd(target, record)
            if compose_cmd:
                current_cmd = compose_cmd
                repo.start_cmd = current_cmd
                self._save_projects()
                record.logs.append("🔧 自愈: 检测到微服务项目，当前启动命令仅覆盖网关，切换为 Docker 基础设施 + 本地微服务全量启动")
            else:
                return self._start_microservices_without_docker(
                    repo,
                    target,
                    record,
                    reason="🔧 自愈: 检测到微服务项目，当前启动命令仅覆盖网关，改为本地微服务全量启动",
                )

        for attempt in range(max_attempts):
            try:
                record.logs.append(f"🚀 {current_cmd}")
                log_file = DEPLOY_DIR / f"{repo.id}_output.log"

                # ── 加载 docker/.env 环境变量到进程环境 ──
                proc_env = os.environ.copy()
                env_vars = self._load_env_file(target)
                if env_vars:
                    proc_env.update(env_vars)
                    env_keys = ", ".join(k for k in env_vars if "PASSWORD" not in k)
                    record.logs.append(f"📋 加载 .env 环境变量: {env_keys}")

                with open(log_file, "w", encoding="utf-8") as lf:
                    proc = subprocess.Popen(
                        current_cmd, cwd=str(target), stdout=lf, stderr=subprocess.STDOUT,
                        shell=True, env=proc_env,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                    )
                self.processes[repo.id] = proc
                record.logs.append(f"⏳ PID: {proc.pid}，等待启动验证...")

                # ── 启动后健康检查 ──
                import time
                for _ in range(3):
                    time.sleep(1)
                    if proc.poll() is not None:
                        break

                if proc.poll() is not None:
                    # 进程已退出
                    exit_code = proc.returncode
                    self.processes.pop(repo.id, None)

                    # ── 特殊处理: docker compose -d (detach) 模式 ──
                    # docker compose up -d 会在启动容器后立即退出(exit=0)，这是正常行为
                    is_docker_detach = (
                        exit_code == 0
                        and "docker" in current_cmd
                        and "-d" in current_cmd
                    )
                    if is_docker_detach:
                        record.logs.append("✅ Docker Compose (detach 模式) 容器已在后台启动")

                        # ── 自动启动微服务 jar 包 ──
                        svc_pids = self._start_microservices(target, record)

                        # 追踪 Docker detach 模式的 repo，使其在 UI 上显示为 "运行中"
                        self.docker_repos[repo.id] = {
                            "cwd": str(target),
                            "cmd": current_cmd,
                            "pid": proc.pid,
                            "service_pids": svc_pids,
                        }
                        if current_port != repo.port or current_cmd != repo.start_cmd:
                            repo.port = current_port
                            repo.start_cmd = current_cmd
                            self._save_projects()
                        return self._finalize_microservice_start(
                            repo,
                            record,
                            project_dir=target,
                            current_cmd=current_cmd,
                            service_pids=svc_pids,
                            current_port=current_port,
                            docker_pid=proc.pid,
                        )

                    err_detail, is_port_error = self._parse_start_error(log_file, record)

                    # ── 自愈: 端口冲突 → 自动换端口重试 ──
                    if is_port_error and attempt == 0 and current_port:
                        new_port = self._find_free_port(current_port + 1)
                        if new_port:
                            record.logs.append(f"🔧 自愈: 端口 {current_port} 不可用，自动切换到 {new_port}")
                            # 替换命令中的端口号
                            current_cmd = re.sub(
                                rf'(--port\s+){current_port}\b',
                                rf'\g<1>{new_port}',
                                current_cmd,
                            )
                            # 也处理 -p port 和 :port 格式
                            if current_cmd == repo.start_cmd:  # 未替换成功，尝试其他格式
                                current_cmd = current_cmd.replace(str(current_port), str(new_port))
                            current_port = new_port
                            continue  # 重试
                        else:
                            record.logs.append("❌ 自愈失败: 无法找到可用端口")

                    # ── 自愈: 根 POM 无主类，切换到 Docker Compose / 本地微服务 ──
                    if (
                        attempt == 0
                        and "spring-boot:run" in current_cmd
                        and "main class" in err_detail.lower()
                    ):
                        compose_cmd = self._derive_compose_start_cmd(target, record)
                        if compose_cmd:
                            record.logs.append("🔧 自愈: spring-boot:run 无可执行主类，切换到 Docker Compose")
                            current_cmd = compose_cmd
                            repo.start_cmd = current_cmd
                            self._save_projects()
                            continue
                        if self._has_local_microservice_jars(target):
                            record.logs.append("🔧 自愈: spring-boot:run 无可执行主类，回退为本地微服务启动")
                            return self._start_microservices_without_docker(repo, target, record)

                    msg = f"进程立即退出 (exit={exit_code})"
                    if err_detail:
                        msg += f": {err_detail}"
                    self._finish_record(record, "failed", msg)
                    return record
                else:
                    # 进程运行中 → 端口验证
                    if current_port:
                        if "docker" in current_cmd and "-d" in current_cmd:
                            record.logs.append("⏳ Docker Compose 正在构建/拉起容器，等待后台命令完成...")
                            compose_state = self._wait_for_process_or_port(
                                proc,
                                port=current_port,
                                timeout_seconds=240,
                            )
                            if compose_state == "exited":
                                exit_code = proc.returncode
                                self.processes.pop(repo.id, None)
                                if exit_code == 0:
                                    record.logs.append("✅ Docker Compose (detach 模式) 容器已在后台启动")
                                    svc_pids = self._start_microservices(target, record)
                                    return self._finalize_microservice_start(
                                        repo,
                                        record,
                                        project_dir=target,
                                        current_cmd=current_cmd,
                                        service_pids=svc_pids,
                                        current_port=current_port,
                                        docker_pid=proc.pid,
                                    )

                                err_detail, _ = self._parse_start_error(log_file, record)
                                msg = f"Docker Compose 启动失败 (exit={exit_code})"
                                if err_detail:
                                    msg += f": {err_detail}"
                                self._finish_record(record, "failed", msg)
                                return record
                            if compose_state == "timeout":
                                self._parse_start_error(log_file, record)
                                self._finish_record(record, "failed", "Docker Compose 执行超时，端口仍未就绪")
                                return record

                        time.sleep(2)
                        if proc.poll() is not None:
                            exit_code = proc.returncode
                            self.processes.pop(repo.id, None)

                            # ── 修复: 延迟退出也需检测 docker detach 模式 ──
                            is_docker_detach_delayed = (
                                exit_code == 0
                                and "docker" in current_cmd
                                and "-d" in current_cmd
                            )
                            if is_docker_detach_delayed:
                                record.logs.append("✅ Docker Compose (detach 模式) 容器已在后台启动")
                                svc_pids = self._start_microservices(target, record)
                                self.docker_repos[repo.id] = {
                                    "cwd": str(target), "cmd": current_cmd,
                                    "pid": proc.pid, "service_pids": svc_pids,
                                }
                                return self._finalize_microservice_start(
                                    repo,
                                    record,
                                    project_dir=target,
                                    current_cmd=current_cmd,
                                    service_pids=svc_pids,
                                    current_port=current_port,
                                    docker_pid=proc.pid,
                                )

                            err_detail, _ = self._parse_start_error(log_file, record)
                            if (
                                attempt == 0
                                and "spring-boot:run" in current_cmd
                                and "main class" in err_detail.lower()
                            ):
                                compose_cmd = self._derive_compose_start_cmd(target, record)
                                if compose_cmd:
                                    record.logs.append("🔧 自愈: spring-boot:run 延迟退出且无主类，切换到 Docker Compose")
                                    current_cmd = compose_cmd
                                    repo.start_cmd = current_cmd
                                    self._save_projects()
                                    continue
                                if self._has_local_microservice_jars(target):
                                    record.logs.append("🔧 自愈: spring-boot:run 延迟退出且无主类，回退为本地微服务启动")
                                    return self._start_microservices_without_docker(repo, target, record)
                            self._finish_record(record, "failed", f"进程延迟退出 (exit={exit_code})")
                            return record
                        elif self._check_port(current_port):
                            # 如果端口变了，持久化
                            if current_port != repo.port or current_cmd != repo.start_cmd:
                                repo.port = current_port
                                repo.start_cmd = current_cmd
                                self._save_projects()
                            record.logs.append(f"⏳ 端口 {current_port} 初步就绪，继续验证稳定性...")
                            if self._wait_for_port_stability(
                                current_port,
                                timeout_seconds=12,
                                stable_seconds=5,
                                process_ids=[proc.pid],
                            ):
                                record.logs.append(f"✅ 端口 {current_port} 已稳定就绪")
                                if self._verify_repo_http_readiness(repo, current_port, record):
                                    self._remember_effective_env(repo, target, record)
                                    self._finish_record(record, "success", f"启动成功 (PID: {proc.pid}, Port: {current_port})")
                                else:
                                    self._finish_record(record, "failed", f"端口 {current_port} 已打开，但 HTTP 就绪校验未通过")
                            else:
                                self._parse_start_error(log_file, record)
                                if proc.poll() is not None:
                                    self.processes.pop(repo.id, None)
                                self._finish_record(record, "failed", f"端口 {current_port} 未通过稳定性验证")
                        else:
                            if current_port != repo.port or current_cmd != repo.start_cmd:
                                repo.port = current_port
                                repo.start_cmd = current_cmd
                                self._save_projects()
                            record.logs.append(f"⏳ 进程运行中，继续等待端口 {current_port} 稳定就绪...")
                            if self._wait_for_port_stability(
                                current_port,
                                timeout_seconds=20,
                                stable_seconds=5,
                                process_ids=[proc.pid],
                            ):
                                record.logs.append(f"✅ 端口 {current_port} 已稳定就绪")
                                if self._verify_repo_http_readiness(repo, current_port, record):
                                    self._remember_effective_env(repo, target, record)
                                    self._finish_record(record, "success", f"启动成功 (PID: {proc.pid}, Port: {current_port})")
                                else:
                                    self._finish_record(record, "failed", f"端口 {current_port} 已打开，但 HTTP 就绪校验未通过")
                            else:
                                self._parse_start_error(log_file, record)
                                if proc.poll() is not None:
                                    self.processes.pop(repo.id, None)
                                self._finish_record(record, "failed", f"进程运行中，但端口 {current_port} 未通过稳定性验证")
                    else:
                        record.logs.append(f"✅ 进程运行中")
                        self._remember_effective_env(repo, target, record)
                        self._finish_record(record, "success", f"启动成功 (PID: {proc.pid})")
                    return record
            except Exception as e:
                self._finish_record(record, "failed", str(e))
                return record

        self._finish_record(record, "failed", "自愈重试次数耗尽")
        return record

    def _parse_start_error(self, log_file: Path, record: DeployRecord) -> tuple:
        """解析启动日志，返回 (错误摘要, 是否为端口错误)"""
        err_detail = ""
        is_port_error = False
        try:
            log_content = log_file.read_text(encoding="utf-8", errors="replace").strip()
            if log_content:
                clean_log = re.sub(r'\x1b\[[0-9;]*m', '', log_content)
                err_lines = clean_log.strip().split("\n")
                record.logs.extend(err_lines[-10:])
                # 第一轮: 优先检查端口错误 (EACCES / EADDRINUSE)
                for line in err_lines:
                    lower_line = line.lower()
                    if (
                        "eacces" in lower_line
                        or "eaddrinuse" in lower_line
                        or "address already in use" in lower_line
                        or re.search(r"port\s+\d+\s+is(?: already)?\s+in use", lower_line)
                    ):
                        err_detail = line.strip()
                        is_port_error = True
                        break
                # 第二轮: 若无端口错误，匹配通用错误
                if not err_detail:
                    for line in err_lines:
                        if "Error:" in line:
                            err_detail = line.strip()
                            break
                    if not err_detail:
                        for line in err_lines:
                            if "error" in line.lower() and line.strip():
                                err_detail = line.strip()
                                break
        except Exception:
            pass
        return err_detail, is_port_error

    def _load_env_file(self, project_dir: Path) -> Dict[str, str]:
        """读取仓库当前生效的环境变量文件，优先 docker/.env。"""
        env_file = self._get_env_file_path(project_dir)
        return self._read_env_file(env_file)

    @staticmethod
    def _pid_alive(pid: Optional[int]) -> bool:
        """跨平台判断进程是否仍然存活。"""
        if not pid:
            return False
        try:
            if os.name == "nt":
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return str(pid) in result.stdout
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def _wait_for_port_stability(
        self,
        port: int,
        *,
        timeout_seconds: int = 40,
        stable_seconds: int = 8,
        process_ids: Optional[List[int]] = None,
    ) -> bool:
        """等待端口持续稳定，同时确认相关进程未在验证期间退出。"""
        deadline = time.time() + timeout_seconds
        stable_since = None
        tracked_pids = [pid for pid in (process_ids or []) if pid]

        while time.time() < deadline:
            if tracked_pids and any(not self._pid_alive(pid) for pid in tracked_pids):
                return False

            if self._check_port(port):
                if stable_since is None:
                    stable_since = time.time()
                elif time.time() - stable_since >= stable_seconds:
                    return True
            else:
                stable_since = None

            time.sleep(1)

        return False

    def _normalize_start_command(
        self,
        repo: RepoConfig,
        current_cmd: str,
        current_port: int,
        record: DeployRecord,
    ) -> str:
        """针对已知前端开发服务器补全端口约束，避免静默顺延端口导致误判。"""
        normalized = (current_cmd or "").strip()
        lower_cmd = normalized.lower()
        tech_stack = (repo.tech_stack or "").lower()
        looks_like_vite = "vite" in lower_cmd or "vite" in tech_stack

        if not looks_like_vite:
            return normalized

        changed = False
        if any(token in lower_cmd for token in ("npm ", "pnpm ", "bun ", "yarn ")):
            separator = " -- "
            first_separator = normalized.find(separator)
            if first_separator != -1:
                prefix = normalized[: first_separator + len(separator)]
                suffix = normalized[first_separator + len(separator):]
                cleaned_suffix = re.sub(r"\s+--\s+(?=-)", " ", suffix)
                if cleaned_suffix != suffix:
                    normalized = prefix + cleaned_suffix.lstrip()
                    changed = True
                    lower_cmd = normalized.lower()
        if current_port:
            rewritten = re.sub(
                r"(--port\s+)\d+\b",
                lambda m: f"{m.group(1)}{current_port}",
                normalized,
                flags=re.IGNORECASE,
            )
            rewritten = re.sub(
                r"(?<!\S)(-p\s+)\d+\b",
                lambda m: f"{m.group(1)}{current_port}",
                rewritten,
                flags=re.IGNORECASE,
            )
            if rewritten != normalized:
                normalized = rewritten
                changed = True
            lower_cmd = normalized.lower()
            has_explicit_port = "--port" in lower_cmd or re.search(r"(?<!\S)-p\s+\d+\b", lower_cmd)
            if not has_explicit_port:
                if any(token in lower_cmd for token in ("npm ", "pnpm ", "bun ", "yarn ")):
                    normalized = f"{normalized} -- --port {current_port}"
                else:
                    normalized = f"{normalized} --port {current_port}"
                changed = True

        if "--strictport" not in normalized.lower():
            normalized = f"{normalized} --strictPort"
            changed = True

        if changed:
            record.logs.append("🔧 自愈: Vite 启动命令已强制绑定目标端口，避免静默切换端口")
        return normalized

    @staticmethod
    def _looks_like_gateway_only_start(current_cmd: str) -> bool:
        """识别只启动网关的微服务命令。"""
        normalized_cmd = re.sub(r"\s+", " ", (current_cmd or "").lower()).strip()
        if not normalized_cmd:
            return False

        gateway_markers = ("sample-gateway", "gateway.jar")
        if "java" in normalized_cmd and "-jar" in normalized_cmd and any(marker in normalized_cmd for marker in gateway_markers):
            return True

        if "spring-boot:run" in normalized_cmd and any(marker in normalized_cmd for marker in gateway_markers):
            return True

        return False

    @staticmethod
    def _http_probe(url: str) -> Dict[str, object]:
        try:
            with urllib.request.urlopen(url, timeout=6) as resp:
                body = resp.read(4096).decode("utf-8", errors="ignore")
                return {"status": resp.status, "body": body}
        except urllib.error.HTTPError as exc:
            body = exc.read(4096).decode("utf-8", errors="ignore")
            return {"status": exc.code, "body": body}
        except Exception as exc:
            return {"error": str(exc)}

    @staticmethod
    def _extract_gateway_port_from_log_text(log_text: str) -> int:
        """从网关日志里提取运行时端口，优先使用明确的网关注册信息。"""
        if not log_text:
            return 0

        for raw_line in reversed(log_text.splitlines()):
            line = raw_line.strip()
            if not line:
                continue
            lower_line = line.lower()

            if "registering service sample-gateway" in lower_line:
                match = re.search(r"\bport=(\d+)\b", line)
                if match:
                    return int(match.group(1))

            if "netty started on port" in lower_line:
                match = re.search(r"netty started on port\s+(\d+)\b", line, flags=re.IGNORECASE)
                if match:
                    return int(match.group(1))

            if "tomcat started on port" in lower_line:
                match = re.search(r"tomcat started on port\(s\):\s*(\d+)\b", line, flags=re.IGNORECASE)
                if match:
                    return int(match.group(1))

        return 0

    def _discover_runtime_gateway_port(
        self,
        project_dir: Path,
        service_pids: List[Dict],
        record: Optional[DeployRecord] = None,
    ) -> int:
        """从当前项目的网关日志里推断真实运行端口。"""
        log_dir = project_dir / "docker" / "logs"
        if not log_dir.exists():
            return 0

        candidates: List[Path] = [
            log_dir / "sample-gateway.log",
            log_dir / "gateway.log",
        ]
        for svc in service_pids:
            name = (svc.get("name") or "").strip()
            if "gateway" in name.lower():
                candidates.append(log_dir / f"{name}.log")

        seen: set[str] = set()
        for log_path in candidates:
            resolved = str(log_path)
            if resolved in seen or not log_path.exists():
                continue
            seen.add(resolved)
            try:
                port = self._extract_gateway_port_from_log_text(
                    log_path.read_text(encoding="utf-8", errors="replace")
                )
            except Exception:
                continue

            if port:
                if record:
                    record.logs.append(f"🔎 从网关日志发现运行时端口: {port} ({log_path.name})")
                return port
        return 0

    def _verify_repo_http_readiness(self, repo: RepoConfig, port: int, record: DeployRecord) -> bool:
        """在端口连通后做最小 HTTP 语义校验，避免把占位响应当成部署成功。"""
        is_frontend = self._is_frontend_repo(repo)

        if is_frontend:
            candidates = ["/", "/login", "/index"]
        else:
            candidates = ["/code", "/captchaImage", "/prod-api/captchaImage", "/auth/login", "/actuator/health"]

        observations: List[str] = []
        for path in candidates:
            url = f"http://127.0.0.1:{port}{path}"
            probe = self._http_probe(url)
            status = probe.get("status")
            body = str(probe.get("body", ""))
            normalized_body = body.lower()

            if status is None:
                observations.append(f"{path}: {probe.get('error', '连接失败')}")
                continue

            if "no static resource" in normalized_body:
                observations.append(f"{path}: {status} (静态占位响应)")
                continue

            if is_frontend:
                if status in (200, 301, 302) and ("<html" in normalized_body or "<!doctype html" in normalized_body):
                    record.logs.append(f"✅ HTTP 页面校验通过: {path} -> {status}")
                    return True
                observations.append(f"{path}: {status}")
                continue

            if status in (200, 401, 403, 405):
                record.logs.append(f"✅ HTTP 路由校验通过: {path} -> {status}")
                return True

            observations.append(f"{path}: {status}")

        if observations:
            record.logs.append(f"⚠️ HTTP 就绪校验未通过: {'; '.join(observations[:4])}")
        return False

    def _has_local_microservice_jars(self, project_dir: Path) -> bool:
        """检查是否存在可直接启动的本地微服务 jar 包"""
        return bool(self._list_local_microservice_jars(project_dir))

    def _list_local_microservice_jars(self, project_dir: Path) -> List[Path]:
        """列出项目下可直接启动的微服务 jar 包。"""
        skip_patterns = {"sample-api-", "sample-common-", "sample-common-"}
        jar_files: List[Path] = []
        for jar in project_dir.rglob("target/*.jar"):
            jar_name = jar.name
            if any(p in jar_name for p in skip_patterns):
                continue
            jar_files.append(jar)
        return jar_files

    def _should_start_local_microservices(self, repo: RepoConfig, project_dir: Path, current_cmd: str) -> bool:
        """微服务项目若只配置了网关启动命令，则自动改为全量启动本地 jar。"""
        jar_files = self._list_local_microservice_jars(project_dir)
        if len(jar_files) <= 1:
            return False

        if not self._looks_like_gateway_only_start(current_cmd):
            return False

        tech_stack = (repo.tech_stack or "").lower()
        looks_like_microservice = (
            "spring cloud" in tech_stack
            or "nacos" in tech_stack
            or "微服务" in tech_stack
            or len(jar_files) >= 3
        )
        return looks_like_microservice

    def _compose_file_looks_runnable(self, project_dir: Path, compose_file: Path, record: DeployRecord) -> bool:
        """快速校验 compose 文件依赖的 build context 是否存在。"""
        try:
            content = compose_file.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            record.logs.append(f"⚠️ 无法读取 Docker Compose 文件: {exc}")
            return False

        missing_contexts = []
        for match in re.finditer(r"(?m)^\s*context:\s*([^\s#]+)", content):
            raw_path = match.group(1).strip().strip('"').strip("'")
            context_path = (compose_file.parent / raw_path).resolve()
            if not context_path.exists():
                missing_contexts.append(raw_path)

        if missing_contexts:
            preview = ", ".join(missing_contexts[:4])
            record.logs.append(f"⚠️ Docker Compose 构建上下文缺失: {preview}")
            return False

        return True

    def _find_compose_file(self, project_dir: Path, record: DeployRecord) -> Optional[Path]:
        """查找项目内可执行的 Compose 文件，避免误用上级目录配置。"""
        for dc_name in ["docker-compose-dev.yml", "docker-compose.yml"]:
            for check_path in [project_dir / "docker" / dc_name, project_dir / dc_name]:
                if check_path.exists():
                    if self._compose_file_looks_runnable(project_dir, check_path, record):
                        return check_path
                    return None
        return None

    def _normalize_compose_command(self, project_dir: Path, current_cmd: str, record: DeployRecord) -> str:
        """将泛化的 docker compose 命令绑定到项目内 Compose 文件，避免向上级目录误匹配。"""
        normalized = (current_cmd or "").strip()
        lower_cmd = normalized.lower()
        if "docker compose" not in lower_cmd and "docker-compose" not in lower_cmd:
            return normalized
        if "-f " in lower_cmd or re.search(r"\bcd\s+.+&&", lower_cmd):
            return normalized

        compose_file = self._find_compose_file(project_dir, record)
        if not compose_file:
            return normalized

        compose_bin = "docker compose" if "docker compose" in lower_cmd else "docker-compose"
        dc_dir = str(compose_file.parent.relative_to(project_dir)).replace("\\", "/")
        explicit_cmd = f"{compose_bin} -f {compose_file.name} up -d"
        if dc_dir and dc_dir != ".":
            explicit_cmd = f"cd {dc_dir} && {explicit_cmd}"

        if explicit_cmd != normalized:
            record.logs.append("🔧 自愈: 通用 Docker Compose 命令已绑定到项目内 Compose 文件，避免误用上级目录配置")
        return explicit_cmd

    @staticmethod
    def _build_java_system_properties(env_vars: Dict[str, str]) -> List[str]:
        """把部署环境变量提升为 JVM System Properties，覆盖硬编码的 Spring/Nacos 配置。"""
        props: List[str] = []

        def add_prop(key: str, value: Optional[str]):
            if value:
                props.append(f"-D{key}={value}")

        profile = env_vars.get("SPRING_PROFILES_ACTIVE")
        nacos_server = env_vars.get("NACOS_SERVER_ADDR")
        nacos_discovery = env_vars.get("NACOS_DISCOVERY_SERVER_ADDR") or nacos_server
        nacos_config = env_vars.get("NACOS_CONFIG_SERVER_ADDR") or nacos_server
        nacos_namespace = env_vars.get("NACOS_NAMESPACE")
        nacos_group = env_vars.get("NACOS_GROUP")
        nacos_username = env_vars.get("NACOS_USERNAME")
        nacos_password = env_vars.get("NACOS_PASSWORD")

        add_prop("spring.profiles.active", profile)
        add_prop("spring.cloud.nacos.discovery.server-addr", nacos_discovery)
        add_prop("spring.cloud.nacos.config.server-addr", nacos_config)
        add_prop("spring.cloud.nacos.discovery.namespace", nacos_namespace)
        add_prop("spring.cloud.nacos.config.namespace", nacos_namespace)
        add_prop("spring.cloud.nacos.discovery.group", nacos_group)
        add_prop("spring.cloud.nacos.config.group", nacos_group)
        add_prop("spring.cloud.nacos.discovery.username", nacos_username)
        add_prop("spring.cloud.nacos.config.username", nacos_username)
        add_prop("spring.cloud.nacos.discovery.password", nacos_password)
        add_prop("spring.cloud.nacos.config.password", nacos_password)
        return props

    @staticmethod
    def _select_critical_microservices(service_pids: List[Dict]) -> List[Dict]:
        """识别微服务项目的关键启动链路，优先关注网关/认证/系统。"""
        critical_prefixes = (
            "sample-gateway",
            "sample-auth",
            "sample-modules-system",
            "sample-system",
        )
        critical_services: List[Dict] = []
        for svc in service_pids:
            name = (svc.get("name") or "").lower()
            if any(name.startswith(prefix) for prefix in critical_prefixes):
                critical_services.append(svc)
        return critical_services

    @staticmethod
    def _wait_for_process_or_port(
        proc: subprocess.Popen,
        *,
        port: int = 0,
        timeout_seconds: int = 180,
    ) -> str:
        """等待进程退出或目标端口开放。返回 exited / port / timeout。"""
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if proc.poll() is not None:
                return "exited"
            if port:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(1)
                        if s.connect_ex(("127.0.0.1", port)) == 0:
                            return "port"
                except Exception:
                    pass
            time.sleep(1)
        return "timeout"

    def _derive_compose_start_cmd(self, project_dir: Path, record: DeployRecord) -> str:
        """根据项目目录推导可执行的 Docker Compose 启动命令。"""
        compose_file = self._find_compose_file(project_dir, record)
        if not compose_file:
            return ""

        compose_bin = ""
        docker_ready = False
        if cmd_available("docker"):
            try:
                docker_ready = subprocess.run(
                    ["docker", "info"], capture_output=True, text=True, timeout=10
                ).returncode == 0
            except Exception:
                docker_ready = False

            if not docker_ready:
                record.logs.append("🐳 检测到 Docker Compose 兜底方案，尝试自动启动 Docker Desktop...")
                docker_ready = self._auto_start_docker(record)

            if docker_ready:
                try:
                    compose_v2 = subprocess.run(
                        ["docker", "compose", "version"], capture_output=True, text=True, timeout=5
                    )
                    if compose_v2.returncode == 0:
                        compose_bin = "docker compose"
                except Exception:
                    pass

        if not compose_bin and cmd_available("docker-compose"):
            compose_bin = "docker-compose"

        if not compose_bin:
            return ""

        dc_dir = str(compose_file.parent.relative_to(project_dir)).replace("\\", "/")
        if dc_dir and dc_dir != ".":
            return f"cd {dc_dir} && {compose_bin} -f {compose_file.name} up -d"
        return f"{compose_bin} -f {compose_file.name} up -d"

    def _finalize_microservice_start(
        self,
        repo: RepoConfig,
        record: DeployRecord,
        *,
        project_dir: Path,
        current_cmd: str,
        service_pids: List[Dict],
        current_port: int,
        docker_pid: Optional[int] = None,
        fallback_no_docker: bool = False,
    ) -> DeployRecord:
        running = [svc for svc in service_pids if svc.get("pid")]
        total = len(service_pids)
        critical_services = self._select_critical_microservices(service_pids)
        critical_missing = [
            svc["name"]
            for svc in critical_services
            if not svc.get("pid")
        ]
        if critical_missing:
            record.logs.append(f"❌ 关键微服务未启动: {', '.join(critical_missing[:6])}")
            self._finish_record(record, "failed", f"关键微服务未启动: {', '.join(critical_missing[:3])}")
            return record

        stability_services = critical_services or running
        tracked_pids = [svc.get("pid") for svc in stability_services if svc.get("pid")]
        critical_names = {svc.get("name") for svc in critical_services if svc.get("name")}

        effective_port = current_port or self._discover_runtime_gateway_port(project_dir, service_pids, record)

        def persist_runtime_state(port_value: int):
            self.docker_repos[repo.id] = {
                "cwd": str(project_dir),
                "cmd": current_cmd,
                "pid": docker_pid,
                "service_pids": service_pids,
                "fallback_no_docker": fallback_no_docker,
                "port": port_value,
            }
            self._update_memory(repo.id, "start_config", {
                "docker_cmd": current_cmd,
                "port": port_value,
                "microservices": [
                    {"name": svc["name"], "status": svc["status"]}
                    for svc in service_pids
                ],
                "success_count": len(running),
                "total_count": total,
                "timestamp": datetime.now().isoformat(),
                "fallback_no_docker": fallback_no_docker,
            }, record)

        if effective_port and effective_port != repo.port:
            repo.port = effective_port
            self._save_projects()

        persist_runtime_state(effective_port)

        if effective_port:
            record.logs.append(f"⏳ 等待端口 {effective_port} 稳定就绪...")
            port_ready = self._wait_for_port_stability(
                effective_port,
                timeout_seconds=60,
                stable_seconds=10,
                process_ids=tracked_pids,
            )
            if not port_ready:
                discovered_port = self._discover_runtime_gateway_port(project_dir, service_pids, record)
                if discovered_port and discovered_port != effective_port:
                    record.logs.append(
                        f"🔧 自愈: 配置端口 {effective_port} 未就绪，改用网关真实运行端口 {discovered_port}"
                    )
                    effective_port = discovered_port
                    repo.port = effective_port
                    self._save_projects()
                    persist_runtime_state(effective_port)
                    record.logs.append(f"⏳ 改用端口 {effective_port} 继续校验...")
                    port_ready = self._wait_for_port_stability(
                        effective_port,
                        timeout_seconds=60,
                        stable_seconds=10,
                        process_ids=tracked_pids,
                    )

            if not port_ready:
                crashed = [
                    svc["name"]
                    for svc in stability_services
                    if not self._pid_alive(svc.get("pid"))
                ]
                if crashed:
                    record.logs.append(f"❌ 稳定性校验失败，已退出服务: {', '.join(crashed[:6])}")
                record.logs.append(f"⚠️ 端口 {effective_port} 未就绪，已启动 {len(running)}/{total} 个微服务")
                self._finish_record(record, "failed", f"微服务已启动 {len(running)}/{total} 个，但端口 {effective_port} 未就绪")
                return record

            record.logs.append(f"✅ 端口 {effective_port} 已稳定就绪")
            if not self._verify_repo_http_readiness(repo, effective_port, record):
                self._finish_record(record, "failed", f"端口 {effective_port} 已打开，但 HTTP 就绪校验未通过")
                return record

            optional_exited = [
                svc["name"]
                for svc in running
                if svc.get("name") not in critical_names and not self._pid_alive(svc.get("pid"))
            ]
            if optional_exited:
                record.logs.append(f"⚠️ 非关键微服务已退出，但关键入口校验通过: {', '.join(optional_exited[:6])}")

        self._update_memory(repo.id, "last_success", datetime.now().isoformat())
        self._remember_effective_env(repo, project_dir, record)
        mode = "Fallback" if fallback_no_docker else "Docker"
        self._finish_record(record, "success", f"启动成功 ({mode} + {len(running)}/{total} 微服务)")
        return record

    def _start_microservices_without_docker(
        self,
        repo: RepoConfig,
        project_dir: Path,
        record: DeployRecord,
        reason: str = "",
    ) -> DeployRecord:
        """Docker 不可用时，回退为直接启动本地已构建微服务 jar"""
        record.logs.append(reason or "🔧 自愈: Docker 不可用，回退为本地微服务启动")
        svc_pids = self._start_microservices(project_dir, record)
        running = [svc for svc in svc_pids if svc.get("pid")]
        total = len(svc_pids)

        if not running:
            self._finish_record(record, "failed", "Docker 不可用，且未能启动任何本地微服务")
            return record
        return self._finalize_microservice_start(
            repo,
            record,
            project_dir=project_dir,
            current_cmd=repo.start_cmd,
            service_pids=svc_pids,
            current_port=repo.port,
            fallback_no_docker=True,
        )

    def _start_microservices(self, project_dir: Path, record: DeployRecord) -> List[Dict]:
        """在 Docker 基础设施启动后，自动扫描并启动所有编译成功的微服务 jar 包"""
        import glob
        results = []

        # ── 读取 .env 环境变量 (Nacos 等) ──
        env_vars = self._load_env_file(project_dir)
        if env_vars:
            env_keys = ", ".join(k for k in env_vars if "PASSWORD" not in k)
            record.logs.append(f"📋 加载 .env 环境变量: {env_keys}")

        # ── 构建 Java 运行环境变量 ──
        svc_env = os.environ.copy()
        svc_env.update(env_vars)
        java_system_props = self._build_java_system_properties(env_vars)
        if java_system_props:
            record.logs.append("🔧 自愈: 为本地微服务注入 Spring/Nacos JVM 参数，覆盖硬编码配置")

        # ── 扫描所有可执行 jar ──
        jar_files = self._list_local_microservice_jars(project_dir)

        if not jar_files:
            record.logs.append("⚠️ 未找到可执行微服务 jar 包")
            return results

        # ── 按优先级排序: Gateway → Auth → System → 其他 ──
        priority_map = {
            "sample-gateway": 0,
            "sample-auth": 1,
            "sample-modules-system": 2,
        }
        def sort_key(jar_path: Path) -> int:
            for name, pri in priority_map.items():
                if name in jar_path.name:
                    return pri
            return 10  # 其他服务排后面

        jar_files.sort(key=sort_key)
        record.logs.append(f"🔍 发现 {len(jar_files)} 个微服务 jar 包")

        # ── 检查 java 是否可用 ──
        try:
            java_check = subprocess.run(
                ["java", "-version"], capture_output=True, text=True, timeout=5
            )
            if java_check.returncode != 0:
                record.logs.append("❌ java 不可用，无法启动微服务")
                return results
        except Exception:
            record.logs.append("❌ java 命令不存在，无法启动微服务")
            return results

        # ── 逐个启动微服务 ──
        log_dir = project_dir / "docker" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        for jar in jar_files:
            svc_name = jar.stem  # e.g. sample-gateway
            svc_log = log_dir / f"{svc_name}.log"
            svc_info = {"name": svc_name, "jar": str(jar), "pid": None, "status": "failed"}

            try:
                log_f = open(svc_log, "w", encoding="utf-8")
                proc = subprocess.Popen(
                    ["java", "-Xms256m", "-Xmx512m", *java_system_props, "-jar", str(jar)],
                    cwd=str(jar.parent.parent),
                    env=svc_env,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )

                # 等待几秒确认没有立即崩溃
                import time
                time.sleep(3)

                if proc.poll() is None:
                    # 进程还在运行 → 成功
                    svc_info["pid"] = proc.pid
                    svc_info["status"] = "running"
                    record.logs.append(f"  ✅ {svc_name} → PID: {proc.pid}")
                else:
                    # 进程已退出 → 启动失败
                    exit_code = proc.returncode
                    # 读取最后几行日志用于错误诊断
                    try:
                        last_lines = svc_log.read_text(encoding="utf-8", errors="replace").strip().split("\n")[-3:]
                        err_hint = " | ".join(l.strip() for l in last_lines if l.strip())[:150]
                    except Exception:
                        err_hint = ""
                    svc_info["status"] = "failed"
                    svc_info["exit_code"] = exit_code
                    record.logs.append(f"  ❌ {svc_name} → exit={exit_code}" + (f" ({err_hint})" if err_hint else ""))
            except Exception as e:
                svc_info["status"] = "error"
                record.logs.append(f"  ❌ {svc_name} → {str(e)[:100]}")

            results.append(svc_info)

        # ── 汇总 ──
        ok = len([r for r in results if r["status"] == "running"])
        fail = len(results) - ok
        record.logs.append(f"📊 微服务启动: {ok} 成功, {fail} 失败 (共 {len(results)} 个)")

        return results

    async def stop_repo(self, project_key: str, repo_id: str) -> DeployRecord:
        _, repo = self._find_repo(project_key, repo_id)
        record = self._add_record(project_key, repo_id, repo.label, "stop")
        target = self._repo_path(repo)

        # ── 检查是否为 Docker detach 模式的 repo ──
        docker_info = self.docker_repos.get(repo.id)
        if docker_info:
            try:
                # 先停止微服务进程
                svc_pids = docker_info.get("service_pids", [])
                killed = 0
                for svc in svc_pids:
                    pid = svc.get("pid")
                    if pid:
                        try:
                            if os.name == "nt":
                                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
                            else:
                                os.kill(pid, signal.SIGTERM)
                            killed += 1
                        except Exception:
                            pass
                if killed:
                    record.logs.append(f"🛑 已停止 {killed} 个微服务进程")

                if not docker_info.get("fallback_no_docker"):
                    # 再停止 Docker 容器
                    stop_cmd = docker_info["cmd"].replace("up -d", "down")
                    record.logs.append(f"🛑 Docker Compose down: {stop_cmd}")
                    result = subprocess.run(
                        stop_cmd, cwd=docker_info["cwd"], shell=True,
                        capture_output=True, text=True, timeout=30
                    )
                    if result.returncode == 0:
                        record.logs.append("✅ Docker 容器已停止")
                    else:
                        record.logs.append(f"⚠️ {result.stderr.strip()[:200]}")
                    message = f"Docker 容器 + {killed} 微服务已停止"
                else:
                    record.logs.append("🛑 已停止本地微服务（未使用 Docker 容器）")
                    message = f"本地微服务已停止 ({killed})"
                self.docker_repos.pop(repo.id, None)
                self._finish_record(record, "success", message)
            except Exception as e:
                self._finish_record(record, "failed", str(e))
            return record

        proc = self.processes.get(repo.id)
        if not proc or proc.poll() is not None:
            killed = self._kill_project_frontend_processes(target, record) if self._is_frontend_repo(repo) else 0
            message = f"已清理 {killed} 个残留前端进程" if killed else "未运行"
            self._finish_record(record, "success", message)
            return record
        try:
            record.logs.append(f"🛑 停止 PID: {proc.pid}")
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=10)
            self.processes.pop(repo.id, None)
            killed = self._kill_project_frontend_processes(target, record) if self._is_frontend_repo(repo) else 0
            message = "已停止"
            if killed:
                message = f"已停止，并清理 {killed} 个残留前端进程"
            self._finish_record(record, "success", message)
        except Exception as e:
            self._finish_record(record, "failed", str(e))
        return record

    async def full_deploy_repo(
        self,
        project_key: str,
        repo_id: str,
        branch: str = "",
        existing_record: DeployRecord = None,
        job_id: str = "",
    ) -> DeployRecord:
        _, repo = self._find_repo(project_key, repo_id)

        # 使用预创建的记录或新建
        if existing_record:
            record = existing_record
        else:
            record = self._add_record(project_key, repo_id, repo.label, "full_deploy")
            record.logs.append(f"🔄 一键部署 [{repo.label}]...")

        # 部署前：将用户上下文写入 .env 文件
        target = self._repo_path(repo)
        if repo.deploy_context and target.exists():
            self._write_env_file(target, repo, record)

        # 初始化 3 个子步骤
        step_names = [("clone", "📥 克隆"), ("install", "📦 安装"), ("start", "🚀 启动")]
        if not record.steps:
            record.steps = [DeployStep(name=n) for n, _ in step_names]
        step_fns = [
            lambda: self.clone_repo(project_key, repo_id, branch),
            lambda: self.install_repo(project_key, repo_id),
            lambda: self.start_repo(project_key, repo_id),
        ]

        self._emit_event(repo_id, {
            "type": "deploy_start", "record_id": record.id, "repo_label": repo.label,
            "steps": [n for n, _ in step_names],
        })

        try:
            for i, (step_fn, (sname, slabel)) in enumerate(zip(step_fns, step_names)):
                if job_id and self._job_cancellation_requested(job_id):
                    for j in range(i, len(record.steps)):
                        if record.steps[j].status == "pending":
                            record.steps[j].status = "skipped"
                            record.steps[j].message = "任务已取消，未执行"
                    self._finish_record(record, "cancelled", "部署任务已取消")
                    self._emit_event(repo_id, {
                        "type": "deploy_done", "status": "cancelled", "message": "部署任务已取消",
                    })
                    return record

                step = record.steps[i]
                step.status = "running"
                self._emit_event(repo_id, {"type": "step_start", "step": sname, "label": slabel})
                self._save_history()

                t0 = time.time()
                sub_record = await step_fn()
                elapsed = (time.time() - t0) * 1000

                step.logs = sub_record.logs
                step.duration_ms = elapsed
                step.status = sub_record.status
                step.message = sub_record.message
                record.logs.extend(sub_record.logs)

                self._emit_event(repo_id, {
                    "type": "step_done", "step": sname, "label": slabel,
                    "status": sub_record.status, "message": sub_record.message,
                    "duration_ms": round(elapsed),
                    "logs": sub_record.logs[-50:],  # 推送最近 50 行日志
                })

                # 删除子记录 (只保留汇总记录)
                self.history = [r for r in self.history if r.id != sub_record.id]

                if job_id and self._job_cancellation_requested(job_id):
                    for j in range(i + 1, len(record.steps)):
                        record.steps[j].status = "skipped"
                        record.steps[j].message = "任务已取消，未执行"
                    self._finish_record(record, "cancelled", "部署任务已取消")
                    self._emit_event(repo_id, {
                        "type": "deploy_done", "status": "cancelled", "message": "部署任务已取消",
                    })
                    return record

                if sub_record.status == "failed":
                    # 后续步骤标记为跳过
                    for j in range(i + 1, len(record.steps)):
                        record.steps[j].status = "skipped"
                        record.steps[j].message = "前序步骤失败，已跳过"
                    self._finish_record(record, "failed", f"{slabel}失败: {sub_record.message}")
                    self._emit_event(repo_id, {
                        "type": "deploy_done", "status": "failed",
                        "message": f"{slabel}失败: {sub_record.message}",
                    })
                    return record

            self._finish_record(record, "success", "一键部署完成 ✅")
            self._emit_event(repo_id, {
                "type": "deploy_done", "status": "success", "message": "一键部署完成 ✅",
            })
        except Exception as e:
            self._finish_record(record, "failed", str(e))
            self._emit_event(repo_id, {
                "type": "deploy_done", "status": "failed", "message": str(e),
            })
        return record

    async def full_deploy_all(
        self,
        project_key: str,
        existing_record: DeployRecord = None,
        job_id: str = "",
    ) -> DeployRecord:
        """一键部署项目下所有仓库"""
        if project_key not in self.projects:
            raise ValueError(f"项目不存在: {project_key}")
        proj = self.projects[project_key]
        record = existing_record or self._add_record(project_key, "", proj.name, "full_deploy_all")
        if not existing_record:
            record.logs.append(f"🔄 一键部署全部 ({len(proj.repos)} 个仓库)...")

        for repo in proj.repos:
            if job_id and self._job_cancellation_requested(job_id):
                self._finish_record(record, "cancelled", "项目级部署任务已取消")
                return record
            record.logs.append(f"📦 开始部署仓库 [{repo.label}]...")
            r = await self.full_deploy_repo(project_key, repo.id, job_id=job_id)
            record.logs.extend(r.logs)
            if r.status == "cancelled":
                self._finish_record(record, "cancelled", f"[{repo.label}] 已取消")
                return record
            if r.status == "failed":
                self._finish_record(record, "failed", f"[{repo.label}] 失败: {r.message}")
                return record

        self._finish_record(record, "success", f"全部 {len(proj.repos)} 个仓库部署完成 ✅")
        return record

    # ── 状态查询 ──────────────────────────────────────────────────────────────
    def get_repo_status(self, repo: RepoConfig) -> Dict:
        target = self._repo_path(repo)
        proc = self.processes.get(repo.id)
        is_running = proc is not None and proc.poll() is None
        docker_info = self.docker_repos.get(repo.id)
        is_docker = False
        pid = proc.pid if is_running else None
        if docker_info:
            if docker_info.get("fallback_no_docker"):
                alive_services = [
                    svc for svc in docker_info.get("service_pids", [])
                    if self._pid_alive(svc.get("pid"))
                ]
                if alive_services:
                    is_docker = True
                    if pid is None:
                        pid = alive_services[0].get("pid")
                else:
                    self.docker_repos.pop(repo.id, None)
            else:
                is_docker = True
                if pid is None:
                    pid = docker_info.get("pid")
        port_open = self._check_port(repo.port) if repo.port else False

        if is_running or is_docker:
            status = "running"
        elif target.exists() and (target / ".git").exists():
            status = "cloned"
        else:
            status = "not_deployed"

        return {
            "id": repo.id, "label": repo.label, "repo_url": repo.repo_url,
            "tech_stack": repo.tech_stack, "local_dir": str(target),
            "exists": target.exists(), "status": status,
            "port": repo.port, "port_open": port_open, "pid": pid,
            "install_cmd": repo.install_cmd, "start_cmd": repo.start_cmd,
            "branch": repo.branch,
            "has_memory": repo.id in self.memory,
            "deploy_count": self.memory.get(repo.id, {}).get("deploy_count", 0),
        }

    def get_project_detail(self, key: str) -> Dict:
        if key not in self.projects:
            raise ValueError(f"项目不存在: {key}")
        proj = self.projects[key]
        repos_status = [self.get_repo_status(r) for r in proj.repos]
        return {
            "key": proj.key,
            "name": proj.name,
            "repos": repos_status,
            "has_token": bool(proj.git_token),
        }

    def get_all_projects(self) -> List[Dict]:
        return [self.get_project_detail(k) for k in self.projects]

    # ── 日志 ──────────────────────────────────────────────────────────────────
    def get_logs(self, repo_id: str, lines: int = 100) -> List[str]:
        if lines <= 0:
            return []
        log_file = DEPLOY_DIR / f"{repo_id}_output.log"
        if not log_file.exists():
            return ["暂无日志"]
        try:
            content = log_file.read_text(encoding="utf-8", errors="replace")
            all_lines = content.strip().split("\n")
            return all_lines[-lines:]
        except Exception as e:
            return [f"读取日志失败: {e}"]

    def get_deploy_history(self, limit: int = 30) -> List[Dict]:
        return [asdict(r) for r in self.history[-limit:]][::-1]

    @staticmethod
    def _check_port(port: int) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                return s.connect_ex(("127.0.0.1", port)) == 0
        except Exception:
            return False

    # ── AI 智能分析 ───────────────────────────────────────────────────────────
    async def ai_analyze_repo(self, project_key: str, repo_id: str) -> Dict:
        """调用 AI 分析仓库结构并返回配置推荐（注入部署记忆）"""
        proj, repo = self._find_repo(project_key, repo_id)
        target = self._repo_path(repo)

        if not target.exists():
            return {"error": "仓库尚未克隆，请先执行克隆操作", "source": "ai"}

        # ── 注入部署记忆 ──
        mem = self._load_memory(repo.id)
        env_state = self._get_repo_env_state(repo)
        memory_hint = ""
        if mem:
            parts = []
            if mem.get("build_strategy"):
                bs = mem["build_strategy"]
                if bs.get("excluded_modules"):
                    parts.append(f"历史构建经验: 需排除模块 {bs['excluded_modules']}")
                if bs.get("cmd"):
                    parts.append(f"上次成功的构建命令: {bs['cmd']}")
            if mem.get("ai_config"):
                ac = mem["ai_config"]
                if ac.get("pom_changes"):
                    parts.append(f"上次 pom 修改: {ac['pom_changes']}")
            if mem.get("start_config"):
                sc = mem["start_config"]
                parts.append(f"上次启动: {sc.get('success_count', 0)}/{sc.get('total_count', 0)} 微服务成功")
                if sc.get("docker_cmd"):
                    parts.append(f"上次稳定启动命令: {sc['docker_cmd']}")
            if mem.get("effective_env", {}).get("summary"):
                parts.append(f"上次生效环境: {mem['effective_env']['summary']}")
            if mem.get("deploy_count"):
                parts.append(f"累计成功部署 {mem['deploy_count']} 次")
            memory_hint = "\n".join(parts)
            logger.info(f"[Memory] 向 AI 注入 {repo.label} 的 {len(parts)} 条历史记忆")

        from services.ai_deploy_analyzer import analyze_project
        result = await analyze_project(
            target, label=repo.label, repo_url=repo.repo_url,
            memory_hint=memory_hint,
            current_env_text=env_state["effective_env_text"],
        )
        result = self._prefer_stable_ai_start_command(repo, result, mem)

        # 在结果中附带记忆信息供前端展示
        if mem:
            result["has_memory"] = True
            result["deploy_count"] = mem.get("deploy_count", 0)
            result["last_success"] = mem.get("last_success", "")

        result.update(env_state)

        return result

    def apply_ai_config(self, project_key: str, repo_id: str, config: Dict) -> Dict:
        """将 AI 推荐的配置应用到仓库（同时保存到记忆）"""
        proj, repo = self._find_repo(project_key, repo_id)

        if config.get("tech_stack"):
            repo.tech_stack = config["tech_stack"]
        if config.get("install_cmd"):
            repo.install_cmd = config["install_cmd"]
        if config.get("start_cmd"):
            repo.start_cmd = config["start_cmd"]
        if config.get("port"):
            repo.port = int(config["port"])
        if self._is_frontend_repo(repo):
            normalized_port = self._normalize_frontend_port(repo, repo.port)
            if normalized_port != repo.port:
                logger.info(f"[AI] 前端端口过低，自动改写: {repo.label} {repo.port} -> {normalized_port}")
                repo.port = normalized_port
            if repo.start_cmd:
                normalized_start_cmd = self._normalize_start_command(
                    repo,
                    repo.start_cmd,
                    repo.port,
                    DeployRecord(project_key=project_key, repo_id=repo.id, repo_label=repo.label, action="apply_ai_config"),
                )
                if normalized_start_cmd != repo.start_cmd:
                    logger.info(f"[AI] 前端启动命令已规范化: {repo.start_cmd} -> {normalized_start_cmd}")
                    repo.start_cmd = normalized_start_cmd
        if config.get("deploy_context"):
            existing_ctx = dict(repo.deploy_context or {})
            ctx = {**existing_ctx, **dict(config["deploy_context"] or {})}
            repo.deploy_context = ctx
            # 用户确认应用 pom 修改
            if ctx.get("apply_pom_changes") and ctx.get("suggested_changes"):
                target = self._repo_path(repo)
                if target.exists():
                    temp_record = DeployRecord()
                    self._apply_pom_changes(target, ctx["suggested_changes"], temp_record)
                    logger.info(f"[AI] pom 修改已应用: {temp_record.logs}")

            # ── Fix3: 将 deploy_context 中的 env_vars 写入 docker/.env ──
            if ctx.get("env_vars"):
                target = self._repo_path(repo)
                if target.exists():
                    overrides = self._parse_env_text(ctx["env_vars"])
                    if ctx.get("server_address"):
                        overrides["DEPLOY_SERVER"] = ctx["server_address"]
                    if ctx.get("db_connection"):
                        overrides["DATABASE_URL"] = ctx["db_connection"]
                    merged = self._merge_env_file(target, overrides)
                    logger.info(f"[AI] 环境变量已写入 {self._get_env_file_path(target, create=True)}: {list(merged.keys())}")

        # ── Fix1: 检测 POM 中已有 profile 排除，自动清理 install_cmd 中的 -pl ! ──
        if repo.install_cmd and "-pl " in repo.install_cmd and "!" in repo.install_cmd:
            target = self._repo_path(repo)
            has_pom_profile = False
            for pom_sub in ["sample-modules/pom.xml", "sample-api/pom.xml"]:
                pom_path = target / pom_sub
                if pom_path.exists():
                    pom_content = pom_path.read_text(encoding="utf-8", errors="replace")
                    if "<profiles>" in pom_content:
                        has_pom_profile = True
                        break
            if has_pom_profile:
                # POM 已通过 profile 排除模块，-pl ! 会冲突，自动移除
                cleaned = re.sub(r'\s+-pl\s+[^\s]+', '', repo.install_cmd).strip()
                logger.info(f"[AI] POM 已有 profile 排除，清理 install_cmd: {repo.install_cmd} → {cleaned}")
                repo.install_cmd = cleaned

        # ── 保存 AI 配置到记忆 ──
        self._update_memory(repo.id, "ai_config", {
            "tech_stack": config.get("tech_stack"),
            "install_cmd": repo.install_cmd,  # 使用清理后的命令
            "start_cmd": repo.start_cmd,
            "port": repo.port,
            "pom_changes": config.get("deploy_context", {}).get("suggested_changes"),
            "timestamp": datetime.now().isoformat()
        })
        logger.info(f"[Memory] AI 配置已保存到记忆: {repo.label}")

        self._save_projects()
        logger.info(f"[AI] 配置已应用: {repo.label} → {repo.tech_stack}")
        return self.get_repo_status(repo)


# ── 单例 ──────────────────────────────────────────────────────────────────────
_service_instance: Optional[DeployService] = None


def get_deploy_service() -> DeployService:
    global _service_instance
    if _service_instance is None:
        _service_instance = DeployService()
    return _service_instance
