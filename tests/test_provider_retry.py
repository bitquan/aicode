import pytest
import requests

from src.providers.ollama_provider import OllamaProvider


class DummyResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"response": "ok"}


def test_provider_retries_then_succeeds(monkeypatch):
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 2:
            raise requests.RequestException("temporary")
        return DummyResponse()

    monkeypatch.setattr("src.providers.ollama_provider.requests.post", fake_post)
    monkeypatch.setattr("src.providers.ollama_provider.time.sleep", lambda *_: None)

    provider = OllamaProvider("m", "http://x", timeout=1, max_retries=2, retry_backoff_seconds=0)
    out = provider.generate("hi", "sys")
    assert out == "ok"
    assert calls["count"] == 2


def test_provider_raises_after_retries(monkeypatch):
    def fake_post(*args, **kwargs):
        raise requests.RequestException("down")

    monkeypatch.setattr("src.providers.ollama_provider.requests.post", fake_post)
    monkeypatch.setattr("src.providers.ollama_provider.time.sleep", lambda *_: None)

    provider = OllamaProvider("m", "http://x", timeout=1, max_retries=1, retry_backoff_seconds=0)
    with pytest.raises(RuntimeError):
        provider.generate("hi", "sys")
