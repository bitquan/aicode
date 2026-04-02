from src.tools.agent_memory import AgentMemoryStore


def test_share_and_recall(tmp_path):
    store = AgentMemoryStore(str(tmp_path))
    store.share('generator', 'auth flow', 'implemented login helper')
    store.share('tester', 'auth flow', 'added edge-case tests')

    recalled = store.recall(topic='auth')
    assert recalled['count'] == 2
    assert recalled['entries'][0]['agent'] in {'generator', 'tester'}


def test_snapshot(tmp_path):
    store = AgentMemoryStore(str(tmp_path))
    store.share('generator', 'x', 'y')
    snap = store.snapshot()
    assert snap['entries'] == 1
    assert 'generator' in snap['agents']


def test_load_failure_logs_warning(tmp_path, caplog):
    broken = tmp_path / ".knowledge_base" / "agent_memory.json"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_text("{bad json")

    with caplog.at_level("WARNING"):
        store = AgentMemoryStore(str(tmp_path))

    assert store.data == {"entries": []}
    assert "event=agent_memory_load_failed" in caplog.text
