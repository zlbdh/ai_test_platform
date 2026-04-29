import pytest
from fastapi.testclient import TestClient
from main import app
from core.shared import SharedBrowserState

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_state():
    """Reset SharedBrowserState before each test"""
    # Save original state
    original_signal = SharedBrowserState.get_signal()
    original_reason = SharedBrowserState.get_pause_reason()
    
    yield
    
    # Restore or Reset
    SharedBrowserState.set_signal("IDLE", None)

def test_api_status_consistency():
    """Verify /api/status returns all expected fields"""
    resp = client.get("/api/status")
    print(f"DEBUG: /api/status response: {resp.json()}")
    assert resp.status_code == 200
    data = resp.json()
    
    # Check core fields
    assert "status" in data
    assert "signal" in data
    assert "task" in data
    assert "is_running" in data
    
    # Check fields added in Round 3 refactor
    assert "pause_reason" in data, f"Missing pause_reason in {list(data.keys())}"
    assert "active_task_id" in data, f"Missing active_task_id in {list(data.keys())}"
    
    # Check signal matches shared state
    assert data["signal"] == SharedBrowserState.get_signal()

def test_suspend_flow():
    """Verify suspend control flow"""
    # 1. Suspend
    reason = "Integration Test Pause"
    resp = client.post("/api/control/suspend", json={"reason": reason})
    print(f"DEBUG: /api/control/suspend response: {resp.json()}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "suspended"
    
    # 2. Verify State
    assert SharedBrowserState.get_signal() == "PAUSED"
    assert SharedBrowserState.get_pause_reason() == reason
    
    # 3. Verify Status API interaction
    status_resp = client.get("/api/status")
    assert status_resp.json()["signal"] == "PAUSED"
    assert status_resp.json()["pause_reason"] == reason

def test_resume_flow():
    """Verify resume control flow"""
    # Setup: First suspend
    client.post("/api/control/suspend", json={"reason": "To be resumed"})
    assert SharedBrowserState.get_signal() == "PAUSED"
    
    # Action: Resume
    resp = client.post("/api/control/resume")
    assert resp.status_code == 200
    
    # Verify State
    # Note: Depending on implementation, it might go to RUNNING or RESUME
    # main.py line ~295: SharedBrowserState.set_signal("RUNNING")
    assert SharedBrowserState.get_signal() == "RUNNING"
    assert SharedBrowserState.get_pause_reason() is None
    
    # Verify Status API
    status_resp = client.get("/api/status")
    assert status_resp.json()["signal"] == "RUNNING"
    assert status_resp.json()["pause_reason"] is None
