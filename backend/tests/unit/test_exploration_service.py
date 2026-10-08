# -*- coding: utf-8 -*-
from contextlib import contextmanager
import sqlite3
from types import SimpleNamespace

import pytest

from services.exploration_service import (
    ExplorationPermissionError,
    ExplorationService,
)


def _make_user(role: str = "tester", project_ids=None):
    return SimpleNamespace(
        user_id="user_demo",
        username="demo",
        role=SimpleNamespace(value=role),
        project_ids=list(project_ids or []),
    )


def _patch_temp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "exploration.db"

    @contextmanager
    def _get_connection():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    monkeypatch.setattr("services.exploration_service.get_connection", _get_connection)


def test_create_exploration_session_persists_summary_and_findings(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    service = ExplorationService()

    session = service.create_session(
        user=_make_user(project_ids=["demo"]),
        group_id="grp_demo",
        project_key="demo",
        target_url="https://demo.example.com/login",
        charter="围绕登录与核心认证链路做探索性测试",
    )

    assert session["status"] == "completed"
    assert session["summary"]["finding_count"] >= 1
    assert session["summary"]["requires_human_review_count"] >= 1
    assert len(session["findings"]) >= 1
    assert session["findings"][0]["evidence"]["reproduction_steps"]
    assert all(item["review_status"] == "pending" for item in session["findings"])
    assert all(item["review_comment"] == "" for item in session["findings"])


def test_list_exploration_findings_supports_review_filter(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    service = ExplorationService()
    session = service.create_session(
        user=_make_user(project_ids=["demo"]),
        group_id="",
        project_key="demo",
        target_url="https://demo.example.com/payment",
        charter="检查支付与下单体验",
    )

    review_only = service.list_findings(
        user=_make_user(project_ids=["demo"]),
        session_id=session["session_id"],
        review_only=True,
    )

    assert review_only["count"] >= 1
    assert all(item["requires_human_review"] for item in review_only["findings"])


def test_review_finding_persists_status_comment_and_reviewer(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    service = ExplorationService()
    user = _make_user(project_ids=["demo"])
    session = service.create_session(
        user=user,
        group_id="grp_demo",
        project_key="demo",
        target_url="https://demo.example.com/login",
        charter="围绕登录与认证链路做探索",
    )
    finding = session["findings"][0]

    reviewed = service.review_finding(
        user=user,
        finding_id=finding["finding_id"],
        decision="confirmed",
        comment="Manual review requires follow-up",
    )

    assert reviewed["review_status"] == "confirmed"
    assert reviewed["review_comment"] == "Manual review requires follow-up"
    assert reviewed["reviewed_by"] == "demo"
    assert reviewed["reviewed_at"]
    refreshed = service.get_finding(user=user, finding_id=finding["finding_id"])
    assert refreshed["review_status"] == "confirmed"
    assert refreshed["review_comment"] == "Manual review requires follow-up"


def test_list_review_queue_defaults_to_pending_human_review_findings(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    service = ExplorationService()
    user = _make_user(project_ids=["demo"])
    session = service.create_session(
        user=user,
        group_id="grp_demo",
        project_key="demo",
        target_url="https://demo.example.com/login",
        charter="围绕登录与认证链路做探索",
    )
    human_review_finding = next(item for item in session["findings"] if item["requires_human_review"])
    service.review_finding(
        user=user,
        finding_id=human_review_finding["finding_id"],
        decision="dismissed",
        comment="Manually rejected",
    )

    pending_queue = service.list_review_queue(user=user)
    dismissed_queue = service.list_review_queue(user=user, review_status="dismissed")

    assert pending_queue["review_status"] == "pending"
    assert all(item["requires_human_review"] for item in pending_queue["findings"])
    assert all(item["review_status"] == "pending" for item in pending_queue["findings"])
    assert dismissed_queue["count"] == 1
    assert dismissed_queue["findings"][0]["finding_id"] == human_review_finding["finding_id"]


def test_get_and_review_finding_enforce_project_scope(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    service = ExplorationService()
    session = service.create_session(
        user=_make_user(project_ids=["demo"]),
        group_id="grp_demo",
        project_key="demo",
        target_url="https://demo.example.com/login",
        charter="围绕登录与认证链路做探索",
    )
    finding_id = session["findings"][0]["finding_id"]
    outsider = _make_user(project_ids=["proj2"])

    with pytest.raises(ExplorationPermissionError):
        service.get_finding(user=outsider, finding_id=finding_id)

    with pytest.raises(ExplorationPermissionError):
        service.review_finding(
            user=outsider,
            finding_id=finding_id,
            decision="confirmed",
            comment="Unauthorized review",
        )


def test_list_exploration_sessions_supports_project_and_status_filters(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    service = ExplorationService()
    user = _make_user(project_ids=["demo"])

    completed = service.create_session(
        user=user,
        group_id="grp_demo",
        project_key="demo",
        target_url="https://demo.example.com/login",
        charter="围绕登录与认证链路做探索",
    )
    service.create_session(
        user=_make_user(project_ids=["proj2"]),
        group_id="grp_proj2",
        project_key="proj2",
        target_url="https://proj2.example.com/home",
        charter="做一轮通用回归探索",
    )

    sessions = service.list_sessions(
        user=user,
        project_key="demo",
        status="completed",
        limit=5,
    )

    assert sessions["count"] == 1
    assert sessions["sessions"][0]["session_id"] == completed["session_id"]
    assert sessions["sessions"][0]["project_key"] == "demo"
    assert sessions["sessions"][0]["finding_count"] >= 1
