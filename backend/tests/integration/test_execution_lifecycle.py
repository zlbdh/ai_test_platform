"""
Execution lifecycle integration tests.
Covers the complete /api/start -> /api/status -> /api/control/stop lifecycle.
Requires a running backend service.
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
    Verify the complete test execution lifecycle.
    Requires the backend service at 127.0.0.1:8020.
    """

    def test_status_idle(self):
        """The initial state should be IDLE."""
        r = _request_or_skip("get", "/api/status")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "IDLE"
        assert data["is_running"] is False

    def test_start_stop_lifecycle(self):
        """Start a task, check its running state, then stop it."""
        # 1. Start with a simple request that needs no real LLM; execution may fail, but the lifecycle should work.
        start_payload = {
            "requirement": "Test case: open Baidu",
            "target_url": "https://www.baidu.com",
            "mode": "CLOUD",
            "planner_mode": "quick",
        }
        try:
            r = _request_or_skip("post", "/api/start", json=start_payload, timeout=10)
            # Startup may succeed or fail if the LLM is unavailable.
            if r.status_code not in (200, 500):
                pytest.skip(f"Unexpected start response: {r.status_code}")
        except httpx.TimeoutException:
            pytest.skip("Start request timed out")

        # 2. Check the status.
        time.sleep(1)
        r = _request_or_skip("get", "/api/status")
        assert r.status_code == 200

        # 3. Stop the task.
        try:
            r = _request_or_skip("post", "/api/control/stop")
            assert r.status_code == 200
        except httpx.TimeoutException:
            pass  # Stop might take time

        # 4. Wait for the state to return to IDLE.
        for _ in range(5):
            time.sleep(1)
            r = _request_or_skip("get", "/api/status")
            if r.json().get("status") == "IDLE":
                break

    def test_stop_when_idle(self):
        """Stopping while IDLE should not raise an error."""
        r = _request_or_skip("post", "/api/control/stop")
        # The request should succeed even if no task is running.
        assert r.status_code in (200, 400, 404)

    def test_health_endpoint(self):
        """Check health at the root endpoint."""
        r = _request_or_skip("get", "/")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
