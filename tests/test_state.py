"""Tests for Pydantic state serialization."""

from models.state import AgentState, PlannerResult


def test_agent_state_roundtrip() -> None:
    state = AgentState(
        repo_path="/tmp/repo",
        task_description="Fix validation",
        planner_result=PlannerResult(
            understanding="Bad message",
            files_to_investigate=["validators.py"],
            plan=["Read validators"],
        ),
    )
    data = state.to_graph_dict()
    restored = AgentState.from_graph_dict(data)
    assert restored.task_description == state.task_description
    assert restored.planner_result is not None
    assert restored.planner_result.files_to_investigate == ["validators.py"]
