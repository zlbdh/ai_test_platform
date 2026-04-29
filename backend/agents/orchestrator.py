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
    指挥官 (The Conductor): 管理 Planner 和 Executor 的生命周期。
    Phase 6 增强版:
    - Executor: 在独立线程运行（sync Playwright 需要独立线程）
    - Planner: 在 asyncio 事件循环运行（async，与 FastAPI 共享循环）
    - 通信: EventBus 混合模式（Executor 用 sync, Planner 用 async）
    - 线程异常传播: Executor 异常存入 _executor_error，Planner 完成时检测
    - SSE 序号: 每条日志带递增序号，支持 Last-Event-ID 断线重连
    - 报告持久化: 任务完成后自动写入 SQLite
    """
    def __init__(self, session_id: str = "default_session"):
        self.session_id = session_id
        self.session = session_manager.get_session(session_id)
        
        self.planner = None
        self.executor = None
        self.bus = None
        self.e_thread = None      # Executor 独立线程
        self._planner_task = None  # Planner asyncio.Task
        self.active_task_id = ""
        self.is_running = False
        self._executor_error: Optional[str] = None  # Executor 线程异常
        self._task_requirement = ""  # 当前任务需求（用于持久化）
        self._task_requirement_raw = ""  # 原始输入（用于诊断）
        self._task_requirement_display = ""  # 用户可见标题
        self._task_target_url = ""  # 目标 URL
        self._task_text_state = NORMAL_TEXT_STATE
        self._task_mode = "smart"   # planner_mode
        self._execution_mode = DEFAULT_EXECUTION_MODE
        self._interaction_policy = DEFAULT_INTERACTION_POLICY
        self._step_budget: Optional[int] = None
        self._execution_profile = resolve_execution_profile()
        self._start_time = 0.0     # 任务开始时间（用于计算时长）
        self._log_seq = 0  # SSE 日志序号
        self._execution_group_id = ""

    def _generate_task_id(self) -> str:
        """生成稳定且低冲突的任务 ID。"""
        return f"task_{uuid.uuid4().hex}"

    @staticmethod
    def _looks_broken_text(value: Optional[str]) -> bool:
        return looks_broken_text(value)

    def _resolve_task_requirement(self, task_requirement: str, target_url: str = "") -> tuple[str, str]:
        display_requirement, text_state = resolve_display_text(task_requirement, target_url, fallback="未命名测试")
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
        # ★ 将 target_url 与预认证会话提示注入 task_goal，确保 Planner 不再重复登录/切站
        effective_goal = self._build_effective_goal(task_requirement, target_url)
        if target_url:
            effective_goal = f"【重要：必须首先访问目标地址 {target_url}，不要猜测其他端口或地址】{effective_goal}"
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
        self.session.set_page_state({})  # 清零旧页面状态，防止 Planner 误判
        self.session.set_context("task_display", self._task_requirement_display)
        self.session.set_context("task_text_state", self._task_text_state)
        self.session.set_context("task_requirement_raw", self._task_requirement_raw)
        self.session.set_context("execution_mode", self._execution_mode)
        self.session.set_context("interaction_policy", self._interaction_policy)
        self.session.set_context("step_budget", self._step_budget)
        self.session.set_context("execution_profile", dict(self._execution_profile))
        self._publish_text_state_log()
        
        # Executor: 独立线程（sync Playwright 需要）
        self.e_thread = threading.Thread(target=self._run_executor, daemon=True, name="ExecutorThread")
        self.e_thread.start()
        
        # Planner: asyncio.Task（与 FastAPI 共享事件循环）
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
                    f"【会话预认证已完成：当前已登录且已切换到{site_hint}。"
                    "除非需求明确要求重新登录或切换站点，否则不要再执行登录、点击城市/站点或切换站点动作。】"
                )
            else:
                effective_goal = (
                    f"{effective_goal}"
                    "【会话预认证已完成：当前已登录。除非需求明确要求重新登录或切换站点，否则不要再执行登录或切站动作。】"
                )

        return effective_goal

    def _run_executor(self):
        """在独立线程运行 Executor（sync Playwright）"""
        try:
            self.executor.run()
        except Exception as e:
            error_msg = f"Executor crashed: {e}"
            logger.error(f"[Orchestrator] {error_msg}")
            self._executor_error = error_msg
            # 尝试将错误发送到 EventBus，让 SSE 流能收到
            try:
                if self.bus:
                    self.bus.publish_log_sync({"type": "error", "content": f"❌ {error_msg}"})
            except Exception:
                pass

    async def _run_planner(self):
        """在 asyncio 事件循环运行 Planner"""
        try:
            await self.planner.run()
        except Exception as e:
            logger.error(f"[Orchestrator] Planner error: {e}")
            # 发送 Planner 错误日志
            try:
                if self.bus:
                    await self.bus.publish_log({"type": "error", "content": f"❌ Planner error: {e}"})
            except Exception:
                pass
        finally:
            # Planner 完成后等待 Executor 线程退出
            if self.e_thread and self.e_thread.is_alive():
                logger.info("[Orchestrator] Waiting for Executor thread to finish...")
                for _ in range(100):  # 最多 10 秒
                    if not self.e_thread.is_alive():
                        break
                    await asyncio.sleep(0.1)
            
            # 检测 Executor 线程是否异常退出
            if self._executor_error:
                logger.warning(f"[Orchestrator] Executor had error: {self._executor_error}")
                try:
                    if self.bus:
                        await self.bus.publish_log({
                            "type": "error",
                            "content": f"⚠️ Executor 异常退出: {self._executor_error}"
                        })
                except Exception:
                    pass
            
            # 持久化测试结果
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
        SSE Generator: 从 EventBus 实时读取日志。
        支持 Last-Event-ID 断线重连 + 心跳保活。
        """
        # 如果客户端重连且提供了 start_seq，先重放已有日志
        if start_seq > 0:
            existing_logs = self.session.get_logs()
            for i, log in enumerate(existing_logs):
                seq = i + 1
                if seq > start_seq:
                    yield f"id: {seq}\ndata: {json.dumps(log, ensure_ascii=False)}\n\n"
            self._log_seq = len(existing_logs)

        heartbeat_interval = 15  # 每 15 秒发送心跳
        last_heartbeat = time.time()

        while self.is_running:
            if self.bus:
                log = await self.bus.get_log(timeout=0.5)
                if log:
                    self._log_seq += 1
                    yield f"id: {self._log_seq}\ndata: {json.dumps(log, ensure_ascii=False)}\n\n"
                    last_heartbeat = time.time()
                elif time.time() - last_heartbeat > heartbeat_interval:
                    # SSE 心跳：防止代理/客户端因长时间无数据断连
                    yield f": heartbeat\n\n"
                    last_heartbeat = time.time()
            else:
                await asyncio.sleep(0.1)
        
        # Drain: 任务结束后，读取残余日志（最多 50 条防无限循环）
        if self.bus:
            drain_count = 0
            while drain_count < 50:
                log = self.bus.get_log_sync(timeout=0.1)
                if not log:
                    break
                self._log_seq += 1
                yield f"id: {self._log_seq}\ndata: {json.dumps(log, ensure_ascii=False)}\n\n"
                drain_count += 1
        
        # 发送 done 事件
        self._log_seq += 1
        yield f"id: {self._log_seq}\ndata: {json.dumps({'type': 'done'})}\n\n"

    def _persist_test_run(self):
        """将测试结果持久化到 SQLite"""
        try:
            logs = self.session.get_logs()
            error_count = sum(1 for l in logs if l.get("type") == "error")
            heal_success = sum(1 for l in logs if l.get("type") == "heal" and "自愈成功" in l.get("content", ""))
            display_requirement = self._task_requirement_display or self._task_requirement or "unknown"
            raw_requirement = self._task_requirement_raw or self._task_requirement or ""
            task_text_state = self._task_text_state or (
                BROKEN_TEXT_STATE if self._looks_broken_text(raw_requirement) else NORMAL_TEXT_STATE
            )
            
            # === 智能状态判定 ===
            # 先检查最终日志是否包含 "Mission Accomplished"（AI 确认任务完成）
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
                # 有错误但 AI 最终确认任务完成 → recovered（过程曲折但结局圆满）
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

            # === Allure Report 自动生成 ===
            try:
                reporter = get_reporter()
                reporter.start_suite(display_requirement or "AI Test Suite")
                
                # 将执行日志转化为 Allure TestResult
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

            # === 发送完成通知 ===
            try:
                from core.notify_helper import send_completion_notification
                duration_str = f"{duration_ms / 1000:.1f}s" if duration_ms else "N/A"
                notification_coro = send_completion_notification(
                    title="AI 编排测试报告",
                    status="completed" if status in ("success", "recovered", "healed") else "failed",
                    summary=f"任务: {display_requirement or 'unknown'}\n目标: {self._task_target_url or 'N/A'}",
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
