from src.config.settings import load_settings
from src.tools.test_runner import run_test_command


def test_load_settings_default_profile(monkeypatch):
    monkeypatch.delenv("APP_PROFILE", raising=False)
    settings = load_settings()
    assert settings.profile == "local"
    assert settings.model
    assert settings.base_url.startswith("http")


def test_load_settings_env_override(monkeypatch):
    monkeypatch.setenv("APP_PROFILE", "dev")
    monkeypatch.setenv("OLLAMA_TIMEOUT", "33")
    settings = load_settings()
    assert settings.profile == "dev"
    assert settings.timeout == 33


def test_run_test_command_blocks_disallowed_binary():
    result = run_test_command("bash -lc 'echo hi'")
    assert result["success"] is False
    assert "Blocked command" in result["stderr"]
