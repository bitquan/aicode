from src.config.capabilities import load_capabilities


def test_load_capabilities_contains_core_flags():
    capabilities = load_capabilities()
    assert capabilities["generate_code"] is True
    assert capabilities["edit_file"] is True
    assert "structured_actions" in capabilities
    assert capabilities["debug_mode"] is True
    assert capabilities["notebook_mode"] is True
    assert capabilities["shared_command_registry"] is True
    assert capabilities["web_fetch"] is True
    assert capabilities["web_policy"]["mode"] == "optional"
