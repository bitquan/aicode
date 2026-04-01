"""Tests for learning metrics HTTP endpoint."""

from fastapi.testclient import TestClient

import src.server as server


def test_learning_metrics_endpoint_returns_payload():
    client = TestClient(server.app)
    response = client.get("/metrics/learning")
    assert response.status_code == 200
    data = response.json()
    assert "routing_accuracy" in data
    assert "preference_hit_rate" in data
    assert "correction_success_rate" in data
