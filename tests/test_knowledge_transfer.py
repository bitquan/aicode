import json
from pathlib import Path

from src.tools.knowledge_transfer import KnowledgeTransfer


def test_export_and_list(tmp_path):
    kb = tmp_path / ".knowledge_base"
    kb.mkdir()
    (kb / "metrics.json").write_text(json.dumps({"success_rate": 0.8}))
    (kb / "patterns.json").write_text(json.dumps({"count": 2}))

    transfer = KnowledgeTransfer(str(tmp_path))
    listed = transfer.list_knowledge_files()
    assert listed["count"] == 2

    exported = transfer.export_bundle("bundle.json")
    assert exported["status"] == "exported"
    assert (tmp_path / "bundle.json").exists()


def test_import_bundle_merge(tmp_path):
    kb = tmp_path / ".knowledge_base"
    kb.mkdir()
    (kb / "metrics.json").write_text(json.dumps({"existing": True}))

    bundle = {
        "files": {
            "metrics.json": {"new": 1},
            "solutions.json": {"s": "ok"},
        }
    }
    bundle_path = tmp_path / "import.json"
    bundle_path.write_text(json.dumps(bundle))

    transfer = KnowledgeTransfer(str(tmp_path))
    result = transfer.import_bundle("import.json", merge=True)

    assert result["status"] == "imported"
    merged_metrics = json.loads((kb / "metrics.json").read_text())
    assert merged_metrics["existing"] is True
    assert merged_metrics["new"] == 1
    assert (kb / "solutions.json").exists()


def test_import_missing_bundle(tmp_path):
    transfer = KnowledgeTransfer(str(tmp_path))
    result = transfer.import_bundle("missing.json")
    assert "error" in result
