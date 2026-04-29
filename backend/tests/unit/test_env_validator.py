"""
EnvironmentValidator 单元测试
覆盖: validate_all, _check_python_deps, _check_external_tools,
      _check_env_vars, _check_directories, _check_services
"""

import os
from unittest.mock import AsyncMock, patch

import pytest

from core.env_validator import (
    CheckResult,
    CheckStatus,
    EnvironmentValidator,
    get_validator,
)


class FakeServiceResponse:
    def __init__(self, status: int):
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeServiceSession:
    def __init__(self, status: int):
        self.status = status
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, url, timeout=None):
        self.calls.append({"url": url, "timeout": timeout})
        return FakeServiceResponse(self.status)


class TestCheckStatus:
    def test_enum_values(self):
        assert CheckStatus.PASSED.value == "passed"
        assert CheckStatus.WARNING.value == "warning"
        assert CheckStatus.FAILED.value == "failed"


class TestCheckResult:
    def test_creation(self):
        result = CheckResult(
            name="Python: fastapi",
            status=CheckStatus.PASSED,
            message="已安装",
        )
        assert result.name == "Python: fastapi"
        assert result.details is None


class TestCheckPythonDeps:
    def test_installed_package(self):
        validator = EnvironmentValidator()
        validator._check_python_deps()
        passed = [c for c in validator.checks if c.status == CheckStatus.PASSED]
        assert len(passed) > 0

    def test_missing_package(self):
        validator = EnvironmentValidator()
        with patch("builtins.__import__", side_effect=ImportError):
            validator._check_python_deps()
        failed = [c for c in validator.checks if c.status == CheckStatus.FAILED]
        assert len(failed) > 0


class TestCheckExternalTools:
    def test_with_shutil_mock(self):
        validator = EnvironmentValidator()
        with patch("core.env_validator.shutil.which", return_value=None):
            validator._check_external_tools()
        warnings = [c for c in validator.checks if c.status == CheckStatus.WARNING]
        assert len(warnings) == 2

    def test_tools_found(self):
        validator = EnvironmentValidator()
        with patch("core.env_validator.shutil.which", return_value="/usr/bin/tool"):
            validator._check_external_tools()
        passed = [c for c in validator.checks if c.status == CheckStatus.PASSED]
        assert len(passed) == 2


class TestCheckEnvVars:
    def test_with_env_set(self):
        validator = EnvironmentValidator()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            validator._check_env_vars()
        passed = [
            c for c in validator.checks
            if "OPENAI_API_KEY" in c.name and c.status == CheckStatus.PASSED
        ]
        assert len(passed) == 1

    def test_whitespace_env_treated_as_missing(self):
        validator = EnvironmentValidator()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "   ", "LLM_PROVIDER": "openai"}, clear=True):
            validator._check_env_vars()

        api_key_check = next(c for c in validator.checks if c.name == "Env: OPENAI_API_KEY")
        provider_check = next(c for c in validator.checks if c.name == "Env: LLM_PROVIDER")
        assert api_key_check.status == CheckStatus.WARNING
        assert provider_check.status == CheckStatus.PASSED


class TestCheckDirectories:
    def test_existing_writable_dir(self, tmp_path):
        validator = EnvironmentValidator(directories=[str(tmp_path)])
        validator._check_directories()
        assert validator.checks[0].status == CheckStatus.PASSED

    def test_create_failure_marks_failed(self):
        validator = EnvironmentValidator(directories=["./blocked"])
        with patch("core.env_validator.os.path.exists", return_value=False):
            with patch("core.env_validator.os.makedirs", side_effect=PermissionError("blocked")):
                validator._check_directories()

        assert validator.checks[0].status == CheckStatus.FAILED
        assert "blocked" in validator.checks[0].message


class TestCheckServices:
    @pytest.mark.asyncio
    async def test_service_healthy(self):
        validator = EnvironmentValidator(services=[("Backend API", "http://localhost:8020/api/status")])
        fake_session = FakeServiceSession(status=200)

        with patch("core.env_validator.aiohttp.ClientSession", return_value=fake_session):
            await validator._check_services()

        assert validator.checks[0].status == CheckStatus.PASSED
        assert validator.checks[0].details == {
            "url": "http://localhost:8020/api/status",
            "status_code": 200,
        }

    @pytest.mark.asyncio
    async def test_service_non_2xx_is_warning(self):
        validator = EnvironmentValidator(services=[("Backend API", "http://localhost:8020/api/status")])
        fake_session = FakeServiceSession(status=503)

        with patch("core.env_validator.aiohttp.ClientSession", return_value=fake_session):
            await validator._check_services()

        assert validator.checks[0].status == CheckStatus.WARNING
        assert validator.checks[0].details["status_code"] == 503

    @pytest.mark.asyncio
    async def test_service_connection_error(self):
        validator = EnvironmentValidator(services=[("Backend API", "http://localhost:8020/api/status")])

        class BrokenSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            def get(self, url, timeout=None):
                raise OSError("offline")

        with patch("core.env_validator.aiohttp.ClientSession", return_value=BrokenSession()):
            await validator._check_services()

        assert validator.checks[0].status == CheckStatus.WARNING
        assert validator.checks[0].details == {"url": "http://localhost:8020/api/status"}


class TestValidateAll:
    @pytest.mark.asyncio
    async def test_validate_all_summary(self):
        validator = EnvironmentValidator(directories=[], services=[])
        validator._check_python_deps = lambda: validator.checks.append(
            CheckResult("deps", CheckStatus.PASSED, "ok")
        )
        validator._check_external_tools = lambda: validator.checks.append(
            CheckResult("tools", CheckStatus.WARNING, "optional")
        )
        validator._check_env_vars = lambda: validator.checks.append(
            CheckResult("env", CheckStatus.FAILED, "missing")
        )
        validator._check_directories = lambda: validator.checks.append(
            CheckResult("dirs", CheckStatus.PASSED, "ok")
        )
        validator._check_services = AsyncMock(
            side_effect=lambda: validator.checks.append(
                CheckResult("svc", CheckStatus.PASSED, "ok")
            )
        )

        result = await validator.validate_all()

        assert result["status"] == "not_ready"
        assert result["summary"] == {
            "total": 5,
            "passed": 3,
            "warnings": 1,
            "failed": 1,
        }


class TestGetValidator:
    def test_factory(self):
        validator = get_validator()
        assert isinstance(validator, EnvironmentValidator)
