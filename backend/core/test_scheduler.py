"""
Test Scheduler

Supports:
- Scheduled test execution
- Test queue management
- Concurrency control
- Result notifications
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
    """Scheduled task"""
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
    """Test scheduler"""

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
        Register a scheduled task with a cron trigger.

        Args:
            name: Task name
            test_config: Test configuration
            interval_seconds: Execution interval in seconds; defaults to one hour
            priority: Priority

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
            f"[Scheduler] Registered scheduled task: {name} (every {interval_seconds}s)"
        )
        return job_id

    def cancel_cron(self, job_id: str) -> bool:
        """Cancel a scheduled task"""
        for job in self._cron_jobs:
            if job["job_id"] == job_id:
                job["enabled"] = False
                return True
        return False

    def get_cron_jobs(self) -> List[Dict[str, Any]]:
        """Get all scheduled tasks"""
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
        """Scheduled-task polling loop"""
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
            await asyncio.sleep(10)  # Check every 10 seconds

    def schedule(
        self,
        name: str,
        test_config: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        scheduled_at: Optional[str] = None
    ) -> ScheduledTask:
        """Schedule a test task"""
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

        # Insert into the queue by priority
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
        """Cancel a task"""
        for task in self.queue:
            if task.task_id == task_id:
                task.status = TaskStatus.CANCELLED
                self.queue.remove(task)
                self.completed.append(task)
                return True
        return False

    def get_status(self, task_id: str) -> Optional[ScheduledTask]:
        """Get task status"""
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
        """Start the scheduler and scheduled-task loop"""
        self._running = True

        # Start the cron task loop
        if self._cron_jobs:
            self._cron_task = asyncio.create_task(self._cron_loop())

        while self._running:
            # Check whether a new task can start
            while len(self.running) < self.max_concurrent and self.queue:
                task = self._get_next_task()
                if task:
                    asyncio.create_task(self._run_task(task, executor))

            await asyncio.sleep(1)

    def stop(self):
        """Stop the scheduler"""
        self._running = False

    def _get_next_task(self) -> Optional[ScheduledTask]:
        """Get the next task"""
        now = datetime.now().isoformat()

        for task in self.queue:
            if task.scheduled_at and task.scheduled_at > now:
                continue

            self.queue.remove(task)
            return task

        return None

    async def _run_task(self, task: ScheduledTask, executor: Callable):
        """Execute a task"""
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

            # Trigger callbacks
            for callback in self.callbacks:
                try:
                    callback(task)
                except Exception as e:
                    logger.warning(f"Scheduler callback failed: {e}")

    def on_complete(self, callback: Callable):
        """Register a completion callback"""
        self.callbacks.append(callback)

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics"""
        return {
            "queue_length": len(self.queue),
            "running": len(self.running),
            "completed": len(self.completed),
            "success": sum(1 for t in self.completed if t.status == TaskStatus.COMPLETED),
            "failed": sum(1 for t in self.completed if t.status == TaskStatus.FAILED),
            "cancelled": sum(1 for t in self.completed if t.status == TaskStatus.CANCELLED)
        }

    def get_queue(self) -> List[Dict[str, Any]]:
        """Get queue status"""
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
        """Get running tasks"""
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
        Register scheduled legion health checks.

        - Morning check: daily at 9:00 (24h interval = 86400s)
        - Daily report: daily at 18:00 (24h interval = 86400s)

        Returns:
            List of registered cron job IDs
        """
        job_ids = []

        # Morning check: comprehensive regression
        job_ids.append(self.schedule_cron(
            name="🌅 Legion morning check",
            test_config={
                "swarm_mode": True,
                "user_input": "Comprehensive regression test: check all core features",
                "target_url": target_url,
                "notify_level": "info",
            },
            interval_seconds=86400,  # 24 hours
            priority=TaskPriority.HIGH,
        ))

        # Daily report: coverage-gap scan
        job_ids.append(self.schedule_cron(
            name="📊 Legion daily report",
            test_config={
                "swarm_mode": True,
                "user_input": "Find coverage gaps and generate a daily report",
                "target_url": target_url,
                "mode": "coverage",
                "notify_level": "report",
            },
            interval_seconds=86400,
            priority=TaskPriority.NORMAL,
        ))

        logging.getLogger(__name__).info(
            f"[Scheduler] Registered legion health checks: {len(job_ids)} cron jobs"
        )
        return job_ids


# Singleton
_scheduler: Optional[TestScheduler] = None

def get_scheduler() -> TestScheduler:
    """Get the scheduler singleton"""
    global _scheduler
    if _scheduler is None:
        _scheduler = TestScheduler()
    return _scheduler
