from src.config.capabilities import load_capabilities


def test_load_capabilities_contains_core_flags():
    capabilities = load_capabilities()
    assert capabilities["generate_code"] is True
    assert capabilities["edit_file"] is True
    assert "structured_actions" in capabilities
