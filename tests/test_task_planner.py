from src.tools.task_planner import build_task_plan


def test_build_task_plan_has_steps():
    plan = build_task_plan("implement safe edit flow")
    assert plan["status"] == "planned"
    assert len(plan["steps"]) == 5
