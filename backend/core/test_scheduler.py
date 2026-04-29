"""
Test Scheduler - 测试调度器

支持：
- 定时执行测试
- 测试队列管理
- 并发控制
- 结果通知
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import asyncio
import logging
import uuid


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ScheduledTask:
    """调度任务"""
    task_id: str
    name: str
    test_config: Dict[str, Any]
    priority: TaskPriority
    status: TaskStatus
    created_at: str
    scheduled_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class TestScheduler:
    """测试调度器"""
    
    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self.queue: List[ScheduledTask] = []
        self.running: Dict[str, ScheduledTask] = {}
        self.completed: List[ScheduledTask] = []
        self.callbacks: List[Callable] = []
        self._running = False
        self._cron_jobs: List[Dict[str, Any]] = []
        self._cron_task: Optional[asyncio.Task] = None

    def schedule_cron(
        self,
        name: str,
        test_config: Dict[str, Any],
        interval_seconds: int = 3600,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> str:
        """
        注册定时调度任务（cron 触发器）。
        
        Args:
            name: 任务名称
            test_config: 测试配置
            interval_seconds: 执行间隔（秒），默认 1 小时
            priority: 优先级
            
        Returns:
            cron job ID
        """
        job_id = str(uuid.uuid4())[:8]
        self._cron_jobs.append({
            "job_id": job_id,
            "name": name,
            "test_config": test_config,
            "interval_seconds": interval_seconds,
            "priority": priority,
            "last_run": None,
            "enabled": True,
        })
        logging.getLogger(__name__).info(
            f"[Scheduler] 定时任务注册: {name} (每 {interval_seconds}s)"
        )
        return job_id

    def cancel_cron(self, job_id: str) -> bool:
        """取消定时任务"""
        for job in self._cron_jobs:
            if job["job_id"] == job_id:
                job["enabled"] = False
                return True
        return False

    def get_cron_jobs(self) -> List[Dict[str, Any]]:
        """获取所有定时任务"""
        return [
            {
                "job_id": j["job_id"],
                "name": j["name"],
                "interval_seconds": j["interval_seconds"],
                "last_run": j["last_run"],
                "enabled": j["enabled"],
            }
            for j in self._cron_jobs
        ]

    async def _cron_loop(self):
        """定时任务轮询循环"""
        while self._running:
            now = datetime.now()
            for job in self._cron_jobs:
                if not job["enabled"]:
                    continue
                last = job["last_run"]
                if last is None or (now - last).total_seconds() >= job["interval_seconds"]:
                    job["last_run"] = now
                    self.schedule(
                        name=f"[Cron] {job['name']}",
                        test_config=job["test_config"],
                        priority=job["priority"],
                    )
            await asyncio.sleep(10)  # 每 10 秒检查一次
    
    def schedule(
        self,
        name: str,
        test_config: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        scheduled_at: Optional[str] = None
    ) -> ScheduledTask:
        """调度测试任务"""
        task = ScheduledTask(
            task_id=str(uuid.uuid4())[:8],
            name=name,
            test_config=test_config,
            priority=priority,
            status=TaskStatus.PENDING,
            created_at=datetime.now().isoformat(),
            scheduled_at=scheduled_at,
            started_at=None,
            completed_at=None
        )
        
        # 按优先级插入队列
        inserted = False
        for i, existing in enumerate(self.queue):
            if task.priority.value > existing.priority.value:
                self.queue.insert(i, task)
                inserted = True
                break
        
        if not inserted:
            self.queue.append(task)
        
        return task
    
    def cancel(self, task_id: str) -> bool:
        """取消任务"""
        for task in self.queue:
            if task.task_id == task_id:
                task.status = TaskStatus.CANCELLED
                self.queue.remove(task)
                self.completed.append(task)
                return True
        return False
    
    def get_status(self, task_id: str) -> Optional[ScheduledTask]:
        """获取任务状态"""
        for task in self.queue:
            if task.task_id == task_id:
                return task
        
        if task_id in self.running:
            return self.running[task_id]
        
        for task in self.completed:
            if task.task_id == task_id:
                return task
        
        return None
    
    async def start(self, executor: Callable):
        """启动调度器（含定时任务循环）"""
        self._running = True

        # 启动 cron 定时任务循环
        if self._cron_jobs:
            self._cron_task = asyncio.create_task(self._cron_loop())
        
        while self._running:
            # 检查是否可以启动新任务
            while len(self.running) < self.max_concurrent and self.queue:
                task = self._get_next_task()
                if task:
                    asyncio.create_task(self._run_task(task, executor))
            
            await asyncio.sleep(1)
    
    def stop(self):
        """停止调度器"""
        self._running = False
    
    def _get_next_task(self) -> Optional[ScheduledTask]:
        """获取下一个任务"""
        now = datetime.now().isoformat()
        
        for task in self.queue:
            if task.scheduled_at and task.scheduled_at > now:
                continue
            
            self.queue.remove(task)
            return task
        
        return None
    
    async def _run_task(self, task: ScheduledTask, executor: Callable):
        """执行任务"""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now().isoformat()
        self.running[task.task_id] = task
        
        try:
            result = await executor(task.test_config)
            task.status = TaskStatus.COMPLETED
            task.result = result
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
        finally:
            task.completed_at = datetime.now().isoformat()
            del self.running[task.task_id]
            self.completed.append(task)
            
            # 触发回调
            for callback in self.callbacks:
                try:
                    callback(task)
                except Exception as e:
                    logger.warning(f"Scheduler callback failed: {e}")
    
    def on_complete(self, callback: Callable):
        """注册完成回调"""
        self.callbacks.append(callback)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "queue_length": len(self.queue),
            "running": len(self.running),
            "completed": len(self.completed),
            "success": sum(1 for t in self.completed if t.status == TaskStatus.COMPLETED),
            "failed": sum(1 for t in self.completed if t.status == TaskStatus.FAILED),
            "cancelled": sum(1 for t in self.completed if t.status == TaskStatus.CANCELLED)
        }
    
    def get_queue(self) -> List[Dict[str, Any]]:
        """获取队列状态"""
        return [
            {
                "task_id": t.task_id,
                "name": t.name,
                "priority": t.priority.value,
                "status": t.status.value,
                "scheduled_at": t.scheduled_at
            }
            for t in self.queue
        ]
    
    def get_running(self) -> List[Dict[str, Any]]:
        """获取运行中任务"""
        return [
            {
                "task_id": t.task_id,
                "name": t.name,
                "started_at": t.started_at
            }
            for t in self.running.values()
        ]

    def register_swarm_crons(self, target_url: str = "") -> List[str]:
        """
        注册军团定时巡检任务。

        - 晨检：每天 9:00（间隔 24h = 86400s）
        - 日报：每天 18:00（间隔 24h = 86400s）

        Returns:
            注册的 cron job ID 列表
        """
        job_ids = []

        # 晨检 — 全面回归
        job_ids.append(self.schedule_cron(
            name="🌅 军团晨检",
            test_config={
                "swarm_mode": True,
                "user_input": "全面回归测试：检查所有核心功能",
                "target_url": target_url,
                "notify_level": "info",
            },
            interval_seconds=86400,  # 24 小时
            priority=TaskPriority.HIGH,
        ))

        # 日报 — 覆盖盲区扫描
        job_ids.append(self.schedule_cron(
            name="📊 军团日报",
            test_config={
                "swarm_mode": True,
                "user_input": "查覆盖盲区，生成日报",
                "target_url": target_url,
                "mode": "coverage",
                "notify_level": "report",
            },
            interval_seconds=86400,
            priority=TaskPriority.NORMAL,
        ))

        logging.getLogger(__name__).info(
            f"[Scheduler] 军团巡检注册完成: {len(job_ids)} 个 cron job"
        )
        return job_ids


# 单例
_scheduler: Optional[TestScheduler] = None

def get_scheduler() -> TestScheduler:
    """获取调度器单例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = TestScheduler()
    return _scheduler
