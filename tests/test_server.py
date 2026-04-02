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
    with patch("src.server.run_test_command", return_value=mock_result) as mock_run:
        result = _execute_tool("run_tests", {"command": "pytest"})
    assert mock_run.call_args.kwargs["cwd"] is not None
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


def test_healthz_endpoint(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"models": [{"model": "qwen2.5-coder:7b"}]}

    mock_awareness = {
        "confidence_policy": {"low_confidence_research_threshold": 0.66},
        "recent_decision_metrics": {
            "events_considered": 5,
            "avg_confidence": 0.8,
            "research_trigger_count": 1,
            "research_trigger_rate": 0.2,
        },
    }

    with patch("src.server.requests.get", return_value=mock_response), patch(
        "src.server._app_service._engine.get_self_awareness_snapshot",
        return_value=mock_awareness,
    ):
        resp = client.get("/healthz")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert "workspace_root" in payload
    assert "model" in payload
    assert "base_url" in payload
    assert payload["ollama"]["reachable"] is True
    assert payload["ollama"]["model_available"] is True
    assert payload["runtime"]["routing_generation"] >= 1
    assert "started_at" in payload["runtime"]
    assert payload["confidence_policy"]["low_confidence_research_threshold"] == 0.66
    assert payload["recent_decision_metrics"]["research_trigger_rate"] == 0.2


def test_readiness_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        "src.server.run_engine_readiness_suite",
        lambda engine: {
            "status": "pass",
            "passed": 3,
            "failed": 0,
            "total": 3,
            "routing_generation": 3,
            "readiness_suite_version": 1,
            "server_reachable": True,
            "ollama_reachable": True,
            "web_enabled": True,
            "known_vscode_panel": "vscode-extension/src/extension.ts",
            "results": [],
        },
    )

    resp = client.get("/v1/aicode/readiness")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "pass"
    assert payload["passed"] == 3
    assert payload["web_enabled"] is True


def test_latest_self_improve_run_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        "src.server.get_latest_self_improvement_run",
        lambda workspace_root: {
            "run_id": "sir_latest",
            "mode": "supervised",
            "state": "proposed",
            "goal": "add a clear chat button",
            "candidate_summary": "User-requested improvement",
            "pinned_files": ["vscode-extension/src/extension.ts"],
            "approved_files": ["vscode-extension/src/extension.ts"],
            "likely_files": [{"path": "vscode-extension/src/extension.ts", "reason": "VS Code panel", "score": 8}],
            "verification_plan": ["npm --prefix vscode-extension run compile"],
            "web_research_used": False,
            "rollback_performed": False,
            "events": [],
        },
    )

    resp = client.get("/v1/aicode/self-improve/runs/latest")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["run_id"] == "sir_latest"
    assert payload["state"] == "proposed"
    assert payload["pinned_files"] == ["vscode-extension/src/extension.ts"]
    assert payload["approved_files"] == ["vscode-extension/src/extension.ts"]


def test_self_improve_run_by_id_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        "src.server.get_self_improvement_run",
        lambda workspace_root, run_id: {
            "run_id": run_id,
            "mode": "supervised",
            "state": "verified",
            "goal": "fix routing",
            "candidate_summary": "Fix a failing canary",
            "pinned_files": ["src/tools/commanding/request_parser.py"],
            "approved_files": ["src/tools/commanding/request_parser.py"],
            "likely_files": [{"path": "src/tools/commanding/request_parser.py", "reason": "parser", "score": 9}],
            "verification_plan": ["./.venv/bin/python -m pytest -q tests/test_app_service.py"],
            "web_research_used": False,
            "rollback_performed": False,
            "events": [],
        },
    )

    resp = client.get("/v1/aicode/self-improve/runs/sir_known")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["run_id"] == "sir_known"
    assert payload["state"] == "verified"
    assert payload["approved_files"] == ["src/tools/commanding/request_parser.py"]


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


def test_app_command_streaming_endpoint(client, monkeypatch):
    class DummyService:
        def parse_command(self, command: str):
            from src.tools.commanding import ActionRequest

            return ActionRequest(action="status", confidence=0.9, raw_input=command)

        def run_request(self, request, *, source="api"):
            return {
                "command": request.raw_input,
                "action": "status",
                "confidence": 0.9,
                "response": "hello streamed world",
                "applied_preferences": [],
                "output_trace_id": "out_123",
                "events": [{"kind": "route", "message": "Routed to status"}],
                "route_attempts": ["status"],
                "recovered_from_action": None,
                "needs_external_research": False,
                "research_trigger_reason": None,
            }

    monkeypatch.setattr("src.server._app_service", DummyService())

    with client.stream(
        "POST",
        "/v1/aicode/command/stream",
        json={"command": "status"},
    ) as response:
        body = "".join(chunk for chunk in response.iter_text())

    assert response.status_code == 200
    assert "event: route" in body
    assert "event: delta" in body
    assert "event: done" in body
    assert "hello streamed world" in body
    assert '"route_attempts": ["status"]' in body
    assert '"needs_external_research": false' in body


def test_editor_chat_endpoint(client):
    mock_agent = MagicMock()
    mock_agent.run_mode.return_value = "Use a helper function here."

    with patch("src.server.CodingAgent", return_value=mock_agent):
        response = client.post(
            "/v1/aicode/editor/chat",
            json={
                "path": "src/demo.py",
                "prompt": "What should I change?",
                "current_content": "def demo():\n    return 1\n",
                "selection": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 1, "character": 12},
                },
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["response"] == "Use a helper function here."
    assert payload["events"][0]["kind"] == "read"
    assert payload["events"][1]["kind"] == "chat"


def test_editor_preview_edit_file_mode(client):
    mock_agent = MagicMock()
    mock_agent.rewrite_file.return_value = "print('updated')\n"

    with patch("src.server.CodingAgent", return_value=mock_agent):
        response = client.post(
            "/v1/aicode/editor/preview-edit",
            json={
                "path": "src/demo.py",
                "instruction": "Update the print value",
                "current_content": "print('original')\n",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "file"
    assert payload["updated_content"] == "print('updated')\n"
    assert "--- a/src/demo.py" in payload["diff"]
    assert payload["events"][1]["kind"] == "edit"


def test_editor_preview_edit_selection_mode(client):
    mock_agent = MagicMock()
    mock_agent.rewrite_selection.return_value = "answer = 42"

    with patch("src.server.CodingAgent", return_value=mock_agent):
        response = client.post(
            "/v1/aicode/editor/preview-edit",
            json={
                "path": "src/demo.py",
                "instruction": "Use a clearer variable name",
                "current_content": "value = 1\nprint(value)\n",
                "selection": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 9},
                },
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "selection"
    assert payload["replacement_text"] == "answer = 42"
    assert payload["updated_content"] == "answer = 42\nprint(value)\n"
