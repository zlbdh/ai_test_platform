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
        label="Backend",
        repo_url="https://example.com/backend.git",
        local_dir="unused",
        tech_stack="Java 17 + Spring Cloud",
        install_cmd="mvn clean install -DskipTests",
        start_cmd="mvn spring-boot:run",
        port=8080,
    )
    project = ProjectConfig(key="proj1", name="Test project", repos=[repo])

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
        "job_queue": DeployJob(id="job_queue", status="queued", message="Pending"),
        "job_run": DeployJob(id="job_run", status="running", message="Running"),
        "job_done": DeployJob(id="job_done", status="success", message="Completed"),
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
        existing_record.message = "One-click deployment completed ✅"
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
        existing_record.message = "Startup failed"
        return existing_record

    with patch.object(service, "full_deploy_repo", side_effect=fake_full_deploy):
        job = service.schedule_full_deploy("proj1", repo.id, "hotfix")
        await asyncio.wait_for(service._active_job_tasks[job.id], timeout=1)

    assert service.jobs[job.id].status == "failed"
    assert service.jobs[job.id].message == "Startup failed"


@pytest.mark.asyncio
async def test_schedule_full_deploy_all_tracks_success_job_lifecycle(tmp_path: Path):
    service, repo = _make_service(tmp_path)
    frontend = RepoConfig(
        id="repo2",
        label="Frontend",
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
        existing_record.message = "All 2 repositories deployed successfully ✅"
        return existing_record

    with patch.object(service, "full_deploy_all", side_effect=fake_full_deploy_all):
        job = service.schedule_full_deploy_all("proj1")
        await asyncio.wait_for(service._active_job_tasks[job.id], timeout=1)

    assert job.record_id
    assert service.jobs[job.id].action == "full_deploy_all"
    assert service.jobs[job.id].status == "success"
    assert service.jobs[job.id].repo_label == "Test project"
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
        existing_record.message = "[Backend] Failed: Startup failed"
        return existing_record

    with patch.object(service, "full_deploy_all", side_effect=fake_full_deploy_all):
        job = service.schedule_full_deploy_all("proj1")
        await asyncio.wait_for(service._active_job_tasks[job.id], timeout=1)

    assert service.jobs[job.id].action == "full_deploy_all"
    assert service.jobs[job.id].status == "failed"
    assert service.jobs[job.id].message == "[Backend] Failed: Startup failed"


@pytest.mark.asyncio
async def test_cancel_job_marks_running_repo_job_cancelled(tmp_path: Path):
    service, repo = _make_service(tmp_path)
    gate = asyncio.Event()

    async def fake_full_deploy(_project_key, _repo_id, branch="", existing_record=None, job_id=""):
        assert branch == "release"
        assert job_id
        existing_record.steps[0].status = "running"
        existing_record.steps[0].message = "Cloning"
        await gate.wait()
        if service._job_cancellation_requested(job_id):
            existing_record.steps[0].status = "cancelled"
            existing_record.steps[0].message = "Deployment job canceled"
            existing_record.status = "cancelled"
            existing_record.message = "Deployment job canceled"
            return existing_record
        existing_record.steps[0].status = "success"
        existing_record.steps[0].message = "Clone completed"
        existing_record.status = "success"
        existing_record.message = "One-click deployment completed ✅"
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
    assert service.history[0].message == "Deployment job canceled"


def test_cancel_job_rejects_finished_job(tmp_path: Path):
    service, _ = _make_service(tmp_path)
    service.jobs = {
        "job_done": DeployJob(id="job_done", status="success", message="Completed"),
    }

    with pytest.raises(ValueError, match="The job has finished and cannot be canceled"):
        service.cancel_job("job_done")


def test_cancel_job_finalizes_without_active_task(tmp_path: Path):
    service, _ = _make_service(tmp_path)
    record = DeployRecord(
        id="rec_cancel",
        project_key="proj1",
        repo_id="repo1",
        repo_label="Backend",
        action="full_deploy",
        status="running",
        steps=[DeployStep(name="clone", status="pending")],
    )
    job = DeployJob(
        id="job_cancel",
        action="full_deploy",
        project_key="proj1",
        repo_id="repo1",
        repo_label="Backend",
        record_id="rec_cancel",
        status="queued",
        message="Pending",
    )
    service.history = [record]
    service.jobs = {job.id: job}

    payload = service.cancel_job(job.id)

    assert payload["status"] == "cancelled"
    assert service.jobs[job.id].status == "cancelled"
    assert service.history[0].status == "cancelled"


def test_get_job_detail_includes_record_status(tmp_path: Path):
    service, _ = _make_service(tmp_path)
    record = DeployRecord(id="rec_demo", project_key="proj1", repo_id="repo1", repo_label="Backend", action="full_deploy", status="success", message="Completed")
    service.history = [record]
    job = DeployJob(id="job_demo", action="full_deploy", project_key="proj1", repo_id="repo1", repo_label="Backend", record_id="rec_demo", status="success", message="Completed")
    service.jobs = {job.id: job}

    payload = service.get_job_detail("job_demo")

    assert payload is not None
    assert payload["record_status"] == "success"
    assert payload["record_message"] == "Completed"


def test_list_jobs_returns_latest_first_and_supports_status_filter(tmp_path: Path):
    service, _ = _make_service(tmp_path)
    service.history = [
        DeployRecord(id="rec_old", status="success", message="Old task"),
        DeployRecord(id="rec_new", status="failed", message="New task"),
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
        requested_by_name="Developer",
    )

    assert payload["status"] == "pending"
    assert payload["action"] == "full_deploy"
    assert payload["project_key"] == "proj1"
    assert payload["repo_id"] == repo.id
    assert payload["repo_label"] == repo.label
    assert payload["branch"] == "release"
    assert payload["requested_by"] == "dev1"
    assert service.approvals[payload["id"]].message == "Awaiting approval"


def test_review_repo_approval_schedules_job_on_approve(tmp_path: Path):
    service, repo = _make_service(tmp_path)
    approval = service.create_deploy_approval(
        action="full_deploy",
        project_key="proj1",
        repo_id=repo.id,
        branch="release",
        requested_by="dev1",
        requested_by_name="Developer",
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
            reviewed_by_name="Administrator",
            comment="Ready to release",
        )

    assert payload["status"] == "approved"
    assert payload["job_id"] == "job_repo_approved"
    assert payload["record_id"] == "rec_repo_approved"
    assert payload["reviewed_by"] == "admin1"
    assert payload["review_comment"] == "Ready to release"
    assert payload["job"]["status"] == "queued"


def test_review_project_approval_schedules_project_job_on_approve(tmp_path: Path):
    service, _ = _make_service(tmp_path)
    approval = service.create_deploy_approval(
        action="full_deploy_all",
        project_key="proj1",
        requested_by="dev1",
        requested_by_name="Developer",
    )

    def fake_schedule(project_key: str) -> DeployJob:
        assert project_key == "proj1"
        job = DeployJob(
            id="job_project_approved",
            action="full_deploy_all",
            project_key=project_key,
            repo_id="",
            repo_label="Test project",
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
            reviewed_by_name="Administrator",
            comment="Project release approved",
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
        requested_by_name="Developer",
    )

    payload = service.review_approval(
        approval["id"],
        approved=False,
        reviewed_by="admin1",
        reviewed_by_name="Administrator",
        comment="Release window has not opened",
    )

    assert payload["status"] == "rejected"
    assert payload["message"] == "Approval rejected"
    assert payload["review_comment"] == "Release window has not opened"
    assert payload["job_id"] == ""


def test_load_jobs_marks_running_job_orphaned_after_reload(tmp_path: Path):
    jobs_file = tmp_path / "deploy_jobs.json"
    original = DeployJob(
        id="job_reload",
        action="full_deploy",
        project_key="proj1",
        repo_id="repo1",
        repo_label="Backend",
        record_id="rec1",
        status="running",
        message="Running",
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
