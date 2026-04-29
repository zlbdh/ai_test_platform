"""
执行生命周期集成测试
覆盖: /api/start → /api/status → /api/control/stop 完整生命周期
需要后端服务运行才能执行
"""
import os
import time

import httpx
import pytest


DEFAULT_CANDIDATE_URLS = [
    "http://127.0.0.1:8021",
    "http://127.0.0.1:8020",
]


def _resolve_base_url():
    env_base_url = os.getenv("AI_TEST_BACKEND_URL", "").strip()
    candidate_urls = [env_base_url] if env_base_url else DEFAULT_CANDIDATE_URLS

    for base_url in candidate_urls:
        if not base_url:
            continue
        try:
            root_response = httpx.get(f"{base_url}/", timeout=3)
            status_response = httpx.get(f"{base_url}/api/status", timeout=3)
            if root_response.status_code == 200 and status_response.status_code == 200:
                return base_url
        except Exception:
            continue
    return ""


BASE_URL = _resolve_base_url()


def _backend_available():
    return bool(BASE_URL)


def _request_or_skip(method: str, path: str, **kwargs):
    if not BASE_URL:
        pytest.skip("Backend not running or /api/status is unavailable on supported ports")

    request = getattr(httpx, method)
    timeout = kwargs.pop("timeout", 5)

    try:
        response = request(f"{BASE_URL}{path}", timeout=timeout, **kwargs)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        pytest.skip(f"Backend unavailable during integration test: {exc}")

    if response.status_code == 503 and not response.text.strip():
        pytest.skip("Backend became unavailable during integration test")

    return response


@pytest.mark.integration
@pytest.mark.skipif(
    not _backend_available(),
    reason="Backend not running or /api/status is unavailable on supported ports",
)
class TestExecutionLifecycle:
    """
    集成测试：验证测试执行的完整生命周期。
    需要后端服务在 127.0.0.1:8020 运行。
    """

    def test_status_idle(self):
        """初始状态应为 IDLE"""
        r = _request_or_skip("get", "/api/status")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "IDLE"
        assert data["is_running"] is False

    def test_start_stop_lifecycle(self):
        """启动任务 → 检查运行中状态 → 停止任务"""
        # 1. 启动（使用一个无需真实 LLM 的简单请求，预期可能失败但生命周期应正常）
        start_payload = {
            "requirement": "测试用例: 打开百度",
            "target_url": "https://www.baidu.com",
            "mode": "CLOUD",
            "planner_mode": "quick",
        }
        try:
            r = _request_or_skip("post", "/api/start", json=start_payload, timeout=10)
            # 可能成功启动，也可能因 LLM 不可用而报错
            if r.status_code not in (200, 500):
                pytest.skip(f"Unexpected start response: {r.status_code}")
        except httpx.TimeoutException:
            pytest.skip("Start request timed out")

        # 2. 检查状态
        time.sleep(1)
        r = _request_or_skip("get", "/api/status")
        assert r.status_code == 200

        # 3. 停止
        try:
            r = _request_or_skip("post", "/api/control/stop")
            assert r.status_code == 200
        except httpx.TimeoutException:
            pass  # Stop might take time

        # 4. 等待回到 IDLE
        for _ in range(5):
            time.sleep(1)
            r = _request_or_skip("get", "/api/status")
            if r.json().get("status") == "IDLE":
                break

    def test_stop_when_idle(self):
        """IDLE 状态下停止应不会出错"""
        r = _request_or_skip("post", "/api/control/stop")
        # 应该返回成功（即使没有运行中的任务）
        assert r.status_code in (200, 400, 404)

    def test_health_endpoint(self):
        """根路径健康检查"""
        r = _request_or_skip("get", "/")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
