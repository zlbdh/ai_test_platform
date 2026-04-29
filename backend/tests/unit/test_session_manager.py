import pytest
import threading
import time
from core.session_manager import SessionManager, SessionState

class TestSessionManager:
    """测试 SessionManager 与 SessionState 的多会话隔离及线程安全"""

    def setup_method(self):
        SessionManager._sessions.clear()

    def test_basic_session(self):
        session = SessionManager.get_session("test_1")
        
        # Test default states
        assert session.session_id == "test_1"
        assert session.agent_status == "IDLE"
        assert session.execution_signal == "RUNNING"
        assert len(session.get_logs()) == 0

        # Test state modifications
        session.set_status("BUSY", task="Login")
        assert session.agent_status == "BUSY"
        assert session.current_task == "Login"

        session.set_signal("PAUSED", reason="Waiting user")
        assert session.execution_signal == "PAUSED"
        assert session.get_pause_reason() == "Waiting user"
        
        session.append_log({"type": "info", "msg": "started"})
        assert len(session.get_logs()) == 1

    def test_multiple_sessions_isolation(self):
        s1 = SessionManager.get_session("s1")
        s2 = SessionManager.get_session("s2")

        s1.set_status("BUSY", "task1")
        s2.set_status("PAUSED", "task2")

        assert s1.agent_status == "BUSY"
        assert s2.agent_status == "PAUSED"

        s1.append_log({"s": 1})
        s2.append_log({"s": 2})

        assert len(s1.get_logs()) == 1
        assert len(s2.get_logs()) == 1
        assert s1.get_logs()[0]["s"] == 1
        assert s2.get_logs()[0]["s"] == 2
        
        SessionManager.remove_session("s1")
        assert "s1" not in SessionManager.list_sessions()
        assert "s2"  in SessionManager.list_sessions()

    def test_thread_safety(self):
        session = SessionManager.get_session("thread_test")
        
        def worker(thread_id):
            for i in range(100):
                session.append_log({"t": thread_id, "i": i})
                time.sleep(0.001)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(session.get_logs()) == 500

    @pytest.mark.asyncio
    async def test_run_browser_direct_on_owner_thread(self):
        session = SessionManager.get_session("browser_direct")
        page = {"value": 41}
        session.set_page(page)

        result = await session.run_browser(lambda active_page: active_page["value"] + 1)
        assert result == 42

    @pytest.mark.asyncio
    async def test_run_browser_dispatches_to_owner_thread(self):
        session = SessionManager.get_session("browser_bridge")
        owner_ready = threading.Event()
        owner_stop = threading.Event()
        page = {"value": 41}

        def owner_worker():
            session.set_page(page)
            owner_ready.set()
            while not owner_stop.is_set():
                session.process_browser_commands(page, max_commands=10)
                time.sleep(0.01)
            session.clear()

        worker = threading.Thread(target=owner_worker, daemon=True)
        worker.start()
        owner_ready.wait(timeout=1.0)

        try:
            result = await session.run_browser(lambda active_page: active_page["value"] + 1, timeout=1.0)
            assert result == 42
        finally:
            owner_stop.set()
            worker.join(timeout=1.0)
