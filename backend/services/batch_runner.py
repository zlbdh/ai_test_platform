# -*- coding: utf-8 -*-
"""
Batch runner: concurrent execution engine.
Runs multiple testing tasks concurrently with asyncio.
"""
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import csv
import uuid
import logging
import os

logger = logging.getLogger(__name__)


class BatchStatus(str, Enum):
    """Batch task status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    """Individual task status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TestCase:
    """Test case"""
    __test__ = False
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    instruction: str = ""
    url: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @property
    def duration(self) -> Optional[float]:
        """Execution duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


@dataclass
class BatchResult:
    """Batch execution result"""
    batch_id: str
    status: BatchStatus
    total: int
    success: int
    failed: int
    skipped: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    tasks: List[TestCase] = field(default_factory=list)
    
    @property
    def duration(self) -> Optional[float]:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.success / self.total * 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "status": self.status.value,
            "total": self.total,
            "success": self.success,
            "failed": self.failed,
            "skipped": self.skipped,
            "success_rate": f"{self.success_rate:.1f}%",
            "duration": f"{self.duration:.2f}s" if self.duration else None,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "tasks": [
                {
                    "id": t.id,
                    "name": t.name,
                    "status": t.status.value,
                    "duration": f"{t.duration:.2f}s" if t.duration else None,
                    "error": t.error
                }
                for t in self.tasks
            ]
        }


class BatchRunner:
    """Concurrent batch execution engine"""
    
    def __init__(self, max_concurrency: int = 3):
        """
        Initialize the batch runner.

        Args:
            max_concurrency: Maximum concurrency.
        """
        self.max_concurrency = max_concurrency
        self._running_batches: Dict[str, BatchResult] = {}
        self._cancelled: set = set()
    
    async def run_batch(
        self,
        test_cases: List[TestCase],
        executor: Callable[[TestCase], Any],
        on_progress: Optional[Callable[[TestCase, BatchResult], None]] = None
    ) -> BatchResult:
        """
        Run test cases in a batch.

        Args:
            test_cases: List of test cases.
            executor: Execution function accepting a TestCase and returning a result.
            on_progress: Progress callback.

        Returns:
            BatchResult containing batch execution results.
        """
        batch_id = str(uuid.uuid4())[:8]
        
        batch_result = BatchResult(
            batch_id=batch_id,
            status=BatchStatus.RUNNING,
            total=len(test_cases),
            success=0,
            failed=0,
            skipped=0,
            started_at=datetime.now(),
            tasks=test_cases
        )
        
        self._running_batches[batch_id] = batch_result
        
        # Limit concurrency with a semaphore
        semaphore = asyncio.Semaphore(self.max_concurrency)
        
        async def run_single(test_case: TestCase):
            if batch_id in self._cancelled:
                test_case.status = TaskStatus.SKIPPED
                batch_result.skipped += 1
                return
            
            async with semaphore:
                test_case.status = TaskStatus.RUNNING
                test_case.started_at = datetime.now()
                
                try:
                    # Run the test
                    if asyncio.iscoroutinefunction(executor):
                        result = await executor(test_case)
                    else:
                        result = await asyncio.to_thread(executor, test_case)
                    
                    test_case.result = result
                    test_case.status = TaskStatus.SUCCESS
                    batch_result.success += 1
                    
                except Exception as e:
                    logger.error(f"Task {test_case.id} failed: {e}")
                    test_case.status = TaskStatus.FAILED
                    test_case.error = str(e)
                    batch_result.failed += 1
                
                finally:
                    test_case.completed_at = datetime.now()
                    
                    # Invoke the progress callback
                    if on_progress:
                        try:
                            on_progress(test_case, batch_result)
                        except Exception as e:
                            logger.warning(f"Progress callback error: {e}")
        
        # Run all tasks concurrently
        await asyncio.gather(*[run_single(tc) for tc in test_cases])
        
        # Update batch status
        batch_result.completed_at = datetime.now()
        if batch_id in self._cancelled:
            batch_result.status = BatchStatus.CANCELLED
        elif batch_result.failed > 0:
            batch_result.status = BatchStatus.FAILED
        else:
            batch_result.status = BatchStatus.COMPLETED
        
        # Clean up
        del self._running_batches[batch_id]
        self._cancelled.discard(batch_id)
        
        logger.info(f"Batch {batch_id} completed: {batch_result.success}/{batch_result.total} success")
        
        return batch_result
    
    def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a batch task"""
        if batch_id in self._running_batches:
            self._cancelled.add(batch_id)
            return True
        return False
    
    def get_batch_status(self, batch_id: str) -> Optional[BatchResult]:
        """Get batch task status"""
        return self._running_batches.get(batch_id)
    
    @staticmethod
    def load_from_csv(
        csv_path: str,
        instruction_template: str,
        url_field: str = "url"
    ) -> List[TestCase]:
        """
        Load test cases from CSV.

        Args:
            csv_path: CSV file path.
            instruction_template: Instruction template with {field_name} placeholders.
            url_field: URL field name.

        Returns:
            List of test cases.
        """
        test_cases = []
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                # Replace template placeholders
                instruction = instruction_template
                for key, value in row.items():
                    instruction = instruction.replace(f"{{{key}}}", str(value))
                
                test_case = TestCase(
                    id=f"csv_{i+1}",
                    name=row.get("name", f"Test Case {i+1}"),
                    instruction=instruction,
                    url=row.get(url_field, ""),
                    data=dict(row)
                )
                test_cases.append(test_case)
        
        logger.info(f"Loaded {len(test_cases)} test cases from {csv_path}")
        return test_cases
    
    @staticmethod
    def create_from_data_factory(
        template: Dict[str, Any],
        instruction_template: str,
        count: int = 10,
        base_url: str = ""
    ) -> List[TestCase]:
        """
        Generate test cases with the data factory.

        Args:
            template: Data template.
            instruction_template: Instruction template.
            count: Number to generate.
            base_url: Base URL.

        Returns:
            List of test cases.
        """
        from core.data_factory import get_data_factory
        
        factory = get_data_factory()
        test_cases = []
        
        for i in range(count):
            data = factory.generate(template)
            
            # Replace template placeholders
            instruction = instruction_template
            for key, value in data.items():
                instruction = instruction.replace(f"{{{key}}}", str(value))
            
            test_case = TestCase(
                id=f"gen_{i+1}",
                name=f"Generated Test {i+1}",
                instruction=instruction,
                url=base_url,
                data=data
            )
            test_cases.append(test_case)
        
        logger.info(f"Generated {count} test cases from data factory")
        return test_cases


# Global singleton
_runner: Optional[BatchRunner] = None


def get_batch_runner(max_concurrency: int = 3) -> BatchRunner:
    """Get the batch runner singleton"""
    global _runner
    if _runner is None:
        _runner = BatchRunner(max_concurrency)
    return _runner
