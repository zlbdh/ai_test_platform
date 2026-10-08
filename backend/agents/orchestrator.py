import asyncio
import logging
import threading
import time
import json
import uuid
from datetime import datetime
from typing import AsyncGenerator, Optional

from core.event_bus import EventBus
from core.text_display import (
    BROKEN_TEXT_STATE,
    NORMAL_TEXT_STATE,
    build_broken_text_notice,
    looks_broken_text,
    resolve_display_text,
)
from core.execution_profile import (
    DEFAULT_EXECUTION_MODE,
    DEFAULT_INTERACTION_POLICY,
    PROBE_EXECUTION_MODE,
    build_probe_goal_hint,
    resolve_execution_profile,
)
from agents.planner_agent import PlannerAgent
from agents.executor_agent import ExecutorAgent
from core.session_manager import session_manager
from core.db_helper import get_connection
from core.allure_reporter import get_reporter, TestResult, TestStatus
from services.execution_center_service import get_execution_center_service

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    The Conductor: manages the Planner and Executor lifecycles.
    Phase 6 enhancements:
    - Executor: Runs in a separate thread, as synchronous Playwright requires
    - Planner: Runs asynchronously in the asyncio event loop shared with FastAPI
    - Communication: hybrid EventBus mode (synchronous for Executor, asynchronous for Planner)
    - Thread exception propagation: save Executor errors in _executor_error and check when Planner finishes
    - SSE sequence numbers: increment with each log entry to support Last-Event-ID reconnection
    - Report persistence: write to SQLite automatically when a task completes
    """
    def __init__(self, session_id: str = "default_session"):
        self.session_id = session_id
        self.session = session_manager.get_session(session_id)

        self.planner = None
        self.executor = None
        self.bus = None
        self.e_thread = None      # Separate Executor thread
        self._planner_task = None  # Planner asyncio.Task
        self.active_task_id = ""
        self.is_running = False
        self._executor_error: Optional[str] = None  # Executor thread error
        self._task_requirement = ""  # Current task requirement for persistence
        self._task_requirement_raw = ""  # Original input for diagnostics
        self._task_requirement_display = ""  # User-visible title
        self._task_target_url = ""  # Target URL
        self._task_text_state = NORMAL_TEXT_STATE
        self._task_mode = "smart"   # planner_mode
        self._execution_mode = DEFAULT_EXECUTION_MODE
        self._interaction_policy = DEFAULT_INTERACTION_POLICY
        self._step_budget: Optional[int] = None
        self._execution_profile = resolve_execution_profile()
        self._start_time = 0.0     # Task start time for calculating duration
        self._log_seq = 0  # SSE log sequence number
        self._execution_group_id = ""

    def _generate_task_id(self) -> str:
        """Generate a stable task ID with a low collision risk."""
        return f"task_{uuid.uuid4().hex}"

    @staticmethod
    def _looks_broken_text(value: Optional[str]) -> bool:
        return looks_broken_text(value)

    def _resolve_task_requirement(self, task_requirement: str, target_url: str = "") -> tuple[str, str]:
        display_requirement, text_state = resolve_display_text(task_requirement, target_url, fallback="Untitled test")
        if text_state == BROKEN_TEXT_STATE:
            logger.warning(
                "[Orchestrator] Requirement text looks broken, fallback display title: %s",
                display_requirement,
            )
        return display_requirement, text_state

    def _publish_text_state_log(self) -> None:
        if not self.bus or self._task_text_state != BROKEN_TEXT_STATE:
            return
        self.bus.publish_log_sync(
            {
                "type": "system",
                "event": "text_encoding_fallback",
                "status": "warning",
                "task_text_state": self._task_text_state,
                "requirement_display": self._task_requirement_display,
                "content": build_broken_text_notice(),
            }
        )

    def start_task(
        self,
        task_requirement: str,
        mode: str = "smart",
        target_url: str = "",
        browser_mode: str = "chromium",
        execution_group_id: str = "",
        execution_mode: str = DEFAULT_EXECUTION_MODE,
        interaction_policy: str = DEFAULT_INTERACTION_POLICY,
    ) -> str:
        # Check zombie state
        if self.is_running:
            zombie = False
            if self.e_thread and not self.e_thread.is_alive():
                zombie = True
            if self._planner_task and self._planner_task.done():
                zombie = True
            if zombie:
                logger.warning("[Orchestrator] Detected zombie state. Resetting...")
                self.is_running = False
            else:
                return "Busy"

        self.active_task_id = self._generate_task_id()
        self.is_running = True
        self._executor_error = None
        self._task_requirement_raw = str(task_requirement or "").strip()
        display_requirement, task_text_state = self._resolve_task_requirement(self._task_requirement_raw, target_url)
        self._task_requirement = display_requirement
        self._task_requirement_display = display_requirement
        self._task_target_url = target_url or ""
        self._task_text_state = task_text_state
        self._task_mode = mode
        self._execution_profile = resolve_execution_profile(
            requirement=self._task_requirement_raw,
            execution_mode=execution_mode,
            interaction_policy=interaction_policy,
        )
        self._execution_mode = self._execution_profile["execution_mode"]
        self._interaction_policy = self._execution_profile["interaction_policy"]
        self._step_budget = self._execution_profile.get("step_budget")
        self._start_time = time.time()
        self._log_seq = 0
        self._execution_group_id = execution_group_id or self.active_task_id

        try:
            get_execution_center_service().ensure_group(
                group_id=self._execution_group_id,
                title=display_requirement,
                requirement=display_requirement,
                target_url=target_url or "",
                mode=mode,
                source="agent",
                root_task_id=self.active_task_id,
                session_id=self.session_id,
                requirement_display=display_requirement,
                requirement_raw_present=1 if self._task_requirement_raw else 0,
                task_text_state=self._task_text_state,
                created_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                status="running",
            )
            get_execution_center_service().bind_session_group(
                self.session_id,
                self._execution_group_id,
                title=display_requirement,
                target_url=target_url or "",
            )
        except Exception as exc:
            logger.warning("[Orchestrator] Failed to initialize execution group: %s", exc)

        # Reset Bus
        self.bus = EventBus(session_id=self.session_id)

        # Instantiate Agents
        # ★ Inject target_url and preauthenticated-session instructions into task_goal to prevent repeated sign-ins or site changes
        effective_goal = self._build_effective_goal(task_requirement, target_url)
        if target_url:
            effective_goal = f"[Important: first navigate to the target URL {target_url}; do not guess other ports or addresses.] {effective_goal}"
        if self._execution_mode == PROBE_EXECUTION_MODE:
            effective_goal = f"{effective_goal}{build_probe_goal_hint(target_url)}"
        self.planner = PlannerAgent(
            task_goal=effective_goal,
            bus=self.bus,
            mode=mode,
            session_id=self.session_id,
            target_url=target_url,
            execution_profile=self._execution_profile,
        )
        self.executor = ExecutorAgent(
            bus=self.bus,
            session_id=self.session_id,
            browser_mode=browser_mode,
            target_url=target_url,
            execution_profile=self._execution_profile,
        )

        self.session.set_status("RUNNING", task=display_requirement)
        self.session.clear_logs()
        self.session.set_page_state({})  # Clear old page state to prevent incorrect Planner decisions
        self.session.set_context("task_display", self._task_requirement_display)
        self.session.set_context("task_text_state", self._task_text_state)
        self.session.set_context("task_requirement_raw", self._task_requirement_raw)
        self.session.set_context("execution_mode", self._execution_mode)
        self.session.set_context("interaction_policy", self._interaction_policy)
        self.session.set_context("step_budget", self._step_budget)
        self.session.set_context("execution_profile", dict(self._execution_profile))
        self._publish_text_state_log()

        # Executor: Separate thread required by synchronous Playwright
        self.e_thread = threading.Thread(target=self._run_executor, daemon=True, name="ExecutorThread")
        self.e_thread.start()

        # Planner: asyncio.Task(Shares the event loop with FastAPI)
        self._planner_task = asyncio.create_task(self._run_planner())

        logger.info(f"[Orchestrator] Task {self.active_task_id} launched (hybrid). (Mode: {mode})")

        return self.active_task_id

    def _build_effective_goal(self, task_requirement: str, target_url: str = "") -> str:
        effective_goal = task_requirement
        normalized_target = (target_url or "").lower()
        if any(token in normalized_target for token in ("/qylogin", "/login", "login")):
            return effective_goal

        bootstrap_payload = self.session.get_context("auth_bootstrap") or {}
        bootstrap_result = self.session.get_context("auth_bootstrap_result") or {}
        bootstrap_applied = bool(self.session.get_context("auth_bootstrap_applied"))
        if not isinstance(bootstrap_payload, dict):
            bootstrap_payload = {}
        if not isinstance(bootstrap_result, dict):
            bootstrap_result = {}

        city = str(bootstrap_result.get("city") or bootstrap_payload.get("city") or "").strip()
        station = str(
            bootstrap_result.get("station_name")
            or bootstrap_payload.get("station_name")
            or bootstrap_result.get("station_id")
            or bootstrap_payload.get("station_id")
            or ""
        ).strip()

        if bootstrap_payload or bootstrap_applied:
            site_hint = f"{city}-{station}".strip("-")
            if site_hint:
                effective_goal = (
                    f"{effective_goal}"
                    f"[Session preauthentication is complete: signed in and switched to {site_hint}. "
                    "Do not sign in again, click a city/site, or switch sites unless the requirement explicitly asks for it.] "
                )
            else:
                effective_goal = (
                    f"{effective_goal}"
                    "[Session preauthentication is complete: signed in. Do not sign in again or switch sites unless the requirement explicitly asks for it.] "
                )

        return effective_goal

    def _run_executor(self):
        """Run Executor in a separate thread with synchronous Playwright"""
        try:
            self.executor.run()
        except Exception as e:
            error_msg = f"Executor crashed: {e}"
            logger.error(f"[Orchestrator] {error_msg}")
            self._executor_error = error_msg
            # Try to send the error to EventBus so the SSE stream can receive it
            try:
                if self.bus:
                    self.bus.publish_log_sync({"type": "error", "content": f"❌ {error_msg}"})
            except Exception:
                pass

    async def _run_planner(self):
        """Run Planner in the asyncio event loop"""
        try:
            await self.planner.run()
        except Exception as e:
            logger.error(f"[Orchestrator] Planner error: {e}")
            # Send the Planner error log
            try:
                if self.bus:
                    await self.bus.publish_log({"type": "error", "content": f"❌ Planner error: {e}"})
            except Exception:
                pass
        finally:
            # Wait for the Executor thread to exit after Planner finishes
            if self.e_thread and self.e_thread.is_alive():
                logger.info("[Orchestrator] Waiting for Executor thread to finish...")
                for _ in range(100):  # Up to 10 seconds
                    if not self.e_thread.is_alive():
                        break
                    await asyncio.sleep(0.1)

            # Check whether the Executor thread exited with an error
            if self._executor_error:
                logger.warning(f"[Orchestrator] Executor had error: {self._executor_error}")
                try:
                    if self.bus:
                        await self.bus.publish_log({
                            "type": "error",
                            "content": f"⚠️ Executor exited with an error: {self._executor_error}"
                        })
                except Exception:
                    pass

            # Persist test results
            self._persist_test_run()

            self.is_running = False
            self.session.set_status("IDLE")
            logger.info(f"[Orchestrator] Task {self.active_task_id} completed.")

    def stop_task(self):
        logger.info("[Orchestrator] Force stopping...")
        if self.planner:
            self.planner.stop()
        if self.executor:
            self.executor.stop()
        if self._planner_task and not self._planner_task.done():
            self._planner_task.cancel()
        self.is_running = False
        self.session.set_status("IDLE")
        self.session.set_signal("RUNNING")  # Reset signal
        logger.info("[Orchestrator] Stopped.")

    async def stream_logs(self, start_seq: int = 0) -> AsyncGenerator:
        """
        SSE Generator: Read logs from EventBus in real time.
        Support Last-Event-ID reconnection and heartbeat keepalives.
        """
        # Replay existing logs first when a reconnecting client supplies start_seq
        if start_seq > 0:
            existing_logs = self.session.get_logs()
            for i, log in enumerate(existing_logs):
                seq = i + 1
                if seq > start_seq:
                    yield f"id: {seq}\ndata: {json.dumps(log, ensure_ascii=False)}\n\n"
            self._log_seq = len(existing_logs)

        heartbeat_interval = 15  # Send a heartbeat every 15 seconds
        last_heartbeat = time.time()

        while self.is_running:
            if self.bus:
                log = await self.bus.get_log(timeout=0.5)
                if log:
                    self._log_seq += 1
                    yield f"id: {self._log_seq}\ndata: {json.dumps(log, ensure_ascii=False)}\n\n"
                    last_heartbeat = time.time()
                elif time.time() - last_heartbeat > heartbeat_interval:
                    # SSE heartbeat: prevent proxies or clients from disconnecting during idle periods
                    yield f": heartbeat\n\n"
                    last_heartbeat = time.time()
            else:
                await asyncio.sleep(0.1)

        # Drain: Read remaining logs after the task ends, capped at 50 to prevent an infinite loop
        if self.bus:
            drain_count = 0
            while drain_count < 50:
                log = self.bus.get_log_sync(timeout=0.1)
                if not log:
                    break
                self._log_seq += 1
                yield f"id: {self._log_seq}\ndata: {json.dumps(log, ensure_ascii=False)}\n\n"
                drain_count += 1

        # Send the done event
        self._log_seq += 1
        yield f"id: {self._log_seq}\ndata: {json.dumps({'type': 'done'})}\n\n"

    def _persist_test_run(self):
        """Persist test results to SQLite"""
        try:
            logs = self.session.get_logs()
            error_count = sum(1 for l in logs if l.get("type") == "error")
            heal_success = sum(1 for l in logs if l.get("type") == "heal" and any(term in l.get("content", "") for term in ("Healing succeeded", "自愈成功")))
            display_requirement = self._task_requirement_display or self._task_requirement or "unknown"
            raw_requirement = self._task_requirement_raw or self._task_requirement or ""
            task_text_state = self._task_text_state or (
                BROKEN_TEXT_STATE if self._looks_broken_text(raw_requirement) else NORMAL_TEXT_STATE
            )

            # === Determine status intelligently ===
            # First check whether the final logs contain "Mission Accomplished" (the AI confirmed completion)
            mission_accomplished = any(
                "Mission Accomplished" in l.get("content", "")
                for l in logs
                if l.get("type") == "system"
            )

            if error_count == 0:
                status = "success"
            elif heal_success >= error_count:
                status = "healed"
            elif mission_accomplished:
                # Errors occurred but the AI ultimately confirmed completion → recovered
                status = "recovered"
            else:
                status = "failed"

            duration_ms = int((time.time() - self._start_time) * 1000) if self._start_time else 0

            local_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            get_execution_center_service().upsert_run(
                task_id=self.active_task_id,
                requirement=display_requirement,
                status=status,
                target_url=self._task_target_url,
                mode=self._task_mode,
                logs=logs,
                duration_ms=duration_ms,
                created_at=local_now,
                execution_group_id=self._execution_group_id or self.active_task_id,
                session_id=self.session_id,
                group_title=display_requirement,
                record_kind="root",
                requirement_display=display_requirement,
                requirement_raw=raw_requirement,
                task_text_state=task_text_state,
            )
            logger.info(f"[Orchestrator] Test run persisted: {self.active_task_id} ({status}, {len(logs)} logs, {error_count} errors, {heal_success} healed, {duration_ms}ms)")

            # === Generate the Allure report automatically ===
            try:
                reporter = get_reporter()
                reporter.start_suite(display_requirement or "AI Test Suite")

                # Convert execution logs into Allure TestResult objects
                steps = []
                for log_entry in logs:
                    steps.append({
                        "name": log_entry.get("step", log_entry.get("type", "step")),
                        "status": "passed" if log_entry.get("type") != "error" else "failed",
                        "details": log_entry.get("content", ""),
                    })

                allure_status = TestStatus.PASSED if status in ("success", "recovered", "healed") else TestStatus.FAILED
                result = TestResult(
                    name=display_requirement or "unknown",
                    status=allure_status,
                    duration=duration_ms / 1000.0,
                    description=f"Target: {self._task_target_url or 'N/A'} | Mode: {self._task_mode}",
                    steps=steps,
                    error_message=next((l.get("content", "") for l in logs if l.get("type") == "error"), ""),
                )
                reporter.add_result(result)
                reporter.finish_suite()
                reporter.generate_report(task_id=self.active_task_id)
                logger.info("[Orchestrator] Allure report generated successfully.")
            except Exception as allure_err:
                logger.warning(f"[Orchestrator] Allure report generation failed: {allure_err}")

            # === Send a completion notification ===
            try:
                from core.notify_helper import send_completion_notification
                duration_str = f"{duration_ms / 1000:.1f}s" if duration_ms else "N/A"
                notification_coro = send_completion_notification(
                    title="AI orchestration test report",
                    status="completed" if status in ("success", "recovered", "healed") else "failed",
                    summary=f"Task: {display_requirement or 'unknown'}\nTarget: {self._task_target_url or 'N/A'}",
                    details={
                        "total_steps": len(logs),
                        "passed": len(logs) - error_count,
                        "failed": error_count,
                        "duration": duration_str,
                        "annotations": [build_broken_text_notice()] if task_text_state == BROKEN_TEXT_STATE else [],
                    },
                )
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    asyncio.run(notification_coro)
                else:
                    loop.create_task(notification_coro)
            except Exception as notify_err:
                logger.debug(f"[Orchestrator] Notification skipped: {notify_err}")

        except Exception as e:
            logger.warning(f"[Orchestrator] Failed to persist test run: {e}")
