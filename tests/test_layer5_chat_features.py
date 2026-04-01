"""Tests for Layer 5 chat_engine integration (security scanner, doc generator,
api generator, dependency resolver, cost optimizer commands)."""
import pytest
from unittest.mock import MagicMock, patch
from src.tools.chat_engine import ChatEngine


@pytest.fixture()
def engine(tmp_path):
    with patch('src.tools.chat_engine.CodingAgent') as mock_agent, \
         patch('src.tools.chat_engine.build_file_index', return_value={}), \
         patch('src.tools.chat_engine.build_status_report', return_value={}):
        mock_agent.return_value = MagicMock()
        eng = ChatEngine(str(tmp_path))
    return eng


# ── parse_request routing ─────────────────────────────────────────────────────

def test_parse_security_scan(engine):
    req = engine.parse_request("security scan src/main.py")
    assert req["action"] == "security_scan"


def test_parse_generate_docs(engine):
    req = engine.parse_request("generate docs src/main.py")
    assert req["action"] == "doc_generate"


def test_parse_generate_api(engine):
    req = engine.parse_request("generate api src/service.py")
    assert req["action"] == "api_generate"


def test_parse_resolve_deps(engine):
    req = engine.parse_request("resolve dependencies")
    assert req["action"] == "dep_resolve"


def test_parse_optimize_costs(engine):
    req = engine.parse_request("optimize costs")
    assert req["action"] == "cost_optimize"


# ── execute / handler smoke tests ─────────────────────────────────────────────

def test_execute_security_scan_returns_string(engine):
    result = engine.execute({"action": "security_scan", "target": "src/"})
    assert isinstance(result, str)
    assert len(result) > 0


def test_execute_doc_generate_returns_string(engine):
    result = engine.execute({"action": "doc_generate", "target": "src/"})
    assert isinstance(result, str)


def test_execute_api_generate_no_file(engine):
    result = engine.execute({"action": "api_generate", "target": "nonexistent.py"})
    assert isinstance(result, str)


def test_execute_dep_resolve_returns_string(engine, tmp_path):
    (tmp_path / "requirements.txt").write_text("requests\npytest\n")
    result = engine.execute({"action": "dep_resolve"})
    assert isinstance(result, str)


def test_execute_cost_optimize_no_data(engine):
    result = engine.execute({"action": "cost_optimize"})
    assert isinstance(result, str)
    assert len(result) > 0
