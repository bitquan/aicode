from pathlib import Path

from src.prompts.layers import build_layered_prompt, load_prompt_layers


def test_build_layered_prompt_contains_sections():
    layers = {"system": "s", "developer": "d", "tool": "t"}
    out = build_layered_prompt("u", layers, context="c")
    assert "[SYSTEM]" in out
    assert "[DEVELOPER]" in out
    assert "[TOOLS]" in out
    assert "[CONTEXT]" in out
    assert "[USER]" in out


def test_load_prompt_layers_reads_optional(tmp_path):
    (tmp_path / "system_prompt.txt").write_text("sys", encoding="utf-8")
    layers = load_prompt_layers(Path(tmp_path))
    assert layers["system"] == "sys"
    assert layers["developer"] == ""
