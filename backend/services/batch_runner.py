# -*- coding: utf-8 -*-
"""
Batch Runner - 批量并发执行引擎
基于 asyncio 实现多任务并发测试
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
    """批量任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    """单个任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TestCase:
    """测试用例"""
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
        """执行时长（秒）"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


@dataclass
class BatchResult:
    """批量执行结果"""
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
    """批量并发执行引擎"""
    
    def __init__(self, max_concurrency: int = 3):
        """
        初始化批量执行器
        
        Args:
            max_concurrency: 最大并发数
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
        批量运行测试用例
        
        Args:
            test_cases: 测试用例列表
            executor: 执行函数，接收 TestCase 返回结果
            on_progress: 进度回调函数
        
        Returns:
            BatchResult 批量执行结果
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
        
        # 使用信号量限制并发
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
                    # 执行测试
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
                    
                    # 触发进度回调
                    if on_progress:
                        try:
                            on_progress(test_case, batch_result)
                        except Exception as e:
                            logger.warning(f"Progress callback error: {e}")
        
        # 并发执行所有任务
        await asyncio.gather(*[run_single(tc) for tc in test_cases])
        
        # 更新批量状态
        batch_result.completed_at = datetime.now()
        if batch_id in self._cancelled:
            batch_result.status = BatchStatus.CANCELLED
        elif batch_result.failed > 0:
            batch_result.status = BatchStatus.FAILED
        else:
            batch_result.status = BatchStatus.COMPLETED
        
        # 清理
        del self._running_batches[batch_id]
        self._cancelled.discard(batch_id)
        
        logger.info(f"Batch {batch_id} completed: {batch_result.success}/{batch_result.total} success")
        
        return batch_result
    
    def cancel_batch(self, batch_id: str) -> bool:
        """取消批量任务"""
        if batch_id in self._running_batches:
            self._cancelled.add(batch_id)
            return True
        return False
    
    def get_batch_status(self, batch_id: str) -> Optional[BatchResult]:
        """获取批量任务状态"""
        return self._running_batches.get(batch_id)
    
    @staticmethod
    def load_from_csv(
        csv_path: str,
        instruction_template: str,
        url_field: str = "url"
    ) -> List[TestCase]:
        """
        从 CSV 加载测试用例
        
        Args:
            csv_path: CSV 文件路径
            instruction_template: 指令模板，使用 {field_name} 占位符
            url_field: URL 字段名
        
        Returns:
            测试用例列表
        """
        test_cases = []
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                # 替换模板占位符
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
        使用数据工厂生成测试用例
        
        Args:
            template: 数据模板
            instruction_template: 指令模板
            count: 生成数量
            base_url: 基础 URL
        
        Returns:
            测试用例列表
        """
        from core.data_factory import get_data_factory
        
        factory = get_data_factory()
        test_cases = []
        
        for i in range(count):
            data = factory.generate(template)
            
            # 替换模板占位符
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


# 全局单例
_runner: Optional[BatchRunner] = None


def get_batch_runner(max_concurrency: int = 3) -> BatchRunner:
    """获取批量执行器单例"""
    global _runner
    if _runner is None:
        _runner = BatchRunner(max_concurrency)
    return _runner
