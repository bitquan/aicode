from src.tools.vscode_integration import VSCodeIntegration


def test_vscode_setup_files(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    integration = VSCodeIntegration(str(tmp_path))

    tasks = integration.ensure_tasks()
    launch = integration.ensure_launch()
    snapshot = integration.workspace_snapshot()

    assert tasks["status"] in {"created", "exists"}
    assert launch["status"] in {"created", "exists"}
    assert snapshot["workspace"] == tmp_path.name
