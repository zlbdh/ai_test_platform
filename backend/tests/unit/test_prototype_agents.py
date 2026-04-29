# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import commander as commander_router
from services.prototype_agents import (
    PrototypeAgentsService,
    PrototypeFinding,
    PrototypeReporter,
    PrototypeSourceResolver,
    PrototypeWorkerResult,
    ResolvedPrototypeSource,
)


class _DummyCommander:
    def __init__(self) -> None:
        self._missions = {}
        self.saved = 0

    def get_mission(self, mission_id: str):
        return self._missions.get(mission_id)

    def get_mission_logs(self, mission_id: str, since_index: int = 0):
        mission = self._missions.get(mission_id) or {}
        return (mission.get("logs") or [])[since_index:]

    def _save_missions(self):
        self.saved += 1


def _build_resolved_source() -> ResolvedPrototypeSource:
    return ResolvedPrototypeSource(
        source_type="url",
        source="https://demo.example.com/prototype",
        source_label="demo.example.com/prototype",
        entry_url="https://demo.example.com/prototype",
        entry_path="https://demo.example.com/prototype",
        source_path="https://demo.example.com/prototype",
        discovered_pages=[
            {
                "title": "home",
                "url": "https://demo.example.com/prototype",
                "file_uri": "https://demo.example.com/prototype",
                "local_path": "",
                "relative_path": "/",
            }
        ],
        playbook_context={},
    )


def test_source_resolver_supports_file_and_directory(tmp_path):
    resolver = PrototypeSourceResolver()
    html_file = tmp_path / "index.html"
    html_file.write_text("<html><title>Demo</title><body><button>Go</button></body></html>", encoding="utf-8")
    nested_dir = tmp_path / "prototype"
    nested_dir.mkdir()
    (nested_dir / "index.html").write_text("<html><title>Home</title></html>", encoding="utf-8")
    (nested_dir / "approval.html").write_text("<html><title>Approval</title></html>", encoding="utf-8")

    file_result = resolver.resolve(source_type="file", source=str(html_file))
    directory_result = resolver.resolve(source_type="directory", source=str(nested_dir))

    assert file_result.source_type == "file"
    assert file_result.source_label == "index.html"
    assert file_result.entry_path.endswith("index.html")
    assert len(file_result.discovered_pages) == 1

    assert directory_result.source_type == "directory"
    assert directory_result.entry_path.endswith("index.html")
    assert [page["relative_path"] for page in directory_result.discovered_pages] == ["approval.html", "index.html"]


def test_source_resolver_injects_sample_platform_playbook_context():
    resolver = PrototypeSourceResolver()

    resolved = resolver.resolve(
        source_type="url",
        source="https://demo.example.com/prototype",
        playbook_id="sample-platform-prototype",
    )

    assert resolved.playbook_context["catalog"]["playbook_id"] == "sample-platform-prototype"
    assert "mapping_summary" in resolved.playbook_context
    assert "critical_pages" in resolved.playbook_context
    assert "module_coverage_rate" in resolved.playbook_context


def test_reporter_sorts_findings_by_severity():
    reporter = PrototypeReporter()
    mission = {"mission_id": "proto001", "playbook_id": "sample-platform-prototype"}
    resolved_source = _build_resolved_source()
    worker_results = [
        PrototypeWorkerResult(
            agent_id="perf",
            status="success",
            provider="mock-lighthouse",
            started_at="2026-03-31T10:00:00",
            finished_at="2026-03-31T10:00:01",
            payload={"score": 72},
            normalized_findings=[
                PrototypeFinding(
                    agent_id="perf",
                    severity="medium",
                    title="性能预警（Mock Lighthouse）",
                    summary="当前 mock 性能评分为 72",
                    category="mock_perf_warning",
                    provider="mock-lighthouse",
                ).to_dict()
            ],
        ),
        PrototypeWorkerResult(
            agent_id="flow",
            status="error",
            provider="playwright-flow",
            started_at="2026-03-31T10:00:00",
            finished_at="2026-03-31T10:00:01",
            payload={"failures": ["关键页面缺失"]},
            normalized_findings=[
                PrototypeFinding(
                    agent_id="flow",
                    severity="blocking",
                    title="流程连通性存在问题",
                    summary="关键页面未映射到原型：审批流",
                    category="blocking_prototype_gap",
                    provider="playwright-flow",
                ).to_dict()
            ],
        ),
        PrototypeWorkerResult(
            agent_id="a11y",
            status="error",
            provider="local-a11y-audit",
            started_at="2026-03-31T10:00:00",
            finished_at="2026-03-31T10:00:01",
            payload={"violations": 1},
            normalized_findings=[
                PrototypeFinding(
                    agent_id="a11y",
                    severity="high",
                    title="color-contrast",
                    summary="对比度不足",
                    category="wcag_violation",
                    provider="local-a11y-audit",
                ).to_dict()
            ],
        ),
    ]

    report = reporter.build_report(
        mission=mission,
        resolved_source=resolved_source,
        worker_results=worker_results,
    )

    assert [item["severity"] for item in report.findings] == ["blocking", "high", "medium"]
    assert report.summary["finding_count"] == 3
    assert report.quality_gate_metrics["blocking_prototype_gap_count"] == 1
    assert any("Flow Worker" in item for item in report.recommendations)


@pytest.mark.asyncio
async def test_ab_worker_skips_without_compare_source():
    service = PrototypeAgentsService()

    result = await service._run_ab_worker(  # pylint: disable=protected-access
        mission={"wcag_level": "AA"},
        resolved_source=_build_resolved_source(),
        compare_source=None,
        provider="mock-chromatic",
    )

    assert result.agent_id == "ab"
    assert result.status == "skipped"
    assert result.payload["changedComponents"] == []
    assert "compare_source" in result.payload["reason"]


@pytest.mark.asyncio
async def test_run_mission_completes_with_mixed_worker_results(monkeypatch):
    service = PrototypeAgentsService()
    commander = _DummyCommander()
    payload = {
        "source_type": "url",
        "source": "https://demo.example.com/prototype",
        "compare_source": "",
        "playbook_id": "",
        "worker_switches": {
            "visual": True,
            "flow": True,
            "ab": True,
            "a11y": False,
            "perf": True,
        },
        "providers": {},
        "wcag_level": "AA",
    }
    mission = service.create_mission(payload, mission_id="proto001")
    commander._missions["proto001"] = mission
    resolved_source = _build_resolved_source()

    async def _fake_run_worker(*, worker_id: str, **kwargs):
        _ = kwargs
        if worker_id == "visual":
            return PrototypeWorkerResult(
                agent_id="visual",
                status="success",
                provider="local-visual-regression",
                started_at="2026-03-31T10:00:00",
                finished_at="2026-03-31T10:00:01",
                payload={"diffPixels": 0, "diffPercentage": 0, "screenshots": []},
                normalized_findings=[],
            )
        if worker_id == "flow":
            return PrototypeWorkerResult(
                agent_id="flow",
                status="error",
                provider="playwright-flow",
                started_at="2026-03-31T10:00:00",
                finished_at="2026-03-31T10:00:01",
                payload={"steps": [], "failures": [{"type": "critical_page_missing"}]},
                normalized_findings=[
                    PrototypeFinding(
                        agent_id="flow",
                        severity="blocking",
                        title="流程连通性存在问题",
                        summary="关键页面未映射到原型：审批流",
                        category="blocking_prototype_gap",
                        provider="playwright-flow",
                    ).to_dict()
                ],
            )
        if worker_id == "ab":
            return PrototypeWorkerResult(
                agent_id="ab",
                status="skipped",
                provider="mock-chromatic",
                started_at="2026-03-31T10:00:00",
                finished_at="2026-03-31T10:00:00",
                payload={"reason": "未提供 compare_source，A/B 结构对比已跳过", "changedComponents": [], "comparedVersions": []},
                normalized_findings=[],
            )
        return PrototypeWorkerResult(
            agent_id="perf",
            status="success",
            provider="mock-lighthouse",
            started_at="2026-03-31T10:00:00",
            finished_at="2026-03-31T10:00:01",
            payload={"score": 72, "lcp": 2.8, "cls": 0.09, "fid": 34},
            normalized_findings=[
                PrototypeFinding(
                    agent_id="perf",
                    severity="medium",
                    title="性能预警（Mock Lighthouse）",
                    summary="当前 mock 性能评分为 72",
                    category="mock_perf_warning",
                    provider="mock-lighthouse",
                ).to_dict()
            ],
        )

    monkeypatch.setattr(service._resolver, "resolve", lambda **kwargs: resolved_source)
    monkeypatch.setattr(service, "_run_worker", _fake_run_worker)
    monkeypatch.setattr(service, "_sync_execution_group", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "_save_artifact", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "_persist_summary_record", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "_save", lambda *args, **kwargs: None)

    result = await service.run_mission(commander, "proto001", payload)

    assert result["status"] == "completed"
    assert result["test_tasks_count"] == 4
    assert result["test_results_count"] == 4
    assert [item["agent_id"] for item in result["worker_results"]] == ["visual", "flow", "ab", "perf"]
    assert [item["severity"] for item in result["report"]["findings"]] == ["blocking", "medium"]
    assert result["bug_summary"][0]["status"] == "blocking"
    assert result["agent_states"]["orchestrator"] == "success"
    assert result["agent_states"]["reporter"] == "success"


def test_commander_prototype_routes(monkeypatch):
    app = FastAPI()
    app.include_router(commander_router.router)
    client = TestClient(app)
    commander = _DummyCommander()
    service = PrototypeAgentsService()

    async def _fake_run_mission(fake_commander, mission_id: str, payload):
        fake_commander._missions[mission_id]["status"] = "completed"
        fake_commander._missions[mission_id]["report"] = {"summary": {"finding_count": 0}}
        return fake_commander._missions[mission_id]

    monkeypatch.setattr("agents.commander.get_commander", lambda: commander)
    monkeypatch.setattr(commander_router, "get_prototype_agents_service", lambda: service)
    monkeypatch.setattr(service, "run_mission", _fake_run_mission)

    response = client.post(
        "/api/commander/prototype/run",
        json={
            "source_type": "url",
            "source": "https://demo.example.com/prototype",
            "compare_source": "",
            "playbook_id": "sample-platform-prototype",
            "worker_switches": {
                "visual": True,
                "flow": True,
                "ab": False,
                "a11y": True,
                "perf": True,
            },
            "providers": {
                "perf": "mock-lighthouse",
            },
            "wcag_level": "AA",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mission_kind"] == "prototype_agents"
    assert body["source"] == "https://demo.example.com/prototype"
    assert body["playbook_id"] == "sample-platform-prototype"
    assert body["worker_switches"]["ab"] is False
    assert body["providers"]["perf"] == "mock-lighthouse"

    status_response = client.get(f"/api/commander/prototype/status/{body['mission_id']}")
    missions_response = client.get("/api/commander/prototype/missions?limit=5")

    assert status_response.status_code == 200
    assert status_response.json()["mission_id"] == body["mission_id"]
    assert missions_response.status_code == 200
    assert missions_response.json()[0]["mission_id"] == body["mission_id"]
