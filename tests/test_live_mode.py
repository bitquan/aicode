from src.tools.learning_events import record_prompt_event
from src.tools.live_mode import (
    load_live_mode_state,
    run_live_learning_cycle,
    run_live_mode,
    unlock_slice,
)


def test_live_mode_default_state(tmp_path):
    state = load_live_mode_state(str(tmp_path))
    assert state["mode"] == "learning_only"
    assert state["points"] == 0
    assert "learn" in state["unlocked_slices"]


def test_live_learning_cycle_processes_prompt_events(tmp_path):
    workspace = str(tmp_path)
    record_prompt_event(
        workspace_root=workspace,
        raw_prompt="learn: prefer short test runs first",
        intent="user_learn",
        confidence=0.95,
        action_taken="user_learn",
        result_status="success",
        source="cli",
    )

    result = run_live_learning_cycle(workspace)
    assert result["events_observed"] >= 1
    assert result["new_events_observed"] >= 1
    assert result["logs_used"] >= 1
    assert result["learned"] is True
    assert result["points_earned"] == 1
    assert "learn" in result["slices_executed"]


def test_live_mode_unlock_slice_manual(tmp_path):
    workspace = str(tmp_path)
    result = unlock_slice(workspace, "research")
    assert result["updated"] is True
    assert "research" in result["state"]["unlocked_slices"]


def test_live_mode_runs_bounded_iterations(tmp_path):
    workspace = str(tmp_path)
    summary = run_live_mode(workspace, interval_seconds=1, iterations=2, allow_unlocked_slices=False)
    assert summary["iterations_run"] == 2
    assert summary["final_state"]["cycles"] >= 2
    assert summary["final_state"]["enabled"] is False


def test_live_mode_does_not_award_points_without_new_events(tmp_path, monkeypatch):
    workspace = str(tmp_path)
    monkeypatch.setattr("src.tools.live_mode.time.sleep", lambda _: None)

    summary = run_live_mode(workspace, interval_seconds=1, iterations=2, allow_unlocked_slices=False)

    assert summary["iterations_run"] == 2
    assert summary["final_state"]["points"] == 0
    assert summary["history"][0]["points_earned"] == 0
    assert summary["history"][1]["points_earned"] == 0


def test_live_mode_only_counts_prompt_event_once(tmp_path, monkeypatch):
    workspace = str(tmp_path)
    monkeypatch.setattr("src.tools.live_mode.time.sleep", lambda _: None)
    record_prompt_event(
        workspace_root=workspace,
        raw_prompt="learn: prefer repo-first answers",
        intent="user_learn",
        confidence=0.95,
        action_taken="user_learn",
        result_status="success",
        source="cli",
    )

    summary = run_live_mode(workspace, interval_seconds=1, iterations=2, allow_unlocked_slices=False)

    assert summary["final_state"]["points"] == 1
    assert summary["history"][0]["points_earned"] == 1
    assert summary["history"][1]["points_earned"] == 0
    assert summary["history"][1]["new_events_observed"] == 0
