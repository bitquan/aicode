from src.tools.repair_strategy import choose_repair_strategy


def test_choose_repair_strategy_known():
    strategy = choose_repair_strategy("syntax")
    assert strategy["strategy"] == "syntax_patch"


def test_choose_repair_strategy_unknown():
    strategy = choose_repair_strategy("weird")
    assert strategy["strategy"] == "generic_patch"
