def build_task_plan(request: str) -> dict:
    words = [word for word in request.strip().split() if word]
    short = " ".join(words[:6]) if words else "task"
    steps = [
        f"Clarify scope for: {short}",
        "Inspect relevant files and dependencies",
        "Implement minimal safe change set",
        "Run targeted verification",
        "Summarize results and next actions",
    ]
    return {
        "request": request,
        "steps": steps,
        "status": "planned",
    }
