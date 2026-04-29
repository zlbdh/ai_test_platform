import time
import datetime
import base64
import logging

logger = logging.getLogger(__name__)

from playwright.sync_api import sync_playwright
from core.event_bus import EventBus, SENTINEL
from core.protocol import TaskEvent, ResultEvent

from core.browser import get_page_state, sync_analyze_with_som, get_clean_html
from core.api_tools import http_request
from core.db_tools import execute_sql, snapshot_db, diff_db, backup_db
from core.session_manager import session_manager
from core.config import Config
from core.dom_indexer import dom_indexer
from core.session_bootstrap import apply_auth_bootstrap
from core.execution_profile import PROBE_EXECUTION_MODE, should_block_probe_action
from agents.inspector_agent import InspectorAgent

class ExecutorAgent:
    """
    手眼 (The Hands): 负责执行具体的浏览器操作。
    Phase 5 混合架构：sync Playwright 在独立线程运行，通过 EventBus sync 方法通信。
    
    集成:
    - Phase 1: DomIndexer 智能元素索引 + 4 层 fallback
    - Phase 2: 每步执行后保存 page_state 到 SharedBrowserState
    - Phase 4: assert 语义验证（精确文本匹配 → LLM 语义 fallback）
    """
    def __init__(
        self,
        bus: EventBus,
        session_id: str = "default_session",
        browser_mode: str = "chromium",
        target_url: str = "",
        execution_profile: dict | None = None,
    ):
        from core.session_manager import session_manager
        self.session_id = session_id
        self.session = session_manager.get_session(session_id)
        self.browser_mode = browser_mode
        self.bus = bus
        self.running = True
        self.inspector = InspectorAgent()
        self.target_url = target_url  # ★ 初始导航目标
        self._step_sequence = 0
        self.execution_profile = execution_profile or {}

    def _is_probe_mode(self) -> bool:
        return self.execution_profile.get("execution_mode") == PROBE_EXECUTION_MODE

    def _probe_block_reason(self, action: str, target: str = "", value: str = "") -> str:
        blocked, reason = should_block_probe_action(action, target, value)
        return reason if blocked else ""

    def _resolve_step_index(self, task: TaskEvent) -> int:
        step_index = task.get("step_index")
        if isinstance(step_index, int):
            self._step_sequence = max(self._step_sequence, step_index + 1)
            return step_index
        current = self._step_sequence
        self._step_sequence += 1
        return current

    def _build_step_log(
        self,
        *,
        log_type: str,
        event: str,
        step_desc: str,
        content: str,
        task_id: str | None = None,
        action: str = "",
        target: str = "",
        value: str = "",
        step_index: int | None = None,
        ui_track: bool = True,
        **extra,
    ) -> dict:
        log_entry = {
            "type": log_type,
            "event": event,
            "step": step_desc,
            "content": content,
            "action": action,
            "target": target,
            "value": value,
            "ui_track": ui_track,
        }
        if task_id is not None:
            log_entry["task_id"] = task_id
        if step_index is not None:
            log_entry["step_index"] = step_index
        log_entry.update(extra)
        return log_entry

    def _drain_browser_commands(self, page, max_commands: int = 10) -> int:
        try:
            return self.session.process_browser_commands(page=page, max_commands=max_commands)
        except Exception as exc:
            logger.warning(f"[Executor] Browser command bridge failed: {exc}")
            return 0

    def _try_auto_resolve_captcha(self, page):
        try:
            from core.auth_interceptor import fill_captcha_if_present

            code = fill_captcha_if_present(page)
            if not code:
                return None

            logger.info(f"[Executor] CAPTCHA auto-resolved with code: {code}")
            self.bus.publish_log_sync({"type": "heal", "content": f"🔐 自动识别并填写验证码: {code}"})
            self.session.set_intervention_screenshot(None)
            try:
                self.session.set_page_state(get_page_state(page))
            except Exception as page_state_err:
                logger.debug(f"[Executor] CAPTCHA page state refresh skipped: {page_state_err}")
            return self._take_screenshot(page)
        except Exception as exc:
            logger.warning(f"[Executor] CAPTCHA auto-resolve failed: {exc}")
            return None

    def _is_captcha_blocking_step(self, action: str, target: str) -> bool:
        if action not in ("fill", "click"):
            return False
        lowered = str(target or "").lower()
        keywords = ("登录", "提交", "确认", "login", "submit", "captcha", "验证", "协议")
        return any(keyword in lowered for keyword in keywords)

    def _apply_session_bootstrap(self, page):
        payload = self.session.get_context("auth_bootstrap")
        if not isinstance(payload, dict) or not payload:
            return None

        if self.session.get_context("auth_bootstrap_applied"):
            cached = self.session.get_context("auth_bootstrap_result")
            return cached if isinstance(cached, dict) else None

        result = apply_auth_bootstrap(page, payload)
        self.session.set_context("auth_bootstrap_applied", True)
        self.session.set_context("auth_bootstrap_result", result)
        target_url = result.get("target_url") or result.get("bootstrap_url") or payload.get("base_url")
        self.bus.publish_log_sync({"type": "system", "content": f"🔐 已应用会话预认证并进入: {target_url}"})
        logger.info(f"[Executor] Session bootstrap applied: {target_url}")
        return result

    def run(self):
        """Main loop: 在独立线程中运行，使用 sync Playwright。"""
        playwright = None
        browser = None
        page = None
        
        try:
            playwright = sync_playwright().start()
            logger.info(f"[Executor] Browser launching... Mode: {self.browser_mode}")
            
            if self.browser_mode == "real":
                # 连接到用户运行在 9222 端口的实机 Chrome
                try:
                    browser = playwright.chromium.connect_over_cdp("http://localhost:9222")
                    context = browser.contexts[0] if browser.contexts else browser.new_context()
                    page = context.pages[0] if context.pages else context.new_page()
                except Exception as cdp_err:
                    logger.error(f"[Executor] CDP Connection failed (Is Chrome running with --remote-debugging-port=9222?): {cdp_err}")
                    raise
            else:
                # 默认 Chromium 沙盒隔离环境
                launch_args = [
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--no-sandbox',
                    '--disable-infobars',
                ]
                browser = playwright.chromium.launch(
                    headless=True,  # 无头模式：不弹出窗口，通过 Live View 沙箱展示
                    args=launch_args,
                )
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                )
                
                # Stealth anti-detection scripts
                stealth_js = """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
                window.chrome = { runtime: {} };
                """
                context.add_init_script(stealth_js)
                
                page = context.new_page()
                
            self.session.set_page(page)
            logger.info("[Executor] Browser ready.")

            bootstrap_result = None
            try:
                bootstrap_result = self._apply_session_bootstrap(page)
            except Exception as bootstrap_err:
                logger.error(f"[Executor] Session bootstrap failed: {bootstrap_err}")
                self.bus.publish_log_sync({"type": "error", "content": f"会话预认证失败: {bootstrap_err}"})
                raise

            bootstrap_target = ""
            if isinstance(bootstrap_result, dict):
                bootstrap_target = str(
                    bootstrap_result.get("target_url")
                    or bootstrap_result.get("bootstrap_url")
                    or ""
                ).strip()

            navigation_target = "" if bootstrap_target else str(self.target_url or "").strip()

            # ★ 自动导航到 target_url（避免 AI 浪费步骤猜测地址）
            if navigation_target:
                try:
                    logger.info(f"[Executor] Auto-navigating to target: {navigation_target}")
                    page.goto(navigation_target, wait_until='domcontentloaded', timeout=30000)
                    try:
                        page.wait_for_load_state('networkidle', timeout=10000)
                    except Exception:
                        pass
                    self.bus.publish_log_sync(
                        self._build_step_log(
                            log_type="action",
                            event="bootstrap_navigation",
                            step_desc=f"goto({navigation_target})",
                            content=f"▶ 自动导航到目标: {navigation_target}",
                            action="goto",
                            target=navigation_target,
                            ui_track=False,
                        )
                    )
                    # Update page state for planner
                    try:
                        page_state = get_page_state(page)
                        self.session.set_page_state(page_state)
                    except Exception:
                        pass
                    logger.info(f"[Executor] Target URL loaded: {page.url}")
                except Exception as nav_err:
                    logger.warning(f"[Executor] Auto-navigation failed: {nav_err}")
                    self.bus.publish_log_sync({"type": "error", "content": f"自动导航失败: {nav_err}"})
            elif bootstrap_target:
                try:
                    page_state = get_page_state(page)
                    self.session.set_page_state(page_state)
                except Exception:
                    pass

            while self.running:
                self._drain_browser_commands(page, max_commands=5)
                task = self.bus.get_task_sync(timeout=0.1)
                
                if task is None:
                    self._drain_browser_commands(page, max_commands=5)
                    # 空闲时也截图，保持 Live View 更新
                    try:
                        raw = page.screenshot(type='jpeg', quality=50, timeout=3000)
                        self.session.set_frame(raw)
                    except Exception:
                        pass
                    continue
                
                if isinstance(task, type(SENTINEL)):
                    logger.info("[Executor] Received Sentinel. Shutting down.")
                    break
                
                task_id = task['id']
                action = task.get('action', '')
                target = task.get('target', '')
                value = task.get('value', '')
                step_index = self._resolve_step_index(task)

                if self._is_probe_mode():
                    block_reason = self._probe_block_reason(action, target, value)
                    if block_reason:
                        logger.warning("[Executor] Probe action blocked: %s", block_reason)
                        self.bus.publish_log_sync(
                            {
                                "type": "system",
                                "event": "probe_action_blocked",
                                "status": "warning",
                                "task_id": task_id,
                                "action": action,
                                "target": target,
                                "value": value,
                                "step_index": step_index,
                                "content": block_reason,
                                "ui_track": False,
                            }
                        )
                        self.bus.publish_result_sync(
                            {
                                "task_id": task_id,
                                "status": "error",
                                "message": f"Probe policy blocked: {block_reason}",
                                "screenshot": None,
                                "data": None,
                                "duration": 0,
                                "timestamp": str(datetime.datetime.now()),
                                "action": action,
                                "target": target,
                                "value": value,
                                "step_index": step_index,
                            }
                        )
                        self.bus.publish_log_sync(
                            self._build_step_log(
                                log_type="result",
                                event="step_result",
                                step_desc=f"{action}({target})",
                                content=f"⚠️ blocked by probe policy: {block_reason}",
                                task_id=task_id,
                                action=action,
                                target=target,
                                value=value,
                                step_index=step_index,
                                status="error",
                                duration=0,
                            )
                        )
                        continue
                
                start_time = time.time()
                step_desc = f"{action}({target})"
                logger.info(f"[Executor] Executing: {step_desc}")
                self.bus.publish_log_sync(
                    self._build_step_log(
                        log_type="action",
                        event="step_start",
                        step_desc=step_desc,
                        content=f"▶ {step_desc}",
                        task_id=task_id,
                        action=action,
                        target=target,
                        value=value,
                        step_index=step_index,
                    )
                )
                
                # Execute
                result_status, output_data, error_msg = "success", None, None
                screenshot_b64 = None
                try:
                    output_data = self._execute_action(page, task)
                    
                    # Log assertions specially
                    if action == 'assert' and output_data:
                        self.bus.publish_log_sync(
                            self._build_step_log(
                                log_type="assertion",
                                event="assertion_pass",
                                step_desc=step_desc,
                                content=str(output_data),
                                task_id=task_id,
                                action=action,
                                target=target,
                                value=value,
                                step_index=step_index,
                                status="pass",
                            )
                        )
                    
                    # Take screenshot on success
                    screenshot_b64 = self._take_screenshot(page)
                    
                except Exception as e:
                    result_status = "error"
                    error_msg = str(e)
                    logger.error(f"[Executor] Action Failed: {error_msg}")
                    self.bus.publish_log_sync(
                        self._build_step_log(
                            log_type="error",
                            event="step_error",
                            step_desc=step_desc,
                            content=error_msg,
                            task_id=task_id,
                            action=action,
                            target=target,
                            value=value,
                            step_index=step_index,
                            status="error",
                        )
                    )
                    
                    # === Self-Healing: 尝试自动修复 ===
                    try:
                        from agents.healer import self_heal
                        
                        elements_text = ""
                        try:
                            elements_text = dom_indexer.format_for_llm(max_items=40)
                        except Exception:
                            pass
                        
                        page_text = ""
                        try:
                            page_text = page.evaluate("() => document.body?.innerText?.substring(0, 800) || ''")
                        except Exception:
                            pass
                        
                        self.bus.publish_log_sync({"type": "heal", "content": "🔧 启动自愈机制..."})
                        healed = self_heal(
                            failed_step=task,
                            error_msg=error_msg,
                            page_content=page_text,
                            interactive_elements=elements_text
                        )
                        
                        if healed and healed.get('action'):
                            healed_desc = f"{healed['action']}({healed.get('target', '')})"
                            self.bus.publish_log_sync({"type": "heal", "content": f"🩹 自愈: {step_desc} → {healed_desc}"})
                            logger.info(f"[Executor] Heal attempt: {healed_desc}")
                            
                            try:
                                output_data = self._execute_action(page, healed)
                                result_status = "success"
                                error_msg = None
                                self.bus.publish_log_sync({"type": "heal", "content": f"✅ 自愈成功: {healed_desc}"})
                            except Exception as heal_err:
                                logger.warning(f"[Executor] Heal execution failed: {heal_err}")
                                self.bus.publish_log_sync({"type": "heal", "content": f"❌ 自愈失败: {heal_err}"})
                        else:
                            logger.info("[Executor] Healer returned no fix.")
                    except Exception as heal_ex:
                        logger.warning(f"[Executor] Self-healing error: {heal_ex}")
                    
                    if result_status == "error":
                        try:
                            screenshot_b64 = self._take_screenshot(page)
                        except Exception:
                            screenshot_b64 = None

                # === Inspector 视觉质检：执行成功后主动审查截图 ===
                # L2: 智能触发 — 关键操作必检 + 间隔抽检（替代原来的全局跳过）
                _is_critical = self._is_captcha_blocking_step(action, target)
                if not hasattr(self, '_inspector_step_counter'):
                    self._inspector_step_counter = 0
                self._inspector_step_counter += 1
                _inspector_interval = getattr(Config, 'INSPECTOR_INTERVAL', 5)
                _should_inspect = _is_critical or (self._inspector_step_counter % _inspector_interval == 0)
                if _should_inspect and result_status == "success" and InspectorAgent.should_inspect(action) and screenshot_b64:
                    try:
                        page_state = self.session.get_page_state() or {}
                        inspection = self.inspector.inspect(
                            screenshot_b64=screenshot_b64,
                            step_desc=f"{action} {target}".strip(),
                            expected_outcome=value or "",
                            page_state=page_state,
                        )
                        if not inspection.passed:
                            # === HIL: CAPTCHA 检测触发人工介入（增强版） ===
                            if inspection.anomalies and "CAPTCHA_DETECTED" in inspection.anomalies:
                                screenshot_after_fill = self._try_auto_resolve_captcha(page)
                                if screenshot_after_fill:
                                    screenshot_b64 = screenshot_after_fill
                                    result_status = "success"
                                    error_msg = None
                                elif not self._is_captcha_blocking_step(action, target):
                                    logger.info("[Executor] CAPTCHA detected on non-blocking step; deferring intervention.")
                                    self.bus.publish_log_sync({"type": "heal", "content": "ℹ️ 检测到验证码，但当前步骤不是提交场景，继续执行。"})
                                    result_status = "success"
                                    error_msg = None
                                else:
                                    logger.warning("[Executor] CAPTCHA detected! Triggering CaptchaWaiter...")
                                    self.session.set_intervention_screenshot(screenshot_b64)
                                    from core.auth_interceptor import captcha_waiter
                                    resolved = captcha_waiter.wait_for_human(
                                        bus=self.bus,
                                        session=self.session,
                                        timeout=120,
                                    )
                                    sig = self.session.get_signal()
                                    if not resolved or sig == "STOPPED":
                                        result_status = "error"
                                        error_msg = "用户终止了任务（验证码场景）" if sig == "STOPPED" else "CAPTCHA 等待超时"
                                    elif sig == "INTERVENTION":
                                        # 超时未响应，自动恢复执行（可能是误判）
                                        logger.warning("[Executor] INTERVENTION 超时，自动恢复执行（可能是误判）")
                                        self.bus.publish_log_sync({"type": "heal", "content": "⚠️ 人工介入超时(30s)，自动恢复执行"})
                                        self.session.set_signal("RUNNING")
                                        result_status = "success"
                                        error_msg = None
                                    else:
                                        # 人工已完成验证码，重新截图继续
                                        self.bus.publish_log_sync({"type": "heal", "content": "✅ 人工介入完成，继续执行..."})
                                        screenshot_b64 = self._take_screenshot(page)
                                        result_status = "success"
                                        error_msg = None
                            else:
                                result_status = "error"
                                error_msg = f"Inspector 驳回 (confidence={inspection.confidence:.0%}): {inspection.reason}"
                                if inspection.anomalies:
                                    error_msg += f" | 异常: {', '.join(inspection.anomalies)}"
                                logger.warning(f"[Executor] {error_msg}")
                                self.bus.publish_log_sync({"type": "error", "step": step_desc, "content": error_msg})
                        else:
                            logger.debug(f"[Executor] Inspector passed (confidence={inspection.confidence:.0%})")
                    except Exception as insp_err:
                        logger.warning(f"[Executor] Inspector error (auto-passing): {insp_err}")

                duration = round(time.time() - start_time, 2)
                
                # Phase 2: 保存页面状态到 SharedBrowserState（供 Smart Mode Planner 读取）
                try:
                    page_state = get_page_state(page)
                    self.session.set_page_state(page_state)
                except Exception as ps_err:
                    logger.warning(f"[Executor] Page state save failed: {ps_err}")
                
                result: ResultEvent = {
                    "task_id": task_id,
                    "status": result_status,
                    "message": error_msg if error_msg else str(output_data or "OK"),
                    "screenshot": screenshot_b64,
                    "data": output_data if isinstance(output_data, dict) else None,
                    "duration": duration,
                    "timestamp": str(datetime.datetime.now()),
                    "action": action,
                    "target": target,
                    "value": value,
                    "step_index": step_index,
                }
                
                self.bus.publish_result_sync(result)
                
                log_entry = self._build_step_log(
                    log_type="result",
                    event="step_result",
                    step_desc=step_desc,
                    content=f"{'✅' if result_status == 'success' else '❌'} {result_status} ({duration}s)",
                    task_id=task_id,
                    action=action,
                    target=target,
                    value=value,
                    step_index=step_index,
                    status=result_status,
                    duration=duration,
                    screenshot=screenshot_b64,
                )
                self.bus.publish_log_sync(log_entry)
                
        except Exception as e:
            logger.critical(f"[Executor] FATAL Error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        finally:
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass
            if playwright:
                try:
                    playwright.stop()
                except Exception:
                    pass
            self.session.set_page(None)
            self.session.set_status("IDLE")
            logger.info("[Executor] Browser closed.")
    
    def _check_signal(self):
        signal = self.session.get_signal()
        while signal == "PAUSED" and self.running:
            time.sleep(0.5)
            signal = self.session.get_signal()
        if signal == "STOPPED":
            self.running = False
            raise Exception("Task stopped by user.")

    def _execute_action(self, page, task: TaskEvent):
        from agents.action_handlers import ACTION_REGISTRY

        action = task['action']
        target = task.get('target', '')
        value = task.get('value', '')

        handler = ACTION_REGISTRY.get(action)
        if handler is None:
            raise Exception(f"Unknown action: {action}")

        # 除 wait 以外，动作执行前检查信号
        if action != 'wait':
            self._check_signal()

        # 构建统一的上下文参数
        return handler(
            page=page,
            target=target,
            value=value,
            dom_indexer=dom_indexer,
            session=self.session,
            bus=self.bus,
            check_signal=self._check_signal,
        )
    def _take_screenshot(self, page):
        try:
            raw = page.screenshot(type='jpeg', quality=50, timeout=5000)
            self.session.set_frame(raw)  # 同步更新 Live View 帧
            return base64.b64encode(raw).decode('utf-8')
        except Exception:
            return None

    def stop(self):
        self.running = False



