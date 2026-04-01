from src.types.actions import AgentAction, ActionType


def test_agent_action_from_json_block():
    raw = """```json
{\"action\":\"edit_file\",\"target_path\":\"src/main.py\",\"instruction\":\"Add argparse\"}
```"""
    action = AgentAction.from_model_output(raw)
    assert action.action == ActionType.EDIT_FILE
    assert action.target_path == "src/main.py"
    assert "argparse" in action.instruction
