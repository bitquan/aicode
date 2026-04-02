"""Tests for decision-timeline CLI command in src.main."""

from unittest.mock import patch

from src import main


def test_main_decision_timeline_command_prints_payload(capsys):
    fake_payload = {"sample_size": 1, "summary": {"reroute_rate": 0.0}, "timeline": []}
    with patch("src.main.build_decision_timeline", return_value=fake_payload):
        with patch("sys.argv", ["python", "decision-timeline", "--limit", "25"]):
            main.main()

    output = capsys.readouterr().out
    assert "sample_size" in output
    assert "reroute_rate" in output
