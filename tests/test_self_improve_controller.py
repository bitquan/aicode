"""Tests for the supervised self-improvement closed loop."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from src.tools.self_improve import (
    apply_self_improvement_run,
    build_self_improvement_status_snapshot,
    create_self_improvement_plan,
)


def _engine(tmp_path):
    builder = MagicMock()
    builder.patterns = {"analysis": {"success_rate": 1.0, "failed_patterns": []}}
    agent = MagicMock()
    return SimpleNamespace(
        workspace_root=tmp_path,
        self_builder=builder,
        agent=agent,
    )


def test_create_self_improvement_plan_from_explicit_goal(monkeypatch, tmp_path):
    engine = _engine(tmp_path)
    monkeypatch.setattr(
        "src.tools.self_improve.build_research_payload",
        lambda engine, goal, prefer_web=False: {
            "goal": goal,
            "likely_files": [{"path": "vscode-extension/src/extension.ts", "reason": "VS Code panel", "score": 9}],
            "verification_plan": ["npm --prefix vscode-extension run compile", "Run readiness canaries"],
            "verification_plan_steps": [
                {"kind": "command", "label": "targeted", "command": "npm --prefix vscode-extension run compile"},
                {"kind": "readiness", "label": "readiness", "command": "GET /v1/aicode/readiness"},
            ],
            "web": {"enabled": True},
            "web_research_used": False,
        },
    )

    run = create_self_improvement_plan(
        str(tmp_path),
        engine,
        goal="add a clear chat button to the VS Code panel",
    )

    assert run["state"] == "proposed"
    assert run["goal"] == "add a clear chat button to the VS Code panel"
    assert run["candidate"]["category"] == "explicit_goal"
    assert run["likely_files"][0]["path"] == "vscode-extension/src/extension.ts"
    assert run["verification_plan"][-1] == "Run readiness canaries"
    assert build_self_improvement_status_snapshot(str(tmp_path))["latest_run_id"] == run["run_id"]


def test_create_self_improvement_plan_uses_failing_canary_when_no_goal(monkeypatch, tmp_path):
    engine = _engine(tmp_path)
    monkeypatch.setattr(
        "src.tools.self_improve.run_engine_readiness_suite",
        lambda engine: {
            "status": "fail",
            "failed": 1,
            "results": [
                {
                    "name": "feature_request_routes_to_research",
                    "prompt": "Add a Clear Chat button to the VS Code panel",
                    "expected_action": "research",
                    "passed": False,
                }
            ],
        },
    )
    monkeypatch.setattr(
        "src.tools.self_improve.build_research_payload",
        lambda engine, goal, prefer_web=False: {
            "goal": goal,
            "likely_files": [{"path": "vscode-extension/src/extension.ts", "reason": "VS Code panel", "score": 9}],
            "verification_plan": ["npm --prefix vscode-extension run compile"],
            "verification_plan_steps": [{"kind": "command", "label": "targeted", "command": "npm --prefix vscode-extension run compile"}],
            "web": {"enabled": True},
            "web_research_used": False,
        },
    )

    run = create_self_improvement_plan(str(tmp_path), engine)

    assert run["candidate"]["category"] == "readiness_canary"
    assert run["goal"] == "Add a Clear Chat button to the VS Code panel"


def test_apply_self_improvement_blocks_dirty_targets(monkeypatch, tmp_path):
    target = tmp_path / "src" / "app_service.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("print('old')\n", encoding="utf-8")
    engine = _engine(tmp_path)
    monkeypatch.setattr(
        "src.tools.self_improve.build_research_payload",
        lambda engine, goal, prefer_web=False: {
            "goal": goal,
            "likely_files": [{"path": "src/app_service.py", "reason": "App service", "score": 8}],
            "verification_plan": ["./.venv/bin/python -m pytest -q tests/test_app_service.py"],
            "verification_plan_steps": [
                {
                    "kind": "command",
                    "label": "targeted",
                    "command": "./.venv/bin/python -m pytest -q tests/test_app_service.py",
                }
            ],
            "web": {"enabled": True},
            "web_research_used": False,
        },
    )
    monkeypatch.setattr(
        "src.tools.self_improve.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout=" M src/app_service.py\n"),
    )

    run = create_self_improvement_plan(str(tmp_path), engine, goal="improve app service")
    applied = apply_self_improvement_run(str(tmp_path), engine, run["run_id"])

    assert applied["state"] == "approved"
    assert "Dirty target files" in str(applied["blocked_reason"])
    engine.agent.rewrite_file.assert_not_called()


def test_apply_self_improvement_rolls_back_on_verification_failure(monkeypatch, tmp_path):
    target = tmp_path / "src" / "app_service.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    original = "print('old')\n"
    target.write_text(original, encoding="utf-8")
    engine = _engine(tmp_path)
    engine.agent.rewrite_file.return_value = "print('new')\n"

    monkeypatch.setattr(
        "src.tools.self_improve.build_research_payload",
        lambda engine, goal, prefer_web=False: {
            "goal": goal,
            "likely_files": [{"path": "src/app_service.py", "reason": "App service", "score": 8}],
            "verification_plan": ["./.venv/bin/python -m pytest -q tests/test_app_service.py", "Run readiness canaries"],
            "verification_plan_steps": [
                {
                    "kind": "command",
                    "label": "targeted",
                    "command": "./.venv/bin/python -m pytest -q tests/test_app_service.py",
                },
                {"kind": "readiness", "label": "readiness", "command": "GET /v1/aicode/readiness"},
            ],
            "web": {"enabled": True},
            "web_research_used": False,
        },
    )
    monkeypatch.setattr(
        "src.tools.self_improve.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout=""),
    )
    monkeypatch.setattr(
        "src.tools.self_improve.run_test_command",
        lambda command, timeout=600, cwd=None: {
            "success": False,
            "returncode": 1,
            "stdout": "",
            "stderr": "boom",
        },
    )

    run = create_self_improvement_plan(str(tmp_path), engine, goal="improve app service")
    applied = apply_self_improvement_run(str(tmp_path), engine, run["run_id"])

    assert applied["state"] == "rolled_back"
    assert applied["rollback_performed"] is True
    assert target.read_text(encoding="utf-8") == original
