"""
log_tools unit tests.
Covers missing files, log tails, line-count boundaries, and read failures.
"""
from pathlib import Path
from unittest.mock import patch

from core.log_tools import read_server_logs


class TestReadServerLogs:
    def test_returns_empty_for_non_positive_lines(self, tmp_path):
        log_file = tmp_path / "server.log"
        log_file.write_text("a\nb\n", encoding="utf-8")

        with patch("core.log_tools.LOG_PATH", str(log_file)):
            assert read_server_logs(0) == ""
            assert read_server_logs(-5) == ""

    def test_returns_not_found_message(self, tmp_path):
        missing_file = tmp_path / "missing.log"
        with patch("core.log_tools.LOG_PATH", str(missing_file)):
            result = read_server_logs()
        assert f"Log file not found at: {missing_file}" == result

    def test_reads_last_n_lines(self, tmp_path):
        log_file = tmp_path / "server.log"
        log_file.write_text("1\n2\n3\n4\n", encoding="utf-8")

        with patch("core.log_tools.LOG_PATH", str(log_file)):
            result = read_server_logs(2)
        assert result == "3\n4\n"

    def test_returns_failure_message_on_read_error(self, tmp_path):
        log_file = tmp_path / "server.log"
        log_file.write_text("demo\n", encoding="utf-8")

        with patch("core.log_tools.LOG_PATH", str(log_file)), \
             patch("builtins.open", side_effect=OSError("access denied")):
            result = read_server_logs()
        assert result == "Failed to read logs: access denied"
