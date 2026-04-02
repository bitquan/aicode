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
            }

    monkeypatch.setattr(server, "_app_service", DummyService())
    client = TestClient(server.app)

    response = client.post("/v1/aicode/command", json={"command": "status"})
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "status"
    assert data["response"] == "ok"
    assert data["route_attempts"] == ["status"]


def test_app_command_endpoint_rejects_empty_command():
    client = TestClient(server.app)
    response = client.post("/v1/aicode/command", json={"command": "   "})
    assert response.status_code == 400
