from datetime import datetime, UTC, timedelta
import os

from src.tools.dependency_inventory import read_dependency_inventory
from src.tools.retention import cleanup_reports


def test_dependency_inventory_reads_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.poetry]
name = "demo"

[tool.poetry.dependencies]
python = "^3.11"
requests = "^2"

[tool.poetry.group.dev.dependencies]
pytest = "^8"
""".strip(),
        encoding="utf-8",
    )
    out = read_dependency_inventory(str(tmp_path))
    assert "requests" in out["dependencies"]
    assert "pytest" in out["dev_dependencies"]


def test_retention_cleanup_deletes_old_files(tmp_path):
    old_file = tmp_path / ".autofix_reports" / "audit" / "old.jsonl"
    old_file.parent.mkdir(parents=True, exist_ok=True)
    old_file.write_text("{}\n", encoding="utf-8")

    old_ts = (datetime.now(UTC) - timedelta(days=30)).timestamp()
    os.utime(old_file, (old_ts, old_ts))

    result = cleanup_reports(str(tmp_path), older_than_days=14)
    assert result["deleted"] == 1
    assert not old_file.exists()
