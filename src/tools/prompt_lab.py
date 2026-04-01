"""Prompt Engineering Lab for tracking prompt outcomes and strategy quality."""

import json
from pathlib import Path
from typing import Dict, List


class PromptLab:
    """Records prompt experiments and recommends strategies."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self.store_path = self.workspace_root / ".knowledge_base" / "prompt_lab.json"
        self.store_path.parent.mkdir(exist_ok=True)
        self._data = self._load()

    def _load(self) -> Dict:
        if self.store_path.exists():
            try:
                with open(self.store_path) as handle:
                    return json.load(handle)
            except Exception:
                pass
        return {"runs": []}

    def _save(self):
        with open(self.store_path, "w") as handle:
            json.dump(self._data, handle, indent=2)

    def record_run(self, prompt: str, strategy: str, success: bool, latency_ms: int = 0) -> Dict:
        run = {
            "prompt": prompt[:300],
            "strategy": strategy,
            "success": bool(success),
            "latency_ms": int(latency_ms),
        }
        self._data["runs"].append(run)
        self._save()
        return {"status": "recorded", "total_runs": len(self._data["runs"])}

    def summarize(self) -> Dict:
        runs = self._data.get("runs", [])
        if not runs:
            return {"total_runs": 0, "overall_success_rate": 0.0, "by_strategy": {}}

        by_strategy: Dict[str, Dict] = {}
        for run in runs:
            strategy = run["strategy"]
            item = by_strategy.setdefault(strategy, {"runs": 0, "success": 0, "latency_total": 0})
            item["runs"] += 1
            item["success"] += 1 if run["success"] else 0
            item["latency_total"] += run.get("latency_ms", 0)

        summary = {}
        for strategy, stats in by_strategy.items():
            summary[strategy] = {
                "runs": stats["runs"],
                "success_rate": stats["success"] / stats["runs"] if stats["runs"] else 0.0,
                "avg_latency_ms": int(stats["latency_total"] / stats["runs"]) if stats["runs"] else 0,
            }

        overall_success = sum(1 for r in runs if r["success"]) / len(runs)
        return {
            "total_runs": len(runs),
            "overall_success_rate": overall_success,
            "by_strategy": summary,
        }

    def recommend_strategy(self, task_text: str) -> Dict:
        summary = self.summarize()
        by_strategy = summary.get("by_strategy", {})

        if not by_strategy:
            return {"strategy": "baseline", "reason": "no historical runs"}

        ranked = sorted(
            by_strategy.items(),
            key=lambda pair: (pair[1]["success_rate"], -pair[1]["avg_latency_ms"], pair[1]["runs"]),
            reverse=True,
        )

        best = ranked[0]
        reason = "highest success rate"
        if "test" in task_text.lower():
            reason = f"best observed for general tasks; recommended for testing context"

        return {
            "strategy": best[0],
            "reason": reason,
            "confidence": round(best[1]["success_rate"], 2),
        }
