# -*- coding: utf-8 -*-
from contextlib import contextmanager
import sqlite3
from types import SimpleNamespace

from services.exploration_service import ExplorationService
from services.release_risk_service import ReleaseRiskService


def _make_user(role: str = "tester", project_ids=None):
    return SimpleNamespace(
        user_id="user_demo",
        username="demo",
        role=SimpleNamespace(value=role),
        project_ids=list(project_ids or []),
    )


def _patch_temp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "release_risk.db"

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
    monkeypatch.setattr("services.release_risk_service.get_connection", _get_connection)


def test_release_risk_blocks_production_and_human_review(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    exploration = ExplorationService()
    release = ReleaseRiskService()
    monkeypatch.setattr("services.release_risk_service.get_exploration_service", lambda: exploration)

    session = exploration.create_session(
        user=_make_user(project_ids=["demo"]),
        group_id="",
        project_key="demo",
        target_url="https://demo.example.com/payment",
        charter="覆盖支付与下单主链路",
    )

    assessment = release.create_assessment(
        user=_make_user(project_ids=["demo"]),
        project_key="demo",
        environment="production",
        exploration_session_ids=[session["session_id"]],
        required_tests_passed=True,
        change_summary="Payment page styling and interaction updates",
    )

    assert assessment["release_risk"] in {"high", "critical"}
    assert assessment["auto_release_eligible"] is False
    blocker_types = {item["type"] for item in assessment["blockers"]}
    assert "production_requires_manual_approval" in blocker_types
    assert "human_review_pending" in blocker_types
    assert assessment["policy_hit"]["review_policy_mode"] == "conservative"
    assert assessment["policy_hit"]["review_blocked"] is True
    assert assessment["evidence"]["review_summary"]["pending"] >= 1
    assert assessment["evidence"]["pending_review_findings"]


def test_release_risk_allows_low_risk_nonprod_auto_release(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    exploration = ExplorationService()
    release = ReleaseRiskService()
    monkeypatch.setattr("services.release_risk_service.get_exploration_service", lambda: exploration)

    session = exploration.create_session(
        user=_make_user(project_ids=["demo"]),
        group_id="",
        project_key="demo",
        target_url="https://demo.example.com/home",
        charter="做一轮通用回归探索",
    )

    assessment = release.create_assessment(
        user=_make_user(project_ids=["demo"]),
        project_key="demo",
        environment="staging",
        exploration_session_ids=[session["session_id"]],
        required_tests_passed=True,
        change_summary="Minor home page styling update",
    )

    assert assessment["release_risk"] == "low"
    assert assessment["auto_release_eligible"] is True
    assert assessment["policy_hit"]["nonprod_only"] is True
    assert assessment["policy_hit"]["review_blocked"] is False
    assert assessment["evidence"]["review_summary"]["effective"] >= 1


def test_release_risk_uses_review_status_for_blockers_and_effective_findings(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    exploration = ExplorationService()
    release = ReleaseRiskService()
    monkeypatch.setattr("services.release_risk_service.get_exploration_service", lambda: exploration)
    user = _make_user(project_ids=["demo"])

    session = exploration.create_session(
        user=user,
        group_id="",
        project_key="demo",
        target_url="https://demo.example.com/search",
        charter="覆盖搜索、浏览与登录主链路",
    )
    findings = {item["title"]: item for item in session["findings"]}
    login_finding = findings["The primary sign-in flow requires close review"]
    search_finding = findings["The discovery path needs additional experience assessment"]

    assessment_pending = release.create_assessment(
        user=user,
        project_key="demo",
        environment="staging",
        exploration_session_ids=[session["session_id"]],
        required_tests_passed=True,
        change_summary="Search and login flow updates",
    )

    pending_blockers = {item["type"] for item in assessment_pending["blockers"]}
    assert "human_review_pending" in pending_blockers
    assert assessment_pending["auto_release_eligible"] is False

    exploration.review_finding(
        user=user,
        finding_id=login_finding["finding_id"],
        decision="confirmed",
        comment="Manual review requires retaining the block",
    )
    exploration.review_finding(
        user=user,
        finding_id=search_finding["finding_id"],
        decision="dismissed",
        comment="Manually rejected the experience issue",
    )

    assessment_reviewed = release.create_assessment(
        user=user,
        project_key="demo",
        environment="staging",
        exploration_session_ids=[session["session_id"]],
        required_tests_passed=True,
        change_summary="Reassess after review",
    )

    reviewed_blockers = {item["type"] for item in assessment_reviewed["blockers"]}
    assert "human_review_pending" not in reviewed_blockers
    assert "confirmed_issue_requires_manual_release" in reviewed_blockers
    assert assessment_reviewed["auto_release_eligible"] is False
    assert assessment_reviewed["policy_hit"]["review_blocked"] is True
    assert assessment_reviewed["evidence"]["review_summary"] == {
        "pending": 0,
        "confirmed": 1,
        "dismissed": 1,
        "active": 1,
        "effective": 1,
    }
    assert assessment_reviewed["evidence"]["confirmed_findings"] == [login_finding["finding_id"]]
    assert assessment_reviewed["evidence"]["pending_review_findings"] == []
    assert assessment_reviewed["evidence"]["high_risk_findings"] == []
    assert assessment_reviewed["release_risk"] == "high"


def test_list_release_risk_assessments_supports_filters(monkeypatch, tmp_path):
    _patch_temp_db(monkeypatch, tmp_path)
    exploration = ExplorationService()
    release = ReleaseRiskService()
    monkeypatch.setattr("services.release_risk_service.get_exploration_service", lambda: exploration)
    user = _make_user(project_ids=["demo"])

    session = exploration.create_session(
        user=user,
        group_id="",
        project_key="demo",
        target_url="https://demo.example.com/home",
        charter="做一轮通用回归探索",
    )
    release.create_assessment(
        user=user,
        project_key="demo",
        environment="staging",
        exploration_session_ids=[session["session_id"]],
        required_tests_passed=True,
        change_summary="Minor home page styling update",
    )
    release.create_assessment(
        user=_make_user(project_ids=["proj2"]),
        project_key="proj2",
        environment="production",
        exploration_session_ids=[],
        required_tests_passed=False,
        change_summary="High-risk change",
    )

    payload = release.list_assessments(
        user=user,
        project_key="demo",
        environment="staging",
        auto_release_eligible=True,
        limit=5,
    )

    assert payload["count"] == 1
    assert payload["assessments"][0]["project_key"] == "demo"
    assert payload["assessments"][0]["environment"] == "staging"
    assert payload["assessments"][0]["auto_release_eligible"] is True
