from src.tools.agent_router import AgentRouter


def test_route_testing_task():
    router = AgentRouter()
    result = router.route('add tests for payment flow')
    assert result['primary'] == 'tester'
    assert 'generator' in result['collaborators']


def test_route_repair_task():
    router = AgentRouter()
    result = router.route('fix error in login handler')
    assert result['primary'] == 'repairer'
    assert 'tester' in result['collaborators']
