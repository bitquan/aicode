from src.agents.coding_agent import CodingAgent


def test_run_mode_uses_model_output(monkeypatch):
    agent = CodingAgent()

    monkeypatch.setattr(agent, "_call_ollama", lambda prompt: "mode output")
    out = agent.run_mode("explain", "why this fails")
    assert out == "mode output"
