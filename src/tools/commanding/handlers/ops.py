"""Operational handlers for generate/edit/fix and conversational support."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from src.tools.autofix import run_autofix_loop
from src.tools.doc_fetcher import enhance_with_docs

if TYPE_CHECKING:
    from src.tools.chat_engine import ChatEngine


def _handle_generate(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Generate code from prompt with streaming output and doc context."""
    instruction = request.get("instruction", "")
    instruction = engine._apply_user_preferences(instruction, request_intent="generate")
    use_streaming = request.get("stream", True)

    doc_context = enhance_with_docs(str(engine.workspace_root), instruction)

    if use_streaming:
        if doc_context:
            print(doc_context, flush=True)
            print()
        print("🔄 Generating... ", end="", flush=True)

    code = engine.agent.generate_code(instruction)

    if use_streaming:
        print("\n\n📄 Code generated:", flush=True)
        print("```python")
        print(code)
        print("```\n")
        print("🧪 Testing... ", end="", flush=True)

    eval_result = engine.agent.evaluate_code(code)

    if use_streaming:
        print("Done!\n", flush=True)

    status = "✅ Success" if eval_result["execution_ok"] else "⚠️ Has issues"
    output = eval_result.get("stdout", "")

    engine._log_interaction(instruction, "generate", eval_result["execution_ok"], doc_context)

    return f"""{status}
Execution output:
{output}"""


def _handle_edit(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Edit a file with instruction."""
    target = request.get("target", "src/main.py")
    instruction = request.get("instruction", "")

    target_path = engine.workspace_root / target
    if not target_path.exists():
        return f"❌ File not found: {target}"

    return f"📝 I'll {instruction.lower()} in {target}. Use 'autofix {target}' to apply changes and test."


def _handle_autofix(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Run autofix loop on target file with streaming feedback and doc context."""
    target = request.get("target", "src/main.py")
    instruction = request.get("instruction", "")
    instruction = engine._apply_user_preferences(instruction, request_intent="autofix")
    use_streaming = request.get("stream", True)

    target_path = engine.workspace_root / target
    if not target_path.exists():
        return f"❌ File not found: {target}"

    doc_context = enhance_with_docs(str(engine.workspace_root), instruction)

    if use_streaming:
        if doc_context:
            print(doc_context, flush=True)
            print()
        print(f"🔧 Running autofix on {target}... ", flush=True)
        print(f"   Instruction: {instruction}\n")

    result = run_autofix_loop(
        agent=engine.agent,
        workspace_root=str(engine.workspace_root),
        target_path=target,
        instruction=instruction,
        max_attempts=3,
    )

    if use_streaming:
        print()

    success = result.get("success", False)
    if success:
        attempts = len(result.get("attempts", []))
        if use_streaming:
            print(f"✅ Success! Fixed in {attempts} attempt(s)", flush=True)
        engine._log_interaction(f"fix {target}", "autofix", True, doc_context)
        return f"✅ Fixed in {attempts} attempt(s)! Tests passed.\nTrace: {result.get('trace_id')}"

    if use_streaming:
        print(f"❌ Couldn't fix after {len(result.get('attempts', []))} attempts", flush=True)
    engine._log_interaction(f"fix {target}", "autofix", False, doc_context)
    return (
        f"❌ Couldn't fix after {len(result.get('attempts', []))} attempts.\n"
        f"Reason: {result.get('reason', 'unknown')}"
    )


def _handle_multi_agent(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Build a collaboration plan across specialized agents."""
    task = request.get("task", "general task")
    result = engine.multi_agent.collaborate(task)
    engine._log_interaction(f"collaborate {task}", "multi_agent", True)
    return (
        "🤝 Multi-Agent Plan\n"
        f"  • Task: {result.get('task')}\n"
        f"  • Primary: {result.get('primary')}\n"
        f"  • Collaborators: {', '.join(result.get('collaborators', [])) or 'None'}\n"
        f"  • Memory Hits: {result.get('memory_hits')}\n"
        + "\n".join(f"  • {step}" for step in result.get("plan", [])[:5])
    )


def _handle_agent_route(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Route a task to the best specialized agent team."""
    task = request.get("task", "general task")
    route = engine.agent_router.route(task)
    engine._log_interaction(f"route task {task}", "agent_route", True)
    return (
        "🧭 Agent Routing\n"
        f"  • Primary Agent: {route.get('primary')}\n"
        f"  • Collaborators: {', '.join(route.get('collaborators', [])) or 'None'}\n"
        f"  • Why: {', '.join(route.get('rationale', []))}"
    )


def _handle_custom_llm(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Route task to configured best-fit LLM model."""
    task = request.get("task", "general task")
    route = engine.custom_llm_support.choose_model(task)
    engine._log_interaction(f"model route {task}", "custom_llm", True)
    return (
        "🧩 Custom LLM Routing\n"
        f"  • Task type: {route.get('task_type')}\n"
        f"  • Provider: {route.get('provider')}\n"
        f"  • Model: {route.get('model')}\n"
        f"  • Cost tier: {route.get('cost_tier')}"
    )


def _handle_help_summary(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Return a concise conversational capability summary."""
    awareness = engine.get_self_awareness_snapshot()
    server = awareness["server"]
    ollama = awareness["ollama"]
    web = awareness["web"]
    raw_prompt = str(request.get("raw_input", "")).strip().lower()
    commands = awareness["commands"]
    prefers_human_style = engine.prefers_conversational_responses("help_summary")

    asks_for_five = bool(re.search(r"\b(5|five)\b", raw_prompt)) and any(
        phrase in raw_prompt for phrase in ("things", "can you do", "what can")
    )
    asks_for_tone_improvement = any(
        phrase in raw_prompt
        for phrase in (
            "improve on how you talk",
            "talk to users",
            "how you talk",
            "communication",
        )
    )

    engine._log_interaction("help", "help_summary", True)

    if asks_for_tone_improvement:
        return (
            "Absolutely — and I can start now.\n"
            "One immediate improvement: keep answers shorter, clearer, and focused on your exact next action.\n"
            "If you want, I can use this response style by default: concise summary, concrete change, and clear next step."
        )

    if asks_for_five:
        return (
            "Here are 5 things I can do for this repo right now:\n"
            "1) Implement or refactor code in specific files.\n"
            "2) Debug failing behavior and fix root causes.\n"
            "3) Run and interpret tests, then patch regressions.\n"
            "4) Improve architecture/quality tools (coverage, safety, performance).\n"
            "5) Build repo-aware plans and execute them end-to-end.\n"
            "Tell me one target file or one goal, and I’ll start immediately."
        )

    if prefers_human_style:
        return (
            "I can help with the real work: implement features, fix bugs, run tests, and improve the repo without big risky diffs.\n"
            f"Right now, the server is {'up' if server['reachable'] else 'down'} and Ollama is {'reachable' if ollama['reachable'] else 'unreachable'}.\n"
            f"Best next step: give me one file or one goal. Example actions: {', '.join(commands[:6])}."
        )

    return (
        "I’m your repo-focused coding partner.\n"
        "I can implement features, fix bugs, run tests, and improve architecture with minimal safe diffs.\n"
        f"Runtime: server is {'up' if server['reachable'] else 'down'} at {server['url']}, "
        f"Ollama is {'reachable' if ollama['reachable'] else 'unreachable'} at {ollama['url']}.\n"
        f"VS Code panel: {awareness['known_surfaces']['vscode_panel']}. Web research: {web['summary']}.\n"
        f"Top actions: {', '.join(commands[:8])}.\n"
        "Try: 'status', 'review src/server.py', or 'fix src/main.py'."
    )


def _handle_clarify(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Ask a short follow-up when intent confidence is low."""
    original = request.get("original_input", "").strip()
    engine._log_interaction(original or "clarify", "clarify", True)
    return (
        "❓ I want to make sure I route this correctly.\n"
        f"Your prompt: {original or '(empty)'}\n"
        "Reply with one of: generate code, fix a file, review code, debug, research, search, repo summary, or status."
    )


def _handle_self_aware_summary(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Return a live capability and runtime awareness snapshot."""
    awareness = engine.get_self_awareness_snapshot()
    server = awareness["server"]
    ollama = awareness["ollama"]
    web = awareness["web"]
    confidence_policy = awareness.get("confidence_policy", {})
    recent = awareness.get("recent_decision_metrics", {})
    self_improvement = awareness.get("self_improvement", {})
    commands_preview = ", ".join(awareness["commands"][:14])
    prefers_human_style = engine.prefers_conversational_responses("self_aware_summary")
    engine._log_interaction("self aware", "self_aware_summary", True)

    if prefers_human_style:
        return (
            "Here’s the quick self-check.\n"
            f"Server: {'up' if server['reachable'] else 'down'} at {server['url']}. Ollama: {'reachable' if ollama['reachable'] else 'unreachable'} at {ollama['url']}.\n"
            f"VS Code panel: {awareness['known_surfaces']['vscode_panel']}. Web research: {web['summary']}.\n"
            f"Decision quality: avg confidence {recent.get('avg_confidence', 0.0)}, reroute rate {recent.get('reroute_rate', 0.0)}.\n"
            f"Self-improvement mode: {self_improvement.get('mode')} (latest run: {self_improvement.get('latest_run_id') or 'none'}).\n"
            f"If you want more detail, I can break down commands next: {commands_preview}."
        )

    return (
        "🪞 Self-Awareness Snapshot\n"
        f"  • VS Code panel: {awareness['known_surfaces']['vscode_panel']}\n"
        f"  • Editable surfaces: {', '.join(awareness.get('editable_surfaces', [])[:4])}\n"
        f"  • Server: {'up' if server['reachable'] else 'down'} ({server['url']})\n"
        f"  • Ollama: {'reachable' if ollama['reachable'] else 'unreachable'} ({ollama['url']})\n"
        f"  • Web research: {web['summary']}\n"
        f"  • Low-confidence threshold: {confidence_policy.get('low_confidence_research_threshold', 'n/a')}\n"
        f"  • Recent avg confidence: {recent.get('avg_confidence', 0.0)}\n"
        f"  • Recent reroute rate: {recent.get('reroute_rate', 0.0)}\n"
        f"  • Recent research trigger rate: {recent.get('research_trigger_rate', 0.0)}\n"
        f"  • Decision alerts: {len(recent.get('alerts', []))} ({recent.get('highest_alert_severity', 'none')})\n"
        f"  • Self-improvement mode: {self_improvement.get('mode')}\n"
        f"  • Latest run: {self_improvement.get('latest_run_id') or 'none'} ({self_improvement.get('latest_state') or 'idle'})\n"
        f"  • Last accepted run: {self_improvement.get('last_accepted_run') or 'none'}\n"
        f"  • Last rollback reason: {self_improvement.get('last_rollback_reason') or 'none'}\n"
        f"  • Executable actions: {commands_preview}"
    )


OPS_HANDLERS = {
    "_handle_generate": _handle_generate,
    "_handle_edit": _handle_edit,
    "_handle_autofix": _handle_autofix,
    "_handle_multi_agent": _handle_multi_agent,
    "_handle_agent_route": _handle_agent_route,
    "_handle_custom_llm": _handle_custom_llm,
    "_handle_help_summary": _handle_help_summary,
    "_handle_self_aware_summary": _handle_self_aware_summary,
    "_handle_clarify": _handle_clarify,
}
