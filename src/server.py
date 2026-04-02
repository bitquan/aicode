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

import asyncio
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
import requests

from src.agents.coding_agent import CodingAgent
from src.app_service import AppService
from src.config.settings import load_settings
from src.prompts.layers import load_prompt_layers
from src.providers.ollama_provider import OllamaProvider
from src.tools.patch_applier import preview_diff
from src.tools.repo_index import build_file_index
from src.tools.semantic_retriever import retrieve_relevant_snippets
from src.tools.dashboard import DashboardBuilder, render_dashboard_html
from src.tools.learning_metrics import build_learning_metrics
from src.tools.test_runner import run_test_command

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
_app_service = AppService(str(WORKSPACE_ROOT))

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
    workspace_root = WORKSPACE_ROOT.resolve()
    target = (workspace_root / rel_path).resolve()
    try:
        target.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError(f"Path escapes workspace: {rel_path!r}") from exc
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
        result = run_test_command(
            command,
            timeout=TEST_COMMAND_TIMEOUT_SECONDS,
            cwd=str(WORKSPACE_ROOT),
        )
        parts = [f"returncode={result['returncode']}"]
        if result["stdout"]:
            parts.append(f"stdout:\n{result['stdout']}")
        if result["stderr"]:
            parts.append(f"stderr:\n{result['stderr']}")
        return "\n".join(parts)

    if name == "edit_file":
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


class AppCommandRequest(BaseModel):
    command: str


class AppCommandResponse(BaseModel):
    command: str
    action: str
    confidence: float
    response: str
    applied_preferences: list[str] = Field(default_factory=list)
    output_trace_id: str | None = None
    events: list[dict[str, str]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    workspace_root: str
    model: str
    base_url: str
    ollama: dict[str, Any]


class EditorPosition(BaseModel):
    line: int
    character: int


class EditorRange(BaseModel):
    start: EditorPosition
    end: EditorPosition


class EditorChatRequest(BaseModel):
    path: str
    prompt: str
    current_content: str
    selection: EditorRange | None = None


class EditorChatResponse(BaseModel):
    path: str
    prompt: str
    response: str
    events: list[dict[str, str]] = Field(default_factory=list)


class EditorEditPreviewRequest(BaseModel):
    path: str
    instruction: str
    current_content: str
    selection: EditorRange | None = None


class EditorEditPreviewResponse(BaseModel):
    path: str
    mode: str
    updated_content: str
    diff: str
    replacement_text: str | None = None
    events: list[dict[str, str]] = Field(default_factory=list)


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


def _offset_from_position(content: str, position: EditorPosition) -> int:
    lines = content.splitlines(keepends=True)
    if position.line < 0 or position.character < 0:
        raise HTTPException(status_code=400, detail="Selection positions must be non-negative")
    if position.line >= len(lines):
        return len(content)

    prefix = "".join(lines[: position.line])
    line_text = lines[position.line]
    line_without_newline = line_text.rstrip("\r\n")
    character = min(position.character, len(line_without_newline))
    return len(prefix) + character


def _selection_offsets(content: str, selection: EditorRange) -> tuple[int, int]:
    start = _offset_from_position(content, selection.start)
    end = _offset_from_position(content, selection.end)
    if end < start:
        raise HTTPException(status_code=400, detail="Selection end must not be before start")
    return start, end


def _editor_events(*events: tuple[str, str]) -> list[dict[str, str]]:
    return [{"kind": kind, "message": message} for kind, message in events]


def _check_ollama_health() -> dict[str, Any]:
    """Return a lightweight Ollama connectivity summary for diagnostics."""
    url = f"{_settings.base_url.rstrip('/')}/api/tags"
    try:
        response = requests.get(url, timeout=1.5)
        response.raise_for_status()
        payload = response.json()
        models = payload.get("models", [])
        model_names = {
            item.get("model", "") or item.get("name", "")
            for item in models
            if isinstance(item, dict)
        }
        model_available = _settings.model in model_names if model_names else False
        detail = "reachable"
        if model_names:
            detail = (
                f"reachable; configured model '{_settings.model}' is available"
                if model_available
                else f"reachable; configured model '{_settings.model}' was not listed"
            )
        return {
            "reachable": True,
            "detail": detail,
            "model_available": model_available,
        }
    except requests.RequestException as exc:
        return {
            "reachable": False,
            "detail": f"unreachable: {exc}",
            "model_available": False,
        }


def _sse_event(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


async def _stream_app_command(command: str) -> AsyncGenerator[str, None]:
    """Stream aicode app-command progress and response chunks as SSE events."""
    try:
        request = _app_service.parse_command(command)
        yield _sse_event(
            "route",
            {
                "command": command,
                "action": request.action,
                "confidence": request.confidence,
            },
        )
        yield _sse_event("status", {"message": "Executing command"})
        result = await asyncio.to_thread(_app_service.run_request, request, source="api_stream")
        for event in result.get("events", []):
            yield _sse_event("event", event)
        yield _sse_event(
            "result",
            {
                "command": result["command"],
                "action": result["action"],
                "confidence": result["confidence"],
                "output_trace_id": result.get("output_trace_id"),
                "applied_preferences": result.get("applied_preferences", []),
            },
        )
        for chunk in _chunk_text(result["response"], chunk_size=24):
            yield _sse_event("delta", {"text": chunk})
        yield _sse_event(
            "done",
            {
                "command": result["command"],
                "action": result["action"],
                "confidence": result["confidence"],
                "response": result["response"],
            },
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        yield _sse_event("error", {"message": str(exc)})


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


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> dict[str, Any]:
    """Return lightweight server health information."""
    return {
        "status": "ok",
        "workspace_root": str(WORKSPACE_ROOT),
        "model": _settings.model,
        "base_url": _settings.base_url,
        "ollama": _check_ollama_health(),
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


@app.get("/metrics/learning")
def learning_metrics_data(limit: int = 1000) -> dict[str, Any]:
    """Return baseline learning metrics as JSON."""
    return build_learning_metrics(str(WORKSPACE_ROOT), limit=max(10, min(limit, 5000)))


@app.post("/v1/aicode/command", response_model=AppCommandResponse)
def app_command(req: AppCommandRequest) -> dict[str, Any]:
    """Run one natural-language app command via the source-of-truth app service."""
    command = req.command.strip()
    if not command:
        raise HTTPException(status_code=400, detail="Command must not be empty")
    return _app_service.run_command(command)


@app.post("/v1/aicode/command/stream")
async def app_command_stream(req: AppCommandRequest) -> StreamingResponse:
    """Stream one natural-language app command as SSE events."""
    command = req.command.strip()
    if not command:
        raise HTTPException(status_code=400, detail="Command must not be empty")
    return StreamingResponse(
        _stream_app_command(command),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/v1/aicode/editor/chat", response_model=EditorChatResponse)
def editor_chat(req: EditorChatRequest) -> dict[str, Any]:
    """Explain or discuss the current file/selection with editor-scoped context."""
    _safe_resolve(req.path)
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt must not be empty")

    selected_text = ""
    if req.selection is not None:
        start, end = _selection_offsets(req.current_content, req.selection)
        selected_text = req.current_content[start:end]

    context_blocks = [f"File: {req.path}"]
    if selected_text:
        context_blocks.append(f"Selected code:\n```\n{selected_text}\n```")
    else:
        context_blocks.append(f"Current file excerpt:\n```\n{req.current_content[:2000]}\n```")

    agent = CodingAgent()
    response = agent.run_mode("explain", prompt, context="\n\n".join(context_blocks))
    return {
        "path": req.path,
        "prompt": prompt,
        "response": response,
        "events": _editor_events(
            ("read", f"Loaded editor context for {req.path}"),
            ("chat", "Generated inline explanation"),
        ),
    }


@app.post("/v1/aicode/editor/preview-edit", response_model=EditorEditPreviewResponse)
def editor_preview_edit(req: EditorEditPreviewRequest) -> dict[str, Any]:
    """Generate an edit preview for the current file or selected region."""
    _safe_resolve(req.path)
    instruction = req.instruction.strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="Instruction must not be empty")

    agent = CodingAgent()
    mode = "file"
    replacement_text: str | None = None

    if req.selection is not None:
        start, end = _selection_offsets(req.current_content, req.selection)
        selected_text = req.current_content[start:end]
        before_context = req.current_content[max(0, start - 1000) : start]
        after_context = req.current_content[end : min(len(req.current_content), end + 1000)]
        replacement_text = agent.rewrite_selection(
            req.path,
            instruction,
            selected_text,
            before_context,
            after_context,
        )
        updated_content = req.current_content[:start] + replacement_text + req.current_content[end:]
        mode = "selection"
    else:
        updated_content = agent.rewrite_file(req.path, instruction, req.current_content)

    diff = preview_diff(req.current_content, updated_content, req.path)
    return {
        "path": req.path,
        "mode": mode,
        "updated_content": updated_content,
        "diff": diff,
        "replacement_text": replacement_text,
        "events": _editor_events(
            ("read", f"Prepared edit preview for {req.path}"),
            ("edit", f"Generated {mode} edit preview"),
            ("diff", "Built diff preview"),
        ),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8005"))
    host = os.getenv("HOST", "127.0.0.1")
    uvicorn.run("src.server:app", host=host, port=port, reload=False)
