from src.tools.symbol_index import build_symbol_index


def test_build_symbol_index_detects_class_and_function(tmp_path):
    code = "class A:\n    pass\n\ndef f():\n    return 1\n"
    (tmp_path / "x.py").write_text(code, encoding="utf-8")
    symbols = build_symbol_index(str(tmp_path))
    names = {(row["kind"], row["name"]) for row in symbols}
    assert ("class", "A") in names
    assert ("function", "f") in names
