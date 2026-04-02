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
                "route_attempts": ["status"],
                "recovered_from_action": None,
                "run_id": None,
                "mode": None,
                "state": None,
                "goal": None,
                "candidate_summary": None,
                "likely_files": [],
                "verification_plan": [],
                "web_research_used": None,
                "rollback_performed": None,
            }

    monkeypatch.setattr(server, "_app_service", DummyService())
    client = TestClient(server.app)

    response = client.post("/v1/aicode/command", json={"command": "status"})
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "status"
    assert data["response"] == "ok"
    assert data["route_attempts"] == ["status"]


def test_app_command_endpoint_returns_self_improve_fields(monkeypatch):
    class DummyService:
        def run_command(self, command: str):
            return {
                "command": command,
                "action": "self_improve_plan",
                "confidence": 0.96,
                "response": "plan ready",
                "route_attempts": ["self_improve_plan"],
                "recovered_from_action": None,
                "run_id": "sir_123",
                "mode": "supervised",
                "state": "proposed",
                "goal": "add a clear chat button",
                "candidate_summary": "User-requested improvement",
                "likely_files": ["vscode-extension/src/extension.ts"],
                "verification_plan": ["npm --prefix vscode-extension run compile"],
                "web_research_used": False,
                "rollback_performed": False,
            }

    monkeypatch.setattr(server, "_app_service", DummyService())
    client = TestClient(server.app)

    response = client.post("/v1/aicode/command", json={"command": "self-improve plan add a clear chat button"})
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "sir_123"
    assert data["state"] == "proposed"
    assert data["likely_files"] == ["vscode-extension/src/extension.ts"]


def test_app_command_endpoint_rejects_empty_command():
    client = TestClient(server.app)
    response = client.post("/v1/aicode/command", json={"command": "   "})
    assert response.status_code == 400
