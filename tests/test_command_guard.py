from src.tools.command_guard import validate_command


def test_validate_command_allows_pytest():
    out = validate_command("python -m pytest -q")
    assert out["allowed"] is True


def test_validate_command_blocks_dangerous():
    out = validate_command("python -m pytest -q && rm -rf /")
    assert out["allowed"] is False
