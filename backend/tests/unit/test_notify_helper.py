"""
notify_helper unit tests.
Covers message formatting, short-circuiting without configuration, send success/
failure, and exception handling.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.notify_helper import _format_message, send_completion_notification


class TestFormatMessage:
    def test_formats_dingtalk(self):
        payload = _format_message("dingtalk", "Report", "completed", "Summary", {"total_steps": 3, "passed": 2, "failed": 1, "duration": "5s"})
        assert payload["msgtype"] == "markdown"
        assert "Report" in payload["markdown"]["title"]
        assert "Steps: 3" in payload["markdown"]["text"]

    def test_formats_wecom(self):
        payload = _format_message("wecom", "Report", "failed", "Summary")
        assert payload["msgtype"] == "markdown"
        assert "❌" in payload["markdown"]["content"]

    def test_formats_notification_platform(self):
        payload = _format_message("notification_platform", "Report", "stopped", "Summary")
        assert payload["msg_type"] == "interactive"
        assert "⏹️ Report" in payload["card"]["header"]["title"]["content"]

    def test_formats_annotations(self):
        payload = _format_message(
            "notification_platform",
            "Report",
            "warning",
            "Summary",
            {"annotations": ["The requirement text appears corrupted; a readable title was used as a fallback."]},
        )
        assert "The requirement text appears corrupted" in payload["card"]["elements"][0]["content"]

    def test_formats_custom(self):
        payload = _format_message("custom", "Report", "unknown", "Summary")
        assert payload["title"] == "Report"
        assert payload["status"] == "unknown"
        assert "📋" in payload["message"]

    def test_formats_warning(self):
        payload = _format_message("custom", "Warning", "warning", "Shadow database detected")
        assert payload["status"] == "warning"
        assert "⚠️" in payload["message"]


class TestSendCompletionNotification:
    @pytest.mark.asyncio
    async def test_returns_when_table_missing(self):
        with patch("core.notify_helper.query_all", side_effect=RuntimeError("no table")):
            result = await send_completion_notification("Report", "completed", "Summary")
        assert result["configured"] == 0
        assert result["delivered"] == 0

    @pytest.mark.asyncio
    async def test_returns_when_no_rows(self):
        with patch("core.notify_helper.query_all", return_value=[]):
            result = await send_completion_notification("Report", "completed", "Summary")
        assert result["configured"] == 0
        assert result["delivered"] == 0

    @pytest.mark.asyncio
    async def test_sends_to_all_rows_with_single_client(self):
        rows = [
            {"name": "DingTalk", "url": "https://example.com/a", "type": "dingtalk"},
            {"name": "Custom", "url": "https://example.com/b", "type": "custom"},
        ]
        response = MagicMock(status_code=200)
        client = AsyncMock()
        client.post = AsyncMock(return_value=response)
        client_cm = AsyncMock()
        client_cm.__aenter__.return_value = client
        client_cm.__aexit__.return_value = False

        with patch("core.notify_helper.query_all", return_value=rows), \
             patch("core.notify_helper.httpx.AsyncClient", return_value=client_cm) as mock_client:
            result = await send_completion_notification("Report", "completed", "Summary", {"total_steps": 2})

        mock_client.assert_called_once_with(timeout=10)
        assert client.post.await_count == 2
        assert result["configured"] == 2
        assert result["attempted"] == 2
        assert result["delivered"] == 2
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_non_2xx_and_exception_are_tolerated(self):
        rows = [
            {"name": "Failure status code", "url": "https://example.com/a", "type": "custom"},
            {"name": "Exception", "url": "https://example.com/b", "type": "custom"},
        ]
        client = AsyncMock()
        client.post = AsyncMock(side_effect=[
            MagicMock(status_code=500), MagicMock(status_code=500), MagicMock(status_code=500),
            RuntimeError("network down"), RuntimeError("network down"), RuntimeError("network down"),
        ])
        client_cm = AsyncMock()
        client_cm.__aenter__.return_value = client
        client_cm.__aexit__.return_value = False

        with patch("core.notify_helper.query_all", return_value=rows), \
             patch("core.notify_helper.asyncio.sleep", new=AsyncMock()), \
             patch("core.notify_helper.httpx.AsyncClient", return_value=client_cm):
            result = await send_completion_notification("Report", "failed", "Summary")

        assert client.post.await_count == 6
        assert result["attempted"] == 2
        assert result["delivered"] == 0
        assert result["failed"] == 2

    @pytest.mark.asyncio
    async def test_retries_transient_5xx_then_succeeds(self):
        rows = [
            {"name": "Transient failure", "url": "https://example.com/a", "type": "custom"},
        ]
        client = AsyncMock()
        client.post = AsyncMock(side_effect=[MagicMock(status_code=503), MagicMock(status_code=200)])
        client_cm = AsyncMock()
        client_cm.__aenter__.return_value = client
        client_cm.__aexit__.return_value = False

        with patch("core.notify_helper.query_all", return_value=rows), \
             patch("core.notify_helper.asyncio.sleep", new=AsyncMock()) as sleep_mock, \
             patch("core.notify_helper.httpx.AsyncClient", return_value=client_cm):
            result = await send_completion_notification("Report", "warning", "Summary")

        assert client.post.await_count == 2
        sleep_mock.assert_awaited_once()
        assert result["delivered"] == 1
        assert result["failed"] == 0
