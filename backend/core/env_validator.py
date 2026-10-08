"""
Environment Validator

Validate the environment before running tests:
- Dependency checks
- Service health checks
- Configuration validation
- Resource availability
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
    """Check result"""
    name: str
    status: CheckStatus
    message: str
    details: Optional[Dict[str, Any]] = None


class EnvironmentValidator:
    """Environment validator"""

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
        """Run all validation checks"""
        self.checks = []

        # 1. Python dependency checks
        self._check_python_deps()

        # 2. External-tool checks
        self._check_external_tools()

        # 3. Environment-variable checks
        self._check_env_vars()

        # 4. Directory-permission checks
        self._check_directories()

        # 5. Service health checks
        await self._check_services()

        # Summarize results
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
        """Whether an environment variable is configured correctly"""
        value = os.getenv(var_name)
        return bool(value and value.strip())

    def _check_python_deps(self):
        """Check Python dependencies"""
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
                    message="installed"
                ))
            except ImportError:
                self.checks.append(CheckResult(
                    name=f"Python: {package}",
                    status=CheckStatus.FAILED,
                    message=f"not installed; run: pip install {package}"
                ))

    def _check_external_tools(self):
        """Check external tools"""
        tools = {
            "grpcurl": "gRPC testing tool",
            "allure": "Allure reporting tool"
        }

        for tool, desc in tools.items():
            if shutil.which(tool):
                self.checks.append(CheckResult(
                    name=f"Tool: {tool}",
                    status=CheckStatus.PASSED,
                    message=f"{desc} installed"
                ))
            else:
                self.checks.append(CheckResult(
                    name=f"Tool: {tool}",
                    status=CheckStatus.WARNING,
                    message=f"{desc} not installed (optional)"
                ))

    def _check_env_vars(self):
        """Check environment variables"""
        required_vars = {
            "OPENAI_API_KEY": "OpenAI API key or another LLM provider key"
        }

        optional_vars = {
            "LLM_PROVIDER": "LLM provider (openai/gemini/deepseek)",
            "OPENAI_BASE_URL": "OpenAI-compatible gateway URL",
            "GEMINI_API_KEY": "Gemini API key",
            "DEEPSEEK_API_KEY": "DeepSeek API key"
        }

        for var, desc in required_vars.items():
            if self._is_env_configured(var):
                self.checks.append(CheckResult(
                    name=f"Env: {var}",
                    status=CheckStatus.PASSED,
                    message=f"{desc} configured"
                ))
            else:
                self.checks.append(CheckResult(
                    name=f"Env: {var}",
                    status=CheckStatus.WARNING,
                    message=f"{desc} not configured (using the default)"
                ))

        for var, desc in optional_vars.items():
            configured = self._is_env_configured(var)
            status = CheckStatus.PASSED if configured else CheckStatus.WARNING
            self.checks.append(CheckResult(
                name=f"Env: {var}",
                status=status,
                message=f"{desc} {'configured' if configured else 'not configured'}"
            ))

    def _check_directories(self):
        """Check directory permissions"""
        for dir_path in self.directories:
            if os.path.exists(dir_path):
                if os.access(dir_path, os.W_OK):
                    self.checks.append(CheckResult(
                        name=f"Dir: {dir_path}",
                        status=CheckStatus.PASSED,
                        message="Writable"
                    ))
                else:
                    self.checks.append(CheckResult(
                        name=f"Dir: {dir_path}",
                        status=CheckStatus.WARNING,
                        message="No write permission"
                    ))
            else:
                try:
                    os.makedirs(dir_path, exist_ok=True)
                    self.checks.append(CheckResult(
                        name=f"Dir: {dir_path}",
                        status=CheckStatus.PASSED,
                        message="Created"
                    ))
                except Exception as e:
                    self.checks.append(CheckResult(
                        name=f"Dir: {dir_path}",
                        status=CheckStatus.FAILED,
                        message=f"Creation failed: {e}"
                    ))

    async def _check_services(self):
        """Check service health"""
        async with aiohttp.ClientSession() as session:
            for name, url in self.services:
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if 200 <= resp.status < 300:
                            self.checks.append(CheckResult(
                                name=f"Service: {name}",
                                status=CheckStatus.PASSED,
                                message="Running",
                                details={"url": url, "status_code": resp.status}
                            ))
                        else:
                            self.checks.append(CheckResult(
                                name=f"Service: {name}",
                                status=CheckStatus.WARNING,
                                message=f"Unexpected response: {resp.status}",
                                details={"url": url, "status_code": resp.status}
                            ))
                except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
                    self.checks.append(CheckResult(
                        name=f"Service: {name}",
                        status=CheckStatus.WARNING,
                        message="Cannot connect; the service may not be running",
                        details={"url": url}
                    ))


def get_validator() -> EnvironmentValidator:
    """Get the validator"""
    return EnvironmentValidator()
