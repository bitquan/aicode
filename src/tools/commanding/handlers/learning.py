"""Learning, memory, and self-improvement handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.tools.commanding import ActionResponse
from src.tools.learned_preferences import add_preference, apply_correction, clear_preferences
from src.tools.learning_metrics import build_learning_metrics
from src.tools.project_memory import remember_note
from src.tools.self_improve import (
    apply_self_improvement_run,
    build_self_improvement_status_snapshot,
    create_self_improvement_plan,
    format_self_improvement_run,
    get_latest_self_improvement_run,
    get_self_improvement_run,
)

if TYPE_CHECKING:
    from src.tools.chat_engine import ChatEngine


def _handle_user_learn(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Persist explicit user lesson into project + team memory stores."""
    lesson = request.get("lesson", "").strip()
    if not lesson:
        return "⚠️ I can learn from your input, but I need a lesson. Try: `learn: always run targeted tests first`."

    remember_note(str(engine.workspace_root), key="lesson", value=lesson)
    category = engine._infer_preference_category(lesson)
    preference = add_preference(
        workspace_root=str(engine.workspace_root),
        statement=lesson,
        category=category,
        user_scope="project",
        origin_prompt=f"learn: {lesson}",
        confidence=0.85,
    )
    engine.team_knowledge_base.add_entry(
        topic="user_input",
        note=lesson,
        author="user",
        tags=["learning", "feedback"],
    )
    engine._log_interaction(f"learn: {lesson}", "user_learn", True)

    return (
        "🧠 Learned from your input\n"
        f"  • Saved lesson: {lesson}\n"
        f"  • Preference ID: {preference['preference_id']} ({category})\n"
        "  • Stored in project memory + team knowledge base\n"
        "  • Use `team kb user_input` to recall saved lessons"
    )


def _handle_user_correct(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Apply correction updates to learned preferences."""
    correction_type = str(request.get("correction_type", "replace"))
    correction_text = str(request.get("correction_text", "")).strip()
    target_preference_id = request.get("target_preference_id")

    if correction_type == "replace" and not correction_text:
        return "⚠️ Provide correction text. Example: `correct: prefer concise responses and always include tests run`."

    result = apply_correction(
        workspace_root=str(engine.workspace_root),
        correction_type=correction_type,
        correction_text=correction_text,
        target_preference_id=target_preference_id,
    )
    engine._log_interaction(f"correction: {correction_type}", "user_correct", bool(result.get("updated")))

    if not result.get("updated"):
        return "⚠️ No active preference found to update. Add a lesson first with `learn:`."

    created = result.get("created_preference")
    created_text = ""
    if created:
        created_text = f"\n  • New preference: {created.get('preference_id')}"

    return (
        "🔁 Preference correction applied\n"
        f"  • Type: {correction_type}\n"
        f"  • Target: {result.get('target_preference_id') or 'latest active'}"
        f"{created_text}"
    )


def _handle_clear_preferences(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Deactivate learned preferences for project-level reset controls."""
    result = clear_preferences(str(engine.workspace_root))
    cleared = int(result.get("cleared", 0))
    engine._log_interaction("clear preferences", "clear_preferences", True)
    return (
        "🧹 Cleared learned preferences\n"
        f"  • Deactivated: {cleared}\n"
        "  • Future generate/autofix calls will run without preference injection until you add new lessons"
    )


def _handle_learn(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Trigger self-improvement cycle based on learned interactions."""
    print("\n📚 Analyzing interactions and building knowledge...\n", flush=True)

    if engine.interaction_log:
        print(f"📊 Processing {len(engine.interaction_log)} interactions...", flush=True)
        engine.self_builder.learn_from_logs(engine.interaction_log)

    plan = engine.self_builder.generate_self_improvement_plan(engine.interaction_log)
    kb = engine.self_builder.export_knowledge_base()

    result = f"""✨ Self-Improvement Complete!

📈 Learning Results:
  • Success Rate: {kb['metrics'].get('success_rate', 0):.1%}
  • Total Interactions: {kb['metrics'].get('interaction_count', 0)}
  • Solutions Cached: {len(kb['solutions'])}
  • Strategies Learned: {len(kb['strategies'])}

🎯 Improvement Plan:
  • Current Success Rate: {plan['current_success_rate']:.1%}
  • Target: {plan['target_success_rate']:.1%}
  • Estimated Cycles Needed: {plan['estimated_cycles']}

💡 Recommendations:
"""

    suggestions = engine.self_builder.get_improvement_suggestions()
    for suggestion in suggestions:
        result += f"  • {suggestion}\n"

    result += """
✅ Knowledge Base:
  • Solutions can guide future code generation
  • Strategies optimize action selection
  • Patterns prevent repeated failures
  • Context-aware responses improve over time
"""

    return result


def _handle_self_build(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Run structured self-improvement cycles driven by status report gaps."""
    cycles = max(1, min(int(request.get("cycles", 1)), 5))
    target_score = 95.0
    summary = engine._run_self_improvement_cycles(
        cycles=cycles,
        target_score=target_score,
        report_timeout_seconds=8.0,
    )

    if not summary.get("results"):
        return "⚠️ Self-build did not produce cycle results."

    latest = summary["results"][-1]
    actions = latest.get("actions", [])[:5]
    action_lines = "\n".join(f"  • {item}" for item in actions) if actions else "  • No immediate actions"

    return (
        "🛠️ Self-Build Cycle Complete\n\n"
        f"  • Cycles requested: {summary.get('cycles_requested', cycles)}\n"
        f"  • Cycles run: {summary.get('cycles_run', 0)}\n"
        f"  • Target score: {summary.get('target_score', target_score):.1f}\n"
        f"  • Latest score: {float(latest.get('score', 0.0)):.1f}\n"
        f"  • Readiness: {latest.get('readiness', 'unknown')}\n"
        f"  • Converged: {'yes' if summary.get('converged') else 'no'}\n\n"
        "🎯 Next Self-Build Actions:\n"
        f"{action_lines}"
    )


def _handle_self_improve_plan(engine: "ChatEngine", request: dict[str, Any]) -> ActionResponse:
    """Create a supervised self-improvement proposal without applying changes."""
    goal = str(request.get("goal", "")).strip()
    run = create_self_improvement_plan(
        str(engine.workspace_root),
        engine,
        goal=goal,
        prefer_web=bool(request.get("prefer_web", False)),
        source="command",
    )
    engine._log_interaction(goal or "self-improve plan", "self_improve_plan", True)
    return ActionResponse(
        action="self_improve_plan",
        text=format_self_improvement_run(run),
        confidence=0.96,
        result_status="success",
        data={
            "run_id": run["run_id"],
            "mode": run["mode"],
            "state": run["state"],
            "goal": run["goal"],
            "candidate_summary": run["candidate_summary"],
            "likely_files": [item["path"] for item in run.get("likely_files", [])],
            "verification_plan": run.get("verification_plan", []),
            "web_research_used": bool(run.get("web_research_used", False)),
            "rollback_performed": bool(run.get("rollback_performed", False)),
            "events": run.get("events", []),
        },
    )


def _handle_self_improve_run(engine: "ChatEngine", request: dict[str, Any]) -> ActionResponse:
    """Supervised run entrypoint; in v1 this returns a proposal until explicitly approved."""
    response = _handle_self_improve_plan(engine, request)
    response.action = "self_improve_run"
    response.text += "\n\n  • Supervised mode: approval is required before apply. Use `approve self-improve <run_id>`."
    return response


def _handle_self_improve_apply(engine: "ChatEngine", request: dict[str, Any]) -> ActionResponse:
    """Apply an approved self-improvement proposal with bounded verification and rollback."""
    run_id = str(request.get("run_id", "")).strip()
    if not run_id:
        return ActionResponse.from_text(
            action="self_improve_apply",
            text="⚠️ I need a run id. Try: `approve self-improve <run_id>`.",
            confidence=0.96,
        )

    run = apply_self_improvement_run(str(engine.workspace_root), engine, run_id)
    success = run.get("state") == "verified"
    engine._log_interaction(f"approve self-improve {run_id}", "self_improve_apply", success)
    result_status = "success" if run.get("state") == "verified" else "failure" if run.get("state") == "rolled_back" else "partial"
    return ActionResponse(
        action="self_improve_apply",
        text=format_self_improvement_run(run),
        confidence=0.97,
        result_status=result_status,
        data={
            "run_id": run.get("run_id"),
            "mode": run.get("mode", build_self_improvement_status_snapshot(str(engine.workspace_root)).get("mode")),
            "state": run.get("state"),
            "goal": run.get("goal", ""),
            "candidate_summary": run.get("candidate_summary", ""),
            "likely_files": [item["path"] for item in run.get("likely_files", [])],
            "verification_plan": run.get("verification_plan", []),
            "web_research_used": bool(run.get("web_research_used", False)),
            "rollback_performed": bool(run.get("rollback_performed", False)),
            "events": run.get("events", []),
        },
    )


def _handle_self_improve_status(engine: "ChatEngine", request: dict[str, Any]) -> ActionResponse:
    """Show the latest or requested self-improvement run."""
    run_id = str(request.get("run_id", "")).strip()
    if run_id:
        run = get_self_improvement_run(str(engine.workspace_root), run_id)
    else:
        run = get_latest_self_improvement_run(str(engine.workspace_root))

    if not run:
        snapshot = build_self_improvement_status_snapshot(str(engine.workspace_root))
        text = (
            "♻️ Self-Improvement Status\n"
            f"  • Mode: {snapshot.get('mode')}\n"
            "  • No runs recorded yet.\n"
            "  • Next step: `self-improve plan <goal>`"
        )
        data = {
            "run_id": None,
            "mode": snapshot.get("mode"),
            "state": None,
            "goal": "",
            "candidate_summary": "",
            "likely_files": [],
            "verification_plan": [],
            "web_research_used": False,
            "rollback_performed": False,
            "events": [],
        }
    else:
        text = format_self_improvement_run(run)
        data = {
            "run_id": run.get("run_id"),
            "mode": run.get("mode"),
            "state": run.get("state"),
            "goal": run.get("goal", ""),
            "candidate_summary": run.get("candidate_summary", ""),
            "likely_files": [item["path"] for item in run.get("likely_files", [])],
            "verification_plan": run.get("verification_plan", []),
            "web_research_used": bool(run.get("web_research_used", False)),
            "rollback_performed": bool(run.get("rollback_performed", False)),
            "events": run.get("events", []),
        }

    engine._log_interaction("self-improve status", "self_improve_status", True)
    return ActionResponse(
        action="self_improve_status",
        text=text,
        confidence=0.95,
        result_status="success",
        data=data,
    )


def _handle_knowledge_transfer(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Export/import knowledge base for sharing."""
    mode = request.get("mode", "export")
    if mode == "export":
        result = engine.knowledge_transfer.export_bundle("knowledge_export.json")
        engine._log_interaction("export knowledge", "knowledge_transfer", True)
        return f"✅ Knowledge exported to {result.get('path')} ({result.get('file_count')} files)"

    bundle = request.get("bundle", "knowledge_export.json")
    result = engine.knowledge_transfer.import_bundle(bundle)
    if "error" in result:
        engine._log_interaction(f"import knowledge {bundle}", "knowledge_transfer", False)
        return f"❌ {result['error']}"
    engine._log_interaction(f"import knowledge {bundle}", "knowledge_transfer", True)
    return f"✅ Knowledge imported from {result.get('bundle')} ({result.get('imported_files')} files)"


def _handle_prompt_lab(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Show prompt strategy metrics and recommendation."""
    summary = engine.prompt_lab.summarize()
    recommendation = engine.prompt_lab.recommend_strategy("general coding task")

    lines = [
        "🧪 Prompt Lab",
        f"  • Total Runs: {summary.get('total_runs', 0)}",
        f"  • Overall Success: {summary.get('overall_success_rate', 0):.1%}",
        f"  • Recommended Strategy: {recommendation.get('strategy')} ({recommendation.get('reason')})",
    ]
    engine._log_interaction("prompt lab", "prompt_lab", True)
    return "\n".join(lines)


def _handle_tool_builder(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Create a custom tool scaffold."""
    name = request.get("name", "custom_tool")
    result = engine.tool_builder.create_tool(name, f"Generated tool: {name}")
    if "error" in result:
        engine._log_interaction(f"build tool {name}", "tool_builder", False)
        return f"❌ {result['error']}"

    engine._log_interaction(f"build tool {name}", "tool_builder", True)
    return f"✅ Tool created: {result['tool']} with test {result['test']}"


def _handle_learning_metrics(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Show baseline learning quality metrics from local telemetry."""
    metrics = build_learning_metrics(str(engine.workspace_root), limit=1000)
    routing = metrics.get("routing_accuracy", {})
    preference = metrics.get("preference_hit_rate", {})
    correction = metrics.get("correction_success_rate", {})
    sizes = metrics.get("sample_sizes", {})

    engine._log_interaction("learning metrics", "learning_metrics", True)
    return (
        "📈 Learning Metrics Harness\n"
        f"  • Prompt events: {sizes.get('prompt_events', 0)}\n"
        f"  • Output traces: {sizes.get('output_traces', 0)}\n"
        f"  • Correction events: {sizes.get('correction_events', 0)}\n"
        f"  • Routing accuracy: {routing.get('accuracy_pct', 0.0)}% "
        f"({routing.get('correct', 0)}/{routing.get('eligible', 0)})\n"
        f"  • Preference hit rate: {preference.get('hit_rate_pct', 0.0)}% "
        f"({preference.get('hits', 0)}/{preference.get('eligible', 0)})\n"
        f"  • Correction success rate: {correction.get('success_rate_pct', 0.0)}% "
        f"({correction.get('successful', 0)}/{correction.get('total', 0)})"
    )


def _handle_agent_memory(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Share or recall multi-agent memory."""
    mode = request.get("mode", "recall")
    topic = request.get("topic", "")
    if mode == "share":
        note = request.get("note", "")
        result = engine.agent_memory.share("chat", topic or "general", note)
        engine._log_interaction(f"agent memory share {topic}", "agent_memory", True)
        return f"✅ Shared Agent Memory: {result.get('entries')} total entries"

    recalled = engine.agent_memory.recall(topic=topic or None)
    engine._log_interaction(f"agent memory {topic}", "agent_memory", True)
    lines = [
        "🧠 Shared Agent Memory",
        f"  • Matches: {recalled.get('count', 0)}",
    ]
    for entry in recalled.get("entries", [])[:5]:
        lines.append(f"  • {entry.get('agent')}: {entry.get('topic')} -> {entry.get('note')}")
    return "\n".join(lines)


LEARNING_HANDLERS = {
    "_handle_user_learn": _handle_user_learn,
    "_handle_user_correct": _handle_user_correct,
    "_handle_clear_preferences": _handle_clear_preferences,
    "_handle_learn": _handle_learn,
    "_handle_self_build": _handle_self_build,
    "_handle_self_improve_plan": _handle_self_improve_plan,
    "_handle_self_improve_run": _handle_self_improve_run,
    "_handle_self_improve_apply": _handle_self_improve_apply,
    "_handle_self_improve_status": _handle_self_improve_status,
    "_handle_knowledge_transfer": _handle_knowledge_transfer,
    "_handle_prompt_lab": _handle_prompt_lab,
    "_handle_tool_builder": _handle_tool_builder,
    "_handle_learning_metrics": _handle_learning_metrics,
    "_handle_agent_memory": _handle_agent_memory,
}
