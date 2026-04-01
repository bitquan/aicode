"""OpenAI-compatible local HTTP API server.

Run with:
    poetry run python -m src.server

Environment variables:
    PORT              Listening port (default: 8005)
    HOST              Bind address (default: 127.0.0.1)
    WORKSPACE_ROOT    Workspace root for file tools (default: cwd)
    OLLAMA_BASE_URL   Ollama server URL
    OLLAMA_MODEL      Model name
    OLLAMA_TIMEOUT    Request timeout in seconds
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from src.config.settings import load_settings
from src.prompts.layers import load_prompt_layers
from src.providers.ollama_provider import OllamaProvider
from src.tools.repo_index import build_file_index
from src.tools.semantic_retriever import retrieve_relevant_snippets
from src.tools.test_runner import run_test_command
from src.tools.dashboard import DashboardBuilder, render_dashboard_html

# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------

app = FastAPI(title="aicode OpenAI-compatible API", version="0.1.0")

_settings = load_settings()
_provider = OllamaProvider(
    model=_settings.model,
    base_url=_settings.base_url,
    timeout=_settings.timeout,
    max_retries=_settings.max_retries,
    retry_backoff_seconds=_settings.retry_backoff_seconds,
)

_prompts_dir = Path(__file__).resolve().parent / "prompts"
_prompt_layers = load_prompt_layers(_prompts_dir)
_system_prompt = _prompt_layers.get("system", "")

WORKSPACE_ROOT = Path(os.getenv("WORKSPACE_ROOT", str(Path.cwd()))).resolve()
_dashboard_builder = DashboardBuilder(str(WORKSPACE_ROOT))

# Maximum iterations in the tool-calling loop before forcing a final response.
# Prevents infinite loops when the model keeps requesting tool calls.
MAX_TOOL_LOOP_ITERATIONS = 10

# Timeout (seconds) for test commands executed via the run_tests tool.
TEST_COMMAND_TIMEOUT_SECONDS = 120

# ---------------------------------------------------------------------------
# Built-in tool definitions (OpenAI function-calling schema)
# ---------------------------------------------------------------------------

BUILTIN_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file from workspace root.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search the repository for code or documentation matching a query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run a test command in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Test command to execute, e.g. 'pytest tests/'.",
                    }
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit a file in the workspace using a plain-English instruction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file from workspace root.",
                    },
                    "instruction": {
                        "type": "string",
                        "description": "Edit instruction describing what to change.",
                    },
                },
                "required": ["path", "instruction"],
            },
        },
    },
]

_BUILTIN_TOOL_NAMES = {t["function"]["name"] for t in BUILTIN_TOOLS}

# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------


def _safe_resolve(rel_path: str) -> Path:
    """Resolve *rel_path* relative to WORKSPACE_ROOT and verify it stays inside."""
    target = (WORKSPACE_ROOT / rel_path).resolve()
    if not str(target).startswith(str(WORKSPACE_ROOT)):
        raise ValueError(f"Path escapes workspace: {rel_path!r}")
    return target


def _execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Execute a named built-in tool and return its string output."""
    if name == "read_file":
        path = _safe_resolve(arguments["path"])
        if not path.exists():
            return f"File not found: {arguments['path']}"
        return path.read_text(encoding="utf-8", errors="replace")

    if name == "search":
        query = arguments["query"]
        try:
            snippets = retrieve_relevant_snippets(str(WORKSPACE_ROOT), query, max_chars=2000)
            return snippets if snippets else "No results found."
        except Exception:
            index = build_file_index(str(WORKSPACE_ROOT))
            matches = [r["path"] for r in index if query.lower() in r["path"].lower()]
            return "\n".join(matches[:20]) if matches else "No results found."

    if name == "run_tests":
        command = arguments["command"]
        result = run_test_command(command, timeout=TEST_COMMAND_TIMEOUT_SECONDS)
        parts = [f"returncode={result['returncode']}"]
        if result["stdout"]:
            parts.append(f"stdout:\n{result['stdout']}")
        if result["stderr"]:
            parts.append(f"stderr:\n{result['stderr']}")
        return "\n".join(parts)

    if name == "edit_file":
        # Import lazily to avoid circular import issues at module load time
        from src.agents.coding_agent import CodingAgent  # noqa: PLC0415

        path_str = arguments["path"]
        instruction = arguments["instruction"]
        try:
            target = _safe_resolve(path_str)
            current_content = target.read_text(encoding="utf-8") if target.exists() else ""
            agent = CodingAgent()
            new_content = agent.rewrite_file(path_str, instruction, current_content)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(new_content, encoding="utf-8")
            return f"File updated: {path_str}"
        except Exception:
            return "Error: could not edit file. Check path and instruction."

    return f"Unknown tool: {name}"


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    role: str
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class ChatCompletionRequest(BaseModel):
    model: str = Field(default="")
    messages: list[ChatMessage]
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    temperature: float | None = None
    max_tokens: int | None = None


# ---------------------------------------------------------------------------
# Core chat logic
# ---------------------------------------------------------------------------


def _messages_to_dicts(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        d: dict[str, Any] = {"role": m.role}
        if m.content is not None:
            d["content"] = m.content
        if m.name is not None:
            d["name"] = m.name
        if m.tool_call_id is not None:
            d["tool_call_id"] = m.tool_call_id
        if m.tool_calls is not None:
            d["tool_calls"] = m.tool_calls
        out.append(d)
    return out


def _prepend_system(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure a system message with the project system prompt is first."""
    if not _system_prompt:
        return messages
    if messages and messages[0].get("role") == "system":
        return messages
    return [{"role": "system", "content": _system_prompt}] + messages


def _tool_calls_from_ollama(raw_tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Ollama tool_calls to OpenAI format."""
    result = []
    for tc in raw_tool_calls:
        fn = tc.get("function", {})
        args = fn.get("arguments", {})
        result.append(
            {
                "id": f"call_{uuid.uuid4().hex[:12]}",
                "type": "function",
                "function": {
                    "name": fn.get("name", ""),
                    "arguments": json.dumps(args) if isinstance(args, dict) else str(args),
                },
            }
        )
    return result


def _run_tool_loop(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    model_name: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Run the tool-calling loop until a final text response is produced.

    Returns (final_content, updated_messages).
    """
    for _ in range(MAX_TOOL_LOOP_ITERATIONS):
        response = _provider.chat(messages=messages, tools=tools, stream=False)
        msg = response.get("message", {})
        raw_tool_calls = msg.get("tool_calls") or []

        if not raw_tool_calls:
            # Final answer
            return msg.get("content", ""), messages

        # Convert and record the assistant tool-call turn
        openai_tcs = _tool_calls_from_ollama(raw_tool_calls)
        assistant_turn: dict[str, Any] = {
            "role": "assistant",
            "content": msg.get("content") or "",
            "tool_calls": openai_tcs,
        }
        messages = messages + [assistant_turn]

        # Execute each tool and append results
        for tc in openai_tcs:
            fn_name = tc["function"]["name"]
            try:
                fn_args = json.loads(tc["function"]["arguments"])
            except (json.JSONDecodeError, TypeError):
                fn_args = {}
            tool_output = _execute_tool(fn_name, fn_args)
            messages = messages + [
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": fn_name,
                    "content": tool_output,
                }
            ]

    # Fallback: one last call without tools to force a text response
    response = _provider.chat(messages=messages, tools=None, stream=False)
    return response.get("message", {}).get("content", ""), messages


def _make_completion_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex}"


def _make_non_streaming_response(
    completion_id: str,
    model_name: str,
    content: str,
    finish_reason: str = "stop",
) -> dict[str, Any]:
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": finish_reason,
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


async def _stream_ollama_response(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    model_name: str,
    completion_id: str,
) -> AsyncGenerator[str, None]:
    """Yield OpenAI-style SSE chunks from Ollama streaming response.

    When tools are active, runs the tool loop synchronously first, then
    streams the final answer.
    """
    # If tools are requested, run the tool loop first (non-streaming)
    # then stream the final content character-by-character.
    if tools:
        final_content, _ = _run_tool_loop(messages, tools, model_name)
        # Stream the result as token-level chunks
        for chunk_text in _chunk_text(final_content):
            yield _sse_chunk(completion_id, model_name, chunk_text)
        yield _sse_chunk(completion_id, model_name, "", finish_reason="stop")
        yield "data: [DONE]\n\n"
        return

    # No tools — stream directly from Ollama
    try:
        resp = _provider.chat(messages=messages, tools=None, stream=True)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Upstream provider error") from exc

    first = True
    for raw_line in resp.iter_lines():
        if not raw_line:
            continue
        try:
            chunk = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        delta_content = chunk.get("message", {}).get("content", "")
        done = chunk.get("done", False)
        if first and delta_content:
            first = False
        if delta_content:
            yield _sse_chunk(completion_id, model_name, delta_content)
        if done:
            yield _sse_chunk(completion_id, model_name, "", finish_reason="stop")
            break

    yield "data: [DONE]\n\n"


def _sse_chunk(
    completion_id: str,
    model_name: str,
    content: str,
    finish_reason: str | None = None,
) -> str:
    payload = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "delta": {"content": content} if content else {},
                "finish_reason": finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(payload)}\n\n"


def _chunk_text(text: str, chunk_size: int = 8):
    """Yield *text* in small pieces to simulate streaming."""
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/v1/models")
def list_models() -> dict[str, Any]:
    """Return the currently configured model in OpenAI /v1/models format."""
    model_id = _settings.model
    return {
        "object": "list",
        "data": [
            {
                "id": model_id,
                "object": "model",
                "created": 0,
                "owned_by": "ollama",
            }
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest) -> Any:
    """OpenAI-compatible chat completions endpoint."""
    model_name = req.model or _settings.model
    messages = _prepend_system(_messages_to_dicts(req.messages))

    # Determine tool availability
    tool_choice = req.tool_choice
    use_tools = tool_choice != "none"
    tools = BUILTIN_TOOLS if use_tools else None

    completion_id = _make_completion_id()

    if req.stream:
        return StreamingResponse(
            _stream_ollama_response(messages, tools, model_name, completion_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Non-streaming path
    if tools:
        content, _ = _run_tool_loop(messages, tools, model_name)
    else:
        try:
            response = _provider.chat(messages=messages, tools=None, stream=False)
            content = response.get("message", {}).get("content", "")
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Upstream provider error") from exc

    return _make_non_streaming_response(completion_id, model_name, content)


@app.get("/dashboard/data")
def dashboard_data() -> dict[str, Any]:
    """Return dashboard metrics as JSON for web UI or API clients."""
    return _dashboard_builder.build()


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page() -> str:
    """Return a lightweight HTML dashboard page."""
    payload = _dashboard_builder.build()
    return render_dashboard_html(payload)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8005"))
    host = os.getenv("HOST", "127.0.0.1")
    uvicorn.run("src.server:app", host=host, port=port, reload=False)
