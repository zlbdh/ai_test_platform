"""
gRPC Testing Service - gRPC 测试服务

支持 gRPC 服务的完整测试：
- Unary 调用
- 服务反射
- 断言验证
- 性能指标
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import json
import subprocess
import time
import asyncio
import shutil


@dataclass
class GrpcRequest:
    """gRPC 请求"""
    service: str
    method: str
    data: Dict[str, Any]
    metadata: Optional[Dict[str, str]] = None


@dataclass
class GrpcResponse:
    """gRPC 响应"""
    success: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    status_code: int
    response_time_ms: int


@dataclass
class GrpcAssertion:
    """gRPC 断言"""
    path: str
    operator: str  # eq, ne, contains, exists, type
    expected: Any


class GrpcTestService:
    """gRPC 测试服务"""
    
    def __init__(self, host: str, port: int = 50051, use_tls: bool = False):
        self.host = host
        self.port = port
        self.use_tls = use_tls
        self.address = f"{host}:{port}"
        self._grpcurl_available = self._check_grpcurl()
    
    def _check_grpcurl(self) -> bool:
        """检查 grpcurl 是否可用"""
        return shutil.which("grpcurl") is not None
    
    def _build_command(
        self,
        service: str,
        method: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, str]] = None
    ) -> List[str]:
        """构建 grpcurl 命令"""
        cmd = ["grpcurl"]
        
        # TLS 选项
        if not self.use_tls:
            cmd.append("-plaintext")
        
        # 元数据
        if metadata:
            for k, v in metadata.items():
                cmd.extend(["-H", f"{k}: {v}"])
        
        # 数据
        cmd.extend(["-d", json.dumps(data)])
        
        # 地址和方法
        cmd.append(self.address)
        cmd.append(f"{service}/{method}")
        
        return cmd
    
    async def call(self, request: GrpcRequest) -> GrpcResponse:
        """执行 gRPC 调用"""
        if not self._grpcurl_available:
            return GrpcResponse(
                success=False,
                data=None,
                error="grpcurl not installed. Install via: go install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest",
                status_code=-1,
                response_time_ms=0
            )
        
        cmd = self._build_command(
            request.service,
            request.method,
            request.data,
            request.metadata
        )
        
        start = time.time()
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30.0
            )
            
            elapsed = int((time.time() - start) * 1000)
            
            if process.returncode == 0:
                try:
                    data = json.loads(stdout.decode())
                except Exception:
                    data = {"raw": stdout.decode()}
                
                return GrpcResponse(
                    success=True,
                    data=data,
                    error=None,
                    status_code=0,
                    response_time_ms=elapsed
                )
            else:
                return GrpcResponse(
                    success=False,
                    data=None,
                    error=stderr.decode(),
                    status_code=process.returncode,
                    response_time_ms=elapsed
                )
        
        except asyncio.TimeoutError:
            return GrpcResponse(
                success=False,
                data=None,
                error="Request timeout",
                status_code=-1,
                response_time_ms=30000
            )
        except Exception as e:
            return GrpcResponse(
                success=False,
                data=None,
                error=str(e),
                status_code=-1,
                response_time_ms=0
            )
    
    async def list_services(self) -> List[str]:
        """列出可用服务 (需要服务端启用反射)"""
        if not self._grpcurl_available:
            return []
        
        cmd = ["grpcurl"]
        if not self.use_tls:
            cmd.append("-plaintext")
        cmd.extend([self.address, "list"])
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            
            if process.returncode == 0:
                return [s.strip() for s in stdout.decode().split('\n') if s.strip()]
        except Exception:
            pass
        
        return []
    
    async def describe_service(self, service: str) -> Dict[str, Any]:
        """描述服务方法"""
        if not self._grpcurl_available:
            return {}
        
        cmd = ["grpcurl"]
        if not self.use_tls:
            cmd.append("-plaintext")
        cmd.extend([self.address, "describe", service])
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            
            if process.returncode == 0:
                return {"raw": stdout.decode()}
        except Exception:
            pass
        
        return {}
    
    def _get_value_by_path(self, data: Any, path: str) -> Any:
        """根据路径获取值"""
        if not path:
            return data
        
        keys = path.split(".")
        value = data
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            elif isinstance(value, list) and key.isdigit():
                value = value[int(key)]
            else:
                return None
        
        return value
    
    def assert_response(
        self,
        response: GrpcResponse,
        assertions: List[GrpcAssertion]
    ) -> List[Dict[str, Any]]:
        """验证响应"""
        results = []
        
        for assertion in assertions:
            actual = self._get_value_by_path(response.data, assertion.path)
            passed = False
            
            if assertion.operator == "eq":
                passed = actual == assertion.expected
            elif assertion.operator == "ne":
                passed = actual != assertion.expected
            elif assertion.operator == "contains":
                passed = assertion.expected in str(actual) if actual else False
            elif assertion.operator == "exists":
                passed = actual is not None
            elif assertion.operator == "type":
                passed = type(actual).__name__ == assertion.expected
            
            results.append({
                "path": assertion.path,
                "operator": assertion.operator,
                "expected": assertion.expected,
                "actual": actual,
                "passed": passed
            })
        
        return results
    
    async def run_test_suite(
        self,
        tests: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """运行测试套件"""
        results = []
        total_passed = 0
        total_failed = 0
        
        for test in tests:
            request = GrpcRequest(
                service=test["service"],
                method=test["method"],
                data=test.get("data", {}),
                metadata=test.get("metadata")
            )
            
            response = await self.call(request)
            
            assertions = [
                GrpcAssertion(**a) for a in test.get("assertions", [])
            ]
            
            assertion_results = self.assert_response(response, assertions) if response.success else []
            
            passed = response.success and all(r["passed"] for r in assertion_results)
            if passed:
                total_passed += 1
            else:
                total_failed += 1
            
            results.append({
                "name": test.get("name", f"{test['service']}/{test['method']}"),
                "passed": passed,
                "response_time_ms": response.response_time_ms,
                "error": response.error,
                "assertions": assertion_results
            })
        
        return {
            "total": len(tests),
            "passed": total_passed,
            "failed": total_failed,
            "success_rate": total_passed / len(tests) if tests else 0,
            "results": results
        }


def create_grpc_service(
    host: str,
    port: int = 50051,
    use_tls: bool = False
) -> GrpcTestService:
    """创建 gRPC 测试服务"""
    return GrpcTestService(host, port, use_tls)
