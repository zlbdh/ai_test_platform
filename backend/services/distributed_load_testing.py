"""
Distributed Load Testing - 分布式压测服务

支持：
- Locust 集成
- 多节点分布式执行
- 实时指标收集
- 报告聚合
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import asyncio
import json
import time
import subprocess
import shutil
import os


class LoadTestStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    COMPLETED = "completed"


@dataclass
class LoadTestConfig:
    """压测配置"""
    target_url: str
    users: int
    spawn_rate: float
    duration_seconds: int
    locustfile: Optional[str] = None


@dataclass
class LoadTestMetrics:
    """压测指标"""
    total_requests: int
    failures: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    rps: float
    percentile_50: float
    percentile_95: float
    percentile_99: float


@dataclass
class WorkerNode:
    """工作节点"""
    node_id: str
    host: str
    port: int
    status: str


class DistributedLoadTester:
    """分布式压测器"""
    
    def __init__(self):
        self.status = LoadTestStatus.IDLE
        self.current_config: Optional[LoadTestConfig] = None
        self.workers: List[WorkerNode] = []
        self.metrics_history: List[LoadTestMetrics] = []
        self._process: Optional[subprocess.Popen] = None
        self._locust_available = shutil.which("locust") is not None
    
    def generate_locustfile(self, config: LoadTestConfig) -> str:
        """生成 Locust 测试文件"""
        content = f'''
from locust import HttpUser, task, between

class LoadTestUser(HttpUser):
    wait_time = between(1, 3)
    host = "{config.target_url}"
    
    @task(3)
    def get_homepage(self):
        self.client.get("/")
    
    @task(1)
    def get_api_health(self):
        self.client.get("/api/health")
    
    @task(2)
    def get_api_status(self):
        self.client.get("/api/status")
'''
        
        filepath = f"./data/locustfile_{int(time.time())}.py"
        os.makedirs("./data", exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(content)
        
        return filepath
    
    async def start_test(
        self,
        config: LoadTestConfig,
        distributed: bool = False,
        worker_count: int = 1
    ) -> Dict[str, Any]:
        """启动压测"""
        if not self._locust_available:
            # 回退到内置简单压测
            return await self._run_simple_load_test(config)
        
        self.current_config = config
        self.status = LoadTestStatus.RUNNING
        
        locustfile = config.locustfile or self.generate_locustfile(config)
        
        cmd = [
            "locust",
            "-f", locustfile,
            "--host", config.target_url,
            "-u", str(config.users),
            "-r", str(config.spawn_rate),
            "--run-time", f"{config.duration_seconds}s",
            "--headless",
            "--only-summary",
            "--csv", f"./data/loadtest_{int(time.time())}"
        ]
        
        if distributed and worker_count > 1:
            # Master 模式
            cmd.extend(["--master", f"--expect-workers={worker_count}"])
        
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 等待完成
            stdout, stderr = self._process.communicate(timeout=config.duration_seconds + 30)
            
            self.status = LoadTestStatus.COMPLETED
            
            return {
                "status": "completed",
                "output": stdout,
                "errors": stderr if stderr else None
            }
        
        except subprocess.TimeoutExpired:
            self._process.kill()
            self.status = LoadTestStatus.STOPPED
            return {"status": "timeout", "message": "Test timed out"}
        
        except Exception as e:
            self.status = LoadTestStatus.STOPPED
            return {"status": "error", "message": str(e)}
    
    async def _run_simple_load_test(self, config: LoadTestConfig) -> Dict[str, Any]:
        """内置简单压测（无需 Locust）"""
        import aiohttp
        
        start_time = time.time()
        results = {
            "total_requests": 0,
            "successful": 0,
            "failed": 0,
            "response_times": []
        }
        
        async def make_request(session, url):
            req_start = time.time()
            try:
                async with session.get(url, ssl=False, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    await resp.text()
                    results["successful"] += 1
                    results["response_times"].append((time.time() - req_start) * 1000)
            except Exception:
                results["failed"] += 1
            results["total_requests"] += 1
        
        async with aiohttp.ClientSession() as session:
            end_time = start_time + config.duration_seconds
            tasks = []
            
            while time.time() < end_time:
                # 控制并发
                while len(tasks) < config.users:
                    task = asyncio.create_task(make_request(session, config.target_url))
                    tasks.append(task)
                
                # 等待一批完成
                if tasks:
                    done, tasks = await asyncio.wait(tasks, timeout=1)
                    tasks = list(tasks)
                
                await asyncio.sleep(1 / config.spawn_rate)
        
        # 计算指标
        response_times = sorted(results["response_times"]) if results["response_times"] else [0]
        total_time = time.time() - start_time
        
        metrics = LoadTestMetrics(
            total_requests=results["total_requests"],
            failures=results["failed"],
            avg_response_time=sum(response_times) / len(response_times) if response_times else 0,
            min_response_time=min(response_times) if response_times else 0,
            max_response_time=max(response_times) if response_times else 0,
            rps=results["total_requests"] / total_time if total_time > 0 else 0,
            percentile_50=response_times[len(response_times) // 2] if response_times else 0,
            percentile_95=response_times[int(len(response_times) * 0.95)] if response_times else 0,
            percentile_99=response_times[int(len(response_times) * 0.99)] if response_times else 0
        )
        
        self.metrics_history.append(metrics)
        self.status = LoadTestStatus.COMPLETED
        
        return {
            "status": "completed",
            "metrics": {
                "total_requests": metrics.total_requests,
                "failures": metrics.failures,
                "success_rate": (metrics.total_requests - metrics.failures) / metrics.total_requests * 100 if metrics.total_requests > 0 else 0,
                "avg_response_time_ms": round(metrics.avg_response_time, 2),
                "min_response_time_ms": round(metrics.min_response_time, 2),
                "max_response_time_ms": round(metrics.max_response_time, 2),
                "rps": round(metrics.rps, 2),
                "p50_ms": round(metrics.percentile_50, 2),
                "p95_ms": round(metrics.percentile_95, 2),
                "p99_ms": round(metrics.percentile_99, 2)
            },
            "duration_seconds": round(total_time, 2),
            "locust_available": self._locust_available
        }
    
    def stop_test(self):
        """停止压测"""
        if self._process:
            self._process.terminate()
        self.status = LoadTestStatus.STOPPED
    
    def add_worker(self, host: str, port: int = 5557) -> WorkerNode:
        """添加工作节点"""
        worker = WorkerNode(
            node_id=f"worker-{len(self.workers)+1}",
            host=host,
            port=port,
            status="ready"
        )
        self.workers.append(worker)
        return worker
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "status": self.status.value,
            "config": {
                "target_url": self.current_config.target_url,
                "users": self.current_config.users,
                "duration": self.current_config.duration_seconds
            } if self.current_config else None,
            "workers": [
                {"id": w.node_id, "host": w.host, "status": w.status}
                for w in self.workers
            ],
            "locust_available": self._locust_available
        }


# 单例
_load_tester: Optional[DistributedLoadTester] = None

def get_load_tester() -> DistributedLoadTester:
    """获取压测器"""
    global _load_tester
    if _load_tester is None:
        _load_tester = DistributedLoadTester()
    return _load_tester
