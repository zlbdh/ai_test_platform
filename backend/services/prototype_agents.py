# -*- coding: utf-8 -*-
"""
Prototype Agents Service
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

import httpx

from services.execution_center_service import get_execution_center_service

logger = logging.getLogger(__name__)

MISSION_KIND = "prototype_agents"
PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE = "sample-platform-prototype"
DEFAULT_WCAG_LEVEL = "AA"
WORKER_ORDER = ("visual", "flow", "ab", "a11y", "perf")
AGENT_ORDER = ("orchestrator", "visual", "flow", "ab", "a11y", "perf", "reporter")
DEFAULT_WORKER_SWITCHES = {
    "visual": True,
    "flow": True,
    "ab": True,
    "a11y": True,
    "perf": True,
}
DEFAULT_PROVIDERS = {
    "visual": "local-visual-regression",
    "flow": "playwright-flow",
    "ab": "mock-chromatic",
    "a11y": "local-a11y-audit",
    "perf": "mock-lighthouse",
}
SUCCESS_STATUSES = {"success", "completed", "new_baseline"}
FAILURE_STATUSES = {"error", "failed", "timeout"}
SEVERITY_ORDER = {"blocking": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _now_iso() -> str:
    return datetime.now().isoformat()


def _coerce_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _duration_ms(started_at: str, finished_at: str) -> int:
    try:
        start = datetime.fromisoformat(started_at)
        end = datetime.fromisoformat(finished_at)
    except ValueError:
        return 0
    return max(0, int((end - start).total_seconds() * 1000))


def _safe_name(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "").strip())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "prototype"


def _hash_text(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()[:12]


def _severity_rank(severity: str) -> int:
    return SEVERITY_ORDER.get(str(severity or "").strip().lower(), len(SEVERITY_ORDER))


def _is_url(value: str) -> bool:
    parsed = urlparse(str(value or "").strip())
    return parsed.scheme in {"http", "https"}


def _read_text_from_source(source_type: str, source: str) -> str:
    if source_type == "url":
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(source)
            response.raise_for_status()
            return response.text
    path = Path(source)
    if path.is_dir():
        html_files = sorted(path.rglob("*.html"))
        if not html_files:
            return ""
        return html_files[0].read_text(encoding="utf-8", errors="ignore")
    if path.exists():
        return path.read_text(encoding="utf-8", errors="ignore")
    return ""


def _extract_html_signals(html: str) -> Dict[str, Any]:
    if not html:
        return {
            "title": "",
            "components": {},
            "interactive_count": 0,
            "text_length": 0,
        }
    lower = html.lower()
    components = {
        "header": len(re.findall(r"<header\b", lower)),
        "nav": len(re.findall(r"<nav\b", lower)),
        "main": len(re.findall(r"<main\b", lower)),
        "section": len(re.findall(r"<section\b", lower)),
        "form": len(re.findall(r"<form\b", lower)),
        "table": len(re.findall(r"<table\b", lower)),
        "dialog": len(re.findall(r"<dialog\b", lower)),
        "input": len(re.findall(r"<input\b", lower)),
        "button": len(re.findall(r"<button\b", lower)),
        "select": len(re.findall(r"<select\b", lower)),
        "textarea": len(re.findall(r"<textarea\b", lower)),
        "aside": len(re.findall(r"<aside\b", lower)),
    }
    title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""
    interactive_count = sum(components[key] for key in ("nav", "form", "input", "button", "select", "textarea"))
    text_length = len(re.sub(r"<[^>]+>", " ", html))
    return {
        "title": title,
        "components": components,
        "interactive_count": interactive_count,
        "text_length": text_length,
    }


@dataclass
class PrototypeFinding:
    agent_id: str
    severity: str
    title: str
    summary: str
    category: str
    provider: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    execution_record_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["finding_id"] = f"{self.agent_id}-{_hash_text(f'{self.title}|{self.summary}|{self.category}')}"
        return payload


@dataclass
class PrototypeWorkerResult:
    agent_id: str
    status: str
    provider: str
    started_at: str
    finished_at: str
    payload: Dict[str, Any]
    normalized_findings: List[Dict[str, Any]] = field(default_factory=list)
    execution_record_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PrototypeReport:
    summary: Dict[str, Any]
    findings: List[Dict[str, Any]]
    recommendations: List[str]
    worker_results: List[Dict[str, Any]]
    quality_gate_metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ResolvedPrototypeSource:
    source_type: str
    source: str
    source_label: str
    entry_url: str
    entry_path: str
    source_path: str
    discovered_pages: List[Dict[str, Any]]
    playbook_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PrototypeSourceResolver:
    """Resolve a URL, local file, or directory and incorporate project bundle context."""

    def resolve(
        self,
        *,
        source_type: str,
        source: str,
        playbook_id: str = "",
    ) -> ResolvedPrototypeSource:
        normalized_type = str(source_type or "").strip().lower()
        normalized_source = str(source or "").strip()
        if normalized_type not in {"url", "file", "directory"}:
            raise ValueError(f"Unsupported source_type: {source_type}")
        if not normalized_source:
            raise ValueError("source must not be empty")

        if normalized_type == "url":
            if not _is_url(normalized_source):
                raise ValueError("A URL source must start with http:// or https://")
            parsed = urlparse(normalized_source)
            source_label = f"{parsed.netloc}{parsed.path or '/'}".strip()
            pages = [
                {
                    "title": source_label,
                    "url": normalized_source,
                    "file_uri": normalized_source,
                    "local_path": "",
                    "relative_path": parsed.path or "/",
                }
            ]
            resolved = ResolvedPrototypeSource(
                source_type="url",
                source=normalized_source,
                source_label=source_label,
                entry_url=normalized_source,
                entry_path=normalized_source,
                source_path=normalized_source,
                discovered_pages=pages,
            )
        else:
            path = Path(normalized_source).expanduser().resolve()
            if normalized_type == "file":
                if not path.exists() or not path.is_file():
                    raise ValueError(f"Prototype file not found: {path}")
                pages = [
                    {
                        "title": path.stem,
                        "url": path.as_uri(),
                        "file_uri": path.as_uri(),
                        "local_path": str(path),
                        "relative_path": path.name,
                    }
                ]
                resolved = ResolvedPrototypeSource(
                    source_type="file",
                    source=str(path),
                    source_label=path.name,
                    entry_url=path.as_uri(),
                    entry_path=str(path),
                    source_path=str(path),
                    discovered_pages=pages,
                )
            else:
                if not path.exists() or not path.is_dir():
                    raise ValueError(f"Prototype directory not found: {path}")
                html_files = sorted(path.rglob("*.html"))
                if not html_files:
                    raise ValueError(f"No HTML prototypes found in directory: {path}")
                entry = next((item for item in html_files if item.name.lower() == "index.html"), html_files[0])
                pages = [
                    {
                        "title": item.stem,
                        "url": item.as_uri(),
                        "file_uri": item.as_uri(),
                        "local_path": str(item),
                        "relative_path": item.relative_to(path).as_posix(),
                    }
                    for item in html_files[:20]
                ]
                resolved = ResolvedPrototypeSource(
                    source_type="directory",
                    source=str(path),
                    source_label=path.name,
                    entry_url=entry.as_uri(),
                    entry_path=str(entry),
                    source_path=str(path),
                    discovered_pages=pages,
                )

        if playbook_id == PLAYBOOK_ID_SAMPLE_PLATFORM_PLATFORM_PROTOTYPE:
            resolved.playbook_context = self._load_sample_platform_platform_context()
        return resolved

    def _load_sample_platform_platform_context(self) -> Dict[str, Any]:
        from core.sample_platform_playbook import (
            get_catalog_entry,
            get_quality_gate_rules,
            get_requirement_playbook,
        )

        playbook = get_requirement_playbook()
        page_mappings = playbook.get("page_mappings") or []
        module_names = {
            str(item.get("module_name") or "").strip()
            for item in page_mappings
            if str(item.get("module_name") or "").strip()
        }
        mapped_module_names = {
            str(item.get("module_name") or "").strip()
            for item in page_mappings
            if str(item.get("mapping_status") or "").strip() == "mapped"
        }
        critical_pages = [
            {
                "mapping_id": item.get("mapping_id"),
                "module_name": item.get("module_name"),
                "page_name": item.get("page_name"),
                "route": item.get("route"),
                "recommended_test_types": item.get("recommended_test_types") or [],
                "prototype_source": item.get("prototype_source") or {},
            }
            for item in page_mappings
            if item.get("critical")
        ]
        mapping_summary = dict(playbook.get("mapping_summary") or {})
        return {
            "catalog": get_catalog_entry(),
            "mapping_summary": mapping_summary,
            "quality_gate_rules": get_quality_gate_rules(),
            "waves": playbook.get("waves") or [],
            "critical_pages": critical_pages,
            "prototype_assets": playbook.get("prototype_assets") or [],
            "module_coverage_rate": round(
                (len(mapped_module_names) / len(module_names)) if module_names else 1.0,
                4,
            ),
        }


class PrototypeReporter:
    """Normalize Worker output into the final report."""

    def build_report(
        self,
        *,
        mission: Dict[str, Any],
        resolved_source: ResolvedPrototypeSource,
        worker_results: Iterable[PrototypeWorkerResult],
    ) -> PrototypeReport:
        worker_result_list = [item.to_dict() for item in worker_results]
        findings: List[Dict[str, Any]] = []
        for result in worker_results:
            findings.extend(result.normalized_findings)

        findings.sort(
            key=lambda item: (
                _severity_rank(str(item.get("severity") or "")),
                str(item.get("agent_id") or ""),
                str(item.get("title") or ""),
            )
        )

        severity_breakdown = {key: 0 for key in SEVERITY_ORDER}
        for finding in findings:
            severity = str(finding.get("severity") or "info").strip().lower()
            severity_breakdown[severity] = severity_breakdown.get(severity, 0) + 1

        summary = {
            "mission_id": mission.get("mission_id"),
            "mission_kind": MISSION_KIND,
            "source_type": resolved_source.source_type,
            "source_label": resolved_source.source_label,
            "entry_url": resolved_source.entry_url,
            "playbook_id": mission.get("playbook_id") or "",
            "total_workers": len(worker_result_list),
            "success_workers": sum(1 for item in worker_result_list if item["status"] in SUCCESS_STATUSES),
            "error_workers": sum(1 for item in worker_result_list if item["status"] in FAILURE_STATUSES),
            "skipped_workers": sum(1 for item in worker_result_list if item["status"] == "skipped"),
            "finding_count": len(findings),
            "severity_breakdown": severity_breakdown,
        }

        quality_gate_metrics = self._build_quality_gate_metrics(
            resolved_source=resolved_source,
            findings=findings,
        )
        recommendations = self._build_recommendations(findings)
        return PrototypeReport(
            summary=summary,
            findings=findings,
            recommendations=recommendations,
            worker_results=worker_result_list,
            quality_gate_metrics=quality_gate_metrics,
        )

    def _build_quality_gate_metrics(
        self,
        *,
        resolved_source: ResolvedPrototypeSource,
        findings: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        playbook_context = resolved_source.playbook_context or {}
        mapping_summary = playbook_context.get("mapping_summary") or {}
        module_coverage_rate = playbook_context.get("module_coverage_rate")
        if module_coverage_rate is None:
            module_coverage_rate = 1.0 if resolved_source.discovered_pages else 0.0
        page_mapping_rate = mapping_summary.get("mapping_rate")
        if page_mapping_rate is None:
            page_mapping_rate = 1.0 if resolved_source.discovered_pages else 0.0

        return {
            "module_coverage_rate": round(_safe_float(module_coverage_rate, 0.0), 4),
            "page_mapping_rate": round(_safe_float(page_mapping_rate, 0.0), 4),
            "blocking_prototype_gap_count": sum(1 for item in findings if item.get("severity") == "blocking"),
            "critical_field_missing_count": sum(1 for item in findings if item.get("category") == "critical_field_missing"),
            "critical_state_transition_gap_count": sum(
                1 for item in findings if item.get("category") == "critical_state_transition_gap"
            ),
        }

    def _build_recommendations(self, findings: List[Dict[str, Any]]) -> List[str]:
        recommendations: List[str] = []
        severities = {str(item.get("severity") or "info") for item in findings}
        agent_ids = {str(item.get("agent_id") or "") for item in findings}
        categories = {str(item.get("category") or "") for item in findings}

        if "blocking" in severities:
            recommendations.append("Resolve blocking prototype discrepancies and critical pages first. Restore the primary workflow structure before addressing styling details.")
        if "flow" in agent_ids:
            recommendations.append("Resolve workflow breaks identified by the Flow Worker so entry pages, critical transitions, and page structures are connected.")
        if "a11y" in agent_ids:
            recommendations.append("Prioritize accessibility labels, alt text, language declarations, and contrast; resolve WCAG A/AA blockers first.")
        if "visual" in agent_ids:
            recommendations.append("Confirm whether visual differences are intended. Update the baseline for intended changes; otherwise revert critical layout changes.")
        if "perf" in agent_ids:
            recommendations.append("Performance results currently come from Mock Lighthouse. Treat them as warning signals before deciding whether to validate with real Lighthouse.")
        if "ab" in agent_ids:
            recommendations.append("Prioritize structural component changes in A/B comparisons. Handle styling adjustments through the visual regression baseline workflow.")
        if "critical_state_transition_gap" in categories:
            recommendations.append("Add pages and feedback areas for critical state transitions to avoid gaps in approvals, listing/unlisting, and exception resolution.")

        return recommendations[:6] or ["No obvious issues were found. Add real Percy, Chromatic, or Lighthouse providers to improve confidence."]


class PrototypeAgentsService:
    def __init__(self) -> None:
        self._resolver = PrototypeSourceResolver()
        self._reporter = PrototypeReporter()
        self._artifacts_root = Path(__file__).resolve().parent.parent / "data" / "prototype_agents"
        self._artifacts_root.mkdir(parents=True, exist_ok=True)

    def create_mission(self, payload: Dict[str, Any], mission_id: Optional[str] = None) -> Dict[str, Any]:
        normalized_switches = self._normalize_worker_switches(payload.get("worker_switches") or {})
        normalized_providers = self._normalize_providers(payload.get("providers") or {})
        now = _now_iso()
        mission_id = mission_id or uuid.uuid4().hex[:8]
        source = str(payload.get("source") or "").strip()
        label = source or "Untitled Prototype"
        return {
            "mission_id": mission_id,
            "mission_kind": MISSION_KIND,
            "user_input": f"Prototype Test · {label}",
            "target_url": source if payload.get("source_type") == "url" else "",
            "status": "pending",
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "trace_id": None,
            "strategy": {
                "worker_switches": normalized_switches,
                "providers": normalized_providers,
                "wcag_level": str(payload.get("wcag_level") or DEFAULT_WCAG_LEVEL),
            },
            "test_tasks_count": 0,
            "test_results_count": 0,
            "report": None,
            "logs": [],
            "execution_group_id": mission_id,
            "execution_center_path": f"/history?group={mission_id}",
            "bug_summary": [],
            "source_type": str(payload.get("source_type") or "").strip(),
            "source": source,
            "compare_source": str(payload.get("compare_source") or "").strip(),
            "playbook_id": str(payload.get("playbook_id") or "").strip(),
            "worker_switches": normalized_switches,
            "providers": normalized_providers,
            "wcag_level": str(payload.get("wcag_level") or DEFAULT_WCAG_LEVEL),
            "agent_states": {agent_id: "idle" for agent_id in AGENT_ORDER},
            "worker_results": [],
            "source_context": None,
        }

    def list_missions(self, commander: Any, limit: int = 20) -> List[Dict[str, Any]]:
        missions: List[Dict[str, Any]] = []
        for item in getattr(commander, "_missions", {}).values():
            if not isinstance(item, dict):
                continue
            if item.get("mission_kind") != MISSION_KIND:
                continue
            missions.append(item)
        missions.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return missions[:limit]

    async def run_mission(self, commander: Any, mission_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        mission = getattr(commander, "_missions", {}).get(mission_id)
        if not isinstance(mission, dict):
            raise ValueError(f"Prototype mission not found: {mission_id}")

        mission["started_at"] = _now_iso()
        mission["status"] = "parsing"
        self._set_agent_state(mission, "orchestrator", "running")
        self._sync_execution_group(mission, mission["status"])
        self._append_log(mission, "Resolving prototype source and project bundle context", data={"agent_id": "orchestrator", "agent_status": "running"})
        self._save(commander)

        resolved_source = self._resolver.resolve(
            source_type=payload.get("source_type") or "",
            source=payload.get("source") or "",
            playbook_id=payload.get("playbook_id") or "",
        )
        compare_resolved = None
        if payload.get("compare_source"):
            compare_resolved = self._resolver.resolve(
                source_type=payload.get("source_type") or "",
                source=payload.get("compare_source") or "",
                playbook_id=payload.get("playbook_id") or "",
            )

        mission["target_url"] = resolved_source.entry_url
        mission["source_context"] = resolved_source.to_dict()
        self._append_log(
            mission,
            "Prototype source resolved",
            data={
                "agent_id": "orchestrator",
                "resolved_pages": len(resolved_source.discovered_pages),
                "entry_url": resolved_source.entry_url,
                "playbook_id": mission.get("playbook_id") or "",
            },
        )
        self._save_artifact(mission_id, "request.json", payload)
        self._save_artifact(mission_id, "source_context.json", mission["source_context"])

        mission["status"] = "dispatching"
        self._sync_execution_group(mission, mission["status"])
        worker_switches = self._normalize_worker_switches(payload.get("worker_switches") or {})
        enabled_workers = [worker for worker in WORKER_ORDER if worker_switches.get(worker, True)]
        mission["test_tasks_count"] = len(enabled_workers)
        self._append_log(
            mission,
            f"Orchestrator dispatched {len(enabled_workers)} Worker tasks",
            data={"agent_id": "orchestrator", "workers": enabled_workers},
        )
        self._save(commander)

        mission["status"] = "executing"
        self._sync_execution_group(mission, mission["status"])
        worker_tasks = [
            self._run_worker(
                commander=commander,
                mission=mission,
                worker_id=worker_id,
                resolved_source=resolved_source,
                compare_source=compare_resolved,
            )
            for worker_id in enabled_workers
        ]
        worker_results = await asyncio.gather(*worker_tasks)
        worker_results.sort(key=lambda item: WORKER_ORDER.index(item.agent_id))
        mission["worker_results"] = [item.to_dict() for item in worker_results]
        mission["test_results_count"] = len(worker_results)
        self._save_artifact(mission_id, "worker_results.json", mission["worker_results"])
        self._set_agent_state(mission, "orchestrator", "success")
        self._save(commander)

        mission["status"] = "reporting"
        self._set_agent_state(mission, "reporter", "running")
        self._sync_execution_group(mission, mission["status"])
        self._append_log(mission, "Reporter is aggregating Worker results", data={"agent_id": "reporter", "agent_status": "running"})
        report = self._reporter.build_report(
            mission=mission,
            resolved_source=resolved_source,
            worker_results=worker_results,
        )
        mission["report"] = report.to_dict()
        mission["bug_summary"] = self._build_bug_summary(report)
        self._set_agent_state(mission, "reporter", "success")
        mission["status"] = "completed"
        mission["completed_at"] = _now_iso()
        self._sync_execution_group(mission, mission["status"])
        self._persist_summary_record(mission)
        self._append_log(
            mission,
            "Prototype testing mission completed",
            data={
                "agent_id": "reporter",
                "finding_count": len(report.findings),
                "blocking_count": report.quality_gate_metrics.get("blocking_prototype_gap_count", 0),
            },
        )
        self._save_artifact(mission_id, "report.json", mission["report"])
        self._save(commander)
        return mission

    def _normalize_worker_switches(self, value: Dict[str, Any]) -> Dict[str, bool]:
        merged = dict(DEFAULT_WORKER_SWITCHES)
        for key in DEFAULT_WORKER_SWITCHES:
            if key in value:
                merged[key] = _coerce_bool(value.get(key), DEFAULT_WORKER_SWITCHES[key])
        return merged

    def _normalize_providers(self, value: Dict[str, Any]) -> Dict[str, str]:
        merged = dict(DEFAULT_PROVIDERS)
        for key in DEFAULT_PROVIDERS:
            if key in value and str(value.get(key) or "").strip():
                merged[key] = str(value.get(key)).strip()
        return merged

    async def _run_worker(
        self,
        *,
        commander: Any,
        mission: Dict[str, Any],
        worker_id: str,
        resolved_source: ResolvedPrototypeSource,
        compare_source: Optional[ResolvedPrototypeSource],
    ) -> PrototypeWorkerResult:
        started_at = _now_iso()
        provider = mission.get("providers", {}).get(worker_id) or DEFAULT_PROVIDERS[worker_id]
        self._set_agent_state(mission, worker_id, "running")
        self._append_log(
            mission,
            f"{worker_id} Worker started",
            data={"agent_id": worker_id, "agent_status": "running", "provider": provider},
        )
        self._save(commander)

        try:
            if worker_id == "visual":
                result = await self._run_visual_worker(mission, resolved_source, provider)
            elif worker_id == "flow":
                result = await self._run_flow_worker(mission, resolved_source, provider)
            elif worker_id == "ab":
                result = await self._run_ab_worker(mission, resolved_source, compare_source, provider)
            elif worker_id == "a11y":
                result = await self._run_a11y_worker(mission, resolved_source, provider)
            elif worker_id == "perf":
                result = await self._run_perf_worker(mission, resolved_source, provider)
            else:
                raise ValueError(f"Unknown worker_id: {worker_id}")
        except Exception as exc:
            logger.exception("[PrototypeAgents] Worker %s failed", worker_id)
            finished_at = _now_iso()
            result = PrototypeWorkerResult(
                agent_id=worker_id,
                status="error",
                provider=provider,
                started_at=started_at,
                finished_at=finished_at,
                payload={"error": str(exc)},
                normalized_findings=[
                    PrototypeFinding(
                        agent_id=worker_id,
                        severity="high",
                        title=f"{worker_id} Worker failed",
                        summary=str(exc),
                        category="worker_runtime_error",
                        provider=provider,
                    ).to_dict()
                ],
            )

        if not result.started_at:
            result.started_at = started_at
        if not result.finished_at:
            result.finished_at = _now_iso()

        record_id = self._persist_worker_record(mission, result, resolved_source)
        result.execution_record_id = record_id
        for finding in result.normalized_findings:
            if not finding.get("execution_record_id") and record_id:
                finding["execution_record_id"] = record_id

        final_agent_status = {
            "skipped": "skipped",
            "error": "error",
        }.get(result.status, "success")
        self._set_agent_state(mission, worker_id, final_agent_status)
        self._append_log(
            mission,
            f"{worker_id} Worker {result.status}",
            level="error" if result.status == "error" else "info",
            data={
                "agent_id": worker_id,
                "agent_status": final_agent_status,
                "provider": result.provider,
                "execution_record_id": record_id,
                "finding_count": len(result.normalized_findings),
            },
        )
        self._save(commander)
        return result

    async def _run_visual_worker(
        self,
        mission: Dict[str, Any],
        resolved_source: ResolvedPrototypeSource,
        provider: str,
    ) -> PrototypeWorkerResult:
        from services.visual_regression import ComparisonResult, get_visual_tester

        started_at = _now_iso()
        screenshot = await self._capture_page_screenshot(resolved_source.entry_url)
        tester = get_visual_tester()
        baseline_name = f"{_safe_name(resolved_source.source_label)}-{_hash_text(resolved_source.entry_url)}"
        comparison = tester.compare(baseline_name, screenshot, threshold=0.01)
        finished_at = _now_iso()

        width = _safe_int(comparison.current.width or comparison.baseline.width, 0)
        height = _safe_int(comparison.current.height or comparison.baseline.height, 0)
        diff_pixels = int((comparison.diff_percentage / 100.0) * max(1, width * height))
        screenshots = [
            {
                "kind": "baseline",
                "path": comparison.baseline.filepath,
                "width": comparison.baseline.width,
                "height": comparison.baseline.height,
            },
            {
                "kind": "current",
                "path": comparison.current.filepath,
                "width": comparison.current.width,
                "height": comparison.current.height,
            },
        ]
        if comparison.diff_filepath:
            screenshots.append({"kind": "diff", "path": comparison.diff_filepath, "width": width, "height": height})

        payload = {
            "baselineName": baseline_name,
            "result": comparison.result.value if hasattr(comparison.result, "value") else str(comparison.result),
            "diffPixels": diff_pixels,
            "diffPercentage": comparison.diff_percentage,
            "screenshots": screenshots,
        }

        findings: List[Dict[str, Any]] = []
        if comparison.result == ComparisonResult.MISMATCH:
            severity = "blocking" if comparison.diff_percentage >= 5 else "high"
            findings.append(
                PrototypeFinding(
                    agent_id="visual",
                    severity=severity,
                    title="Significant visual regression differences",
                    summary=f"Pixel difference: {comparison.diff_percentage:.2f}% (approximately {diff_pixels} px)",
                    category="visual_regression_gap",
                    provider=provider,
                    evidence={
                        "diffPercentage": comparison.diff_percentage,
                        "diffPixels": diff_pixels,
                        "baselineName": baseline_name,
                    },
                ).to_dict()
            )

        return PrototypeWorkerResult(
            agent_id="visual",
            status="success",
            provider=provider,
            started_at=started_at,
            finished_at=finished_at,
            payload=payload,
            normalized_findings=findings,
        )

    async def _run_flow_worker(
        self,
        mission: Dict[str, Any],
        resolved_source: ResolvedPrototypeSource,
        provider: str,
    ) -> PrototypeWorkerResult:
        started_at = _now_iso()
        failures: List[Dict[str, Any]] = []
        steps: List[Dict[str, Any]] = []

        pages_to_visit = resolved_source.discovered_pages[: min(3, len(resolved_source.discovered_pages))]
        for page in pages_to_visit:
            step_started = _now_iso()
            try:
                page_snapshot = await self._inspect_page(page["url"])
                steps.append(
                    {
                        "step": f"goto:{page['relative_path'] or page['title']}",
                        "status": "success",
                        "url": page["url"],
                        "title": page_snapshot.get("title") or page["title"],
                        "clickables": page_snapshot.get("clickables", []),
                        "durationMs": _duration_ms(step_started, _now_iso()),
                    }
                )
            except Exception as exc:
                failures.append(
                    {
                        "type": "page_load_error",
                        "page": page.get("relative_path") or page.get("title"),
                        "message": str(exc),
                    }
                )
                steps.append(
                    {
                        "step": f"goto:{page['relative_path'] or page['title']}",
                        "status": "error",
                        "url": page["url"],
                        "error": str(exc),
                        "durationMs": _duration_ms(step_started, _now_iso()),
                    }
                )

        playbook_context = resolved_source.playbook_context or {}
        critical_missing_pages = (playbook_context.get("mapping_summary") or {}).get("critical_missing_pages") or []
        for missing_page in critical_missing_pages[:6]:
            failures.append(
                {
                    "type": "critical_page_missing",
                    "page": str(missing_page),
                    "message": f"Critical pages not mapped to a prototype: {missing_page}",
                }
            )

        findings: List[Dict[str, Any]] = []
        for failure in failures:
            failure_type = failure.get("type")
            severity = "blocking" if failure_type == "critical_page_missing" else "high"
            category = "blocking_prototype_gap" if failure_type == "critical_page_missing" else "flow_execution_gap"
            findings.append(
                PrototypeFinding(
                    agent_id="flow",
                    severity=severity,
                    title="Workflow connectivity issues",
                    summary=str(failure.get("message") or "A critical workflow cannot continue"),
                    category=category,
                    provider=provider,
                    evidence=failure,
                ).to_dict()
            )

        finished_at = _now_iso()
        return PrototypeWorkerResult(
            agent_id="flow",
            status="error" if failures else "success",
            provider=provider,
            started_at=started_at,
            finished_at=finished_at,
            payload={"steps": steps, "failures": failures},
            normalized_findings=findings,
        )

    async def _run_ab_worker(
        self,
        mission: Dict[str, Any],
        resolved_source: ResolvedPrototypeSource,
        compare_source: Optional[ResolvedPrototypeSource],
        provider: str,
    ) -> PrototypeWorkerResult:
        started_at = _now_iso()
        if compare_source is None:
            finished_at = _now_iso()
            return PrototypeWorkerResult(
                agent_id="ab",
                status="skipped",
                provider=provider,
                started_at=started_at,
                finished_at=finished_at,
                payload={
                    "reason": "compare_source was not provided; A/B structural comparison skipped",
                    "changedComponents": [],
                    "comparedVersions": [],
                },
                normalized_findings=[],
            )

        current_signals = self._compare_signals_for_source(resolved_source)
        compare_signals = self._compare_signals_for_source(compare_source)
        changed_components = self._diff_component_signals(current_signals, compare_signals)

        findings: List[Dict[str, Any]] = []
        for component in changed_components:
            change_type = component.get("changeType")
            if change_type not in {"page_added", "page_removed", "structural_change"}:
                continue
            severity = "medium" if change_type == "structural_change" else "low"
            findings.append(
                PrototypeFinding(
                    agent_id="ab",
                    severity=severity,
                    title="A/B versions differ structurally",
                    summary=f"{component.get('name')} has a {component.get('changeType')} change",
                    category="ab_structural_diff",
                    provider=provider,
                    evidence=component,
                ).to_dict()
            )

        finished_at = _now_iso()
        return PrototypeWorkerResult(
            agent_id="ab",
            status="success",
            provider=provider,
            started_at=started_at,
            finished_at=finished_at,
            payload={
                "changedComponents": changed_components,
                "comparedVersions": [resolved_source.source_label, compare_source.source_label],
            },
            normalized_findings=findings,
        )

    async def _run_a11y_worker(
        self,
        mission: Dict[str, Any],
        resolved_source: ResolvedPrototypeSource,
        provider: str,
    ) -> PrototypeWorkerResult:
        from services.accessibility_testing import AccessibilityTestService

        started_at = _now_iso()
        level = str(mission.get("wcag_level") or DEFAULT_WCAG_LEVEL)
        service = AccessibilityTestService()
        report = await service.audit(resolved_source.entry_url, level)
        payload = report.to_dict() if hasattr(report, "to_dict") else dict(report)
        violations = payload.get("issues") or []
        findings: List[Dict[str, Any]] = []
        for issue in violations[:20]:
            issue_severity = str(issue.get("severity") or "info").strip().lower()
            severity = {
                "critical": "high",
                "major": "medium",
                "minor": "low",
                "info": "info",
            }.get(issue_severity, "info")
            findings.append(
                PrototypeFinding(
                    agent_id="a11y",
                    severity=severity,
                    title=str(issue.get("rule_id") or "a11y issue"),
                    summary=str(issue.get("description") or "Accessibility issues found"),
                    category="wcag_violation",
                    provider=provider,
                    evidence=issue,
                ).to_dict()
            )

        finished_at = _now_iso()
        normalized_payload = {
            "violations": violations,
            "wcagLevel": level,
            "score": payload.get("score"),
            "summary": payload.get("summary"),
        }
        return PrototypeWorkerResult(
            agent_id="a11y",
            status="error" if violations else "success",
            provider=provider,
            started_at=started_at,
            finished_at=finished_at,
            payload=normalized_payload,
            normalized_findings=findings,
        )

    async def _run_perf_worker(
        self,
        mission: Dict[str, Any],
        resolved_source: ResolvedPrototypeSource,
        provider: str,
    ) -> PrototypeWorkerResult:
        started_at = _now_iso()
        perf_snapshot = await self._mock_lighthouse_snapshot(resolved_source.entry_url)
        score = _safe_int(perf_snapshot.get("score"), 0)
        findings: List[Dict[str, Any]] = []
        if score < 90:
            findings.append(
                PrototypeFinding(
                    agent_id="perf",
                    severity="medium" if score < 75 else "low",
                    title="Performance warning (Mock Lighthouse)",
                    summary=f"Current mock performance score: {score}; validate with real Lighthouse later.",
                    category="mock_perf_warning",
                    provider=provider,
                    evidence=perf_snapshot,
                ).to_dict()
            )
        finished_at = _now_iso()
        payload = {
            "score": score,
            "lcp": perf_snapshot.get("lcp"),
            "cls": perf_snapshot.get("cls"),
            "fid": perf_snapshot.get("fid"),
            "providerMode": "mock",
        }
        return PrototypeWorkerResult(
            agent_id="perf",
            status="success",
            provider=provider,
            started_at=started_at,
            finished_at=finished_at,
            payload=payload,
            normalized_findings=findings,
        )

    async def _capture_page_screenshot(self, page_url: str) -> bytes:
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page(viewport={"width": 1440, "height": 960})
                await page.goto(page_url, wait_until="load", timeout=20000)
                await page.wait_for_timeout(600)
                return await page.screenshot(full_page=True)
            finally:
                await browser.close()

    async def _inspect_page(self, page_url: str) -> Dict[str, Any]:
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page(viewport={"width": 1440, "height": 960})
                await page.goto(page_url, wait_until="load", timeout=20000)
                await page.wait_for_timeout(300)
                title = await page.title()
                clickables = await page.evaluate(
                    """
                    () => Array.from(document.querySelectorAll('a[href], button, [role="button"]'))
                      .slice(0, 6)
                      .map((node) => ({
                        tag: node.tagName.toLowerCase(),
                        text: (node.textContent || '').trim().slice(0, 40),
                        href: node.getAttribute('href') || '',
                      }))
                    """
                )
                return {
                    "title": title,
                    "clickables": clickables,
                }
            finally:
                await browser.close()

    async def _mock_lighthouse_snapshot(self, page_url: str) -> Dict[str, Any]:
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page(viewport={"width": 1440, "height": 960})
                await page.goto(page_url, wait_until="load", timeout=20000)
                await page.wait_for_timeout(500)
                raw = await page.evaluate(
                    """
                    () => {
                      const nav = performance.getEntriesByType('navigation')[0] || {};
                      return {
                        domContentLoaded: Number(nav.domContentLoadedEventEnd || 0),
                        loadEvent: Number(nav.loadEventEnd || nav.domComplete || 0),
                        resourceCount: performance.getEntriesByType('resource').length,
                        nodeCount: document.querySelectorAll('*').length,
                      };
                    }
                    """
                )
            finally:
                await browser.close()

        dom_content_loaded = max(0, _safe_float(raw.get("domContentLoaded"), 0.0))
        load_event = max(dom_content_loaded, _safe_float(raw.get("loadEvent"), dom_content_loaded))
        resource_count = _safe_int(raw.get("resourceCount"), 0)
        node_count = _safe_int(raw.get("nodeCount"), 0)
        lcp = round(max(1.2, load_event / 1000.0), 2)
        cls = round(min(0.24, 0.01 + node_count / 18000.0), 3)
        fid = min(120, 12 + resource_count)
        score = int(
            max(
                30,
                min(
                    100,
                    100 - (lcp * 8) - (cls * 120) - min(25, resource_count / 4),
                ),
            )
        )
        return {
            "score": score,
            "lcp": lcp,
            "cls": cls,
            "fid": fid,
            "resourceCount": resource_count,
            "nodeCount": node_count,
        }

    def _compare_signals_for_source(self, resolved_source: ResolvedPrototypeSource) -> Dict[str, Dict[str, Any]]:
        signals: Dict[str, Dict[str, Any]] = {}
        if resolved_source.source_type == "directory":
            root = Path(resolved_source.source_path)
            for html_file in sorted(root.rglob("*.html"))[:30]:
                relative_path = html_file.relative_to(root).as_posix()
                html = html_file.read_text(encoding="utf-8", errors="ignore")
                signals[relative_path] = _extract_html_signals(html)
            return signals

        signal_key = Path(resolved_source.entry_path).name if resolved_source.source_type != "url" else resolved_source.entry_url
        signals[signal_key] = _extract_html_signals(_read_text_from_source(resolved_source.source_type, resolved_source.source))
        return signals

    def _diff_component_signals(
        self,
        current_signals: Dict[str, Dict[str, Any]],
        compare_signals: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        changed: List[Dict[str, Any]] = []
        all_keys = sorted(set(current_signals) | set(compare_signals))
        for key in all_keys:
            current = current_signals.get(key)
            baseline = compare_signals.get(key)
            if current is None:
                changed.append({"name": key, "changeType": "page_removed", "details": {"compare": baseline}})
                continue
            if baseline is None:
                changed.append({"name": key, "changeType": "page_added", "details": {"current": current}})
                continue

            current_components = current.get("components") or {}
            baseline_components = baseline.get("components") or {}
            component_diffs = {
                name: {
                    "current": current_components.get(name, 0),
                    "compare": baseline_components.get(name, 0),
                }
                for name in set(current_components) | set(baseline_components)
                if current_components.get(name, 0) != baseline_components.get(name, 0)
            }
            if component_diffs or current.get("title") != baseline.get("title"):
                changed.append(
                    {
                        "name": key,
                        "changeType": "structural_change",
                        "details": {
                            "title": {"current": current.get("title"), "compare": baseline.get("title")},
                            "components": component_diffs,
                        },
                    }
                )
        return changed[:20]

    def _set_agent_state(self, mission: Dict[str, Any], agent_id: str, status: str) -> None:
        mission.setdefault("agent_states", {})
        mission["agent_states"][agent_id] = status

    def _append_log(
        self,
        mission: Dict[str, Any],
        message: str,
        level: str = "info",
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry = {
            "timestamp": _now_iso(),
            "level": level,
            "message": message,
            "data": data or {},
        }
        mission.setdefault("logs", []).append(entry)
        logger.info("[PrototypeAgents][%s] %s", mission.get("mission_id"), message)
        try:
            from core.event_bus import EventBus

            EventBus.instance().put(
                {
                    "type": "commander_log",
                    "mission_id": mission.get("mission_id"),
                    "level": level,
                    "message": message,
                    "data": data or {},
                    "timestamp": entry["timestamp"],
                }
            )
        except Exception:
            pass

    def _sync_execution_group(self, mission: Dict[str, Any], status: str) -> None:
        try:
            get_execution_center_service().ensure_group(
                group_id=mission["execution_group_id"],
                title=f"Prototype Test · {str(mission.get('source') or '').strip()[:48] or mission['mission_id']}",
                requirement=str(mission.get("source") or mission.get("user_input") or mission["mission_id"]),
                target_url=str(mission.get("target_url") or ""),
                mode=MISSION_KIND,
                source=MISSION_KIND,
                root_task_id=mission["mission_id"],
                session_id=f"{MISSION_KIND}_{mission['mission_id']}",
                created_at=mission.get("started_at") or mission.get("created_at") or _now_iso(),
                status=status,
            )
        except Exception as exc:
            logger.warning("[PrototypeAgents] Failed to synchronize execution-center batch: %s", exc)

    def _persist_worker_record(
        self,
        mission: Dict[str, Any],
        result: PrototypeWorkerResult,
        resolved_source: ResolvedPrototypeSource,
    ) -> Optional[str]:
        try:
            logs = [
                {
                    "type": "system",
                    "content": f"{result.agent_id} Worker finished; provider={result.provider}, status={result.status}",
                }
            ]
            if result.status == "skipped":
                logs.append(
                    {
                        "type": "observation",
                        "content": str(result.payload.get("reason") or "Skipped"),
                    }
                )
            for finding in result.normalized_findings[:6]:
                logs.append(
                    {
                        "type": "assertion",
                        "status": "fail",
                        "action": "assert",
                        "step": finding.get("title"),
                        "target": finding.get("category"),
                        "content": finding.get("summary"),
                    }
                )
            if not result.normalized_findings and result.status in SUCCESS_STATUSES:
                logs.append(
                    {
                        "type": "assertion",
                        "status": "pass",
                        "action": "assert",
                        "step": f"{result.agent_id}-summary",
                        "target": result.agent_id,
                        "content": "No significant issues found",
                    }
                )

            mode_map = {
                "visual": "visual_regression",
                "flow": "ui_e2e",
                "ab": "prototype_ab",
                "a11y": "accessibility",
                "perf": "prototype_perf",
            }
            record_id = f"prototype_{mission['mission_id']}_{result.agent_id}"
            get_execution_center_service().upsert_run(
                task_id=record_id,
                requirement=f"Prototype Specialized Test · {result.agent_id}",
                status="success" if result.status in SUCCESS_STATUSES else ("skipped" if result.status == "skipped" else "failed"),
                target_url=resolved_source.entry_url,
                mode=mode_map.get(result.agent_id, result.agent_id),
                logs=logs,
                duration_ms=_duration_ms(result.started_at, result.finished_at),
                execution_group_id=mission["execution_group_id"],
                session_id=f"{MISSION_KIND}_{mission['mission_id']}",
                group_title=f"Prototype Test · {resolved_source.source_label}",
                record_kind="child",
            )
            return record_id
        except Exception as exc:
            logger.warning("[PrototypeAgents] Failed to persist Worker record: %s", exc)
            return None

    def _persist_summary_record(self, mission: Dict[str, Any]) -> None:
        report = mission.get("report") or {}
        summary = report.get("summary") or {}
        findings = report.get("findings") or []
        try:
            logs = [
                {"type": "system", "content": f"Prototype testing mission completed: {mission.get('source') or mission.get('user_input')}"},
                {
                    "type": "assertion",
                    "status": "pass" if not findings else "fail",
                    "action": "assert",
                    "step": "prototype-report",
                    "target": "prototype_agents",
                    "content": f"Worker {summary.get('total_workers', 0)}; issues found: {summary.get('finding_count', 0)}",
                },
            ]
            for finding in findings[:8]:
                logs.append(
                    {
                        "type": "assertion",
                        "status": "fail",
                        "action": "assert",
                        "step": finding.get("title"),
                        "target": finding.get("category"),
                        "content": finding.get("summary"),
                    }
                )
            get_execution_center_service().upsert_run(
                task_id=mission["mission_id"],
                requirement=f"Prototype Test · {mission.get('source') or mission.get('mission_id')}",
                status="success" if not findings else "failed",
                target_url=str(mission.get("target_url") or ""),
                mode=MISSION_KIND,
                logs=logs,
                duration_ms=_duration_ms(str(mission.get("started_at") or ""), str(mission.get("completed_at") or "")),
                execution_group_id=mission["execution_group_id"],
                session_id=f"{MISSION_KIND}_{mission['mission_id']}",
                group_title=f"Prototype Test · {mission.get('source') or mission['mission_id']}",
                record_kind="child",
            )
        except Exception as exc:
            logger.warning("[PrototypeAgents] Failed to persist summary record: %s", exc)

    def _build_bug_summary(self, report: PrototypeReport) -> List[Dict[str, Any]]:
        bug_items = []
        for finding in report.findings[:8]:
            bug_items.append(
                {
                    "test_type": finding.get("agent_id"),
                    "title": finding.get("title"),
                    "status": finding.get("severity"),
                    "summary": finding.get("summary"),
                    "execution_record_id": finding.get("execution_record_id"),
                }
            )
        return bug_items

    def _save_artifact(self, mission_id: str, filename: str, payload: Any) -> None:
        target_dir = self._artifacts_root / mission_id
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def _save(self, commander: Any) -> None:
        if hasattr(commander, "_save_missions"):
            try:
                commander._save_missions()
            except Exception as exc:
                logger.warning("[PrototypeAgents] Failed to persist mission: %s", exc)


_prototype_agents_service: Optional[PrototypeAgentsService] = None


def get_prototype_agents_service() -> PrototypeAgentsService:
    global _prototype_agents_service
    if _prototype_agents_service is None:
        _prototype_agents_service = PrototypeAgentsService()
    return _prototype_agents_service
