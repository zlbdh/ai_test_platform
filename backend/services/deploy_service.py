# -*- coding: utf-8 -*-
"""
Automated deployment service for projects under test

Data model: Project -> Repos (two levels)
A project can contain multiple repositories (frontend, backend, microservices, etc.) managed together.

Note: Data classes and utility functions have moved to deploy_models.py.
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


# -- Deployment service --------------------------------------------------
class DeployService:
    """Deployment management service for projects under test"""

    SENSITIVE_ENV_KEYWORDS = ("PASSWORD", "SECRET", "TOKEN", "API_KEY", "ACCESS_KEY")

    def __init__(self):
        self.projects: Dict[str, ProjectConfig] = {}
        self.processes: Dict[str, subprocess.Popen] = {}   # key = repo.id
        self.docker_repos: Dict[str, Dict] = {}              # key = repo.id, val = {cwd, compose_file, cmd}
        self.history: List[DeployRecord] = []
        self.jobs: Dict[str, DeployJob] = {}
        self.approvals: Dict[str, DeployApproval] = {}
        self.memory: Dict[str, Dict] = {}                    # key = repo.id, value = deployment memory
        self._deploy_event_bus: Dict[str, asyncio.Queue] = {}  # repo_id -> Queue
        self._active_job_tasks: Dict[str, asyncio.Task] = {}
        self._load_projects()
        self._load_history()
        self._load_jobs()
        self._load_approvals()
        self._mark_incomplete_jobs_orphaned()
        self._load_state()
        self._load_all_memory()

    # -- Persistence ---------------------------------------------------------
    def _ensure_job_runtime(self):
        if not hasattr(self, "jobs") or self.jobs is None:
            self.jobs = {}
        if not hasattr(self, "approvals") or self.approvals is None:
            self.approvals = {}
        if not hasattr(self, "_active_job_tasks") or self._active_job_tasks is None:
            self._active_job_tasks = {}

    def _load_state(self):
        """Load global state (legacy compatibility)"""
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                # Legacy compatibility: migrate the global token to the first project
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
            logger.warning(f"Failed to save state: {e}")

    def _load_projects(self):
        if PROJECTS_FILE.exists():
            try:
                raw = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
                for item in raw:
                    repos = [RepoConfig(**r) for r in item.pop("repos", [])]
                    cfg = ProjectConfig(**item, repos=repos)
                    self.projects[cfg.key] = cfg
            except Exception as e:
                logger.warning(f"Failed to load projects: {e}")
                self.projects = {}

    def _save_projects(self):
        try:
            data = [asdict(p) for p in self.projects.values()]
            PROJECTS_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Failed to save projects: {e}")

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
            logger.warning(f"Failed to save history: {e}")

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
                logger.warning(f"Failed to load deployment jobs: {exc}")
                self.jobs = {}

    def _save_jobs(self):
        self._ensure_job_runtime()
        try:
            JOBS_FILE.write_text(
                json.dumps([asdict(job) for job in list(self.jobs.values())[-200:]], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Failed to save deployment jobs: {e}")

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
                logger.warning(f"Failed to load deployment approvals: {exc}")
                self.approvals = {}

    def _save_approvals(self):
        self._ensure_job_runtime()
        try:
            APPROVALS_FILE.write_text(
                json.dumps([asdict(item) for item in list(self.approvals.values())[-200:]], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Failed to save deployment approvals: {e}")

    def _mark_incomplete_jobs_orphaned(self):
        self._ensure_job_runtime()
        changed = False
        now = datetime.now().isoformat()
        for job in self.jobs.values():
            if job.status in {"queued", "running"}:
                job.status = "orphaned"
                reason = "The task did not finish before the service restarted and was marked orphaned"
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
                raise ValueError(f"Project not found: {project_key}")
            repo_label = self.projects[project_key].name
            repo_id = ""
        else:
            raise ValueError("Unsupported approval action")

        approval = DeployApproval(
            action=action,
            project_key=project_key,
            repo_id=repo_id,
            repo_label=repo_label,
            branch=branch,
            request_comment=request_comment,
            requested_by=requested_by,
            requested_by_name=requested_by_name or requested_by,
            message="Awaiting approval",
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
            raise ValueError("Approval request not found")
        if approval.status != "pending":
            raise ValueError("Approval request already processed")

        approval.reviewed_by = reviewed_by
        approval.reviewed_by_name = reviewed_by_name or reviewed_by
        approval.reviewed_at = datetime.now().isoformat()
        approval.review_comment = comment

        if not approved:
            approval.status = "rejected"
            approval.message = "Approval rejected"
            self._save_approvals()
            return self._approval_to_payload(approval)

        if approval.action == "full_deploy":
            job = self.schedule_full_deploy(approval.project_key, approval.repo_id, approval.branch)
        elif approval.action == "full_deploy_all":
            job = self.schedule_full_deploy_all(approval.project_key)
        else:
            raise ValueError("Unsupported approval action")

        approval.status = "approved"
        approval.job_id = job.id
        approval.record_id = job.record_id
        approval.message = "Approved; deployment job created"
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
                    step.message = "Task canceled without execution"
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
            raise ValueError("Job not found")
        if job.status in {"success", "failed", "cancelled", "orphaned"}:
            raise ValueError("The job has finished and cannot be canceled")
        if job.status == "cancel_requested":
            payload = self.get_job_detail(job_id)
            if payload is None:
                raise ValueError("Job not found")
            return payload

        job.status = "cancel_requested"
        job.message = "Cancellation request received"
        self._save_jobs()

        record = self._get_history_record(job.record_id)
        if record and record.status == "running":
            record.logs.append("⛔ Cancellation requested; stop further execution after the current step completes")
            self._save_history()

        task = self._active_job_tasks.get(job_id)
        if task is None or task.done():
            payload = self._finalize_job_cancellation(job_id, "Task canceled")
            if payload is None:
                raise ValueError("Job not found")
            return payload

        payload = self.get_job_detail(job_id)
        if payload is None:
            raise ValueError("Job not found")
        return payload

    def schedule_full_deploy(self, project_key: str, repo_id: str, branch: str = "") -> DeployJob:
        """Schedule a one-click deployment in the background and return job details immediately."""
        self._ensure_job_runtime()
        _, repo = self._find_repo(project_key, repo_id)

        record = self._add_record(project_key, repo_id, repo.label, "full_deploy")
        record.logs.append(f"🔄 One-click deployment [{repo.label}]...")
        record.steps = [DeployStep(name="clone"), DeployStep(name="install"), DeployStep(name="start")]
        self._save_history()

        job = self._create_job(
            action="full_deploy",
            project_key=project_key,
            repo_id=repo_id,
            repo_label=repo.label,
            record_id=record.id,
            branch=branch,
            message="Background deployment job created",
        )

        async def _runner():
            if self._job_cancellation_requested(job.id):
                self._finalize_job_cancellation(job.id, "Task canceled before startup")
                return
            self._update_job(job.id, status="running", message="Background deployment running", started=True)
            try:
                final_record = await self.full_deploy_repo(project_key, repo_id, branch, record, job_id=job.id)
            except Exception as exc:
                logger.exception("[DeployService] Background deployment failed: %s", exc)
                self._update_job(job.id, status="failed", message=str(exc), started=True, finished=True)
                return

            if final_record.status == "cancelled":
                self._update_job(job.id, status="cancelled", message=final_record.message or "Task canceled", started=True, finished=True)
                return
            final_status = "success" if final_record.status == "success" else "failed"
            final_message = final_record.message or ("One-click deployment completed ✅" if final_status == "success" else "Deployment failed")
            self._update_job(job.id, status=final_status, message=final_message, started=True, finished=True)

        task = asyncio.create_task(_runner(), name=f"deploy-job-{job.id}")
        self._active_job_tasks[job.id] = task

        def _cleanup(_task: asyncio.Task):
            self._active_job_tasks.pop(job.id, None)

        task.add_done_callback(_cleanup)
        return job

    def schedule_full_deploy_all(self, project_key: str) -> DeployJob:
        """Schedule a project-wide one-click deployment in the background and return job details immediately."""
        self._ensure_job_runtime()
        if project_key not in self.projects:
            raise ValueError(f"Project not found: {project_key}")

        project = self.projects[project_key]
        record = self._add_record(project_key, "", project.name, "full_deploy_all")
        record.logs.append(f"🔄 Deploy all ({len(project.repos)} repositories)...")
        self._save_history()

        job = self._create_job(
            action="full_deploy_all",
            project_key=project_key,
            repo_id="",
            repo_label=project.name,
            record_id=record.id,
            message="Project-wide background deployment job created",
        )

        async def _runner():
            if self._job_cancellation_requested(job.id):
                self._finalize_job_cancellation(job.id, "Task canceled before startup")
                return
            self._update_job(job.id, status="running", message="Project-wide background deployment running", started=True)
            try:
                final_record = await self.full_deploy_all(project_key, existing_record=record, job_id=job.id)
            except Exception as exc:
                logger.exception("[DeployService] Project-wide background deployment failed: %s", exc)
                self._update_job(job.id, status="failed", message=str(exc), started=True, finished=True)
                return

            if final_record.status == "cancelled":
                self._update_job(job.id, status="cancelled", message=final_record.message or "Task canceled", started=True, finished=True)
                return
            final_status = "success" if final_record.status == "success" else "failed"
            final_message = final_record.message or (
                f"All {len(project.repos)} repositories deployed ✅"
                if final_status == "success"
                else "Project-wide deployment failed"
            )
            self._update_job(job.id, status=final_status, message=final_message, started=True, finished=True)

        task = asyncio.create_task(_runner(), name=f"deploy-job-{job.id}")
        self._active_job_tasks[job.id] = task

        def _cleanup(_task: asyncio.Task):
            self._active_job_tasks.pop(job.id, None)

        task.add_done_callback(_cleanup)
        return job

    # -- Deployment memory ---------------------------------------------------
    def _memory_file(self, repo_id: str) -> Path:
        return MEMORY_DIR / f"{repo_id}.json"

    def _load_all_memory(self):
        """Load deployment memory for every repository at startup"""
        for f in MEMORY_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                self.memory[f.stem] = data
            except Exception:
                pass
        if self.memory:
            logger.info(f"[Memory] Loaded deployment memory for {len(self.memory)} repositories")

    def _load_memory(self, repo_id: str) -> Dict:
        """Load memory for a repository"""
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
        """Save repository deployment memory to disk"""
        self.memory[repo_id] = data
        try:
            self._memory_file(repo_id).write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"[Memory] Failed to save memory ({repo_id}): {e}")

    def _update_memory(self, repo_id: str, key: str, value, record: DeployRecord = None):
        """Update a repository memory field"""
        mem = self._load_memory(repo_id)
        mem[key] = value
        mem["last_updated"] = datetime.now().isoformat()
        # A successful build or startup counts as a valid deployment
        should_inc = (
            key == "last_success"
            or (key == "build_strategy" and isinstance(value, dict) and value.get("success"))
        )
        mem["deploy_count"] = mem.get("deploy_count", 0) + (1 if should_inc else 0)
        self._save_memory(repo_id, mem)
        if record:
            record.logs.append(f"🧠 Memory updated: {key}")

    @staticmethod
    def _parse_env_text(env_text: str) -> Dict[str, str]:
        """Parse KEY=VALUE text into an environment-variable dictionary."""
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
        """Convert an environment-variable dictionary back to KEY=VALUE text."""
        if not env_vars:
            return ""
        return "\n".join(f"{key}={value}" for key, value in env_vars.items())

    @classmethod
    def _mask_env_vars(cls, env_vars: Dict[str, str]) -> Dict[str, str]:
        """Mask environment variables to avoid exposing sensitive values in the UI or memory."""
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
        """Summarize key environment variables for memory and prompts."""
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
        """Locate the environment file actually used by the repository, preferring docker/.env."""
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
        """Convert an environment file path into a frontend-friendly source label."""
        try:
            return str(env_file.relative_to(project_dir)).replace("\\", "/")
        except ValueError:
            return env_file.name

    def _read_env_file(self, env_file: Path) -> Dict[str, str]:
        """Read an environment file."""
        if not env_file.exists():
            return {}
        return self._parse_env_text(env_file.read_text(encoding="utf-8"))

    def _merge_env_file(self, project_dir: Path, overrides: Dict[str, str], record: Optional[DeployRecord] = None) -> Dict[str, str]:
        """Merge environment-variable updates into the active .env file, preserving unchanged entries."""
        env_file = self._get_env_file_path(project_dir, create=True)
        env_file.parent.mkdir(parents=True, exist_ok=True)
        merged = self._read_env_file(env_file)
        merged.update(overrides)
        with open(env_file, "w", encoding="utf-8") as handle:
            for key, value in merged.items():
                handle.write(f"{key}={value}\n")
        if record and overrides:
            changed = ", ".join(overrides.keys())
            record.logs.append(f"📝 Environment configuration updated incrementally ({self._env_source_label(project_dir, env_file)}): {changed}")
        return merged

    def _get_repo_env_state(self, repo: RepoConfig) -> Dict[str, object]:
        """Summarize the active environment, saved overrides, and frontend display notes."""
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
            effective_env_source = "Saved deployment overrides"

        masked_effective = self._mask_env_vars(effective_env_vars)
        masked_saved = self._mask_env_vars(saved_env_vars)
        return {
            "saved_context": saved_context,
            "saved_env_vars": masked_saved,
            "saved_env_text": self._dump_env_text(saved_env_vars),
            "effective_env_vars": masked_effective,
            "effective_env_text": self._dump_env_text(effective_env_vars),
            "effective_env_source": effective_env_source,
            "env_apply_behavior": "When no supplemental information is provided, retain the active values. KEY=VALUE entries in supplemental information are merged into the existing .env and remain effective for later deployments.",
        }

    def _remember_effective_env(self, repo: RepoConfig, project_dir: Path, record: Optional[DeployRecord] = None):
        """After a successful deployment, record the active environment summary for the next AI analysis."""
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
        """Protect stable AI recommendations by preferring a previously verified startup command."""
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
        suffix = "Kept the currently verified Docker startup command to prevent AI recommendations from overriding a stable deployment flow."
        result["notes"] = f"{result.get('notes', '').strip()} {suffix}".strip()
        result["stability_guard_applied"] = True
        logger.info(f"[AI] Stable command protection enabled: {repo.label} -> {stable_start}")
        return result

    def _auto_start_docker(self, record: DeployRecord) -> bool:
        """Start Docker Desktop automatically and wait up to 60 seconds for the daemon"""
        import time as _time

        # Locate the Docker Desktop executable
        docker_desktop_path = None
        if os.name == "nt":
            # Windows: common installation paths
            candidates = [
                Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Docker" / "Docker" / "Docker Desktop.exe",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Docker" / "Docker Desktop.exe",
            ]
            for c in candidates:
                if c.exists():
                    docker_desktop_path = str(c)
                    break
            # If no fixed path is found, try the where command
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
            record.logs.append("⚠️ Docker Desktop installation not found; automatic startup is unavailable")
            return False

        # Start Docker Desktop
        try:
            record.logs.append(f"🐳 Starting Docker Desktop...")
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
            record.logs.append(f"⚠️ Failed to start Docker Desktop: {e}")
            return False

        # Wait up to 60 seconds for the Docker daemon
        max_wait = 60
        interval = 3
        waited = 0
        record.logs.append(f"⏳ Waiting for the Docker daemon (up to {max_wait}s)...")
        while waited < max_wait:
            _time.sleep(interval)
            waited += interval
            try:
                r = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=10)
                if r.returncode == 0:
                    record.logs.append(f"✅ Docker Desktop is ready (waited {waited}s)")
                    return True
            except Exception:
                pass
            if waited % 15 == 0:
                record.logs.append(f"⏳ Still waiting for Docker to start... ({waited}s/{max_wait}s)")

        record.logs.append(f"⚠️ Docker Desktop startup timed out ({max_wait}s); check it manually")
        return False

    def _kill_project_java_processes(self, project_dir: Path, record: DeployRecord):
        """Clean up remaining Java processes for this project before building to release locked JAR files"""
        killed = 0
        # Match the project directory name; it is more reliable than the full path
        dir_name = project_dir.name.lower()
        jar_markers = {
            dir_name,
            *(jar.stem.lower() for jar in self._list_local_microservice_jars(project_dir)),
            *(jar.name.lower() for jar in self._list_local_microservice_jars(project_dir)),
        }

        # 1) First terminate microservice PIDs recorded in docker_repos
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

        # 2) Use PowerShell/ps to find Java processes whose command lines contain the project directory name
        try:
            if os.name == "nt":
                # PowerShell Get-CimInstance is more reliable than WMIC
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
                            logger.info(f"[Process cleanup] Terminate Java PID {pid_str}")
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
            logger.debug(f"[Process cleanup] Scan error: {e}")

        if killed:
            record.logs.append(f"🧹 Pre-build cleanup: terminated {killed} remaining Java processes")
            logger.info(f"[Process cleanup] Project {project_dir.name}: terminated {killed} Java processes")
            time.sleep(2)  # Wait for file handles to be released
        else:
            record.logs.append("🔍 Pre-build check: no remaining Java processes")

    @staticmethod
    def _is_frontend_repo(repo: RepoConfig) -> bool:
        label = repo.label or ""
        tech_stack = (repo.tech_stack or "").lower()
        return (label == "前端" or label.lower() == "frontend") or any(keyword in tech_stack for keyword in ("vite", "vue", "react", "next"))

    def _kill_project_frontend_processes(self, project_dir: Path, record: DeployRecord) -> int:
        """Before startup or shutdown, clean up this repository's remaining Vite/Node frontend processes so old instances do not occupy ports."""
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
            logger.debug(f"[Frontend process cleanup] Scan error: {e}")

        if killed:
            record.logs.append(f"🧹 Pre-run frontend cleanup: terminated {killed} remaining Node/Vite processes")
            time.sleep(1)
        else:
            record.logs.append("🔍 Pre-run frontend check: no remaining Node/Vite processes")
        return killed

    # -- Event stream --------------------------------------------------------
    def _emit_event(self, repo_id: str, event: dict):
        """Push a deployment event to the event bus"""
        q = self._deploy_event_bus.get(repo_id)
        if q:
            try: q.put_nowait(event)
            except asyncio.QueueFull: pass

    async def get_event_stream(self, repo_id: str):
        """SSE consumer: yield events until deployment completes"""
        # Use the preregistered queue, or create one if none exists
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
            yield {"type": "deploy_done", "status": "timeout", "message": "Event stream timed out"}
        finally:
            self._deploy_event_bus.pop(repo_id, None)

    def _repo_path(self, repo: RepoConfig) -> Path:
        return DEPLOY_DIR / repo.local_dir

    def _find_repo(self, project_key: str, repo_id: str) -> tuple:
        """Find a project and repository; return (ProjectConfig, RepoConfig)"""
        if project_key not in self.projects:
            raise ValueError(f"Project not found: {project_key}")
        proj = self.projects[project_key]
        repo = next((r for r in proj.repos if r.id == repo_id), None)
        if not repo:
            raise ValueError(f"Repository not found: {repo_id}")
        return proj, repo

    # ── Git Token ─────────────────────────────────────────────────────────────
    def set_project_token(self, project_key: str, token: str):
        """Set the project-level Git token"""
        if project_key not in self.projects:
            raise ValueError(f"Project not found: {project_key}")
        self.projects[project_key].git_token = token
        self._save_projects()

    def _auth_url(self, url: str, token: str = "") -> str:
        if token and "://" in url:
            parts = url.split("://", 1)
            return f"{parts[0]}://oauth2:{token}@{parts[1]}"
        return url

    # -- Project CRUD --------------------------------------------------------
    def add_project(self, name: str, repos: List[dict]) -> ProjectConfig:
        """Add a project with multiple repositories"""
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
                label=rd.get("label", "Default"),
                repo_url=rd["repo_url"],
                local_dir=local_dir,
                tech_stack=rd.get("tech_stack", ""),
                install_cmd=rd.get("install_cmd", ""),
                start_cmd=rd.get("start_cmd", ""),
                port=rd.get("port", 0),
                branch=rd.get("branch", "master"),
                deploy_context=rd.get("deploy_context", {}),
            ))

        # Get the token from arguments or the legacy global token
        token = ""
        if repos and repos[0].get("git_token"):
            token = repos[0].get("git_token", "")
        elif hasattr(self, '_legacy_token') and self._legacy_token:
            token = self._legacy_token
            self._legacy_token = ""  # Clear after migration

        cfg = ProjectConfig(key=key, name=name, repos=repo_configs, git_token=token)
        self.projects[key] = cfg
        self._save_projects()
        logger.info(f"Project added: {name} ({len(repo_configs)} repositories)")
        return cfg

    def update_project(self, key: str, name: str = None, repos: List[dict] = None) -> ProjectConfig:
        """Update a project, including its name and repository list"""
        if key not in self.projects:
            raise ValueError(f"Project not found: {key}")
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
                    label=rd.get("label", "Default"),
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
            raise ValueError(f"Project not found: {key}")
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

    # -- Per-repository deployment operations --------------------------------
    async def clone_repo(self, project_key: str, repo_id: str, branch: str = "") -> DeployRecord:
        proj, repo = self._find_repo(project_key, repo_id)
        record = self._add_record(project_key, repo_id, repo.label, "clone")
        target = self._repo_path(repo)
        use_branch = branch or repo.branch

        try:
            if target.exists() and (target / ".git").exists():
                record.logs.append(f"📂 Already exists; running git pull ({use_branch})")
                # Use synchronous subprocess.run to avoid Windows asyncio compatibility issues
                r1 = subprocess.run(
                    ["git", "checkout", use_branch], cwd=str(target),
                    capture_output=True, text=True, timeout=30,
                )
                if r1.stdout.strip():
                    record.logs.append(r1.stdout.strip())
                if r1.stderr.strip():
                    record.logs.append(r1.stderr.strip())

                # Automatically stash local changes, such as AI-edited pom.xml, to avoid pull conflicts
                stash_result = subprocess.run(
                    ["git", "stash", "--include-untracked"], cwd=str(target),
                    capture_output=True, text=True, timeout=30,
                )
                has_stash = "No local changes" not in (stash_result.stdout or "")
                if has_stash:
                    record.logs.append(f"📦 Local changes stashed (git stash)")

                r2 = subprocess.run(
                    ["git", "pull", "origin", use_branch], cwd=str(target),
                    capture_output=True, text=True, timeout=120,
                )
                if r2.stdout.strip():
                    record.logs.append(r2.stdout.strip())
                if r2.stderr.strip():
                    record.logs.append(r2.stderr.strip())

                if r2.returncode != 0:
                    # Restore the stash if pull fails
                    if has_stash:
                        subprocess.run(["git", "stash", "pop"], cwd=str(target),
                                       capture_output=True, text=True, timeout=30)
                    self._finish_record(record, "failed", f"Pull failed (exit={r2.returncode})")
                    return record

                # After a successful pull, try to restore local changes
                if has_stash:
                    pop_result = subprocess.run(
                        ["git", "stash", "pop"], cwd=str(target),
                        capture_output=True, text=True, timeout=30,
                    )
                    if pop_result.returncode == 0:
                        record.logs.append("📦 Local changes restored")
                    else:
                        record.logs.append("⚠️ Conflicts occurred while restoring local changes; old changes were discarded")
                        subprocess.run(["git", "stash", "drop"], cwd=str(target),
                                       capture_output=True, text=True, timeout=30)
                        subprocess.run(["git", "checkout", "."], cwd=str(target),
                                       capture_output=True, text=True, timeout=30)

                self._finish_record(record, "success", f"Pulled ({use_branch})")
            else:
                auth_url = self._auth_url(repo.repo_url, proj.git_token)
                record.logs.append(f"🔄 Cloning {repo.repo_url}")
                # Use synchronous subprocess.run to avoid Windows asyncio compatibility issues
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
                        record.logs.append(f"🔍 Detected: {repo.tech_stack}")
                    self._finish_record(record, "success", "Clone completed")
                else:
                    self._finish_record(record, "failed", f"Clone failed (exit={r.returncode})")
        except subprocess.TimeoutExpired:
            self._finish_record(record, "failed", "Clone timed out (>300s)")
        except Exception as e:
            self._finish_record(record, "failed", str(e))
        return record

    # -- Self-healing helpers ------------------------------------------------
    @staticmethod
    def _find_free_port(preferred: int, range_size: int = 100) -> int:
        """Search for an available port starting at preferred"""
        for port in range(preferred, preferred + range_size):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("0.0.0.0", port))
                    return port
            except OSError:
                continue
        return 0  # Not found

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
        """Low frontend ports cause EACCES locally; replace them with safe ports."""
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
                f"🔧 Self-healing: low frontend port {port or 'Not configured'} is unsuitable for the local environment; changed to {safe_port}"
            )
        return safe_port

    def _get_deploy_env(self, repo: 'RepoConfig') -> dict:
        """Build the deployment environment: OS environment plus deploy_context.env_vars supplied by the user"""
        env = dict(os.environ)
        ctx = repo.deploy_context or {}
        # Parse user-supplied KEY=VALUE environment variables
        env.update(self._parse_env_text(ctx.get("env_vars", "")))
        # Database connection
        if ctx.get("db_connection"):
            env["DATABASE_URL"] = ctx["db_connection"]
        return env

    def _write_env_file(self, target: Path, repo: 'RepoConfig', record: DeployRecord):
        """Merge deploy_context into the project environment file, preserving unchanged entries."""
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
            record.logs.append(f"⚠️ Failed to write {self._env_source_label(target, env_file)}: {e}")

    def _apply_pom_changes(self, target: Path, suggested_changes: list, record: DeployRecord):
        """After user confirmation, apply Maven profile changes to pom.xml without modifying unrelated code"""
        import re as _re
        for change in suggested_changes:
            if change.get("type") != "maven_profile":
                continue
            pom_file = target / change["file"]
            if not pom_file.exists():
                record.logs.append(f"⚠️ File not found: {change['file']}")
                continue
            try:
                content = pom_file.read_text(encoding="utf-8")
                mod = change["module"]
                profile_id = change.get("profile_id", "aigc")

                # Check whether the profile already exists
                if f'<id>{profile_id}</id>' in content:
                    record.logs.append(f"ℹ️ {change['file']} Profile already exists: {profile_id}; skipping")
                    continue

                # Replace <module>mod</module> with a comment
                pattern = f'(\\s*)<module>{_re.escape(mod)}</module>'
                match = _re.search(pattern, content)
                if not match:
                    record.logs.append(f"ℹ️ {change['file']} does not contain {mod}; skipping")
                    continue

                indent = match.group(1)
                # Replace with a comment
                content = _re.sub(
                    pattern,
                    f'{indent}<!-- {mod} moved to a profile; excluded from packaging by default -->',
                    content,
                )

                # Insert a <profiles> section after </modules>
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
                record.logs.append(f"✅ Applied: {change['file']} → {mod} moved to profile '{profile_id}'")
            except Exception as e:
                record.logs.append(f"⚠️ Failed to modify {change['file']}: {e}")


    def _run_install_cmd(self, cmd: str, cwd: str, record: DeployRecord, env: dict = None) -> int:
        """Execute the install command and record logs; return the exit code"""
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
            self._finish_record(record, "failed", "Clone the repository first")
            return record
        if not repo.install_cmd:
            self._finish_record(record, "failed", "No install command configured")
            return record

        # -- Preflight: clean up remaining Java processes before a Maven build --
        if "mvn" in (repo.install_cmd or ""):
            self._kill_project_java_processes(target, record)

        # -- Preflight: verify build tools and attempt self-healing --
        cmd_first = repo.install_cmd.split()[0]
        cmd_base = cmd_first.replace("./", "").replace(".\\" , "")
        wrapper_path = target / cmd_first.replace("./", "").replace(".\\" , "")

        if not wrapper_path.exists() and not cmd_available(cmd_base):
            # -- Self-healing: Maven/Gradle missing -> check Docker configuration --
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
                    # Docker available -> switch to Docker deployment
                    record.logs.append(f"🔧 Self-healing: {cmd_base} is not installed; Docker configuration detected -> skip the local build")
                    dc_dir = str(docker_compose.parent.relative_to(target)).replace("\\", "/")
                    if dc_dir and dc_dir != ".":
                        new_start = f"cd {dc_dir} && docker-compose -f {docker_compose.name} up -d"
                    else:
                        new_start = f"docker-compose -f {docker_compose.name} up -d"
                    repo.install_cmd = "echo [Self-healing] Skip the local build and deploy with Docker"
                    repo.start_cmd = new_start
                    self._save_projects()
                    record.logs.append(f"🔧 Self-healing: startup command changed to: {new_start}")
                    self._finish_record(record, "success", "Self-healing: skipped the local build (using Docker)")
                    return record
                else:
                    # Neither tool is available -> present both options clearly
                    tool_name = "Maven" if "mvn" in cmd_base else "Gradle"
                    hints = [f"❌ {tool_name} and Docker are both missing; automated deployment is unavailable"]
                    hints.append(f"  Option 1: Install {tool_name} → https://maven.apache.org/download.cgi" if "mvn" in cmd_base else f"  Option 1: Install {tool_name} → https://gradle.org/install/")
                    hints.append("  Option 2: Install Docker Desktop -> https://www.docker.com/products/docker-desktop/")
                    hints.append("  Install either tool and deploy again")
                    for h in hints:
                        record.logs.append(h)
                    self._finish_record(record, "failed", f"{tool_name} and Docker are both missing; install either tool and try again")
                    return record
            else:
                hint_map = {
                    "npm": "npm is not installed. Install Node.js: https://nodejs.org/",
                    "pip": "pip is not installed. Check your Python environment configuration",
                }
                hint = hint_map.get(cmd_base, f"Command '{cmd_base}' not found")
                record.logs.append(f"❌ Preflight failed: {hint}")
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
                self._finish_record(record, "success", "Installation completed")
            else:
                # -- Self-healing: attempt repairs after installation fails --
                log_text = "\n".join(record.logs[-30:])

                # Self-healing 1: npm install fails -> retry with the Taobao mirror
                if "npm" in repo.install_cmd and "registry" not in repo.install_cmd:
                    record.logs.append("🔧 Self-healing: npm install failed; retrying with the Taobao mirror...")
                    mirror_cmd = f"{repo.install_cmd} --registry=https://registry.npmmirror.com"
                    rc2 = self._run_install_cmd(mirror_cmd, str(target), record, env=deploy_env)
                    if rc2 == 0:
                        self._finish_record(record, "success", "Self-healing: installation succeeded with the Taobao mirror")
                    else:
                        self._finish_record(record, "failed", f"Installation failed (original registry and mirror both failed, exit={rc2})")

                # Self-healing 2: Maven build fails -> multilevel healing strategy
                elif "mvn" in repo.install_cmd:
                    healed = False
                    current_cmd = repo.install_cmd

                    # Strategy A: test compilation fails -> add -Dmaven.test.skip=true
                    if ("testCompile" in log_text or "test-compile" in log_text) and "-Dmaven.test.skip=true" not in current_cmd:
                        record.logs.append("🔧 Self-healing: Maven test compilation failed; retrying with -Dmaven.test.skip=true...")
                        current_cmd = current_cmd.replace("-DskipTests", "").strip() + " -Dmaven.test.skip=true"
                        rc2 = self._run_install_cmd(current_cmd, str(target), record, env=deploy_env)
                        if rc2 == 0:
                            repo.install_cmd = current_cmd
                            self._save_projects()
                            self._finish_record(record, "success", "Self-healing: build succeeded after skipping test compilation")
                            healed = True
                        else:
                            log_text = "\n".join(record.logs[-30:])

                    # Strategy B: module compilation fails -> exclude with -pl without modifying source
                    if not healed and ("FAILURE" in log_text or "BUILD FAILURE" in log_text or "Compilation failure" in log_text or "Could not find" in log_text):
                        excluded_modules = set()

                        # -- Preflight: detect modules already excluded by a POM profile to avoid -pl ! conflicts --
                        profile_excluded = set()
                        for pom_sub in ["sample-modules/pom.xml", "sample-api/pom.xml"]:
                            pom_path = target / pom_sub
                            if pom_path.exists():
                                pom_content = pom_path.read_text(encoding="utf-8", errors="replace")
                                if "<profiles>" in pom_content:
                                    # Extract <module> names from <profiles>
                                    profiles_section = pom_content.split("<profiles>", 1)[-1].split("</profiles>", 1)[0]
                                    for m in re.findall(r'<module>([^<]+)</module>', profiles_section):
                                        profile_excluded.add(m)
                        if profile_excluded:
                            record.logs.append(f"📋 POM profile already excludes: {', '.join(profile_excluded)}")

                        # Do not exclude the aggregator parent module
                        parent_modules = {"sample-modules", "sample-api", "sample-common", "sample-auth",
                                          "sample-gateway", "sample-visual", "sample-base", "sample-ui"}
                        for _round in range(3):  # Exclude at most 3 modules
                            failed_module = None
                            recent_logs = record.logs[-80:]

                            # First choice: [ERROR] on project xxx / Could not find ... reactor
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

                            # Second choice: module names in Compilation failure paths
                            if not failed_module:
                                for log_line in recent_logs:
                                    if "Compilation failure" in log_line or "[ERROR]" in log_line:
                                        match = re.search(r'[\\/](sample-\w+)[\\/]', log_line)
                                        if match:
                                            mod = match.group(1)
                                            if mod not in excluded_modules and mod not in parent_modules and mod not in profile_excluded:
                                                failed_module = mod
                                                break

                            # Last choice: FAILURE rows in Reactor Summary
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
                                break  # No newly failing modules

                            excluded_modules.add(failed_module)
                            # Also exclude the corresponding API module
                            api_mod = failed_module.replace("sample-", "sample-api-").replace("ruyi-", "sample-api-")
                            excluded_modules.add(api_mod)
                            # Build comma-separated -pl exclusion arguments
                            pl_excludes = ",".join([f"!{m}" for m in excluded_modules])
                            # Quote ! in PowerShell
                            exclude_cmd = f'{current_cmd} -pl "{pl_excludes}" --fail-at-end'
                            record.logs.append(f"🔧 Self-healing [round {_round+1}]: exclude {failed_module} + {api_mod} (command-line -pl; source unchanged)")
                            rc2 = self._run_install_cmd(exclude_cmd, str(target), record, env=deploy_env)
                            if rc2 == 0:
                                self._update_memory(repo.id, "build_strategy", {
                                    "cmd": exclude_cmd, "success": True,
                                    "excluded_modules": list(excluded_modules),
                                    "self_healed": True,
                                    "timestamp": datetime.now().isoformat()
                                }, record)
                                self._finish_record(record, "success", f"Self-healing: excluded {', '.join(excluded_modules)} and the build succeeded")
                                healed = True
                                break
                            else:
                                log_text = "\n".join(record.logs[-30:])
                                if _round == 2:
                                    self._finish_record(record, "failed", f"Maven build failed (excluded {', '.join(excluded_modules)}; still failing)")
                                    healed = True

                    if not healed:
                        self._finish_record(record, "failed", f"Maven build failed (exit={rc})")
        except subprocess.TimeoutExpired:
            self._finish_record(record, "failed", "Installation timed out (>600s)")
        except Exception as e:
            self._finish_record(record, "failed", str(e))
        return record

    async def start_repo(self, project_key: str, repo_id: str) -> DeployRecord:
        proj, repo = self._find_repo(project_key, repo_id)
        record = self._add_record(project_key, repo_id, repo.label, "start")
        target = self._repo_path(repo)

        if not target.exists():
            self._finish_record(record, "failed", "Clone the repository first")
            return record
        if not repo.start_cmd:
            self._finish_record(record, "failed", "No startup command configured")
            return record
        if repo.id in self.processes and self.processes[repo.id].poll() is None:
            self._finish_record(record, "failed", "Already running")
            return record

        if self._is_frontend_repo(repo):
            self._kill_project_frontend_processes(target, record)

        # -- Preflight: check tools used by the startup command --
        # Handle compound commands such as "cd dir && docker-compose ..."
        if "docker" in repo.start_cmd:
            docker_ok = False
            daemon_running = False
            # Detect the docker compose v2 subcommand
            if cmd_available("docker"):
                # The docker command exists, but the daemon may not be running
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
                                record.logs.append("🔧 Self-healing: docker-compose -> docker compose (v2)")
                                repo.start_cmd = current_cmd
                                self._save_projects()
                    except Exception:
                        pass
                    if not docker_ok and cmd_available("docker-compose"):
                        docker_ok = True
                else:
                    # Docker is installed but its daemon is not running -> start Docker Desktop automatically
                    record.logs.append("🐳 Docker is installed but not running; starting Docker Desktop automatically...")
                    started = self._auto_start_docker(record)
                    if started:
                        docker_ok = True
                        # Check the Compose version again after startup succeeds
                        try:
                            r = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True, timeout=5)
                            if r.returncode == 0 and "docker-compose" in repo.start_cmd:
                                current_cmd = re.sub(r'docker-compose(?=\s|$)', 'docker compose', repo.start_cmd)
                                record.logs.append("🔧 Self-healing: docker-compose -> docker compose (v2)")
                                repo.start_cmd = current_cmd
                                self._save_projects()
                        except Exception:
                            pass

            if not docker_ok:
                # Detect the standalone docker-compose v1 command
                if cmd_available("docker-compose") and daemon_running:
                    docker_ok = True

            if not docker_ok:
                if self._has_local_microservice_jars(target):
                    return self._start_microservices_without_docker(repo, target, record)
                record.logs.append("❌ Docker is not installed or cannot start")
                record.logs.append("  Install: https://www.docker.com/products/docker-desktop/")
                record.logs.append("  After installation, ensure the docker command is available in PATH")
                self._finish_record(record, "failed",
                    "Docker is not installed or cannot start. Install Docker Desktop: https://www.docker.com/products/docker-desktop/")
                return record

        # Retry at most once for port self-healing
        max_attempts = 2
        current_cmd = repo.start_cmd
        current_port = repo.port

        # -- Self-healing: source xxx.sh is unavailable on Windows -> parse the .sh file to load environment variables --
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
                        # Handle export KEY=VALUE and KEY=VALUE formats
                        line = line.replace("export ", "")
                        if "=" in line:
                            k, v = line.split("=", 1)
                            v = v.strip().strip("'").strip('"')
                            env_loaded[k.strip()] = v
                    if env_loaded:
                        # Merge environment variables into docker/.env
                        env_file = target / "docker" / ".env"
                        env_file.parent.mkdir(parents=True, exist_ok=True)
                        self._merge_env_file(target, env_loaded, record)
                        env_keys = ", ".join(k for k in env_loaded if "PASSWORD" not in k)
                        record.logs.append(f"🔧 Self-healing: Windows does not support source -> loaded environment variables from {sh_file}: {env_keys}")
                else:
                    record.logs.append(f"⚠️ Not found: {sh_file}; skipping the source command")
                # Remove the source xxx.sh && prefix
                current_cmd = re.sub(r'source\s+\S+\.sh\s*&&\s*', '', current_cmd).strip()
                record.logs.append(f"🔧 Self-healing: startup command adjusted to: {current_cmd}")
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
                record.logs.append("🔧 Self-healing: microservices detected, but the command starts only the gateway; switching to Docker infrastructure plus all local microservices")
            else:
                return self._start_microservices_without_docker(
                    repo,
                    target,
                    record,
                    reason="🔧 Self-healing: microservices detected, but the command starts only the gateway; switching to all local microservices",
                )

        for attempt in range(max_attempts):
            try:
                record.logs.append(f"🚀 {current_cmd}")
                log_file = DEPLOY_DIR / f"{repo.id}_output.log"

                # -- Load docker/.env variables into the process environment --
                proc_env = os.environ.copy()
                env_vars = self._load_env_file(target)
                if env_vars:
                    proc_env.update(env_vars)
                    env_keys = ", ".join(k for k in env_vars if "PASSWORD" not in k)
                    record.logs.append(f"📋 Loaded .env variables: {env_keys}")

                with open(log_file, "w", encoding="utf-8") as lf:
                    proc = subprocess.Popen(
                        current_cmd, cwd=str(target), stdout=lf, stderr=subprocess.STDOUT,
                        shell=True, env=proc_env,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                    )
                self.processes[repo.id] = proc
                record.logs.append(f"⏳ PID: {proc.pid}; waiting for startup verification...")

                # -- Post-startup health check --
                import time
                for _ in range(3):
                    time.sleep(1)
                    if proc.poll() is not None:
                        break

                if proc.poll() is not None:
                    # Process exited
                    exit_code = proc.returncode
                    self.processes.pop(repo.id, None)

                    # -- Special handling: docker compose -d (detach) mode --
                    # docker compose up -d exits immediately after starting containers (exit=0); this is expected
                    is_docker_detach = (
                        exit_code == 0
                        and "docker" in current_cmd
                        and "-d" in current_cmd
                    )
                    if is_docker_detach:
                        record.logs.append("✅ Docker Compose containers started in the background (detach mode)")

                        # -- Automatically start microservice JAR files --
                        svc_pids = self._start_microservices(target, record)

                        # Track repositories in Docker detach mode so the UI shows them as running
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

                    # -- Self-healing: port conflict -> retry with another port --
                    if is_port_error and attempt == 0 and current_port:
                        new_port = self._find_free_port(current_port + 1)
                        if new_port:
                            record.logs.append(f"🔧 Self-healing: port {current_port} is unavailable; switching to {new_port}")
                            # Replace the port number in the command
                            current_cmd = re.sub(
                                rf'(--port\s+){current_port}\b',
                                rf'\g<1>{new_port}',
                                current_cmd,
                            )
                            # Also handle -p port and :port formats
                            if current_cmd == repo.start_cmd:  # If replacement fails, try other formats
                                current_cmd = current_cmd.replace(str(current_port), str(new_port))
                            current_port = new_port
                            continue  # Retry
                        else:
                            record.logs.append("❌ Self-healing failed: no available port found")

                    # -- Self-healing: root POM has no main class -> switch to Docker Compose or local microservices --
                    if (
                        attempt == 0
                        and "spring-boot:run" in current_cmd
                        and "main class" in err_detail.lower()
                    ):
                        compose_cmd = self._derive_compose_start_cmd(target, record)
                        if compose_cmd:
                            record.logs.append("🔧 Self-healing: spring-boot:run has no executable main class; switching to Docker Compose")
                            current_cmd = compose_cmd
                            repo.start_cmd = current_cmd
                            self._save_projects()
                            continue
                        if self._has_local_microservice_jars(target):
                            record.logs.append("🔧 Self-healing: spring-boot:run has no executable main class; falling back to local microservices")
                            return self._start_microservices_without_docker(repo, target, record)

                    msg = f"Process exited immediately (exit={exit_code})"
                    if err_detail:
                        msg += f": {err_detail}"
                    self._finish_record(record, "failed", msg)
                    return record
                else:
                    # Process is running -> verify the port
                    if current_port:
                        if "docker" in current_cmd and "-d" in current_cmd:
                            record.logs.append("⏳ Docker Compose is building or starting containers; waiting for the background command to finish...")
                            compose_state = self._wait_for_process_or_port(
                                proc,
                                port=current_port,
                                timeout_seconds=240,
                            )
                            if compose_state == "exited":
                                exit_code = proc.returncode
                                self.processes.pop(repo.id, None)
                                if exit_code == 0:
                                    record.logs.append("✅ Docker Compose containers started in the background (detach mode)")
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
                                msg = f"Docker Compose startup failed (exit={exit_code})"
                                if err_detail:
                                    msg += f": {err_detail}"
                                self._finish_record(record, "failed", msg)
                                return record
                            if compose_state == "timeout":
                                self._parse_start_error(log_file, record)
                                self._finish_record(record, "failed", "Docker Compose timed out and the port is still not ready")
                                return record

                        time.sleep(2)
                        if proc.poll() is not None:
                            exit_code = proc.returncode
                            self.processes.pop(repo.id, None)

                            # -- Fix: detect Docker detach mode after a delayed exit as well --
                            is_docker_detach_delayed = (
                                exit_code == 0
                                and "docker" in current_cmd
                                and "-d" in current_cmd
                            )
                            if is_docker_detach_delayed:
                                record.logs.append("✅ Docker Compose containers started in the background (detach mode)")
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
                                    record.logs.append("🔧 Self-healing: spring-boot:run exited late without a main class; switching to Docker Compose")
                                    current_cmd = compose_cmd
                                    repo.start_cmd = current_cmd
                                    self._save_projects()
                                    continue
                                if self._has_local_microservice_jars(target):
                                    record.logs.append("🔧 Self-healing: spring-boot:run exited late without a main class; falling back to local microservices")
                                    return self._start_microservices_without_docker(repo, target, record)
                            self._finish_record(record, "failed", f"Process exited after a delay (exit={exit_code})")
                            return record
                        elif self._check_port(current_port):
                            # Persist the port if it changed
                            if current_port != repo.port or current_cmd != repo.start_cmd:
                                repo.port = current_port
                                repo.start_cmd = current_cmd
                                self._save_projects()
                            record.logs.append(f"⏳ Port {current_port} is initially ready; checking stability...")
                            if self._wait_for_port_stability(
                                current_port,
                                timeout_seconds=12,
                                stable_seconds=5,
                                process_ids=[proc.pid],
                            ):
                                record.logs.append(f"✅ Port {current_port} is stable and ready")
                                if self._verify_repo_http_readiness(repo, current_port, record):
                                    self._remember_effective_env(repo, target, record)
                                    self._finish_record(record, "success", f"Started successfully (PID: {proc.pid}, Port: {current_port})")
                                else:
                                    self._finish_record(record, "failed", f"Port {current_port} is open, but HTTP readiness validation failed")
                            else:
                                self._parse_start_error(log_file, record)
                                if proc.poll() is not None:
                                    self.processes.pop(repo.id, None)
                                self._finish_record(record, "failed", f"Port {current_port} failed stability validation")
                        else:
                            if current_port != repo.port or current_cmd != repo.start_cmd:
                                repo.port = current_port
                                repo.start_cmd = current_cmd
                                self._save_projects()
                            record.logs.append(f"⏳ Process is running; waiting for port {current_port} to become stable...")
                            if self._wait_for_port_stability(
                                current_port,
                                timeout_seconds=20,
                                stable_seconds=5,
                                process_ids=[proc.pid],
                            ):
                                record.logs.append(f"✅ Port {current_port} is stable and ready")
                                if self._verify_repo_http_readiness(repo, current_port, record):
                                    self._remember_effective_env(repo, target, record)
                                    self._finish_record(record, "success", f"Started successfully (PID: {proc.pid}, Port: {current_port})")
                                else:
                                    self._finish_record(record, "failed", f"Port {current_port} is open, but HTTP readiness validation failed")
                            else:
                                self._parse_start_error(log_file, record)
                                if proc.poll() is not None:
                                    self.processes.pop(repo.id, None)
                                self._finish_record(record, "failed", f"Process is running, but port {current_port} failed stability validation")
                    else:
                        record.logs.append(f"✅ Process is running")
                        self._remember_effective_env(repo, target, record)
                        self._finish_record(record, "success", f"Started successfully (PID: {proc.pid})")
                    return record
            except Exception as e:
                self._finish_record(record, "failed", str(e))
                return record

        self._finish_record(record, "failed", "Self-healing retries exhausted")
        return record

    def _parse_start_error(self, log_file: Path, record: DeployRecord) -> tuple:
        """Parse startup logs; return (error summary, is port error)"""
        err_detail = ""
        is_port_error = False
        try:
            log_content = log_file.read_text(encoding="utf-8", errors="replace").strip()
            if log_content:
                clean_log = re.sub(r'\x1b\[[0-9;]*m', '', log_content)
                err_lines = clean_log.strip().split("\n")
                record.logs.extend(err_lines[-10:])
                # First pass: prioritize port errors (EACCES / EADDRINUSE)
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
                # Second pass: if there are no port errors, match general errors
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
        """Read the repository's active environment file, preferring docker/.env."""
        env_file = self._get_env_file_path(project_dir)
        return self._read_env_file(env_file)

    @staticmethod
    def _pid_alive(pid: Optional[int]) -> bool:
        """Check whether a process is alive across platforms."""
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
        """Wait for a stable port and confirm that related processes remain alive throughout verification."""
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
        """Enforce port constraints for known frontend development servers to avoid false results from silent port fallback."""
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
            record.logs.append("🔧 Self-healing: Vite startup is bound to the target port to prevent silent port changes")
        return normalized

    @staticmethod
    def _looks_like_gateway_only_start(current_cmd: str) -> bool:
        """Identify microservice commands that start only the gateway."""
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
        """Extract the runtime port from gateway logs, preferring explicit gateway registration information."""
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
        """Infer the actual runtime port from the current project's gateway logs."""
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
                    record.logs.append(f"🔎 Runtime port found in gateway logs: {port} ({log_path.name})")
                return port
        return 0

    def _verify_repo_http_readiness(self, repo: RepoConfig, port: int, record: DeployRecord) -> bool:
        """After a port connects, perform minimal HTTP semantic validation so a placeholder response is not counted as deployment success."""
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
                observations.append(f"{path}: {probe.get('error', 'Connection failed')}")
                continue

            if "no static resource" in normalized_body:
                observations.append(f"{path}: {status} (static placeholder response)")
                continue

            if is_frontend:
                if status in (200, 301, 302) and ("<html" in normalized_body or "<!doctype html" in normalized_body):
                    record.logs.append(f"✅ HTTP page validation passed: {path} -> {status}")
                    return True
                observations.append(f"{path}: {status}")
                continue

            if status in (200, 401, 403, 405):
                record.logs.append(f"✅ HTTP route validation passed: {path} -> {status}")
                return True

            observations.append(f"{path}: {status}")

        if observations:
            record.logs.append(f"⚠️ HTTP readiness validation failed: {'; '.join(observations[:4])}")
        return False

    def _has_local_microservice_jars(self, project_dir: Path) -> bool:
        """Check for locally executable microservice JAR files"""
        return bool(self._list_local_microservice_jars(project_dir))

    def _list_local_microservice_jars(self, project_dir: Path) -> List[Path]:
        """List microservice JAR files that can run directly within the project."""
        skip_patterns = {"sample-api-", "sample-common-", "sample-common-"}
        jar_files: List[Path] = []
        for jar in project_dir.rglob("target/*.jar"):
            jar_name = jar.name
            if any(p in jar_name for p in skip_patterns):
                continue
            jar_files.append(jar)
        return jar_files

    def _should_start_local_microservices(self, repo: RepoConfig, project_dir: Path, current_cmd: str) -> bool:
        """If a microservice project is configured to start only the gateway, start all local JAR files instead."""
        jar_files = self._list_local_microservice_jars(project_dir)
        if len(jar_files) <= 1:
            return False

        if not self._looks_like_gateway_only_start(current_cmd):
            return False

        tech_stack = (repo.tech_stack or "").lower()
        looks_like_microservice = (
            "spring cloud" in tech_stack
            or "nacos" in tech_stack
            or "microservice" in tech_stack
            or "微服务" in tech_stack
            or len(jar_files) >= 3
        )
        return looks_like_microservice

    def _compose_file_looks_runnable(self, project_dir: Path, compose_file: Path, record: DeployRecord) -> bool:
        """Quickly check that the build contexts required by a Compose file exist."""
        try:
            content = compose_file.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            record.logs.append(f"⚠️ Cannot read Docker Compose file: {exc}")
            return False

        missing_contexts = []
        for match in re.finditer(r"(?m)^\s*context:\s*([^\s#]+)", content):
            raw_path = match.group(1).strip().strip('"').strip("'")
            context_path = (compose_file.parent / raw_path).resolve()
            if not context_path.exists():
                missing_contexts.append(raw_path)

        if missing_contexts:
            preview = ", ".join(missing_contexts[:4])
            record.logs.append(f"⚠️ Docker Compose build context missing: {preview}")
            return False

        return True

    def _find_compose_file(self, project_dir: Path, record: DeployRecord) -> Optional[Path]:
        """Find an executable Compose file inside the project to avoid using a parent directory's configuration."""
        for dc_name in ["docker-compose-dev.yml", "docker-compose.yml"]:
            for check_path in [project_dir / "docker" / dc_name, project_dir / dc_name]:
                if check_path.exists():
                    if self._compose_file_looks_runnable(project_dir, check_path, record):
                        return check_path
                    return None
        return None

    def _normalize_compose_command(self, project_dir: Path, current_cmd: str, record: DeployRecord) -> str:
        """Bind generic docker compose commands to the project's Compose file to avoid matching parent directories."""
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
            record.logs.append("🔧 Self-healing: generic Docker Compose command bound to the project's Compose file to avoid using a parent directory's configuration")
        return explicit_cmd

    @staticmethod
    def _build_java_system_properties(env_vars: Dict[str, str]) -> List[str]:
        """Promote deployment environment variables to JVM System Properties to override hardcoded Spring/Nacos configuration."""
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
        """Identify critical microservice startup paths, prioritizing gateway, authentication, and system services."""
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
        """Wait for process exit or an open target port. Return exited / port / timeout."""
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
        """Derive an executable Docker Compose startup command from the project directory."""
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
                record.logs.append("🐳 Docker Compose fallback found; attempting to start Docker Desktop automatically...")
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
            record.logs.append(f"❌ Critical microservices failed to start: {', '.join(critical_missing[:6])}")
            self._finish_record(record, "failed", f"Critical microservices failed to start: {', '.join(critical_missing[:3])}")
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
            record.logs.append(f"⏳ Waiting for port {effective_port} to become stable...")
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
                        f"🔧 Self-healing: configured port {effective_port} is not ready; using the gateway's actual runtime port {discovered_port}"
                    )
                    effective_port = discovered_port
                    repo.port = effective_port
                    self._save_projects()
                    persist_runtime_state(effective_port)
                    record.logs.append(f"⏳ Continuing validation on port {effective_port}...")
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
                    record.logs.append(f"❌ Stability validation failed; exited services: {', '.join(crashed[:6])}")
                record.logs.append(f"⚠️ Port {effective_port} is not ready; started {len(running)}/{total} microservices")
                self._finish_record(record, "failed", f"Started {len(running)}/{total} microservices, but port {effective_port} is not ready")
                return record

            record.logs.append(f"✅ Port {effective_port} is stable and ready")
            if not self._verify_repo_http_readiness(repo, effective_port, record):
                self._finish_record(record, "failed", f"Port {effective_port} is open, but HTTP readiness validation failed")
                return record

            optional_exited = [
                svc["name"]
                for svc in running
                if svc.get("name") not in critical_names and not self._pid_alive(svc.get("pid"))
            ]
            if optional_exited:
                record.logs.append(f"⚠️ Noncritical microservices exited, but critical entry-point validation passed: {', '.join(optional_exited[:6])}")

        self._update_memory(repo.id, "last_success", datetime.now().isoformat())
        self._remember_effective_env(repo, project_dir, record)
        mode = "Fallback" if fallback_no_docker else "Docker"
        self._finish_record(record, "success", f"Started successfully ({mode} + {len(running)}/{total} microservices)")
        return record

    def _start_microservices_without_docker(
        self,
        repo: RepoConfig,
        project_dir: Path,
        record: DeployRecord,
        reason: str = "",
    ) -> DeployRecord:
        """When Docker is unavailable, run locally built microservice JAR files directly"""
        record.logs.append(reason or "🔧 Self-healing: Docker is unavailable; falling back to local microservices")
        svc_pids = self._start_microservices(project_dir, record)
        running = [svc for svc in svc_pids if svc.get("pid")]
        total = len(svc_pids)

        if not running:
            self._finish_record(record, "failed", "Docker is unavailable, and no local microservices could be started")
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
        """After Docker infrastructure starts, scan for and start all successfully built microservice JAR files"""
        import glob
        results = []

        # -- Read .env variables, including Nacos configuration --
        env_vars = self._load_env_file(project_dir)
        if env_vars:
            env_keys = ", ".join(k for k in env_vars if "PASSWORD" not in k)
            record.logs.append(f"📋 Loaded .env variables: {env_keys}")

        # -- Build the Java runtime environment --
        svc_env = os.environ.copy()
        svc_env.update(env_vars)
        java_system_props = self._build_java_system_properties(env_vars)
        if java_system_props:
            record.logs.append("🔧 Self-healing: inject Spring/Nacos JVM arguments into local microservices to override hardcoded configuration")

        # -- Scan all executable JAR files --
        jar_files = self._list_local_microservice_jars(project_dir)

        if not jar_files:
            record.logs.append("⚠️ No executable microservice JAR files found")
            return results

        # -- Priority order: Gateway -> Auth -> System -> others --
        priority_map = {
            "sample-gateway": 0,
            "sample-auth": 1,
            "sample-modules-system": 2,
        }
        def sort_key(jar_path: Path) -> int:
            for name, pri in priority_map.items():
                if name in jar_path.name:
                    return pri
            return 10  # Put other services later

        jar_files.sort(key=sort_key)
        record.logs.append(f"🔍 Found {len(jar_files)} microservice JAR files")

        # -- Check whether Java is available --
        try:
            java_check = subprocess.run(
                ["java", "-version"], capture_output=True, text=True, timeout=5
            )
            if java_check.returncode != 0:
                record.logs.append("❌ Java is unavailable; cannot start microservices")
                return results
        except Exception:
            record.logs.append("❌ The java command does not exist; cannot start microservices")
            return results

        # -- Start microservices one at a time --
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

                # Wait a few seconds to check for an immediate crash
                import time
                time.sleep(3)

                if proc.poll() is None:
                    # Process still running -> success
                    svc_info["pid"] = proc.pid
                    svc_info["status"] = "running"
                    record.logs.append(f"  ✅ {svc_name} → PID: {proc.pid}")
                else:
                    # Process exited -> startup failure
                    exit_code = proc.returncode
                    # Read the final log lines for diagnosis
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

        # -- Summary --
        ok = len([r for r in results if r["status"] == "running"])
        fail = len(results) - ok
        record.logs.append(f"📊 Microservice startup: {ok} succeeded, {fail} failed (total {len(results)})")

        return results

    async def stop_repo(self, project_key: str, repo_id: str) -> DeployRecord:
        _, repo = self._find_repo(project_key, repo_id)
        record = self._add_record(project_key, repo_id, repo.label, "stop")
        target = self._repo_path(repo)

        # -- Check whether the repository uses Docker detach mode --
        docker_info = self.docker_repos.get(repo.id)
        if docker_info:
            try:
                # Stop microservice processes first
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
                    record.logs.append(f"🛑 Stopped {killed} microservice processes")

                if not docker_info.get("fallback_no_docker"):
                    # Then stop Docker containers
                    stop_cmd = docker_info["cmd"].replace("up -d", "down")
                    record.logs.append(f"🛑 Docker Compose down: {stop_cmd}")
                    result = subprocess.run(
                        stop_cmd, cwd=docker_info["cwd"], shell=True,
                        capture_output=True, text=True, timeout=30
                    )
                    if result.returncode == 0:
                        record.logs.append("✅ Docker containers stopped")
                    else:
                        record.logs.append(f"⚠️ {result.stderr.strip()[:200]}")
                    message = f"Docker containers and {killed} microservices stopped"
                else:
                    record.logs.append("🛑 Local microservices stopped (no Docker containers were used)")
                    message = f"Local microservices stopped ({killed})"
                self.docker_repos.pop(repo.id, None)
                self._finish_record(record, "success", message)
            except Exception as e:
                self._finish_record(record, "failed", str(e))
            return record

        proc = self.processes.get(repo.id)
        if not proc or proc.poll() is not None:
            killed = self._kill_project_frontend_processes(target, record) if self._is_frontend_repo(repo) else 0
            message = f"Cleaned up {killed} remaining frontend processes" if killed else "Not running"
            self._finish_record(record, "success", message)
            return record
        try:
            record.logs.append(f"🛑 Stopping PID: {proc.pid}")
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=10)
            self.processes.pop(repo.id, None)
            killed = self._kill_project_frontend_processes(target, record) if self._is_frontend_repo(repo) else 0
            message = "Stopped"
            if killed:
                message = f"Stopped and cleaned up {killed} remaining frontend processes"
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

        # Use the precreated record or create a new one
        if existing_record:
            record = existing_record
        else:
            record = self._add_record(project_key, repo_id, repo.label, "full_deploy")
            record.logs.append(f"🔄 One-click deployment [{repo.label}]...")

        # Before deployment: write user context to the .env file
        target = self._repo_path(repo)
        if repo.deploy_context and target.exists():
            self._write_env_file(target, repo, record)

        # Initialize three child steps
        step_names = [("clone", "📥 Clone"), ("install", "📦 Install"), ("start", "🚀 Start")]
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
                            record.steps[j].message = "Task canceled without execution"
                    self._finish_record(record, "cancelled", "Deployment job canceled")
                    self._emit_event(repo_id, {
                        "type": "deploy_done", "status": "cancelled", "message": "Deployment job canceled",
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
                    "logs": sub_record.logs[-50:],  # Push the latest 50 log lines
                })

                # Delete child records, keeping only the summary record
                self.history = [r for r in self.history if r.id != sub_record.id]

                if job_id and self._job_cancellation_requested(job_id):
                    for j in range(i + 1, len(record.steps)):
                        record.steps[j].status = "skipped"
                        record.steps[j].message = "Task canceled without execution"
                    self._finish_record(record, "cancelled", "Deployment job canceled")
                    self._emit_event(repo_id, {
                        "type": "deploy_done", "status": "cancelled", "message": "Deployment job canceled",
                    })
                    return record

                if sub_record.status == "failed":
                    # Mark later steps as skipped
                    for j in range(i + 1, len(record.steps)):
                        record.steps[j].status = "skipped"
                        record.steps[j].message = "Skipped because a previous step failed"
                    self._finish_record(record, "failed", f"{slabel} Failed: {sub_record.message}")
                    self._emit_event(repo_id, {
                        "type": "deploy_done", "status": "failed",
                        "message": f"{slabel} Failed: {sub_record.message}",
                    })
                    return record

            self._finish_record(record, "success", "One-click deployment completed ✅")
            self._emit_event(repo_id, {
                "type": "deploy_done", "status": "success", "message": "One-click deployment completed ✅",
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
        """Deploy every repository in the project with one click"""
        if project_key not in self.projects:
            raise ValueError(f"Project not found: {project_key}")
        proj = self.projects[project_key]
        record = existing_record or self._add_record(project_key, "", proj.name, "full_deploy_all")
        if not existing_record:
            record.logs.append(f"🔄 Deploy all ({len(proj.repos)} repositories)...")

        for repo in proj.repos:
            if job_id and self._job_cancellation_requested(job_id):
                self._finish_record(record, "cancelled", "Project-wide deployment job canceled")
                return record
            record.logs.append(f"📦 Deploying repository [{repo.label}]...")
            r = await self.full_deploy_repo(project_key, repo.id, job_id=job_id)
            record.logs.extend(r.logs)
            if r.status == "cancelled":
                self._finish_record(record, "cancelled", f"[{repo.label}] canceled")
                return record
            if r.status == "failed":
                self._finish_record(record, "failed", f"[{repo.label}] failed: {r.message}")
                return record

        self._finish_record(record, "success", f"All {len(proj.repos)} repositories deployed ✅")
        return record

    # -- Status queries ------------------------------------------------------
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
            raise ValueError(f"Project not found: {key}")
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

    # -- Logs ----------------------------------------------------------------
    def get_logs(self, repo_id: str, lines: int = 100) -> List[str]:
        if lines <= 0:
            return []
        log_file = DEPLOY_DIR / f"{repo_id}_output.log"
        if not log_file.exists():
            return ["No logs yet"]
        try:
            content = log_file.read_text(encoding="utf-8", errors="replace")
            all_lines = content.strip().split("\n")
            return all_lines[-lines:]
        except Exception as e:
            return [f"Failed to read logs: {e}"]

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

    # -- AI analysis ---------------------------------------------------------
    async def ai_analyze_repo(self, project_key: str, repo_id: str) -> Dict:
        """Use AI to analyze repository structure and recommend configuration, incorporating deployment memory"""
        proj, repo = self._find_repo(project_key, repo_id)
        target = self._repo_path(repo)

        if not target.exists():
            return {"error": "The repository has not been cloned; clone it first", "source": "ai"}

        # -- Incorporate deployment memory --
        mem = self._load_memory(repo.id)
        env_state = self._get_repo_env_state(repo)
        memory_hint = ""
        if mem:
            parts = []
            if mem.get("build_strategy"):
                bs = mem["build_strategy"]
                if bs.get("excluded_modules"):
                    parts.append(f"Build history: exclude modules {bs['excluded_modules']}")
                if bs.get("cmd"):
                    parts.append(f"Last successful build command: {bs['cmd']}")
            if mem.get("ai_config"):
                ac = mem["ai_config"]
                if ac.get("pom_changes"):
                    parts.append(f"Previous POM changes: {ac['pom_changes']}")
            if mem.get("start_config"):
                sc = mem["start_config"]
                parts.append(f"Previous startup: {sc.get('success_count', 0)}/{sc.get('total_count', 0)} microservices succeeded")
                if sc.get("docker_cmd"):
                    parts.append(f"Last stable startup command: {sc['docker_cmd']}")
            if mem.get("effective_env", {}).get("summary"):
                parts.append(f"Previously active environment: {mem['effective_env']['summary']}")
            if mem.get("deploy_count"):
                parts.append(f"Total successful deployments: {mem['deploy_count']}")
            memory_hint = "\n".join(parts)
            logger.info(f"[Memory] Providing AI with {repo.label}'s {len(parts)} historical memory entries")

        from services.ai_deploy_analyzer import analyze_project
        result = await analyze_project(
            target, label=repo.label, repo_url=repo.repo_url,
            memory_hint=memory_hint,
            current_env_text=env_state["effective_env_text"],
        )
        result = self._prefer_stable_ai_start_command(repo, result, mem)

        # Include memory details in the result for frontend display
        if mem:
            result["has_memory"] = True
            result["deploy_count"] = mem.get("deploy_count", 0)
            result["last_success"] = mem.get("last_success", "")

        result.update(env_state)

        return result

    def apply_ai_config(self, project_key: str, repo_id: str, config: Dict) -> Dict:
        """Apply AI-recommended configuration to the repository and save it to memory"""
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
                logger.info(f"[AI] Frontend port is too low; adjusted automatically: {repo.label} {repo.port} -> {normalized_port}")
                repo.port = normalized_port
            if repo.start_cmd:
                normalized_start_cmd = self._normalize_start_command(
                    repo,
                    repo.start_cmd,
                    repo.port,
                    DeployRecord(project_key=project_key, repo_id=repo.id, repo_label=repo.label, action="apply_ai_config"),
                )
                if normalized_start_cmd != repo.start_cmd:
                    logger.info(f"[AI] Frontend startup command normalized: {repo.start_cmd} -> {normalized_start_cmd}")
                    repo.start_cmd = normalized_start_cmd
        if config.get("deploy_context"):
            existing_ctx = dict(repo.deploy_context or {})
            ctx = {**existing_ctx, **dict(config["deploy_context"] or {})}
            repo.deploy_context = ctx
            # User confirms POM changes
            if ctx.get("apply_pom_changes") and ctx.get("suggested_changes"):
                target = self._repo_path(repo)
                if target.exists():
                    temp_record = DeployRecord()
                    self._apply_pom_changes(target, ctx["suggested_changes"], temp_record)
                    logger.info(f"[AI] POM changes applied: {temp_record.logs}")

            # -- Fix3: write deploy_context.env_vars into docker/.env --
            if ctx.get("env_vars"):
                target = self._repo_path(repo)
                if target.exists():
                    overrides = self._parse_env_text(ctx["env_vars"])
                    if ctx.get("server_address"):
                        overrides["DEPLOY_SERVER"] = ctx["server_address"]
                    if ctx.get("db_connection"):
                        overrides["DATABASE_URL"] = ctx["db_connection"]
                    merged = self._merge_env_file(target, overrides)
                    logger.info(f"[AI] Environment variables written to {self._get_env_file_path(target, create=True)}: {list(merged.keys())}")

        # -- Fix1: detect existing POM profile exclusions and remove conflicting -pl ! from install_cmd --
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
                # POM profiles already exclude modules; remove conflicting -pl ! arguments automatically
                cleaned = re.sub(r'\s+-pl\s+[^\s]+', '', repo.install_cmd).strip()
                logger.info(f"[AI] POM already has profile exclusions; cleaning install_cmd: {repo.install_cmd} → {cleaned}")
                repo.install_cmd = cleaned

        # -- Save AI configuration to memory --
        self._update_memory(repo.id, "ai_config", {
            "tech_stack": config.get("tech_stack"),
            "install_cmd": repo.install_cmd,  # Use the cleaned command
            "start_cmd": repo.start_cmd,
            "port": repo.port,
            "pom_changes": config.get("deploy_context", {}).get("suggested_changes"),
            "timestamp": datetime.now().isoformat()
        })
        logger.info(f"[Memory] AI configuration saved: {repo.label}")

        self._save_projects()
        logger.info(f"[AI] Configuration applied: {repo.label} → {repo.tech_stack}")
        return self.get_repo_status(repo)


# -- Singleton -----------------------------------------------------------
_service_instance: Optional[DeployService] = None


def get_deploy_service() -> DeployService:
    global _service_instance
    if _service_instance is None:
        _service_instance = DeployService()
    return _service_instance
