from src.tools.dashboard import DashboardBuilder, render_dashboard_html


def test_dashboard_builder_payload(tmp_path):
    (tmp_path / "DEVELOPMENT_ROADMAP.md").write_text("- [x] done\n- [ ] todo\n")
    builder = DashboardBuilder(str(tmp_path))
    payload = builder.build()
    assert "workspace" in payload
    assert "roadmap_percent" in payload


def test_dashboard_html_render():
    html = render_dashboard_html({
        "workspace": "demo",
        "readiness": "good",
        "benchmark_score": 90,
        "roadmap_percent": 50,
        "roadmap_done": 1,
        "roadmap_total": 2,
    })
    assert "aicode Dashboard" in html
    assert "demo" in html
