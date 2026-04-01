"""Tests for AuditTrail."""

from src.tools.audit_trail import AuditTrail


def test_log_and_entries(tmp_path):
    audit = AuditTrail(str(tmp_path))
    audit.log_action(action="edit", actor="alice", target="src/main.py", allowed=True)
    rows = audit.entries()
    assert rows["count"] == 1
    assert rows["entries"][0]["action"] == "edit"


def test_filter_by_actor(tmp_path):
    audit = AuditTrail(str(tmp_path))
    audit.log_action(action="edit", actor="alice")
    audit.log_action(action="review", actor="bob")
    rows = audit.entries(actor="alice")
    assert rows["count"] == 1
    assert rows["entries"][0]["actor"] == "alice"


def test_compliance_summary_review_status(tmp_path):
    audit = AuditTrail(str(tmp_path))
    audit.log_action(action="deploy", actor="release", allowed=False)
    summary = audit.compliance_summary()
    assert summary["denied_events"] == 1
    assert summary["status"] == "REVIEW"


def test_compliance_summary_ok_status(tmp_path):
    audit = AuditTrail(str(tmp_path))
    audit.log_action(action="search", actor="dev", allowed=True)
    summary = audit.compliance_summary()
    assert summary["status"] == "OK"
