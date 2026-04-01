import json
from pathlib import Path


DEFAULT_BUDGETS = {
    "max_autofix_seconds": 120.0,
    "max_gate_seconds": 90.0,
    "max_autofix_attempts": 4,
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


def record_metric(workspace_root: str, workflow: str, duration_seconds: float, success: bool, attempts: int | None = None):
    payload = {
        "workflow": workflow,
        "duration_seconds": round(float(duration_seconds), 4),
        "success": bool(success),
    }
    if attempts is not None:
        payload["attempts"] = int(attempts)
    path = _metrics_path(workspace_root)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")
    return payload


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

    return {
        "config": config,
        "latest_autofix": latest_autofix,
        "latest_gate": latest_gate,
        "checks": checks,
        "passed": all(checks.values()),
    }
