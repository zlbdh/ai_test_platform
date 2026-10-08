import asyncio
import inspect
import logging
import time
import uuid
import re
from typing import List, Dict, Any

logger = logging.getLogger(__name__)
from core.event_bus import EventBus
from core.protocol import TaskEvent, ResultEvent, SENTINEL
from services.planner_service import planner_service
from core.session_manager import session_manager
from core.execution_profile import PROBE_EXECUTION_MODE, should_block_probe_action
from faker import Faker

class PlannerAgent:
    """
    The Brain: handles high-level planning and decisions.
    Phase 5: fully asynchronous implementation.

    Supports two modes:
    - smart: Step-by-step reasoning loop (observe the page → LLM decision → execute → repeat)
    - quick: Generate all steps at once, then execute them as a batch
    """
    def __init__(
        self,
        task_goal: str,
        bus: EventBus,
        mode: str = "smart",
        session_id: str = "default_session",
        target_url: str = "",
        execution_profile: Dict[str, Any] | None = None,
    ):
        self.session_id = session_id
        self.session = session_manager.get_session(session_id)
        self.task_goal = task_goal
        self.target_url = target_url
        self.bus = bus
        self.mode = mode
        self.running = True
        self.plan: List[Dict[str, Any]] = []
        self.plan_step_index = 0
        self.context: Dict[str, Any] = {}
        self.history: List[Dict[str, Any]] = []
        self.execution_profile = execution_profile or {}

    def _is_probe_mode(self) -> bool:
        return self.execution_profile.get("execution_mode") == PROBE_EXECUTION_MODE

    def _step_budget(self) -> int:
        return int(self.execution_profile.get("max_steps") or 200)

    def _timeout_budget(self) -> int:
        return int(self.execution_profile.get("timeout_seconds") or 120)

    async def _apply_probe_plan_budget(self, test_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self._is_probe_mode():
            return test_cases

        max_scenarios = int(self.execution_profile.get("max_scenarios") or 1)
        max_steps = self._step_budget()
        original_scenarios = len(test_cases)
        original_steps = sum(len(tc.get("steps", []) or []) for tc in test_cases)

        trimmed_cases: List[Dict[str, Any]] = []
        consumed_steps = 0
        scenario_trimmed = original_scenarios > max_scenarios
        step_trimmed = False

        for index, test_case in enumerate(test_cases):
            if index >= max_scenarios:
                scenario_trimmed = True
                break

            steps = list(test_case.get("steps", []) or [])
            remaining_steps = max_steps - consumed_steps
            if remaining_steps <= 0:
                step_trimmed = True
                break

            if len(steps) > remaining_steps:
                steps = steps[:remaining_steps]
                step_trimmed = True

            trimmed_case = dict(test_case)
            trimmed_case["steps"] = steps
            trimmed_cases.append(trimmed_case)
            consumed_steps += len(steps)

        if scenario_trimmed or step_trimmed:
            summary = (
                f"Read-only probe limited the plan to {len(trimmed_cases)} scenarios / {consumed_steps} steps"
                f" (originally {original_scenarios} scenarios / {original_steps} steps)"
            )
            await self._publish_probe_event(
                "probe_plan_trimmed",
                summary,
                execution_mode=self.execution_profile.get("execution_mode", "probe"),
                interaction_policy=self.execution_profile.get("interaction_policy", "read_only"),
                step_budget=max_steps,
                original_scenarios=original_scenarios,
                original_steps=original_steps,
                trimmed_scenarios=len(trimmed_cases),
                trimmed_steps=consumed_steps,
            )

        return trimmed_cases

    async def _publish_probe_event(self, event: str, content: str, **extra) -> None:
        payload = {
            "type": "system",
            "event": event,
            "status": "warning" if event != "probe_summary" else "success",
            "content": content,
        }
        payload.update(extra)
        await self.bus.publish_log(payload)

    async def _run_probe_mode(self):
        max_wait_seconds = min(self._timeout_budget(), 20)
        start = time.time()
        msg = "🧠 [Planner/Probe] Starting read-only probe mode: inspect page state without entering input or submitting forms"
        logger.info(msg)
        await self.bus.publish_log({"type": "thought", "subtype": "planner", "content": msg})

        while self.running and (time.time() - start) < max_wait_seconds:
            page_state = self.session.get_page_state() or {}
            current_url = str(page_state.get("url") or "").strip()
            current_title = str(page_state.get("title") or "").strip()
            if current_url and current_url != "（未导航）":
                interactive_elements = str(page_state.get("interactive_elements") or "")
                interactive_count = interactive_elements.count("[")
                summary = (
                    f"Read-only probe completed: URL={current_url} | Title={current_title or 'N/A'} | "
                    f"Indexed interactive elements≈{interactive_count}"
                )
                await self._publish_probe_event(
                    "probe_summary",
                    summary,
                    execution_mode="probe",
                    interaction_policy=self.execution_profile.get("interaction_policy", "read_only"),
                    step_budget=self.execution_profile.get("step_budget"),
                )
                await self.bus.publish_log({"type": "system", "content": f"Mission Accomplished. {summary}"})
                self.running = False
                await self.bus.shutdown()
                return
            if not self.target_url and not current_url and (time.time() - start) >= 2:
                err = "🧠 [Planner/Probe] No target URL was provided and the current session has no page to inspect; ending immediately"
                logger.warning(err)
                await self.bus.publish_log({"type": "error", "content": err})
                self.running = False
                await self.bus.shutdown()
                return
            await asyncio.sleep(0.5)

        err = "🧠 [Planner/Probe] Probe timed out: no usable page state was available within the time budget"
        logger.warning(err)
        await self.bus.publish_log({"type": "error", "content": err})
        self.running = False
        await self.bus.shutdown()

    def _build_loop_recovery(self, repeated_action: str, page_state: Dict[str, Any]) -> Dict[str, str]:
        """Choose a safer recovery action for a persistent loop."""
        elements = str((page_state or {}).get('interactive_elements', '') or '')
        lowered_elements = elements.lower()

        if any(keyword in lowered_elements for keyword in ("captcha", "verification", "verify code")) or "验证码" in elements:
            return {
                "action": "done",
                "target": "Detected a CAPTCHA or human verification page; stopped automatic recovery and requested human intervention",
                "value": "",
                "override_msg": (
                    f"🧠 [Planner/Smart] ➡️ Repeated action '{repeated_action}' and a CAPTCHA was detected;"
                    "stop automatic recovery and request human intervention"
                ),
            }

        if '登录' in elements or '提交' in elements:
            return {
                "action": "click",
                "target": "登录按钮",
                "value": "",
                "override_msg": "🧠 [Planner/Smart] ➡️ Force a sign-in/submit click to break the loop",
            }

        return {
            "action": "scroll",
            "target": "",
            "value": "down",
            "override_msg": "🧠 [Planner/Smart] ➡️ Force a page scroll to break the loop",
        }

    # ═══════════════════════════════════════════
    # Quick Mode (Plan once)
    # ═══════════════════════════════════════════

    async def _resolve_maybe_async(self, value):
        """Support synchronous and asynchronous planner services to prevent await failures with mocks or legacy implementations."""
        if inspect.isawaitable(value):
            return await value
        return value

    async def _initialize_plan(self):
        """Call LLM to generate plan based on goal (sync LLM wrapped in to_thread)"""
        msg = f"🧠 [Planner] Generating Plan for: {self.task_goal}..."
        logger.info(msg)
        await self.bus.publish_log({"type": "thought", "subtype": "planner", "content": msg})

        try:
            generated = await self._resolve_maybe_async(
                planner_service.generate_plan(
                    self.task_goal,
                    True,
                    self.target_url,
                    execution_mode=self.execution_profile.get("execution_mode", "default"),
                    interaction_policy=self.execution_profile.get("interaction_policy", "default"),
                )
            )
            test_cases = await self._apply_probe_plan_budget(generated.get('test_cases', []))

            if not test_cases:
                await self.bus.publish_log({"type": "error", "content": "Planner failed to generate test cases."})
                logger.warning("[Planner] No test cases generated.")
                return

            all_steps = []
            for tc in test_cases:
                scenario_name = tc.get('scenario', 'Unknown scenario')
                steps = tc.get('steps', [])
                for step in steps:
                    step['_scenario'] = scenario_name
                    all_steps.append(step)
                msg = f"🧠 [Planner] Added Scenario: {scenario_name} ({len(steps)} steps)"
                logger.info(msg)
                await self.bus.publish_log({"type": "thought", "subtype": "planner", "content": msg})

            self.plan = all_steps
            msg = f"🧠 [Planner] Total Plan: {len(all_steps)} steps across {len(test_cases)} scenarios"
            logger.info(msg)
            await self.bus.publish_log({"type": "thought", "subtype": "planner", "content": msg})

        except Exception as e:
            err = f"🧠 [Planner] Planning Failed: {e}"
            logger.error(err)
            await self.bus.publish_log({"type": "error", "content": err})
            self.plan = []

    async def _capture_page_screenshot(self):
        """Safely retrieve the current page screenshot through the SessionState bridge."""
        if self.session.get_page() is None:
            return None

        try:
            raw = await self.session.run_browser(
                lambda page: page.screenshot(type='jpeg', quality=50, timeout=5000)
            )
            import base64 as _b64
            return _b64.b64encode(raw).decode('utf-8')
        except Exception:
            return None

    def _resolve_variables(self, text: str) -> str:
        if not isinstance(text, str): return text

        if not hasattr(self, '_faker'):
            self._faker = Faker('zh_CN')
        fake = self._faker

        matches = re.findall(r"\$\{(.*?)\}", text)
        for var in matches:
            replacement = None

            if var.startswith("fake."):
                method = var.split(".")[1]
                if hasattr(fake, method):
                    try:
                        replacement = getattr(fake, method)()
                    except Exception:
                        pass

            if replacement is None:
                val = self.session.get_context(var)
                if val is not None:
                    replacement = val

            if replacement is None and var in self.context:
                replacement = self.context[var]

            if replacement is not None:
                text = text.replace(f"${{{var}}}", str(replacement))

        return text

    async def _run_quick_mode(self):
        """Quick Mode: Generate all steps → execute in a batch (skip failed steps and continue)"""
        await self._initialize_plan()

        if not self.plan:
            logger.warning("[Planner] Aborting due to empty plan.")
            self.running = False
            await self.bus.shutdown()
            return

        current_task_id = None
        failed_steps = 0
        total_steps = len(self.plan)

        while self.running:
            result = await self.bus.get_result(timeout=0.5)
            if result:
                self._handle_result(result)

            if self.plan_step_index < len(self.plan):
                if current_task_id:
                    if result and result['task_id'] == current_task_id:
                        if result['status'] == 'success':
                            msg = f"🧠 [Planner] Step {self.plan_step_index + 1} Succeeded."
                            logger.info(msg)
                            await self.bus.publish_log({"type": "observation", "content": msg})
                            self.plan_step_index += 1
                            current_task_id = None
                        else:
                            failed_steps += 1
                            msg = f"🧠 [Planner] Step {self.plan_step_index + 1}/{total_steps} Failed (skipped): {result['message']}"
                            logger.warning(msg)
                            await self.bus.publish_log({"type": "error", "content": msg})
                            # Skip to the next step instead of stopping the entire run
                            self.plan_step_index += 1
                            current_task_id = None
                        continue
                    else:
                        await asyncio.sleep(0.1)
                        continue

                step = self.plan[self.plan_step_index]
                task_id = str(uuid.uuid4())
                current_task_id = task_id

                scenario_name = step.get('_scenario', '')
                if scenario_name:
                    prev_scenario = self.plan[self.plan_step_index - 1].get('_scenario', '') if self.plan_step_index > 0 else ''
                    if scenario_name != prev_scenario:
                        msg = f"🧠 [Planner] ▶ Scenario: {scenario_name}"
                        logger.info(msg)
                        await self.bus.publish_log({"type": "thought", "subtype": "planner", "content": msg})

                        # Rescan the DOM element index when switching scenarios
                        try:
                            if self.session.get_page() is not None:
                                from core.dom_indexer import dom_indexer
                                await self.session.run_browser(lambda page: dom_indexer.scan(page))
                                logger.info(f"[Planner] DomIndexer rescanned for new scenario: {scenario_name}")
                        except Exception as scan_err:
                            logger.warning(f"[Planner] DomIndexer rescan failed: {scan_err}")

                target = self._resolve_variables(step.get('target', ''))
                value = self._resolve_variables(step.get('value', ''))

                new_task: TaskEvent = {
                    "id": task_id,
                    "type": "action",
                    "action": step['action'],
                    "target": target,
                    "value": value,
                    "timestamp": str(time.time()),
                    "step_index": self.plan_step_index,
                    "scenario": scenario_name,
                }

                msg = f"🧠 [Planner] Instructing: {step['action']} -> {target}"
                logger.info(msg)
                await self.bus.publish_log({"type": "thought", "subtype": "planner", "content": msg})

                await self.bus.publish_task(new_task)

            else:
                if current_task_id is None:
                    passed = total_steps - failed_steps
                    summary = f"Mission Accomplished. ({passed}/{total_steps} passed, {failed_steps} failed)"
                    logger.info(f"[Planner] {summary}")
                    await self.bus.publish_log({"type": "system", "content": summary})
                    self.running = False
                    await self.bus.shutdown()
                    break

            await asyncio.sleep(0.05)

    # ═══════════════════════════════════════════
    # Smart Mode (Phase 2)
    # ═══════════════════════════════════════════

    async def _run_smart_mode(self):
        """
        Smart Mode: Step-by-step reasoning loop.
        Each step: read page state → LLM decision → Executor action → collect result → repeat
        """
        max_steps = self._step_budget()
        step_count = 0

        msg = f"🧠 [Planner/Smart] Starting step-by-step reasoning; goal: {self.task_goal}"
        logger.info(msg)
        await self.bus.publish_log({"type": "thought", "subtype": "planner", "content": msg})

        # ★ Wait for the Executor browser to be ready to avoid a Planner-Executor race
        wait_msg = "🧠 [Planner/Smart] Waiting for the browser..."
        logger.info(wait_msg)
        await self.bus.publish_log({"type": "thought", "subtype": "planner", "content": wait_msg})
        for _wait in range(60):  # Wait up to 30 seconds
            if self.session.get_page() is not None:
                break
            await asyncio.sleep(0.5)
        else:
            err = "🧠 [Planner/Smart] ⚠️ Browser was not ready within 30 seconds; stopping"
            logger.error(err)
            await self.bus.publish_log({"type": "error", "content": err})
            self.running = False
            await self.bus.shutdown()
            return

        ready_msg = "🧠 [Planner/Smart] ✅ Browser is ready; starting reasoning"
        logger.info(ready_msg)
        await self.bus.publish_log({"type": "thought", "subtype": "planner", "content": ready_msg})

        while self.running and step_count < max_steps:
            # 1. Read the current page state
            page_state = self.session.get_page_state()

            if not page_state:
                page_state = {"url": "（未导航）", "title": "", "interactive_elements": "", "visible_text": ""}

            # 1.5 ★ L1: Capture a page screenshot for multimodal VLM reasoning
            screenshot_b64 = await self._capture_page_screenshot()

            # 2. Single-step LLM reasoning (synchronous, using to_thread)
            msg = f"🧠 [Planner/Smart] Step {step_count + 1}: Reasoning...{' (📸 Vision)' if screenshot_b64 else ''}"
            logger.info(msg)
            await self.bus.publish_log({"type": "thought", "subtype": "planner", "content": msg})

            try:
                next_step = await self._resolve_maybe_async(
                    planner_service.plan_next_step(
                        goal=self.task_goal,
                        page_state=page_state,
                        history=self.history,
                        screenshot_b64=screenshot_b64,
                        execution_profile=self.execution_profile,
                    )
                )
            except Exception as e:
                err = f"🧠 [Planner/Smart] Reasoning error: {e}"
                logger.error(err)
                await self.bus.publish_log({"type": "error", "content": err})
                break

            action = next_step.get('action', 'done')
            target = next_step.get('target', '')
            value = next_step.get('value', '')
            thinking = next_step.get('thinking', '')

            if thinking:
                await self.bus.publish_log({"type": "thought", "subtype": "planner", "content": f"💭 {thinking}"})

            # === L3: Detect state loops: stop early when page error messages remain unchanged ===
            if len(self.history) >= 8:
                recent_msgs = [h.get('message', '')[:80] for h in self.history[-8:]]
                unique_msgs = set(m for m in recent_msgs if m.strip())
                if len(unique_msgs) <= 2 and len([m for m in recent_msgs if m.strip()]) >= 8:
                    state_loop_msg = f"🧠 [Planner/Smart] ⛔ State loop: page messages unchanged for eight steps → {list(unique_msgs)[:1]}"
                    logger.warning(state_loop_msg)
                    await self.bus.publish_log({"type": "error", "content": state_loop_msg})
                    action = 'done'
                    target = f'Stuck in the same page state: {list(unique_msgs)[:1]}'
                    value = ''

            # === Hard loop cutoff in case the LLM ignores prompt warnings===
            if self.history and len(self.history) >= 5:
                consecutive = 1
                last_a = self.history[-1].get('action', '')
                for h in reversed(self.history[:-1]):
                    if h.get('action', '') == last_a:
                        consecutive += 1
                    else:
                        break

                # Override the LLM if it returns the same action for five or more consecutive steps
                if consecutive >= 5 and action == last_a:
                    warn = f"🧠 [Planner/Smart] ⛔ Detected {consecutive+1}x '{action}' repetitions in a loop; overriding the LLM decision"
                    logger.warning(warn)
                    await self.bus.publish_log({"type": "error", "content": warn})

                    page_state = self.session.get_page_state() or {}
                    recovery = self._build_loop_recovery(action, page_state)
                    action = recovery["action"]
                    target = recovery["target"]
                    value = recovery["value"]
                    override_msg = recovery["override_msg"]

                    logger.info(override_msg)
                    await self.bus.publish_log({"type": "thought", "subtype": "planner", "content": override_msg})

            # 3. Check whether the task is complete

            if action == 'done':
                msg = f"🧠 [Planner/Smart] Task completed: {target}"
                logger.info(msg)
                await self.bus.publish_log({"type": "system", "content": f"Mission Accomplished. {target}"})
                break

            # 3.5 Check for reasoning failure
            if action == 'error':
                msg = f"🧠 [Planner/Smart] ❌ Reasoning failed: {target}"
                logger.error(msg)
                await self.bus.publish_log({"type": "error", "content": msg})
                break

            # 4. Resolve variables
            target = self._resolve_variables(target)
            value = self._resolve_variables(value)

            blocked, block_reason = should_block_probe_action(action, target, value) if self._is_probe_mode() else (False, "")
            if blocked:
                await self._publish_probe_event(
                    "probe_action_blocked",
                    f"{block_reason}; read-only probe task ended",
                    action=action,
                    target=target,
                    value=value,
                    step_budget=self.execution_profile.get("step_budget"),
                )
                await self.bus.publish_log({"type": "system", "content": f"Mission Accomplished. {block_reason}"})
                break

            # 5. Send to Executor
            task_id = str(uuid.uuid4())
            current_step_index = step_count
            new_task: TaskEvent = {
                "id": task_id,
                "type": "action",
                "action": action,
                "target": target,
                "value": value,
                "timestamp": str(time.time()),
                "step_index": current_step_index,
            }

            msg = f"🧠 [Planner/Smart] → {action} {target}"
            logger.info(msg)
            await self.bus.publish_log({"type": "thought", "subtype": "planner", "content": msg})

            await self.bus.publish_task(new_task)
            step_count += 1

            # 6. Wait for the Executor result
            result = await self._wait_for_result(task_id, timeout=self._timeout_budget())

            if result is None:
                err = "🧠 [Planner/Smart] Execution timed out; stopping"
                logger.error(err)
                await self.bus.publish_log({"type": "error", "content": err})
                break

            # 7. Record in history
            self.history.append({
                "action": action,
                "target": target,
                "value": value,
                "status": result.get('status', 'error'),
                "message": result.get('message', ''),
            })

            status_icon = "✅" if result['status'] == 'success' else "❌"
            msg = f"🧠 [Planner/Smart] {status_icon} Step {step_count}: {action} → {result['status']}"
            logger.info(msg)
            await self.bus.publish_log({"type": "observation", "content": msg})

            await asyncio.sleep(0.5)

        if step_count >= max_steps:
            msg = f"🧠 [Planner/Smart] ⚠️ Reached the maximum step count: {max_steps}; stopping safely"
            logger.info(msg)
            await self.bus.publish_log({"type": "error", "content": msg})

        self.running = False
        await self.bus.shutdown()

    async def _wait_for_result(self, task_id: str, timeout: int = 120) -> dict:
        """Wait for the ResultEvent with the specified task_id; return None on timeout"""
        start = time.time()
        while self.running and (time.time() - start) < timeout:
            result = await self.bus.get_result(timeout=0.5)
            if result:
                self._handle_result(result)
                if result.get('task_id') == task_id:
                    return result
        return None

    # ═══════════════════════════════════════════
    # Public methods
    # ═══════════════════════════════════════════

    async def run(self):
        logger.info(f"[Planner] Started (async). Goal: {self.task_goal} | Mode: {self.mode}")

        if self._is_probe_mode():
            await self._run_probe_mode()
        elif self.mode == "smart":
            await self._run_smart_mode()
        else:
            await self._run_quick_mode()

    def _handle_result(self, result: ResultEvent):
        if result['data'] and isinstance(result['data'], dict):
            self.context.update(result['data'])

    def stop(self):
        self.running = False
