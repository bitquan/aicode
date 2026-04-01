from src.tools.self_improve import run_self_improvement_cycles


def test_self_improve_converges_when_score_high(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "src.tools.self_improve.build_status_report",
        lambda workspace_root: {
            "readiness": "release_candidate",
            "roadmap": {"remaining": []},
            "benchmark": {"score": 100.0, "checks": []},
            "budgets": {"passed": True},
            "compliance": {"license_scan_passed": True, "playbooks_ready": True},
        },
    )
    monkeypatch.setattr("src.tools.self_improve.remember_note", lambda *args, **kwargs: kwargs)

    out = run_self_improvement_cycles(str(tmp_path), cycles=3, target_score=95.0)
    assert out["converged"] is True
    assert out["cycles_run"] == 1


def test_self_improve_suggests_actions_on_failures(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "src.tools.self_improve.build_status_report",
        lambda workspace_root: {
            "readiness": "in_progress",
            "roadmap": {"remaining": [40, 46]},
            "benchmark": {"score": 70.0, "checks": [{"name": "regression_gate", "passed": False}]},
            "budgets": {"passed": False},
            "compliance": {"license_scan_passed": False, "playbooks_ready": False},
        },
    )
    monkeypatch.setattr("src.tools.self_improve.remember_note", lambda *args, **kwargs: kwargs)

    out = run_self_improvement_cycles(str(tmp_path), cycles=1, target_score=95.0)
    assert out["converged"] is False
    actions = out["results"][0]["actions"]
    assert any("roadmap" in item.lower() for item in actions)
    assert any("license" in item.lower() for item in actions)
