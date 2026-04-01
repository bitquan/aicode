"""Unit tests for src/server.py — request/response shape validation."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

# httpx is required by FastAPI's TestClient (installed as starlette dependency)
try:
    from fastapi.testclient import TestClient
    _HAS_TESTCLIENT = True
except ImportError:  # pragma: no cover
    _HAS_TESTCLIENT = False

from src.server import (
    BUILTIN_TOOLS,
    _execute_tool,
    _make_completion_id,
    _make_non_streaming_response,
    _messages_to_dicts,
    _safe_resolve,
    _tool_calls_from_ollama,
    app,
)


# ---------------------------------------------------------------------------
# Helper fixtures / mocks
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    if not _HAS_TESTCLIENT:
        pytest.skip("httpx/TestClient not available")
    return TestClient(app, raise_server_exceptions=True)


def _mock_chat_response(content: str = "hello", tool_calls: list | None = None) -> dict:
    msg: dict = {"role": "assistant", "content": content}
    if tool_calls is not None:
        msg["tool_calls"] = tool_calls
    return {"model": "test-model", "message": msg, "done": True}


# ---------------------------------------------------------------------------
# _make_completion_id
# ---------------------------------------------------------------------------

def test_make_completion_id_format():
    cid = _make_completion_id()
    assert cid.startswith("chatcmpl-")
    assert len(cid) > 10


# ---------------------------------------------------------------------------
# _make_non_streaming_response
# ---------------------------------------------------------------------------

def test_non_streaming_response_shape():
    resp = _make_non_streaming_response("chatcmpl-abc", "my-model", "Hello!")
    assert resp["object"] == "chat.completion"
    assert resp["id"] == "chatcmpl-abc"
    assert resp["model"] == "my-model"
    choices = resp["choices"]
    assert len(choices) == 1
    assert choices[0]["message"]["role"] == "assistant"
    assert choices[0]["message"]["content"] == "Hello!"
    assert choices[0]["finish_reason"] == "stop"
    assert "usage" in resp


# ---------------------------------------------------------------------------
# _messages_to_dicts
# ---------------------------------------------------------------------------

def test_messages_to_dicts_basic():
    from src.server import ChatMessage

    msgs = [
        ChatMessage(role="system", content="sys"),
        ChatMessage(role="user", content="hi"),
    ]
    result = _messages_to_dicts(msgs)
    assert result[0] == {"role": "system", "content": "sys"}
    assert result[1] == {"role": "user", "content": "hi"}


def test_messages_to_dicts_omits_none_fields():
    from src.server import ChatMessage

    msgs = [ChatMessage(role="user", content="hello")]
    result = _messages_to_dicts(msgs)
    assert "name" not in result[0]
    assert "tool_call_id" not in result[0]


# ---------------------------------------------------------------------------
# _safe_resolve
# ---------------------------------------------------------------------------

def test_safe_resolve_valid(tmp_path):
    from src import server as srv

    original = srv.WORKSPACE_ROOT
    srv.WORKSPACE_ROOT = tmp_path
    try:
        target = _safe_resolve("src/main.py")
        assert str(target).startswith(str(tmp_path))
    finally:
        srv.WORKSPACE_ROOT = original


def test_safe_resolve_path_traversal(tmp_path):
    from src import server as srv

    original = srv.WORKSPACE_ROOT
    srv.WORKSPACE_ROOT = tmp_path
    try:
        with pytest.raises(ValueError, match="escapes workspace"):
            _safe_resolve("../../etc/passwd")
    finally:
        srv.WORKSPACE_ROOT = original


# ---------------------------------------------------------------------------
# _tool_calls_from_ollama
# ---------------------------------------------------------------------------

def test_tool_calls_from_ollama_basic():
    raw = [
        {"function": {"name": "read_file", "arguments": {"path": "src/main.py"}}}
    ]
    result = _tool_calls_from_ollama(raw)
    assert len(result) == 1
    tc = result[0]
    assert tc["type"] == "function"
    assert tc["function"]["name"] == "read_file"
    # arguments should be a JSON string
    args = json.loads(tc["function"]["arguments"])
    assert args["path"] == "src/main.py"
    assert tc["id"].startswith("call_")


# ---------------------------------------------------------------------------
# _execute_tool — read_file
# ---------------------------------------------------------------------------

def test_execute_tool_read_file(tmp_path):
    from src import server as srv

    original = srv.WORKSPACE_ROOT
    srv.WORKSPACE_ROOT = tmp_path
    try:
        f = tmp_path / "hello.txt"
        f.write_text("world")
        result = _execute_tool("read_file", {"path": "hello.txt"})
        assert result == "world"
    finally:
        srv.WORKSPACE_ROOT = original


def test_execute_tool_read_file_missing(tmp_path):
    from src import server as srv

    original = srv.WORKSPACE_ROOT
    srv.WORKSPACE_ROOT = tmp_path
    try:
        result = _execute_tool("read_file", {"path": "nonexistent.txt"})
        assert "not found" in result.lower()
    finally:
        srv.WORKSPACE_ROOT = original


# ---------------------------------------------------------------------------
# _execute_tool — search
# ---------------------------------------------------------------------------

def test_execute_tool_search_fallback(tmp_path):
    from src import server as srv

    original = srv.WORKSPACE_ROOT
    srv.WORKSPACE_ROOT = tmp_path
    try:
        (tmp_path / "my_module.py").write_text("pass")
        # Patch semantic_retriever to raise so we test the fallback
        with patch("src.server.retrieve_relevant_snippets", side_effect=Exception("no index")):
            result = _execute_tool("search", {"query": "my_module"})
        assert "my_module.py" in result
    finally:
        srv.WORKSPACE_ROOT = original


# ---------------------------------------------------------------------------
# _execute_tool — run_tests
# ---------------------------------------------------------------------------

def test_execute_tool_run_tests():
    mock_result = {
        "command": "pytest",
        "success": True,
        "stdout": "1 passed",
        "stderr": "",
        "returncode": 0,
        "timed_out": False,
    }
    with patch("src.server.run_test_command", return_value=mock_result):
        result = _execute_tool("run_tests", {"command": "pytest"})
    assert "returncode=0" in result
    assert "1 passed" in result


# ---------------------------------------------------------------------------
# _execute_tool — unknown tool
# ---------------------------------------------------------------------------

def test_execute_tool_unknown():
    result = _execute_tool("nonexistent_tool", {})
    assert "Unknown tool" in result


# ---------------------------------------------------------------------------
# BUILTIN_TOOLS schema
# ---------------------------------------------------------------------------

def test_builtin_tools_schema():
    tool_names = {t["function"]["name"] for t in BUILTIN_TOOLS}
    assert tool_names == {"read_file", "search", "run_tests", "edit_file"}
    for tool in BUILTIN_TOOLS:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn


# ---------------------------------------------------------------------------
# GET /v1/models
# ---------------------------------------------------------------------------

def test_get_models(client):
    resp = client.get("/v1/models")
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "list"
    assert len(data["data"]) >= 1
    assert data["data"][0]["object"] == "model"
    assert "id" in data["data"][0]


# ---------------------------------------------------------------------------
# POST /v1/chat/completions — non-streaming, no tools
# ---------------------------------------------------------------------------

def test_chat_completions_non_streaming(client):
    mock_resp = _mock_chat_response("The answer is 42.")
    with patch("src.server._provider") as mock_prov:
        mock_prov.chat.return_value = mock_resp
        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "What is 6 * 7?"}],
                "stream": False,
                "tool_choice": "none",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["content"] == "The answer is 42."
    assert data["choices"][0]["finish_reason"] == "stop"


def test_dashboard_data_endpoint(client):
    resp = client.get("/dashboard/data")
    assert resp.status_code == 200
    payload = resp.json()
    assert "workspace" in payload
    assert "roadmap_percent" in payload

def test_dashboard_page_endpoint(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "aicode Dashboard" in resp.text

# ---------------------------------------------------------------------------
# POST /v1/chat/completions — tool loop executes tool and returns final answer
# ---------------------------------------------------------------------------

def test_chat_completions_tool_loop(client):
    # First call returns a tool_call; second returns the final answer
    call_count = {"n": 0}

    def fake_chat(messages, tools=None, stream=False):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _mock_chat_response(
                content="",
                tool_calls=[
                    {"function": {"name": "run_tests", "arguments": {"command": "pytest"}}}
                ],
            )
        return _mock_chat_response("All tests passed!")

    mock_test_result = {
        "command": "pytest",
        "success": True,
        "stdout": "1 passed",
        "stderr": "",
        "returncode": 0,
        "timed_out": False,
    }

    with patch("src.server._provider") as mock_prov, \
         patch("src.server.run_test_command", return_value=mock_test_result):
        mock_prov.chat.side_effect = fake_chat
        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "Run the tests"}],
                "stream": False,
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["choices"][0]["message"]["content"] == "All tests passed!"
    assert call_count["n"] == 2


# ---------------------------------------------------------------------------
# POST /v1/chat/completions — streaming
# ---------------------------------------------------------------------------

def test_chat_completions_streaming(client):
    """Verify streaming returns SSE lines with correct structure."""

    def fake_iter_lines():
        for word in ["Hello", " world"]:
            yield json.dumps({"message": {"role": "assistant", "content": word}, "done": False})
        yield json.dumps({"message": {"role": "assistant", "content": ""}, "done": True})

    mock_stream_resp = MagicMock()
    mock_stream_resp.iter_lines.return_value = fake_iter_lines()

    with patch("src.server._provider") as mock_prov:
        mock_prov.chat.return_value = mock_stream_resp
        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "Say hello"}],
                "stream": True,
                "tool_choice": "none",
            },
        )
    assert resp.status_code == 200
    body = resp.text
    assert "data:" in body
    assert "[DONE]" in body
    # Each non-DONE data line should parse as valid JSON with the right shape
    for line in body.splitlines():
        if line.startswith("data:") and "[DONE]" not in line:
            payload = json.loads(line[len("data:"):].strip())
            assert payload["object"] == "chat.completion.chunk"
            assert "choices" in payload
