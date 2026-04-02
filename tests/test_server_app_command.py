"""Tests for /v1/aicode/command endpoint."""

from fastapi.testclient import TestClient

import src.server as server


def test_app_command_endpoint_returns_structured_payload(monkeypatch):
    class DummyService:
        def run_command(self, command: str):
            return {
                "command": command,
                "action": "status",
                "confidence": 0.9,
                "response": "ok",
                "next_step": "If you want, I can run a full status validation next.",
                "route_attempts": ["status"],
                "recovered_from_action": None,
                "run_id": None,
                "mode": None,
                "state": None,
                "goal": None,
                "candidate_summary": None,
                "pinned_files": [],
                "approved_files": [],
                "likely_files": [],
                "verification_plan": [],
                "web_research_used": None,
                "needs_external_research": False,
                "research_trigger_reason": None,
                "rollback_performed": None,
            }

    monkeypatch.setattr(server, "_app_service", DummyService())
    client = TestClient(server.app)

    response = client.post("/v1/aicode/command", json={"command": "status"})
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "status"
    assert data["response"] == "ok"
    assert data["next_step"] == "If you want, I can run a full status validation next."
    assert data["route_attempts"] == ["status"]
    assert data["needs_external_research"] is False
    assert data["research_trigger_reason"] is None


def test_app_command_endpoint_returns_self_improve_fields(monkeypatch):
    class DummyService:
        def run_command(self, command: str):
            return {
                "command": command,
                "action": "self_improve_plan",
                "confidence": 0.96,
                "response": "plan ready",
                "next_step": "If you want, I can verify this plan with readiness checks next.",
                "route_attempts": ["self_improve_plan"],
                "recovered_from_action": None,
                "run_id": "sir_123",
                "mode": "supervised",
                "state": "proposed",
                "goal": "add a clear chat button",
                "candidate_summary": "User-requested improvement",
                "pinned_files": ["vscode-extension/src/extension.ts"],
                "approved_files": ["vscode-extension/src/extension.ts"],
                "likely_files": ["vscode-extension/src/extension.ts"],
                "verification_plan": ["npm --prefix vscode-extension run compile"],
                "web_research_used": False,
                "needs_external_research": True,
                "research_trigger_reason": "low_confidence_unknown",
                "rollback_performed": False,
            }

    monkeypatch.setattr(server, "_app_service", DummyService())
    client = TestClient(server.app)

    response = client.post("/v1/aicode/command", json={"command": "self-improve plan add a clear chat button"})
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "sir_123"
    assert data["state"] == "proposed"
    assert data["next_step"] == "If you want, I can verify this plan with readiness checks next."
    assert data["pinned_files"] == ["vscode-extension/src/extension.ts"]
    assert data["approved_files"] == ["vscode-extension/src/extension.ts"]
    assert data["likely_files"] == ["vscode-extension/src/extension.ts"]
    assert data["needs_external_research"] is True
    assert data["research_trigger_reason"] == "low_confidence_unknown"


def test_app_command_endpoint_rejects_empty_command():
    client = TestClient(server.app)
    response = client.post("/v1/aicode/command", json={"command": "   "})
    assert response.status_code == 400
