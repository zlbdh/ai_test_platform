"""
HybridEventBus — 跨线程异步安全的消息总线（Phase 5 修正版）。

设计：
- task_queue / result_queue: 使用 queue.Queue（线程安全），因为 Executor 在独立线程
- log_queue: 使用 queue.Queue（线程安全），SSE 从主线程读取
- Planner（async）通过 asyncio.to_thread 安全地等待 queue
"""
import asyncio
import queue
from core.protocol import SENTINEL


class EventBus:
    """
    混合事件总线：
    - 底层使用 queue.Queue（线程安全，支持跨线程 Executor）
    - 提供 async 包装方法（供 Planner 在 asyncio 事件循环中调用）
    - 也提供 sync 方法（供 Executor 线程直接调用）
    """
    
    def __init__(self, session_id: str = "default_session"):
        from core.session_manager import session_manager
        self.session_id = session_id
        self.session = session_manager.get_session(session_id)
        self.task_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.log_queue = queue.Queue()
    
    # === Sync 方法（Executor 线程直接调用） ===
    
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
        self.session.append_log(log)  # 同步存入隔离会话日志
    
    def get_log_sync(self, timeout=None):
        try:
            return self.log_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def shutdown_sync(self):
        self.task_queue.put(SENTINEL)
    
    # === Async 包装（Planner 在 asyncio 事件循环中调用） ===
    
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
