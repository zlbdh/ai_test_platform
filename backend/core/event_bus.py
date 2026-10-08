"""
HybridEventBus — thread-safe and async-safe message bus (Phase 5 revision).

Design:
- task_queue / result_queue: Use thread-safe queue.Queue because Executor runs in a separate thread
- log_queue: Use thread-safe queue.Queue; SSE reads from the main thread
- The asynchronous Planner safely waits on queues through asyncio.to_thread
"""
import asyncio
import queue
from core.protocol import SENTINEL


class EventBus:
    """
    Hybrid event bus:
    - Uses thread-safe queue.Queue to support an Executor in another thread
    - Provides async wrappers for Planner calls in the asyncio event loop
    - Also provides synchronous methods for direct Executor-thread calls
    """

    def __init__(self, session_id: str = "default_session"):
        from core.session_manager import session_manager
        self.session_id = session_id
        self.session = session_manager.get_session(session_id)
        self.task_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.log_queue = queue.Queue()

    # === Synchronous methods called directly by the Executor thread ===

    def publish_task_sync(self, task):
        self.task_queue.put(task)

    def get_task_sync(self, timeout=None):
        try:
            return self.task_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def publish_result_sync(self, result):
        self.result_queue.put(result)

    def get_result_sync(self, timeout=None):
        try:
            return self.result_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def publish_log_sync(self, log):
        self.log_queue.put(log)
        self.session.append_log(log)  # Store synchronously in the isolated session log

    def get_log_sync(self, timeout=None):
        try:
            return self.log_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def shutdown_sync(self):
        self.task_queue.put(SENTINEL)

    # === Async wrappers called by Planner in the asyncio event loop ===

    async def publish_task(self, task):
        await asyncio.to_thread(self.task_queue.put, task)

    async def get_task(self, timeout=None):
        return await asyncio.to_thread(self.get_task_sync, timeout)

    async def publish_result(self, result):
        await asyncio.to_thread(self.result_queue.put, result)

    async def get_result(self, timeout=None):
        return await asyncio.to_thread(self.get_result_sync, timeout)

    async def publish_log(self, log):
        await asyncio.to_thread(self.publish_log_sync, log)

    async def get_log(self, timeout=None):
        return await asyncio.to_thread(self.get_log_sync, timeout)

    async def shutdown(self):
        await asyncio.to_thread(self.task_queue.put, SENTINEL)
