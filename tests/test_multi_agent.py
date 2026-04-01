from src.tools.multi_agent import MultiAgentCoordinator


def test_collaboration_plan(tmp_path):
    coordinator = MultiAgentCoordinator(str(tmp_path))
    result = coordinator.collaborate('review and test API auth flow')
    assert result['primary'] in {'reviewer', 'tester'}
    assert len(result['plan']) >= 3


def test_record_outcome(tmp_path):
    coordinator = MultiAgentCoordinator(str(tmp_path))
    result = coordinator.record_outcome('auth flow', 'good fix', ['generator', 'tester'])
    assert result['status'] == 'recorded'
    assert result['shares'] == 2
