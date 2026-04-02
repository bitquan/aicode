"""Tests for self-improvement readiness canary suite."""

from unittest.mock import MagicMock

from src.tools.commanding import ActionRequest, ActionResponse
from src.tools.readiness_suite import run_engine_readiness_suite


def test_run_engine_readiness_suite_reports_pass(monkeypatch):
    engine = MagicMock()
    engine.get_self_awareness_snapshot.return_value = {
        "server": {"reachable": True},
        "ollama": {"reachable": True},
        "web": {"enabled": True},
        "known_surfaces": {"vscode_panel": "vscode-extension/src/extension.ts"},
    }
    prompts = [
        {
            "name": "feature",
            "prompt": "Add a Clear Chat button to the VS Code panel",
            "expected_action": "research",
            "response_must_include": ["vscode-extension/src/extension.ts"],
        }
    ]
    monkeypatch.setattr("src.tools.readiness_suite.load_readiness_canaries", lambda config_path=None: prompts)
    monkeypatch.setattr(
        "src.tools.readiness_suite.load_runtime_manifest",
        lambda config_path=None: {"routing_generation": 3, "readiness_suite_version": 1},
    )
    engine.parse_request_model.return_value = ActionRequest(
        action="research",
        confidence=0.9,
        raw_input="Add a Clear Chat button to the VS Code panel",
        params={"goal": "Add a Clear Chat button to the VS Code panel"},
    )
    engine.execute_request.return_value = ActionResponse(
        action="research",
        text="🔎 Research Summary\n  • VS Code panel source: vscode-extension/src/extension.ts",
        confidence=0.9,
        result_status="success",
    )

    report = run_engine_readiness_suite(engine)

    assert report["status"] == "pass"
    assert report["passed"] == 1
    assert report["known_vscode_panel"] == "vscode-extension/src/extension.ts"


def test_run_engine_readiness_suite_reports_failures(monkeypatch):
    engine = MagicMock()
    engine.get_self_awareness_snapshot.return_value = {
        "server": {"reachable": False},
        "ollama": {"reachable": False},
        "web": {"enabled": True},
        "known_surfaces": {"vscode_panel": "vscode-extension/src/extension.ts"},
    }
    prompts = [
        {
            "name": "feature",
            "prompt": "Add a Clear Chat button to the VS Code panel",
            "expected_action": "research",
            "response_must_include": ["vscode-extension/src/extension.ts"],
        }
    ]
    monkeypatch.setattr("src.tools.readiness_suite.load_readiness_canaries", lambda config_path=None: prompts)
    monkeypatch.setattr(
        "src.tools.readiness_suite.load_runtime_manifest",
        lambda config_path=None: {"routing_generation": 3, "readiness_suite_version": 1},
    )
    engine.parse_request_model.return_value = ActionRequest(
        action="edit",
        confidence=0.85,
        raw_input="Add a Clear Chat button to the VS Code panel",
        params={"target": "the VS Code panel"},
    )
    engine.execute_request.return_value = ActionResponse(
        action="edit",
        text="❌ File not found: the VS Code panel",
        confidence=0.85,
        result_status="failure",
    )

    report = run_engine_readiness_suite(engine)

    assert report["status"] == "fail"
    assert report["failed"] == 1
    assert report["results"][0]["actual_action"] == "edit"
