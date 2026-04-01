from src.tools.logger import load_audit_events, log_event, new_trace_id


def test_log_event_writes_and_loads_audit(tmp_path):
    trace_id = new_trace_id()
    log_event("demo", trace_id, workspace_root=str(tmp_path), hello="world")
    events = load_audit_events(str(tmp_path), trace_id)
    assert len(events) == 1
    assert events[0]["event"] == "demo"
    assert events[0]["hello"] == "world"
