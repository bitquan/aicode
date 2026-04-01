from src.tools.prompt_optimizer import choose_prompt_strategy, record_prompt_outcome


def test_prompt_optimizer_prefers_better_strategy(tmp_path):
    record_prompt_outcome(str(tmp_path), "concise", True)
    record_prompt_outcome(str(tmp_path), "concise", True)
    record_prompt_outcome(str(tmp_path), "verbose", False)

    selected = choose_prompt_strategy(str(tmp_path), ["concise", "verbose"], "concise")
    assert selected == "concise"
