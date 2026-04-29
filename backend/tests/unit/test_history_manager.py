import json
from unittest.mock import patch

from core import history_manager


class TestHistoryManager:
    def test_get_data_dir_points_to_repo_data(self):
        path = history_manager.get_data_dir()
        assert path.endswith("data")

    def test_load_history_returns_empty_when_missing(self, tmp_path):
        history_file = tmp_path / "history.json"
        with patch("core.history_manager.get_history_file", return_value=str(history_file)):
            assert history_manager.load_history() == []

    def test_load_history_returns_empty_when_json_is_not_list(self, tmp_path):
        history_file = tmp_path / "history.json"
        history_file.write_text(json.dumps({"invalid": True}), encoding="utf-8")

        with patch("core.history_manager.get_history_file", return_value=str(history_file)):
            assert history_manager.load_history() == []

    def test_load_history_returns_data_when_valid(self, tmp_path):
        history_file = tmp_path / "history.json"
        payload = [{"task_id": "1"}, {"task_id": "2"}]
        history_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        with patch("core.history_manager.get_history_file", return_value=str(history_file)):
            assert history_manager.load_history() == payload

    def test_save_history_writes_file(self, tmp_path):
        history_file = tmp_path / "history.json"
        payload = [{"task_id": "1", "status": "done"}]

        with patch("core.history_manager.get_history_file", return_value=str(history_file)):
            with patch("core.history_manager.ensure_data_dir"):
                history_manager.save_history(payload)

        written = json.loads(history_file.read_text(encoding="utf-8"))
        assert written == payload
