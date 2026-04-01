from src.tools.incident_automation import build_incident_timeline, generate_incident_report
from src.tools.logger import log_event


def test_incident_timeline_and_report(tmp_path):
    log_event("autofix_start", "trace77", workspace_root=str(tmp_path), target_path="src/main.py")
    log_event("autofix_attempt", "trace77", workspace_root=str(tmp_path), attempt=1)

    timeline = build_incident_timeline(str(tmp_path), "trace77")
    assert len(timeline) == 2
    assert timeline[0]["event"] == "autofix_start"

    out = generate_incident_report(str(tmp_path), "trace77")
    assert out.endswith("incident_trace77.md")
