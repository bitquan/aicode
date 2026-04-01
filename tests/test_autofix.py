from src.tools.autofix import run_autofix_loop


class StubAgent:
    def __init__(self, outputs):
        self.outputs = outputs
        self.index = 0

    def rewrite_file(self, file_path, instruction, current_content):
        out = self.outputs[self.index]
        if self.index < len(self.outputs) - 1:
            self.index += 1
        return out


def test_autofix_succeeds_after_retry(tmp_path, monkeypatch):
    target = tmp_path / "demo.py"
    target.write_text("x = 1\n", encoding="utf-8")

    agent = StubAgent(["x = 2\n", "x = 3\n"])

    results = [
        {"success": False, "stdout": "", "stderr": "fail", "returncode": 1, "timed_out": False},
        {"success": True, "stdout": "", "stderr": "", "returncode": 0, "timed_out": False},
    ]

    def fake_run_test_command(command):
        return results.pop(0)

    monkeypatch.setattr("src.tools.autofix.run_test_command", fake_run_test_command)

    outcome = run_autofix_loop(
        agent=agent,
        workspace_root=str(tmp_path),
        target_path="demo.py",
        instruction="set x",
        max_attempts=3,
    )

    assert outcome["success"] is True
    assert outcome["rolled_back"] is False
    assert outcome["trace_id"]
    assert outcome["audit_log"].endswith(".jsonl")
    assert outcome["test_command"]
    assert outcome["blocker_report"] is None
    assert outcome["minimal_repro"] is None
    assert outcome["confidence"] > 0
    assert outcome["planned_files"]
    assert len(outcome["attempts"]) == 2
    assert outcome["attempts"][0]["failure"]["category"] == "unknown"
    assert outcome["attempts"][0]["strategy"]["strategy"] == "generic_patch"
    assert target.read_text(encoding="utf-8") == "x = 3\n"


def test_autofix_rolls_back_after_exhausted_attempts(tmp_path, monkeypatch):
    target = tmp_path / "demo.py"
    target.write_text("x = 1\n", encoding="utf-8")

    agent = StubAgent(["x = 99\n"])

    def fake_run_test_command(command):
        return {"success": False, "stdout": "", "stderr": "fail", "returncode": 1, "timed_out": False}

    monkeypatch.setattr("src.tools.autofix.run_test_command", fake_run_test_command)

    outcome = run_autofix_loop(
        agent=agent,
        workspace_root=str(tmp_path),
        target_path="demo.py",
        instruction="set x",
        max_attempts=2,
    )

    assert outcome["success"] is False
    assert outcome["rolled_back"] is True
    assert outcome["blocker_report"] is not None
    assert outcome["minimal_repro"].endswith("_repro.md")
    assert outcome["confidence"] > 0
    assert "path" in outcome["blocker_report"]
    assert outcome["attempts"][0]["failure"]["category"] == "unknown"
    assert target.read_text(encoding="utf-8") == "x = 1\n"


def test_autofix_circuit_breaker_stops_early(tmp_path, monkeypatch):
    target = tmp_path / "demo.py"
    target.write_text("x = 1\n", encoding="utf-8")

    agent = StubAgent(["x = 2\n", "x = 3\n", "x = 4\n"])

    def fake_run_test_command(command):
        return {"success": False, "stdout": "", "stderr": "SyntaxError: bad", "returncode": 1, "timed_out": False}

    monkeypatch.setattr("src.tools.autofix.run_test_command", fake_run_test_command)

    outcome = run_autofix_loop(
        agent=agent,
        workspace_root=str(tmp_path),
        target_path="demo.py",
        instruction="set x",
        max_attempts=5,
        circuit_breaker_repeats=2,
    )

    assert outcome["success"] is False
    assert "Circuit breaker" in outcome["reason"]
    assert len(outcome["attempts"]) == 2


def test_autofix_flaky_confirm_can_succeed(tmp_path, monkeypatch):
    target = tmp_path / "demo.py"
    target.write_text("x = 1\n", encoding="utf-8")

    agent = StubAgent(["x = 2\n"])
    results = [
        {"success": False, "stdout": "flaky rerun happened", "stderr": "", "returncode": 1, "timed_out": False},
        {"success": True, "stdout": "", "stderr": "", "returncode": 0, "timed_out": False},
    ]

    def fake_run_test_command(command):
        return results.pop(0)

    monkeypatch.setattr("src.tools.autofix.run_test_command", fake_run_test_command)

    outcome = run_autofix_loop(
        agent=agent,
        workspace_root=str(tmp_path),
        target_path="demo.py",
        instruction="set x",
        max_attempts=2,
        confirm_flaky=True,
    )

    assert outcome["success"] is True
