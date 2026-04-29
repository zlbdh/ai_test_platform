# -*- coding: utf-8 -*-
"""
单元测试: EventBus 线程安全通信
测试 sync/async 方法的正确性和线程安全性
"""
import asyncio
import threading
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from core.event_bus import EventBus
from core.protocol import SENTINEL


class TestEventBusSync:
    """测试 EventBus 同步方法"""

    def test_publish_and_get_task(self):
        bus = EventBus()
        bus.publish_task_sync({"action": "click", "selector": "#btn"})
        task = bus.get_task_sync(timeout=1)
        assert task is not None
        assert task["action"] == "click"

    def test_publish_and_get_log(self):
        bus = EventBus()
        bus.publish_log_sync({"type": "info", "content": "test log"})
        log = bus.get_log_sync(timeout=1)
        assert log is not None
        assert log["content"] == "test log"

    def test_get_task_timeout(self):
        bus = EventBus()
        task = bus.get_task_sync(timeout=0.1)
        assert task is None

    def test_get_log_timeout(self):
        bus = EventBus()
        log = bus.get_log_sync(timeout=0.1)
        assert log is None

    def test_sentinel_detection(self):
        bus = EventBus()
        bus.task_queue.put(SENTINEL)
        item = bus.get_task_sync(timeout=1)
        assert item is SENTINEL

    def test_multiple_logs(self):
        bus = EventBus()
        for i in range(5):
            bus.publish_log_sync({"type": "info", "content": f"log {i}"})
        
        logs = []
        for _ in range(5):
            log = bus.get_log_sync(timeout=1)
            if log:
                logs.append(log)
        
        assert len(logs) == 5
        assert logs[0]["content"] == "log 0"
        assert logs[4]["content"] == "log 4"


class TestEventBusAsync:
    """测试 EventBus 异步方法"""

    @pytest.mark.asyncio
    async def test_async_publish_and_get_task(self):
        bus = EventBus()
        await bus.publish_task({"action": "navigate"})
        task = await bus.get_task(timeout=1)
        assert task is not None
        assert task["action"] == "navigate"

    @pytest.mark.asyncio
    async def test_async_publish_and_get_log(self):
        bus = EventBus()
        await bus.publish_log({"type": "info", "content": "async log"})
        log = await bus.get_log(timeout=1)
        assert log is not None
        assert log["content"] == "async log"


class TestEventBusCrossThread:
    """测试跨线程通信"""

    def test_sync_publish_async_consume(self):
        bus = EventBus()
        
        def producer():
            for i in range(3):
                bus.publish_log_sync({"content": f"thread msg {i}"})
        
        t = threading.Thread(target=producer)
        t.start()
        t.join()
        
        logs = []
        while not bus.log_queue.empty():
            log = bus.get_log_sync(timeout=0.1)
            if log:
                logs.append(log)
        
        assert len(logs) == 3
        assert logs[0]["content"] == "thread msg 0"

    def test_concurrent_producers(self):
        bus = EventBus()
        num_threads = 5
        msgs_per_thread = 10
        
        def producer(thread_id):
            for i in range(msgs_per_thread):
                bus.publish_log_sync({"thread": thread_id, "idx": i})
        
        threads = [threading.Thread(target=producer, args=(tid,)) for tid in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        count = 0
        while not bus.log_queue.empty():
            bus.get_log_sync(timeout=0.1)
            count += 1
        
        assert count == num_threads * msgs_per_thread


class TestEventBusNoDuplicateLog:
    """测试 publish_log 不重复存储到 SharedBrowserState"""

    def setup_method(self):
        from core.shared import SharedBrowserState
        SharedBrowserState.clear_logs()

    @pytest.mark.asyncio
    async def test_async_publish_log_no_duplicate(self):
        """async publish_log 应只在 SharedBrowserState 中存一次"""
        from core.shared import SharedBrowserState
        bus = EventBus()
        await bus.publish_log({"type": "info", "content": "async test"})

        logs = SharedBrowserState.get_logs()
        # 修复前会是 2 (queue.put + append_log 各一次)，修复后应为 1
        matching = [l for l in logs if l.get("content") == "async test"]
        assert len(matching) == 1, f"Expected 1 log entry, got {len(matching)}"
