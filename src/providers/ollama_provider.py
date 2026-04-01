import requests
import time
from typing import Any

from src.providers.base import ModelProvider


class OllamaProvider(ModelProvider):
    def __init__(self, model: str, base_url: str, timeout: int = 60, max_retries: int = 2, retry_backoff_seconds: float = 1.0):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        full_prompt = f"{system_prompt}\n\nUser request:\n{prompt}" if system_prompt else prompt
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": full_prompt,
                        "stream": False,
                        "options": {"temperature": 0.2},
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                return response.json().get("response", "").strip()
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.max_retries:
                    sleep_seconds = self.retry_backoff_seconds * (2 ** attempt)
                    time.sleep(sleep_seconds)

        raise RuntimeError(f"Ollama request failed after retries: {last_error}")

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> Any:
        """Send a chat request to Ollama /api/chat.

        Returns the full response dict when *stream* is False.
        Returns a streaming ``requests.Response`` (caller iterates
        ``.iter_lines()``) when *stream* is True.
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {"temperature": 0.2},
        }
        if tools:
            payload["tools"] = tools

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=self.timeout,
                    stream=stream,
                )
                response.raise_for_status()
                if stream:
                    return response  # caller iterates .iter_lines()
                return response.json()
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.max_retries:
                    sleep_seconds = self.retry_backoff_seconds * (2 ** attempt)
                    time.sleep(sleep_seconds)

        raise RuntimeError(f"Ollama chat request failed after retries: {last_error}")
