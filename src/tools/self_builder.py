"""
Self-improvement system that learns from chat interactions and builds specialized knowledge.
The chat system improves itself by analyzing patterns and building a custom knowledge base.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import Counter


logger = logging.getLogger(__name__)


class SelfBuilder:
    """Analyzes interactions and builds specialized knowledge for continuous improvement."""
    
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root)
        self.kb_dir = self.workspace_root / ".knowledge_base"
        self.kb_dir.mkdir(exist_ok=True)
        
        self.patterns_file = self.kb_dir / "patterns.json"
        self.solutions_file = self.kb_dir / "solutions.json"
        self.strategies_file = self.kb_dir / "strategies.json"
        self.metrics_file = self.kb_dir / "metrics.json"
        
        self.patterns = self._load_json(self.patterns_file)
        self.solutions = self._load_json(self.solutions_file)
        self.strategies = self._load_json(self.strategies_file)
        self.metrics = self._load_json(self.metrics_file)
    
    def _load_json(self, filepath: Path) -> Dict:
        """Load JSON file or return empty dict."""
        try:
            if filepath.exists():
                with open(filepath) as f:
                    return json.load(f)
        except Exception as exc:
            logger.warning(
                "event=self_builder_load_json_failed filepath=%s error=%s",
                filepath,
                exc,
            )
        return {}
    
    def _save_json(self, filepath: Path, data: Dict):
        """Save JSON file."""
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as exc:
            logger.warning(
                "event=self_builder_save_json_failed filepath=%s error=%s",
                filepath,
                exc,
            )
    
    def analyze_interactions(self, logs: List[Dict]) -> Dict:
        """Analyze interaction logs to extract patterns and insights."""
        analysis = {
            "total_interactions": len(logs),
            "success_rate": 0.0,
            "action_breakdown": {},
            "common_queries": [],
            "failed_patterns": [],
            "successful_patterns": [],
            "recommendations": []
        }
        
        if not logs:
            return analysis
        
        successful = sum(1 for log in logs if log.get("success", False))
        analysis["success_rate"] = successful / len(logs) if logs else 0.0
        
        # Breakdown by action type
        actions = [log.get("action") for log in logs]
        analysis["action_breakdown"] = dict(Counter(actions))
        
        # Find common query patterns
        queries = [log.get("query", "")[:50] for log in logs if log.get("query")]
        analysis["common_queries"] = [q for q, _ in Counter(queries).most_common(5)]
        
        # Separate successful and failed
        for log in logs:
            query = log.get("query", "")
            if log.get("success"):
                analysis["successful_patterns"].append({
                    "query": query,
                    "action": log.get("action"),
                    "doc_context": bool(log.get("doc_context"))
                })
            else:
                analysis["failed_patterns"].append({
                    "query": query,
                    "action": log.get("action"),
                    "reason": "no doc context" if not log.get("doc_context") else "unknown"
                })
        
        # Generate recommendations
        analysis["recommendations"] = self._generate_recommendations(analysis)
        
        return analysis
    
    def _generate_recommendations(self, analysis: Dict) -> List[str]:
        """Generate improvement recommendations based on analysis."""
        recommendations = []
        
        if analysis["success_rate"] < 0.7:
            recommendations.append("success_rate_low: Increase doc context for failures")
        
        if len(analysis["successful_patterns"]) > 0:
            recommendations.append("build_templates: Create code templates from successful patterns")
        
        if analysis["failed_patterns"]:
            recommendations.append("fix_failures: Analyze why these patterns failed and retry")
        
        if "search" in analysis["action_breakdown"]:
            recommendations.append("search_optimization: Build indexed search cache for common queries")
        
        return recommendations
    
    def extract_solutions(self, logs: List[Dict]) -> Dict[str, str]:
        """Extract reusable solutions from successful interactions."""
        solutions = {}
        
        for log in logs:
            if log.get("success") and log.get("action") in ["generate", "autofix"]:
                query = log.get("query", "").lower()
                
                # Extract common solution patterns
                if "function" in query or "write" in query:
                    key = f"solution:code_generation"
                    solutions[key] = "Successfully generates code with doc context"
                
                if "fix" in query or "autofix" in query:
                    key = f"solution:autofix"
                    solutions[key] = "Successfully fixes code with multiple attempts"
                
                if "search" in query:
                    key = f"solution:semantic_search"
                    solutions[key] = "Successfully finds relevant code patterns"
        
        return solutions
    
    def build_strategies(self, analysis: Dict) -> Dict[str, Dict]:
        """Build optimized strategies based on analysis."""
        strategies = {}
        
        # Strategy for high-success actions
        for action, count in analysis["action_breakdown"].items():
            if count > 0:
                success_count = len([
                    p for p in analysis["successful_patterns"]
                    if p.get("action") == action
                ])
                success_rate = success_count / count if count > 0 else 0
                
                strategies[f"optimize:{action}"] = {
                    "success_rate": success_rate,
                    "usage_count": count,
                    "recommendation": "improve" if success_rate < 0.8 else "maintain"
                }
        
        return strategies
    
    def build_code_templates(self, logs: List[Dict]) -> Dict[str, str]:
        """Build reusable code templates from successful generations."""
        templates = {}
        
        for log in logs:
            if log.get("success") and log.get("action") == "generate":
                query = log.get("query", "").lower()
                
                # Smart template extraction based on query patterns
                if "http" in query or "request" in query:
                    templates["http_client"] = """
import requests

def make_request(url, method='GET', **kwargs):
    try:
        response = requests.request(method, url, timeout=5, **kwargs)
        response.raise_for_status()
        return response.json() if response.text else None
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None
"""
                
                if "list" in query or "sort" in query or "filter" in query:
                    templates["data_transform"] = """
def transform_data(items, key=None, reverse=False):
    return sorted(items, key=key, reverse=reverse)

def filter_data(items, condition):
    return [item for item in items if condition(item)]
"""
                
                if "test" in query or "unittest" in query:
                    templates["test_framework"] = """
import pytest

def test_basic():
    result = function_under_test()
    assert result is not None

@pytest.fixture
def setup():
    return {"data": []}
"""
        
        return templates
    
    def get_specialized_prompt(self, query: str, analysis: Dict) -> str:
        """Generate a specialized prompt based on learned patterns."""
        base = f"Task: {query}\n\n"
        
        # Add context from successful patterns
        if analysis.get("successful_patterns"):
            base += "Similar successful patterns:\n"
            for pattern in analysis["successful_patterns"][:2]:
                base += f"  • {pattern.get('query')}\n"
            base += "\n"
        
        # Add learned strategies
        if analysis.get("action_breakdown"):
            base += "Preferred approaches (by success rate):\n"
            for action in analysis["action_breakdown"].keys():
                base += f"  • {action} is effective for this codebase\n"
        
        return base
    
    def learn_from_logs(self, logs: List[Dict]):
        """Main method to learn from interaction logs and build knowledge."""
        if not logs:
            return
        
        # Analyze interactions
        analysis = self.analyze_interactions(logs)
        
        # Extract and save solutions
        solutions = self.extract_solutions(logs)
        self.solutions.update(solutions)
        self._save_json(self.solutions_file, self.solutions)
        
        # Build and save strategies
        strategies = self.build_strategies(analysis)
        self.strategies.update(strategies)
        self._save_json(self.strategies_file, self.strategies)
        
        # Update patterns
        self.patterns["analysis"] = analysis
        self.patterns["timestamp"] = datetime.now().isoformat()
        self.patterns["total_learned_from"] = len(logs)
        self._save_json(self.patterns_file, self.patterns)
        
        # Update metrics
        self.metrics["success_rate"] = analysis["success_rate"]
        self.metrics["last_updated"] = datetime.now().isoformat()
        self.metrics["interaction_count"] = analysis["total_interactions"]
        self._save_json(self.metrics_file, self.metrics)
    
    def get_improvement_suggestions(self) -> List[str]:
        """Get suggestions for how the system can improve itself."""
        suggestions = []
        
        if self.patterns.get("analysis"):
            analysis = self.patterns["analysis"]
            suggestions.extend(analysis.get("recommendations", []))
        
        if self.metrics.get("success_rate", 0) < 0.8:
            suggestions.append("Run self-improve cycle to boost success rate")
        
        if self.solutions:
            suggestions.append(f"You have {len(self.solutions)} cached solutions - use them!")
        
        if self.strategies:
            suggestions.append(f"Learned {len(self.strategies)} specialized strategies")
        
        return suggestions
    
    def export_knowledge_base(self) -> Dict:
        """Export all learned knowledge as a structured knowledge base."""
        return {
            "patterns": self.patterns,
            "solutions": self.solutions,
            "strategies": self.strategies,
            "metrics": self.metrics,
            "export_date": datetime.now().isoformat()
        }
    
    def generate_self_improvement_plan(self, logs: List[Dict]) -> Dict:
        """Generate a plan for the system to improve itself."""
        analysis = self.analyze_interactions(logs)
        
        plan = {
            "status": "ready",
            "current_success_rate": analysis["success_rate"],
            "target_success_rate": 0.95,
            "actions": [],
            "estimated_cycles": 0
        }
        
        if analysis["success_rate"] < 0.95:
            plan["actions"].append({
                "priority": "high",
                "action": "improve_failed_patterns",
                "reason": f"Success rate {analysis['success_rate']:.1%} below target 95%"
            })
            plan["actions"].append({
                "priority": "medium",
                "action": "build_solution_cache",
                "reason": f"Cache {len(analysis['successful_patterns'])} successful patterns"
            })
            plan["actions"].append({
                "priority": "low",
                "action": "optimize_strategy",
                "reason": f"Refine strategies for {len(analysis['action_breakdown'])} action types"
            })
            
            gap = 0.95 - analysis["success_rate"]
            plan["estimated_cycles"] = max(1, int(gap * 10))
        
        return plan

    def record_run_outcome(
        self,
        *,
        run_id: str,
        state: str,
        goal: str,
        category: str,
        rollback_performed: bool = False,
        verification_passed: bool = False,
    ) -> None:
        """Persist recent self-improvement outcomes for future scoring feedback."""
        outcomes = self.metrics.setdefault("self_improvement_outcomes", [])
        outcomes.append(
            {
                "run_id": run_id,
                "state": state,
                "goal": goal,
                "category": category,
                "rollback_performed": rollback_performed,
                "verification_passed": verification_passed,
                "timestamp": datetime.now().isoformat(),
            }
        )
        self.metrics["self_improvement_outcomes"] = outcomes[-50:]
        self.metrics["last_self_improvement_state"] = state
        self._save_json(self.metrics_file, self.metrics)
