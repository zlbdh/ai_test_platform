from unittest.mock import MagicMock, patch

from agents.orchestrator import Orchestrator


def test_generate_task_id_is_uuid_backed_and_unique():
    with patch("agents.orchestrator.session_manager") as mock_session_manager:
        mock_session_manager.get_session.return_value = MagicMock()
        orch = Orchestrator(session_id="task_id_test")

    first = orch._generate_task_id()
    second = orch._generate_task_id()

    assert first.startswith("task_")
    assert second.startswith("task_")
    assert len(first) == len("task_") + 32
    assert len(second) == len("task_") + 32
    assert first != second
