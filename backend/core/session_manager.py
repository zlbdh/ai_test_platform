import asyncio
from concurrent.futures import Future
import inspect
import queue as thread_queue
import threading
from typing import Callable, Dict, List, Optional, Tuple

class SessionState:
    """
    Isolated test-session state
    Replace the SharedBrowserState singleton so sessions can run concurrently with isolated state.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id

        self.page = None
        self._page_owner_thread_id = None
        self.execution_signal = "RUNNING"  # RUNNING, PAUSED, STOPPED
        self.agent_status = "IDLE"         # IDLE, RUNNING
        self.current_task = ""
        self.logs = []

        # Locks for thread safety
        self._logs_lock = threading.Lock()
        self._signal_lock = threading.Lock()
        self._page_lock = threading.Lock()

        self._active_context_id = None
        self._pause_reason = None
        self._intervention_screenshot = None

        self._page_state: dict = {}
        self._page_state_lock = threading.Lock()

        self.context_data = {}
        self._context_lock = threading.Lock()

        self._latest_frame: bytes = None
        self._frame_lock = threading.Lock()
        self._browser_command_queue: thread_queue.Queue = thread_queue.Queue()

    # --- Methods migrated from SharedBrowserState ---
    def set_status(self, status: str, task: str = ""):
        self.agent_status = status
        if task:
            self.current_task = task

    def append_log(self, log_entry: dict):
        with self._logs_lock:
            self.logs.append(log_entry)

    def get_logs(self) -> List[dict]:
        with self._logs_lock:
            return list(self.logs)

    def clear_logs(self):
        with self._logs_lock:
            self.logs.clear()

    def get_status(self) -> Tuple[str, str]:
        return self.agent_status, self.current_task

    def set_signal(self, signal: str, reason: str = None):
        with self._signal_lock:
            self.execution_signal = signal
            if reason:
                self._pause_reason = reason
            elif signal != "PAUSED":
                self._pause_reason = None

    def set_intervention_screenshot(self, screenshot):
        self._intervention_screenshot = screenshot

    def get_intervention_screenshot(self):
        return self._intervention_screenshot

    def get_signal(self) -> str:
        with self._signal_lock:
            return self.execution_signal

    def get_pause_reason(self) -> Optional[str]:
        with self._signal_lock:
            return self._pause_reason

    def set_page_state(self, state: dict):
        with self._page_state_lock:
            self._page_state = state

    def get_page_state(self) -> dict:
        with self._page_state_lock:
            return dict(self._page_state) if self._page_state else {}

    def set_context(self, key: str, value):
        with self._context_lock:
            self.context_data[key] = value

    def get_context(self, key: str = None):
        with self._context_lock:
            if key:
                return self.context_data.get(key)
            return dict(self.context_data)

    def clear_context(self):
        with self._context_lock:
            self.context_data = {}

    def set_page(self, p, context_id=None):
        with self._page_lock:
            if context_id:
                if self._active_context_id is None or self._active_context_id == context_id:
                    self._active_context_id = context_id
                    self.page = p
                    self._page_owner_thread_id = threading.get_ident() if p is not None else None
            else:
                self.page = p
                self._page_owner_thread_id = threading.get_ident() if p is not None else None

    def clear(self, context_id=None):
        with self._page_lock:
            if context_id:
                if self._active_context_id == context_id:
                    self.page = None
                    self._active_context_id = None
                    self._page_owner_thread_id = None
            else:
                self.page = None
                self._active_context_id = None
                self._page_owner_thread_id = None
        with self._logs_lock:
            if not context_id:
                self.logs.clear()
        self._fail_pending_browser_commands(RuntimeError("Browser session cleared"))

    def get_page(self):
        with self._page_lock:
            return self.page

    def get_page_owner_thread_id(self):
        with self._page_lock:
            return self._page_owner_thread_id

    def set_frame(self, frame_bytes: bytes):
        with self._frame_lock:
            self._latest_frame = frame_bytes

    def get_frame(self) -> bytes:
        with self._frame_lock:
            return self._latest_frame

    def _fail_pending_browser_commands(self, error: Exception):
        while True:
            try:
                _, future = self._browser_command_queue.get_nowait()
            except thread_queue.Empty:
                break
            if not future.done():
                future.set_exception(error)

    async def run_browser(self, callback: Callable, timeout: float = 10.0):
        """
        Execute browser actions safely in the thread that owns the page.

        - Execute directly when the current thread owns the page
        - Otherwise dispatch the callback to the page's owning thread
        """
        page = self.get_page()
        if page is None:
            raise RuntimeError("No active browser page")

        owner_thread_id = self.get_page_owner_thread_id()
        if owner_thread_id is None or owner_thread_id == threading.get_ident():
            result = callback(page)
            if inspect.isawaitable(result):
                return await result
            return result

        future: Future = Future()
        self._browser_command_queue.put((callback, future))
        return await asyncio.wait_for(asyncio.wrap_future(future), timeout=timeout)

    def process_browser_commands(self, page=None, max_commands: int = 10) -> int:
        """
        Execute pending browser commands in the page's owning thread.
        Called repeatedly by the Executor thread.
        """
        active_page = page or self.get_page()
        if active_page is None:
            self._fail_pending_browser_commands(RuntimeError("No active browser page"))
            return 0

        processed = 0
        while processed < max_commands:
            try:
                callback, future = self._browser_command_queue.get_nowait()
            except thread_queue.Empty:
                break

            if future.cancelled():
                continue

            try:
                result = callback(active_page)
                if inspect.isawaitable(result):
                    raise RuntimeError("Cross-thread browser callbacks must be synchronous")
                if not future.done():
                    future.set_result(result)
            except Exception as exc:
                if not future.done():
                    future.set_exception(exc)
            processed += 1

        return processed


class SessionManager:
    """
    Multi-session manager
    """
    _sessions: Dict[str, SessionState] = {}
    _lock = threading.Lock()

    # Default global session ID for compatibility while migrating to explicit session_id arguments
    DEFAULT_SESSION_ID = "default_session"

    @classmethod
    def get_session(cls, session_id: str = None) -> SessionState:
        with cls._lock:
            sid = session_id or cls.DEFAULT_SESSION_ID
            if sid not in cls._sessions:
                cls._sessions[sid] = SessionState(sid)
            return cls._sessions[sid]

    @classmethod
    def remove_session(cls, session_id: str):
        with cls._lock:
            if session_id in cls._sessions:
                del cls._sessions[session_id]

    @classmethod
    def list_sessions(cls) -> List[str]:
        with cls._lock:
            return list(cls._sessions.keys())

# Global singleton manager
session_manager = SessionManager()
