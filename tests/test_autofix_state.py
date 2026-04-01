from src.tools.autofix_state import load_autofix_state, save_autofix_state


def test_autofix_state_roundtrip(tmp_path):
    payload = {"trace_id": "abc", "status": "running", "attempts": []}
    save_autofix_state(str(tmp_path), "abc", payload)
    loaded = load_autofix_state(str(tmp_path), "abc")
    assert loaded["status"] == "running"
    assert loaded["trace_id"] == "abc"
