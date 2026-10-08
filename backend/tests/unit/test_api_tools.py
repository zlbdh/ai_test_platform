"""
api_tools unit tests.
Covers JSON responses, text fallback, default request parameters, and error paths.
"""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from core.api_tools import http_request


class TestHttpRequest:
    def test_returns_json_content(self):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"ok": True}
        response.text = '{"ok": true}'
        response.elapsed.total_seconds.return_value = 0.23
        response.headers = {"X-Test": "1"}

        with patch("core.api_tools.requests.request", return_value=response) as mock_request:
            result = http_request("get", "https://example.com/api")

        mock_request.assert_called_once_with(
            method="GET",
            url="https://example.com/api",
            headers={"Content-Type": "application/json"},
            json=None,
            timeout=10,
        )
        assert result == {
            "status_code": 200,
            "content": {"ok": True},
            "elapsed": 0.23,
            "headers": {"X-Test": "1"},
        }

    def test_falls_back_to_truncated_text(self):
        response = MagicMock()
        response.status_code = 202
        response.json.side_effect = ValueError("not json")
        response.text = "x" * 3000
        response.elapsed.total_seconds.return_value = 1.5
        response.headers = {}

        with patch("core.api_tools.requests.request", return_value=response):
            result = http_request("post", "https://example.com/api", headers={"X-App": "demo"}, json_body={"a": 1})

        assert result["status_code"] == 202
        assert result["content"] == "x" * 2000
        assert result["elapsed"] == 1.5

    def test_preserves_custom_headers_and_body(self):
        response = MagicMock()
        response.status_code = 204
        response.json.side_effect = ValueError("empty")
        response.text = ""
        response.elapsed.total_seconds.return_value = 0.0
        response.headers = {"Content-Length": "0"}

        with patch("core.api_tools.requests.request", return_value=response) as mock_request:
            http_request(
                "patch",
                "https://example.com/api/1",
                headers={"Authorization": "Bearer token"},
                json_body={"enabled": True},
            )

        mock_request.assert_called_once_with(
            method="PATCH",
            url="https://example.com/api/1",
            headers={"Authorization": "Bearer token"},
            json={"enabled": True},
            timeout=10,
        )

    def test_returns_error_payload_on_request_failure(self):
        with patch("core.api_tools.requests.request", side_effect=RuntimeError("network down")):
            result = http_request("get", "https://example.com/api")

        assert result == {"error": "network down", "status_code": -1}
