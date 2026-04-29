# -*- coding: utf-8 -*-
"""
性能测试服务 - 基于 Locust 的压力测试模块
提供 API 接口进行性能测试配置和执行
"""
import os
import json
import asyncio
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from urllib.parse import urljoin

from services.execution_center_service import get_execution_center_service


class LoadTestStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class LoadTestConfig:
    """负载测试配置"""
    target_url: str
    users: int = 10
    spawn_rate: int = 1
    duration: int = 60  # 秒
    endpoints: List[Dict[str, Any]] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=dict)
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


@dataclass
class LoadTestResult:
    """负载测试结果"""
    test_id: str
    status: LoadTestStatus
    config: LoadTestConfig
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    stats: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    @property
    def duration(self) -> Optional[float]:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None


class PerformanceRunner:
    """性能测试运行器"""

    def __init__(self, results_dir: str = "data/performance"):
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self._current_process: Optional[subprocess.Popen] = None
        self._current_result: Optional[LoadTestResult] = None
        self._status = LoadTestStatus.IDLE

    @property
    def status(self) -> LoadTestStatus:
        return self._status

    def generate_locustfile(self, config: LoadTestConfig) -> str:
        """生成 Locust 测试脚本"""
        endpoints_code = ""
        
        if config.endpoints:
            for i, ep in enumerate(config.endpoints):
                method = ep.get("method", "GET").upper()
                path = ep.get("path", "/")
                weight = ep.get("weight", 1)
                body = ep.get("body", None)
                
                if method == "GET":
                    endpoints_code += f'''
    @task({weight})
    def endpoint_{i}(self):
        self.client.get("{path}", headers=self.headers)
'''
                elif method == "POST":
                    body_str = json.dumps(body) if body else "{}"
                    endpoints_code += f'''
    @task({weight})
    def endpoint_{i}(self):
        self.client.post("{path}", json={body_str}, headers=self.headers)
'''
        else:
            # 默认测试根路径
            endpoints_code = '''
    @task
    def default_endpoint(self):
        self.client.get("/", headers=self.headers)
'''

        headers_str = json.dumps(config.headers) if config.headers else "{}"
        
        return f'''# Auto-generated Locust test file
from locust import HttpUser, task, between

class LoadTestUser(HttpUser):
    wait_time = between(0.5, 2)
    headers = {headers_str}
    
{endpoints_code}
'''

    async def run_test(self, config: LoadTestConfig) -> LoadTestResult:
        """运行负载测试"""
        import uuid
        
        test_id = str(uuid.uuid4())[:8]
        self._status = LoadTestStatus.RUNNING
        
        result = LoadTestResult(
            test_id=test_id,
            status=LoadTestStatus.RUNNING,
            config=config,
            started_at=datetime.now()
        )
        self._current_result = result
        
        # 生成 Locust 文件
        locustfile_content = self.generate_locustfile(config)
        locustfile_path = self.results_dir / f"locustfile_{test_id}.py"
        
        with open(locustfile_path, 'w', encoding='utf-8') as f:
            f.write(locustfile_content)
        
        # 结果文件路径
        stats_file = self.results_dir / f"stats_{test_id}.json"
        
        try:
            # 运行 Locust (headless mode)
            cmd = [
                "locust",
                "-f", str(locustfile_path),
                "--host", config.target_url,
                "--users", str(config.users),
                "--spawn-rate", str(config.spawn_rate),
                "--run-time", f"{config.duration}s",
                "--headless",
                "--json"
            ]
            
            # 在后台运行
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.results_dir)
            )
            self._current_process = process
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=config.duration + 30  # 额外超时
            )
            
            result.finished_at = datetime.now()
            
            # 解析输出
            if stdout:
                try:
                    output = stdout.decode('utf-8')
                    # Locust JSON 输出格式
                    if output.strip().startswith('['):
                        stats = json.loads(output)
                        result.stats = self._parse_locust_stats(stats)
                except json.JSONDecodeError:
                    result.stats = {"raw_output": stdout.decode('utf-8', errors='ignore')}
            
            if process.returncode == 0:
                # Locust 成功但如果 stats 为空，fallback 到简单测试
                if not result.stats or not result.stats.get('total_requests', 0):
                    try:
                        fallback_result = await self._run_simple_load_test(config, test_id)
                        result.stats = fallback_result.stats
                        result.finished_at = fallback_result.finished_at
                    except Exception:
                        pass
                result.status = LoadTestStatus.COMPLETED
                self._status = LoadTestStatus.COMPLETED
            else:
                stderr_output = stderr.decode('utf-8', errors='ignore')
                # Locust 在有请求失败时也返回非0，但如果有 stats 数据就不算失败
                if result.stats and result.stats.get('total_requests', 0) > 0:
                    result.status = LoadTestStatus.COMPLETED
                    self._status = LoadTestStatus.COMPLETED
                else:
                    # Locust 无有效数据，fallback 到简单测试
                    try:
                        fallback_result = await self._run_simple_load_test(config, test_id)
                        result.stats = fallback_result.stats
                        result.status = fallback_result.status
                        self._status = fallback_result.status
                        result.finished_at = fallback_result.finished_at
                    except Exception:
                        result.status = LoadTestStatus.FAILED
                        self._status = LoadTestStatus.FAILED
                    if stderr_output.strip():
                        result.errors.append(f"Locust fallback: {stderr_output[:200]}")
                
        except asyncio.TimeoutError:
            result.status = LoadTestStatus.FAILED
            result.errors.append("Test timed out")
            self._status = LoadTestStatus.FAILED
            if self._current_process:
                self._current_process.terminate()
                
        except FileNotFoundError:
            # Locust 未安装，使用模拟测试
            result = await self._run_simple_load_test(config, test_id)
            
        except Exception as e:
            result.status = LoadTestStatus.FAILED
            result.errors.append(str(e))
            self._status = LoadTestStatus.FAILED
            
        finally:
            self._current_process = None
            
            # 保存结果
            self._save_result(result)
            
        return result

    async def _run_simple_load_test(self, config: LoadTestConfig, test_id: str) -> LoadTestResult:
        """简单的负载测试（不依赖 Locust）"""
        import aiohttp
        
        result = LoadTestResult(
            test_id=test_id,
            status=LoadTestStatus.RUNNING,
            config=config,
            started_at=datetime.now()
        )
        
        stats = {
            "total_requests": 0,
            "transport_success": 0,
            "success": 0,
            "business_success": 0,
            "failures": 0,
            "http_2xx": 0,
            "http_3xx": 0,
            "http_4xx": 0,
            "http_5xx": 0,
            "response_times": [],
            "errors": []
        }
        
        async def make_request(session, endpoint: Optional[Dict[str, Any]] = None):
            endpoint = endpoint or {}
            method = str(endpoint.get("method", "GET")).upper()
            path = str(endpoint.get("path", "/") or "/")
            headers = dict(config.headers or {})
            headers.update(endpoint.get("headers") or {})
            payload = endpoint.get("body")
            url = urljoin(config.target_url.rstrip("/") + "/", path.lstrip("/"))
            try:
                start = datetime.now()
                request_kwargs: Dict[str, Any] = {
                    "headers": headers,
                    "timeout": aiohttp.ClientTimeout(total=10),
                }
                if method in ("POST", "PUT", "PATCH", "DELETE"):
                    request_kwargs["json"] = payload
                elif method == "GET" and isinstance(payload, dict):
                    request_kwargs["params"] = payload

                async with session.request(method, url, **request_kwargs) as resp:
                    await resp.text()
                    elapsed = (datetime.now() - start).total_seconds() * 1000
                    stats["total_requests"] += 1
                    stats["response_times"].append(elapsed)
                    stats["transport_success"] += 1
                    if 200 <= resp.status < 300:
                        stats["http_2xx"] += 1
                        stats["success"] += 1
                        stats["business_success"] += 1
                    elif 300 <= resp.status < 400:
                        stats["http_3xx"] += 1
                        stats["failures"] += 1
                        stats["errors"].append(f"{method} {path} -> HTTP {resp.status}")
                    elif 400 <= resp.status < 500:
                        stats["http_4xx"] += 1
                        stats["failures"] += 1
                        stats["errors"].append(f"{method} {path} -> HTTP {resp.status}")
                    else:
                        stats["http_5xx"] += 1
                        stats["failures"] += 1
                        stats["errors"].append(f"{method} {path} -> HTTP {resp.status}")
            except Exception as e:
                stats["total_requests"] += 1
                stats["failures"] += 1
                stats["errors"].append(str(e)[:100])
        
        async with aiohttp.ClientSession() as session:
            # 并发请求
            end_time = datetime.now().timestamp() + config.duration
            
            while datetime.now().timestamp() < end_time:
                tasks = []
                for _ in range(min(config.users, 10)):  # 限制并发
                    endpoint = config.endpoints[(stats["total_requests"] + len(tasks)) % len(config.endpoints)] if config.endpoints else None
                    tasks.append(make_request(session, endpoint))
                
                await asyncio.gather(*tasks)
                await asyncio.sleep(0.1)
        
        result.finished_at = datetime.now()
        
        # 计算统计
        response_times = stats["response_times"]
        if response_times:
            result.stats = {
                "total_requests": stats["total_requests"],
                "transport_success": stats["transport_success"],
                "success": stats["success"],
                "business_success": stats["business_success"],
                "failures": stats["failures"],
                "http_2xx": stats["http_2xx"],
                "http_3xx": stats["http_3xx"],
                "http_4xx": stats["http_4xx"],
                "http_5xx": stats["http_5xx"],
                "transport_success_rate": round(stats["transport_success"] / stats["total_requests"] * 100, 2),
                "business_success_rate": round(stats["success"] / stats["total_requests"] * 100, 2),
                "success_rate": round(stats["success"] / stats["total_requests"] * 100, 2),
                "avg_response_time": round(sum(response_times) / len(response_times), 2),
                "min_response_time": round(min(response_times), 2),
                "max_response_time": round(max(response_times), 2),
                "requests_per_second": round(stats["total_requests"] / config.duration, 2)
            }
        
        result.status = LoadTestStatus.COMPLETED
        self._status = LoadTestStatus.COMPLETED
        
        return result

    def _parse_locust_stats(self, stats: List[Dict]) -> Dict[str, Any]:
        """解析 Locust 统计数据"""
        aggregated = {}
        
        for entry in stats:
            if entry.get("name") == "Aggregated":
                aggregated = {
                    "total_requests": entry.get("num_requests", 0),
                    "failures": entry.get("num_failures", 0),
                    "transport_success": entry.get("num_requests", 0),
                    "business_success": max(entry.get("num_requests", 0) - entry.get("num_failures", 0), 0),
                    "business_success_rate": round((1 - entry.get("num_failures", 0) / max(entry.get("num_requests", 1), 1)) * 100, 2),
                    "success_rate": round((1 - entry.get("num_failures", 0) / max(entry.get("num_requests", 1), 1)) * 100, 2),
                    "avg_response_time": entry.get("avg_response_time", 0),
                    "min_response_time": entry.get("min_response_time", 0),
                    "max_response_time": entry.get("max_response_time", 0),
                    "requests_per_second": entry.get("current_rps", 0),
                    "percentile_50": entry.get("response_time_percentile_50", 0),
                    "percentile_95": entry.get("response_time_percentile_95", 0)
                }
                break
                
        return aggregated or {"entries": stats}

    def _save_result(self, result: LoadTestResult):
        """保存测试结果"""
        result_file = self.results_dir / f"result_{result.test_id}.json"
        
        data = {
            "test_id": result.test_id,
            "status": result.status.value,
            "started_at": result.started_at.isoformat() if result.started_at else None,
            "finished_at": result.finished_at.isoformat() if result.finished_at else None,
            "duration": result.duration,
            "config": asdict(result.config),
            "stats": result.stats,
            "errors": result.errors
        }
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        try:
            get_execution_center_service().record_performance_result(result)
        except Exception as exc:
            result.errors.append(f"execution center sync failed: {exc}")

    def stop_test(self):
        """停止当前测试"""
        if self._current_process:
            self._current_process.terminate()
            self._status = LoadTestStatus.STOPPED
            if self._current_result:
                self._current_result.status = LoadTestStatus.STOPPED
                self._current_result.finished_at = datetime.now()
                self._save_result(self._current_result)

    def get_history(self, limit: int = 10) -> List[Dict]:
        """获取测试历史"""
        results = []
        
        for f in sorted(self.results_dir.glob("result_*.json"), reverse=True)[:limit]:
            with open(f, 'r', encoding='utf-8') as file:
                results.append(json.load(file))
                
        return results

    def delete_history(self, test_id: str) -> bool:
        """删除单条测试历史"""
        result_file = self.results_dir / f"result_{test_id}.json"
        if result_file.exists():
            result_file.unlink()
            # 同时清理关联文件
            for pattern in [f"locustfile_{test_id}.py", f"stats_{test_id}.json"]:
                f = self.results_dir / pattern
                if f.exists():
                    f.unlink()
            return True
        return False

    def clear_history(self) -> int:
        """清空全部测试历史，返回删除数量"""
        count = 0
        for f in self.results_dir.glob("result_*.json"):
            f.unlink()
            count += 1
        # 清理关联文件
        for f in self.results_dir.glob("locustfile_*.py"):
            f.unlink()
        for f in self.results_dir.glob("stats_*.json"):
            f.unlink()
        return count


# 全局实例
_runner: Optional[PerformanceRunner] = None


def get_performance_runner() -> PerformanceRunner:
    """获取性能测试运行器单例"""
    global _runner
    if _runner is None:
        from core.config import Config
        results_dir = os.path.join(Config.PROJECT_ROOT, "data", "performance")
        _runner = PerformanceRunner(results_dir)
    return _runner
