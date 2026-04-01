from src.tools.prompt_lab import PromptLab


def test_record_and_summarize(tmp_path):
    lab = PromptLab(str(tmp_path))

    lab.record_run("write test", "baseline", True, 120)
    lab.record_run("fix bug", "baseline", False, 150)
    lab.record_run("write test", "structured", True, 180)

    summary = lab.summarize()
    assert summary["total_runs"] == 3
    assert "baseline" in summary["by_strategy"]
    assert summary["overall_success_rate"] > 0


def test_recommend_strategy(tmp_path):
    lab = PromptLab(str(tmp_path))
    lab.record_run("task", "baseline", False, 100)
    lab.record_run("task", "chain_of_thought", True, 140)

    recommendation = lab.recommend_strategy("test this")
    assert recommendation["strategy"] in {"chain_of_thought", "baseline"}
    assert "reason" in recommendation
