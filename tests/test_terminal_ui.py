from src.ui.terminal_ui import parse_tui_command


def test_parse_tui_command_empty():
    command, args = parse_tui_command("")
    assert command == ""
    assert args == []


def test_parse_tui_command_with_quotes():
    command, args = parse_tui_command('edit src/main.py "add argparse support"')
    assert command == "edit"
    assert args[0] == "src/main.py"
    assert args[1] == "add argparse support"
