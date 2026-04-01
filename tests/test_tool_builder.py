from src.tools.tool_builder import ToolBuilder


def test_create_tool_scaffold(tmp_path):
    (tmp_path / "src" / "tools").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)

    builder = ToolBuilder(str(tmp_path))
    result = builder.create_tool("cache helper", "Cache helper tool")

    assert result["status"] == "created"
    assert (tmp_path / result["tool"]).exists()
    assert (tmp_path / result["test"]).exists()


def test_create_tool_reject_duplicate(tmp_path):
    (tmp_path / "src" / "tools").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)

    builder = ToolBuilder(str(tmp_path))
    first = builder.create_tool("my_tool", "desc")
    second = builder.create_tool("my_tool", "desc")

    assert first["status"] == "created"
    assert "error" in second
