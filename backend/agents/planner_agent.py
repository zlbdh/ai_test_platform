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
    大脑 (The Brain): 负责高层规划与决策。
    Phase 5: 全 async 版本。
    
    支持双模式:
    - smart: 单步推理循环（每步观察页面→LLM决策→执行→循环）
    - quick: 一次性生成全部步骤后批量执行
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
                f"只读探针已将规划结果收敛为 {len(trimmed_cases)} 个场景 / {consumed_steps} 步"
                f"（原始 {original_scenarios} 个场景 / {original_steps} 步）"
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
        msg = "🧠 [Planner/Probe] 启动只读探针模式，仅读取页面状态，不执行输入或提交"
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
                    f"只读探针完成: URL={current_url} | 标题={current_title or 'N/A'} | "
                    f"可交互元素索引数≈{interactive_count}"
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
                err = "🧠 [Planner/Probe] 未提供目标地址，且当前会话无可探测页面，已快速结束"
                logger.warning(err)
                await self.bus.publish_log({"type": "error", "content": err})
                self.running = False
                await self.bus.shutdown()
                return
            await asyncio.sleep(0.5)

        err = "🧠 [Planner/Probe] 探针超时：未在预算内拿到可用页面状态"
        logger.warning(err)
        await self.bus.publish_log({"type": "error", "content": err})
        self.running = False
        await self.bus.shutdown()

    def _build_loop_recovery(self, repeated_action: str, page_state: Dict[str, Any]) -> Dict[str, str]:
        """为连续死循环选择更安全的恢复动作。"""
        elements = str((page_state or {}).get('interactive_elements', '') or '')
        lowered_elements = elements.lower()

        if any(keyword in lowered_elements for keyword in ("captcha", "verification", "verify code")) or "验证码" in elements:
            return {
                "action": "done",
                "target": "检测到验证码或人工校验页面，已停止自动恢复并请求人工介入",
                "value": "",
                "override_msg": (
                    f"🧠 [Planner/Smart] ➡️ 连续重复 '{repeated_action}' 且检测到验证码，"
                    "停止自动恢复并请求人工介入"
                ),
            }

        if '登录' in elements or '提交' in elements:
            return {
                "action": "click",
                "target": "登录按钮",
                "value": "",
                "override_msg": "🧠 [Planner/Smart] ➡️ 强制点击登录/提交以打破循环",
            }

        return {
            "action": "scroll",
            "target": "",
            "value": "down",
            "override_msg": "🧠 [Planner/Smart] ➡️ 强制滚动页面以打破循环",
        }

    # ═══════════════════════════════════════════
    # Quick Mode (一次规划)
    # ═══════════════════════════════════════════

    async def _resolve_maybe_async(self, value):
        """兼容同步/异步 planner service，避免 mock 或旧实现导致 await 失败。"""
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
                scenario_name = tc.get('scenario', '未知场景')
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
        """通过 SessionState 桥接安全获取当前页面截图。"""
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
        """Quick Mode: 一次生成全部步骤 → 批量执行（失败跳步继续）"""
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
                            msg = f"🧠 [Planner] Step {self.plan_step_index + 1}/{total_steps} Failed (跳过): {result['message']}"
                            logger.warning(msg)
                            await self.bus.publish_log({"type": "error", "content": msg})
                            # 跳到下一步而非终止全局
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
                        
                        # 场景切换时重新扫描 DOM 元素索引
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
        Smart Mode: 单步推理循环。
        每步：获取页面状态 → LLM 决策 → Executor 执行 → 收结果 → 循环
        """
        max_steps = self._step_budget()
        step_count = 0
        
        msg = f"🧠 [Planner/Smart] 开始单步推理，目标: {self.task_goal}"
        logger.info(msg)
        await self.bus.publish_log({"type": "thought", "subtype": "planner", "content": msg})
        
        # ★ 等待 Executor 浏览器就绪（解决 Planner-Executor 竞态条件）
        wait_msg = "🧠 [Planner/Smart] 等待浏览器就绪..."
        logger.info(wait_msg)
        await self.bus.publish_log({"type": "thought", "subtype": "planner", "content": wait_msg})
        for _wait in range(60):  # 最多等 30 秒
            if self.session.get_page() is not None:
                break
            await asyncio.sleep(0.5)
        else:
            err = "🧠 [Planner/Smart] ⚠️ 浏览器未在 30 秒内就绪，终止"
            logger.error(err)
            await self.bus.publish_log({"type": "error", "content": err})
            self.running = False
            await self.bus.shutdown()
            return
        
        ready_msg = "🧠 [Planner/Smart] ✅ 浏览器已就绪，开始推理"
        logger.info(ready_msg)
        await self.bus.publish_log({"type": "thought", "subtype": "planner", "content": ready_msg})
        
        while self.running and step_count < max_steps:
            # 1. 获取当前页面状态
            page_state = self.session.get_page_state()
            
            if not page_state:
                page_state = {"url": "（未导航）", "title": "", "interactive_elements": "", "visible_text": ""}
            
            # 1.5 ★ L1: 获取页面截图供 VLM 多模态推理
            screenshot_b64 = await self._capture_page_screenshot()
            
            # 2. LLM 单步推理（sync，用 to_thread）
            msg = f"🧠 [Planner/Smart] Step {step_count + 1}: 正在推理...{' (📸 Vision)' if screenshot_b64 else ''}"
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
                err = f"🧠 [Planner/Smart] 推理异常: {e}"
                logger.error(err)
                await self.bus.publish_log({"type": "error", "content": err})
                break
            
            action = next_step.get('action', 'done')
            target = next_step.get('target', '')
            value = next_step.get('value', '')
            thinking = next_step.get('thinking', '')
            
            if thinking:
                await self.bus.publish_log({"type": "thought", "subtype": "planner", "content": f"💭 {thinking}"})
            
            # === L3: 状态级循环检测 — 页面错误信息不变时提前终止 ===
            if len(self.history) >= 8:
                recent_msgs = [h.get('message', '')[:80] for h in self.history[-8:]]
                unique_msgs = set(m for m in recent_msgs if m.strip())
                if len(unique_msgs) <= 2 and len([m for m in recent_msgs if m.strip()]) >= 8:
                    state_loop_msg = f"🧠 [Planner/Smart] ⛔ 状态循环: 页面信息 8 步未变 → {list(unique_msgs)[:1]}"
                    logger.warning(state_loop_msg)
                    await self.bus.publish_log({"type": "error", "content": state_loop_msg})
                    action = 'done'
                    target = f'卡在相同页面状态: {list(unique_msgs)[:1]}'
                    value = ''
            
            # === 硬性循环截断（防止 LLM 忽略 prompt 中的警告）===
            if self.history and len(self.history) >= 5:
                consecutive = 1
                last_a = self.history[-1].get('action', '')
                for h in reversed(self.history[:-1]):
                    if h.get('action', '') == last_a:
                        consecutive += 1
                    else:
                        break
                
                # 如果 LLM 又返回了相同动作，并且已连续 5+ 次 → 强制覆盖
                if consecutive >= 5 and action == last_a:
                    warn = f"🧠 [Planner/Smart] ⛔ 检测到连续 {consecutive+1}x '{action}' 死循环！强制覆盖 LLM 决策"
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
            
            # 3. 检查是否完成

            if action == 'done':
                msg = f"🧠 [Planner/Smart] 任务完成: {target}"
                logger.info(msg)
                await self.bus.publish_log({"type": "system", "content": f"Mission Accomplished. {target}"})
                break
            
            # 3.5 检查是否推理失败
            if action == 'error':
                msg = f"🧠 [Planner/Smart] ❌ 推理失败: {target}"
                logger.error(msg)
                await self.bus.publish_log({"type": "error", "content": msg})
                break
            
            # 4. 变量解析
            target = self._resolve_variables(target)
            value = self._resolve_variables(value)

            blocked, block_reason = should_block_probe_action(action, target, value) if self._is_probe_mode() else (False, "")
            if blocked:
                await self._publish_probe_event(
                    "probe_action_blocked",
                    f"{block_reason}，已结束只读探针任务",
                    action=action,
                    target=target,
                    value=value,
                    step_budget=self.execution_profile.get("step_budget"),
                )
                await self.bus.publish_log({"type": "system", "content": f"Mission Accomplished. {block_reason}"})
                break
            
            # 5. 发送到 Executor
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
            
            # 6. 等待 Executor 返回结果
            result = await self._wait_for_result(task_id, timeout=self._timeout_budget())
            
            if result is None:
                err = "🧠 [Planner/Smart] 执行超时，终止"
                logger.error(err)
                await self.bus.publish_log({"type": "error", "content": err})
                break
            
            # 7. 记录到历史
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
            msg = f"🧠 [Planner/Smart] ⚠️ 达到最大步数 {max_steps}，安全终止"
            logger.info(msg)
            await self.bus.publish_log({"type": "error", "content": msg})
        
        self.running = False
        await self.bus.shutdown()

    async def _wait_for_result(self, task_id: str, timeout: int = 120) -> dict:
        """等待指定 task_id 的 ResultEvent，超时返回 None"""
        start = time.time()
        while self.running and (time.time() - start) < timeout:
            result = await self.bus.get_result(timeout=0.5)
            if result:
                self._handle_result(result)
                if result.get('task_id') == task_id:
                    return result
        return None

    # ═══════════════════════════════════════════
    # 公共方法
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
