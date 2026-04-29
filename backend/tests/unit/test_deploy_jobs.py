# -*- coding: utf-8 -*-
import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from services.deploy_models import DeployJob, DeployRecord, DeployStep, ProjectConfig, RepoConfig
from services.deploy_service import DeployService


def _make_service(project_dir: Path) -> tuple[DeployService, RepoConfig]:
    service = DeployService.__new__(DeployService)
    repo = RepoConfig(
        id="repo1",
        label="后端",
        repo_url="https://example.com/backend.git",
        local_dir="unused",
        tech_stack="Java 17 + Spring Cloud",
        install_cmd="mvn clean install -DskipTests",
        start_cmd="mvn spring-boot:run",
        port=8080,
    )
    project = ProjectConfig(key="proj1", name="测试项目", repos=[repo])

    service.projects = {project.key: project}
    service.processes = {}
    service.docker_repos = {}
    service.history = []
    service.jobs = {}
    service.approvals = {}
    service.memory = {}
    service._deploy_event_bus = {}
    service._active_job_tasks = {}
    service._repo_path = lambda _repo: project_dir
    service._save_history = lambda: None
    service._save_projects = lambda: None
    service._save_jobs = lambda: None
    service._save_approvals = lambda: None
    return service, repo


def test_mark_incomplete_jobs_as_orphaned():
    service, _ = _make_service(Path("."))
    service.jobs = {
        "job_queue": DeployJob(id="job_queue", status="queued", message="待执行"),
        "job_run": DeployJob(id="job_run", status="running", message="执行中"),
        "job_done": DeployJob(id="job_done", status="success", message="完成"),
    }

    service._mark_incomplete_jobs_orphaned()

    assert service.jobs["job_queue"].status == "orphaned"
    assert service.jobs["job_run"].status == "orphaned"
    assert service.jobs["job_done"].status == "success"
    assert service.jobs["job_queue"].finished_at
    assert service.jobs["job_run"].finished_at


@pytest.mark.asyncio
async def test_schedule_full_deploy_tracks_success_job_lifecycle(tmp_path: Path):
    service, repo = _make_service(tmp_path)

    async def fake_full_deploy(project_key, repo_id, branch="", existing_record=None, job_id=""):
        assert project_key == "proj1"
        assert repo_id == repo.id
        assert branch == "release"
        assert job_id
        existing_record.status = "success"
        existing_record.message = "一键部署完成 ✅"
        return existing_record

    with patch.object(service, "full_deploy_repo", side_effect=fake_full_deploy):
        job = service.schedule_full_deploy("proj1", repo.id, "release")
        await asyncio.wait_for(service._active_job_tasks[job.id], timeout=1)

    assert job.record_id
    assert service.jobs[job.id].status == "success"
    assert service.jobs[job.id].branch == "release"
    assert service.jobs[job.id].started_at
    assert service.jobs[job.id].finished_at
    assert service.history[0].id == job.record_id
    assert service.history[0].action == "full_deploy"


@pytest.mark.asyncio
async def test_schedule_full_deploy_tracks_failed_job_lifecycle(tmp_path: Path):
    service, repo = _make_service(tmp_path)

    async def fake_full_deploy(_project_key, _repo_id, branch="", existing_record=None, job_id=""):
        assert branch == "hotfix"
        assert job_id
        existing_record.status = "failed"
        existing_record.message = "启动失败"
        return existing_record

    with patch.object(service, "full_deploy_repo", side_effect=fake_full_deploy):
        job = service.schedule_full_deploy("proj1", repo.id, "hotfix")
        await asyncio.wait_for(service._active_job_tasks[job.id], timeout=1)

    assert service.jobs[job.id].status == "failed"
    assert service.jobs[job.id].message == "启动失败"


@pytest.mark.asyncio
async def test_schedule_full_deploy_all_tracks_success_job_lifecycle(tmp_path: Path):
    service, repo = _make_service(tmp_path)
    frontend = RepoConfig(
        id="repo2",
        label="前端",
        repo_url="https://example.com/frontend.git",
        local_dir="unused-frontend",
        tech_stack="React + Vite",
        install_cmd="npm install",
        start_cmd="npm run dev",
        port=8010,
    )
    service.projects["proj1"].repos.append(frontend)

    async def fake_full_deploy_all(project_key, existing_record=None, job_id=""):
        assert project_key == "proj1"
        assert existing_record is service.history[0]
        assert job_id
        existing_record.status = "success"
        existing_record.message = "全部 2 个仓库部署完成 ✅"
        return existing_record

    with patch.object(service, "full_deploy_all", side_effect=fake_full_deploy_all):
        job = service.schedule_full_deploy_all("proj1")
        await asyncio.wait_for(service._active_job_tasks[job.id], timeout=1)

    assert job.record_id
    assert service.jobs[job.id].action == "full_deploy_all"
    assert service.jobs[job.id].status == "success"
    assert service.jobs[job.id].repo_label == "测试项目"
    assert service.jobs[job.id].started_at
    assert service.jobs[job.id].finished_at
    assert service.history[0].id == job.record_id
    assert service.history[0].action == "full_deploy_all"


@pytest.mark.asyncio
async def test_schedule_full_deploy_all_tracks_failed_job_lifecycle(tmp_path: Path):
    service, _ = _make_service(tmp_path)

    async def fake_full_deploy_all(_project_key, existing_record=None, job_id=""):
        assert job_id
        existing_record.status = "failed"
        existing_record.message = "[后端] 失败: 启动失败"
        return existing_record

    with patch.object(service, "full_deploy_all", side_effect=fake_full_deploy_all):
        job = service.schedule_full_deploy_all("proj1")
        await asyncio.wait_for(service._active_job_tasks[job.id], timeout=1)

    assert service.jobs[job.id].action == "full_deploy_all"
    assert service.jobs[job.id].status == "failed"
    assert service.jobs[job.id].message == "[后端] 失败: 启动失败"


@pytest.mark.asyncio
async def test_cancel_job_marks_running_repo_job_cancelled(tmp_path: Path):
    service, repo = _make_service(tmp_path)
    gate = asyncio.Event()

    async def fake_full_deploy(_project_key, _repo_id, branch="", existing_record=None, job_id=""):
        assert branch == "release"
        assert job_id
        existing_record.steps[0].status = "running"
        existing_record.steps[0].message = "克隆中"
        await gate.wait()
        if service._job_cancellation_requested(job_id):
            existing_record.steps[0].status = "cancelled"
            existing_record.steps[0].message = "部署任务已取消"
            existing_record.status = "cancelled"
            existing_record.message = "部署任务已取消"
            return existing_record
        existing_record.steps[0].status = "success"
        existing_record.steps[0].message = "克隆完成"
        existing_record.status = "success"
        existing_record.message = "一键部署完成 ✅"
        return existing_record

    with patch.object(service, "full_deploy_repo", side_effect=fake_full_deploy):
        job = service.schedule_full_deploy("proj1", repo.id, "release")
        await asyncio.sleep(0)
        payload = service.cancel_job(job.id)
        gate.set()
        await asyncio.wait_for(service._active_job_tasks[job.id], timeout=1)

    assert payload["status"] == "cancel_requested"
    assert service.jobs[job.id].status == "cancelled"
    assert service.history[0].status == "cancelled"
    assert service.history[0].message == "部署任务已取消"


def test_cancel_job_rejects_finished_job(tmp_path: Path):
    service, _ = _make_service(tmp_path)
    service.jobs = {
        "job_done": DeployJob(id="job_done", status="success", message="完成"),
    }

    with pytest.raises(ValueError, match="作业已结束，无法取消"):
        service.cancel_job("job_done")


def test_cancel_job_finalizes_without_active_task(tmp_path: Path):
    service, _ = _make_service(tmp_path)
    record = DeployRecord(
        id="rec_cancel",
        project_key="proj1",
        repo_id="repo1",
        repo_label="后端",
        action="full_deploy",
        status="running",
        steps=[DeployStep(name="clone", status="pending")],
    )
    job = DeployJob(
        id="job_cancel",
        action="full_deploy",
        project_key="proj1",
        repo_id="repo1",
        repo_label="后端",
        record_id="rec_cancel",
        status="queued",
        message="待执行",
    )
    service.history = [record]
    service.jobs = {job.id: job}

    payload = service.cancel_job(job.id)

    assert payload["status"] == "cancelled"
    assert service.jobs[job.id].status == "cancelled"
    assert service.history[0].status == "cancelled"


def test_get_job_detail_includes_record_status(tmp_path: Path):
    service, _ = _make_service(tmp_path)
    record = DeployRecord(id="rec_demo", project_key="proj1", repo_id="repo1", repo_label="后端", action="full_deploy", status="success", message="完成")
    service.history = [record]
    job = DeployJob(id="job_demo", action="full_deploy", project_key="proj1", repo_id="repo1", repo_label="后端", record_id="rec_demo", status="success", message="完成")
    service.jobs = {job.id: job}

    payload = service.get_job_detail("job_demo")

    assert payload is not None
    assert payload["record_status"] == "success"
    assert payload["record_message"] == "完成"


def test_list_jobs_returns_latest_first_and_supports_status_filter(tmp_path: Path):
    service, _ = _make_service(tmp_path)
    service.history = [
        DeployRecord(id="rec_old", status="success", message="旧任务"),
        DeployRecord(id="rec_new", status="failed", message="新任务"),
    ]
    service.jobs = {
        "job_old": DeployJob(id="job_old", record_id="rec_old", status="success", created_at="2026-03-19T10:00:00"),
        "job_new": DeployJob(id="job_new", record_id="rec_new", status="failed", created_at="2026-03-20T10:00:00"),
    }

    failed_jobs = service.list_jobs(limit=10, status="failed")
    all_jobs = service.list_jobs(limit=10)

    assert failed_jobs[0]["id"] == "job_new"
    assert len(failed_jobs) == 1
    assert all_jobs[0]["id"] == "job_new"
    assert all_jobs[1]["id"] == "job_old"


def test_create_deploy_approval_returns_pending_payload(tmp_path: Path):
    service, repo = _make_service(tmp_path)

    payload = service.create_deploy_approval(
        action="full_deploy",
        project_key="proj1",
        repo_id=repo.id,
        branch="release",
        requested_by="dev1",
        requested_by_name="开发者",
    )

    assert payload["status"] == "pending"
    assert payload["action"] == "full_deploy"
    assert payload["project_key"] == "proj1"
    assert payload["repo_id"] == repo.id
    assert payload["repo_label"] == repo.label
    assert payload["branch"] == "release"
    assert payload["requested_by"] == "dev1"
    assert service.approvals[payload["id"]].message == "等待审批"


def test_review_repo_approval_schedules_job_on_approve(tmp_path: Path):
    service, repo = _make_service(tmp_path)
    approval = service.create_deploy_approval(
        action="full_deploy",
        project_key="proj1",
        repo_id=repo.id,
        branch="release",
        requested_by="dev1",
        requested_by_name="开发者",
    )

    def fake_schedule(project_key: str, repo_id: str, branch: str = "") -> DeployJob:
        assert project_key == "proj1"
        assert repo_id == repo.id
        assert branch == "release"
        job = DeployJob(
            id="job_repo_approved",
            action="full_deploy",
            project_key=project_key,
            repo_id=repo_id,
            repo_label=repo.label,
            record_id="rec_repo_approved",
            branch=branch,
            status="queued",
        )
        service.jobs[job.id] = job
        return job

    with patch.object(service, "schedule_full_deploy", side_effect=fake_schedule):
        payload = service.review_approval(
            approval["id"],
            approved=True,
            reviewed_by="admin1",
            reviewed_by_name="管理员",
            comment="可以发布",
        )

    assert payload["status"] == "approved"
    assert payload["job_id"] == "job_repo_approved"
    assert payload["record_id"] == "rec_repo_approved"
    assert payload["reviewed_by"] == "admin1"
    assert payload["review_comment"] == "可以发布"
    assert payload["job"]["status"] == "queued"


def test_review_project_approval_schedules_project_job_on_approve(tmp_path: Path):
    service, _ = _make_service(tmp_path)
    approval = service.create_deploy_approval(
        action="full_deploy_all",
        project_key="proj1",
        requested_by="dev1",
        requested_by_name="开发者",
    )

    def fake_schedule(project_key: str) -> DeployJob:
        assert project_key == "proj1"
        job = DeployJob(
            id="job_project_approved",
            action="full_deploy_all",
            project_key=project_key,
            repo_id="",
            repo_label="测试项目",
            record_id="rec_project_approved",
            status="queued",
        )
        service.jobs[job.id] = job
        return job

    with patch.object(service, "schedule_full_deploy_all", side_effect=fake_schedule):
        payload = service.review_approval(
            approval["id"],
            approved=True,
            reviewed_by="admin1",
            reviewed_by_name="管理员",
            comment="项目级发布通过",
        )

    assert payload["status"] == "approved"
    assert payload["job_id"] == "job_project_approved"
    assert payload["record_id"] == "rec_project_approved"
    assert payload["job"]["action"] == "full_deploy_all"


def test_review_approval_marks_rejected_without_creating_job(tmp_path: Path):
    service, repo = _make_service(tmp_path)
    approval = service.create_deploy_approval(
        action="full_deploy",
        project_key="proj1",
        repo_id=repo.id,
        requested_by="dev1",
        requested_by_name="开发者",
    )

    payload = service.review_approval(
        approval["id"],
        approved=False,
        reviewed_by="admin1",
        reviewed_by_name="管理员",
        comment="发布窗口未到",
    )

    assert payload["status"] == "rejected"
    assert payload["message"] == "审批已拒绝"
    assert payload["review_comment"] == "发布窗口未到"
    assert payload["job_id"] == ""


def test_load_jobs_marks_running_job_orphaned_after_reload(tmp_path: Path):
    jobs_file = tmp_path / "deploy_jobs.json"
    original = DeployJob(
        id="job_reload",
        action="full_deploy",
        project_key="proj1",
        repo_id="repo1",
        repo_label="后端",
        record_id="rec1",
        status="running",
        message="执行中",
    )

    service, _ = _make_service(tmp_path)
    service.jobs = {original.id: original}

    with patch("services.deploy_service.JOBS_FILE", jobs_file):
        service._save_jobs = DeployService._save_jobs.__get__(service, DeployService)
        service._save_jobs()

        reloaded, _ = _make_service(tmp_path)
        reloaded._load_jobs = DeployService._load_jobs.__get__(reloaded, DeployService)
        reloaded._save_jobs = DeployService._save_jobs.__get__(reloaded, DeployService)
        reloaded._mark_incomplete_jobs_orphaned = DeployService._mark_incomplete_jobs_orphaned.__get__(reloaded, DeployService)
        reloaded._load_jobs()
        reloaded._mark_incomplete_jobs_orphaned()

    assert reloaded.jobs["job_reload"].status == "orphaned"
    assert "orphaned" in reloaded.jobs["job_reload"].message.lower()
