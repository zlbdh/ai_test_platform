"""
Environment Validator - 环境验证器

在测试执行前验证环境配置：
- 依赖检查
- 服务健康检查
- 配置验证
- 资源可用性
"""

from typing import Dict, Any, List, Optional, Sequence, Tuple
from dataclasses import dataclass
from enum import Enum
import os
import shutil
import asyncio
import aiohttp


class CheckStatus(Enum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


@dataclass
class CheckResult:
    """检查结果"""
    name: str
    status: CheckStatus
    message: str
    details: Optional[Dict[str, Any]] = None


class EnvironmentValidator:
    """环境验证器"""

    DEFAULT_DIRECTORIES = ("./reports", "./data", "./logs")
    DEFAULT_SERVICES = (("Backend API", "http://localhost:8020/api/status"),)

    def __init__(
        self,
        directories: Optional[Sequence[str]] = None,
        services: Optional[Sequence[Tuple[str, str]]] = None
    ):
        self.checks: List[CheckResult] = []
        self.directories = list(directories or self.DEFAULT_DIRECTORIES)
        self.services = list(services or self.DEFAULT_SERVICES)
    
    async def validate_all(self) -> Dict[str, Any]:
        """执行所有验证"""
        self.checks = []
        
        # 1. Python 依赖检查
        self._check_python_deps()
        
        # 2. 外部工具检查
        self._check_external_tools()
        
        # 3. 环境变量检查
        self._check_env_vars()
        
        # 4. 目录权限检查
        self._check_directories()
        
        # 5. 服务健康检查
        await self._check_services()
        
        # 汇总结果
        passed = sum(1 for c in self.checks if c.status == CheckStatus.PASSED)
        warnings = sum(1 for c in self.checks if c.status == CheckStatus.WARNING)
        failed = sum(1 for c in self.checks if c.status == CheckStatus.FAILED)
        
        return {
            "status": "ready" if failed == 0 else "not_ready",
            "summary": {
                "total": len(self.checks),
                "passed": passed,
                "warnings": warnings,
                "failed": failed
            },
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    **({"details": c.details} if c.details else {})
                }
                for c in self.checks
            ]
        }

    @staticmethod
    def _is_env_configured(var_name: str) -> bool:
        """环境变量是否有效配置"""
        value = os.getenv(var_name)
        return bool(value and value.strip())
    
    def _check_python_deps(self):
        """检查 Python 依赖"""
        required_packages = [
            "fastapi",
            "uvicorn",
            "langchain",
            "playwright",
            "aiohttp",
            "pydantic"
        ]
        
        for package in required_packages:
            try:
                __import__(package)
                self.checks.append(CheckResult(
                    name=f"Python: {package}",
                    status=CheckStatus.PASSED,
                    message="已安装"
                ))
            except ImportError:
                self.checks.append(CheckResult(
                    name=f"Python: {package}",
                    status=CheckStatus.FAILED,
                    message=f"未安装，请运行: pip install {package}"
                ))
    
    def _check_external_tools(self):
        """检查外部工具"""
        tools = {
            "grpcurl": "gRPC 测试工具",
            "allure": "Allure 报告工具"
        }
        
        for tool, desc in tools.items():
            if shutil.which(tool):
                self.checks.append(CheckResult(
                    name=f"Tool: {tool}",
                    status=CheckStatus.PASSED,
                    message=f"{desc} 已安装"
                ))
            else:
                self.checks.append(CheckResult(
                    name=f"Tool: {tool}",
                    status=CheckStatus.WARNING,
                    message=f"{desc} 未安装（可选）"
                ))
    
    def _check_env_vars(self):
        """检查环境变量"""
        required_vars = {
            "OPENAI_API_KEY": "OpenAI API 密钥（或其他 LLM Provider Key）"
        }
        
        optional_vars = {
            "LLM_PROVIDER": "LLM 提供商 (openai/gemini/deepseek)",
            "OPENAI_BASE_URL": "OpenAI 兼容网关地址",
            "GEMINI_API_KEY": "Gemini API 密钥",
            "DEEPSEEK_API_KEY": "DeepSeek API 密钥"
        }
        
        for var, desc in required_vars.items():
            if self._is_env_configured(var):
                self.checks.append(CheckResult(
                    name=f"Env: {var}",
                    status=CheckStatus.PASSED,
                    message=f"{desc} 已配置"
                ))
            else:
                self.checks.append(CheckResult(
                    name=f"Env: {var}",
                    status=CheckStatus.WARNING,
                    message=f"{desc} 未配置（使用默认值）"
                ))
        
        for var, desc in optional_vars.items():
            configured = self._is_env_configured(var)
            status = CheckStatus.PASSED if configured else CheckStatus.WARNING
            self.checks.append(CheckResult(
                name=f"Env: {var}",
                status=status,
                message=f"{desc} {'已' if configured else '未'}配置"
            ))
    
    def _check_directories(self):
        """检查目录权限"""
        for dir_path in self.directories:
            if os.path.exists(dir_path):
                if os.access(dir_path, os.W_OK):
                    self.checks.append(CheckResult(
                        name=f"Dir: {dir_path}",
                        status=CheckStatus.PASSED,
                        message="可写"
                    ))
                else:
                    self.checks.append(CheckResult(
                        name=f"Dir: {dir_path}",
                        status=CheckStatus.WARNING,
                        message="无写入权限"
                    ))
            else:
                try:
                    os.makedirs(dir_path, exist_ok=True)
                    self.checks.append(CheckResult(
                        name=f"Dir: {dir_path}",
                        status=CheckStatus.PASSED,
                        message="已创建"
                    ))
                except Exception as e:
                    self.checks.append(CheckResult(
                        name=f"Dir: {dir_path}",
                        status=CheckStatus.FAILED,
                        message=f"创建失败: {e}"
                    ))
    
    async def _check_services(self):
        """检查服务健康"""
        async with aiohttp.ClientSession() as session:
            for name, url in self.services:
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if 200 <= resp.status < 300:
                            self.checks.append(CheckResult(
                                name=f"Service: {name}",
                                status=CheckStatus.PASSED,
                                message="运行中",
                                details={"url": url, "status_code": resp.status}
                            ))
                        else:
                            self.checks.append(CheckResult(
                                name=f"Service: {name}",
                                status=CheckStatus.WARNING,
                                message=f"响应异常: {resp.status}",
                                details={"url": url, "status_code": resp.status}
                            ))
                except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
                    self.checks.append(CheckResult(
                        name=f"Service: {name}",
                        status=CheckStatus.WARNING,
                        message="无法连接（服务可能未启动）",
                        details={"url": url}
                    ))


def get_validator() -> EnvironmentValidator:
    """获取验证器"""
    return EnvironmentValidator()
