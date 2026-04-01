from unittest.mock import patch

from src.agents.coding_agent import CodingAgent


def test_generate_code_uses_ollama_response():
    agent = CodingAgent()
    with patch.object(agent, "_call_ollama", return_value="def add(a, b):\n    return a + b"):
        result = agent.generate_code("write add function")
    assert "def add" in result


def test_generate_code_strips_markdown_fence():
    agent = CodingAgent()
    fenced = "```python\ndef add(a, b):\n    return a + b\n```"
    with patch.object(agent, "_call_ollama", return_value=fenced):
        result = agent.generate_code("write add function")
    assert result.startswith("def add")
    assert "```" not in result


def test_evaluate_code_valid_script():
    agent = CodingAgent()
    code = "print(2 + 3)"
    result = agent.evaluate_code(code)
    assert result["syntax_ok"] is True
    assert result["execution_ok"] is True
    assert "5" in result["stdout"]


def test_evaluate_code_syntax_error():
    agent = CodingAgent()
    code = "def broken(:\n    pass"
    result = agent.evaluate_code(code)
    assert result["syntax_ok"] is False
    assert result["execution_ok"] is False


def test_plan_action_parses_structured_output():
    agent = CodingAgent()
    raw = '{"action":"edit_file","target_path":"src/main.py","instruction":"Add argparse"}'
    with patch.object(agent, "_call_ollama", return_value=raw):
        action = agent.plan_action("add argparse")
    assert action.action.value == "edit_file"
    assert action.target_path == "src/main.py"