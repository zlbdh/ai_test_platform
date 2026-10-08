# -*- coding: utf-8 -*-
"""
E2E scenario chain engine — sequential execution of multistep test scenarios

Features:
1. Define scenario chains consisting of multiple test steps
2. Share state across steps (cookies, variables, and data)
3. Conditional branches (skip later steps if a prerequisite fails)
4. Scenario chain template management (save, load, and execute)
"""
import json
import uuid
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, field, asdict

from core.config import Config

logger = logging.getLogger(__name__)

SCENARIOS_DIR = Path(Config.PROJECT_ROOT) / "data" / "scenarios"
SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ScenarioStep:
    """A step in a scenario chain"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    url: str = ""
    instruction: str = ""
    mode: str = "smart"
    timeout: int = 60
    on_failure: str = "stop"  # stop / skip / continue
    depends_on: Optional[str] = None  # Prerequisite step ID
    status: str = "pending"
    result: Optional[Dict] = None
    duration_ms: int = 0


@dataclass
class Scenario:
    """E2E test scenario chain"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    name: str = ""
    description: str = ""
    steps: List[Dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "draft"  # draft / running / completed / failed
    tags: List[str] = field(default_factory=list)


class ScenarioChainEngine:
    """Scenario chain management engine"""

    def __init__(self):
        self.scenarios: Dict[str, Scenario] = {}
        self._load_all()

    @staticmethod
    def _merge_step_state(step_data: Dict[str, Any], step: ScenarioStep) -> Dict[str, Any]:
        merged = dict(step_data)
        merged.update(asdict(step))
        return merged

    def _reset_step_runtime(self, scenario: Scenario):
        for index, step_data in enumerate(scenario.steps):
            step = ScenarioStep(**{k: v for k, v in step_data.items() if k in ScenarioStep.__dataclass_fields__})
            step.status = "pending"
            step.result = None
            step.duration_ms = 0
            scenario.steps[index] = self._merge_step_state(step_data, step)
        self._save(scenario)

    def _persist_step_runtime(self, scenario: Scenario, step_index: int, step_data: Dict[str, Any], step: ScenarioStep):
        scenario.steps[step_index] = self._merge_step_state(step_data, step)
        self._save(scenario)

    def _get_orchestrator(self, session_id: str):
        from main import get_orchestrator

        return get_orchestrator(session_id)

    def _query_task_status(self, task_id: str) -> Optional[str]:
        from core.db_helper import query_one

        row = query_one("SELECT status FROM test_runs WHERE task_id=?", (task_id,))
        if not row:
            return None
        return row.get("status")

    def _load_all(self):
        """Load all scenarios"""
        for f in SCENARIOS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                sc = Scenario(**{k: v for k, v in data.items() if k in Scenario.__dataclass_fields__})
                self.scenarios[sc.id] = sc
            except Exception as e:
                logger.warning(f"Failed to load scenario {f}: {e}")

    def _save(self, scenario: Scenario):
        """Save a scenario to disk"""
        scenario.updated_at = datetime.now().isoformat()
        path = SCENARIOS_DIR / f"{scenario.id}.json"
        path.write_text(json.dumps(asdict(scenario), ensure_ascii=False, indent=2), encoding="utf-8")

    def list_scenarios(self) -> List[Dict]:
        """List all scenarios"""
        return [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "stepCount": len(s.steps),
                "status": s.status,
                "tags": s.tags,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
            }
            for s in sorted(self.scenarios.values(), key=lambda x: x.updated_at, reverse=True)
        ]

    def get_scenario(self, scenario_id: str) -> Optional[Dict]:
        """Get scenario details"""
        sc = self.scenarios.get(scenario_id)
        if not sc:
            return None
        return asdict(sc)

    def create_scenario(self, name: str, description: str = "", steps: List[Dict] = None, tags: List[str] = None) -> Dict:
        """Create a scenario"""
        sc = Scenario(
            name=name,
            description=description,
            steps=steps or [],
            tags=tags or [],
        )
        self.scenarios[sc.id] = sc
        self._save(sc)
        return asdict(sc)

    def upsert_scenario_by_name(
        self,
        name: str,
        description: str = "",
        steps: List[Dict] = None,
        tags: List[str] = None,
    ) -> Dict:
        """Update or create a scenario by name to support importing project scenario packages."""
        existing = next((scenario for scenario in self.scenarios.values() if scenario.name == name), None)
        if existing:
            existing.description = description
            existing.steps = steps or []
            existing.tags = tags or []
            self._save(existing)
            return asdict(existing)
        return self.create_scenario(name=name, description=description, steps=steps, tags=tags)

    def update_scenario(self, scenario_id: str, data: Dict) -> Optional[Dict]:
        """Update the scenario"""
        sc = self.scenarios.get(scenario_id)
        if not sc:
            return None
        for k in ("name", "description", "steps", "tags"):
            if k in data:
                setattr(sc, k, data[k])
        self._save(sc)
        return asdict(sc)

    def delete_scenario(self, scenario_id: str) -> bool:
        """Delete the scenario"""
        if scenario_id not in self.scenarios:
            return False
        del self.scenarios[scenario_id]
        path = SCENARIOS_DIR / f"{scenario_id}.json"
        if path.exists():
            path.unlink()
        return True

    async def execute_scenario(self, scenario_id: str) -> Dict:
        """Execute a scenario chain"""
        sc = self.scenarios.get(scenario_id)
        if not sc:
            return {"error": "Scenario not found"}

        self._reset_step_runtime(sc)
        sc.status = "running"
        self._save(sc)

        results = []
        shared_state: Dict[str, Any] = {}
        failed_steps = set()

        for i, step_data in enumerate(sc.steps):
            step = ScenarioStep(**{k: v for k, v in step_data.items() if k in ScenarioStep.__dataclass_fields__})

            # Check dependencies
            if step.depends_on and step.depends_on in failed_steps:
                step.status = "skipped"
                step.result = {"reason": f"Prerequisite step {step.depends_on} failed"}
                self._persist_step_runtime(sc, i, step_data, step)
                results.append({"step": step.name, "status": "skipped", "reason": step.result["reason"]})
                continue

            step.status = "running"
            start = datetime.now()
            self._persist_step_runtime(sc, i, step_data, step)

            try:
                # Create a separate Orchestrator to execute the current step independently
                session_id = f"scen_{scenario_id}_{step.id}"
                orch = self._get_orchestrator(session_id)
                
                task_id = orch.start_task(
                    task_requirement=step.instruction,
                    mode=step.mode,
                    target_url=step.url,
                    browser_mode="chromium"
                )

                if task_id == "Busy":
                    task_id = f"task_{int(time.time())}"
                    raise Exception("Orchestrator is Busy! System may be overloaded or locked.")

                # Wait for completion by polling in-memory state and database results
                final_status = "running"
                waited = 0
                while waited < step.timeout:
                    await asyncio.sleep(2)
                    waited += 2
                    
                    if not orch.is_running:
                        # Execution stopped; check the final SQLite result (healed, success, completed)
                        status_val = self._query_task_status(task_id)
                        if status_val:
                            final_status = "success" if status_val in ("success", "completed", "healed") else "failed"
                        else:
                            final_status = "error"
                        break

                if final_status == "running":
                    # Stop unfinished execution at timeout and record failure
                    orch.stop_task()
                    final_status = "failed"
                    
                step.duration_ms = int((datetime.now() - start).total_seconds() * 1000)
                step.status = "passed" if final_status in ("success", "completed") else "failed"
                step.result = {"task_id": task_id, "status": final_status}
                shared_state[step.id] = dict(step.result)
                step.result["shared_state"] = dict(shared_state)
                self._persist_step_runtime(sc, i, step_data, step)

                if step.status == "failed":
                    failed_steps.add(step.id)
                    if step.on_failure == "stop":
                        results.append({"step": step.name, "status": "failed", "duration_ms": step.duration_ms})
                        break

            except Exception as e:
                step.status = "failed"
                step.duration_ms = int((datetime.now() - start).total_seconds() * 1000)
                step.result = {"error": str(e)}
                shared_state[step.id] = dict(step.result)
                step.result["shared_state"] = dict(shared_state)
                self._persist_step_runtime(sc, i, step_data, step)
                failed_steps.add(step.id)
                if step.on_failure == "stop":
                    results.append({"step": step.name, "status": "error", "error": str(e)})
                    break

            results.append({
                "step": step.name,
                "status": step.status,
                "duration_ms": step.duration_ms,
                "task_id": step.result.get("task_id", "") if step.result else "",
            })

        # Update scenario status
        all_passed = all(r["status"] in ("passed", "skipped") for r in results)
        sc.status = "completed" if all_passed else "failed"
        self._save(sc)

        return {
            "scenario_id": scenario_id,
            "name": sc.name,
            "status": sc.status,
            "total_steps": len(sc.steps),
            "executed": len(results),
            "passed": sum(1 for r in results if r["status"] == "passed"),
            "failed": sum(1 for r in results if r["status"] in ("failed", "error")),
            "skipped": sum(1 for r in results if r["status"] == "skipped"),
            "results": results,
        }


# ── Singleton ──
_engine: Optional[ScenarioChainEngine] = None


def get_scenario_engine() -> ScenarioChainEngine:
    global _engine
    if _engine is None:
        _engine = ScenarioChainEngine()
    return _engine
