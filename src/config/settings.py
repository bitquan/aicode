from dataclasses import dataclass
from pathlib import Path
import json
import os


@dataclass
class AppSettings:
    profile: str
    model: str
    base_url: str
    timeout: int
    max_retries: int
    retry_backoff_seconds: float


def load_settings(profile: str | None = None) -> AppSettings:
    active_profile = profile or os.getenv("APP_PROFILE", "local")
    profile_path = Path(__file__).with_name("profiles.json")
    profiles = json.loads(profile_path.read_text(encoding="utf-8"))
    data = profiles.get(active_profile, profiles["local"]) 

    model = os.getenv("OLLAMA_MODEL", data["model"])
    base_url = os.getenv("OLLAMA_BASE_URL", data["base_url"])
    timeout = int(os.getenv("OLLAMA_TIMEOUT", str(data["timeout"])))
    max_retries = int(os.getenv("OLLAMA_MAX_RETRIES", str(data["max_retries"])))
    retry_backoff_seconds = float(os.getenv("OLLAMA_RETRY_BACKOFF", str(data["retry_backoff_seconds"])))

    return AppSettings(
        profile=active_profile,
        model=model,
        base_url=base_url,
        timeout=timeout,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
    )
