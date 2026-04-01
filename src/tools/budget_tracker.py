import json
from pathlib import Path


DEFAULT_BUDGETS = {
    "max_autofix_seconds": 120.0,
    "max_gate_seconds": 90.0,
    "max_autofix_attempts": 4,
    "usd_per_1k_input_tokens": 0.0002,
    "usd_per_1k_output_tokens": 0.0006,
    "max_daily_cost_usd": 1.0,
}


def _budget_config_path(workspace_root: str) -> Path:
    root = Path(workspace_root).resolve()
    out_dir = root / ".autofix_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "budget_config.json"


def _metrics_path(workspace_root: str) -> Path:
    root = Path(workspace_root).resolve()
    out_dir = root / ".autofix_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "budget_metrics.jsonl"


def load_budget_config(workspace_root: str) -> dict:
    path = _budget_config_path(workspace_root)
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_BUDGETS, indent=2), encoding="utf-8")
        return dict(DEFAULT_BUDGETS)
    data = json.loads(path.read_text(encoding="utf-8"))
    return {**DEFAULT_BUDGETS, **data}


def set_budget_value(workspace_root: str, key: str, value: float) -> dict:
    config = load_budget_config(workspace_root)
    config[key] = value
    _budget_config_path(workspace_root).write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_cost_usd(workspace_root: str, input_tokens: int, output_tokens: int) -> float:
    config = load_budget_config(workspace_root)
    in_cost = (max(0, input_tokens) / 1000.0) * float(config["usd_per_1k_input_tokens"])
    out_cost = (max(0, output_tokens) / 1000.0) * float(config["usd_per_1k_output_tokens"])
    return round(in_cost + out_cost, 8)


def record_metric(
    workspace_root: str,
    workflow: str,
    duration_seconds: float,
    success: bool,
    attempts: int | None = None,
    metadata: dict | None = None,
):
    payload = {
        "workflow": workflow,
        "duration_seconds": round(float(duration_seconds), 4),
        "success": bool(success),
    }
    if attempts is not None:
        payload["attempts"] = int(attempts)
    if metadata:
        payload.update(metadata)
    path = _metrics_path(workspace_root)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")
    return payload


def record_model_usage(
    workspace_root: str,
    model: str,
    prompt: str,
    response: str,
    success: bool,
    trace_id: str | None = None,
):
    input_tokens = estimate_tokens(prompt)
    output_tokens = estimate_tokens(response)
    cost = estimate_cost_usd(workspace_root, input_tokens=input_tokens, output_tokens=output_tokens)
    metadata = {
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": cost,
    }
    if trace_id:
        metadata["trace_id"] = trace_id

    return record_metric(
        workspace_root=workspace_root,
        workflow="model_inference",
        duration_seconds=0.0,
        success=success,
        metadata=metadata,
    )


def read_metrics(workspace_root: str, limit: int = 50) -> list[dict]:
    path = _metrics_path(workspace_root)
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows[-limit:]


def evaluate_budgets(workspace_root: str) -> dict:
    config = load_budget_config(workspace_root)
    rows = read_metrics(workspace_root, limit=200)

    latest_autofix = next((row for row in reversed(rows) if row.get("workflow") == "autofix"), None)
    latest_gate = next((row for row in reversed(rows) if row.get("workflow") == "gate"), None)

    checks = {
        "autofix_duration_ok": True,
        "gate_duration_ok": True,
        "autofix_attempts_ok": True,
    }

    if latest_autofix:
        checks["autofix_duration_ok"] = latest_autofix.get("duration_seconds", 0) <= config["max_autofix_seconds"]
        checks["autofix_attempts_ok"] = latest_autofix.get("attempts", 0) <= config["max_autofix_attempts"]

    if latest_gate:
        checks["gate_duration_ok"] = latest_gate.get("duration_seconds", 0) <= config["max_gate_seconds"]

    total_cost = sum(float(row.get("estimated_cost_usd", 0.0)) for row in rows)
    checks["daily_cost_ok"] = total_cost <= float(config["max_daily_cost_usd"])

    return {
        "config": config,
        "latest_autofix": latest_autofix,
        "latest_gate": latest_gate,
        "estimated_total_cost_usd": round(total_cost, 8),
        "checks": checks,
        "passed": all(checks.values()),
    }


def summarize_costs(workspace_root: str) -> dict:
    rows = read_metrics(workspace_root, limit=1000)
    model_rows = [row for row in rows if row.get("workflow") == "model_inference"]
    total_input = sum(int(row.get("input_tokens", 0)) for row in model_rows)
    total_output = sum(int(row.get("output_tokens", 0)) for row in model_rows)
    total_cost = sum(float(row.get("estimated_cost_usd", 0.0)) for row in model_rows)
    return {
        "inference_events": len(model_rows),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "estimated_total_cost_usd": round(total_cost, 8),
    }
