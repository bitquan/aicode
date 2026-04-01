from src.tools.budget_tracker import read_metrics


def summarize_costs_by_trace(workspace_root: str, limit: int = 200) -> dict:
    rows = read_metrics(workspace_root, limit=limit)
    grouped = {}
    for row in rows:
        trace_id = row.get("trace_id")
        if not trace_id:
            continue
        grouped.setdefault(trace_id, {"events": 0, "estimated_cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0})
        grouped[trace_id]["events"] += 1
        grouped[trace_id]["estimated_cost_usd"] += float(row.get("estimated_cost_usd", 0.0))
        grouped[trace_id]["input_tokens"] += int(row.get("input_tokens", 0))
        grouped[trace_id]["output_tokens"] += int(row.get("output_tokens", 0))

    traces = [
        {
            "trace_id": trace_id,
            "events": data["events"],
            "input_tokens": data["input_tokens"],
            "output_tokens": data["output_tokens"],
            "estimated_cost_usd": round(data["estimated_cost_usd"], 8),
        }
        for trace_id, data in grouped.items()
    ]
    traces.sort(key=lambda row: row["estimated_cost_usd"], reverse=True)

    return {
        "trace_count": len(traces),
        "traces": traces,
        "estimated_total_cost_usd": round(sum(row["estimated_cost_usd"] for row in traces), 8),
    }
